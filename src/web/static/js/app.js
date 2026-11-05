// 앱 셸: 로그인, 사이드바, 라우팅
import { html, render, Icon, useState, useEffect, api } from './lib.js';
import { S, useStore, touch, go, newChat, deleteChat, agentOf, GENERAL, refreshStatus } from './store.js';
import { ChatView } from './chat.js';

function Login({ onOk }) {
  const [code, setCode] = useState('');
  const [err, setErr] = useState('');
  const submit = async (e) => {
    e.preventDefault();
    try { await api('/api/login', { method: 'POST', body: { code } }); onOk(); } catch (ex) { setErr(ex.message); }
  };
  return html`<div class="login"><form class="card" onSubmit=${submit}>
    <div class="logo"><${Icon} name="sparkles" size=28 /></div>
    <h1>Contoso AI</h1><p>Microsoft Foundry 데모 · 접속 코드를 입력하세요</p>
    <input type="password" autofocus placeholder="••••••" value=${code} onInput=${(e) => { setCode(e.target.value); setErr(''); }} />
    ${err ? html`<div class="err">${err}</div>` : null}
    <button class="btn primary" type="submit"><${Icon} name="key-round" size=16 />입장</button>
    <div class="foot-note" style="margin-top:16px">운영 환경에서는 Microsoft Entra ID 로그인(SSO·MFA)으로 바꿉니다</div></form></div>`;
}

// 채팅 기록을 오늘 / 어제 / 이전으로 묶는다 (ChatGPT 와 같은 방식)
function groupChats(chats) {
  const day0 = (d) => new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
  const today = day0(new Date());
  const groups = [['오늘', []], ['어제', []], ['이전', []]];
  for (const c of chats.filter((x) => x.messages.length)) {
    const t = day0(new Date(c.ts || 0));
    groups[t >= today ? 0 : t >= today - 86400000 ? 1 : 2][1].push(c);
  }
  return groups.filter(([, list]) => list.length);
}

function Sidebar() {
  useStore();
  const r = S.route;
  const user = S.config?.user || {};
  const agents = S.config?.agents || [];
  return html`<aside class="side">
    <div class="brand"><div class="logo"><${Icon} name="sparkles" size=20 /></div><div><b>Contoso AI</b><small>Powered by Microsoft Foundry</small></div></div>
    <button class="newchat" onClick=${() => { const a = r.view === 'chat' ? r.agent : 'knowledge'; newChat(a); go('chat/' + a); }}><${Icon} name="plus" size=18 />새 채팅</button>
    <div class="side-scroll">
      <div class="side-title">에이전트</div>
      ${agents.map((a) => html`<button class=${'nav ' + (r.view === 'chat' && r.agent === a.key ? 'on' : '')} onClick=${() => { newChat(a.key); go('chat/' + a.key); }}>
        <span class="dot" style=${'background:' + a.color}><${Icon} name=${a.icon} size=16 /></span><span class="t"><span>${a.title}</span><small>${a.subtitle}</small></span></button>`)}
      <button class=${'nav ' + (r.view === 'chat' && r.agent === 'general' ? 'on' : '')} onClick=${() => { newChat('general'); go('chat/general'); }}>
        <span class="dot" style=${'background:' + GENERAL.color}><${Icon} name=${GENERAL.icon} size=16 /></span><span class="t"><span>${GENERAL.title}</span><small>${GENERAL.subtitle}</small></span></button>
      ${groupChats(S.chats).map(([title, list]) => html`<div class="side-title">${title}</div>
        ${list.slice(0, 10).map((c) => html`<button class=${'hist ' + (S.currentId === c.id && r.view === 'chat' ? 'on' : '')} onClick=${() => { S.currentId = c.id; go('chat/' + c.agent); touch(); }}>
          <i style=${'background:' + agentOf(c.agent).color}></i><span>${c.title}</span><button class="x" onClick=${(e) => { e.stopPropagation(); deleteChat(c.id); }}><${Icon} name="x" size=14 /></button></button>`)}`)}
    </div>
    <div class="side-foot">
      <div class="user"><div class="avatar">${(user.name || '김')[0]}</div><div style="flex:1"><b>${user.name}</b><small>${user.team}</small></div>
        ${S.auth.required ? html`<button class="icobtn" title="로그아웃" onClick=${async () => { await api('/api/logout', { method: 'POST' }); location.reload(); }}><${Icon} name="log-out" size=17 /></button>` : null}</div>
      ${S.config?.links?.agents ? html`<a class="adminlink" href=${S.config.links.agents} target="_blank" rel="noopener"><${Icon} name="sliders-horizontal" size=15 />관리자 콘솔 · Foundry 포털<${Icon} name="arrow-up-right" size=14 /></a>` : null}
      <div class="chips"><span class="chip brand"><${Icon} name="map-pin" size=12 />${S.config?.region}</span><span class="chip ok"><${Icon} name="key-round" size=12 />키 없음 · Entra ID</span></div>
    </div></aside>`;
}

function App() {
  useStore();
  const [authed, setAuthed] = useState(null);
  const [ready, setReady] = useState(false);

  const boot = async () => {
    try {
      S.config = await api('/api/config');
      setAuthed(true); setReady(true); touch();
    } catch { /* contoso-unauth 이벤트가 처리 */ }
  };
  useEffect(() => {
    api('/api/session').then((s) => { S.auth.required = s.auth_mode === 'code'; if (s.authenticated) boot(); else setAuthed(false); });
    const un = () => setAuthed(false);
    window.addEventListener('contoso-unauth', un);
    return () => window.removeEventListener('contoso-unauth', un);
  }, []);
  useEffect(() => {
    if (!ready) return undefined;
    refreshStatus();
    const t = setInterval(() => { if (!S.status || !['ready', 'idle'].includes(S.status.state)) refreshStatus(); }, 2500);
    return () => clearInterval(t);
  }, [ready]);

  if (authed === null) return html`<div class="login"></div>`;
  if (authed === false) return html`<${Login} onOk=${() => { setAuthed(true); boot(); }} />`;
  if (!S.config) return html`<div class="login"><${Icon} name="loader" size=28 cls="spin" /></div>`;
  const r = S.route;
  return html`<div class="app"><${Sidebar} /><main class="main"><${ChatView} agentKey=${r.view === 'chat' ? r.agent : 'knowledge'} key=${r.view === 'chat' ? r.agent : 'knowledge'} /></main></div>`;
}

render(html`<${App} />`, document.getElementById('app'));
