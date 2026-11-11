"""채팅 스트리밍 — Foundry Responses 스트림 이벤트를 프런트엔드용 SSE 이벤트로 번역합니다.

프런트엔드가 받는 이벤트(JSON, 한 줄씩 `data: ...`):
  start      {conversation_id, agent, model}
  pii        {entities:[{category,label,text}], redacted}          개인정보 자동 마스킹 결과
  step       {id, kind, title, status: running|done, detail, ms}  에이전트가 일하는 과정(검색·코드·MCP·함수·웹검색·추론)
  text       {delta}
  final      {text, citations:[…], files:[…]}                       출처·생성 파일이 반영된 최종 답변
  approval   {conversation_id, agent, calls:[{call_id, name, arguments, title}]}   사람 승인 대기 (Human-in-the-loop)
  blocked    {reason, detail}                                        가드레일 차단
  usage      {model, input_tokens, output_tokens, reasoning_tokens, latency_ms, ttft_ms}
  error      {message}
  done       {}
"""
from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any, AsyncIterator

import openai

from . import safety, tools_local
from .agents_def import APPROVAL_REQUIRED, spec_by_key
from .config import settings
from .foundry import foundry
from .i18n import pick

log = logging.getLogger("chat")

MAX_ROUNDS = 6
GENERAL_INSTRUCTIONS = pick(
    "당신은 Contoso(주) 임직원을 돕는 AI 어시스턴트입니다. 한국어로 명확하고 간결하게 답하세요. "
    "글쓰기·요약·번역·분석·아이디어 같은 일반 업무 요청은 사내 자료 없이도 바로 작성해 주세요(예: 고객에게 보낼 사과 문자 초안). "
    "사내 규정이나 제도 자체를 묻는 질문일 때만 'Contoso Guide' 에이전트를 안내하세요. 모르는 사실은 추측하지 마세요.",
    "You are an AI assistant that helps employees of Contoso Ltd. Answer clearly and concisely in English. "
    "Handle general work requests such as writing, summarizing, translating, analysis and brainstorming directly, without needing internal documents "
    "(for example, drafting an apology text message to send to a customer). "
    "Point to the 'Contoso Guide' agent only when the question is about company policies or procedures themselves. Do not guess facts you do not know.",
)


@dataclass
class Turn:
    """한 번의 응답 스트림에서 모은 값."""
    response_id: str = ""
    model: str = ""
    usage: dict[str, int] = field(default_factory=dict)
    first_token_at: float | None = None
    calls: list[dict[str, Any]] = field(default_factory=list)  # 이번 응답의 function_call
    messages: list[str] = field(default_factory=list)
    annotations: list[Any] = field(default_factory=list)
    tools_used: list[str] = field(default_factory=list)
    blocked: dict[str, Any] | None = None
    error: str | None = None
    step_started: dict[str, float] = field(default_factory=dict)


# ------------------------------------------------------------------------------------------- 도구 단계 설명
def _trunc(s: Any, n: int = 700) -> str:
    s = s if isinstance(s, str) else json.dumps(s, ensure_ascii=False, default=str)
    return s if len(s) <= n else s[: n - 1] + "…"


def describe_item(item: Any, done: bool) -> tuple[str, str, dict[str, Any]] | None:
    t = getattr(item, "type", "")
    if t == "file_search_call":
        detail: dict[str, Any] = {"queries": list(getattr(item, "queries", None) or [])}
        results = getattr(item, "results", None)
        if results:
            detail["results"] = [
                {"filename": r.filename, "score": round(float(r.score or 0), 3), "snippet": _trunc((r.text or "").strip().replace("\n", " "), 160)}
                for r in results[:6]
            ]
        return "search", pick("지식 검색 (file_search)", "Knowledge search (file_search)"), detail
    if t == "code_interpreter_call":
        detail = {"code": getattr(item, "code", None) or ""}
        outs = []
        for o in getattr(item, "outputs", None) or []:
            ot = getattr(o, "type", "")
            if ot == "logs":
                outs.append({"type": "logs", "text": _trunc(getattr(o, "logs", ""), 500)})
            elif ot == "image":
                outs.append({"type": "image"})
        if outs:
            detail["outputs"] = outs
        return "code", pick("코드 실행 (Code Interpreter)", "Code execution (Code Interpreter)"), detail
    if t == "mcp_call":
        label = getattr(item, "server_label", "mcp")
        name = getattr(item, "name", "")
        detail = {"arguments": _trunc(getattr(item, "arguments", "") or "", 300)}
        if done:
            detail["output"] = _trunc(getattr(item, "output", "") or "", 500)
            if getattr(item, "error", None):
                detail["error"] = _trunc(item.error, 300)
        return "mcp", pick(f"MCP 도구 호출 · {label}.{name}", f"MCP tool call · {label}.{name}"), detail
    if t == "mcp_list_tools":
        tools = [getattr(x, "name", "") for x in (getattr(item, "tools", None) or [])]
        server = getattr(item, "server_label", "")
        return "mcp", pick(f"MCP 도구 목록 확인 · {server}", f"MCP tools listed · {server}"), {"tools": tools[:12]}
    if t == "function_call":
        return "function", pick(f"함수 호출 · {item.name}", f"Function call · {item.name}"), {"arguments": _trunc(item.arguments or "", 600)}
    if t == "web_search_call":
        action = getattr(item, "action", None)
        q = getattr(action, "query", None) or (getattr(action, "queries", None) or [None])[0] if action else None
        return "web", pick("웹 검색", "Web search"), {"query": q or ""}
    if t == "reasoning":
        return "reasoning", pick("추론", "Reasoning"), {}
    return None


