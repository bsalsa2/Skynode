// Mobile menu: the toggle button opens the nav links as a dropdown panel.
export function initNavMenu() {
  const nav = document.querySelector('.nav');
  const toggle = document.querySelector('.nav-toggle');
  if (!nav || !toggle) return;
  const set = (open) => {
    nav.classList.toggle('is-open', open);
    toggle.setAttribute('aria-expanded', String(open));
    toggle.setAttribute('aria-label', open ? 'Close menu' : 'Open menu');
  };
  toggle.addEventListener('click', () => set(!nav.classList.contains('is-open')));
  nav.addEventListener('click', (e) => e.target.closest('a') && set(false));
  document.addEventListener('keydown', (e) => e.key === 'Escape' && set(false));
  document.addEventListener('click', (e) => !nav.contains(e.target) && set(false));
}
