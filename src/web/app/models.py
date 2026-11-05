"""일반 채팅의 모델 선택 목록 — 프로젝트에 배포된 모델을 사용자 친화적인 이름으로 보여 줍니다.

모든 모델이 같은 프로젝트·같은 호출 방식을 쓰므로, 사용자는 목록에서 고르기만 하고
관리자는 Foundry 포털의 '모델 + 엔드포인트' 화면에서 배포를 추가·교체합니다.
"""
from __future__ import annotations

from typing import Any

from .config import settings

CATALOG: dict[str, dict[str, str]] = {
    "gpt-6.1-sol": {"label": "GPT-6.1 Sol", "vendor": "OpenAI", "tag": "플래그십 · 고난도 추론"},
    "gpt-6.1-terra": {"label": "GPT-6.1 Terra", "vendor": "OpenAI", "tag": "빠르고 균형 잡힌"},
    "model-router": {"label": "Model Router", "vendor": "Microsoft Foundry", "tag": "질문마다 모델 자동 선택"},
    "deepseek-v4-pro": {"label": "DeepSeek V4 Pro", "vendor": "DeepSeek", "tag": "오픈 웨이트 계열"},
    "kimi-k3.1-pro": {"label": "Kimi K3.1 Pro", "vendor": "Moonshot AI", "tag": "긴 문맥 · 에이전트"},
    "llama-4-maverick": {"label": "Llama 4 Maverick", "vendor": "Meta", "tag": "오픈 모델"},
    "mistral-large-3": {"label": "Mistral Large 3", "vendor": "Mistral AI", "tag": "유럽 기반"},
    "grok-4.7": {"label": "Grok 4.7", "vendor": "xAI", "tag": "추론 중심"},
}


def model_options(deployed: list[dict[str, Any]]) -> list[dict[str, Any]]:
    names = {d["name"] for d in deployed}
    out = []
    for name, meta in CATALOG.items():
        if name in names:
            out.append({"name": name, **meta})
    for d in deployed:  # 카탈로그에 없는 배포도 노출
        if d["name"] not in CATALOG and d["name"] != settings.model_embedding and "embedding" not in d["name"]:
            out.append({"name": d["name"], "label": d["name"], "vendor": d.get("publisher") or "", "tag": ""})
    return out