def _file_url(container_id: str, file_id: str, filename: str) -> str:
    from urllib.parse import quote
    return f"/api/files/container/{container_id}/{file_id}?name={quote(filename)}"


def build_final(turn: Turn) -> dict[str, Any]:
    """샌드박스 링크를 실제 다운로드 URL 로 바꾸고, 출처 목록을 만든다."""
    text = "\n\n".join(m for m in turn.messages if m).strip()
    citations: dict[str, dict[str, Any]] = {}
    files: dict[str, dict[str, Any]] = {}
    for a in turn.annotations:
        at = getattr(a, "type", "")
        if at == "file_citation":
            c = citations.setdefault(a.filename, {"kind": "file", "title": a.filename, "file_id": a.file_id, "count": 0})
            c["count"] += 1
        elif at == "url_citation":
            citations.setdefault(a.url, {"kind": "url", "title": getattr(a, "title", None) or a.url, "url": a.url, "count": 0})["count"] += 1
        elif at == "container_file_citation":
            url = _file_url(a.container_id, a.file_id, a.filename)
            files[a.file_id] = {"name": a.filename, "url": url, "image": bool(re.search(r"\.(png|jpe?g|gif|webp|svg)$", a.filename, re.I))}
    # 코드 인터프리터가 쓰는 sandbox:/mnt/data/<파일명> 링크를 실제 다운로드 URL 로 바꾼다
    for f in files.values():
        text = re.sub(r"sandbox:[^)\s\]]*" + re.escape(f["name"]), f["url"], text)
    return {"text": text, "citations": list(citations.values()), "files": list(files.values())}


# ------------------------------------------------------------------------------------------- 단일 응답 스트림
async def _stream_once(
    turn: Turn, *, agent_name: str | None, conversation_id: str, input_items: Any, model: str | None,
    include: list[str], tools: list[dict[str, Any]] | None, instructions: str | None,
) -> AsyncIterator[dict[str, Any]]:
    oc = foundry.openai
    kwargs: dict[str, Any] = dict(conversation=conversation_id, input=input_items, stream=True)
    extra_headers: dict[str, str] = {}
    if agent_name:
        kwargs["extra_body"] = {"agent_reference": {"name": agent_name, "type": "agent_reference"}}
        if include:
            kwargs["include"] = include
    else:
        kwargs["model"] = model
        if tools:
            kwargs["tools"] = tools
        if instructions:
            kwargs["instructions"] = instructions
        if model == settings.model_router:
            extra_headers["Foundry-Features"] = "ModelRouterControls=V1Preview"
    if extra_headers:
        kwargs["extra_headers"] = extra_headers

    try:
        stream = await oc.responses.create(**kwargs)
    except openai.BadRequestError as exc:
        body = getattr(exc, "body", None) or {}
        code = body.get("code") if isinstance(body, dict) else None
        if code == "content_filter" or "content management policy" in str(exc):
            turn.blocked = {"reason": "content_filter", "detail": safety.parse_filter_error(body)}
            return
        if include and "include" in str(exc).lower():
            kwargs.pop("include", None)
            stream = await oc.responses.create(**kwargs)
        else:
            raise

    async for ev in stream:
        t = ev.type
        if t == "response.created":
            turn.response_id = ev.response.id
            turn.model = ev.response.model or turn.model
        elif t == "response.output_item.added":
            d = describe_item(ev.item, done=False)
            if d and d[0] != "message":
                turn.step_started[ev.item.id] = time.time()
                yield {"type": "step", "id": ev.item.id, "kind": d[0], "title": d[1], "status": "running", "detail": d[2]}
        elif t == "response.output_item.done":
            item = ev.item
            if item.type == "message":
                for part in item.content or []:
                    if getattr(part, "type", "") == "output_text":
                        turn.messages.append(part.text)
                        turn.annotations.extend(part.annotations or [])
                continue
            if item.type == "function_call":
                turn.calls.append({"call_id": item.call_id, "name": item.name, "arguments": item.arguments})
            d = describe_item(item, done=True)
            if d:
                ms = round((time.time() - turn.step_started.pop(item.id, time.time())) * 1000)
                if d[0] not in ("reasoning",) or ms > 400:
                    turn.tools_used.append(d[0])
                yield {"type": "step", "id": item.id, "kind": d[0], "title": d[1], "status": "done", "detail": d[2], "ms": ms}
        elif t == "response.output_text.delta":
            if turn.first_token_at is None:
                turn.first_token_at = time.time()
            yield {"type": "text", "delta": ev.delta}
        elif t == "response.reasoning_summary_text.delta":
            yield {"type": "reasoning", "delta": ev.delta}
        elif t == "response.completed":
            u = ev.response.usage
            if u:
                turn.usage = {
                    "input_tokens": u.input_tokens, "output_tokens": u.output_tokens,
                    "reasoning_tokens": getattr(getattr(u, "output_tokens_details", None), "reasoning_tokens", 0) or 0,
                    "cached_tokens": getattr(getattr(u, "input_tokens_details", None), "cached_tokens", 0) or 0,
                }
            turn.model = ev.response.model or turn.model
        elif t == "response.incomplete":
            reason = getattr(ev.response.incomplete_details, "reason", None)
            if reason == "content_filter":
                turn.blocked = {"reason": "content_filter", "detail": {
                    "stage": pick("응답 처리 중", "Processing the response"),
                    "message": pick("가드레일이 요청을 차단했습니다.", "Guardrails blocked the request."),
                }}
                turn.messages.clear()  # 모델이 만든 영어 거절 문구 대신 (에디션 언어의) 차단 카드를 보여 준다
            else:
                turn.error = pick(f"응답이 완료되지 않았습니다({reason})", f"The response did not complete ({reason})")
        elif t in ("response.failed", "error"):
            err = getattr(getattr(ev, "response", None), "error", None) or ev
            turn.error = f"{getattr(err, 'code', '') or ''} {getattr(err, 'message', '') or str(err)[:300]}".strip()


