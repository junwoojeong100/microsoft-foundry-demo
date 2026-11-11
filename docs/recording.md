# 데모 영상 다시 만들기
<!-- summary: 대본·음성·녹화·조립까지, 이 데모 영상을 직접 다시 만드는 방법. -->

`video/microsoft-foundry-demo-ko.mp4` 는 이 저장소의 코드로 **실제 Azure 에 배포한 환경**을 녹화해 만들었습니다.
화면 연출(커서·자막·강조 상자)과 내레이션 합성, 장면 조립까지 모두 `recording/` 의 스크립트이므로 대본이나 장면을 고쳐 다시 만들 수 있습니다.

```
대본(script_ko.py) ─▶ tts.py ─▶ audio/*.mp3 ─┐
장면(scenes.py)   ─▶ record.py ─▶ raw/<장면>/scene.mp4 ─┴▶ compose.py ─▶ video/microsoft-foundry-demo-ko.mp4
```

## 영문판 (`REC_LANG=en`)

같은 파이프라인으로 영문판(영어 화면·내레이션·자막)을 만들 수 있습니다. 한국어판 결과물과 섞이지 않도록 산출물 폴더가 따로 나뉩니다.

| | 한국어(기본) | 영어(`REC_LANG=en`) |
|---|---|---|
| 대본 | `script_ko.py` | `script_en.py` |
| 내레이션 | `audio/` · `ko-KR-SunHiNeural` | `audio_en/` · `en-US-Andrew:DragonHDLatestNeural` (`tts.py --lang en`) |
| 슬라이드·터미널 화면 | `pages/slides.html` · `terminal.html` | `pages/slides_en.html` · `terminal_en.html` |
| 녹화 중간 산출물 | `raw/` | `raw_en/` |
| 앱 | `DEMO_LANG` 미설정(한국어 앱) | **`DEMO_LANG=en` 으로 따로 배포한 앱**(영문 UI·사규 PDF·평가 질문) |
| 포털 | 한국어 UI | 영어 UI (`save_portal_state.py --lang en` 으로 세션 저장) |
| 결과 | `video/microsoft-foundry-demo-ko.*` | `video/microsoft-foundry-demo-en.*` |

```bash
export REC_LANG=en AZURE_ENV_NAME=contoso-demo-en     # 영문판 azd 환경(DEMO_LANG=en)
python recording/tts.py --lang en --build --verify     # --verify: 합성한 음성을 다시 받아 적어 대본과 비교
python recording/record.py all-slides S03_deploy all-app all-portal
python recording/compose.py
```

영문판 `azd up` 기록은 `recording/assets/azd_up_en.cast` 입니다. 화면의 모든 글자가 영어여야 하므로 앱·포털 장면 모두 영어 UI 로 녹화합니다(포털은 번역하지 않고 실제 영어 화면을 씁니다).

## 준비물

| 항목 | 용도 |
|---|---|
| `azd up` 으로 배포된 환경 | 앱 장면(S05~S10)은 배포된 앱의 공개 주소와 접속 코드를 `azd env` 에서 읽어 씁니다 |
| Python 3.12 + `pip install -r requirements-dev.txt` · `playwright install chromium` | 화면 녹화(헤드리스 Chromium) |
| `ffmpeg` · `ffprobe` | 장면 인코딩·조립 |
| `az login` | 내레이션 합성(Foundry 리소스의 Speech 엔드포인트를 Entra ID 로 호출 — 키 불필요) |
| Foundry 포털 로그인 세션 | 포털 장면(P01~P06). `python recording/save_portal_state.py` 로 한 번 저장 |

## 순서

```bash
# 1) 내레이션 합성 — 문장이 바뀐 것만 다시 만듭니다(해시 비교)
python recording/tts.py --build

# 2) 장면 녹화 — 장면마다 recording/raw/<장면>/scene.mp4 와 scene.json 이 만들어집니다
python recording/record.py all-slides S03_deploy      # 슬라이드·장 구분 카드 + azd up 재생
python recording/record.py all-app                    # 직원 앱 장면 (배포된 앱 사용)
python recording/record.py all-portal                 # Foundry 포털 장면 (로그인 세션 필요)
python recording/record.py S07_analyst                # 장면 하나만 다시 녹화

# 3) 조립 — 먼저 점검만 해 볼 수 있습니다
python recording/compose.py --check
python recording/compose.py                           # video/ 에 mp4 · 챕터 · 자막(SRT) · 썸네일
```

## 파일 안내

