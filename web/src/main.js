import { gsap } from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';

const root = document.documentElement;
const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
const finePointer = window.matchMedia('(hover: hover) and (pointer: fine)').matches;

if (!reduceMotion) root.classList.add('js-motion');

// ---------------------------------------------------------------------------
// Scroll progress bar (cheap: one custom property per frame).
// ---------------------------------------------------------------------------
{
  const bar = document.getElementById('progress');
  let ticking = false;
  const update = () => {
    ticking = false;
    const max = document.documentElement.scrollHeight - window.innerHeight;
    bar?.style.setProperty('--p', max > 0 ? Math.min(1, window.scrollY / max).toFixed(4) : '0');
  };
  window.addEventListener(
    'scroll',
    () => {
      if (!ticking) {
        ticking = true;
        requestAnimationFrame(update);
      }
    },
    { passive: true }
  );
  update();
}

// Split text for reveals. The element keeps its text for screen readers via
// aria-label; the pieces are hidden from them.
function splitChars(el) {
  const text = el.textContent;
  el.setAttribute('aria-label', text);
  el.textContent = '';
  const out = [];
  for (const ch of text) {
    const span = document.createElement('span');
    span.className = 'ch';
    span.setAttribute('aria-hidden', 'true');
    span.textContent = ch === ' ' ? '\u00a0' : ch;
    el.append(span);
    out.push(span);
  }
  return out;
}
function splitWords(el) {
  const text = el.textContent.trim();
  el.setAttribute('aria-label', text);
  el.textContent = '';
  const out = [];
  text.split(/\s+/).forEach((word, i, all) => {
    const wrap = document.createElement('span');
    wrap.className = 'sw';
    wrap.setAttribute('aria-hidden', 'true');
    const inner = document.createElement('span');
    inner.className = 'sw-in';
    inner.textContent = word;
    wrap.append(inner);
    el.append(wrap);
    if (i < all.length - 1) el.append(' ');
    out.push(inner);
  });
  return out;
}

// ---------------------------------------------------------------------------
// Liquid-glass refraction: only Chromium renders SVG filters inside
// backdrop-filter. Safari and Firefox parse the rule but drop the whole
// backdrop, so gate it on a Chromium-only API and keep plain blur elsewhere.
// ---------------------------------------------------------------------------
if ('userAgentData' in navigator && window.CSS?.supports?.('backdrop-filter', 'url(#sn-liquid) blur(1px)')) {
  root.classList.add('has-refraction');
}

// ---------------------------------------------------------------------------
// Nav: tucks away while you read down the page, comes back when you scroll
// up. Highlights the section you're in.
// ---------------------------------------------------------------------------
const header = document.getElementById('top-nav');
{
  let lastY = window.scrollY;
  let raf = 0;
  window.addEventListener(
    'scroll',
    () => {
      cancelAnimationFrame(raf);
      raf = requestAnimationFrame(() => {
        const y = window.scrollY;
        const down = y > lastY + 4;
        const up = y < lastY - 4;
        if (down && y > window.innerHeight * 0.6) header.classList.add('is-hidden');
        else if (up || y < 80) header.classList.remove('is-hidden');
        if (down || up) lastY = y;
      });
    },
    { passive: true }
  );
  // Keyboard users always get the nav back.
  header.addEventListener('focusin', () => header.classList.remove('is-hidden'));
}

const navLinks = [...document.querySelectorAll('.nav-link')];
const sectionFor = new Map(
  navLinks.map((link) => [document.querySelector(link.getAttribute('href')), link]).filter(([s]) => s)
);
// The "About me" card sits under the Status link.
const statusLink = sectionFor.get(document.getElementById('status'));
if (statusLink) sectionFor.set(document.getElementById('build'), statusLink);
{
  const visible = new Set();
  const io = new IntersectionObserver(
    (entries) => {
      entries.forEach((e) => (e.isIntersecting ? visible.add(e.target) : visible.delete(e.target)));
      const current = [...sectionFor.keys()].find((s) => visible.has(s));
      navLinks.forEach((l) => l.removeAttribute('aria-current'));
      if (current) sectionFor.get(current).setAttribute('aria-current', 'true');
    },
    { rootMargin: '-45% 0px -50% 0px' }
  );
  sectionFor.forEach((_, section) => section && io.observe(section));
}

