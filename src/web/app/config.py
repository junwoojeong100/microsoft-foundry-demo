"""환경 설정 — 모든 값은 환경 변수(= Bicep 이 Container App 에 주입)에서 읽습니다."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


@dataclass(frozen=True)
class Settings:
    project_endpoint: str
    account_name: str
    project_name: str
    region: str
    model_flagship: str
    model_fast: str
    model_router: str
    model_embedding: str
    auth_mode: str  # "none" | "code"
    access_code: str
    auto_bootstrap: bool
    seed_dir: Path
    static_dir: Path
    appinsights_connection_string: str

    @property
    def account_endpoint(self) -> str:
        """Foundry 리소스의 AI Foundry API 엔드포인트."""
        return f"https://{self.account_name}.services.ai.azure.com"

    @property
    def cognitive_endpoint(self) -> str:
        """Content Safety · Language(PII) · Speech 등 Azure AI 서비스 엔드포인트."""
        return f"https://{self.account_name}.cognitiveservices.azure.com"

    @property
    def portal_base(self) -> str:
        return "https://ai.azure.com"


def load_settings() -> Settings:
    endpoint = _env("FOUNDRY_PROJECT_ENDPOINT")
    account = _env("FOUNDRY_ACCOUNT_NAME")
    if not account and endpoint:
        account = endpoint.split("//", 1)[-1].split(".", 1)[0]
    return Settings(
        project_endpoint=endpoint,
        account_name=account,
        project_name=_env("FOUNDRY_PROJECT_NAME", "contoso-ai"),
        region=_env("AZURE_REGION", "koreacentral"),
        model_flagship=_env("MODEL_FLAGSHIP", "gpt-6.1-sol"),
        model_fast=_env("MODEL_FAST", "gpt-6.1-terra"),
        model_router=_env("MODEL_ROUTER", "model-router"),
        model_embedding=_env("MODEL_EMBEDDING", "text-embedding-3-large"),
        auth_mode=_env("AUTH_MODE", "none"),
        access_code=_env("DEMO_ACCESS_CODE"),
        auto_bootstrap=_env("AUTO_BOOTSTRAP", "true").lower() in ("1", "true", "yes"),
        seed_dir=Path(_env("SEED_DIR") or BASE_DIR / "seed"),
        static_dir=Path(_env("STATIC_DIR") or BASE_DIR / "static"),
        appinsights_connection_string=_env("APPLICATIONINSIGHTS_CONNECTION_STRING"),
    )


settings = load_settings()
