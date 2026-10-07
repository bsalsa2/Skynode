import { gsap } from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';

const root = document.documentElement;
const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
const finePointer = window.matchMedia('(hover: hover) and (pointer: fine)').matches;

if (!reduceMotion) root.classList.add('js-motion');

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
  gsap.from('.hero-title .line-in', { yPercent: 70, opacity: 0.01, duration: 1.8, ease, stagger: 0.12, delay: 0.25 });
  gsap.from('[data-hero]', { y: 28, opacity: 0.01, duration: 1.6, ease, stagger: 0.08, delay: 0.45, clearProps: 'transform' });

  // ---- Hero exit: the horizon rises to meet you, the moon slips away, and
  // the copy recedes.
  const heroTl = gsap.timeline({
    scrollTrigger: { trigger: '.hero', start: 'top top', end: 'bottom top', scrub: 0.8 },
  });
  heroTl
    .to('#planet', { yPercent: -9, scale: 1.08, ease: 'none' }, 0)
    .to('#moon', { yPercent: -70, ease: 'none' }, 0)
    .to('.hero-inner', { y: -90, opacity: 0, ease: 'power1.in' }, 0)
    .to('.hero-facts', { opacity: 0, ease: 'none' }, 0);

  // ---- 01 The math: words light up as you read; the numbers count.
  const words = gsap.utils.toArray('.math-statement .w');
  if (words.length) {
    gsap.to(words, {
      color: (_, el) => (el.classList.contains('w--hi') ? '#ffffff' : '#76767a'),
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
    gsap.from(head.children, {
      y: 40,
      opacity: 0,
      duration: 1.5,
      ease,
      stagger: 0.08,
      scrollTrigger: { trigger: head, start: 'top 88%' },
    });
  });

  // ---- Generic float-up reveals.
  gsap.utils.toArray('[data-reveal]:not(.step)').forEach((el) => {
    gsap.from(el, {
      y: 56,
      opacity: 0,
      duration: 1.6,
      ease,
      clearProps: 'transform', // hand transforms back to CSS (glass tilt)
      scrollTrigger: { trigger: el, start: 'top 90%' },
    });
  });

  // ---- 02 How it works: the three glass panels float up in sequence.
  gsap.from('.step', {
    y: 100,
    rotationX: 14,
    opacity: 0,
    duration: 1.8,
    ease,
    stagger: 0.14,
    transformPerspective: 1100,
    clearProps: 'transform',
    scrollTrigger: { trigger: '.steps', start: 'top 86%' },
  });
  gsap.to('.halo', {
    yPercent: 30,
    ease: 'none',
    scrollTrigger: { trigger: '.how', start: 'top bottom', end: 'bottom top', scrub: true },
  });

  // ---- 03 Status: rows reveal one after another.
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

  // Closing: a second horizon rises out of the dark under the last line.
  gsap.fromTo(
    '#outro-planet',
    { y: 260 },
    { y: 0, ease: 'none', scrollTrigger: { trigger: '.outro', start: 'top bottom', end: 'bottom bottom', scrub: 0.8 } }
  );
  gsap.from('.closing', {
    y: 40,
    opacity: 0,
    duration: 1.8,
    ease,
    scrollTrigger: { trigger: '.outro', start: 'top 70%' },
  });

  // Footer wordmark surfaces as you reach the bottom.
  gsap.from('.footer-giant', {
    yPercent: 35,
    opacity: 0,
    ease: 'none',
    scrollTrigger: { trigger: '.site-footer', start: 'top bottom', end: 'bottom bottom', scrub: 0.6 },
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

// Hero sky: stars, the aircraft pass, and the live readout.
afterLoad(() => {
  const hero = document.getElementById('top');
  const canvas = document.getElementById('sky-canvas');
  if (!canvas) return;
  import('./hero.js')
    .then(({ createHeroSky }) =>
      createHeroSky({ hero, canvas, card: document.getElementById('hud'), reduceMotion, finePointer })
    )
    .catch((err) => console.warn('[skynode] hero sky unavailable.', err));
});

// Simulated sensor view.
whenNear(document.getElementById('sensor'), () =>
  import('./sensor.js')
    .then(({ createSensor }) => createSensor({ root: document.getElementById('sensor'), reduceMotion }))
    .catch((err) => console.warn('[skynode] sensor view unavailable.', err))
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
      .catch((err) => console.warn('[skynode] mount viewer unavailable, keeping the still.', err))
  );
});
