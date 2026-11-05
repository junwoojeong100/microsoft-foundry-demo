#!/usr/bin/env python3
"""asciinema 캐스트의 개인 식별 값(구독 ID·테넌트 ID·이메일·계정 이름)을 같은 길이의 가짜 값으로 바꿔서 저장합니다.

    python recording/mask_cast.py recording/raw/azd_up_final.cast recording/assets/azd_up.cast

pty_capture.py 로 기록한 원본(recording/raw/, 저장소에 올리지 않음)에는 실제 값이 들어 있으므로,
영상 장면(S03_deploy)과 저장소에는 이 스크립트로 가린 파일(recording/assets/)을 씁니다.
"""
from __future__ import annotations

import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from terminal_cfg import load_cast  # noqa: E402


def main() -> None:
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    src, dst = sys.argv[1:3]
    header, events = load_cast(src, mask=True)
    lines = [json.dumps(header, ensure_ascii=False)]
    lines += [json.dumps([t, "o", data], ensure_ascii=False) for t, data in events]
    out = pathlib.Path(dst)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"{src} → {dst}  (이벤트 {len(events)}개, {out.stat().st_size / 1024:.0f}KB)")


if __name__ == "__main__":
    main()
