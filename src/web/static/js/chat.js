// 채팅 화면: 환영 화면, 메시지(작업 과정·출처·승인·차단·사용량), 입력창
import { html, Icon, md, useState, useEffect, useRef, fmt, toast, fileToDataURL, urlToDataURL, api } from './lib.js';
import { tt } from './i18n.js';
import { S, useStore, newChat, currentChat, agentOf, send, stop, isBusy, decide, touch, GENERAL } from './store.js';

const KIND_ICON = { search: 'file-search', code: 'code', mcp: 'plug', function: 'square-function', web: 'globe', reasoning: 'brain' };
const ARG_LABELS = {
  employee_id: tt('사번', 'Employee ID'), category: tt('분류', 'Category'), merchant: tt('상호', 'Merchant'), receipt_date: tt('영수증 일자', 'Receipt date'),
  total_amount_krw: tt('영수증 합계', 'Receipt total'), claimed_amount_krw: tt('청구 금액 (규정 적용)', 'Claimed amount (policy applied)'),
  headcount: tt('참석 인원', 'Headcount'), purpose: tt('목적', 'Purpose'), policy_notes: tt('규정 검토', 'Policy review'),
};
const SAMPLE_ATTACH = {
  expense: [
    { name: tt('receipt_A_점심_영업1팀.png', 'receipt_A_lunch_sales_team_1.png'), label: tt('점심 영수증(4명)으로 정산하기', 'Submit with the lunch receipt (4 people)') },
    { name: tt('receipt_B_회식_영업2팀.png', 'receipt_B_team_dinner_sales_team_2.png'), label: tt('회식 영수증(12명)으로 정산하기', 'Submit with the team-dinner receipt (12 people)') },
  ],
};
const plural = (n, one, many) => (n === 1 ? one : many);

// ───────────────────────── 작업 과정(Steps)
function StepDetail({ step }) {
  const d = step.detail || {};
  if (step.kind === 'search') {
    return html`<div class="step-detail">
      ${d.queries?.length ? html`<div class="qchips">${d.queries.map((q) => html`<span class="qchip">“${q}”</span>`)}</div>` : null}
      ${d.results?.length ? html`<div class="hits">${d.results.slice(0, 3).map((r) => html`<div class="hit">
        <b><${Icon} name="file-text" size=14 />${r.filename}<span class="bar" title=${tt('관련도 ', 'Relevance ') + r.score}><i style=${'width:' + Math.min(100, r.score * 3000) + '%'}></i></span></b>
        <p>${r.snippet}</p></div>`)}${d.results.length > 3 ? html`<div style="font-size:12.5px;color:var(--text-3)">${tt(`외 ${d.results.length - 3}개 조각 · 관련도 순`, `+${d.results.length - 3} more ${plural(d.results.length - 3, 'chunk', 'chunks')} · ranked by relevance`)}</div>` : null}</div>` : null}</div>`;
  }
  if (step.kind === 'code') {
    return html`<div class="step-detail">
      ${d.code ? html`<div class="md" dangerouslySetInnerHTML=${{ __html: md('```python\n' + d.code + '\n```') }}></div>` : null}
      ${(d.outputs || []).filter((o) => o.type === 'logs').map((o) => html`<div class="mono">${o.text}</div>`)}</div>`;
  }
  if (step.kind === 'function') {
    let args = d.arguments; let out = d.output;
    try { args = JSON.stringify(JSON.parse(args), null, 1); } catch { /* 부분 JSON */ }
    return html`<div class="step-detail"><div class="mono">${args}</div>${out ? html`<div class="mono">→ ${out}</div>` : null}</div>`;
  }
  if (step.kind === 'mcp') {
    return html`<div class="step-detail">${d.tools ? html`<div class="qchips">${d.tools.map((t) => html`<span class="qchip">${t}</span>`)}</div>` : null}
      ${d.arguments ? html`<div class="mono">${d.arguments}</div>` : null}${d.output ? html`<div class="mono">${d.output}</div>` : null}</div>`;
  }
  if (step.kind === 'web') return html`<div class="step-detail"><div class="qchips"><span class="qchip">“${d.query}”</span></div></div>`;
  return null;
}

