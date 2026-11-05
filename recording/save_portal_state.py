#!/usr/bin/env python3
"""Foundry 포털 녹화용 로그인 세션을 한 번 저장합니다 (포털 장면 P01~P06 이 사용).

    python recording/save_portal_state.py                 # /tmp/foundry_portal_state.json 에 저장
    PORTAL_STATE=~/portal_state.json python recording/save_portal_state.py

브라우저 창이 열리면 Foundry 포털(https://ai.azure.com)에 평소처럼 로그인(MFA 포함)하세요.
프로젝트 화면이 보이면 터미널에서 Enter 를 누르면 세션(쿠키)이 파일로 저장됩니다.
이 파일에는 인증 쿠키가 들어 있으므로 저장소에 올리지 마세요(.gitignore 에 이미 제외돼 있습니다).
"""
from __future__ import annotations

import os
import pathlib

from playwright.sync_api import sync_playwright

STATE = pathlib.Path(os.environ.get("PORTAL_STATE", "/tmp/foundry_portal_state.json")).expanduser()


def main() -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        ctx = browser.new_context(viewport={"width": 1440, "height": 900}, locale="ko-KR")
        page = ctx.new_page()
        page.goto("https://ai.azure.com")
        input("포털에 로그인해 프로젝트 화면이 보이면 여기서 Enter 를 누르세요… ")
        ctx.storage_state(path=str(STATE))
        STATE.chmod(0o600)
        print(f"저장했습니다: {STATE}")
        browser.close()


if __name__ == "__main__":
    main()
