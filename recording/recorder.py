"""녹화 엔진 — Playwright(헤드리스 Chromium) + CDP 스크린캐스트로 화면을 프레임 단위로 저장하고,
내레이션(say)·빨리감기(ff) 이벤트를 같은 시계로 기록한 뒤 ffmpeg 로 장면 영상을 만듭니다.

윈도우를 직접 녹화하지 않으므로 화면 잠금·알림 팝업과 무관하게 동작하고, 해상도(1920×1080)·품질이 항상 일정합니다.

두 가지 모드
  · 일반 장면   : 한 페이지(1440×810)를 녹화. 자막 바는 페이지 안에 얹습니다(overlay.js).
  · 포털 장면   : 남의 사이트(Foundry 포털)는 레이아웃을 건드릴 수 없으므로, 포털 페이지(1440×732)와
                  자막 전용 페이지(1440×78)를 같은 시계로 따로 녹화해 위아래로 붙입니다(vstack).
"""
from __future__ import annotations

import asyncio
import base64
import json
import pathlib
import random
import re
import subprocess
import time
from typing import Any, Awaitable

from playwright.async_api import Browser, BrowserContext, Page

ROOT = pathlib.Path(__file__).resolve().parent
RAW = ROOT / "raw"
VIEWPORT = {"width": 1440, "height": 810}
PORTAL_VIEWPORT = {"width": 1440, "height": 732}  # 아래 78px 는 자막 전용 페이지 몫
CAPTION_VIEWPORT = {"width": 1440, "height": 78}
DSF = 4 / 3  # 1440×810 CSS px → 1920×1080 화면 픽셀
FPS = 30


def chromium_path() -> str | None:
    cache = pathlib.Path.home() / "Library/Caches/ms-playwright"
    found = sorted(cache.glob("chromium_headless_shell-*/chrome-headless-shell-mac-arm64/chrome-headless-shell"))
    return str(found[-1]) if found else None


async def launch(playwright: Any) -> Browser:
    return await playwright.chromium.launch(executable_path=chromium_path(), args=["--hide-scrollbars", "--force-color-profile=srgb", "--font-render-hinting=none"])


async def new_context(browser: Browser, *, viewport: dict[str, int] | None = None, caph: int = 78, mask: bool = False, **kw: Any) -> BrowserContext:
    """caph: 페이지 안에 얹을 자막 바 높이(0 이면 자막 바 없음). mask: 포털용 개인정보 가리개 주입."""
    ctx = await browser.new_context(viewport=viewport or VIEWPORT, device_scale_factor=DSF, locale="ko-KR", timezone_id="Asia/Seoul", color_scheme="light", **kw)
    await ctx.add_init_script(script=f"window.__REC_CAPH = {int(caph)};")
    await ctx.add_init_script(path=str(ROOT / "overlay.js"))
    if mask:
        from masking import personal_terms  # 내 계정에서 알아낸 구독 이름·계정 이름(저장소에는 개인 값을 두지 않는다)

        terms = [[re.escape(real).replace("\\ ", "\\s+"), fake] for real, fake in personal_terms()]
        await ctx.add_init_script(script=f"window.__MASK_TERMS = {json.dumps(terms, ensure_ascii=False)};")
        await ctx.add_init_script(path=str(ROOT / "portal_mask.js"))
    return ctx


class Recorder:
    """한 페이지의 프레임 기록기."""

    def __init__(self, name: str, subdir: str = "frames") -> None:
        self.name = name
        self.dir = RAW / name
        self.frames_dir = self.dir / subdir
        self.frames: list[tuple[float, str]] = []
        self.events: list[dict[str, Any]] = []
        self.t_start = 0.0
        self.t_end = 0.0
        self._cdp: Any = None
        self._n = 0
        self._last_hash = None

    async def start(self, page: Page) -> None:
        self.frames_dir.mkdir(parents=True, exist_ok=True)
        self._cdp = await page.context.new_cdp_session(page)
        self._cdp.on("Page.screencastFrame", lambda p: asyncio.ensure_future(self._on_frame(p)))
        self.t_start = time.time()
        await self._cdp.send("Page.startScreencast", {"format": "jpeg", "quality": 86, "maxWidth": 1920, "maxHeight": 1080, "everyNthFrame": 2})

    async def _on_frame(self, p: dict[str, Any]) -> None:
        try:
            await self._cdp.send("Page.screencastFrameAck", {"sessionId": p["sessionId"]})
        except Exception:  # noqa: BLE001 — 종료 중 경합
            return
        data = base64.b64decode(p["data"])
        h = hash(data)
        if h == self._last_hash:
            return
        self._last_hash = h
        self._n += 1
        name = f"f_{self._n:06d}.jpg"
        (self.frames_dir / name).write_bytes(data)
        self.frames.append((float(p["metadata"]["timestamp"]), name))

    async def stop(self) -> None:
        self.t_end = time.time()
        try:
            await self._cdp.send("Page.stopScreencast")
        except Exception:  # noqa: BLE001
            pass
        await asyncio.sleep(0.2)