function Steps({ msg }) {
  const steps = msg.steps.filter((s) => !(s.kind === 'reasoning' && (s.ms || 0) < 600));
  const [open, setOpen] = useState(true);
  const [closed, setClosed] = useState({});
  if (!steps.length) return null;
  const done = steps.filter((s) => s.status === 'done').length;
  const total = steps.reduce((a, s) => a + (s.ms || 0), 0);
  const lastCode = steps.map((x) => x.kind).lastIndexOf('code');
  const dflt = (s) => (s.kind === 'code' ? s.status === 'running' || (msg.streaming && steps.indexOf(s) === lastCode) : ['search', 'function'].includes(s.kind));
  const isOpen = (s) => (closed[s.id] === undefined ? dflt(s) : !closed[s.id]);
  return html`<div class="steps fade">
    <button class="steps-head" onClick=${() => setOpen(!open)}>
      <${Icon} name="workflow" size=16 style="color:var(--brand)" />
      <span>${msg.streaming ? tt('에이전트가 작업하는 중…', 'The agent is working…') : tt(`에이전트가 ${steps.length}단계를 수행했습니다`, `The agent completed ${steps.length} ${plural(steps.length, 'step', 'steps')}`)}</span>
      <small>${tt(`${done}/${steps.length} 완료`, `${done}/${steps.length} done`)}${total ? ' · ' + fmt.ms(total) : ''}</small><span class="grow"></span>
      <${Icon} name=${open ? 'chevron-down' : 'chevron-right'} size=16 /></button>
    ${open ? steps.map((s) => html`<div class=${'step ' + (s.status === 'running' ? 'run' : '')} key=${s.id}>
      <button class="step-row" onClick=${() => setClosed({ ...closed, [s.id]: isOpen(s) })}>
        <span class=${'sic ' + s.kind}><${Icon} name=${KIND_ICON[s.kind] || 'wrench'} size=15 /></span>
        <span class="t">${s.title}</span>
        ${s.ms != null ? html`<span class="ms">${fmt.ms(s.ms)}</span>` : null}
        <span class=${'stat ' + (s.status === 'done' ? 'done' : 'run')}>${s.status === 'done' ? html`<${Icon} name="circle-check" size=18 />` : html`<${Icon} name="loader" size=16 cls="spin" />`}</span>
      </button>
      ${isOpen(s) ? html`<${StepDetail} step=${s} />` : null}</div>`) : null}
  </div>`;
}

// ───────────────────────── 승인(Human-in-the-loop)
function Approval({ chat, msg }) {
  const a = msg.approval;
  if (!a) return null;
  const call = a.calls.find((c) => c.needs_approval) || a.calls[0];
  const args = call.arguments || {};
  const pending = a.status === 'pending';
  return html`<div class="approval fade">
    <h4><${Icon} name="hand" size=20 style="color:#d97a06" />${tt('사람의 승인이 필요합니다', 'Human approval required')} ${!pending ? html`<span class=${'chip ' + (a.status === 'approved' ? 'ok' : 'bad')}>${a.status === 'approved' ? tt('승인됨', 'Approved') : tt('거절됨', 'Rejected')}</span>` : null}</h4>
    <p>${tt(html`에이전트가 <b>${call.name}</b> 도구로 정산을 상신하려고 합니다. 이 도구는 <b>승인 후에만</b> 실행되도록 설정되어 있습니다.`,
      html`The agent is about to submit the expense claim with the <b>${call.name}</b> tool. This tool is configured to run <b>only after approval</b>.`)}</p>
    <table>${Object.entries(args).map(([k, v]) => html`<tr><td>${ARG_LABELS[k] || k}</td><td class=${k === 'claimed_amount_krw' ? 'hl' : ''}>${/amount/.test(k) ? fmt.krw(v) : String(v)}</td></tr>`)}</table>
    ${pending ? html`<div class="btns">
      <button class="btn primary" onClick=${() => decide(chat, msg, true)}><${Icon} name="check" size=16 />${tt('승인하고 실행', 'Approve and run')}</button>
      <button class="btn danger" onClick=${() => decide(chat, msg, false)}><${Icon} name="x" size=16 />${tt('거절', 'Reject')}</button></div>` : null}
  </div>`;
}

