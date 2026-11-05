# 오픈소스 고지 (Third-Party Notices)

이 저장소는 아래 오픈소스를 **그대로 포함**(vendoring)하고 있습니다. 각 파일은 원 저작권 고지와 라이선스를 유지하며, 라이선스 전문은 각 프로젝트 저장소에서 볼 수 있습니다.
Python 패키지(FastAPI, azure-ai-projects 등)는 포함하지 않고 `requirements.txt` 로 설치합니다.

## 웹 앱 프런트엔드 — `src/web/static/`

| 구성 요소 | 버전 | 라이선스 | 저작권 | 위치 |
|---|---|---|---|---|
| [Preact](https://github.com/preactjs/preact) | 10.24.3 | MIT | Copyright (c) 2015-present Jason Miller | `vendor/preact.mjs`, `vendor/preact-hooks.mjs` |
| [htm](https://github.com/developit/htm) | 3.1.1 | Apache-2.0 | Copyright 2018 Google Inc. | `vendor/htm.mjs` |
| [marked](https://github.com/markedjs/marked) | 15.0.0 | MIT | Copyright (c) 2011-2024, Christopher Jeffrey | `vendor/marked.mjs` |
| [DOMPurify](https://github.com/cure53/DOMPurify) | 3.2.3 | Apache-2.0 또는 MPL-2.0 (이중 라이선스) | (c) Cure53 and other contributors | `vendor/purify.mjs` |
| [highlight.js](https://github.com/highlightjs/highlight.js) | 11.10.0 | BSD-3-Clause | (c) 2006-2024 Josh Goebel and other contributors | `vendor/highlight.mjs`, `vendor/hljs-github.css` |
| [Lucide](https://lucide.dev) 아이콘 (lucide-static) | 1.68.0 | ISC | Copyright (c) 2026 Lucide Icons and Contributors | `vendor/icons.js` (필요한 아이콘만 추려 담음) |
| [Pretendard](https://github.com/orioncactus/pretendard) 글꼴 | 1.3.9 | SIL Open Font License 1.1 | Kil Hyung-jin 외 | `fonts/PretendardVariable.woff2` |

## 데모 영상 제작 — `recording/`

| 구성 요소 | 라이선스 | 저작권 | 위치 |
|---|---|---|---|
| [xterm.js](https://github.com/xtermjs/xterm.js) | MIT | Copyright (c) 2014 The xterm.js authors. / Copyright (c) 2012-2013, Christopher Jeffrey | `pages/vendor/xterm.js`, `pages/vendor/xterm.css` |
| Pretendard 글꼴 | SIL Open Font License 1.1 | 위와 같음 | `pages/vendor/PretendardVariable.woff2` |
| [나눔고딕코딩](https://github.com/fontsource/font-files/tree/main/fonts/google/nanum-gothic-coding) 글꼴 | SIL Open Font License 1.1 | Copyright (c) 2009 NHN Corporation. Font designed by Sandoll Communications Inc. | `pages/vendor/nanum-gothic-coding-*.woff2` |

## GitHub Pages 사이트 — `site/`

- 사이트의 GitHub 로고는 [Octicons](https://github.com/primer/octicons)의 `mark-github` 아이콘(MIT, Copyright (c) GitHub Inc.)입니다. GitHub 로고는 GitHub, Inc. 의 상표입니다.
- 사이트 빌드 시 위의 `marked`, `DOMPurify`, Pretendard 파일과 Lucide 아이콘이 함께 배포됩니다.

## 데모 영상의 소리·화면

- 내레이션은 Azure AI Speech(`ko-KR-SunHiNeural`)로 합성했습니다.
- 화면에 나오는 Microsoft Foundry 포털·Azure 서비스의 이름과 로고는 Microsoft 의 상표입니다. 영상에 나오는 회사 ‘Contoso’와 샘플 문서·영수증·수치는 모두 가상입니다.
