/* 녹화용 오버레이 — 자막 바, 가상 커서·클릭 효과, 빨리감기 배지, 챕터 표시, 강조 상자.
 * Playwright add_init_script 로 모든 페이지에 주입됩니다 (앱 코드에는 영향 없음).
 * 페이지 본문이 자막에 가리지 않도록 body.rec 일 때 #app 높이를 줄입니다(app.css 의 body.rec 규칙).
 */
(() => {
  if (window.__rec) return;
  const CAP_H = typeof window.__REC_CAPH === 'number' ? window.__REC_CAPH : 78;
  const css = `
  #__cap { position: fixed; left: 0; right: 0; bottom: 0; height: ${CAP_H}px; z-index: 2147483000; display: flex; align-items: center; justify-content: center;
    background: linear-gradient(180deg, #0b1020 0%, #0a0f1d 100%); border-top: 1px solid rgba(255,255,255,.08); padding: 0 80px; pointer-events: none; }
  #__cap span { color: #fff; font: 600 23px/1.4 'Pretendard','Apple SD Gothic Neo',sans-serif; letter-spacing: -.01em; text-align: center; max-width: 1280px; text-shadow: 0 1px 2px rgba(0,0,0,.4); }
  #__chap { position: fixed; right: 22px; bottom: ${CAP_H + 14}px; z-index: 2147483000; background: rgba(11,16,32,.88); color: #fff; padding: 7px 15px 7px 11px; border-radius: 999px; display: none; align-items: center; gap: 9px;
    font: 700 15px/1 'Pretendard',sans-serif; box-shadow: 0 6px 20px rgba(0,0,0,.25); pointer-events: none; }
  #__chap b { background: linear-gradient(135deg,#0f6cbd,#6d4ae0); border-radius: 999px; padding: 4px 9px; font-size: 13px; }
  #__ff { position: fixed; right: 20px; top: 14px; z-index: 2147483000; background: rgba(217,122,6,.95); color: #fff; padding: 8px 16px; border-radius: 999px; font: 800 16px/1 'Pretendard',sans-serif; display: none; align-items: center; gap: 8px;
    box-shadow: 0 6px 18px rgba(0,0,0,.25); pointer-events: none; animation: __pulse 1.2s infinite; }
  @keyframes __pulse { 50% { transform: scale(1.04); } }
  #__cur { position: fixed; left: 0; top: 0; width: 28px; height: 28px; z-index: 2147483600; pointer-events: none; transform: translate(-100px,-100px); transition: transform .06s linear; filter: drop-shadow(0 3px 4px rgba(0,0,0,.35)); }
  .__rip { position: fixed; z-index: 2147483500; width: 14px; height: 14px; margin: -7px 0 0 -7px; border-radius: 50%; border: 3px solid #0f6cbd; background: rgba(15,108,189,.25); pointer-events: none; animation: __rip .55s ease-out forwards; }
  @keyframes __rip { to { transform: scale(4.2); opacity: 0; } }
  .__spot { position: fixed; z-index: 2147483400; border: 3px solid #f59e0b; border-radius: 14px; box-shadow: 0 0 0 4px rgba(245,158,11,.25), 0 0 0 9999px rgba(10,15,29,.28); pointer-events: none; animation: __spot 1.4s ease-in-out infinite; }
  @keyframes __spot { 50% { box-shadow: 0 0 0 9px rgba(245,158,11,.18), 0 0 0 9999px rgba(10,15,29,.28); } }
  ${CAP_H > 0 ? `body.rec #app { height: calc(100vh - ${CAP_H}px) !important; }` : ''}
  `;
  const st = document.createElement('style'); st.textContent = css;
  const mount = () => {
    document.documentElement.appendChild(st);
    const cap = Object.assign(document.createElement('div'), { id: '__cap' }); cap.innerHTML = '<span></span>';
    if (CAP_H <= 0) cap.style.display = 'none';
    const chap = Object.assign(document.createElement('div'), { id: '__chap' });
    const ff = Object.assign(document.createElement('div'), { id: '__ff' }); ff.innerHTML = '⏩ <span>빨리 감기</span>';
    const cur = Object.assign(document.createElement('div'), { id: '__cur' });
    cur.innerHTML = '<svg width="28" height="28" viewBox="0 0 24 24"><path d="M5 3l14 7-6 2-2 6z" fill="#fff" stroke="#111" stroke-width="1.5" stroke-linejoin="round"/></svg>';
    document.documentElement.append(cap, chap, ff, cur);
    document.body && CAP_H > 0 && document.body.classList.add('rec');
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', mount); else mount();
  const $ = (id) => document.getElementById(id);
  let mx = -100, my = -100;
  window.addEventListener('mousemove', (e) => { mx = e.clientX; my = e.clientY; const c = $('__cur'); if (c) c.style.transform = `translate(${mx - 5}px,${my - 3}px)`; }, true);
  window.addEventListener('mousedown', (e) => {
    const r = document.createElement('div'); r.className = '__rip'; r.style.left = e.clientX + 'px'; r.style.top = e.clientY + 'px';
    document.documentElement.appendChild(r); setTimeout(() => r.remove(), 600);
  }, true);
  window.__rec = {
    capH: CAP_H,
    caption(text) { const c = $('__cap'); if (!c) return; c.querySelector('span').textContent = text; },
    chapter(n, title) { const c = $('__chap'); if (!c) return; if (!title) { c.style.display = 'none'; return; } c.innerHTML = `<b>${n}</b>${title}`; c.style.display = 'flex'; },
    ff(on, label) { const f = $('__ff'); if (!f) return; f.style.display = on ? 'flex' : 'none'; if (label) f.querySelector('span').textContent = label; },
    spot(selector, pad = 8) {
      this.unspot();
      const el = typeof selector === 'string' ? document.querySelector(selector) : selector; if (!el) return false;
      const r = el.getBoundingClientRect(); const d = document.createElement('div'); d.className = '__spot';
      Object.assign(d.style, { left: r.left - pad + 'px', top: r.top - pad + 'px', width: r.width + 2 * pad + 'px', height: r.height + 2 * pad + 'px' });
      document.documentElement.appendChild(d); return true;
    },
    unspot() { document.querySelectorAll('.__spot').forEach((e) => e.remove()); },
  };
})();
