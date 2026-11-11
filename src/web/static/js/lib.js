// 공통 모듈: Preact + htm, 아이콘, 마크다운, API/SSE 헬퍼, 작은 유틸리티
import { h, render, Fragment } from 'preact';
import { useState, useEffect, useRef, useMemo, useCallback, useLayoutEffect } from 'preact/hooks';
import htm from '../vendor/htm.mjs';
import { marked } from '../vendor/marked.mjs';
import DOMPurify from '../vendor/purify.mjs';
import hljs from '../vendor/highlight.mjs';
import { ICONS } from '../vendor/icons.js';
import { LANG, tt } from './i18n.js';

export { h, render, Fragment, useState, useEffect, useRef, useMemo, useCallback, useLayoutEffect };
export const html = htm.bind(h);

// ───────────────────────── 아이콘
export function Icon({ name, size = 18, cls = '', stroke = 2, style }) {
  return html`<svg class=${'ic ' + cls} width=${size} height=${size} viewBox="0 0 24 24" fill="none" stroke="currentColor"
    stroke-width=${stroke} stroke-linecap="round" stroke-linejoin="round" style=${style} dangerouslySetInnerHTML=${{ __html: ICONS[name] || '' }}></svg>`;
}

// ───────────────────────── 마크다운
const esc = (s) => s.replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
marked.use({
  gfm: true,
  tokenizer: {
    // 한국어는 '7~10월'처럼 물결표를 범위 표기로 자주 써서, 기본 규칙(물결표 1개도 취소선)이면 문장이 통째로 그어진다. 취소선은 ~~두 개~~ 일 때만 인정한다.
    del(src) {
      const m = /^~~(?=[^\s~])((?:\\.|[^\\])*?(?:\\.|[^\s~\\]))~~(?=[^~]|$)/.exec(src);
      if (m) return { type: 'del', raw: m[0], text: m[1], tokens: this.lexer.inlineTokens(m[1]) };
    },
  },
  renderer: {
    code({ text, lang }) {
      const language = lang && hljs.getLanguage(lang) ? lang : null;
      const body = language ? hljs.highlight(text, { language }).value : esc(text);
      return `<div class="codeblock"><div class="codehead"><span>${esc(lang || 'text')}</span><button class="copybtn" data-copy>${tt('복사', 'Copy')}</button></div><pre><code class="hljs">${body}</code></pre></div>`;
    },
  },
});
DOMPurify.addHook('afterSanitizeAttributes', (node) => {
  if (node.tagName === 'A') { node.setAttribute('target', '_blank'); node.setAttribute('rel', 'noopener noreferrer'); }
});
const mdCache = new Map();
export function md(text) {
  // 모델이 본문에 끼워 넣는 인용 표식(U+E200~U+E201, 스트리밍 중 잘린 꼬리 포함)은 출처 칩으로 대신 보여 주므로 숨긴다.
  text = (text || '').replace(/\uE200[^\uE201]*(\uE201|$)/g, '').replace(/[\uE000-\uF8FF]/g, '');
  // 모델이 자주 쓰는 **‘강조’** 꼴은 CommonMark 가 강조로 보지 않으므로 따옴표 안쪽으로 옮겨 준다
  text = text.replace(/\*\*([‘“'"])([^*\n]+?)([’”'"])\*\*/g, '$1**$2**$3');
  const hit = mdCache.get(text);
  if (hit) return hit;
  const out = DOMPurify.sanitize(marked.parse(text), { ADD_ATTR: ['target', 'data-copy'] });
  if (mdCache.size > 300) mdCache.clear();
  mdCache.set(text, out);
  return out;
}
document.addEventListener('click', (e) => {
  const b = e.target.closest?.('[data-copy]');
  if (!b) return;
  const code = b.closest('.codeblock')?.querySelector('code')?.innerText || '';
  navigator.clipboard?.writeText(code);
  b.textContent = tt('복사됨', 'Copied');
  setTimeout(() => (b.textContent = tt('복사', 'Copy')), 1400);
});

// ───────────────────────── API
export async function api(path, { method = 'GET', body } = {}) {
  const r = await fetch(path, { method, credentials: 'same-origin', headers: body ? { 'content-type': 'application/json' } : undefined, body: body ? JSON.stringify(body) : undefined });
  if (r.status === 401) { window.dispatchEvent(new Event('contoso-unauth')); throw new Error(tt('로그인이 필요합니다', 'Sign-in required')); }
  if (!r.ok) {
    let d = r.statusText;
    try { d = (await r.json()).detail || d; } catch { /* 본문이 JSON 이 아님 */ }
    throw new Error(typeof d === 'string' ? d : JSON.stringify(d));
  }
  return r.json();
}

export async function* sse(path, body, signal) {
  const r = await fetch(path, { method: 'POST', credentials: 'same-origin', headers: { 'content-type': 'application/json' }, body: JSON.stringify(body), signal });
  if (r.status === 401) { window.dispatchEvent(new Event('contoso-unauth')); throw new Error(tt('로그인이 필요합니다', 'Sign-in required')); }
  if (!r.ok) throw new Error(tt(`요청 실패 (${r.status})`, `Request failed (${r.status})`));
  const reader = r.body.getReader();
  const dec = new TextDecoder();
  let buf = '';
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buf += dec.decode(value, { stream: true });
    let i;
    while ((i = buf.indexOf('\n\n')) >= 0) {
      const chunk = buf.slice(0, i);
      buf = buf.slice(i + 2);
      for (const line of chunk.split('\n')) if (line.startsWith('data: ')) yield JSON.parse(line.slice(6));
    }
  }
}

// ───────────────────────── 유틸
const LOCALE = tt('ko-KR', 'en-US');
const REGION_NAMES = { koreacentral: 'Korea Central', koreasouth: 'Korea South', japaneast: 'Japan East', eastus: 'East US', eastus2: 'East US 2', westus3: 'West US 3', swedencentral: 'Sweden Central', westeurope: 'West Europe', northeurope: 'North Europe', southeastasia: 'Southeast Asia' };
export const fmt = {
  n: (v) => (v == null ? '–' : Number(v).toLocaleString(LOCALE)),
  ms: (v) => (v == null ? '–' : v >= 1000 ? (v / 1000).toFixed(1) + tt('초', ' s') : Math.round(v) + 'ms'),
  krw: (v) => tt(Number(v).toLocaleString('ko-KR') + '원', 'KRW ' + Number(v).toLocaleString('en-US')),
  // 한국어 화면은 리전 ID 를 그대로, 영어 화면은 읽기 좋은 이름으로 보여 준다
  region: (r) => (LANG === 'en' ? REGION_NAMES[r] || r : r),
};
export const uid = () => Math.random().toString(36).slice(2, 10);
export function toast(msg) {
  const el = document.createElement('div');
  el.className = 'toast'; el.textContent = msg;
  document.body.appendChild(el);
  setTimeout(() => el.remove(), 2200);
}
export function fileToDataURL(file) {
  return new Promise((res, rej) => { const r = new FileReader(); r.onload = () => res(r.result); r.onerror = rej; r.readAsDataURL(file); });
}
export async function urlToDataURL(url) {
  const blob = await (await fetch(url, { credentials: 'same-origin' })).blob();
  return fileToDataURL(blob);
}
