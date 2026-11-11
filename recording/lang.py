"""녹화 언어 선택 — 환경 변수 REC_LANG (ko 기본 | en).

    REC_LANG=en python recording/record.py all-slides      # 영어판: 대본 script_en.py · 음성 audio_en/ · 장면 raw_en/ · 슬라이드 slides_en.html
    REC_LANG=en python recording/compose.py                # → video/microsoft-foundry-demo-en.mp4

한국어판은 기존 파일(audio/, raw/, script_ko.py, slides.html …)을 그대로 씁니다. 영어판 산출물은 이름 끝에 `_en` 이 붙은 별도 폴더에 만들어져 서로 섞이지 않습니다.
"""
from __future__ import annotations

import os
from typing import TypeVar

T = TypeVar("T")

LANG = "en" if os.environ.get("REC_LANG", "ko").strip().lower() == "en" else "ko"
SUFFIX = "" if LANG == "ko" else f"_{LANG}"


def pick(ko: T, en: T) -> T:
    return en if LANG == "en" else ko
