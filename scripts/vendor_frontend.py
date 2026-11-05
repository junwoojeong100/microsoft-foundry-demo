#!/usr/bin/env python3
"""프런트엔드 외부 라이브러리를 src/web/static/vendor 에 내려받습니다 (빌드 도구 없이 쓰는 ESM).

    python scripts/vendor_frontend.py            # 없는 파일만 받음
    python scripts/vendor_frontend.py --force    # 모두 다시 받음

받은 파일은 저장소에 그대로 포함되어 있으므로, 이 스크립트는 버전을 올릴 때만 실행하면 됩니다.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import urllib.request

CDN = "https://cdn.jsdelivr.net/npm"
ROOT = pathlib.Path(__file__).resolve().parents[1]
STATIC = ROOT / "src/web/static"
VENDOR = STATIC / "vendor"

LIBS = {
    "vendor/preact.mjs": "preact@10.24.3/dist/preact.module.js",
    "vendor/preact-hooks.mjs": "preact@10.24.3/hooks/dist/hooks.module.js",
    "vendor/htm.mjs": "htm@3.1.1/dist/htm.module.js",
    "vendor/marked.mjs": "marked@15.0.0/lib/marked.esm.js",
    "vendor/purify.mjs": "dompurify@3.2.3/dist/purify.es.mjs",
    "vendor/highlight.mjs": "@highlightjs/cdn-assets@11.10.0/es/highlight.min.js",
    "vendor/hljs-github.css": "@highlightjs/cdn-assets@11.10.0/styles/github.min.css",
    "fonts/PretendardVariable.woff2": "pretendard@1.3.9/dist/web/variable/woff2/PretendardVariable.woff2",
}

LUCIDE = "lucide-static@1.68.0"
ICONS = """plus send arrow-up paperclip book-open chart-column chart-line receipt cloud scale shield-check shield-alert
flask-conical activity search code plug square-function globe brain sparkles check x chevron-down chevron-right download image
file-text lock key-round zap clock coins thumbs-up thumbs-down copy refresh-cw message-square message-square-plus panel-left
user log-out database git-compare layers bot cpu rocket terminal external-link triangle-alert circle-check loader eye
wand-sparkles gauge timer trophy trending-up server network blocks badge-check fingerprint file-search table play square
user-check hand list-checks arrow-right info wrench workflow bell folder link hash pencil trash-2 ellipsis route
sliders-horizontal scan-text flag cloud-upload boxes id-card building-2 history circle-alert ban user-round map-pin arrow-up-right""".split()


def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "microsoft-foundry-demo/vendor"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read()


def build_icons() -> str:
    icons: dict[str, str] = {}
    for name in ICONS:
        svg = fetch(f"{CDN}/{LUCIDE}/icons/{name}.svg").decode()
        svg = re.sub(r"<!--.*?-->", "", svg, flags=re.S).strip()
        inner = re.sub(r"^<svg[^>]*>|</svg>$", "", svg, flags=re.S).strip()
        icons[name] = re.sub(r"\s+", " ", inner)
    body = json.dumps(icons, ensure_ascii=False, indent=0)
    return (
        "// Lucide 아이콘(ISC 라이선스) — scripts/vendor_frontend.py 가 생성한 파일입니다. 직접 수정하지 마세요.\n"
        f"// {LUCIDE}\nexport const ICONS = {body};\n"
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    for rel, src in LIBS.items():
        dest = STATIC / rel
        if dest.exists() and not args.force:
            print(f"· {rel} (있음)")
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(fetch(f"{CDN}/{src}"))
        print(f"✔ {rel}  {dest.stat().st_size // 1024} KB")
    icons = VENDOR / "icons.js"
    if args.force or not icons.exists():
        icons.write_text(build_icons(), encoding="utf-8")
        print(f"✔ vendor/icons.js  {len(ICONS)}개 아이콘")


if __name__ == "__main__":
    main()
