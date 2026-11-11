"""에디션 언어 선택 — `DEMO_LANG=en` 이면 모델·화면에 나가는 문구가 영어, 그 외에는 한국어(기본)입니다."""
from __future__ import annotations

from typing import TypeVar

from .config import settings

T = TypeVar("T")


def pick(ko: T, en: T) -> T:
    return en if settings.lang == "en" else ko
