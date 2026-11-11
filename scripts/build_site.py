#!/usr/bin/env python3
"""GitHub Pages 사이트를 만듭니다 — 표준 라이브러리만 써서 GitHub Actions 에서도, 내 컴퓨터에서도 같은 명령으로 실행됩니다.

    python scripts/build_site.py                       # _site/ 에 만들기
    python scripts/build_site.py --out /tmp/site       # 위치 지정
    python scripts/build_site.py --repo owner/name     # 포크해서 쓸 때 (Actions 에서는 GITHUB_REPOSITORY 로 자동)

    cd _site && python -m http.server 8080             # http://localhost:8080 에서 미리 보기

입력                                                      → 출력(_site/)
  site/index.html · doc.html · assets/                    → {{자리표시자}} 를 채운 페이지
  video/<이름>-ko.mp4 · .srt · .chapters.txt · .thumbnail.png → 영상, 챕터(눌러서 이동), 대본, 길이·용량 표시
  video/<이름>-en.mp4 · .srt                              → 영문 영상 (사이트에서 바로 재생되는 파일 링크)
  slides/Microsoft_Foundry_Demo_Deck_{KO,EN}.pptx         → slides/  (README·사이트의 Office 웹 뷰어 링크가 이 파일을 가리킴 — scripts/publish_deck.py 로 복사)
  docs/*.md                                               → docs/*.md  (doc.html 이 브라우저에서 변환해 보여 줌)
  src/web/static/{vendor,fonts}                           → vendor/ · fonts/ · 아이콘

영상을 다시 만들어 video/ 를 바꾸고 push 하면 챕터·길이·대본이 저절로 바뀝니다.
페이지 자리표시자: {{t:키}} {{mmss:키}} (챕터 시각) · {{icon:이름}} · {{duration}} {{size_mb}} {{repo_url}} {{base_url}} {{viewer_ko}} {{viewer_en}} …
"""
from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import os
import pathlib
import re
import shutil
import struct
import subprocess
import sys
import urllib.parse
import zipfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = ROOT / "site"
VIDEO_DIR = ROOT / "video"
DOCS_DIR = ROOT / "docs"
STATIC = ROOT / "src/web/static"
BASENAME = "microsoft-foundry-demo-ko"
BASENAME_EN = "microsoft-foundry-demo-en"
SLIDES_DIR = ROOT / "slides"
DECK_NAMES = {"ko": "Microsoft_Foundry_Demo_Deck_KO.pptx", "en": "Microsoft_Foundry_Demo_Deck_EN.pptx"}
OFFICE_VIEWER = "https://view.officeapps.live.com/op/view.aspx?src="  # 공개 주소의 PPTX 를 PowerPoint 웹 뷰어로 보여 줍니다(다운로드 불필요)
DEFAULT_REPO = "junwoojeong100/microsoft-foundry-demo"
KST = dt.timezone(dt.timedelta(hours=9))

# 페이지의 {{t:키}} · {{mmss:키}} 가 가리키는 챕터 — 챕터 제목의 앞부분과 비교합니다.
CHAPTER_KEYS = {
    "intro": "오프닝", "arch": "Foundry 구조", "deploy": "배포",
    "guide": "직원 경험 · 지식 검색", "pay": "직원 경험 · 업무 자동화", "analyst": "직원 경험 · 데이터 분석",
    "architect": "직원 경험 · 최신 지식", "chat": "직원 경험 · 일반 채팅", "safety": "직원 경험 · 안전장치",
    "code": "에이전트는 코드로", "admin": "관리자 · 모델", "agents": "관리자 · 에이전트", "guard": "관리자 · 가드레일",
    "trace": "관리자 · 추적", "eval": "관리자 · 평가", "ops": "관리자 · 운영", "enterprise": "엔터프라이즈", "wrap": "정리",
}
PLACEHOLDER = re.compile(r"\{\{\s*([a-z_]+)(?::([^{}]*?))?\s*\}\}")
PAGES = ("index.html", "doc.html")


def die(msg: str) -> None:
    print(f"✘ {msg}", file=sys.stderr)
    sys.exit(1)


def mmss(sec: float) -> str:
    s = int(sec)
    return f"{s // 60:02d}:{s % 60:02d}"