// ───────────────────────── 메시지
function Bot({ chat, msg, last }) {
  const agent = agentOf(msg.agent);
  const showTyping = msg.streaming && !msg.text && !msg.blocked && !msg.approval && msg.steps.every((s) => s.status === 'done');
  const u = msg.usage;
  return html`<div class="msg bot fade">
    <div class="dot" style=${'background:' + agent.color}><${Icon} name=${agent.icon} size=19 /></div>
    <div class="body">
      <div class="who"><b>${agent.title}</b>${msg.model ? html`<span class="chip">${msg.model}</span>` : null}</div>
      ${msg.pii ? html`<div class="note pii"><${Icon} name="fingerprint" size=20 /><div><b>${tt(`개인정보 ${msg.pii.entities.length}건이 자동으로 마스킹되었습니다`, `${msg.pii.entities.length} personal data ${plural(msg.pii.entities.length, 'item was', 'items were')} masked automatically`)}</b>
        <div>${msg.pii.entities.map((e) => html`<span class="chip" style="margin:2px 4px 2px 0">${e.label}</span>`)}</div>
        <div style="margin-top:4px;font-size:13px">${tt(html`모델에는 <span class="masked">마스킹된 문장</span>만 전달됩니다`, html`Only the <span class="masked">masked text</span> is sent to the model`)} · Azure AI Language PII (${msg.pii.ms}ms)</div></div></div>` : null}
      <${Steps} msg=${msg} />
      ${msg.blocked ? html`<div class="note bad fade"><${Icon} name="shield-alert" size=22 /><div>
        <b>${tt('Foundry 가드레일이 요청을 차단했습니다', 'Foundry guardrails blocked the request')}</b>
        <div>${msg.blocked.detail?.message || ''}</div>
        <div style="margin-top:6px" class="chips">${(msg.blocked.detail?.filters || []).map((f) => html`<span class="chip bad">${f.label}${f.severity != null ? ' · ' + f.severity : ''}</span>`)}
          <span class="chip">${msg.blocked.detail?.stage || tt('입력 검사', 'Input check')}</span></div></div></div>` : null}
      ${showTyping ? html`<div class="typing"><i></i><i></i><i></i></div>` : null}
      ${msg.text ? html`<div class="md" dangerouslySetInnerHTML=${{ __html: md(msg.text) }}></div>` : null}
      ${msg.streaming && msg.text ? html`<span class="cursor"></span>` : null}
      ${(msg.files || []).filter((f) => f.image).length ? html`<div class="files">${msg.files.filter((f) => f.image).map((f) => html`<div class="fileimg fade"><img src=${f.url} alt=${f.name} />
        <div class="cap"><span><${Icon} name="image" size=14 /> ${f.name}</span><a href=${f.url} download=${f.name} class="chip brand"><${Icon} name="download" size=13 />${tt('다운로드', 'Download')}</a></div></div>`)}</div>` : null}
      ${(msg.citations || []).length ? html`<div class="cites">${msg.citations.map((c) => c.kind === 'file'
        ? html`<a class="cite" href=${'/api/samples/knowledge/' + encodeURIComponent(c.title)} target="_blank"><${Icon} name="file-text" size=15 />${c.title.replace(/\.pdf$/i, '').replace(/_/g, ' ')}</a>`
        : html`<a class="cite" href=${c.url} target="_blank"><${Icon} name="link" size=15 />${c.title}</a>`)}</div>` : null}
      ${msg.approval ? html`<${Approval} chat=${chat} msg=${msg} />` : null}
      ${msg.error ? html`<div class="note warn"><${Icon} name="triangle-alert" size=20 /><div><b>${tt('문제가 발생했습니다', 'Something went wrong')}</b>${msg.error}</div></div>` : null}
      ${u ? html`<div class="usage">
        <span class="chip"><${Icon} name="cpu" size=13 />${u.model}</span>
        <span class="chip"><${Icon} name="coins" size=13 />${tt(`입력 ${fmt.n(u.input_tokens)} · 출력 ${fmt.n(u.output_tokens)}${u.reasoning_tokens ? ' (추론 ' + fmt.n(u.reasoning_tokens) + ')' : ''}`,
          `Input ${fmt.n(u.input_tokens)} · Output ${fmt.n(u.output_tokens)}${u.reasoning_tokens ? ' (reasoning ' + fmt.n(u.reasoning_tokens) + ')' : ''}`)}</span>
        <span class="chip"><${Icon} name="timer" size=13 />${fmt.ms(u.latency_ms)}</span>
        ${u.ttft_ms ? html`<span class="chip"><${Icon} name="zap" size=13 />${tt('첫 토큰 ', 'First token ')}${fmt.ms(u.ttft_ms)}</span>` : null}
        <span class="acts">
          <button class="icobtn" title=${tt('복사', 'Copy')} onClick=${() => { navigator.clipboard?.writeText(msg.text); toast(tt('복사했습니다', 'Copied')); }}><${Icon} name="copy" size=16 /></button>
          <button class="icobtn" title=${tt('좋아요', 'Good response')} onClick=${() => toast(tt('피드백을 기록했습니다 (데모)', 'Feedback recorded (demo)'))}><${Icon} name="thumbs-up" size=16 /></button>
          <button class="icobtn" title=${tt('별로예요', 'Bad response')} onClick=${() => toast(tt('피드백을 기록했습니다 (데모)', 'Feedback recorded (demo)'))}><${Icon} name="thumbs-down" size=16 /></button>
        </span></div>` : null}
    </div></div>`;
}

