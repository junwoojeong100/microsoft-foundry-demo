"""Azure AI Speech 로 한국어 내레이션을 만듭니다 — Foundry 리소스의 Speech 엔드포인트를 Entra ID(az login)로 호출하므로 키가 필요 없습니다.

    python recording/tts.py --list                         # 사용 가능한 한국어 음성
    python recording/tts.py --say "안녕하세요" --out /tmp/a.mp3
    python recording/tts.py --build                        # script_ko.py 의 모든 내레이션 합성 (캐시됨)
    python recording/tts.py --lang en --build              # 영어판: script_en.py → audio_en/ (Andrew HD 음성)
    python recording/tts.py --lang en --build --verify     # 합성한 음성을 음성 인식(STT)으로 다시 들어 대본과 다른 곳을 찾습니다

음성은 recording/audio/<키>.mp3 (영어판은 audio_en/) 로 캐시되고, 문장이 바뀐 경우에만 다시 합성합니다(해시 비교).

영어판 환경 변수(모두 선택)
  SPEECH_ENDPOINT      Speech 엔드포인트. 없으면 azd 환경의 Foundry 리소스(…cognitiveservices.azure.com)를 씁니다
  SPEECH_SUBSCRIPTION  Speech 리소스가 있는 구독(토큰을 받을 테넌트). 전역 az 로그인은 바꾸지 않습니다
  VOICE                영어 음성 이름(기본 en-US-Andrew:DragonHDLatestNeural)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import re
import subprocess
import sys
import tempfile
import time
from xml.sax.saxutils import escape

import httpx

ROOT = pathlib.Path(__file__).resolve().parent
AUDIO = ROOT / "audio"
VOICE = "ko-KR-SunHiNeural"
FORMAT = "audio-24khz-96kbitrate-mono-mp3"

# 영어판: Azure AI Speech HD 음성. 파라미터는 말투의 변화폭(temperature)과 발음 보정입니다.
EN_VOICE = os.environ.get("VOICE", "en-US-Andrew:DragonHDLatestNeural")
EN_PARAMS = "temperature=0.4;enhancePronunciation=true"

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


# 영어판: 약어·제품명을 음성이 정확히 읽도록 '읽는 문장'에서만 풀어 씁니다(자막은 원문 그대로).
PRONOUNCE_EN = [
    ("azd up", "A Z D up"), ("GPT-6.1", "G P T six point one"), ("ChatGPT", "Chat G P T"), ("OpenAI", "Open A I"), ("DeepSeek", "Deep Seek"),
    ("Entra ID", "Entra I D"), ("HR-001", "H R zero zero one"), ("PDFs", "P D Fs"), ("PDF", "P D F"), ("MCP", "M C P"), ("API", "A P I"),
    ("Kimi", "Kee-mee"), ("GPT", "G P T"), ("YAML", "yammel"), ("Bicep", "Bye-sep"),
]


def speak_text_en(text: str) -> str:
    out = text
    for a, b in PRONOUNCE_EN:
        out = out.replace(a, b)
    out = re.sub(r"\bID\b", "I D", out)
    return re.sub(r"\bAI\b", "A I", out)


def token() -> str:
    cmd = ["az", "account", "get-access-token", "--resource", "https://cognitiveservices.azure.com"]
    if os.environ.get("SPEECH_SUBSCRIPTION"):  # Speech 리소스가 다른 구독·테넌트에 있을 때 — 전역 로그인은 바꾸지 않는다
        cmd += ["--subscription", os.environ["SPEECH_SUBSCRIPTION"]]
    r = subprocess.run(cmd + ["--query", "accessToken", "-o", "tsv"], capture_output=True, text=True, check=True)
    return r.stdout.strip()


def endpoint() -> str:
    if os.environ.get("SPEECH_ENDPOINT"):
        return os.environ["SPEECH_ENDPOINT"].rstrip("/")
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


def ssml_en(text: str, voice: str = EN_VOICE, params: str = EN_PARAMS) -> str:
    body = escape(speak_text_en(text)).replace("\n", " ")
    return (f"<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xmlns:mstts='https://www.w3.org/2001/mstts' xml:lang='en-US'>"
            f"<voice name='{voice}' parameters='{params}'>{body}</voice></speak>")


def synth(text: str, out: pathlib.Path, base: str, tok: str, rate: str = "+4%", voice: str = VOICE) -> None:
    english = voice.startswith("en-")
    for attempt in range(5):
        body = ssml_en(text, voice) if english else ssml(text, rate, voice)
        r = httpx.post(f"{base}/tts/cognitiveservices/v1", content=body.encode("utf-8"), timeout=180,
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


def build(script: dict[str, str], voice: str = VOICE, rate: str = "+4%", audio: pathlib.Path | None = None) -> dict[str, float]:
    global AUDIO
    AUDIO = audio or AUDIO
    AUDIO.mkdir(exist_ok=True)
    base, tok = endpoint(), token()
    manifest_path = AUDIO / "manifest.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    durations: dict[str, float] = {}
    for key, text in script.items():
        mp3 = AUDIO / f"{key}.mp3"
        payload = f"{voice}|{EN_PARAMS}|{text}" if voice.startswith("en-") else f"{voice}|{rate}|{text}"
        digest = hashlib.sha256(payload.encode()).hexdigest()[:16]
        if not (mp3.exists() and manifest.get(key, {}).get("hash") == digest):
            synth(text, mp3, base, tok, rate, voice)
            manifest[key] = {"hash": digest}
            print(f"  ♪ {key} ({len(text)} chars)")
        manifest.setdefault(key, {})["duration"] = durations[key] = round(duration(mp3), 3)
        manifest[key]["text"] = text
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=1))
    return durations


def canonical(text: str) -> list[str]:
    """비교용 낱말 목록 — 소문자, 문장부호 제거, 'g p t' 처럼 한 글자씩 읽힌 약어는 붙여서 비교."""
    words = re.sub(r"[^a-z0-9' ]+", " ", text.lower().replace("-", " ")).split()
    merged = re.sub(r"\b(?:[a-z0-9] ){1,}[a-z0-9]\b", lambda m: m[0].replace(" ", ""), " ".join(words))
    return merged.split()


def wer(ref: list[str], hyp: list[str]) -> float:
    d = list(range(len(hyp) + 1))
    for i, r in enumerate(ref, 1):
        prev, d[0] = d[0], i
        for j, h in enumerate(hyp, 1):
            prev, d[j] = d[j], min(d[j] + 1, d[j - 1] + 1, prev + (r != h))
    return d[-1] / max(1, len(ref))


def transcribe(mp3: pathlib.Path, base: str, tok: str, seg: int = 45) -> str:
    """mp3 → 16kHz wav 를 seg 초 조각으로 나눠 영어 음성 인식(STT) 결과를 이어 붙입니다(REST 는 조각당 60초 제한)."""
    texts: list[str] = []
    with tempfile.TemporaryDirectory(prefix="stt_") as tmp:
        subprocess.run(["ffmpeg", "-nostdin", "-y", "-loglevel", "error", "-i", str(mp3), "-ar", "16000", "-ac", "1", "-f", "segment", "-segment_time", str(seg),
                        "-c:a", "pcm_s16le", f"{tmp}/s_%03d.wav"], check=True)
        for part in sorted(pathlib.Path(tmp).glob("s_*.wav")):
            for attempt in range(3):
                r = httpx.post(f"{base}/stt/speech/recognition/conversation/cognitiveservices/v1?language=en-US&format=detailed", content=part.read_bytes(), timeout=120,
                               headers={"Authorization": f"Bearer {tok}", "Content-Type": "audio/wav; codecs=audio/pcm; samplerate=16000", "Accept": "application/json"})
                if r.status_code == 200:
                    j = r.json()
                    if j.get("RecognitionStatus") == "Success" and j.get("NBest"):
                        texts.append(j["NBest"][0].get("Lexical") or j["NBest"][0].get("Display", ""))
                    break
                time.sleep(2 ** attempt)
    return " ".join(texts)


def verify(script: dict[str, str], audio: pathlib.Path, limit: float = 0.10) -> list[str]:
    """합성한 영어 음성을 STT 로 다시 들어 대본(읽는 문장)과 비교 — 낱말 오류율이 limit 를 넘는 키를 돌려줍니다."""
    base, tok = endpoint(), token()
    bad: list[str] = []
    for key, text in script.items():
        hyp = canonical(transcribe(audio / f"{key}.mp3", base, tok))
        ref = canonical(speak_text_en(text))
        err = wer(ref, hyp)
        flag = "  ⚠" if err > limit else ""
        print(f"  {key:12} WER {err:5.1%}{flag}")
        if err > limit:
            bad.append(key)
    return bad


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lang", choices=["ko", "en"], default="ko")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--say")
    ap.add_argument("--out", default="/tmp/say.mp3")
    ap.add_argument("--voice")
    ap.add_argument("--build", action="store_true")
    ap.add_argument("--verify", action="store_true", help="(영어판) 합성한 음성을 STT 로 다시 들어 대본과 비교")
    args = ap.parse_args()
    english = args.lang == "en"
    voice = args.voice or (EN_VOICE if english else VOICE)
    locale = "en-US" if english else "ko-KR"
    if args.list:
        r = httpx.get(f"{endpoint()}/tts/cognitiveservices/voices/list", headers={"Authorization": f"Bearer {token()}"}, timeout=60)
        for v in r.json():
            if v["Locale"] == locale:
                print(v["ShortName"], v.get("Gender"), v.get("VoiceType"))
    elif args.say:
        out = pathlib.Path(args.out)
        synth(args.say, out, endpoint(), token(), voice=voice)
        print(f"{out}  {duration(out):.2f}s")
    elif args.build or args.verify:
        sys.path.insert(0, str(ROOT))
        if english:
            from script_en import SCRIPT  # noqa: E402
            audio = ROOT / "audio_en"
        else:
            from script_ko import SCRIPT  # noqa: E402
            audio = ROOT / "audio"
        if args.build:
            d = build(SCRIPT, voice=voice, audio=audio)
            print(f"{len(d)} clips, {sum(d.values()) / 60:.1f} min in total")
        if args.verify:
            bad = verify(SCRIPT, audio)
            print(f"verify: {len(bad)} clip(s) above the limit {bad}" if bad else "verify: all clips match the script")


if __name__ == "__main__":
    main()
