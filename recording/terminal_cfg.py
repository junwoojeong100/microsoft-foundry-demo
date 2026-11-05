"""asciinema(v2) 형식 캐스트 → 터미널 재생 페이지용 설정(마스킹·단계 표식·시간 압축 지도)."""
from __future__ import annotations

import json
import pathlib
import re
from typing import Any

ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)|\x1b\(B")

try:
    from masking import personal_terms  # 지금 az login 한 계정에서 알아낸 구독 이름·계정 이름
except ImportError:  # recording/ 이 sys.path 에 없으면 모양으로 알 수 있는 값만 가린다
    def personal_terms() -> tuple[tuple[str, str], ...]:
        return ()

# 같은 길이로 바꿔 ANSI 커서 이동·정렬이 어긋나지 않게 합니다.
MASKS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"), "00000000-0000-0000-0000-000000000000"),
    (re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"), "demo.user@contoso.com"),
    (re.compile(r"[A-Za-z0-9-]+\.onmicrosoft\.com", re.I), "contoso.onmicrosoft.com"),
]


def _same_len(repl: str, n: int) -> str:
    return (repl + " " * n)[:n] if len(repl) < n else repl[:n]


def mask_text(text: str) -> str:
    masks = MASKS + [(re.compile(re.escape(real), re.I), fake) for real, fake in personal_terms()]
    for pat, repl in masks:
        text = pat.sub(lambda m, r=repl: _same_len(r, len(m.group(0))), text)
    return text


def load_cast(path: str | pathlib.Path, mask: bool = True) -> tuple[dict[str, Any], list[list[Any]]]:
    lines = pathlib.Path(path).read_text(encoding="utf-8").splitlines()
    header = json.loads(lines[0])
    events = [json.loads(l) for l in lines[1:] if l.strip()]
    events = [[e[0], e[2]] for e in events if e[1] == "o"]
    if mask:
        whole = "".join(e[1] for e in events)
        masked = mask_text(whole)
        pos = 0
        for e in events:
            n = len(e[1])
            e[1] = masked[pos:pos + n]
            pos += n
    return header, events


def find_markers(events: list[list[Any]], markers: list[tuple[str, str]]) -> list[dict[str, Any]]:
    """[(단계 이름, 찾을 문자열)] → [{name, c(캐스트 시각)}] — ANSI 를 걷어낸 텍스트에서 처음 나타난 시각."""
    chars: list[str] = []
    owner: list[int] = []
    for i, (_, data) in enumerate(events):
        pos = 0
        for m in ANSI.finditer(data):
            seg = data[pos:m.start()]
            chars.extend(seg)
            owner.extend([i] * len(seg))
            pos = m.end()
        seg = data[pos:]
        chars.extend(seg)
        owner.extend([i] * len(seg))
    text = "".join(chars)
    out = []
    last = 0.0
    for name, needle in markers:
        idx = text.find(needle)
        c = events[owner[idx]][0] if idx >= 0 else last
        c = max(c, last)
        out.append({"name": name, "c": round(c, 3)})
        last = c
    return out


def build_map(events: list[list[Any]], stages: list[dict[str, Any]], seconds: list[float]) -> list[dict[str, float]]:
    """단계별로 '재생에 쓸 시간(초)'을 정해 캐스트 구간을 선형으로 늘이거나 줄입니다."""
    total = events[-1][0] + 0.5
    bounds = [0.0] + [s["c"] for s in stages] + [total]  # 구간 = len(stages)+1 (첫 단계 이전 ~ 마지막 단계 끝)
    assert len(seconds) == len(bounds) - 1, f"seconds 는 {len(bounds) - 1}개여야 합니다 (받은 값 {len(seconds)}개)"
    segs = []
    for i, dur in enumerate(seconds):
        c0, c1 = bounds[i], bounds[i + 1]
        if c1 - c0 < 0.05:
            continue
        segs.append({"c0": c0, "c1": c1, "dur": dur})
    return segs


def terminal_cfg(cast_path: str | pathlib.Path, markers: list[tuple[str, str]], seconds: list[float], command: str, title: str,
                 extra: list[str] | None = None) -> dict[str, Any]:
    """extra: 캐스트 끝에 이어 붙일 출력 조각(실제 실행 결과를 같은 형식으로 마무리할 때). 마스킹은 붙인 뒤에 적용한다."""
    header, events = load_cast(cast_path, mask=False)
    t = events[-1][0]
    for chunk in extra or []:
        t += 0.12
        events.append([round(t, 3), chunk])
    whole = "".join(e[1] for e in events)
    masked = mask_text(whole)
    pos = 0
    for e in events:
        n = len(e[1])
        e[1] = masked[pos:pos + n]
        pos += n
    stages = find_markers(events, markers)
    return {
        "cols": header["width"], "rows": header["height"], "events": events, "stages": stages,
        "map": build_map(events, stages, seconds), "command": command, "title": title,
        "cast_seconds": events[-1][0],
    }
