// Page behaviour. Small on purpose: everything is readable without it.
//  - Reveals: headings, cards and diagrams fade up once as they scroll in.
//  - Hero: the tracking animation (CSS) pauses while the hero is off screen.
//  - Feed: the simulated dashboard and radar (feed.js) load near the panel
//    and only animate while it is visible.
// Visitors who turn off motion get the finished, still page.

const root = document.documentElement;
const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
if (!reduceMotion) root.classList.add('js-motion');

// ---- Hero: fade in on load, pause its animation off screen -------------------
const hero = document.querySelector('.hero');
requestAnimationFrame(() => document.querySelectorAll('[data-hero]').forEach((el) => el.classList.add('is-in')));
if (hero) {
  new IntersectionObserver(([e]) => hero.classList.toggle('is-off', !e.isIntersecting)).observe(hero);
}

// ---- Scroll reveals ----------------------------------------------------------
const revealed = document.querySelectorAll('[data-reveal]');
if (reduceMotion || !('IntersectionObserver' in window)) {
  revealed.forEach((el) => el.classList.add('is-in'));
} else {
  const io = new IntersectionObserver(
    (entries) => {
      entries.forEach((e) => {
        if (!e.isIntersecting) return;
        e.target.classList.add('is-in');
        io.unobserve(e.target);
      });
    },
    { rootMargin: '0px 0px -12% 0px' }
  );
  revealed.forEach((el) => io.observe(el));
}

// ---- Simulated dashboard -------------------------------------------------------
const feed = document.getElementById('feed');
if (feed) {
  const near = new IntersectionObserver(
    ([e]) => {
      if (!e.isIntersecting) return;
      near.disconnect();
      import('./feed.js')
        .then(({ createFeed }) => createFeed({ root: feed, reduceMotion }))
        .catch((err) => console.warn('[varn] dashboard simulation unavailable.', err));
    },
    { rootMargin: '400px 0px' }
  );
  near.observe(feed);
}

// ---- In-page links move focus too, for keyboard and screen reader users ----------
document.addEventListener('click', (e) => {
  const link = e.target.closest('a[href^="#"]');
  if (!link) return;
  const target = document.getElementById(link.getAttribute('href').slice(1));
  if (!target) return;
  if (!target.hasAttribute('tabindex')) target.setAttribute('tabindex', '-1');
  target.focus({ preventScroll: true });
});
