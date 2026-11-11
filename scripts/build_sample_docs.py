#!/usr/bin/env python3
"""sample_content.py 의 가상 사규를 PDF 로 만듭니다 (Playwright/Chromium 의 page.pdf 사용).

    python scripts/build_sample_docs.py              # 한국어: sample_content.py  → src/web/seed/knowledge/
    python scripts/build_sample_docs.py --lang en    # English: sample_content_en.py → src/web/seed_en/knowledge/
    python scripts/build_sample_docs.py --out DIR    # 출력 폴더를 직접 지정 (기본값을 덮어쓰지 않고 시험할 때)

결과: src/web/seed/knowledge/*.pdf  — 데모 앱이 시작할 때 Foundry 벡터 스토어에 올립니다.
"""
from __future__ import annotations

import argparse
import base64
import functools
import html
import importlib
import os
import pathlib
import sys

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(pathlib.Path(__file__).parent))

ROOT = pathlib.Path(__file__).resolve().parents[1]
FONT = ROOT / "src/web/static/fonts/PretendardVariable.woff2"

# 언어별 설정 — ko 의 출력은 기존 PDF 와 같아야 하므로 ko 항목은 바꾸지 마세요.
# embed_font: set_content 페이지(about:blank)는 file:// 글꼴을 못 읽어 시스템 글꼴로 대체되므로,
#   en 은 Pretendard 를 data URI 로 직접 넣습니다 (ko 는 기존 PDF 와 같은 대체 글꼴을 유지).
LANGS = {
    "ko": {
        "content": "sample_content",
        "out": ROOT / "src/web/seed/knowledge",
        "brand": "사내 규정",
        "doc_no": "문서번호",
        "owner": "소관",
        "revised": "개정일",
        "level": "등급",
        "footer": "데모용 가상 문서 (실제 규정이 아닙니다)",
        "embed_font": False,
        "css": "",
    },
    "en": {
        "content": "sample_content_en",
        "out": ROOT / "src/web/seed_en/knowledge",
        "brand": "Company policy",
        "doc_no": "Document no.",
        "owner": "Owner",
        "revised": "Revised",
        "level": "Classification",
        "footer": "Fictional demo document (not an actual policy)",
        "embed_font": True,
        "css": "h2 { break-after: avoid; }\n",
    },
}

CSS = f"""
@font-face {{ font-family: 'Pretendard'; src: url('file://{FONT}') format('woff2'); font-weight: 100 900; }}
* {{ box-sizing: border-box; }}
body {{ font-family: 'Pretendard', 'Apple SD Gothic Neo', sans-serif; color: #1f2937; font-size: 10.5pt; line-height: 1.65; margin: 0; }}
.head {{ border-bottom: 3px solid #1e40af; padding-bottom: 10px; margin-bottom: 18px; }}
.brand {{ font-size: 9pt; color: #1e40af; font-weight: 700; letter-spacing: .06em; }}
h1 {{ font-size: 21pt; margin: 4px 0 8px; color: #111827; letter-spacing: -.02em; }}
.meta {{ display: flex; gap: 18px; font-size: 9pt; color: #4b5563; }}
.meta b {{ color: #111827; font-weight: 600; }}
.badge {{ display: inline-block; padding: 1px 8px; border-radius: 999px; background: #e0e7ff; color: #3730a3; font-weight: 600; }}
h2 {{ font-size: 12.5pt; color: #1e3a8a; margin: 20px 0 8px; padding-left: 9px; border-left: 4px solid #3b82f6; }}
p {{ margin: 6px 0; }}
ul {{ margin: 6px 0 6px 0; padding-left: 20px; }}
li {{ margin: 3px 0; }}
table {{ border-collapse: collapse; width: 100%; margin: 8px 0 10px; font-size: 9.8pt; }}
th {{ background: #eff6ff; color: #1e3a8a; text-align: left; font-weight: 700; }}
th, td {{ border: 1px solid #cbd5e1; padding: 5px 9px; vertical-align: top; }}
.note {{ margin: 10px 0; padding: 9px 12px; background: #fff7ed; border-left: 4px solid #f97316; border-radius: 4px; color: #7c2d12; }}
"""