// Move focus with in-page links so keyboard and screen reader users land
// where the page scrolled to.
document.addEventListener('click', (e) => {
  const link = e.target.closest('a[href^="#"]');
  if (!link) return;
  const target = document.querySelector(link.getAttribute('href'));
  if (!target) return;
  if (!target.hasAttribute('tabindex')) target.setAttribute('tabindex', '-1');
  target.focus({ preventScroll: true });
});

// ---------------------------------------------------------------------------
// Micro-interactions (fine pointers only).
// ---------------------------------------------------------------------------
if (finePointer && !reduceMotion) {
  // Magnetic buttons: drift toward the cursor, spring back on leave.
  document.querySelectorAll('.magnetic').forEach((btn) => {
    btn.addEventListener('pointermove', (e) => {
      const r = btn.getBoundingClientRect();
      btn.style.setProperty('--mx', `${((e.clientX - (r.left + r.width / 2)) * 0.3).toFixed(1)}px`);
      btn.style.setProperty('--my', `${((e.clientY - (r.top + r.height / 2)) * 0.3).toFixed(1)}px`);
    });
    btn.addEventListener('pointerleave', () => {
      btn.style.setProperty('--mx', '0px');
      btn.style.setProperty('--my', '0px');
    });
  });
}

if (finePointer) {
  // Glass: the light follows the cursor; the panel tilts when motion is OK.
  document.querySelectorAll('.tilt').forEach((card) => {
    let raf = 0;
    card.addEventListener('pointermove', (e) => {
      cancelAnimationFrame(raf);
      raf = requestAnimationFrame(() => {
        const r = card.getBoundingClientRect();
        const px = (e.clientX - r.left) / r.width;
        const py = (e.clientY - r.top) / r.height;
        card.style.setProperty('--mx', `${(px * 100).toFixed(1)}%`);
        card.style.setProperty('--my', `${(py * 100).toFixed(1)}%`);
        if (!reduceMotion) {
          card.classList.add('is-tilting');
          card.style.setProperty('--rx', `${((0.5 - py) * 6).toFixed(2)}deg`);
          card.style.setProperty('--ry', `${((px - 0.5) * 8).toFixed(2)}deg`);
        }
      });
    });
    card.addEventListener('pointerleave', () => {
      cancelAnimationFrame(raf);
      card.classList.remove('is-tilting');
      card.style.setProperty('--rx', '0deg');
      card.style.setProperty('--ry', '0deg');
    });
  });
}

// ---------------------------------------------------------------------------
// Count-up for the cost numbers: "$10,000s" counts from $0 to $10,000s.
// ---------------------------------------------------------------------------
function countUp(el, duration = 1.6) {
  const m = /^(\D*)([\d,]+(?:\.\d+)?)(.*)$/.exec(el.dataset.count || '');
  if (!m) return;
  const [, pre, num, post] = m;
  const target = parseFloat(num.replace(/,/g, ''));
  const decimals = (num.split('.')[1] || '').length;
  const fmt = (v) =>
    pre + v.toLocaleString('en-US', { minimumFractionDigits: decimals, maximumFractionDigits: decimals }) + post;
  const state = { v: 0 };
  el.textContent = fmt(0);
  gsap.to(state, {
    v: target,
    duration,
    ease: 'expo.out',
    onUpdate: () => (el.textContent = fmt(state.v)),
    onComplete: () => (el.textContent = el.dataset.count),
  });
}