# ------------------------------------------------------------------------------------------- 한 번의 사용자 요청
async def _run_turn(
    *, agent_key: str, conversation_id: str, input_items: Any, model: str | None, web_search: bool, started: float,
    user_text: str = "",
) -> AsyncIterator[dict[str, Any]]:
    spec = spec_by_key(agent_key)
    agent_name = spec.name if spec else None
    include = []
    if spec and spec.uses_file_search:
        include.append("file_search_call.results")
    tools = [{"type": "web_search"}] if (not spec and web_search) else None

    all_tools: list[str] = []
    total = {"input_tokens": 0, "output_tokens": 0, "reasoning_tokens": 0}
    first_token_at = None
    last_model = model or ""
    pending_input = input_items
    blocked = None
    error = None
    final_payload: dict[str, Any] | None = None

    for _ in range(MAX_ROUNDS):
        turn = Turn()
        try:
            async for ev in _stream_once(
                turn, agent_name=agent_name, conversation_id=conversation_id, input_items=pending_input,
                model=model, include=include, tools=tools, instructions=None if spec else GENERAL_INSTRUCTIONS,
            ):
                yield ev
        except Exception as exc:  # noqa: BLE001
            log.exception("스트림 오류")
            turn.error = f"{type(exc).__name__}: {str(exc)[:400]}"
        for k in total:
            total[k] += turn.usage.get(k, 0)
        first_token_at = first_token_at or turn.first_token_at
        last_model = turn.model or last_model
        all_tools += turn.tools_used
        if turn.blocked:
            blocked = turn.blocked
            if user_text and not blocked["detail"].get("filters"):
                try:
                    blocked["detail"] = await safety.explain_block(user_text)
                except Exception:  # noqa: BLE001
                    log.debug("explain_block 실패", exc_info=True)
            yield {"type": "blocked", **blocked}
            break
        if turn.error:
            error = turn.error
            yield {"type": "error", "message": turn.error}
            break
        if turn.calls:
            needs = [c for c in turn.calls if c["name"] in APPROVAL_REQUIRED]
            if needs:  # 사람의 승인을 기다린다 — 승인/거절은 /api/chat/approve 로 이어진다
                yield {"type": "approval", "conversation_id": conversation_id, "agent": agent_key,
                       "calls": [{"call_id": c["call_id"], "name": c["name"], "arguments": json.loads(c["arguments"] or "{}"),
                                  "needs_approval": c["name"] in APPROVAL_REQUIRED} for c in turn.calls]}
                final_payload = None
                break
            outputs = []
            for c in turn.calls:
                result = tools_local.execute(c["name"], json.loads(c["arguments"] or "{}"))
                outputs.append({"type": "function_call_output", "call_id": c["call_id"], "output": json.dumps(result, ensure_ascii=False)})
            pending_input = outputs
            continue
        final_payload = build_final(turn)
        break

    if final_payload:
        yield {"type": "final", **final_payload}
    latency = round((time.time() - started) * 1000)
    ttft = round((first_token_at - started) * 1000) if first_token_at else None
    yield {"type": "usage", "model": last_model, **total, "latency_ms": latency, "ttft_ms": ttft, "tools": all_tools}
    yield {"type": "done"}


