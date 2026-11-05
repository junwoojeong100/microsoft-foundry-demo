"""화면·터미널 기록에서 가릴 '내 계정' 값을 실행할 때 알아냅니다.

구독 이름·로그인 계정 이름 같은 개인 식별 값을 저장소에 하드코딩하지 않으려고, 지금 `az login` 한 계정에서 읽어 옵니다.
GUID·이메일처럼 모양으로 알 수 있는 값은 portal_mask.js · terminal_cfg.py 가 따로 처리합니다.

더 가리고 싶은 문자열이 있으면 환경 변수로 더하세요(쉼표로 구분, 실제값=바꿀값):

    MASK_TERMS="Acme Corp=Contoso,secret-project=demo-project" python recording/record.py all-portal
"""
from __future__ import annotations

import base64
import functools
import json
import os
import subprocess


def _az(*args: str) -> str:
    try:
        r = subprocess.run(["az", *args, "-o", "tsv"], capture_output=True, text=True, timeout=30)
    except Exception:  # noqa: BLE001 — az 가 없거나 로그인하지 않았으면 개인 값 없이 진행
        return ""
    return r.stdout.strip() if r.returncode == 0 else ""


def _claims() -> dict:
    """az 가 발급한 액세스 토큰(JWT)의 본문 — 표시 이름과 계정 이름이 들어 있어 Graph 권한 없이 읽을 수 있다."""
    token = _az("account", "get-access-token", "--query", "accessToken")
    try:
        payload = token.split(".")[1]
        return json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
    except Exception:  # noqa: BLE001
        return {}


@functools.lru_cache(maxsize=1)
def personal_terms() -> tuple[tuple[str, str], ...]:
    """((가릴 문자열, 바꿀 문자열), …) — 긴 것부터(구독 이름 안에 계정 이름이 들어 있어도 통째로 먼저 바뀌도록)."""
    terms: dict[str, str] = {}
    sub = _az("account", "show", "--query", "name")
    if len(sub) >= 4:
        terms[sub] = "Contoso-Subscription"
    claims = _claims()
    upn = str(claims.get("upn") or claims.get("unique_name") or claims.get("preferred_username") or _az("account", "show", "--query", "user.name"))
    if "@" in upn and len(upn.split("@")[0]) >= 4:
        terms[upn.split("@")[0]] = "contoso-admin"
    display = str(claims.get("name") or "")
    if len(display) >= 4:
        terms[display] = "Contoso Admin"
    for pair in filter(None, os.environ.get("MASK_TERMS", "").split(",")):
        if "=" in pair:
            real, fake = pair.split("=", 1)
            if real.strip():
                terms[real.strip()] = fake.strip()
    return tuple(sorted(terms.items(), key=lambda kv: -len(kv[0])))
