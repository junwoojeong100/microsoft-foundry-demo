#!/usr/bin/env python3
"""장면 녹화 실행기.

    python recording/record.py S05_knowledge S06_pay            # 앱 장면 (배포된 앱 주소·접속 코드는 azd 환경에서 자동으로 읽음)
    python recording/record.py S00_title S01_intro S02_arch     # 슬라이드류
    python recording/record.py S03_deploy                       # azd up 실제 기록 재생
    python recording/record.py P01_models P02_agents            # 포털 장면 (로그인 세션 필요 — recording/portal.py 참고)
    python recording/record.py all-slides | all-app | all-portal
    REC_LANG=en python recording/record.py all-slides ...     # 영어판: audio_en/ 의 음성·script_en.py·slides_en.html 을 쓰고 raw_en/ 에 녹화

각 장면은 별도 브라우저 컨텍스트에서 실제로 실행되고, 끝나면 recording/raw/<장면>/scene.mp4 가 만들어집니다.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import pathlib
import socket
import subprocess
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from playwright.async_api import async_playwright  # noqa: E402

from lang import SUFFIX  # noqa: E402

from portal import azd_values, open_portal, portal_base  # noqa: E402
from recorder import assemble_scene, launch, new_context  # noqa: E402
from scenes import SCENES, WARNINGS, Ctx  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent
REPO = ROOT.parent


def ensure_http() -> None:
    with socket.socket() as s:
        if s.connect_ex(("127.0.0.1", 8799)) == 0:
            return
    subprocess.Popen([sys.executable, "-m", "http.server", "8799", "--bind", "127.0.0.1", "--directory", str(REPO)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1.0)


def groups() -> dict[str, list[str]]:
    names = list(SCENES)
    return {
        "all-slides": [n for n in names if n.startswith(("S00", "S01", "S02", "S10b", "S12", "C"))],
        "all-app": [n for n in names if n.startswith(("S05", "S06", "S07", "S08", "S09", "S10_"))],
        "all-portal": [n for n in names if n.startswith("P")],
    }


async def run_scene(browser, name: str, args: argparse.Namespace, manifest: dict, vals: dict[str, str]) -> None:
    t0 = time.time()
    portal = name.startswith("P")
    errors: list[str] = []
    ctxs = []
    try:
        if portal:
            pctx, page, cctx, cap = await open_portal(browser)
            ctxs += [pctx, cctx]
            base, tid = portal_base(vals)
            ctx = Ctx(page, manifest, portal=base, tid=tid, account=vals.get("FOUNDRY_ACCOUNT_NAME", ""), cap=cap)
        else:
            c = await new_context(browser)
            ctxs.append(c)
            page = await c.new_page()
            ctx = Ctx(page, manifest, base=args.base, code=args.code)
        page.on("pageerror", lambda e: errors.append(str(e)))
        await asyncio.wait_for(SCENES[name](ctx), timeout=args.timeout)  # 포털 페이지가 멈춰도 장면 하나가 영원히 걸려 있지 않게 한다
        for c in ctxs:  # 녹화가 끝난 페이지를 곧바로 닫아 CPU 를 비운다(인코딩과 다른 장면 녹화가 느려지지 않게)
            await c.close()
        ctxs.clear()
        info = await asyncio.to_thread(assemble_scene, name)  # ffmpeg 인코딩이 이벤트 루프를 막으면 동시에 녹화 중인 다른 장면의 자막·화면 타이밍이 밀린다
        print(f"✔ {name}: {info['duration']:.1f}초 (녹화 {time.time() - t0:.0f}초) 페이지 오류 {len(errors)}건 {errors[:2]}", flush=True)
    except Exception as exc:  # noqa: BLE001
        print(f"✘ {name}: {type(exc).__name__}: {str(exc)[:500]}", flush=True)
        try:
            await page.screenshot(path=str(ROOT / f"raw{SUFFIX}" / f"FAIL_{name}.png"))
        except Exception:  # noqa: BLE001
            pass
    finally:
        for c in ctxs:
            await c.close()


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("scenes", nargs="+")
    ap.add_argument("--base", default="")
    ap.add_argument("--code", default="")
    ap.add_argument("--parallel", type=int, default=1, help="동시에 녹화할 장면 수")
    ap.add_argument("--timeout", type=float, default=480, help="장면 하나의 최대 녹화 시간(초)")
    args = ap.parse_args()
    vals = azd_values()
    args.base = (args.base or vals.get("WEB_URI", "")).rstrip("/")
    args.code = args.code or vals.get("DEMO_ACCESS_CODE", "")
    g = groups()
    names: list[str] = []
    for n in args.scenes:
        names += g.get(n, [n])
    unknown = [n for n in names if n not in SCENES]
    if unknown:
        sys.exit(f"알 수 없는 장면: {unknown}\n가능: {sorted(SCENES)}")
    ensure_http()
    manifest = json.loads((ROOT / f"audio{SUFFIX}" / "manifest.json").read_text())
    async with async_playwright() as p:
        browser = await launch(p)
        sem = asyncio.Semaphore(args.parallel)

        async def guarded(n: str) -> None:
            async with sem:
                await run_scene(browser, n, args, manifest, vals)

        await asyncio.gather(*[guarded(n) for n in names])
        await browser.close()
    if WARNINGS:
        print(f"\n경고 {len(WARNINGS)}건:")
        for w in WARNINGS:
            print("  ⚠", w)


if __name__ == "__main__":
    asyncio.run(main())
