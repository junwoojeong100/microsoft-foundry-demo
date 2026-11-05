#!/usr/bin/env python3
"""sample_content.py 의 가상 사규를 PDF 로 만듭니다 (Playwright/Chromium 의 page.pdf 사용).

    python scripts/build_sample_docs.py

결과: src/web/seed/knowledge/*.pdf  — 데모 앱이 시작할 때 Foundry 벡터 스토어에 올립니다.
"""
from __future__ import annotations

import html
import os
import pathlib
import sys

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from sample_content import COMPANY, DOCS  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "src/web/seed/knowledge"
FONT = ROOT / "src/web/static/fonts/PretendardVariable.woff2"

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


def render_doc(doc: dict) -> str:
    body = "".join(
        f"<h2>{html.escape(title)}</h2>" + "".join(render_block(b) for b in blocks)
        for title, blocks in doc["sections"]
    )
    return f"""<!doctype html><html lang="ko"><head><meta charset="utf-8"><style>{CSS}</style></head><body>
<div class="head"><div class="brand">{html.escape(COMPANY)} · 사내 규정</div>
<h1>{html.escape(doc['title'])}</h1>
<div class="meta"><span>문서번호 <b>{doc['id']}</b></span><span>소관 <b>{html.escape(doc['owner'])}</b></span>
<span>개정일 <b>{doc['rev']}</b></span><span>등급 <span class="badge">{html.escape(doc['level'])}</span></span></div></div>
{body}</body></html>"""


def find_chromium() -> str | None:
    cache = pathlib.Path.home() / "Library/Caches/ms-playwright"
    for pat in ("chromium_headless_shell-*/chrome-headless-shell-mac-arm64/chrome-headless-shell",
                "chromium-*/chrome-mac-arm64/Chromium.app/Contents/MacOS/Chromium"):
        found = sorted(cache.glob(pat))
        if found:
            return str(found[-1])
    return None


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    footer = (
        "<div style=\"width:100%;font-size:8px;color:#6b7280;padding:0 16mm;display:flex;justify-content:space-between;"
        "font-family:'Apple SD Gothic Neo',sans-serif\"><span>{company} · 데모용 가상 문서 (실제 규정이 아닙니다)</span>"
        "<span><span class='pageNumber'></span> / <span class='totalPages'></span></span></div>"
    ).replace("{company}", COMPANY)
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=os.environ.get("CHROMIUM_PATH") or find_chromium())
        for doc in DOCS:
            page = browser.new_page()
            page.set_content(render_doc(doc), wait_until="load")
            page.evaluate("document.fonts.ready")
            target = OUT / doc["file"]
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