function User({ msg }) {
  return html`<div class="msg user fade"><div class="bubble">
    ${msg.images?.length ? html`<div class="imgs">${msg.images.map((i) => html`<img src=${i.data_url} alt=${i.name} />`)}</div>` : null}
    ${msg.files?.length ? html`<div class="imgs">${msg.files.map((f) => html`<span class="attach-chip"><${Icon} name="file-text" size=14 />${f.name}</span>`)}</div>` : null}
    ${msg.display || msg.text}</div></div>`;
}

// ───────────────────────── 새 대화 화면 (ChatGPT 처럼 인사말 + 입력창을 가운데에, 추천 질문은 입력창 아래에)
function HeroHead({ agentKey }) {
  const agent = agentOf(agentKey);
  const general = agentKey === 'general';
  const givenName = (S.config?.user?.name || '').split(/\s+/)[0];
  return html`<div class="hero fade">
    ${general ? null : html`<div class="logo"><${Icon} name=${agent.icon} size=30 /></div>`}
    <h2>${general ? tt('무엇을 도와드릴까요?', 'How can I help?') : agent.title}</h2>
    <p>${general ? tt(`${S.config?.user?.name || ''}님, 업무에 필요한 전용 에이전트는 왼쪽에서 고를 수 있어요.`, `${givenName ? givenName + ', you' : 'You'} can pick a dedicated agent for your work from the left.`) : agent.subtitle}</p>
    ${general ? null : html`<div class="chips" style="justify-content:center;margin-top:12px">${agent.capabilities.map((c) => html`<span class="chip brand">${c}</span>`)}<span class="chip"><${Icon} name="cpu" size=13 />${agent.model}</span></div>`}
  </div>`;
}

function Starters({ agentKey, onStart }) {
  const agent = agentOf(agentKey);
  const samples = SAMPLE_ATTACH[agentKey] || [];
  return html`<div class="starters fade" style=${'--c:' + agent.color}>
    ${samples.map((s, i) => html`<button class="starter" onClick=${() => onStart(agent.starters[i], s.name)}><${Icon} name="paperclip" size=18 />${agent.starters[i]}<em>${s.label}</em></button>`)}
    ${(samples.length ? [] : agent.starters).map((t) => html`<button class="starter" onClick=${() => onStart(t)}><${Icon} name="sparkles" size=18 />${t}</button>`)}
    ${agentKey === 'analyst' ? html`<div class="hint">${tt('분석 대상: ', 'Data to analyze: ')}<a href="/api/samples/data/sales_2025_2026.csv">sales_2025_2026.csv</a> · <a href="/api/samples/data/voc_2026.csv">voc_2026.csv</a>${tt(' (에이전트의 Code Interpreter에 이미 연결되어 있습니다)', ' (already connected to the agent’s Code Interpreter)')}</div>` : null}
  </div>`;
}