| 파일 | 설명 |
|---|---|
| `script_ko.py` | 한국어 내레이션 대본(키 → 문장)과 장 구분 카드. 자막은 이 원문을 그대로 씁니다 |
| `tts.py` | Azure AI Speech(`ko-KR-SunHiNeural`)로 대본을 mp3 로 합성. 영어 제품명은 `PRONOUNCE` 표로 한글 발음으로 바꿔 읽힙니다 |
| `scenes.py` | 장면 정의. 각 함수가 실제 화면을 조작하며 녹화합니다(클릭·타이핑·스크롤·강조) |
| `recorder.py` | 녹화 엔진. CDP 스크린캐스트로 프레임을 저장하고, 모델 응답처럼 기다리는 구간은 영상에서 **빨리 감기 배지**와 함께 압축합니다 |
| `overlay.js` | 자막 바·가상 커서·클릭 효과·챕터 표시·강조 상자(페이지에 주입, 앱 코드에는 영향 없음) |
| `portal.py` · `portal_mask.js` · `masking.py` | 포털 장면 도우미. 포털에 표시되는 이름·이메일·구독/테넌트 ID·권한 주체 이름을 화면에서 가립니다. 가릴 구독 이름·계정 이름은 지금 `az login` 한 계정에서 실행할 때 읽어 오고(저장소에는 개인 값이 없습니다), `MASK_TERMS="실제값=바꿀값,…"` 로 더할 수 있습니다 |
| `pty_capture.py` · `mask_cast.py` · `terminal_cfg.py` · `pages/terminal.html` | `azd up` 실제 출력 기록(asciinema 형식) → 개인 식별 값 가리기 → 터미널 재생 화면 |
| `assets/azd_up.cast` | 위 과정으로 만든 `azd up` 기록(값이 가려져 있어 저장소에 포함) |
| `compose.py` | 장면 영상 + 내레이션 조립. 음량 평탄화(-16 LUFS), 챕터, SRT, 썸네일 생성 |
| `raw/` | 녹화 중간 산출물(용량이 커서 `.gitignore` 로 제외) |

## 새로 `azd up` 을 기록하고 싶다면

```bash
python recording/pty_capture.py recording/raw/azd_up.cast --cwd . --cols 118 --rows 30 -- azd up --no-prompt
python recording/mask_cast.py recording/raw/azd_up.cast recording/assets/azd_up.cast
```

`pty_capture.py` 는 가짜 영상이 아니라 실제 명령의 출력과 소요 시간을 그대로 기록합니다. 장면 코드(`S03_deploy`)의 `markers` 와 `seconds` 로
단계 표식과 단계별 재생 시간(압축 비율)을 정합니다.

## 알아 둘 점

- **한 번에 한 가지 일만 시키세요.** 헤드리스 브라우저를 여러 개 동시에 돌리면 CPU 가 포화돼 타이핑·화면 전환이 느려지고 영상 타이밍이 어긋납니다. 장면은 하나씩(`--parallel 1`, 기본값) 또는 슬라이드처럼 가벼운 것만 2개까지 동시에 녹화하세요.
- **모델 응답은 실행마다 다릅니다.** 내레이션은 수치를 단정하지 않도록 썼습니다. 화면 값이 중요한 곳(예: 평가 점수)은 장면 코드가 화면과 대본을 비교해 경고를 냅니다.
- **포털 화면은 바뀔 수 있습니다.** 포털 장면은 화면의 글자(한국어 UI)와 요소 역할로 찾습니다. 포털이 개편되면 `scenes.py` 의 선택자를 고쳐야 할 수 있습니다.
- **포털 세션 파일에는 인증 쿠키가 들어 있습니다.** 기본 위치는 `/tmp/foundry_portal_state.json`(환경 변수 `PORTAL_STATE` 로 변경)이며 저장소에 올리지 마세요.
- **영상 용량.** GitHub 는 파일당 100MB 를 넘길 수 없습니다. `compose.py --crf 27` 처럼 CRF 값을 올리면 용량이 줄어듭니다(숫자가 클수록 작고 거칩니다).
- **웹사이트는 자동으로 갱신됩니다.** 영상을 다시 만든 뒤 `video/` 의 파일(mp4·srt·chapters.txt·thumbnail·poster)을 커밋해 push 하면 GitHub Actions 가 사이트의 챕터·길이·대본을 새 영상 기준으로 다시 만듭니다. 미리 보려면 `python scripts/build_site.py` 를 실행하세요.
