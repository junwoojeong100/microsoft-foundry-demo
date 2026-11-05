#!/usr/bin/env python3
"""장면 영상(recording/raw/<장면>/scene.mp4) + 내레이션(recording/audio/*.mp3) → 최종 영상(video/…mp4) 조립.

    python recording/compose.py --check            # 장면별 길이·내레이션 겹침·누락 점검만
    python recording/compose.py                    # 최종 영상 + 챕터 + 자막(SRT) + 썸네일·포스터
    python recording/compose.py --crf 28           # 용량을 더 줄이고 싶을 때(숫자가 클수록 작고 거칩니다)

하는 일
  1) 장면마다 '내레이션이 놓일 시각'(scene.json 의 says)에 맞춰 음성 트랙을 만들고, 영상 길이와 정확히 같게 맞춥니다.
  2) 모든 장면 음성을 이어 붙여 음량을 한 번에 평탄화(EBU R128 -16 LUFS)합니다.
  3) 장면 영상을 이어 붙여 한 번에 인코딩하고(H.264, GitHub 의 파일당 100MB 제한 안에 들도록 CRF 로 조절), 챕터를 넣습니다.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import subprocess
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from recorder import split_caption  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent
REPO = ROOT.parent
RAW = ROOT / "raw"
AUDIO = ROOT / "audio"
OUT_DIR = REPO / "video"
BASENAME = "microsoft-foundry-demo-ko"
SR = 48000

# (장면, 챕터 제목) — 챕터 제목이 있으면 그 장면(앞이 장 구분 카드면 카드부터)에서 새 챕터가 시작됩니다.
ORDER: list[tuple[str, str | None]] = [
    ("S00_title", "오프닝"),
    ("S01_intro", None),
    ("S02_arch", "Foundry 구조"),
    ("C02_chapter", "배포 — azd up 한 줄"),
    ("S03_deploy", None),
    ("C03_chapter", "직원 경험 · 지식 검색 (Contoso Guide)"),
    ("S05_knowledge", None),
    ("S06_pay", "직원 경험 · 업무 자동화 (Contoso Pay)"),
    ("S07_analyst", "직원 경험 · 데이터 분석 (Contoso Analyst)"),
    ("S08_architect", "직원 경험 · 최신 지식 MCP (Contoso Architect)"),
    ("S09_chat", "직원 경험 · 일반 채팅과 모델 선택"),
    ("S10_safety", "직원 경험 · 안전장치"),
    ("S10b_code", "에이전트는 코드로"),
    ("C04_chapter", "관리자 · 모델 (Foundry 포털)"),
    ("P01_models", None),
    ("P02_agents", "관리자 · 에이전트"),
    ("P03_guard", "관리자 · 가드레일"),
    ("P04_trace", "관리자 · 추적"),
    ("P05_eval", "관리자 · 평가"),
    ("P06_ops", "관리자 · 운영과 거버넌스"),
    ("S12a_ent", "엔터프라이즈 도입 체크리스트"),
    ("S12_outro", "정리와 다음 단계"),
]


def run(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, check=True, **kw)


def probe_duration(path: pathlib.Path) -> float:
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)], capture_output=True, text=True, check=True)
    return float(r.stdout.strip())


def load_scene(name: str) -> dict:
    d = RAW / name
    mp4, js = d / "scene.mp4", d / "scene.json"
    if not mp4.exists() or not js.exists():
        raise FileNotFoundError(f"{name}: 녹화가 없습니다 ({mp4}) — python recording/record.py {name}")
    info = json.loads(js.read_text())
    info["file"] = str(mp4)
    info["real"] = probe_duration(mp4)
    return info


def fmt(t: float) -> str:
    t = max(0.0, t)
    return f"{int(t // 60):02d}:{t % 60:05.2f}"


def check(scenes: list[dict]) -> list[str]:
    problems: list[str] = []
    manifest = json.loads((AUDIO / "manifest.json").read_text())
    t0 = 0.0
    print(f"{'시작':>8}  {'길이':>7}  장면")
    for s in scenes:
        says = s["says"]
        print(f"{fmt(t0):>8}  {s['real']:7.1f}  {s['name']}  (내레이션 {len(says)}개)")
        end = 0.0
        for e in says:
            if e["key"] not in manifest:
                problems.append(f"{s['name']}: 대본에 없는 내레이션 {e['key']}")
            if e["t"] < end - 0.05:
                problems.append(f"{s['name']}: {e['key']} 가 앞 내레이션과 {end - e['t']:.1f}초 겹칩니다")
            end = e["t"] + e["dur"]
        if says and end > s["real"] + 0.3:
            problems.append(f"{s['name']}: 마지막 내레이션이 장면보다 {end - s['real']:.1f}초 깁니다(잘림)")
        if abs(s["real"] - s["duration"]) > 0.5:
            problems.append(f"{s['name']}: 영상 길이 {s['real']:.1f}초 ≠ 기록 {s['duration']:.1f}초")
        t0 += s["real"]
    print(f"\n합계 {fmt(t0)} ({t0 / 60:.1f}분)")
    return problems


def scene_audio(s: dict, out: pathlib.Path) -> None:
    dur = s["real"]
    says = s["says"]
    if not says:
        run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", f"anullsrc=r={SR}:cl=mono", "-t", f"{dur:.3f}", "-c:a", "pcm_s16le", str(out)])
        return
    cmd = ["ffmpeg", "-y", "-loglevel", "error"]
    parts = []
    for i, e in enumerate(says):
        cmd += ["-i", str(AUDIO / f"{e['key']}.mp3")]
        parts.append(f"[{i}:a]aresample={SR},aformat=channel_layouts=mono,adelay={int(round(e['t'] * 1000))}:all=1[a{i}]")
    mix = "".join(f"[a{i}]" for i in range(len(says))) + f"amix=inputs={len(says)}:normalize=0:duration=longest,apad=whole_dur={dur:.3f},atrim=0:{dur:.3f}[m]"
    cmd += ["-filter_complex", ";".join(parts + [mix]), "-map", "[m]", "-ar", str(SR), "-ac", "1", "-c:a", "pcm_s16le", str(out)]
    run(cmd)


def normalize(src: pathlib.Path, dst: pathlib.Path) -> None:
    """EBU R128 두 번 측정(선형) — 음량이 오르내리지 않고 전체를 같은 비율로만 맞춥니다."""
    target = "I=-16:TP=-1.5:LRA=11"
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(src), "-af", f"loudnorm={target}:print_format=json", "-f", "null", "-"], capture_output=True, text=True, check=True)
    m = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", r.stderr, re.S)
    if not m:
        raise RuntimeError("loudnorm 측정 실패")
    j = json.loads(m.group(0))
    af = (f"loudnorm={target}:measured_I={j['input_i']}:measured_TP={j['input_tp']}:measured_LRA={j['input_lra']}:"
          f"measured_thresh={j['input_thresh']}:offset={j['target_offset']}:linear=true:print_format=summary")
    run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(src), "-af", af, "-ar", str(SR), "-ac", "1", "-c:a", "pcm_s16le", str(dst)])
    print(f"  음량 {j['input_i']} LUFS → -16 LUFS")


def build_chapters(scenes: list[dict]) -> list[dict]:
    titles = dict(ORDER)
    chapters: list[dict] = []
    t = 0.0
    for s in scenes:
        if titles.get(s["name"]):
            chapters.append({"start": t, "title": titles[s["name"]]})
        t += s["real"]
    for i, c in enumerate(chapters):
        c["end"] = chapters[i + 1]["start"] if i + 1 < len(chapters) else t
    return chapters


def write_srt(scenes: list[dict], path: pathlib.Path) -> None:
    manifest = json.loads((AUDIO / "manifest.json").read_text())
    n = 0
    t0 = 0.0
    lines: list[str] = []

    def ts(x: float) -> str:
        ms = int(round(x * 1000))
        return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"

    for s in scenes:
        for e in s["says"]:
            parts = split_caption(manifest[e["key"]]["text"])
            weights = [max(8, len(p)) for p in parts]
            total = sum(weights)
            cur = t0 + e["t"]
            for p, w in zip(parts, weights):
                d = e["dur"] * w / total
                n += 1
                lines += [str(n), f"{ts(cur)} --> {ts(cur + d)}", p, ""]
                cur += d
        t0 += s["real"]
    path.write_text("\n".join(lines), encoding="utf-8")


def write_chapters(chapters: list[dict], meta: pathlib.Path, txt: pathlib.Path, title: str) -> None:
    out = [";FFMETADATA1", f"title={title}"]
    for c in chapters:
        out += ["[CHAPTER]", "TIMEBASE=1/1000", f"START={int(c['start'] * 1000)}", f"END={int(c['end'] * 1000)}", f"title={c['title']}"]
    meta.write_text("\n".join(out) + "\n", encoding="utf-8")
    rows = []
    for c in chapters:
        s = int(c["start"])
        rows.append(f"{s // 60:02d}:{s % 60:02d} {c['title']}")
    txt.write_text("\n".join(rows) + "\n", encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--crf", type=int, default=27)
    ap.add_argument("--preset", default="slow")
    ap.add_argument("--out", default=BASENAME)
    ap.add_argument("--skip-missing", action="store_true", help="녹화가 없는 장면은 건너뜁니다(중간 점검용)")
    args = ap.parse_args()

    scenes: list[dict] = []
    for name, _ in ORDER:
        try:
            scenes.append(load_scene(name))
        except FileNotFoundError as exc:
            if not args.skip_missing:
                sys.exit(str(exc))
            print("건너뜀:", exc)
    problems = check(scenes)
    for p in problems:
        print("  ⚠", p)
    if args.check:
        sys.exit(1 if problems else 0)
    if problems:
        sys.exit("위 문제를 해결한 뒤 다시 실행하세요")

    OUT_DIR.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="compose_") as tmp:
        tmp_p = pathlib.Path(tmp)
        wavs = []
        for s in scenes:
            w = tmp_p / f"{s['name']}.wav"
            scene_audio(s, w)
            wavs.append(w)
        (tmp_p / "wavs.txt").write_text("\n".join(f"file '{w}'" for w in wavs))
        raw_wav = tmp_p / "narration_raw.wav"
        run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(tmp_p / "wavs.txt"), "-c", "copy", str(raw_wav)])
        narr = tmp_p / "narration.wav"
        normalize(raw_wav, narr)

        (tmp_p / "videos.txt").write_text("\n".join(f"file '{s['file']}'" for s in scenes))
        chapters = build_chapters(scenes)
        title = "Microsoft Foundry 데모 — Contoso AI (한국어)"
        meta = tmp_p / "chapters.ffmeta"
        write_chapters(chapters, meta, OUT_DIR / f"{args.out}.chapters.txt", title)
        write_srt(scenes, OUT_DIR / f"{args.out}.srt")

        out = OUT_DIR / f"{args.out}.mp4"
        total = sum(s["real"] for s in scenes)
        print(f"\n인코딩 중… (영상 {total / 60:.1f}분, CRF {args.crf}, preset {args.preset})")
        run(["ffmpeg", "-y", "-loglevel", "error", "-stats", "-f", "concat", "-safe", "0", "-i", str(tmp_p / "videos.txt"), "-i", str(narr), "-i", str(meta),
             "-map", "0:v:0", "-map", "1:a:0", "-map_metadata", "2", "-map_chapters", "2",
             "-c:v", "libx264", "-preset", args.preset, "-crf", str(args.crf), "-g", "60", "-pix_fmt", "yuv420p", "-r", "30",
             "-c:a", "aac", "-b:a", "80k", "-ar", str(SR), "-ac", "1", "-shortest", "-movflags", "+faststart", str(out)])
    thumb = OUT_DIR / f"{args.out}.thumbnail.png"
    # 타이틀 슬라이드가 다 채워진 시점(24초)의 화면에서 아래 자막 바(976px 아래)를 잘라 썸네일로 씁니다
    run(["ffmpeg", "-y", "-loglevel", "error", "-ss", "24", "-i", str(out), "-frames:v", "1", "-vf", "crop=1920:976:0:0", str(thumb)])
    # 웹 플레이어의 포스터(16:9 전체 화면): 타이틀 내레이션이 끝나 자막이 지워진 직후(31.2초)의 프레임
    poster = OUT_DIR / f"{args.out}.poster.jpg"
    run(["ffmpeg", "-y", "-loglevel", "error", "-ss", "31.2", "-i", str(out), "-frames:v", "1", "-q:v", "3", str(poster)])
    size = out.stat().st_size / 1e6
    print(f"\n✔ {out.relative_to(REPO)}  {size:.1f}MB  {probe_duration(out) / 60:.1f}분")
    if size > 95:
        print("⚠ GitHub 파일당 100MB 제한에 가깝습니다 — --crf 값을 올려 다시 실행하거나 Git LFS/Release 를 쓰세요")


if __name__ == "__main__":
    main()
