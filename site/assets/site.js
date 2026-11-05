/* 영상 플레이어(챕터 이동 · 시점 링크) · 코드 복사 — 외부 라이브러리 없음 */
(() => {
  const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const pad = (n) => String(n).padStart(2, '0');
  const mmss = (s) => `${pad(Math.floor(s / 60))}:${pad(Math.floor(s % 60))}`;

  const video = document.getElementById('demo');
  if (video) {
    const list = document.getElementById('chapter-list');
    const buttons = [...list.querySelectorAll('button[data-t]')];
    const starts = buttons.map((b) => Number(b.dataset.t));
    const now = document.getElementById('now');
    const scroller = list.closest('.chapters-scroll');
    let current = -1;

    const seek = (t, { play = true, reveal = true } = {}) => {
      if (video.readyState === 0) {
        video.addEventListener('loadedmetadata', () => { video.currentTime = t; }, { once: true });
      } else {
        video.currentTime = t;
      }
      if (play) video.play().catch(() => {});
      markChapter(t); // 영상이 해당 위치를 불러오기 전에도 챕터 표시와 '지금' 문구를 바로 바꾼다
      if (reveal) {
        const r = video.getBoundingClientRect();
        if (r.top < 64 || r.bottom > innerHeight) video.scrollIntoView({ behavior: reduce ? 'auto' : 'smooth', block: 'center' });
      }
    };

    const markChapter = (t) => {
      let i = starts.length - 1;
      while (i > 0 && starts[i] > t + 0.3) i--;
      if (i === current) return;
      current = i;
      buttons.forEach((b, k) => (k === i ? b.setAttribute('aria-current', 'true') : b.removeAttribute('aria-current')));
      const b = buttons[i];
      now.textContent = `${mmss(starts[i])} · ${b.querySelector('span').textContent}`;
      const top = b.offsetTop - list.offsetTop;
      if (top < scroller.scrollTop || top + b.offsetHeight > scroller.scrollTop + scroller.clientHeight) {
        scroller.scrollTo({ top: Math.max(0, top - 8), behavior: reduce ? 'auto' : 'smooth' });
      }
    };

    video.addEventListener('timeupdate', () => markChapter(video.currentTime));
    video.addEventListener('seeked', () => markChapter(video.currentTime));

    // 챕터 · 기능 카드 · 대본의 시각 버튼 — data-t 가 있는 모든 것이 영상을 그 시각으로 옮긴다
    document.addEventListener('click', (e) => {
      const el = e.target.closest('[data-t]');
      if (!el || e.defaultPrevented || e.metaKey || e.ctrlKey || e.shiftKey) return;
      e.preventDefault();
      const t = Number(el.dataset.t);
      seek(t);
      history.replaceState(null, '', t > 0 ? `#t=${t}` : '#video');
    });

    // 공유받은 #t=263 링크는 그 시각에 맞춰 열어 둔다(자동 재생은 브라우저가 막으므로 재생 버튼만 누르면 됩니다)
    const fromHash = () => {
      const m = /^#t=(\d+)$/.exec(location.hash);
      if (m) seek(Number(m[1]), { play: false });
    };
    addEventListener('hashchange', fromHash);
    fromHash();
    markChapter(0);

    const share = document.getElementById('share');
    share?.addEventListener('click', async () => {
      const url = `${location.origin}${location.pathname}#t=${Math.floor(video.currentTime)}`;
      const label = share.querySelector('span');
      const old = label.textContent;
      try {
        await navigator.clipboard.writeText(url);
        label.textContent = `${mmss(video.currentTime)} 링크를 복사했습니다`;
        share.classList.add('done');
      } catch {
        label.textContent = '복사하지 못했습니다 — 주소창의 링크를 쓰세요';
        history.replaceState(null, '', `#t=${Math.floor(video.currentTime)}`);
      }
      setTimeout(() => { label.textContent = old; share.classList.remove('done'); }, 2200);
    });
  }

  document.querySelectorAll('.code .copy').forEach((btn) => {
    btn.addEventListener('click', async () => {
      const label = btn.querySelector('span');
      const old = label.textContent;
      try {
        await navigator.clipboard.writeText(btn.closest('.code').querySelector('code').innerText);
        label.textContent = '복사됨';
        btn.classList.add('done');
      } catch {
        label.textContent = '직접 선택해 복사하세요';
      }
      setTimeout(() => { label.textContent = old; btn.classList.remove('done'); }, 1800);
    });
  });
})();
