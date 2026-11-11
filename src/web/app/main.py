"""Contoso AI — FastAPI 백엔드 (+ 정적 프런트엔드 서빙)."""
from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import json
import logging
import mimetypes
import os
import time
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator
from urllib.parse import quote

from fastapi import Depends, FastAPI, File, HTTPException, Request, Response, UploadFile
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import bootstrap, chat, models
from .agents_def import agent_specs
from .config import settings
from .foundry import foundry
from .i18n import pick

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("web")
for noisy in ("azure", "httpx", "openai", "httpcore"):
    logging.getLogger(noisy).setLevel(logging.WARNING)

SESSION_COOKIE = "contoso_session"
SESSION_TTL = 12 * 3600


# ------------------------------------------------------------------------------------------- 수명 주기
def _setup_telemetry() -> None:
    if not settings.appinsights_connection_string:
        return
    try:
        from azure.monitor.opentelemetry import configure_azure_monitor

        configure_azure_monitor(connection_string=settings.appinsights_connection_string)
        log.info("Application Insights 텔레메트리 활성화")
    except Exception as exc:  # noqa: BLE001
        log.warning("텔레메트리 설정 실패: %s", exc)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    _setup_telemetry()
    await foundry.start()
    task = asyncio.create_task(bootstrap.run_bootstrap()) if settings.auto_bootstrap else None
    yield
    if task and not task.done():
        task.cancel()
    await foundry.close()


app = FastAPI(title="Contoso AI — Microsoft Foundry Demo", lifespan=lifespan)


# ------------------------------------------------------------------------------------------- 접속 코드 인증 (데모 보호용)
def _sign(payload: str) -> str:
    key = hashlib.sha256(("contoso-portal|" + settings.access_code).encode()).digest()
    return hmac.new(key, payload.encode(), hashlib.sha256).hexdigest()[:32]


def _make_cookie() -> str:
    exp = str(int(time.time()) + SESSION_TTL)
    return f"{exp}.{_sign(exp)}"


def _valid_cookie(value: str | None) -> bool:
    if not value or "." not in value:
        return False
    exp, sig = value.split(".", 1)
    return exp.isdigit() and int(exp) > time.time() and hmac.compare_digest(sig, _sign(exp))


async def require_auth(request: Request) -> None:
    if settings.auth_mode != "code":
        return
    if not _valid_cookie(request.cookies.get(SESSION_COOKIE)):
        raise HTTPException(status_code=401, detail=pick("로그인이 필요합니다.", "Please sign in first."))


class LoginBody(BaseModel):
    code: str


@app.post("/api/login")
async def login(body: LoginBody, response: Response, request: Request) -> dict[str, Any]:
    if settings.auth_mode == "code" and not hmac.compare_digest(body.code.strip(), settings.access_code):
        await asyncio.sleep(0.6)
        raise HTTPException(status_code=401, detail=pick("접속 코드가 올바르지 않습니다.", "The access code is incorrect."))
    response.set_cookie(SESSION_COOKIE, _make_cookie(), max_age=SESSION_TTL, httponly=True, samesite="lax",
                        secure=request.url.scheme == "https" or request.headers.get("x-forwarded-proto") == "https")
    return {"ok": True}


@app.post("/api/logout")
async def logout(response: Response) -> dict[str, Any]:
    response.delete_cookie(SESSION_COOKIE)
    return {"ok": True}


@app.get("/api/session")
async def session(request: Request) -> dict[str, Any]:
    authed = settings.auth_mode != "code" or _valid_cookie(request.cookies.get(SESSION_COOKIE))
    return {"authenticated": authed, "auth_mode": settings.auth_mode, "lang": settings.lang}


@app.get("/healthz")
async def healthz() -> dict[str, Any]:
    return {"ok": True, "bootstrap": bootstrap.state.state}


# ------------------------------------------------------------------------------------------- 구성 / 상태
def _portal_links() -> dict[str, str]:
    sub = os.environ.get("AZURE_SUBSCRIPTION_ID", "")
    rg = os.environ.get("AZURE_RESOURCE_GROUP", "")
    if not (sub and rg and settings.account_name):
        return {}
    try:
        token = base64.urlsafe_b64encode(bytes.fromhex(sub.replace("-", ""))).decode().rstrip("=")
    except ValueError:
        return {}
    base = f"{settings.portal_base}/nextgen/r/{token},{rg},,{settings.account_name},{settings.project_name}"
    tid = os.environ.get("AZURE_TENANT_ID", "")
    q = f"?tid={tid}" if tid else ""
    return {"agents": f"{base}/build/agents{q}", "evaluations": f"{base}/build/evaluations{q}", "models": f"{base}/build/models{q}",
            "guardrails": f"{base}/build/guardrails{q}", "tracing": f"{base}/build/tracing{q}", "project": f"{base}/home{q}"}


@app.get("/api/config", dependencies=[Depends(require_auth)])
async def config() -> dict[str, Any]:
    try:
        deployed = await foundry.list_deployments()
    except Exception as exc:  # noqa: BLE001
        log.warning("배포 목록 실패: %s", exc)
        deployed = []
    return {
        "region": settings.region,
        "project": settings.project_name,
        "account": settings.account_name,
        "lang": settings.lang,
        "user": {"name": os.environ.get("DEMO_USER_NAME", pick("김민준", "Minjun Kim")),
                 "team": os.environ.get("DEMO_USER_TEAM", pick("영업1팀 · 데모 계정", "Sales Team 1 · Demo account"))},
        "agents": [
            {"key": s.key, "name": s.name, "title": s.title, "subtitle": s.subtitle, "icon": s.icon, "color": s.color, "model": s.model,
             "capabilities": s.capabilities, "starters": s.starters, "accepts": s.accepts}
            for s in agent_specs()
        ],
        "models": models.model_options(deployed),
        "default_model": settings.model_fast,
        "flagship_model": settings.model_flagship,
        "links": _portal_links(),
        "bootstrap": bootstrap.state.public(),
    }