// ───────────────────────── 입력창
function Composer({ chat, agent, onSend, disabled, inline = false }) {
  const [text, setText] = useState('');
  const [images, setImages] = useState([]);
  const [files, setFiles] = useState([]);
  const [pii, setPii] = useState(false);
  const [web, setWeb] = useState(false);
  const ta = useRef(); const fileIn = useRef();
  const busy = isBusy(chat);

  useEffect(() => { if (ta.current) { ta.current.style.height = 'auto'; ta.current.style.height = Math.min(200, ta.current.scrollHeight) + 'px'; } }, [text]);
  useEffect(() => { window.__composer = { setText, setImages, setPii, setWeb, focus: () => ta.current?.focus(), submit: () => submit(text, images) }; });

  const addFiles = async (list) => {
    for (const f of list) {
      if (f.type.startsWith('image/')) setImages((x) => [...x, { name: f.name, data_url: null, pending: fileToDataURL(f) }]);
      else toast(tt('이 데모에서는 이미지 첨부를 지원합니다 (영수증 등)', 'This demo only supports image attachments (such as receipts)'));
    }
    setImages((x) => x);
  };
  useEffect(() => { images.filter((i) => i.pending).forEach(async (i) => { const d = await i.pending; setImages((xs) => xs.map((y) => (y === i ? { name: i.name, data_url: d } : y))); }); }, [images]);

  const submit = (t = text, imgs = images) => {
    if ((!t.trim() && !imgs.length) || busy || disabled) return;
    onSend({ text: t.trim(), images: imgs.filter((i) => i.data_url), files, redactPii: pii, webSearch: web });
    setText(''); setImages([]); setFiles([]);
  };
  const onKey = (e) => { if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) { e.preventDefault(); submit(); } };
  const onPaste = (e) => { const f = [...(e.clipboardData?.files || [])]; if (f.length) { e.preventDefault(); addFiles(f); } };

  return html`<div class=${'composer-wrap' + (inline ? ' inline' : '')}><div class="composer">
    ${images.length || files.length ? html`<div class="pending">
      ${images.map((i) => html`<div class="p"><img src=${i.data_url || ''} alt=${i.name} /><button onClick=${() => setImages(images.filter((x) => x !== i))}><${Icon} name="x" size=12 /></button></div>`)}
    </div>` : null}
    <textarea ref=${ta} rows="1" value=${text} placeholder=${disabled ? tt('준비 중입니다…', 'Getting ready…') : agent.key === 'general' ? tt('무엇이든 물어보세요', 'Ask me anything') : tt(agent.title + '에게 물어보세요', 'Ask ' + agent.title)}
      onInput=${(e) => setText(e.target.value)} onKeyDown=${onKey} onPaste=${onPaste} disabled=${disabled}></textarea>
    <div class="row">
      <input ref=${fileIn} type="file" accept="image/*" multiple hidden onChange=${(e) => { addFiles([...e.target.files]); e.target.value = ''; }} />
      <button class="tog" onClick=${() => fileIn.current.click()}><${Icon} name="paperclip" size=15 />${tt('이미지', 'Image')}</button>
      <button class=${'tog ' + (pii ? 'on' : '')} onClick=${() => setPii(!pii)} title=${tt('질문에 포함된 주민번호·전화번호 등을 모델로 보내기 전에 지웁니다', 'Masks personal data in your question, such as names, ID numbers and phone numbers, before it is sent to the model')}><${Icon} name="fingerprint" size=15 />${tt('개인정보 자동 마스킹', 'Mask personal data')}</button>
      ${agent.key === 'general' ? html`<button class=${'tog ' + (web ? 'on' : '')} onClick=${() => setWeb(!web)}><${Icon} name="globe" size=15 />${tt('웹 검색', 'Web search')}</button>` : null}
      ${busy ? html`<button class="send stop" onClick=${() => stop(chat)} title=${tt('중단', 'Stop')}><${Icon} name="square" size=14 /></button>`
        : html`<button class="send" disabled=${(!text.trim() && !images.length) || disabled} onClick=${() => submit()}><${Icon} name="arrow-up" size=19 stroke=2.6 /></button>`}
    </div></div>
    <div class="foot-note">${tt(`AI가 만든 답변은 부정확할 수 있습니다. 중요한 내용은 출처 원문을 확인하세요 · Microsoft Foundry 프로젝트(${S.config?.region || ''})로 호출됩니다`,
      `AI-generated answers may be inaccurate. Check the source documents for anything important · Calls go to the Microsoft Foundry project (${fmt.region(S.config?.region) || ''})`)}</div></div>`;
}

