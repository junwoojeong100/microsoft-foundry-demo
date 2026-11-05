#!/usr/bin/env python3
"""개발용 SSE 클라이언트.

    python scripts/sse_client.py /api/chat '{"agent":"knowledge","text":"연차 알려줘"}' [--base http://localhost:8765]
"""
import json
import sys
import time

import httpx


def main() -> None:
    base = "http://localhost:8765"
    args = sys.argv[1:]
    if "--base" in args:
        i = args.index("--base")
        base = args[i + 1]
        del args[i:i + 2]
    path, body = args[0], json.loads(args[1])
    t0 = time.time()
    with httpx.stream("POST", base + path, json=body, timeout=300) as r:
        if r.status_code != 200:
            print("HTTP", r.status_code, r.read()[:500])
            return
        for line in r.iter_lines():
            if not line.startswith("data: "):
                continue
            ev = json.loads(line[6:])
            t = ev.get("type")
            at = f"[{time.time() - t0:5.1f}s]"
            if t in ("text", "delta", "reasoning"):
                continue
            if t == "step":
                d = ev.get("detail", {})
                brief = {k: (v if not isinstance(v, str) else v[:90]) for k, v in d.items() if k in ("queries", "arguments", "query", "output", "tools", "results")}
                if ev["status"] == "done" or ev["kind"] != "reasoning":
                    print(at, "STEP", ev["kind"], ev["status"], ev["title"], json.dumps(brief, ensure_ascii=False)[:260], ev.get("ms", ""))
            elif t == "final":
                print(at, "FINAL", json.dumps({"citations": ev["citations"], "files": ev["files"]}, ensure_ascii=False)[:500])
                print("----- answer -----")
                print(ev["text"][:1800])
                print("------------------")
            else:
                print(at, t.upper(), json.dumps({k: v for k, v in ev.items() if k != "type"}, ensure_ascii=False)[:500])


if __name__ == "__main__":
    main()
