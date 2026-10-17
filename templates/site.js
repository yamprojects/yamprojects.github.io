// Progressive enhancement only: the page is complete without this file. It is loaded with defer;
// the .js class that the entrance animations wait for is set by a one-line script in <head>.
(() => {
  const root = document.documentElement;

  // The aurora only moves while the hero is on screen, the tab is visible and motion is not
  // paused with the toggle in the top bar (its choice is remembered on this device).
  const hero = document.querySelector('.hero');
  const toggle = document.querySelector('.motion');
  const KEY = 'motion-paused';
  let heroVisible = true;
  let userPaused = false;
  let video = null;
  try { userPaused = localStorage.getItem(KEY) === '1'; } catch { /* storage blocked */ }
  const syncMotion = () => {
    const still = document.hidden || !heroVisible || userPaused;
    root.classList.toggle('still', still);
    video?.sync(still);
  };
  document.addEventListener('visibilitychange', syncMotion);
  if (hero && 'IntersectionObserver' in window) {
    new IntersectionObserver(([entry]) => {
      heroVisible = entry.isIntersecting;
      syncMotion();
    }).observe(hero);
  }
  if (toggle) {
    toggle.hidden = false;
    toggle.setAttribute('aria-pressed', String(userPaused));
    toggle.addEventListener('click', () => {
      userPaused = !userPaused;
      toggle.setAttribute('aria-pressed', String(userPaused));
      try { localStorage.setItem(KEY, userPaused ? '1' : '0'); } catch { /* storage blocked */ }
      syncMotion();
    });
  }

  // The background video. Its sources (WebM, then MP4; 540p up to 900px wide) are attached only
  // the first time it is actually going to play: after the page has loaded and the browser is
  // idle, with motion allowed, no Save-Data, the hero on screen, the tab visible and motion not
  // paused. It fades in while playing (is-playing follows play and pause) and switches files when
  // the color scheme or the width class changes.
  const box = document.querySelector('.bg-video');
  const clip = box?.querySelector('video');
  if (clip) {
    const reduce = matchMedia('(prefers-reduced-motion: reduce)');
    const dark = matchMedia('(prefers-color-scheme: dark)');
    const small = matchMedia('(max-width: 900px)');
    const saveData = navigator.connection?.saveData === true;
    let loaded = '', wanted = false, ready = false, settle = 0;
    const update = () => {
      clearTimeout(settle);
      if (!ready || !wanted || reduce.matches || saveData) {
        if (!clip.paused) clip.pause();
        return;
      }
      // The first time, wait until the page has settled (a link to #translations scrolls the
      // hero away right after load), so nothing is fetched for a video that would not play.
      if (!loaded) {
        settle = setTimeout(() => { if (wanted) attach(); }, 900);
        return;
      }
      attach();
    };
    const attach = () => {
      const name = `bg-${dark.matches ? 'dark' : 'light'}${small.matches ? '-720' : ''}`;
      if (name !== loaded) {
        loaded = name;
        box.classList.remove('is-playing');
        clip.innerHTML = `<source src="${box.dataset.base}${name}.webm" type="video/webm">`
          + `<source src="${box.dataset.base}${name}.mp4" type="video/mp4">`;
        clip.load();
      }
      clip.play().catch(() => {}); // autoplay refused: the poster stays, which is fine
    };
    clip.addEventListener('playing', () => box.classList.add('is-playing'));
    clip.addEventListener('pause', () => box.classList.remove('is-playing'));
    [reduce, dark, small].forEach((m) => m.addEventListener('change', update));
    video = { sync(still) { wanted = !still; update(); } };
    const start = () => (window.requestIdleCallback || setTimeout)(() => { ready = true; update(); }, { timeout: 2000 });
    if (document.readyState === 'complete') start(); else addEventListener('load', start, { once: true });
  }
  syncMotion();

  // Spotlight: the glow and the bright edge of a card follow the pointer (once per frame).
  if (matchMedia('(hover: hover) and (pointer: fine)').matches) {
    for (const card of document.querySelectorAll('.card')) {
      let frame = 0, x = 0, y = 0;
      card.addEventListener('pointermove', (e) => {
        x = e.clientX; y = e.clientY;
        if (frame) return;
        frame = requestAnimationFrame(() => {
          frame = 0;
          const r = card.getBoundingClientRect();
          card.style.setProperty('--mx', `${x - r.left}px`);
          card.style.setProperty('--my', `${y - r.top}px`);
        });
      });
      card.addEventListener('pointerleave', () => {
        cancelAnimationFrame(frame);
        frame = 0;
        card.style.removeProperty('--mx');
        card.style.removeProperty('--my');
      });
    }
  }

  // The category bar fades at an edge that has more links past it. Browsers with scroll-driven
  // animations do this in CSS alone; the others get the same two variables from here.
  const cats = document.querySelector('.cats');
  if (cats && !CSS.supports('animation-timeline: scroll()')) {
    const fade = () => {
      const max = cats.scrollWidth - cats.clientWidth;
      const pos = Math.abs(cats.scrollLeft);
      cats.style.setProperty('--fade-start', max > 1 && pos > 1 ? '28px' : '0px');
      cats.style.setProperty('--fade-end', max > 1 && pos < max - 1 ? '28px' : '0px');
    };
    cats.addEventListener('scroll', fade, { passive: true });
    addEventListener('resize', fade);
    fade();
  }

  if (!('IntersectionObserver' in window)) return;

  // The category link of the section on screen lights up.
  const links = new Map([...document.querySelectorAll('.cats a')].map((a) => [a.hash.slice(1), a]));
  const spy = new IntersectionObserver((entries) => {
    for (const entry of entries) {
      const link = links.get(entry.target.id);
      if (!link) continue;
      if (entry.isIntersecting) {
        links.forEach((a) => a.removeAttribute('aria-current'));
        link.setAttribute('aria-current', 'location');
      } else if (link.hasAttribute('aria-current') && entry.boundingClientRect.top > 0) {
        link.removeAttribute('aria-current');
      }
    }
  }, { rootMargin: '-35% 0px -60% 0px' });
  document.querySelectorAll('.category').forEach((s) => spy.observe(s));
})();