// ---------------------------------------------------------------------------
// Scroll story (GSAP + ScrollTrigger). Skipped entirely for reduced motion:
// the page is complete and readable without it.
// ---------------------------------------------------------------------------
if (!reduceMotion) {
  gsap.registerPlugin(ScrollTrigger);
  const ease = 'expo.out';

  // ---- Hero entrance. Opacity starts just above zero so the browser still
  // counts the headline as painted immediately (keeps LCP fast).
  const heroChars = [...document.querySelectorAll('.hero-title .line-in')].flatMap(splitChars);
  gsap.from(heroChars, { yPercent: 110, rotate: 6, opacity: 0.01, duration: 1.5, ease, stagger: 0.035, delay: 0.2 });
  gsap.from('[data-hero]', { y: 28, opacity: 0.01, duration: 1.6, ease, stagger: 0.08, delay: 0.45, clearProps: 'transform' });

  // ---- Hero exit: the copy and the lens recede.
  const heroTl = gsap.timeline({
    scrollTrigger: { trigger: '.hero', start: 'top top', end: 'bottom top', scrub: 0.8 },
  });
  heroTl
    .to('.hero-inner', { y: -90, opacity: 0, ease: 'power1.in' }, 0)
    .to('.hero-foot', { opacity: 0, ease: 'none' }, 0);

  // ---- 01 The math: words light up as you read; the numbers count.
  const words = gsap.utils.toArray('.math-statement .w');
  if (words.length) {
    const css = getComputedStyle(root);
    const lit = css.getPropertyValue('--varn-text').trim();
    const dim = css.getPropertyValue('--dim').trim();
    gsap.to(words, {
      color: (_, el) => (el.classList.contains('w--hi') ? lit : dim),
      stagger: 0.1,
      ease: 'none',
      scrollTrigger: { trigger: '.math-statement', start: 'top 82%', end: 'bottom 45%', scrub: 0.6 },
    });
  }
  document.querySelectorAll('[data-count]').forEach((el, i) => {
    ScrollTrigger.create({
      trigger: el,
      start: 'top 90%',
      once: true,
      onEnter: () => gsap.delayedCall(i * 0.12, () => countUp(el)),
    });
  });

  // ---- Section headings rise in.
  gsap.utils.toArray('.section-head').forEach((head) => {
    const h = head.querySelector('.h-section');
    const words = h ? splitWords(h) : [];
    const others = [...head.children].filter((c) => c !== h && !c.hasAttribute('data-reveal'));
    const tl = gsap.timeline({ scrollTrigger: { trigger: head, start: 'top 86%' } });
    tl.from(others, { y: 30, opacity: 0, duration: 1.2, ease, stagger: 0.08 }, 0);
    if (words.length) tl.from(words, { yPercent: 115, duration: 1.4, ease, stagger: 0.07 }, 0.1);
  });

  // ---- Generic float-up reveals.
  gsap.utils.toArray('[data-reveal]').forEach((el) => {
    gsap.from(el, {
      y: 56,
      opacity: 0,
      duration: 1.6,
      ease,
      clearProps: 'transform', // hand transforms back to CSS (glass tilt)
      scrollTrigger: { trigger: el, start: 'top 90%' },
    });
  });

  gsap.to('.how-stage .stage-steel', {
    yPercent: 30,
    ease: 'none',
    scrollTrigger: { trigger: '.how', start: 'top bottom', end: 'bottom top', scrub: true },
  });

  // ---- Story: pinned. Scrolling steps through the five stages; the scene,
  // rail and text follow. Below 900 px the same thing runs with a shorter pin.
  const story = document.getElementById('story');
  if (story) {
    const steps = [...story.querySelectorAll('.story-step')];
    const scenes = [...story.querySelectorAll('.scene')];
    const dots = [...story.querySelectorAll('.rail-dot')];
    const lines = [...story.querySelectorAll('.rail-line')];
    const counter = document.getElementById('story-step');
    const n = steps.length;
    let current = -1;
    const show = (i) => {
      if (i === current) return;
      current = i;
      steps.forEach((el, k) => el.classList.toggle('is-active', k === i));
      scenes.forEach((el, k) => {
        // Re-trigger the scene's CSS animation each time it becomes active.
        if (k === i) {
          el.classList.remove('is-active');
          void el.offsetWidth;
        }
        el.classList.toggle('is-active', k === i);
      });
      dots.forEach((el, k) => {
        el.classList.toggle('is-active', k === i);
        el.classList.toggle('is-done', k < i);
      });
      if (counter) counter.textContent = `0${i + 1} / 0${n}`;
    };
    ScrollTrigger.create({
      trigger: '.story-pin',
      start: 'top top',
      end: () => `+=${Math.round(window.innerHeight * 0.75 * n)}`,
      pin: true,
      anticipatePin: 1,
      onUpdate: (self) => {
        const p = self.progress;
        show(Math.min(n - 1, Math.floor(p * n * 0.9999)));
        lines.forEach((line, k) => {
          const f = Math.min(1, Math.max(0, p * n - (k + 0.5)));
          line.firstElementChild.style.setProperty('--fill', f.toFixed(3));
        });
      },
    });
    // The device floats in as the section arrives.
    gsap.from('.story-device', {
      y: 80,
      opacity: 0,
      rotationX: 10,
      transformPerspective: 1100,
      duration: 1.6,
      ease,
      clearProps: 'transform',
      scrollTrigger: { trigger: '.story', start: 'top 70%' },
    });
  }

  // ---- Label cards float up in sequence.
  gsap.from('.label-card', {
    y: 80,
    opacity: 0,
    duration: 1.5,
    ease,
    stagger: 0.14,
    clearProps: 'transform',
    scrollTrigger: { trigger: '.label-grid', start: 'top 85%' },
  });

  // ---- Status: rows reveal one after another.
  ScrollTrigger.batch('.status-row', {
    start: 'top 92%',
    once: true,
    onEnter: (rows) =>
      gsap.from(rows, { x: -24, opacity: 0, duration: 1.2, ease, stagger: 0.06, clearProps: 'transform' }),
  });

  // ---- 04 About: the orb drifts behind the glass, so the glass bends it.
  gsap.fromTo(
    '.build-orb',
    { yPercent: 30, xPercent: 8 },
    {
      yPercent: -25,
      xPercent: -6,
      ease: 'none',
      scrollTrigger: { trigger: '.build', start: 'top bottom', end: 'bottom top', scrub: true },
    }
  );

  // ---- 05 Roadmap: the line draws itself and lights each phase.
  const track = document.querySelector('.roadmap-track');
  const phases = gsap.utils.toArray('.phase');
  gsap.fromTo(
    track,
    { '--draw': 0 },
    {
      '--draw': 1,
      ease: 'none',
      scrollTrigger: {
        trigger: track,
        start: 'top 78%',
        end: 'bottom 55%',
        scrub: 0.6,
        onUpdate: (self) =>
          phases.forEach((p, i) => p.classList.toggle('is-lit', self.progress >= (i / Math.max(1, phases.length - 1)) * 0.98)),
      },
    }
  );
  gsap.from(phases, {
    y: 50,
    opacity: 0,
    duration: 1.5,
    ease,
    stagger: 0.12,
    clearProps: 'transform',
    scrollTrigger: { trigger: track, start: 'top 84%' },
  });

  // Closing: the mark rises out of the dark above the last line.
  gsap.fromTo(
    '#outro-lens',
    { y: 80, opacity: 0.01 },
    { y: 0, opacity: 1, ease: 'none', scrollTrigger: { trigger: '.outro', start: 'top bottom', end: 'center bottom', scrub: 0.8 } }
  );
  gsap.from('.closing', {
    y: 40,
    opacity: 0,
    duration: 1.8,
    ease,
    scrollTrigger: { trigger: '.outro', start: 'top 70%' },
  });

  // Web fonts change line lengths; re-measure once they are in.
  document.fonts?.ready.then(() => ScrollTrigger.refresh());
} else {
  document.querySelectorAll('.phase').forEach((p) => p.classList.add('is-lit'));
}

