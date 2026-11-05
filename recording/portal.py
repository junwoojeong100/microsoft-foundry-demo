"""Foundry 포털 녹화 도우미 — azd 환경 값으로 포털 주소를 만들고, 로그인된 브라우저 세션(storage state)으로 포털을 엽니다.

포털은 Microsoft Entra 로그인이 필요합니다. 비밀번호를 코드에 넣지 않고, 이미 로그인된 브라우저에서 내보낸
세션 파일(기본 /tmp/foundry_portal_state.json)을 읽어 쓰므로 이 파일은 저장소에 넣지 않습니다(.gitignore).
"""
from __future__ import annotations

import base64
import os
import pathlib
import subprocess
from typing import Any

from playwright.async_api import Browser, Page

from recorder import CAPTION_VIEWPORT, PORTAL_VIEWPORT, new_context

ROOT = pathlib.Path(__file__).resolve().parent
STATE = pathlib.Path(os.environ.get("PORTAL_STATE", "/tmp/foundry_portal_state.json"))


def azd_values() -> dict[str, str]:
    out = subprocess.run(["azd", "env", "get-values"], capture_output=True, text=True, cwd=ROOT.parent, env={**os.environ, "AZD_SKIP_UPDATE_CHECK": "1"}).stdout
    vals: dict[str, str] = {}
    for line in out.splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            vals[k.strip()] = v.strip().strip('"')
    return vals


def portal_base(vals: dict[str, str] | None = None) -> tuple[str, str]:
    """(프로젝트 기준 주소, ?tid=…)"""
    v = vals or azd_values()
    token = base64.urlsafe_b64encode(bytes.fromhex(v["AZURE_SUBSCRIPTION_ID"].replace("-", ""))).decode().rstrip("=")
    base = f"https://ai.azure.com/nextgen/r/{token},{v['AZURE_RESOURCE_GROUP']},,{v['FOUNDRY_ACCOUNT_NAME']},{v['FOUNDRY_PROJECT_NAME']}"
    return base, f"?tid={v['AZURE_TENANT_ID']}"


async def open_portal(browser: Browser) -> tuple[Any, Page, Any, Page]:
    """(포털 컨텍스트, 포털 페이지, 자막 컨텍스트, 자막 페이지)"""
    if not STATE.exists():
        raise SystemExit(f"포털 로그인 세션 파일이 없습니다: {STATE}\n로그인된 브라우저에서 storage state 를 내보내 주세요.")
    ctx = await new_context(browser, viewport=PORTAL_VIEWPORT, caph=0, mask=True, storage_state=str(STATE))
    page = await ctx.new_page()
    cctx = await new_context(browser, viewport=CAPTION_VIEWPORT, caph=CAPTION_VIEWPORT["height"])
    cap = await cctx.new_page()
    await cap.goto("about:blank")
    return ctx, page, cctx, cap
