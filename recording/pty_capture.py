#!/usr/bin/env python3
"""터미널 세션을 '실제로 실행하면서' 기록합니다 (asciinema v2 형식 — 한 줄에 [시간, "o", 출력]).

    python recording/pty_capture.py OUT.cast --cwd DIR --cols 118 --rows 30 -- azd up --no-prompt

가짜 영상이 아니라 실제 명령의 출력과 실제 소요 시간이 그대로 남습니다. 재생은 recording/terminal.html(xterm.js)이 합니다.
"""
from __future__ import annotations

import argparse
import fcntl
import json
import os
import pty
import select
import struct
import subprocess
import sys
import termios
import time


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--cwd", default=".")
    ap.add_argument("--cols", type=int, default=118)
    ap.add_argument("--rows", type=int, default=30)
    ap.add_argument("--env", action="append", default=[], help="KEY=VALUE")
    argv = sys.argv[1:]
    cmd: list[str] = []
    if "--" in argv:  # `--` 뒤는 전부 실행할 명령
        i = argv.index("--")
        argv, cmd = argv[:i], argv[i + 1:]
    args = ap.parse_args(argv)
    if not cmd:
        ap.error("실행할 명령이 필요합니다 ( -- 뒤에 적으세요)")

    env = dict(os.environ, TERM="xterm-256color", COLUMNS=str(args.cols), LINES=str(args.rows), NO_COLOR="")
    env.pop("NO_COLOR", None)
    for kv in args.env:
        k, v = kv.split("=", 1)
        env[k] = v

    # macOS 는 자식이 끝나 슬레이브가 닫히면 아직 읽지 않은 출력을 버릴 수 있으므로, 부모가 슬레이브를 끝까지 붙들고 있다가 다 읽은 뒤 닫습니다.
    fd, slave = pty.openpty()
    fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack("HHHH", args.rows, args.cols, 0, 0))

    def _ctty() -> None:
        os.setsid()
        fcntl.ioctl(0, termios.TIOCSCTTY, 0)

    proc = subprocess.Popen(cmd, cwd=args.cwd, env=env, stdin=slave, stdout=slave, stderr=slave, preexec_fn=_ctty, close_fds=True)
    pid = proc.pid

    t0 = time.time()
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(json.dumps({"version": 2, "width": args.cols, "height": args.rows, "timestamp": int(t0), "command": " ".join(cmd)}) + "\n")
        buf = b""
        quiet_after_exit = 0
        while True:
            try:
                r, _, _ = select.select([fd], [], [], 0.2)
            except InterruptedError:
                continue
            if r:
                try:
                    data = os.read(fd, 65536)
                except OSError:
                    break
                if not data:
                    break
                quiet_after_exit = 0
                buf += data
                try:  # 멀티바이트 문자가 잘리지 않게 디코딩 가능한 만큼만 기록
                    text = buf.decode("utf-8")
                    buf = b""
                except UnicodeDecodeError as e:
                    text, buf = buf[: e.start].decode("utf-8"), buf[e.start:]
                if text:
                    f.write(json.dumps([round(time.time() - t0, 3), "o", text], ensure_ascii=False) + "\n")
                    f.flush()
                    sys.stdout.write(text)
                    sys.stdout.flush()
            elif proc.poll() is not None:
                quiet_after_exit += 1
                if quiet_after_exit >= 3:  # 종료 후 0.6초 동안 더 읽을 게 없으면 끝
                    break
    os.close(slave)
    os.close(fd)
    code = proc.wait()
    print(f"\n[capture] 종료 코드 {code}, 소요 {time.time() - t0:.0f}초 → {args.out}")
    return code


if __name__ == "__main__":
    sys.exit(main())