// ---------------------------------------------------------------------------
// Real footage (when content.js has it) plays muted, unless motion is off.
// ---------------------------------------------------------------------------
const footage = document.querySelector('.hero-video');
if (footage) {
  if (reduceMotion) footage.controls = true;
  else footage.play().catch(() => (footage.controls = true));
}

// ---------------------------------------------------------------------------
// Lazy pieces: never on the critical path.
// ---------------------------------------------------------------------------
const idle = window.requestIdleCallback || ((fn) => setTimeout(fn, 200));
const afterLoad = (fn) => {
  if (document.readyState === 'complete') idle(fn, { timeout: 1500 });
  else window.addEventListener('load', () => idle(fn, { timeout: 1500 }), { once: true });
};
// Load a module when its element is about to scroll into view.
const whenNear = (el, load) => {
  if (!el) return;
  const io = new IntersectionObserver(
    ([entry]) => {
      if (!entry.isIntersecting) return;
      io.disconnect();
      load();
    },
    { rootMargin: '600px 0px' }
  );
  io.observe(el);
};

// Hero lens: the simulated sky, and the card that follows it.
afterLoad(() => {
  const lens = document.getElementById('lens');
  const canvas = document.getElementById('lens-canvas');
  if (!lens || !canvas) return;
  import('./hero-lens.js')
    .then(({ createLens }) => createLens({ lens, canvas, card: document.getElementById('sighting'), reduceMotion }))
    .catch((err) => console.warn('[varn] hero lens unavailable.', err));
});

