"""Microsoft Foundry 클라이언트 — 키 없이 Entra ID(관리 ID / az login)만 사용합니다."""
from __future__ import annotations

import logging
import time
from typing import Any

import httpx
from azure.ai.projects.aio import AIProjectClient
from azure.identity.aio import DefaultAzureCredential

from .config import settings

log = logging.getLogger("foundry")

COGNITIVE_SCOPE = "https://cognitiveservices.azure.com/.default"


class Foundry:
    """프로젝트 클라이언트(에이전트·평가·배포 목록) + OpenAI 호환 클라이언트(Responses·Conversations) 묶음."""

    def __init__(self) -> None:
        self.credential: DefaultAzureCredential | None = None
        self.project: AIProjectClient | None = None
        self.openai: Any = None  # openai.AsyncOpenAI
        self.http: httpx.AsyncClient | None = None

    async def start(self) -> None:
        if not settings.project_endpoint:
            raise RuntimeError("FOUNDRY_PROJECT_ENDPOINT 가 설정되지 않았습니다.")
        self.credential = DefaultAzureCredential()
        self.project = AIProjectClient(endpoint=settings.project_endpoint, credential=self.credential)
        self.openai = self.project.get_openai_client()
        self.http = httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=15.0))
        log.info("Foundry 클라이언트 준비 완료: %s", settings.project_endpoint)

    async def close(self) -> None:
        if self.http:
            await self.http.aclose()
        if self.openai:
            await self.openai.close()
        if self.project:
            await self.project.close()
        if self.credential:
            await self.credential.close()

    # ------------------------------------------------------------------ Azure AI 서비스 REST (Content Safety, Language)
    async def _headers(self) -> dict[str, str]:
        token = await self.credential.get_token(COGNITIVE_SCOPE)  # type: ignore[union-attr]
        return {"Authorization": f"Bearer {token.token}", "Content-Type": "application/json"}

    async def post_cognitive(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        resp = await self.http.post(f"{settings.cognitive_endpoint}{path}", headers=await self._headers(), json=body)  # type: ignore[union-attr]
        if resp.status_code >= 400:
            raise RuntimeError(f"{path} → HTTP {resp.status_code}: {resp.text[:300]}")
        return resp.json()

    _dep_cache: tuple[float, list[dict[str, Any]]] = (0.0, [])

    async def list_deployments(self, max_age: float = 60.0) -> list[dict[str, Any]]:
        ts, cached = self._dep_cache
        if cached and time.time() - ts < max_age:
            return cached
        out = []
        async for d in self.project.deployments.list():  # type: ignore[union-attr]
            out.append({
                "name": d.name,
                "model": getattr(d, "model_name", None) or d.name,
                "publisher": getattr(d, "model_publisher", None),
                "sku": getattr(getattr(d, "sku", None), "name", None),
            })
        self._dep_cache = (time.time(), out)
        return out


foundry = Foundry()