SAMPLE_DIRS = {"receipts": "receipts", "data": "samples", "knowledge": "knowledge"}


@app.get("/api/samples/{kind}/{name}", dependencies=[Depends(require_auth)])
async def sample_file(kind: str, name: str) -> FileResponse:
    """데모용 가상 샘플(영수증 이미지·분석 CSV·사규 PDF)을 내려줍니다."""
    folder = SAMPLE_DIRS.get(kind)
    if not folder:
        raise HTTPException(404, pick("알 수 없는 종류입니다.", "Unknown sample type."))
    path = (settings.seed_dir / folder / name).resolve()
    if settings.seed_dir.resolve() not in path.parents or not path.is_file():
        raise HTTPException(404, pick("파일을 찾을 수 없습니다.", "File not found."))
    return FileResponse(path)


@app.get("/api/status", dependencies=[Depends(require_auth)])
async def status() -> dict[str, Any]:
    return bootstrap.state.public()


# ------------------------------------------------------------------------------------------- SSE 헬퍼
def sse(events: AsyncIterator[dict[str, Any]]) -> StreamingResponse:
    async def body() -> AsyncIterator[str]:
        try:
            async for ev in events:
                yield f"data: {json.dumps(ev, ensure_ascii=False, default=str)}\n\n"
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001
            log.exception("SSE 오류")
            yield f"data: {json.dumps({'type': 'error', 'message': str(exc)[:300]}, ensure_ascii=False)}\n\n"

    return StreamingResponse(body(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no", "Connection": "keep-alive"})


# ------------------------------------------------------------------------------------------- 채팅
class Image(BaseModel):
    name: str = ""
    data_url: str


class FileRef(BaseModel):
    name: str = ""
    file_id: str


class ChatBody(BaseModel):
    agent: str = "knowledge"
    model: str | None = None
    text: str
    conversation_id: str | None = None
    images: list[Image] = Field(default_factory=list)
    files: list[FileRef] = Field(default_factory=list)
    redact_pii: bool = False
    web_search: bool = False


class Decision(BaseModel):
    call_id: str
    approve: bool


class ApprovalBody(BaseModel):
    conversation_id: str
    agent: str = "expense"
    decisions: list[Decision]


@app.post("/api/chat", dependencies=[Depends(require_auth)])
async def chat_endpoint(body: ChatBody) -> StreamingResponse:
    return sse(chat.stream_chat(body.model_dump()))


@app.post("/api/chat/approve", dependencies=[Depends(require_auth)])
async def approve_endpoint(body: ApprovalBody) -> StreamingResponse:
    return sse(chat.stream_approval(body.model_dump()))


ALLOWED_UPLOADS = {".pdf", ".txt", ".md", ".csv", ".json", ".docx", ".xlsx", ".pptx"}


@app.post("/api/upload", dependencies=[Depends(require_auth)])
async def upload(file: UploadFile = File(...)) -> dict[str, Any]:
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_UPLOADS:
        allowed = ", ".join(sorted(ALLOWED_UPLOADS))
        raise HTTPException(400, pick(f"지원하지 않는 형식입니다 ({ext}). 가능: {allowed}", f"Unsupported file type ({ext}). Allowed: {allowed}"))
    data = await file.read()
    if len(data) > 20 * 1024 * 1024:
        raise HTTPException(413, pick("파일은 20MB 이하만 올릴 수 있습니다.", "Files must be 20 MB or smaller."))
    uploaded = await foundry.openai.files.create(purpose="assistants", file=(file.filename, data))
    return {"file_id": uploaded.id, "name": file.filename, "size": len(data)}


@app.get("/api/files/container/{container_id}/{file_id}", dependencies=[Depends(require_auth)])
async def container_file(container_id: str, file_id: str, name: str = "file") -> Response:
    content = await foundry.openai.containers.files.content.retrieve(file_id=file_id, container_id=container_id)
    data = content.read() if hasattr(content, "read") else bytes(content)
    media = mimetypes.guess_type(name)[0] or "application/octet-stream"
    return Response(data, media_type=media, headers={"Content-Disposition": f"inline; filename*=UTF-8''{quote(name)}"})


@app.exception_handler(HTTPException)
async def http_exc(_: Request, exc: HTTPException) -> JSONResponse:
    return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)


# ------------------------------------------------------------------------------------------- 정적 프런트엔드
class NoCacheStatic(StaticFiles):
    async def get_response(self, path: str, scope: Any) -> Response:
        resp = await super().get_response(path, scope)
        if path.endswith((".js", ".mjs", ".css", ".html")) or path in ("", "."):
            resp.headers["Cache-Control"] = "no-cache"
        else:
            resp.headers["Cache-Control"] = "public, max-age=86400"
        return resp


if settings.static_dir.exists():
    app.mount("/", NoCacheStatic(directory=str(settings.static_dir), html=True), name="static")