def split_caption(text: str, limit: int = 62) -> list[str]:
    """내레이션을 자막 한 장면 길이로 쪼갭니다 (문장 → 쉼표/공백)."""
    parts: list[str] = []
    for sent in re.split(r"(?<=[.!?。…])\s+", text.strip()):
        if len(sent) <= limit:
            parts.append(sent)
            continue
        cur = ""
        for chunk in re.split(r"(?<=[,，])\s*|\s+", sent):
            if cur and len(cur) + len(chunk) + 1 > limit:
                parts.append(cur.strip())
                cur = chunk
            else:
                cur = f"{cur} {chunk}".strip()
        if cur:
            parts.append(cur)
    return [p for p in parts if p]


class Scene:
    """장면 스크립트에서 쓰는 도우미 — 내레이션, 사람 같은 마우스/타이핑, 빨리감기."""

    def __init__(self, name: str, page: Page, manifest: dict[str, Any], cap_page: Page | None = None) -> None:
        self.name = name
        self.page = page
        self.cap_page = cap_page
        self.manifest = manifest
        self.rec = Recorder(name)
        self.rec_cap = Recorder(name, "cap_frames") if cap_page else None
        self.mx, self.my = 720.0, 405.0

    # ───────── 시작/끝
    async def __aenter__(self) -> "Scene":
        if self.dir_exists():
            subprocess.run(["rm", "-rf", str(RAW / self.name)], check=True)
        if self.cap_page and self.rec_cap:
            await self.cap_page.evaluate("window.__rec && __rec.caption('\\u00a0')")
            await self.rec_cap.start(self.cap_page)
        await self.rec.start(self.page)
        if self.rec_cap:  # 두 기록기의 시작 시각을 맞춘다
            self.rec_cap.t_start = self.rec.t_start
        return self

    def dir_exists(self) -> bool:
        return (RAW / self.name).exists()

    async def __aexit__(self, *exc: Any) -> None:
        await self.page.evaluate("window.__rec && (__rec.caption(''), __rec.ff(false), __rec.unspot())")
        if self.cap_page:
            await self.cap_page.evaluate("window.__rec && __rec.caption('')")
            await asyncio.sleep(0.3)
        await self.rec.stop()
        if self.rec_cap:
            await self.rec_cap.stop()
        meta: dict[str, Any] = {"name": self.name, "t_start": self.rec.t_start, "t_end": self.rec.t_end, "frames": self.rec.frames, "events": self.rec.events}
        if self.rec_cap:
            meta["cap_frames"] = self.rec_cap.frames
        (RAW / self.name).mkdir(parents=True, exist_ok=True)
        (RAW / self.name / "meta.json").write_text(json.dumps(meta, ensure_ascii=False))

    # ───────── 내레이션
    async def say(self, key: str, *actions: Awaitable[Any], tail: float = 0.35) -> None:
        info = self.manifest[key]
        dur, text = float(info["duration"]), info["text"]
        self.rec.events.append({"t": time.time(), "type": "say", "key": key, "dur": dur})
        parts = split_caption(text)
        weights = [max(8, len(p)) for p in parts]
        total_w = sum(weights)
        target = self.cap_page or self.page

        async def captions() -> None:
            for p, w in zip(parts, weights):
                await target.evaluate("t => window.__rec && __rec.caption(t)", p)
                await asyncio.sleep(dur * w / total_w)
            await target.evaluate("window.__rec && __rec.caption('')")

        await asyncio.gather(captions(), *actions, asyncio.sleep(dur + tail))

    async def pause(self, seconds: float) -> None:
        await asyncio.sleep(seconds)

    async def chapter(self, n: str, title: str) -> None:
        await self.page.evaluate("([n, t]) => window.__rec && __rec.chapter(n, t)", [n, title])

    # ───────── 빨리감기: 실제 대기 시간은 그대로 기다리되 영상에서는 target 초로 압축
    async def ff(self, awaitable: Awaitable[Any], label: str = "빨리 감기", target: float = 5.0, badge: bool = True) -> Any:
        t0 = time.time()
        if badge:
            await self.page.evaluate("l => window.__rec && __rec.ff(true, l)", label)
        try:
            return await awaitable
        finally:
            t1 = time.time()
            if badge:
                await self.page.evaluate("window.__rec && __rec.ff(false)")
            if t1 - t0 > target + 0.6:
                self.rec.events.append({"type": "ff", "t0": t0, "t1": t1, "target": target})

    async def quiet(self, awaitable: Awaitable[Any], target: float = 0.8) -> Any:
        """로딩 대기를 배지 없이 조용히 압축한다(포털 화면 전환용)."""
        return await self.ff(awaitable, target=target, badge=False)

    # ───────── 사람 같은 입력
    async def glide(self, x: float, y: float, dur: float = 0.55) -> None:
        sx, sy = self.mx, self.my
        n = max(10, int(dur / 0.016))
        for i in range(1, n + 1):
            k = i / n
            e = k * k * (3 - 2 * k)  # ease-in-out
            await self.page.mouse.move(sx + (x - sx) * e, sy + (y - sy) * e)
            await asyncio.sleep(dur / n)
        self.mx, self.my = x, y

    def _loc(self, target: str | Any) -> Any:
        return self.page.locator(target).first if isinstance(target, str) else target

    async def hover(self, target: str | Any, *, dur: float = 0.6, dx: float = 0, dy: float = 0) -> None:
        loc = self._loc(target)
        await loc.scroll_into_view_if_needed()
        box = await loc.bounding_box()
        assert box, f"요소를 찾을 수 없음: {target}"
        await self.glide(box["x"] + box["width"] / 2 + dx, box["y"] + box["height"] / 2 + dy, dur)

    async def click(self, target: str | Any, *, dur: float = 0.55, pause: float = 0.25, dx: float = 0, dy: float = 0) -> None:
        await self.hover(target, dur=dur, dx=dx, dy=dy)
        await asyncio.sleep(pause)
        await self.page.mouse.down()
        await asyncio.sleep(0.07)
        await self.page.mouse.up()
        await asyncio.sleep(0.2)

    async def type(self, target: str, text: str, delay: float = 0.038) -> None:
        await self.click(target, pause=0.1)
        for ch in text:
            await self.page.keyboard.type(ch)
            await asyncio.sleep(delay * random.uniform(0.6, 1.5))

    async def scroll(self, selector: str, to: float | str, dur: float = 0.9) -> None:
        await self.page.evaluate(
            """async ([sel, to, dur]) => {
              const el = document.querySelector(sel); if (!el) return;
              const start = el.scrollTop; const end = to === 'bottom' ? el.scrollHeight : to === 'top' ? 0 : to;
              const t0 = performance.now();
              await new Promise(res => { const f = (t) => { const k = Math.min(1, (t - t0) / (dur * 1000)); const e = k * k * (3 - 2 * k);
                el.scrollTop = start + (end - start) * e; k < 1 ? requestAnimationFrame(f) : res(); }; requestAnimationFrame(f); });
            }""", [selector, to, dur])

    async def scroll_to(self, target: Any, *, by: float = 0, dur: float = 0.9) -> None:
        """가장 가까운 스크롤 가능한 조상을 찾아 부드럽게 by 픽셀 스크롤(포털처럼 컨테이너를 모르는 화면용)."""
        handle = await target.element_handle()
        await self.page.evaluate(
            """async ([el, by, dur]) => {
              let n = el; while (n && n !== document.body && !(n.scrollHeight > n.clientHeight + 4 && /(auto|scroll)/.test(getComputedStyle(n).overflowY))) n = n.parentElement;
              n = n || document.scrollingElement; const start = n.scrollTop; const t0 = performance.now();
              await new Promise(res => { const f = (t) => { const k = Math.min(1, (t - t0) / (dur * 1000)); const e = k * k * (3 - 2 * k);
                n.scrollTop = start + by * e; k < 1 ? requestAnimationFrame(f) : res(); }; requestAnimationFrame(f); });
            }""", [handle, by, dur])

    async def spot(self, selector: str | Any, seconds: float = 2.0, pad: int = 8) -> None:
        """요소를 강조 상자로 잠시 비춘다. selector 는 CSS 문자열 또는 Locator."""
        if not isinstance(selector, str):
            handle = await selector.element_handle()
            ok = await self.page.evaluate("([el, p]) => window.__rec && __rec.spot(el, p)", [handle, pad])
        else:
            ok = await self.page.evaluate("([s, p]) => window.__rec && __rec.spot(s, p)", [selector, pad])
        if ok:
            await asyncio.sleep(seconds)
            await self.page.evaluate("window.__rec && __rec.unspot()")


