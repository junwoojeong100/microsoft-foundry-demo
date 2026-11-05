/* 포털 녹화용 개인정보 가리개 — 화면에 보이는 문자열에서 사람·구독·테넌트 식별 정보를 지웁니다.
 * (Foundry 포털은 로그인한 사람의 이름·이메일·구독 이름·GUID 를 곳곳에 표시합니다.)
 * 텍스트 노드와 value/title/aria-label/placeholder 속성을 찾아 바꾸고, DOM 이 바뀔 때마다 다시 적용합니다.
 *
 * 코드 편집기(YAML 보기의 CodeMirror)는 예외입니다. 편집기는 자기 DOM 이 바뀌면 곧바로 되돌리므로
 * 글자를 고치면 서로 되돌리며 무한 반복해 페이지가 멈춥니다. 편집기 안은 글자를 건드리지 않고,
 * GUID·이메일이 있는 자리 위에 회색 가림 막대를 따로 덮습니다.
 */
(() => {
  // 포털 본문(최상위 프레임)에서만 동작한다 — 로그인 창·숨은 인증 iframe 의 값을 바꾸면 로그인이 깨진다.
  if (window.__mask || window.top !== window || !/(^|\.)ai\.azure\.com$/.test(location.hostname)) return;
  const GUID = /[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}/g;
  const MAIL = /[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}/g;
  const RULES = [
    [GUID, '00000000-0000-0000-0000-000000000000'],
    [MAIL, 'admin@contoso.com'],
    [/[A-Za-z0-9-]+\.onmicrosoft\.com/gi, 'contoso.onmicrosoft.com'],
  ];
  // 지금 az login 한 계정의 구독 이름·표시 이름·계정 이름 — recorder.py 가 window.__MASK_TERMS 로 넣어 준다: [[정규식 원문, 바꿀 값], …]
  for (const [src, to] of window.__MASK_TERMS || []) RULES.push([new RegExp(src, 'gi'), to]);
  const fix = (s) => {
    if (!s || s.length < 3) return s;
    let out = s;
    for (const [re, to] of RULES) out = out.replace(re, to);
    return out;
  };
  // 프로젝트 '사용자' 표 같은 곳에는 테넌트의 실제 주체(서비스 주체·관리 계정) 이름이 그대로 나옵니다. 표시 이름을 중립적인 이름으로 바꿉니다.
  const PERSONAS = ['Contoso Admin', 'Platform Automation', 'Cloud Operator', 'Security Service', 'Identity Service', 'Backup Service', 'Monitoring Service', 'Support Engineer', 'Policy Service', 'Billing Admin'];
  const PERSONA_DONE = new RegExp('^(' + PERSONAS.concat(['Directory object']).join('|') + ')( \\d+)?$');
  const PERSONA_KEEP = /^(id-web-|ai-|contoso|Contoso)/; // 이 데모의 리소스(앱 관리 ID 등)는 그대로 보여 준다
  const PERSONA_LOADING = /^(ServicePrincipal|User|Group) [0-9a-f]{8}$/i; // 이름을 불러오기 전 잠깐 보이는 객체 ID 조각
  const personaMap = new Map();
  const persona = (name) => {
    const t = name.trim();
    if (!t || PERSONA_DONE.test(t) || PERSONA_KEEP.test(t)) return name;
    if (PERSONA_LOADING.test(t)) return 'Directory object';
    if (!personaMap.has(t)) {
      const i = personaMap.size;
      personaMap.set(t, PERSONAS[i % PERSONAS.length] + (i >= PERSONAS.length ? ' ' + (Math.floor(i / PERSONAS.length) + 1) : ''));
    }
    return personaMap.get(t);
  };
  const ATTRS = ['title', 'aria-label', 'placeholder', 'alt'];
  const SKIP = new Set(['SCRIPT', 'STYLE', 'NOSCRIPT']);
  const EDITOR = '.cm-editor, .monaco-editor';
  const inEditor = (n) => { const e = n.nodeType === 1 ? n : n.parentElement; return !!(e && e.closest && e.closest(EDITOR)); };
  const fixNode = (n) => {
    if (n.nodeType === 3) {
      if (n.parentNode && SKIP.has(n.parentNode.nodeName)) return;
      const par = n.parentElement;
      const isPersona = par && par.classList && par.classList.contains('fui-Persona__primaryText');
      const v = isPersona ? persona(fix(n.nodeValue)) : fix(n.nodeValue);
      if (v !== n.nodeValue) n.nodeValue = v; return;
    }
    if (n.nodeType !== 1 || SKIP.has(n.tagName)) return;
    const avatar = n.classList && n.classList.contains('fui-Avatar');
    for (const a of ATTRS) { const v = n.getAttribute(a); if (v) { const f = avatar && a === 'aria-label' ? persona(fix(v)) : fix(v); if (f !== v) n.setAttribute(a, f); } }
    // 입력창 값은 화면 표시용(읽기 전용)인 것만 바꾼다 — 사용자가 편집하는 값·숨은 필드는 건드리지 않는다.
    if ((n.tagName === 'INPUT' || n.tagName === 'TEXTAREA') && n.readOnly && n.type !== 'hidden' && n.type !== 'password' && typeof n.value === 'string') {
      const f = fix(n.value); if (f !== n.value) { try { n.value = f; } catch { /* 읽기 전용 */ } }
    }
  };
  const walk = (root) => {
    if (!root || (root.nodeType === 1 && root.matches && root.matches(EDITOR)) || inEditor(root)) return;
    fixNode(root);
    const w = document.createTreeWalker(root, NodeFilter.SHOW_ELEMENT | NodeFilter.SHOW_TEXT, {
      acceptNode: (n) => (n.nodeType === 1 && n.matches && n.matches(EDITOR) ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_ACCEPT),
    });
    let n; while ((n = w.nextNode())) fixNode(n);
  };

  // ── 코드 편집기 위 가림 막대
  let layer = null;
  const redact = () => {
    const ed = document.querySelector('.cm-content');
    if (!ed && !layer) return;
    if (!layer) {
      layer = document.createElement('div');
      layer.id = '__redact';
      layer.style.cssText = 'position:fixed;left:0;top:0;width:0;height:0;z-index:2147483200;pointer-events:none';
      document.documentElement.appendChild(layer);
    }
    const rects = [];
    if (ed) {
      const w = document.createTreeWalker(ed, NodeFilter.SHOW_TEXT);
      let n;
      while ((n = w.nextNode())) {
        for (const re of [GUID, MAIL]) {
          re.lastIndex = 0;
          let m;
          while ((m = re.exec(n.data))) {
            if (/^[0-]+$/.test(m[0])) continue;
            const r = document.createRange(); r.setStart(n, m.index); r.setEnd(n, m.index + m[0].length);
            const b = r.getBoundingClientRect();
            if (b.width > 1) rects.push(b);
          }
        }
      }
    }
    while (layer.children.length > rects.length) layer.lastChild.remove();
    while (layer.children.length < rects.length) {
      const d = document.createElement('div');
      d.style.cssText = 'position:fixed;background:#cfd6e4;border-radius:4px';
      layer.appendChild(d);
    }
    rects.forEach((b, i) => {
      const s = layer.children[i].style;
      s.left = b.left - 2 + 'px'; s.top = b.top - 1 + 'px'; s.width = b.width + 4 + 'px'; s.height = b.height + 2 + 'px';
    });
  };

  const start = () => {
    walk(document.documentElement);
    new MutationObserver((muts) => {
      if (layer && muts.every((m) => layer.contains(m.target))) return; // 가림 막대 자신의 변화는 무시
      for (const m of muts) {
        if (m.type === 'characterData' || m.type === 'attributes') { if (!inEditor(m.target)) fixNode(m.target); }
        else m.addedNodes.forEach((n) => walk(n));
      }
      redact();
    }).observe(document.documentElement, { subtree: true, childList: true, characterData: true, attributes: true, attributeFilter: ATTRS.concat(['value']) });
    window.addEventListener('scroll', redact, true);
    setInterval(() => { walk(document.documentElement); document.title = fix(document.title); redact(); }, 700); // 입력창 값 등 이벤트 없이 바뀌는 곳 보강
  };
  window.__mask = { fix, personaMap };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start); else start();
})();
