"""채팅 안의 안전장치 — 사용자가 보는 두 가지.

  · 개인정보 자동 마스킹 : Azure AI Language PII (주민등록번호 등 한국형 개인정보 포함) — 입력창의 토글
  · 가드레일 차단 설명   : 모델 배포에 연결된 Foundry 가드레일(RAI 정책)이 요청을 막으면, 같은 분류기
                          (Content Safety · Prompt Shields)로 사유를 보강해 한국어 차단 카드로 보여 줌

정책 자체(임계값·Prompt Shields·배포 연결)는 코드(infra/modules/foundry.bicep)로 배포되고
관리자는 Foundry 포털의 '가드레일' 화면에서 확인·수정합니다. 모든 호출은 Foundry 리소스 하나와 Entra ID 로 이뤄집니다.
"""
from __future__ import annotations

import asyncio
import time
from typing import Any

from .foundry import foundry

PII_LABELS = {
    "Person": "이름", "PhoneNumber": "전화번호", "Email": "이메일", "Address": "주소",
    "KRResidentRegistrationNumber": "주민등록번호", "CreditCardNumber": "카드번호",
    "InternationalBankingAccountNumber": "계좌번호", "KRPassportNumber": "여권번호",
    "KRDriversLicenseNumber": "운전면허번호", "IPAddress": "IP주소",
}
FILTER_LABELS = {
    "hate": "혐오", "sexual": "성적 콘텐츠", "violence": "폭력", "self_harm": "자해", "jailbreak": "탈옥 시도 (Prompt Shields)",
    "indirect_attack": "간접 프롬프트 주입", "protected_material_text": "저작권 보호 텍스트", "protected_material_code": "코드 라이선스",
}
CATEGORY_LABELS = {"Hate": "혐오", "Sexual": "성적 콘텐츠", "Violence": "폭력", "SelfHarm": "자해"}


async def redact_pii(text: str) -> dict[str, Any]:
    body = {
        "kind": "PiiEntityRecognition",
        "parameters": {"modelVersion": "latest", "stringIndexType": "UnicodeCodePoint"},
        "analysisInput": {"documents": [{"id": "1", "language": "ko", "text": text}]},
    }
    t0 = time.time()
    data = await foundry.post_cognitive("/language/:analyze-text?api-version=2024-11-01", body)
    doc = data["results"]["documents"][0]
    ents = [e for e in doc["entities"] if e["category"] in PII_LABELS]
    redacted = text
    for e in sorted(ents, key=lambda x: x["offset"], reverse=True):
        redacted = redacted[: e["offset"]] + f"[{PII_LABELS[e['category']]}]" + redacted[e["offset"] + e["length"]:]
    return {
        "entities": [{"category": e["category"], "label": PII_LABELS[e["category"]], "text": e["text"], "confidence": round(e["confidenceScore"], 2)} for e in ents],
        "redacted": redacted,
        "ms": round((time.time() - t0) * 1000),
    }


async def analyze_text(text: str) -> dict[str, Any]:
    t0 = time.time()
    data = await foundry.post_cognitive(
        "/contentsafety/text:analyze?api-version=2024-09-01",
        {"text": text, "categories": ["Hate", "Sexual", "Violence", "SelfHarm"], "outputType": "FourSeverityLevels"},
    )
    cats = [{"name": c["category"], "label": CATEGORY_LABELS.get(c["category"], c["category"]), "severity": c["severity"]} for c in data["categoriesAnalysis"]]
    return {"categories": cats, "ms": round((time.time() - t0) * 1000)}


async def shield_prompt(user_prompt: str, documents: list[str] | None = None) -> dict[str, Any]:
    t0 = time.time()
    data = await foundry.post_cognitive(
        "/contentsafety/text:shieldPrompt?api-version=2024-09-01",
        {"userPrompt": user_prompt, "documents": documents or []},
    )
    return {
        "jailbreak": bool(data.get("userPromptAnalysis", {}).get("attackDetected")),
        "indirect_attack": any(d.get("attackDetected") for d in data.get("documentsAnalysis", [])),
        "ms": round((time.time() - t0) * 1000),
    }


def parse_filter_error(body: Any) -> dict[str, Any]:
    """OpenAI SDK 의 400(content_filter) 본문에서 어떤 필터가 걸렸는지 뽑는다."""
    inner = (body or {}).get("innererror", {}) if isinstance(body, dict) else {}
    result = inner.get("content_filter_result", {}) or {}
    return {"stage": "입력(프롬프트) 검사", "filters": _filters_from_result(result), "message": "Foundry 가드레일 정책이 요청을 차단했습니다."}


def _filters_from_result(result: dict[str, Any]) -> list[dict[str, Any]]:
    out = []
    for name, r in (result or {}).items():
        if isinstance(r, dict) and (r.get("filtered") or r.get("detected")):
            out.append({"name": name, "label": FILTER_LABELS.get(name, name), "severity": r.get("severity"), "filtered": bool(r.get("filtered"))})
    return out


async def explain_block(text: str) -> dict[str, Any]:
    """Responses/에이전트 경로의 차단은 사유가 비어 오므로, 같은 분류기(Prompt Shields·Content Safety)로 사유를 보강한다."""
    shield, cats = await asyncio.gather(shield_prompt(text), analyze_text(text), return_exceptions=True)
    filters: list[dict[str, Any]] = []
    if not isinstance(shield, Exception) and shield.get("jailbreak"):
        filters.append({"name": "jailbreak", "label": FILTER_LABELS["jailbreak"], "severity": None, "filtered": True})
    if not isinstance(cats, Exception):
        for c in cats["categories"]:
            if c["severity"] >= 4:
                filters.append({"name": c["name"].lower(), "label": c["label"], "severity": c["severity"], "filtered": True})
    return {"stage": "입력(프롬프트) 검사", "filters": filters, "message": "Foundry 가드레일 정책이 요청을 차단했습니다."}
