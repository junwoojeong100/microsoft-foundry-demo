// 표시 언어(ko | en): 서버(DEMO_LANG)가 /api/session 으로 알려 준다. 실패하면 한국어.
// 최상위 await 이므로 이 모듈을 import 하는 모듈은 LANG 이 정해진 뒤에 실행된다 → 모듈 수준 상수에도 tt() 를 쓸 수 있다.
async function detectLang() {
  try {
    const r = await fetch('/api/session', { credentials: 'same-origin', cache: 'no-store' });
    if (r.ok) return (await r.json()).lang === 'en' ? 'en' : 'ko';
  } catch { /* 네트워크 오류 · JSON 아님 → 한국어 */ }
  return 'ko';
}

export const LANG = await detectLang();
export const tt = (ko, en) => (LANG === 'en' ? en : ko);

if (LANG === 'en') {
  document.documentElement.lang = 'en';
  document.title = 'Contoso AI · Microsoft Foundry demo';
}