def _content_parts(text: str, images: list[dict[str, str]], files: list[dict[str, str]]) -> list[dict[str, Any]]:
    parts: list[dict[str, Any]] = [{"type": "input_text", "text": text}]
    for img in images:
        parts.append({"type": "input_image", "image_url": img["data_url"], "detail": "high"})
    for f in files:
        parts.append({"type": "input_file", "file_id": f["file_id"]})
    return parts


async def stream_chat(req: dict[str, Any]) -> AsyncIterator[dict[str, Any]]:
    started = time.time()
    oc = foundry.openai
    agent_key = req.get("agent") or "knowledge"
    model = req.get("model") or settings.model_fast
    conversation_id = req.get("conversation_id")
    try:
        if not conversation_id:
            conversation_id = (await oc.conversations.create()).id
        yield {"type": "start", "conversation_id": conversation_id, "agent": agent_key, "model": model}
        text = req.get("text", "")
        if req.get("redact_pii"):
            red = await safety.redact_pii(text)
            if red["entities"]:
                yield {"type": "pii", **red}
                text = red["redacted"]
        input_items = [{"role": "user", "content": _content_parts(text, req.get("images") or [], req.get("files") or [])}]
        async for ev in _run_turn(agent_key=agent_key, conversation_id=conversation_id, input_items=input_items, model=model,
                                  web_search=bool(req.get("web_search")), started=started, user_text=text):
            yield ev
    except Exception as exc:  # noqa: BLE001
        log.exception("chat 실패")
        yield {"type": "error", "message": f"{type(exc).__name__}: {str(exc)[:400]}"}
        yield {"type": "done"}


# ------------------------------------------------------------------------------------------- 승인(Human-in-the-loop) 이어받기
async def pending_function_calls(conversation_id: str) -> list[dict[str, Any]]:
    oc = foundry.openai
    outputs: set[str] = set()
    calls: list[dict[str, Any]] = []
    async for item in oc.conversations.items.list(conversation_id=conversation_id, order="desc", limit=30):
        if item.type == "function_call_output":
            outputs.add(item.call_id)
        elif item.type == "function_call" and item.call_id not in outputs:
            calls.append({"call_id": item.call_id, "name": item.name, "arguments": item.arguments})
        elif item.type == "message" and getattr(item, "role", "") == "user":
            break
    return list(reversed(calls))


async def stream_approval(req: dict[str, Any]) -> AsyncIterator[dict[str, Any]]:
    started = time.time()
    conversation_id, agent_key = req["conversation_id"], req.get("agent") or "expense"
    decisions: dict[str, bool] = {d["call_id"]: bool(d["approve"]) for d in req.get("decisions", [])}
    try:
        yield {"type": "start", "conversation_id": conversation_id, "agent": agent_key, "model": ""}
        outputs = []
        for c in await pending_function_calls(conversation_id):
            args = json.loads(c["arguments"] or "{}")
            if c["name"] in APPROVAL_REQUIRED and not decisions.get(c["call_id"], False):
                result = {"status": "REJECTED_BY_USER", "message": pick(
                    "사용자가 실행을 승인하지 않았습니다. 등록되지 않았습니다.",
                    "The user did not approve the run. Nothing was registered.",
                )}
            else:
                result = tools_local.execute(c["name"], args)
            yield {"type": "step", "id": c["call_id"], "kind": "function", "title": pick(f"함수 실행 · {c['name']}", f"Function run · {c['name']}"), "status": "done",
                   "detail": {"arguments": _trunc(args, 400), "output": _trunc(result, 400)}, "ms": 0}
            outputs.append({"type": "function_call_output", "call_id": c["call_id"], "output": json.dumps(result, ensure_ascii=False)})
        async for ev in _run_turn(agent_key=agent_key, conversation_id=conversation_id, input_items=outputs, model=None,
                                  web_search=False, started=started):
            yield ev
    except Exception as exc:  # noqa: BLE001
        log.exception("approval 실패")
        yield {"type": "error", "message": f"{type(exc).__name__}: {str(exc)[:400]}"}
        yield {"type": "done"}
