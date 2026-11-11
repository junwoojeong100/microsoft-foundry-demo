"""앱이 뜰 때 Foundry 프로젝트를 데모 상태로 맞춥니다 (멱등 — 여러 번 실행해도 안전).

1. 사규 PDF → 벡터 스토어 `contoso-knowledge`  (file_search 의 지식 소스)
2. 분석용 CSV → Foundry Files                  (Code Interpreter 가 /mnt/data 로 마운트)
3. 에이전트 4개 → 정의가 바뀐 경우에만 새 버전 생성 (해시 비교)

`python -m app.bootstrap` 으로 단독 실행할 수도 있습니다.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any

from azure.ai.projects.models import PromptAgentDefinition

from .agents_def import AgentSpec, agent_specs
from .config import settings
from .foundry import foundry
from .i18n import pick

log = logging.getLogger("bootstrap")

VECTOR_STORE_NAME = "contoso-knowledge"

STEP_VECTOR_STORE = pick("지식 소스(벡터 스토어)", "Knowledge source (vector store)")
STEP_DATA_FILES = pick("분석용 데이터 파일", "Analysis data files")
STEP_PROJECT = pick("Foundry 프로젝트 연결", "Foundry project connection")


@dataclass
class BootstrapState:
    state: str = "idle"  # idle | running | ready | error
    message: str = pick("대기 중", "Waiting to start")
    steps: list[dict[str, Any]] = field(default_factory=list)
    started_at: float = 0.0
    finished_at: float = 0.0
    vector_store_id: str = ""
    data_file_ids: list[str] = field(default_factory=list)
    agents: dict[str, dict[str, Any]] = field(default_factory=dict)

    def step(self, title: str, status: str = "running", detail: str = "") -> None:
        for s in self.steps:
            if s["title"] == title:
                s.update(status=status, detail=detail)
                break
        else:
            self.steps.append({"title": title, "status": status, "detail": detail})
        self.message = f"{title} {detail}".strip()
        log.info("[bootstrap] %s — %s %s", title, status, detail)

    def public(self) -> dict[str, Any]:
        return {
            "state": self.state,
            "message": self.message,
            "steps": self.steps,
            "elapsed": round((self.finished_at or time.time()) - self.started_at, 1) if self.started_at else 0,
            "agents": {k: {"name": v["name"], "version": v["version"]} for k, v in self.agents.items()},
        }


state = BootstrapState()


def _sha(*parts: bytes | str) -> str:
    h = hashlib.sha256()
    for p in parts:
        h.update(p if isinstance(p, bytes) else p.encode())
    return h.hexdigest()


async def _ensure_vector_store() -> str:
    oc = foundry.openai
    knowledge = sorted((settings.seed_dir / "knowledge").glob("*.pdf"))
    seed_hash = _sha(*[p.read_bytes() for p in knowledge])[:16]

    async for vs in oc.vector_stores.list():
        if vs.name == VECTOR_STORE_NAME:
            counts = vs.file_counts
            if (vs.metadata or {}).get("seed_hash") == seed_hash and counts.completed == len(knowledge) and counts.failed == 0:
                state.step(STEP_VECTOR_STORE, "done", pick(f"기존 {counts.completed}개 문서 사용", f"Using {counts.completed} existing documents"))
                return vs.id
            await oc.vector_stores.delete(vs.id)  # 내용이 달라졌다면 다시 만듭니다
            break

    state.step(STEP_VECTOR_STORE, "running", pick(f"사규 PDF {len(knowledge)}개 업로드·임베딩 중", f"Uploading and embedding {len(knowledge)} policy PDFs"))
    vs = await oc.vector_stores.create(name=VECTOR_STORE_NAME, metadata={"seed_hash": seed_hash, "app": "contoso-ai-portal"})

    async def upload(path):
        with open(path, "rb") as f:
            await oc.vector_stores.files.upload_and_poll(vector_store_id=vs.id, file=(path.name, f.read()))

    await asyncio.gather(*[upload(p) for p in knowledge])
    state.step(STEP_VECTOR_STORE, "done", pick(f"{len(knowledge)}개 문서 인덱싱 완료", f"{len(knowledge)} documents indexed"))
    return vs.id


async def _ensure_data_files() -> list[str]:
    oc = foundry.openai
    existing: dict[str, str] = {}
    async for f in oc.files.list(purpose="assistants"):
        existing[f.filename] = f.id
    ids = []
    for path in sorted((settings.seed_dir / "samples").glob("*.csv")):
        if path.name in existing:
            ids.append(existing[path.name])
            continue
        uploaded = await oc.files.create(purpose="assistants", file=(path.name, path.read_bytes()))
        ids.append(uploaded.id)
    state.step(STEP_DATA_FILES, "done", pick(f"{len(ids)}개 (Code Interpreter용)", f"{len(ids)} files (for Code Interpreter)"))
    return ids


def _definition(spec: AgentSpec, ctx: dict[str, Any], baseline: bool = False) -> PromptAgentDefinition:
    if baseline:
        return PromptAgentDefinition(model=spec.model, instructions=spec.baseline_instructions or spec.instructions)
    return PromptAgentDefinition(model=spec.model, instructions=spec.instructions, tools=spec.build_tools(ctx))


def _definition_hash(d: PromptAgentDefinition) -> str:
    return _sha(json.dumps(d.as_dict(), sort_keys=True, ensure_ascii=False))[:16]


async def _latest_version(name: str):
    try:
        async for v in foundry.project.agents.list_versions(agent_name=name, limit=1, order="desc"):
            return v
    except Exception as exc:  # 아직 없는 에이전트
        log.debug("agent %s 없음: %s", name, exc)
    return None


async def _ensure_agents(ctx: dict[str, Any]) -> None:
    pc = foundry.project
    for spec in agent_specs():
        step_title = pick(f"에이전트 · {spec.title}", f"Agent · {spec.title}")
        state.step(step_title, "running")
        latest = await _latest_version(spec.name)
        if latest is None and spec.baseline_instructions:
            base = _definition(spec, ctx, baseline=True)
            await pc.agents.create_version(
                agent_name=spec.name, definition=base,
                description=pick(
                    "초기 프로토타입 — 모델만 연결 (지식 없음). 평가 비교의 기준 버전",
                    "Initial prototype — model only (no knowledge). Baseline version for the evaluation comparison",
                ),
                metadata={"role": "baseline", "hash": _definition_hash(base), "app": "contoso-ai-portal"},
            )
            latest = await _latest_version(spec.name)
        definition = _definition(spec, ctx)
        digest = _definition_hash(definition)
        if latest is not None and (latest.metadata or {}).get("hash") == digest:
            version = latest
        else:
            version = await pc.agents.create_version(
                agent_name=spec.name, definition=definition,
                description=f"{spec.title} — {spec.subtitle}",
                metadata={"role": "final", "hash": digest, "app": "contoso-ai-portal"},
            )
        state.agents[spec.key] = {"name": spec.name, "version": version.version}
        state.step(step_title, "done", f"{spec.name} v{version.version}")


async def run_bootstrap() -> BootstrapState:
    state.state, state.started_at, state.finished_at = "running", time.time(), 0.0
    state.steps = []
    delay = 10.0
    while True:
        try:
            state.step(STEP_PROJECT, "running")
            await foundry.list_deployments()  # 권한(RBAC) 전파 확인용
            state.step(STEP_PROJECT, "done", settings.project_name)
            vs_id = await _ensure_vector_store()
            files = await _ensure_data_files()
            state.vector_store_id, state.data_file_ids = vs_id, files
            await _ensure_agents({"vector_store_id": vs_id, "data_file_ids": files})
            state.state, state.finished_at = "ready", time.time()
            state.message = pick("모든 준비가 끝났습니다", "Everything is ready")
            return state
        except Exception as exc:  # RBAC 전파 지연 등은 재시도
            state.state = "running"
            state.message = pick(f"재시도 대기: {type(exc).__name__}: {str(exc)[:160]}", f"Waiting to retry: {type(exc).__name__}: {str(exc)[:160]}")
            log.warning("bootstrap 실패 — %.0f초 후 재시도: %s", delay, exc)
            await asyncio.sleep(delay)
            delay = min(delay * 1.5, 60.0)
            if time.time() - state.started_at > 25 * 60:
                state.state, state.finished_at = "error", time.time()
                return state


async def main() -> None:  # python -m app.bootstrap
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    await foundry.start()
    try:
        s = await run_bootstrap()
        print(json.dumps(s.public(), ensure_ascii=False, indent=2))
    finally:
        await foundry.close()


if __name__ == "__main__":
    asyncio.run(main())