// Simulated radar-style plot.
whenNear(document.getElementById('radar'), () =>
  import('./radar.js')
    .then(({ createRadar }) => createRadar({ root: document.getElementById('radar'), reduceMotion }))
    .catch((err) => console.warn('[varn] radar view unavailable.', err))
);

// Simulated sensor view.
whenNear(document.getElementById('sensor'), () =>
  import('./sensor.js')
    .then(({ createSensor }) => createSensor({ root: document.getElementById('sensor'), reduceMotion }))
    .catch((err) => console.warn('[varn] sensor view unavailable.', err))
);

// Pan-tilt mount viewer (three.js). Only hardware-accelerated WebGL 2:
// software renderers would grind the main thread, so they keep the still.
// Add ?gl=any to the URL to force it anyway (handy for testing).
function hasFastWebGL2() {
  try {
    const gl = document.createElement('canvas').getContext('webgl2');
    if (!gl) return false;
    const info = gl.getExtension('WEBGL_debug_renderer_info');
    const renderer = String(gl.getParameter(info ? info.UNMASKED_RENDERER_WEBGL : gl.RENDERER) || '');
    gl.getExtension('WEBGL_lose_context')?.loseContext();
    if (new URLSearchParams(location.search).get('gl') === 'any') return true;
    return !/swiftshader|llvmpipe|softpipe|software|basic render/i.test(renderer);
  } catch {
    return false;
  }
}

afterLoad(() => {
  const stage = document.getElementById('mount-stage');
  if (!stage || !hasFastWebGL2()) return;
  const parts = [...document.querySelectorAll('.mount-parts li')];
  whenNear(stage, () =>
    import('./mount.js')
      .then(({ createMount }) =>
        createMount({
          container: stage,
          url: new URL('models/pantilt.bin', document.baseURI).href,
          reduceMotion,
          finePointer,
          onTooSlow: () => stage.classList.remove('is-ready'),
        })
      )
      .then((mount) => {
        stage.classList.add('is-ready');
        parts.forEach((li, i) => {
          li.addEventListener('pointerenter', () => {
            li.classList.add('is-active');
            mount.setActive(i);
          });
          li.addEventListener('pointerleave', () => {
            li.classList.remove('is-active');
            mount.setActive(-1);
          });
        });
      })
      .catch((err) => console.warn('[varn] mount viewer unavailable, keeping the still.', err))
  );
});