def render_block(block) -> str:
    kind = block[0]
    if kind == "p":
        return f"<p>{html.escape(block[1])}</p>"
    if kind == "ul":
        return "<ul>" + "".join(f"<li>{html.escape(i)}</li>" for i in block[1]) + "</ul>"
    if kind == "note":
        return f"<div class='note'>{html.escape(block[1])}</div>"
    if kind == "table":
        head = "".join(f"<th>{html.escape(h)}</th>" for h in block[1])
        rows = "".join("<tr>" + "".join(f"<td>{html.escape(c)}</td>" for c in r) + "</tr>" for r in block[2])
        return f"<table><thead><tr>{head}</tr></thead><tbody>{rows}</tbody></table>"
    raise ValueError(kind)


@functools.cache
def font_data_uri() -> str:
    return "data:font/woff2;base64," + base64.b64encode(FONT.read_bytes()).decode()


def render_doc(doc: dict, company: str, lang: str = "ko") -> str:
    t = LANGS[lang]
    css = CSS + t["css"]
    if t["embed_font"]:
        css = css.replace(f"file://{FONT}", font_data_uri())
    body = "".join(
        f"<h2>{html.escape(title)}</h2>" + "".join(render_block(b) for b in blocks)
        for title, blocks in doc["sections"]
    )
    return f"""<!doctype html><html lang="{lang}"><head><meta charset="utf-8"><style>{css}</style></head><body>
<div class="head"><div class="brand">{html.escape(company)} · {t['brand']}</div>
<h1>{html.escape(doc['title'])}</h1>
<div class="meta"><span>{t['doc_no']} <b>{doc['id']}</b></span><span>{t['owner']} <b>{html.escape(doc['owner'])}</b></span>
<span>{t['revised']} <b>{doc['rev']}</b></span><span>{t['level']} <span class="badge">{html.escape(doc['level'])}</span></span></div></div>
{body}</body></html>"""


def render_footer(company: str, lang: str = "ko") -> str:
    return (
        "<div style=\"width:100%;font-size:8px;color:#6b7280;padding:0 16mm;display:flex;justify-content:space-between;"
        "font-family:'Apple SD Gothic Neo',sans-serif\"><span>" + f"{html.escape(company)} · {LANGS[lang]['footer']}" + "</span>"
        "<span><span class='pageNumber'></span> / <span class='totalPages'></span></span></div>"
    )


def find_chromium() -> str | None:
    cache = pathlib.Path.home() / "Library/Caches/ms-playwright"
    for pat in ("chromium_headless_shell-*/chrome-headless-shell-mac-arm64/chrome-headless-shell",
                "chromium-*/chrome-mac-arm64/Chromium.app/Contents/MacOS/Chromium"):
        found = sorted(cache.glob(pat))
        if found:
            return str(found[-1])
    return None


def main() -> None:
    ap = argparse.ArgumentParser(description="Build the fictional company-policy PDFs.")
    ap.add_argument("--lang", choices=sorted(LANGS), default="ko", help="document language (default: ko)")
    ap.add_argument("--out", type=pathlib.Path, help="output folder (default: the seed folder of the chosen language)")
    args = ap.parse_args()

    content = importlib.import_module(LANGS[args.lang]["content"])
    out = args.out or LANGS[args.lang]["out"]
    out.mkdir(parents=True, exist_ok=True)
    footer = render_footer(content.COMPANY, args.lang)
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=os.environ.get("CHROMIUM_PATH") or find_chromium())
        for doc in content.DOCS:
            page = browser.new_page()
            page.set_content(render_doc(doc, content.COMPANY, args.lang), wait_until="load")
            page.evaluate("document.fonts.ready")
            target = out / doc["file"]
            page.pdf(
                path=str(target), format="A4", print_background=True,
                margin={"top": "16mm", "bottom": "18mm", "left": "16mm", "right": "16mm"},
                display_header_footer=True, header_template="<span></span>", footer_template=footer,
            )
            page.close()
            print(f"✔ {target.name}  ({target.stat().st_size // 1024} KB)")
        browser.close()


if __name__ == "__main__":
    main()
