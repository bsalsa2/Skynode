import { gsap } from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';

const root = document.documentElement;
const motionQuery = window.matchMedia('(prefers-reduced-motion: reduce)');
const reduceMotion = motionQuery.matches;
const finePointer = window.matchMedia('(hover: hover) and (pointer: fine)').matches;
const clamp01 = (v) => Math.min(1, Math.max(0, v));

if (!reduceMotion) root.classList.add('js-motion');

// ---------------------------------------------------------------------------
// Liquid-glass refraction: only Chromium renders SVG filters inside
// backdrop-filter. Safari and Firefox parse the rule but drop the whole
// backdrop, so gate it on a Chromium-only API and keep plain blur elsewhere.
// ---------------------------------------------------------------------------
if (
  'userAgentData' in navigator &&
  window.CSS?.supports?.('backdrop-filter', 'url(#glass-refract) blur(1px)')
) {
  root.classList.add('has-refraction');
}

// ---------------------------------------------------------------------------
// Nav: glass pill after the hero, active section highlighting.
// ---------------------------------------------------------------------------
const header = document.getElementById('top-nav');
const hero = document.getElementById('top');

new IntersectionObserver(
  ([entry]) => header.classList.toggle('is-pinned', !entry.isIntersecting),
  { rootMargin: '-35% 0px -65% 0px' }
).observe(hero);