# ───────────────────────────────────────── 입력 읽기
def read_chapters(path: pathlib.Path) -> list[dict]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^(\d+):(\d{2})\s+(.+)$", line.strip())
        if m:
            rows.append({"t": int(m[1]) * 60 + int(m[2]), "title": m[3].strip()})
    if not rows:
        die(f"챕터를 읽지 못했습니다: {path}")
    return rows


def mp4_duration(path: pathlib.Path) -> float:
    """mp4 의 moov/mvhd 에서 재생 시간(초)을 읽습니다 — ffprobe 없이."""
    size = path.stat().st_size
    with path.open("rb") as f:
        pos = 0
        while pos + 8 <= size:
            f.seek(pos)
            n, typ = struct.unpack(">I4s", f.read(8))
            head = 8
            if n == 1:
                n, head = struct.unpack(">Q", f.read(8))[0], 16
            elif n == 0:
                n = size - pos
            if n < head:
                break
            if typ == b"moov":
                p, end = pos + head, pos + n
                while p + 8 <= end:
                    f.seek(p)
                    m, t = struct.unpack(">I4s", f.read(8))
                    if t == b"mvhd":
                        version = f.read(1)[0]
                        f.read(3)
                        if version == 1:
                            f.read(16)
                            scale, dur = struct.unpack(">IQ", f.read(12))
                        else:
                            f.read(8)
                            scale, dur = struct.unpack(">II", f.read(8))
                        return dur / scale
                    if m < 8:
                        break
                    p += m
            pos += n
    die(f"mp4 에서 재생 시간(mvhd)을 찾지 못했습니다: {path}")
    return 0.0


def parse_srt(path: pathlib.Path) -> list[tuple[float, float, str]]:
    cues = []
    for block in re.split(r"\n\s*\n", path.read_text(encoding="utf-8").strip()):
        lines = block.splitlines()
        if len(lines) < 3:
            continue
        m = re.match(r"(\d+):(\d+):(\d+)[,.](\d+)\s*-->\s*(\d+):(\d+):(\d+)[,.](\d+)", lines[1])
        if not m:
            continue
        a = [int(x) for x in m.groups()]
        cues.append((a[0] * 3600 + a[1] * 60 + a[2] + a[3] / 1000, a[4] * 3600 + a[5] * 60 + a[6] + a[7] / 1000, " ".join(l.strip() for l in lines[2:])))
    return cues


GITHUB_SVG = ('<svg class="ic" viewBox="0 0 16 16" fill="currentColor" aria-hidden="true" focusable="false"><path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 '
              '7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 '
              '1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 '
              '1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 '
              '.21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z"/></svg>')  # GitHub Octicons "mark-github" (MIT)


def vtt_time(sec: float) -> str:
    ms = int(round(sec * 1000))
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d}.{ms % 1000:03d}"


def write_vtt(cues: list[tuple[float, float, str]], path: pathlib.Path) -> None:
    """SRT 자막 → WebVTT (<track> 은 VTT 만 읽습니다)."""
    body = ["WEBVTT", ""]
    for s, e, text in cues:
        body += [f"{vtt_time(s)} --> {vtt_time(e)}", text.replace("&", "&amp;").replace("<", "&lt;"), ""]
    path.write_text("\n".join(body), encoding="utf-8")


def load_icons() -> dict[str, str]:
    js = (STATIC / "vendor/icons.js").read_text(encoding="utf-8")
    m = re.search(r"export const ICONS = (\{.*\});", js, re.S)
    if not m:
        die("src/web/static/vendor/icons.js 에서 아이콘을 읽지 못했습니다")
    return json.loads(m.group(1))


def docs_info() -> list[dict]:
    """문서 목록 — 제목은 첫 '# ' 줄, 설명은 제목 아래 `<!-- summary: … -->` 주석(없으면 첫 문단)."""
    items = []
    for p in sorted(DOCS_DIR.glob("*.md")):
        text = p.read_text(encoding="utf-8")
        lines = text.splitlines()
        title = next((l[2:].strip() for l in lines if l.startswith("# ")), p.stem)
        m = re.search(r"<!--\s*summary:\s*(.+?)\s*-->", text, re.S)
        if m:
            desc = " ".join(m.group(1).split())
        else:
            desc = next((l.strip() for l in lines[1:] if l.strip() and not l.lstrip().startswith(("#", ">", "|", "```", "-", "1.", "<!--"))), "")
            desc = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", desc)
            desc = re.sub(r"[`*_]", "", desc)
        items.append({"slug": p.stem, "title": title, "desc": desc if len(desc) <= 130 else desc[:128].rstrip() + "…"})
    return items