# ───────────────────────────────────────── 조립
def _tmap_builder(meta: dict[str, Any]):
    ffs = sorted([e for e in meta["events"] if e["type"] == "ff"], key=lambda e: e["t0"])

    def tmap(t: float) -> float:
        out = t - meta["t_start"]
        for w in ffs:
            raw = w["t1"] - w["t0"]
            keep = min(raw, w["target"])
            if t >= w["t1"]:
                out -= raw - keep
            elif t > w["t0"]:
                out -= (t - w["t0"]) * (1 - keep / raw)
        return out
    return tmap


def _frames_to_mp4(d: pathlib.Path, frames: list[tuple[float, str]], sub: str, tmap: Any, total: float, out: pathlib.Path, crf: int) -> None:
    lines = []
    for i, (ts, fn) in enumerate(frames):
        a = tmap(ts) if i else 0.0
        b = tmap(frames[i + 1][0]) if i + 1 < len(frames) else total
        dur = max(0.001, b - a)
        lines.append(f"file '{sub}/{fn}'\nduration {dur:.4f}")
    lines.append(f"file '{sub}/{frames[-1][1]}'")
    lst = d / f"list_{sub}.txt"
    lst.write_text("\n".join(lines))
    subprocess.run(["ffmpeg", "-nostdin", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst),
                    "-vf", f"fps={FPS},scale=1920:-2:flags=lanczos,format=yuv420p", "-t", f"{total:.3f}", "-c:v", "libx264", "-preset", "veryfast", "-crf", str(crf),
                    "-pix_fmt", "yuv420p", str(out)], check=True)