const navLinks = [...document.querySelectorAll('.nav-link')];
const sectionFor = new Map(
  navLinks.map((link) => [document.querySelector(link.getAttribute('href')), link])
);
// "How I build" sits under the Status link.
sectionFor.set(document.getElementById('build'), sectionFor.get(document.getElementById('status')));
const visible = new Set();
{
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
// Micro-interactions (fine pointers only, and never with reduced motion).
// ---------------------------------------------------------------------------
if (finePointer && !reduceMotion) {
  // Magnetic buttons: drift toward the cursor, spring back on leave.
  document.querySelectorAll('.magnetic').forEach((btn) => {
    const strength = 0.32;
    btn.addEventListener('pointermove', (e) => {
      const r = btn.getBoundingClientRect();
      const x = (e.clientX - (r.left + r.width / 2)) * strength;
      const y = (e.clientY - (r.top + r.height / 2)) * strength;
      btn.style.setProperty('--mx', `${x.toFixed(1)}px`);
      btn.style.setProperty('--my', `${y.toFixed(1)}px`);
    });
    btn.addEventListener('pointerleave', () => {
      btn.style.setProperty('--mx', '0px');
      btn.style.setProperty('--my', '0px');
    });
  });
}

if (finePointer) {
  // Glass cards: light sheen follows the cursor; tilt only when motion is OK.
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
          card.style.setProperty('--rx', `${((0.5 - py) * 9).toFixed(2)}deg`);
          card.style.setProperty('--ry', `${((px - 0.5) * 11).toFixed(2)}deg`);
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
// Scroll story (GSAP + ScrollTrigger). Skipped entirely for reduced motion:
// the page is complete and readable without it.
// ---------------------------------------------------------------------------
if (!reduceMotion) {
  gsap.registerPlugin(ScrollTrigger);
  const ease = 'expo.out';

  // Hero entrance. Opacity starts just above zero so the browser still
  // counts the headline as painted immediately (keeps LCP fast).
  gsap.from('[data-hero]', {
    y: 28,
    opacity: 0.01,
    duration: 1.6,
    ease,
    stagger: 0.09,
    delay: 0.1,
  });

  // The math is backwards: pin it and light the words up one by one.
  const words = gsap.utils.toArray('.math-body .w');
  gsap
    .timeline({
      scrollTrigger: {
        trigger: '.math-pin',
        start: 'top top',
        end: '+=110%',
        pin: true,
        scrub: 0.6,
      },
    })
    .to(words, { color: '#f1f4fb', stagger: 0.12, ease: 'none', duration: 0.5 })
    .to({}, { duration: 1.2 });

  // Generic float-up reveals (below the fold, so they can start fully hidden).
  gsap.utils
    .toArray(
      '.section-title, .mount, .how-note, .results-intro, .result, .build-card, .closing, .sister-card'
    )
    .forEach((el) => {
      gsap.from(el, {
        y: 48,
        opacity: 0,
        duration: 1.6,
        ease,
        clearProps: 'transform', // hand transforms back to CSS (card tilt)
        scrollTrigger: { trigger: el, start: 'top 88%' },
      });
    });

  // How it works: three glass cards float in.
  gsap.from('.card', {
    y: 90,
    rotationX: 12,
    opacity: 0,
    duration: 1.8,
    ease,
    stagger: 0.14,
    clearProps: 'transform',
    scrollTrigger: { trigger: '.cards', start: 'top 85%' },
  });

  // Status: rows reveal, the spine fills as you go.
  gsap.utils.toArray('.status-row').forEach((row) => {
    gsap.from(row.children, {
      x: (i) => (i === 0 ? 0 : -24),
      scale: (i) => (i === 0 ? 0.4 : 1),
      opacity: 0,
      duration: 1.2,
      ease,
      stagger: 0.08,
      scrollTrigger: { trigger: row, start: 'top 88%' },
    });
  });
  const timeline = document.querySelector('.timeline');
  gsap.fromTo(
    timeline,
    { '--fill': 0 },
    {
      '--fill': 1,
      ease: 'none',
      scrollTrigger: { trigger: timeline, start: 'top 70%', end: 'bottom 70%', scrub: 0.5 },
    }
  );

  // Roadmap: the connecting line draws itself and lights each phase.
  const track = document.querySelector('.roadmap-track');
  const phases = gsap.utils.toArray('.phase');
  phases.forEach((p) => p.classList.remove('is-lit'));
  gsap.fromTo(
    track,
    { '--draw': 0 },
    {
      '--draw': 1,
      ease: 'none',
      scrollTrigger: {
        trigger: track,
        start: 'top 75%',
        end: 'bottom 60%',
        scrub: 0.6,
        onUpdate: (self) => {
          phases.forEach((p, i) =>
            p.classList.toggle('is-lit', self.progress >= (i / (phases.length - 1)) * 0.98)
          );
        },
      },
    }
  );
  gsap.from('.phase-card', {
    y: 60,
    opacity: 0,
    duration: 1.6,
    ease,
    stagger: 0.12,
    scrollTrigger: { trigger: track, start: 'top 80%' },
  });

  // Web fonts change line lengths; re-measure once they are in.
  document.fonts?.ready.then(() => ScrollTrigger.refresh());
} else {
  document.querySelectorAll('.phase').forEach((p) => p.classList.add('is-lit'));
}

// ---------------------------------------------------------------------------
// Scroll story for the 3D scene: p goes 0 -> 3 as the viewport centre moves
// hero -> math -> the cards -> the mount viewer (or Status), and fade takes
// the orb out before the mount viewer arrives.
// ---------------------------------------------------------------------------
const stops = [
  document.getElementById('top'),
  document.getElementById('math'),
  document.querySelector('.cards'),
  document.getElementById('mount') || document.getElementById('status'),
];
function getStory() {
  const vh = window.innerHeight;
  const ys = stops.map((el, i) => {
    const r = el.getBoundingClientRect();
    // Centres for the first three; the last stop a little after its top edge.
    return i === 3 ? r.top + vh * 0.2 : r.top + r.height / 2;
  });
  const y = vh / 2;
  let p = 0;
  if (y >= ys[3]) p = 3;
  else {
    for (let i = 0; i < 3; i++) {
      if (y < ys[i + 1]) {
        p = i + clamp01((y - ys[i]) / (ys[i + 1] - ys[i]));
        break;
      }
    }
  }
  const fade = 1 - clamp01((p - 2.2) / 0.55);
  return { p, fade };
}

// ---------------------------------------------------------------------------
// 3D hero: lazy-loaded after the page has painted, never on the critical path.
// ---------------------------------------------------------------------------
// Only hardware-accelerated WebGL 2. Software renderers (SwiftShader,
// llvmpipe) would grind the main thread, so they get the static hero.
// Add ?gl=any to the URL to force 3D anyway (handy for testing).
const forceGL = new URLSearchParams(location.search).get('gl') === 'any';
let fastGL;
function hasFastWebGL2() {
  if (fastGL !== undefined) return fastGL;
  fastGL = detectFastWebGL2();
  return fastGL;
}
function detectFastWebGL2() {
  try {
    const gl = document.createElement('canvas').getContext('webgl2');
    if (!gl) return false;
    const info = gl.getExtension('WEBGL_debug_renderer_info');
    const renderer = String(
      gl.getParameter(info ? info.UNMASKED_RENDERER_WEBGL : gl.RENDERER) || ''
    );
    gl.getExtension('WEBGL_lose_context')?.loseContext();
    if (forceGL) return true;
    return !/swiftshader|llvmpipe|softpipe|software|basic render/i.test(renderer);
  } catch {
    return false;
  }
}

function loadScene() {
  if (!hasFastWebGL2()) {
    root.classList.add('no-webgl');
    return;
  }
  const container = reduceMotion
    ? document.getElementById('hero-visual')
    : document.getElementById('scene');
  import('./scene.js')
    .then(({ createScene }) =>
      createScene({
        container,
        reduceMotion,
        finePointer,
        getStory,
        // Device can't keep up even at low resolution: back to the static hero.
        onTooSlow: () => {
          container.classList.remove('is-ready');
          root.classList.remove('has-scene');
          root.classList.add('no-webgl');
        },
      })
    )
    .then(() => {
      container.classList.add('is-ready');
      if (!reduceMotion) root.classList.add('has-scene');
      setTimeout(() => container.classList.add('is-settled'), 1700);
    })
    .catch((err) => {
      // Anything goes wrong: the static SVG hero simply stays.
      console.warn('[skynode] 3D scene unavailable, showing static hero.', err);
      root.classList.add('no-webgl');
    });
}

// ---------------------------------------------------------------------------
// Real footage (when content.js has it) replaces the concept scene.
// ---------------------------------------------------------------------------
const heroVisual = document.getElementById('hero-visual');
const footage = heroVisual.querySelector('.hero-video');
if (footage) {
  if (reduceMotion) footage.controls = true;
  else footage.play().catch(() => (footage.controls = true));
}

// ---------------------------------------------------------------------------
// Pan-tilt mount viewer: loads when it's about to scroll into view.
// ---------------------------------------------------------------------------
function watchMount() {
  const stage = document.getElementById('mount-stage');
  if (!stage || !hasFastWebGL2()) return;
  const parts = [...document.querySelectorAll('.mount-parts li')];
  const io = new IntersectionObserver(
    ([entry]) => {
      if (!entry.isIntersecting) return;
      io.disconnect();
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
        .catch((err) => console.warn('[skynode] mount viewer unavailable, keeping the still.', err));
    },
    { rootMargin: '600px 0px' }
  );
  io.observe(stage);
}

const idle = window.requestIdleCallback || ((fn) => setTimeout(fn, 200));
const afterLoad = (fn) => {
  if (document.readyState === 'complete') idle(fn, { timeout: 1500 });
  else window.addEventListener('load', () => idle(fn, { timeout: 1500 }), { once: true });
};
if (!footage) afterLoad(loadScene);
afterLoad(watchMount);
