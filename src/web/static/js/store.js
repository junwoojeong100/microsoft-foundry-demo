// 전역 상태 (아주 작은 스토어) + 대화 컨트롤러(스트리밍 이벤트 → 메시지)
import { useState, useEffect, sse, api, uid } from './lib.js';

const KEY = 'contoso.chats.v1';

function loadChats() {
  try { return JSON.parse(localStorage.getItem(KEY) || '[]'); } catch { return []; }
}

export const S = {
  config: null,
  status: null,
  chats: loadChats(),
  currentId: null,
  route: parseRoute(),
  auth: { required: false, ok: true },
  aborters: {},
};

const subs = new Set();
let raf = 0;
let saveTimer = 0;
export function touch() {
  if (!raf) raf = requestAnimationFrame(() => { raf = 0; subs.forEach((f) => f()); });
  clearTimeout(saveTimer);
  saveTimer = setTimeout(persist, 500);
}
export function useStore() {
  const [, set] = useState(0);
  useEffect(() => { const f = () => set((x) => x + 1); subs.add(f); return () => subs.delete(f); }, []);
  return S;
}
function persist() {
  const slim = () => S.chats.slice(0, 30).map((c) => ({ ...c, messages: c.messages.map((m) => ({ ...m, streaming: false })) }));
  try { localStorage.setItem(KEY, JSON.stringify(slim())); } catch {
    try { localStorage.setItem(KEY, JSON.stringify(slim().slice(0, 5).map((c) => ({ ...c, messages: c.messages.map((m) => ({ ...m, images: undefined })) })))); } catch { /* 용량 초과 — 저장 포기 */ }
  }
}