def assemble_scene(name: str, crf: int = 20) -> dict[str, Any]:
    """프레임 목록 → 장면 mp4. 내레이션이 놓일 '최종 영상 기준 시각'을 scene.json 에 기록한다."""
    d = RAW / name
    meta = json.loads((d / "meta.json").read_text())
    tmap = _tmap_builder(meta)
    frames = meta["frames"]
    if not frames:
        raise RuntimeError(f"{name}: 프레임이 없습니다")
    total = tmap(meta["t_end"])
    out = d / "scene.mp4"
    if meta.get("cap_frames"):
        _frames_to_mp4(d, frames, "frames", tmap, total, d / "main.mp4", crf)
        _frames_to_mp4(d, meta["cap_frames"], "cap_frames", tmap, total, d / "cap.mp4", crf)
        subprocess.run(["ffmpeg", "-nostdin", "-y", "-loglevel", "error", "-i", str(d / "main.mp4"), "-i", str(d / "cap.mp4"),
                        "-filter_complex", "[0:v][1:v]vstack=inputs=2,scale=1920:1080:flags=lanczos,format=yuv420p[v]", "-map", "[v]",
                        "-c:v", "libx264", "-preset", "veryfast", "-crf", str(crf), "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(out)], check=True)
    else:
        _frames_to_mp4(d, frames, "frames", tmap, total, out, crf)
        tmp = d / "scene_fast.mp4"
        subprocess.run(["ffmpeg", "-nostdin", "-y", "-loglevel", "error", "-i", str(out), "-c", "copy", "-movflags", "+faststart", str(tmp)], check=True)
        tmp.replace(out)
    says = [{"key": e["key"], "t": round(tmap(e["t"]), 3), "dur": e["dur"]} for e in meta["events"] if e["type"] == "say"]
    info = {"name": name, "duration": round(total, 3), "says": says, "file": str(out)}
    (d / "scene.json").write_text(json.dumps(info, ensure_ascii=False, indent=1))
    return info
