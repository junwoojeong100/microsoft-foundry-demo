#!/usr/bin/env python3
"""Foundry 포털 녹화용 로그인 세션을 한 번 저장합니다 (포털 장면 P01~P06 이 사용).

    python recording/save_portal_state.py                 # /tmp/foundry_portal_state.json 에 저장
    PORTAL_STATE=~/portal_state.json python recording/save_portal_state.py
    python recording/save_portal_state.py --lang en --auto   # 영어 포털용 · Enter 대신 로그인이 끝나면 저절로 저장
    python recording/save_portal_state.py --browser msedge   # Playwright 크로미움 대신 설치된 Microsoft Edge 로 로그인

브라우저 창이 열리면 Foundry 포털(https://ai.azure.com)에 평소처럼 로그인(MFA 포함)하세요.
프로젝트 화면이 보이면 터미널에서 Enter 를 누르면 세션(쿠키)이 파일로 저장됩니다(--auto 는 로그인 완료를 직접 감지).
이 파일에는 인증 쿠키가 들어 있으므로 저장소에 올리지 마세요(.gitignore 에 이미 제외돼 있습니다).
"""
from __future__ import annotations

import argparse
import os
import pathlib
import time

from playwright.sync_api import sync_playwright

STATE = pathlib.Path(os.environ.get("PORTAL_STATE", "/tmp/foundry_portal_state.json")).expanduser()
LOCALES = {"ko": "ko-KR", "en": "en-US"}


def chromium_path() -> str | None:
    """설치된 Playwright 크로미움(최신 버전 하나). 없으면 Playwright 기본값을 씁니다."""
    cache = pathlib.Path.home() / "Library/Caches/ms-playwright"
    found = sorted(cache.glob("chromium-*/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing"))
    return str(found[-1]) if found else None


def signed_in(ctx, page) -> bool:
    """Entra ID 세션 쿠키가 생겼고 포털(ai.azure.com) 화면으로 돌아왔는지."""
    has_session = any(c["name"].startswith("ESTSAUTH") and "login.microsoftonline.com" in c["domain"] for c in ctx.cookies())
    return has_session and page.url.startswith("https://ai.azure.com")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lang", choices=sorted(LOCALES), default="ko", help="포털 화면 언어(브라우저 로케일)")
    ap.add_argument("--browser", choices=["chromium", "msedge", "chrome"], default="chromium", help="로그인에 쓸 브라우저(msedge·chrome 은 설치된 것을 사용)")
    ap.add_argument("--auto", action="store_true", help="Enter 대신 로그인 완료를 감지해 자동 저장")
    ap.add_argument("--timeout", type=float, default=3 * 3600, help="--auto 로 기다릴 최대 시간(초)")
    args = ap.parse_args()
    with sync_playwright() as p:
        if args.browser == "chromium":
            browser = p.chromium.launch(headless=False, executable_path=chromium_path())
        else:
            browser = p.chromium.launch(headless=False, channel=args.browser)
        ctx = browser.new_context(viewport={"width": 1440, "height": 900}, locale=LOCALES[args.lang])
        page = ctx.new_page()
        page.goto("https://ai.azure.com")
        if args.auto:
            print("포털에 로그인하세요 — 로그인이 끝나면 저절로 저장합니다…", flush=True)
            t0, stable = time.time(), 0
            while time.time() - t0 < args.timeout:
                stable = stable + 1 if signed_in(ctx, page) else 0
                if stable >= 6:  # 리디렉션이 끝나고 약 12초 동안 포털 화면에 머물면 로그인 완료로 본다
                    break
                page.wait_for_timeout(2000)
            else:
                raise SystemExit("시간 초과 — 로그인이 감지되지 않았습니다")
            page.wait_for_timeout(4000)
        else:
            input("포털에 로그인해 프로젝트 화면이 보이면 여기서 Enter 를 누르세요… ")
        STATE.parent.mkdir(parents=True, exist_ok=True)
        ctx.storage_state(path=str(STATE))
        STATE.chmod(0o600)
        print(f"저장했습니다: {STATE}", flush=True)
        browser.close()


if __name__ == "__main__":
    main()
