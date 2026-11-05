#!/usr/bin/env python3
"""화면 점검: 모든 화면을 헤드리스 Chromium 으로 열어 콘솔 오류를 모으고 스크린샷을 저장합니다.

    python scripts/qa_screens.py [--base http://localhost:8765] [--out /tmp/qa]
"""
from __future__ import annotations

import argparse
import asyncio
import pathlib

from playwright.async_api import async_playwright

ROUTES = ["chat/knowledge", "chat/expense", "chat/analyst", "chat/architect", "chat/general"]


def chromium() -> str | None:
    cache = pathlib.Path.home() / "Library/Caches/ms-playwright"
    found = sorted(cache.glob("chromium_headless_shell-*/chrome-headless-shell-mac-arm64/chrome-headless-shell"))
    return str(found[-1]) if found else None


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://localhost:8765")
    ap.add_argument("--out", default="/tmp/qa")
    args = ap.parse_args()
    out = pathlib.Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as p:
        browser = await p.chromium.launch(executable_path=chromium())
        ctx = await browser.new_context(viewport={"width": 1440, "height": 810}, device_scale_factor=1.3333, locale="ko-KR")
        page = await ctx.new_page()
        errors: list[str] = []
        page.on("console", lambda m: errors.append(f"[{m.type}] {m.text}") if m.type in ("error", "warning") else None)
        page.on("pageerror", lambda e: errors.append(f"[pageerror] {e}"))
        page.on("requestfailed", lambda r: errors.append(f"[requestfailed] {r.url} {r.failure}"))
        for route in ROUTES:
            await page.goto(f"{args.base}/#/{route}")
            await page.wait_for_timeout(1500)
            name = route.replace("/", "_")
            await page.screenshot(path=str(out / f"{name}.png"))
            print("✔", route)
        await browser.close()
    print("\n콘솔 오류/경고:", len(errors))
    for e in errors[:30]:
        print("  ", e[:300])


if __name__ == "__main__":
    asyncio.run(main())
