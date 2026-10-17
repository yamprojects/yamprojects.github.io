// Progressive enhancement only: the page is complete without this file. It is loaded with defer;
// the .js class that the entrance animations wait for is set by a one-line script in <head>.
(() => {
  const root = document.documentElement;

  // The hero's loops only run while it is on screen and the tab is visible (.still otherwise);
  // a card's travelling border light only runs while that card is on screen (.lit).
  const hero = document.querySelector('.hero');
  let heroVisible = true;
  let video = null;
  const syncMotion = () => {
    const still = document.hidden || !heroVisible;
    root.classList.toggle('still', still);
    root.classList.toggle('tab-hidden', document.hidden);
    video?.sync(still);
    sky?.sync(still);
  };
  document.addEventListener('visibilitychange', syncMotion);
  if ('IntersectionObserver' in window) {
    if (hero) {
      new IntersectionObserver(([entry]) => {
        heroVisible = entry.isIntersecting;
        syncMotion();
      }).observe(hero);
    }
    const lit = new IntersectionObserver((entries) => {
      for (const entry of entries) entry.target.classList.toggle('lit', entry.isIntersecting);
    });
    document.querySelectorAll('.card, .category').forEach((el) => lit.observe(el));
  }

  // The stats count up from 0 the first time they are seen (the page holds the real numbers,
  // so without this script, or with reduced motion, they simply show).
  const stats = document.querySelector('.stats');
  if (stats && 'IntersectionObserver' in window && !matchMedia('(prefers-reduced-motion: reduce)').matches) {
    const cells = [...stats.querySelectorAll('dd')].map((dd) => ({ dd, to: Number(dd.textContent) }))
      .filter((c) => Number.isFinite(c.to) && c.to > 0);
    const once = new IntersectionObserver(([entry]) => {
      if (!entry.isIntersecting) return;
      once.disconnect();
      // keep each number's width, so nothing moves while it counts
      cells.forEach((c) => { c.dd.style.minWidth = `${String(c.to).length}ch`; c.dd.textContent = '0'; });
      // about ten text updates, not one per frame: each one is a small layout
      const t0 = performance.now(), length = 900;
      let last = 0;
      const step = (now) => {
        const k = Math.min(1, (now - t0) / length), ease = 1 - (1 - k) ** 3;
        if (k === 1 || now - last > 90) {
          last = now;
          cells.forEach((c) => { c.dd.textContent = String(Math.round(c.to * ease)); });
        }
        if (k < 1) requestAnimationFrame(step);
      };
      requestAnimationFrame(step);
    }, { threshold: .6 });
    once.observe(stats);
  }

  // The sky in the hero: the star layers shift a little with the pointer (desktop) and with the
  // scroll, at three depths, and meteors cross it now and then. Everything stops while the hero
  // is off screen or the tab is hidden.
  const space = document.querySelector('.space');
  const calm = matchMedia('(prefers-reduced-motion: reduce)');
  let sky = null;
  if (space && !calm.matches) {
    const layers = [['.stars--far', .12, 6], ['.stars--mid', .22, 12], ['.stars--near', .34, 20]]
      .map(([sel, scrollK, pointerK]) => ({ el: space.querySelector(sel), scrollK, pointerK }));
    let px = 0, py = 0, sy = 0, queued = false;
    const apply = () => {
      queued = false;
      for (const l of layers) {
        l.el.style.transform = `translate3d(${(px * l.pointerK).toFixed(1)}px, ${(py * l.pointerK + sy * l.scrollK).toFixed(1)}px, 0)`;
      }
    };
    const queue = () => { if (!queued) { queued = true; requestAnimationFrame(apply); } };
    addEventListener('scroll', () => { if (heroVisible) { sy = scrollY; queue(); } }, { passive: true });
    if (matchMedia('(hover: hover) and (pointer: fine)').matches) {
      addEventListener('pointermove', (e) => {
        if (!heroVisible) return;
        px = e.clientX / innerWidth - .5;
        py = e.clientY / innerHeight - .5;
        queue();
      }, { passive: true });
    }

    // Meteors: three pooled streak elements. Each flight is one Web Animations transform and
    // opacity animation, which the compositor runs on its own, so a meteor costs the page no
    // work per frame (no canvas, no requestAnimationFrame, nothing allocated while it flies).
    const phone = matchMedia('(max-width: 430px)');
    const pool = [...space.querySelectorAll('.meteors i')];
    let timer = 0, running = false, first = true;
    const launch = (big) => {
      const m = pool.find((el) => !el.flight || el.flight.playState === 'finished' || el.flight.playState === 'idle');
      if (!m) return;
      const r = space.getBoundingClientRect();
      const w = r.width, h = r.height;
      const dir = Math.random() < .5 ? 1 : -1;     // falling to the right or to the left
      const a = big ? .42 : .3 + Math.random() * .32;
      const len = big ? 420 : 150 + Math.random() * 120;
      const dist = (big ? 1.5 : .75 + Math.random() * .45) * (big ? 1150 : 700 + Math.random() * 450);
      const x0 = dir > 0 ? Math.random() * w * .6 : w * .4 + Math.random() * w * .6;
      const y0 = Math.random() * h * .3;
      const deg = (dir > 0 ? a : Math.PI - a) * 180 / Math.PI;
      const x1 = x0 + Math.cos(a) * dir * dist, y1 = y0 + Math.sin(a) * dist;
      m.classList.toggle('big', big);
      m.style.width = `${Math.round(len)}px`;
      const at = (x, y, s) => `translate(${(x - len).toFixed(0)}px, ${y.toFixed(0)}px) rotate(${deg.toFixed(1)}deg) scaleX(${s})`;
      m.flight = m.animate([
        { transform: at(x0, y0, .35), opacity: 0 },
        { opacity: 1, offset: .15 },
        { transform: at((x0 + x1) / 2, (y0 + y1) / 2, 1), opacity: 1, offset: .6 },
        { transform: at(x1, y1, 1), opacity: 0 },
      ], { duration: (big ? 1.5 : .75 + Math.random() * .45) * 1000, easing: 'linear' });
    };
    const schedule = () => {
      clearTimeout(timer);
      if (!running) return;
      // the first one waits until the page has settled
      const wait = (first || phone.matches ? 5000 : 3000) + Math.random() * 4000;
      first = false;
      timer = setTimeout(() => {
        launch(Math.random() < .1);
        if (!phone.matches && Math.random() < .25) setTimeout(() => running && launch(false), 250 + Math.random() * 600);
        schedule();
      }, wait);
    };
    sky = {
      sync(still) {
        if (still === !running) return;
        running = !still;
        if (running) schedule();
        else { clearTimeout(timer); pool.forEach((m) => m.flight?.cancel()); }
      },
    };
  }

  // The version pills follow the projects' own sites: each project's latest.json is read once
  // (two small requests, skipped under Save-Data) and a newer version replaces the text.
  const versioned = [...document.querySelectorAll('[data-version-url]')];
  if (versioned.length && 'fetch' in window && navigator.connection?.saveData !== true) {
    const check = () => {
      const groups = new Map();
      for (const el of versioned) {
        const url = el.dataset.versionUrl;
        if (!groups.has(url)) groups.set(url, []);
        groups.get(url).push(el);
      }
      for (const [url, els] of groups) {
        fetch(url, { credentials: 'omit' })
          .then((r) => (r.ok ? r.json() : null))
          .then((data) => {
            const value = data && String(data[els[0].dataset.versionKey] ?? '').trim();
            if (!value || !/^\d+(\.\d+){1,3}$/.test(value)) return;
            for (const el of els) if (el.textContent !== `v${value}`) el.textContent = `v${value}`;
          })
          .catch(() => {});
      }
    };
    const later = () => (window.requestIdleCallback || setTimeout)(check, { timeout: 3000 });
    if (document.readyState === 'complete') later(); else addEventListener('load', later, { once: true });
  }

  // The background video. Its sources (WebM, then MP4; 540p up to 900px wide) are attached only
  // the first time it is actually going to play: after the page has loaded and the browser is
  // idle, with motion allowed, no Save-Data, the hero on screen and the tab visible. It fades in
  // while playing (is-playing follows play and pause) and switches files when the color scheme or
  // the width class changes.
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
