"""Azure AI Speech 로 한국어 내레이션을 만듭니다 — Foundry 리소스의 Speech 엔드포인트를 Entra ID(az login)로 호출하므로 키가 필요 없습니다.

    python recording/tts.py --list                         # 사용 가능한 한국어 음성
    python recording/tts.py --say "안녕하세요" --out /tmp/a.mp3
    python recording/tts.py --build                        # script_ko.py 의 모든 내레이션 합성 (캐시됨)

음성은 recording/audio/<키>.mp3 로 캐시되고, 문장이 바뀐 경우에만 다시 합성합니다(해시 비교).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import subprocess
import sys
import time
from xml.sax.saxutils import escape

import httpx

ROOT = pathlib.Path(__file__).resolve().parent
AUDIO = ROOT / "audio"
VOICE = "ko-KR-SunHiNeural"
FORMAT = "audio-24khz-96kbitrate-mono-mp3"

# 영어 제품명은 한국어 음성이 어색하게 읽으므로, '읽는 문장'에서만 한글 발음으로 바꿉니다(자막은 원문 그대로).
PRONOUNCE = [
    ("Azure Policy", "애저, 폴리시"), ("Microsoft Foundry", "마이크로소프트 파운드리"), ("Foundry", "파운드리"), ("Azure", "애저"), ("azd up", "에이제드디 업"), ("azd down", "에이제드디 다운"),
    ("azd", "에이제드디"), ("GPT-6.1", "지피티 육 점 일"), ("GPT", "지피티"), ("Model Router", "모델 라우터"), ("Entra ID", "엔트라 아이디"),
    ("Entra", "엔트라"), ("Bicep", "바이셉"), ("Container Apps", "컨테이너 앱스"), ("Container App", "컨테이너 앱"), ("Application Insights", "애플리케이션 인사이츠"),
    ("Log Analytics", "로그 애널리틱스"), ("Code Interpreter", "코드 인터프리터"), ("file_search", "파일 서치"), ("MCP", "엠씨피"), ("Prompt Shields", "프롬프트 쉴즈"),
    ("Content Safety", "콘텐츠 세이프티"), ("DeepSeek", "딥시크"), ("Llama", "라마"), ("Mistral", "미스트랄"), ("Kimi", "키미"), ("Grok", "그록"),
    ("Moonshot", "문샷"), ("OpenAI", "오픈에이아이"), ("RBAC", "알비에이씨"), ("API", "에이피아이"), ("PDF", "피디에프"), ("CSV", "씨에스브이"),
    ("VOC", "브이오씨"), ("PII", "피아이아이"), ("SSO", "에스에스오"), ("MFA", "엠에프에이"), ("CI/CD", "씨아이 씨디"), ("Korea Central", "코리아 센트럴"),
    ("ChatGPT", "챗지피티"), ("SDK", "에스디케이"), ("KPI", "케이피아이"), ("ACR", "에이씨알"), ("PTU", "피티유"), ("HR-001", "에이치알 공공일"),
    ("FIN-002", "에프아이엔 공공이"), ("SEC-003", "에스이씨 공공삼"), ("Pay", "페이"), ("PNG", "피엔지"), ("TTFT", "첫 토큰 시간"), ("p95", "피 구십오"),
    ("Responses", "리스폰시스"), ("Playwright", "플레이라이트"), ("Learn", "런"),
    ("Defender", "디펜더"), ("Purview", "퍼뷰"), ("Policy", "폴리시"), ("Microsoft", "마이크로소프트"),
    ("Contoso", "콘토소"), ("Guide", "가이드"), ("Analyst", "애널리스트"), ("Architect", "아키텍트"), ("Anthropic", "앤트로픽"), ("Copilot", "코파일럿"), ("Teams", "팀즈"), ("YAML", "야믈"),
]


def speak_text(text: str) -> str:
    out = text
    for a, b in PRONOUNCE:
        out = out.replace(a, b)
    return out


def token() -> str:
    r = subprocess.run(["az", "account", "get-access-token", "--resource", "https://cognitiveservices.azure.com", "--query", "accessToken", "-o", "tsv"],
                       capture_output=True, text=True, check=True)
    return r.stdout.strip()


def endpoint() -> str:
    cfg = json.loads((ROOT / "config.json").read_text()) if (ROOT / "config.json").exists() else {}
    acc = cfg.get("speech_account") or subprocess.run(["azd", "env", "get-value", "FOUNDRY_ACCOUNT_NAME"], capture_output=True, text=True, cwd=ROOT.parent).stdout.strip()
    return f"https://{acc}.cognitiveservices.azure.com"


def ssml(text: str, rate: str = "+4%", voice: str = VOICE) -> str:
    body = escape(speak_text(text)).replace("\n", " ")
    # 문장 사이 짧은 쉼으로 자연스러운 호흡을 줍니다
    for mark in ("다. ", "요. ", "죠. ", "다.", "요."):
        body = body.replace(mark, mark.rstrip() + '<break time="260ms"/> ')
    return (f'<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="ko-KR"><voice name="{voice}">'
            f'<prosody rate="{rate}">{body}</prosody></voice></speak>')


def synth(text: str, out: pathlib.Path, base: str, tok: str, rate: str = "+4%", voice: str = VOICE) -> None:
    for attempt in range(5):
        r = httpx.post(f"{base}/tts/cognitiveservices/v1", content=ssml(text, rate, voice).encode("utf-8"), timeout=90,
                       headers={"Authorization": f"Bearer {tok}", "Content-Type": "application/ssml+xml", "X-Microsoft-OutputFormat": FORMAT, "User-Agent": "foundry-demo"})
        if r.status_code == 200 and r.content:
            out.write_bytes(r.content)
            return
        if r.status_code in (429, 500, 502, 503):
            time.sleep(2 ** attempt)
            continue
        raise RuntimeError(f"TTS {r.status_code}: {r.text[:300]}")
    raise RuntimeError("TTS 재시도 초과")


def duration(path: pathlib.Path) -> float:
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)], capture_output=True, text=True, check=True)
    return float(r.stdout.strip())


def build(script: dict[str, str], voice: str = VOICE, rate: str = "+4%") -> dict[str, float]:
    AUDIO.mkdir(exist_ok=True)
    base, tok = endpoint(), token()
    manifest_path = AUDIO / "manifest.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    durations: dict[str, float] = {}
    for key, text in script.items():
        mp3 = AUDIO / f"{key}.mp3"
        digest = hashlib.sha256(f"{voice}|{rate}|{text}".encode()).hexdigest()[:16]
        if not (mp3.exists() and manifest.get(key, {}).get("hash") == digest):
            synth(text, mp3, base, tok, rate, voice)
            manifest[key] = {"hash": digest}
            print(f"  ♪ {key} ({len(text)}자)")
        manifest.setdefault(key, {})["duration"] = durations[key] = round(duration(mp3), 3)
        manifest[key]["text"] = text
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=1))
    return durations


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--say")
    ap.add_argument("--out", default="/tmp/say.mp3")
    ap.add_argument("--voice", default=VOICE)
    ap.add_argument("--build", action="store_true")
    args = ap.parse_args()
    if args.list:
        r = httpx.get(f"{endpoint()}/tts/cognitiveservices/voices/list", headers={"Authorization": f"Bearer {token()}"}, timeout=60)
        for v in r.json():
            if v["Locale"] == "ko-KR":
                print(v["ShortName"], v.get("Gender"), v.get("VoiceType"))
    elif args.say:
        out = pathlib.Path(args.out)
        synth(args.say, out, endpoint(), token(), voice=args.voice)
        print(f"{out}  {duration(out):.2f}초")
    elif args.build:
        sys.path.insert(0, str(ROOT))
        from script_ko import SCRIPT  # noqa: E402
        d = build(SCRIPT)
        print(f"총 {len(d)}개, 합계 {sum(d.values()) / 60:.1f}분")


if __name__ == "__main__":
    main()