// ───────────────────────── 채팅 화면
export function ChatView({ agentKey }) {
  useStore();
  const agent = agentOf(agentKey);
  let chat = currentChat();
  if (!chat || chat.agent !== agentKey) {
    const found = S.chats.find((c) => c.agent === agentKey && c.id === S.currentId);
    chat = found || null;
  }
  const scroller = useRef(); const stick = useRef(true);
  const ready = !S.status || ['ready', 'idle'].includes(S.status.state);

  useEffect(() => { if (!chat) newChat(agentKey); }, [agentKey, chat?.id]);
  useEffect(() => { const el = scroller.current; if (el && stick.current && chat?.messages.length) el.scrollTop = el.scrollHeight; });
  useEffect(() => {
    const el = scroller.current;
    const onLoad = () => { if (stick.current) el.scrollTop = el.scrollHeight; };
    el?.addEventListener('load', onLoad, true);
    return () => el?.removeEventListener('load', onLoad, true);
  }, [chat?.id]);

  const start = async (text, sampleName) => {
    const c = chat || newChat(agentKey);
    let images = [];
    if (sampleName) images = [{ name: sampleName, data_url: await urlToDataURL('/api/samples/receipts/' + encodeURIComponent(sampleName)) }];
    send(c, { text, images });
  };
  const models = S.config?.models || [];

  const empty = !chat || chat.messages.length === 0;
  const doSend = (p) => { stick.current = true; send(chat, p); };

  return html`<div class="main-col" style="display:flex;flex-direction:column;flex:1;min-height:0">
    <div class="top"><h1><span class="dot" style=${'width:30px;height:30px;border-radius:9px;display:grid;place-items:center;color:#fff;background:' + agent.color}><${Icon} name=${agent.icon} size=17 /></span>${agent.title}</h1>
      <span class="sub">${agent.subtitle}</span><span class="grow"></span>
      ${agentKey === 'general' && chat ? html`<select class="select" value=${chat.model} onChange=${(e) => { chat.model = e.target.value; chat.conv_id = chat.messages.length ? chat.conv_id : null; touch(); }}>
        ${models.map((m) => html`<option value=${m.name}>${m.label}</option>`)}</select>` : null}
      <span class="chip ok"><span class="pulse"></span>${tt('Foundry 연결됨', 'Connected to Foundry')}</span><span class="chip"><${Icon} name="map-pin" size=13 />${fmt.region(S.config?.region)}</span></div>
    ${!ready ? html`<div class="banner"><${Icon} name="loader" size=22 cls="spin" /><div><b>${tt('처음 배포 후 한 번만 하는 준비 작업을 진행 중입니다', 'One-time setup after the first deployment is in progress')}</b>
      <span style="font-size:13px;color:#7a4a05">${tt('사규 PDF를 벡터 스토어에 올리고, 에이전트 4개를 Foundry 프로젝트에 만듭니다.', 'Uploading the policy PDFs to the vector store and creating 4 agents in the Foundry project.')}</span>
      <ul>${(S.status?.steps || []).map((s) => html`<li>${s.status === 'done' ? '✅' : '⏳'} ${s.title} ${s.detail || ''}</li>`)}</ul></div></div>` : null}
    ${empty ? html`<div class="scroll empty" ref=${scroller}><div class="col empty-col">
        <${HeroHead} agentKey=${agentKey} />
        ${chat ? html`<${Composer} chat=${chat} agent=${agent} disabled=${!ready} inline=${true} onSend=${doSend} />` : null}
        <${Starters} agentKey=${agentKey} onStart=${start} /></div></div>`
      : html`<div class="scroll" ref=${scroller} onScroll=${(e) => { const el = e.target; stick.current = el.scrollHeight - el.scrollTop - el.clientHeight < 140; }}>
          <div class="col msgs">${chat.messages.map((m, i) => (m.role === 'user' ? html`<${User} msg=${m} key=${m.id} />` : html`<${Bot} chat=${chat} msg=${m} key=${m.id} last=${i === chat.messages.length - 1} />`))}</div></div>
        <${Composer} chat=${chat} agent=${agent} disabled=${!ready} onSend=${doSend} />`}
  </div>`;
}