def viewer_url(base: str, rel: str) -> str:
    """Office 웹 뷰어 링크 — src 에는 덱의 공개 주소(퍼센트 인코딩)를 넣습니다."""
    return OFFICE_VIEWER + urllib.parse.quote(base + rel, safe="")


def deck_counts(path: pathlib.Path) -> tuple[int, int]:
    """(슬라이드 수, 슬라이드에 내장된 영상 수)"""
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
    return sum(1 for n in names if re.fullmatch(r"ppt/slides/slide\d+\.xml", n)), sum(1 for n in names if re.fullmatch(r"ppt/media/.+\.mp4", n))


def minutes_text(seconds: float, english: bool = False) -> str:
    m, sec = divmod(int(round(seconds)), 60)
    return f"{m} min {sec} s" if english else f"{m}분 {sec}초"


# ───────────────────────────────────────── HTML 조각
def chapters_html(chapters: list[dict]) -> str:
    rows = [f'<li><button type="button" data-t="{c["t"]}"><time>{mmss(c["t"])}</time><span>{html.escape(c["title"])}</span></button></li>' for c in chapters]
    return "\n      ".join(rows)


def transcript_html(cues: list[tuple[float, float, str]], chapters: list[dict]) -> str:
    """말 사이 쉼(0.8초 이상)마다 문단을 나누고, 챕터별로 묶어 시각 버튼을 붙입니다."""
    blocks: list[dict] = []
    for s, e, text in cues:
        if blocks and s - blocks[-1]["end"] < 0.8:
            blocks[-1]["text"] += " " + text
            blocks[-1]["end"] = e
        else:
            blocks.append({"start": s, "end": e, "text": text})
    out = []
    for i, ch in enumerate(chapters):
        lo, hi = ch["t"], chapters[i + 1]["t"] if i + 1 < len(chapters) else float("inf")
        mine = [b for b in blocks if lo <= int(b["start"]) < hi]
        if not mine:
            continue
        paras = "".join(f'<p><button type="button" class="ts" data-t="{int(b["start"])}">{mmss(b["start"])}</button> {html.escape(b["text"])}</p>' for b in mine)
        out.append(f"<section><h4>{html.escape(ch['title'])}</h4>{paras}</section>")
    return "\n".join(out)


def docs_cards(docs: list[dict]) -> str:
    return "\n      ".join(
        f'<a class="doc-card" href="doc.html?p={d["slug"]}"><h3>{html.escape(d["title"])}</h3><p>{html.escape(d["desc"])}</p><span>읽기 →</span></a>' for d in docs
    )


# ───────────────────────────────────────── 렌더링
def render(text: str, ctx: dict[str, str], chapter_by_key: dict[str, dict], icons: dict[str, str], name: str) -> str:
    problems: list[str] = []

    def sub(m: re.Match[str]) -> str:
        kind, arg = m.group(1), (m.group(2) or "").strip()
        if kind in ("t", "mmss"):
            ch = chapter_by_key.get(arg)
            if ch is None:
                problems.append(f"{name}: 챕터 키 '{arg}' 에 해당하는 챕터가 없습니다")
                return ""
            return str(ch["t"]) if kind == "t" else mmss(ch["t"])
        if kind == "icon":
            if arg == "github":
                return GITHUB_SVG
            inner = icons.get(arg)
            if inner is None:
                problems.append(f"{name}: 아이콘 '{arg}' 가 없습니다")
                return ""
            return ('<svg class="ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" '
                    f'stroke-linejoin="round" aria-hidden="true" focusable="false">{inner}</svg>')
        if kind in ctx and not arg:
            return ctx[kind]
        problems.append(f"{name}: 알 수 없는 자리표시자 {m.group(0)}")
        return ""

    result = PLACEHOLDER.sub(sub, text)
    if problems:
        die("\n  ".join(problems))
    return result