// ───────────────────────── 라우터
export function parseRoute() {
  const p = (location.hash || '#/chat/knowledge').replace(/^#\/?/, '').split('/');
  if (p[0] === 'chat') return { view: 'chat', agent: p[1] || 'knowledge' };
  return { view: p[0] || 'chat', agent: 'knowledge' };
}
export function go(path) { location.hash = '#/' + path; }
window.addEventListener('hashchange', () => { S.route = parseRoute(); touch(); });

// ───────────────────────── 대화
export const GENERAL = {
  key: 'general', title: '일반 채팅', subtitle: '모델을 골라 대화 · 웹 검색', icon: 'message-square', color: '#475569', capabilities: ['모델 선택', '웹 검색'],
  starters: [
    '로봇청소기 리튬이온 배터리와 관련해, 유럽연합 배터리 규정에서 제조사가 알아야 할 핵심 의무를 세 가지로 요약해줘. (웹 검색)',
    '배터리 불만이 늘어난 로봇청소기 고객에게 보낼 사과 문자를 세 문장으로 써줘.',
    'CFO에게 보낼 3분기 마감 일정 지연 보고 메일 초안을 정중한 톤으로 써줘.',
  ],
  accepts: ['image'],
};
export const agentOf = (key) => (key === 'general' ? GENERAL : S.config?.agents.find((a) => a.key === key) || GENERAL);

export function newChat(agent) {
  const empty = S.chats.find((c) => c.agent === agent && c.messages.length === 0);
  if (empty) { S.currentId = empty.id; touch(); return empty; }
  const chat = { id: uid(), title: '새 채팅', agent, model: S.config?.default_model, conv_id: null, messages: [], ts: Date.now() };
  S.chats.unshift(chat);
  S.currentId = chat.id;
  touch();
  return chat;
}
export function currentChat() {
  const c = S.chats.find((x) => x.id === S.currentId);
  return c;
}
export function deleteChat(id) {
  S.chats = S.chats.filter((c) => c.id !== id);
  if (S.currentId === id) S.currentId = null;
  touch();
}

function applyEvent(chat, bot, user, ev) {
  switch (ev.type) {
    case 'start':
      chat.conv_id = ev.conversation_id;
      break;
    case 'pii':
      bot.pii = { entities: ev.entities, redacted: ev.redacted, ms: ev.ms };
      if (user) {
        // 개인정보는 화면·대화 기록(브라우저 저장소)·제목 어디에도 남기지 않는다
        user.text = ev.redacted; user.display = ev.redacted; user.masked = true;
        if (chat.messages[0] === user) chat.title = ev.redacted.replace(/\s+/g, ' ').slice(0, 28);
      }
      break;
    case 'step': {
      const i = bot.steps.findIndex((s) => s.id === ev.id);
      const step = { id: ev.id, kind: ev.kind, title: ev.title, status: ev.status, detail: ev.detail || {}, ms: ev.ms, t0: i >= 0 ? bot.steps[i].t0 : Date.now() };
      if (i >= 0) bot.steps[i] = step; else bot.steps.push(step);
      break;
    }
    case 'text': bot.text += ev.delta; break;
    case 'final':
      bot.text = ev.text; bot.citations = ev.citations; bot.files = ev.files;
      break;
    case 'approval': bot.approval = { calls: ev.calls, status: 'pending' }; break;
    case 'blocked': bot.blocked = ev; bot.text = ''; break;
    case 'usage': bot.usage = ev; if (ev.model) bot.model = ev.model; break;
    case 'error': bot.error = ev.message; break;
    case 'done': bot.streaming = false; break;
    default: break;
  }
}

async function run(chat, bot, user, path, body) {
  const ctl = new AbortController();
  S.aborters[chat.id] = ctl;
  try {
    for await (const ev of sse(path, body, ctl.signal)) { applyEvent(chat, bot, user, ev); touch(); }
  } catch (e) {
    if (e.name !== 'AbortError') bot.error = e.message;
    else bot.text += '\n\n_(응답을 중단했습니다)_';
  } finally {
    bot.streaming = false;
    delete S.aborters[chat.id];
    touch();
  }
}

export function isBusy(chat) { return !!(chat && S.aborters[chat.id]); }
export function stop(chat) { S.aborters[chat.id]?.abort(); }

export async function send(chat, { text, images = [], files = [], redactPii = false, webSearch = false }) {
  const user = { id: uid(), role: 'user', text, images, files };
  const bot = { id: uid(), role: 'bot', agent: chat.agent, model: chat.agent === 'general' ? chat.model : agentOf(chat.agent).model, text: '', steps: [], citations: [], files: [], streaming: true };
  if (chat.messages.length === 0) chat.title = text.replace(/\s+/g, ' ').slice(0, 28) || '새 채팅';
  chat.messages.push(user, bot);
  chat.ts = Date.now();
  touch();
  await run(chat, bot, user, '/api/chat', {
    agent: chat.agent === 'general' ? 'general' : chat.agent, model: chat.agent === 'general' ? chat.model : undefined,
    text, conversation_id: chat.conv_id, images: images.map((i) => ({ name: i.name, data_url: i.data_url })),
    files: files.map((f) => ({ name: f.name, file_id: f.file_id })), redact_pii: redactPii, web_search: webSearch,
  });
}

export async function decide(chat, botMsg, approve) {
  if (!botMsg.approval || botMsg.approval.status !== 'pending') return;
  botMsg.approval.status = approve ? 'approved' : 'rejected';
  const next = { id: uid(), role: 'bot', agent: chat.agent, model: botMsg.model, text: '', steps: [], citations: [], files: [], streaming: true };
  chat.messages.push(next);
  touch();
  await run(chat, next, null, '/api/chat/approve', {
    conversation_id: chat.conv_id, agent: chat.agent,
    decisions: botMsg.approval.calls.filter((c) => c.needs_approval).map((c) => ({ call_id: c.call_id, approve })),
  });
}

export async function refreshStatus() {
  try { S.status = await api('/api/status'); } catch { /* 로그인 전 */ }
  touch();
}