def repo_slug(arg: str | None) -> str:
    if arg:
        return arg
    if os.environ.get("GITHUB_REPOSITORY"):
        return os.environ["GITHUB_REPOSITORY"]
    try:
        url = subprocess.run(["git", "remote", "get-url", "origin"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
        m = re.search(r"github\.com[:/]([^/]+/[^/.]+?)(?:\.git)?$", url)
        if m:
            return m.group(1)
    except Exception:  # noqa: BLE001 — git 이 없거나 원격이 없으면 기본값
        pass
    return DEFAULT_REPO


def short_commit() -> str:
    if os.environ.get("GITHUB_SHA"):
        return os.environ["GITHUB_SHA"][:7]
    try:
        return subprocess.run(["git", "rev-parse", "--short=7", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip() or "local"
    except Exception:  # noqa: BLE001
        return "local"


def check_links(out: pathlib.Path) -> None:
    """만든 페이지가 가리키는 내 사이트 안의 파일이 모두 있는지 확인합니다."""
    missing = []
    for page in PAGES:
        text = (out / page).read_text(encoding="utf-8")
        for m in re.finditer(r'(?:href|src|poster)="([^"#?]+)(?:[?#][^"]*)?"', text):
            ref = m.group(1)
            if re.match(r"^(https?:|mailto:|data:|//)", ref):
                continue
            if not (out / ref).exists():
                missing.append(f"{page}: {ref}")
    if missing:
        die("페이지가 가리키는 파일이 없습니다:\n  " + "\n  ".join(sorted(set(missing))))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=str(ROOT / "_site"))
    ap.add_argument("--repo", help="owner/name (기본: GITHUB_REPOSITORY → git 원격 → 기본값)")
    ap.add_argument("--base-url", default=os.environ.get("PAGES_BASE_URL", ""), help="배포 주소(공유 미리보기 이미지용). 기본: https://<owner>.github.io/<name>/")
    args = ap.parse_args()
    out = pathlib.Path(args.out).resolve()
    if out in (ROOT, SRC, VIDEO_DIR):
        die(f"출력 위치가 위험합니다: {out}")

    mp4, srt, chap, thumb, poster = (VIDEO_DIR / f"{BASENAME}{ext}" for ext in (".mp4", ".srt", ".chapters.txt", ".thumbnail.png", ".poster.jpg"))
    mp4_en, srt_en = (VIDEO_DIR / f"{BASENAME_EN}{ext}" for ext in (".mp4", ".srt"))
    decks = {lang: SLIDES_DIR / name for lang, name in DECK_NAMES.items()}
    for f in (mp4, srt, chap, thumb, poster, mp4_en, srt_en, *decks.values(), SRC / "index.html", SRC / "doc.html"):
        if not f.exists():
            hint = "  (덱은 python scripts/publish_deck.py <덱.pptx> --lang ko|en 으로 slides/ 에 복사하세요)" if f.parent == SLIDES_DIR else ""
            die(f"필요한 파일이 없습니다: {f.relative_to(ROOT)}{hint}")

    slug = repo_slug(args.repo)
    owner, name = slug.split("/", 1)
    base = args.base_url or (f"https://{owner}.github.io/" if name.lower() == f"{owner.lower()}.github.io" else f"https://{owner}.github.io/{name}/")
    base = base.rstrip("/") + "/"

    chapters = read_chapters(chap)
    chapter_by_key = {}
    for key, prefix in CHAPTER_KEYS.items():
        hit = next((c for c in chapters if c["title"].startswith(prefix)), None)
        if hit:
            chapter_by_key[key] = hit
    duration = mp4_duration(mp4)
    cues = parse_srt(srt)
    docs = docs_info()
    icons = load_icons()
    now = dt.datetime.now(KST)
    d_min, d_sec = divmod(int(round(duration)), 60)
    deck_stats = {lang: deck_counts(path) for lang, path in decks.items()}
    ctx = {
        "owner": owner, "repo": name, "repo_url": f"https://github.com/{slug}", "base_url": base,
        "duration": f"{d_min}분 {d_sec}초", "duration_mmss": f"{d_min}:{d_sec:02d}", "size_mb": f"{mp4.stat().st_size / 1e6:.1f}MB",
        "chapter_count": str(len(chapters)), "chapters_html": chapters_html(chapters), "transcript_html": transcript_html(cues, chapters),
        "docs_cards": docs_cards(docs), "docs_json": json.dumps({d["slug"]: d["title"] for d in docs}, ensure_ascii=False),
        "commit": short_commit(), "build_date": now.strftime("%Y-%m-%d %H:%M KST"), "video_file": mp4.name, "srt_file": srt.name, "vtt_file": f"{BASENAME}.vtt",
        "video_en_file": mp4_en.name, "srt_en_file": srt_en.name, "duration_en": minutes_text(mp4_duration(mp4_en), english=True), "size_en_mb": f"{mp4_en.stat().st_size / 1e6:.1f}MB",
    }
    for lang, path in decks.items():
        rel = f"slides/{path.name}"
        ctx.update({f"pptx_{lang}": rel, f"pptx_{lang}_mb": f"{path.stat().st_size / 1e6:.0f}MB", f"viewer_{lang}": viewer_url(base, rel),
                    f"slides_{lang}_count": str(deck_stats[lang][0]), f"clips_{lang}_count": str(deck_stats[lang][1])})

    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    shutil.copytree(SRC / "assets", out / "assets")
    (out / "fonts").mkdir()
    shutil.copy2(STATIC / "fonts/PretendardVariable.woff2", out / "fonts")
    (out / "vendor").mkdir()
    for lib in ("marked.mjs", "purify.mjs"):
        shutil.copy2(STATIC / "vendor" / lib, out / "vendor" / lib)
    shutil.copy2(mp4, out / mp4.name)
    shutil.copy2(srt, out / srt.name)
    shutil.copy2(mp4_en, out / mp4_en.name)
    shutil.copy2(srt_en, out / srt_en.name)
    (out / "slides").mkdir()
    for path in decks.values():
        shutil.copy2(path, out / "slides" / path.name)
    shutil.copy2(thumb, out / "thumbnail.png")  # 공유 미리보기(og:image)용
    shutil.copy2(poster, out / "poster.jpg")     # 재생 전 플레이어에 보이는 16:9 화면
    write_vtt(cues, out / ctx["vtt_file"])
    (out / "docs").mkdir()
    for d in DOCS_DIR.glob("*.md"):
        shutil.copy2(d, out / "docs" / d.name)
    notices = ROOT / "THIRD_PARTY_NOTICES.md"
    if notices.exists():
        shutil.copy2(notices, out / "docs" / "third-party-notices.md")
    (out / ".nojekyll").write_text("")

    for page in PAGES:
        (out / page).write_text(render((SRC / page).read_text(encoding="utf-8"), ctx, chapter_by_key, icons, page), encoding="utf-8")
    check_links(out)

    total = sum(p.stat().st_size for p in out.rglob("*") if p.is_file())
    print(f"✔ {out}  ({total / 1e6:.1f}MB)")
    print(f"  영상 {ctx['duration']} · {ctx['size_mb']} · 챕터 {len(chapters)}개 · 대본 {len(cues)}줄 · 문서 {len(docs)}개")
    print(f"  영문 영상 {ctx['duration_en']} · {ctx['size_en_mb']} · 슬라이드 한국어 {ctx['slides_ko_count']}장({ctx['pptx_ko_mb']}) · 영어 {ctx['slides_en_count']}장({ctx['pptx_en_mb']})")
    print(f"  슬라이드 보기 {ctx['viewer_ko']}")
    print(f"  주소 {base}   저장소 https://github.com/{slug}   커밋 {ctx['commit']}")
    unmapped = [c["title"] for c in chapters if not any(c is v for v in chapter_by_key.values())]
    if unmapped:
        print(f"  ℹ 카드 연결이 없는 챕터: {', '.join(unmapped)}")
    for big in (mp4, mp4_en, *decks.values()):
        if big.stat().st_size > 100 * 1024 * 1024:
            print(f"  ⚠ {big.name} 이(가) 100MB 를 넘습니다 — GitHub 저장소 파일 한도(100MB)를 넘어 push 할 수 없습니다(영상은 compose.py --crf 값을 올리고, 덱은 슬라이드 속 클립 화질을 낮추세요)")


if __name__ == "__main__":
    main()
