// Turns src/content.js into static HTML at build time (see vite.config.js).
// The page ships as plain HTML, so it is readable before any JavaScript runs.

const esc = (s) =>
  String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');

const isExternal = (href) => /^https?:\/\//.test(href);
const linkAttrs = (href) =>
  isExternal(href) ? ` href="${esc(href)}" target="_blank" rel="noopener"` : ` href="${esc(href)}"`;

// Small line-art glyphs for the three How-it-works cards, keyed by title.
const GLYPHS = {
  sense:
    '<circle cx="28" cy="28" r="22" /><circle cx="28" cy="28" r="13" /><circle cx="28" cy="28" r="4" class="accent-fill" /><path d="M28 2v6M28 48v6M2 28h6M48 28h6" />',
  track:
    '<rect x="10" y="10" width="36" height="36" rx="2" stroke-dasharray="3 4" /><path d="M4 16V4h12M40 4h12v12M52 40v12H40M16 52H4V40" class="accent" /><circle cx="34" cy="22" r="5" class="accent" />',
  log:
    '<path d="M8 12h40M8 24h40M8 36h28M8 48h18" /><circle cx="46" cy="44" r="6" class="accent" /><path d="M46 41v3l2 2" class="accent" />',
};
const glyph = (title) =>
  `<svg class="card-glyph" viewBox="0 0 56 56" aria-hidden="true">${GLYPHS[String(title).toLowerCase()] || GLYPHS.sense}</svg>`;

const STATUS_KINDS = { DONE: 'done', 'IN PROGRESS': 'progress', NEXT: 'next' };

const statusIcon = (kind) => {
  if (kind === 'done')
    return '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M3.5 8.5l3 3 6-7" /></svg>';
  if (kind === 'progress')
    return '<svg viewBox="0 0 16 16" aria-hidden="true"><circle cx="8" cy="8" r="5.5" class="track" /><path d="M8 2.5a5.5 5.5 0 0 1 5.5 5.5" class="arc" /></svg>';
  return '<svg viewBox="0 0 16 16" aria-hidden="true"><circle cx="8" cy="8" r="4.5" /></svg>';
};

// Static stand-in for the 3D scene: shown before WebGL loads, when WebGL is
// unavailable, and as the poster image for the 3D canvas.
const heroFallback = () => `
<svg class="hero-fallback" viewBox="0 0 600 600" role="img" aria-labelledby="fallback-title">
  <title id="fallback-title">Concept illustration: a faceted glass sensor orb with an amber targeting ring locked on a small aircraft.</title>
  <defs>
    <radialGradient id="fb-orb" cx="38%" cy="32%" r="70%">
      <stop offset="0" stop-color="#dfe8ff" stop-opacity=".55" />
      <stop offset=".35" stop-color="#6f83b8" stop-opacity=".22" />
      <stop offset=".8" stop-color="#1a2547" stop-opacity=".35" />
      <stop offset="1" stop-color="#9fb4ff" stop-opacity=".5" />
    </radialGradient>
    <radialGradient id="fb-glow" cx="50%" cy="50%" r="50%">
      <stop offset="0" stop-color="#3b5bb5" stop-opacity=".35" />
      <stop offset="1" stop-color="#3b5bb5" stop-opacity="0" />
    </radialGradient>
  </defs>
  <circle cx="300" cy="300" r="280" fill="url(#fb-glow)" />
  <circle cx="300" cy="300" r="150" fill="url(#fb-orb)" stroke="rgba(220,230,255,.35)" />
  <g fill="none" stroke="rgba(220,230,255,.18)">
    <path d="M300 150 L390 230 L300 300 L210 230 Z M390 230 L440 320 L300 300 M210 230 L160 320 L300 300 M160 320 L230 430 L300 300 L370 430 L440 320 M230 430 L300 450 L370 430" />
  </g>
  <circle cx="318" cy="292" r="22" fill="#0b1124" stroke="rgba(240,190,90,.5)" />
  <circle cx="324" cy="288" r="5" fill="#f0be5a" />
  <g transform="translate(470 150) rotate(-24)">
    <path d="M0 -16 L3 -6 L18 2 L18 5 L3 2 L2 12 L7 16 L7 18 L0 16 L-7 18 L-7 16 L-2 12 L-3 2 L-18 5 L-18 2 L-3 -6 Z" fill="rgba(225,234,255,.85)" />
  </g>
  <g fill="none" stroke="#f0be5a" stroke-width="1.5">
    <circle cx="470" cy="150" r="34" stroke-opacity=".9" />
    <path d="M470 108v10M470 182v10M428 150h10M502 150h10" />
  </g>
  <path d="M340 270 L440 172" stroke="rgba(240,190,90,.35)" stroke-dasharray="3 6" />
</svg>`;

// Real footage, once it exists (see hero.footage in content.js). main.js
// starts playback only for visitors who haven't turned off motion.
const heroVideo = (f) => `
<video class="hero-video" muted loop playsinline preload="metadata"${f.poster ? ` poster="${esc(f.poster)}"` : ''} aria-label="${esc(f.caption)}">
  <source src="${esc(f.video)}" />
</video>`;

// Pan-tilt mount: a still image first, replaced by a live 3D view (mount.js).
const mountBlock = (m) => `
      <figure class="mount glass" id="mount" data-reveal>
        <div class="mount-stage" id="mount-stage">
          <img class="mount-still" src="./models/pantilt-still.webp" width="900" height="760" loading="lazy" decoding="async"
            alt="3D render of the Skynode pan-tilt mount from its CAD files: a base holding the pan servo, a yoke on top, and a camera arm between the yoke's uprights." />
        </div>
        <figcaption class="mount-info">
          <p class="mono mount-label"><span class="mount-dot" aria-hidden="true"></span>${esc(m.label)}</p>
          <ul class="mount-parts">
            ${m.parts
              .map(
                (p, i) => `<li data-part="${i}"><span class="mono mount-part-name">${esc(p.name)}</span><p>${esc(p.text)}</p></li>`
              )
              .join('')}
          </ul>
          <p class="mount-caption">${esc(m.caption)}</p>
        </figcaption>
      </figure>`;

// Accuracy results: rendered only once there are measured numbers.
const resultsSection = (r) => {
  if (!r || !Array.isArray(r.items) || r.items.length === 0) return '';
  return `
  <section class="results section" id="results" aria-labelledby="results-title">
    <div class="wrap wrap--narrow">
      <h2 class="section-title display" id="results-title" data-reveal>${esc(r.heading)}</h2>
      ${r.intro ? `<p class="results-intro" data-reveal>${esc(r.intro)}</p>` : ''}
      <dl class="results-grid">
        ${r.items
          .map(
            (it) => `
        <div class="result glass" data-reveal>
          <dt class="mono">${esc(it.label)}</dt>
          <dd class="result-value display">${esc(it.value)}</dd>
          ${it.note ? `<dd class="result-note">${esc(it.note)}</dd>` : ''}
        </div>`
          )
          .join('')}
      </dl>
      <p class="results-source mono">${esc(r.source)}</p>
    </div>
  </section>`;
};

const sisterCard = (s) => `
  <section class="sister" aria-label="${esc(s.label)}: ${esc(s.name)}">
    <div class="wrap">
      <a class="sister-card glass glass--refract tilt"${linkAttrs(s.href)} data-reveal>
        <span class="card-sheen" aria-hidden="true"></span>
        <span class="sister-mark" aria-hidden="true">
          <svg viewBox="0 0 48 48"><circle cx="24" cy="24" r="9" /><path d="M24 4v6M24 38v6M4 24h6M38 24h6M9.9 9.9l4.2 4.2M33.9 33.9l4.2 4.2M9.9 38.1l4.2-4.2M33.9 14.1l4.2-4.2" /></svg>
        </span>
        <span class="sister-text">
          <span class="mono sister-label">${esc(s.label)}</span>
          <span class="sister-name display">${esc(s.name)}</span>
          ${s.description ? `<span class="sister-desc">${esc(s.description)}</span>` : ''}
        </span>
        <span class="sister-cta">
          <span class="mono">${esc(s.linkLabel)}</span>
          <svg viewBox="0 0 16 16" aria-hidden="true"><path d="M5 11L11 5M6 5h5v5" /></svg>
        </span>
      </a>
    </div>
  </section>`;

// GoatCounter visit counter, only when content.js has a code.
const counter = (c) => {
  const code = c.analytics && c.analytics.goatcounter;
  return code
    ? `
    <script data-goatcounter="https://${esc(code)}.goatcounter.com/count" async src="https://gc.zgo.at/count.js"></script>`
    : '';
};

export function renderHead(c) {
  const { title, description, url } = c.meta;
  const image = new URL('og-image.png', url).href;
  return `${counter(c)}
    <title>${esc(title)}</title>
    <meta name="description" content="${esc(description)}" />
    <link rel="canonical" href="${esc(url)}" />
    <meta property="og:type" content="website" />
    <meta property="og:site_name" content="Skynode" />
    <meta property="og:title" content="${esc(title)}" />
    <meta property="og:description" content="${esc(description)}" />
    <meta property="og:url" content="${esc(url)}" />
    <meta property="og:image" content="${esc(image)}" />
    <meta property="og:image:width" content="1200" />
    <meta property="og:image:height" content="630" />
    <meta property="og:image:alt" content="Skynode: Drones are cheap. Detecting them isn't." />
    <meta name="twitter:card" content="summary_large_image" />
    <meta name="twitter:title" content="${esc(title)}" />
    <meta name="twitter:description" content="${esc(description)}" />
    <meta name="twitter:image" content="${esc(image)}" />`;
}

export function renderBody(c) {
  const { nav, hero, math, how, status, results, build, roadmap, sister, footer } = c;
  const footage = hero.footage && hero.footage.video ? hero.footage : null;

  const navLinks = nav.links
    .map((l) => `<li><a class="nav-link" href="${esc(l.href)}">${esc(l.label)}</a></li>`)
    .join('');

  const mathWords = math.body
    .split(/\s+/)
    .map((w) => `<span class="w">${esc(w)}</span>`)
    .join(' ');

  const steps = how.steps
    .map(
      (s) => `
        <li class="card glass glass--refract tilt" data-reveal>
          <span class="card-sheen" aria-hidden="true"></span>
          <div class="card-top">
            <span class="mono card-num">${esc(s.number)}</span>
            ${glyph(s.title)}
          </div>
          <h3 class="card-title">${esc(s.title)}</h3>
          <p>${esc(s.body)}</p>
        </li>`
    )
    .join('');

  const statusRows = status.items
    .map((it) => {
      const kind = STATUS_KINDS[String(it.label).trim().toUpperCase()] || 'next';
      return `
        <li class="status-row status-row--${kind}" data-reveal>
          <span class="status-node" aria-hidden="true">${statusIcon(kind)}</span>
          <div class="status-body glass">
            <span class="pill pill--${kind} mono">${esc(it.label)}</span>
            <p>${esc(it.text)}</p>
          </div>
        </li>`;
    })
    .join('');

  const phases = roadmap.phases
    .map(
      (p, i) => `
        <li class="phase is-lit" data-phase="${i}">
          <span class="phase-node" aria-hidden="true"></span>
          <article class="phase-card glass" data-reveal>
            <p class="mono phase-label">${esc(p.phase)}</p>
            <h3 class="phase-title">${esc(p.title)}</h3>
            <p>${esc(p.body)}</p>
          </article>
        </li>`
    )
    .join('');

  // Each sentence of the headline on its own line.
  const headline = hero.headline
    .split(/(?<=[.!?])\s+/)
    .map((line) => `<span class="line">${esc(line)}</span>`)
    .join(' ');

  const facts = hero.facts.map((f) => `<li>${esc(f)}</li>`).join('');

  return `
<a class="skip-link" href="#main">Skip to content</a>

<svg class="svg-defs" width="0" height="0" aria-hidden="true" focusable="false">
  <filter id="glass-refract" x="0%" y="0%" width="100%" height="100%" color-interpolation-filters="sRGB">
    <feTurbulence type="fractalNoise" baseFrequency="0.008 0.012" numOctaves="2" seed="7" result="noise" />
    <feGaussianBlur in="noise" stdDeviation="2" result="soft" />
    <feDisplacementMap in="SourceGraphic" in2="soft" scale="38" xChannelSelector="R" yChannelSelector="G" />
  </filter>
</svg>

<div class="sky" aria-hidden="true">
  <div class="sky-glow sky-glow--a"></div>
  <div class="sky-glow sky-glow--b"></div>
  <div class="sky-grid"></div>
</div>

<div class="scene" id="scene" aria-hidden="true"></div>

<header class="site-header" id="top-nav">
  <nav class="nav glass" aria-label="Primary">
    <a class="brand" href="#top">
      <svg class="brand-mark" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="8" /><path d="M12 1v5M12 18v5M1 12h5M18 12h5" /><circle cx="12" cy="12" r="2" class="dot" /></svg>
      <span>${esc(nav.brand)}</span>
    </a>
    <ul class="nav-links">${navLinks}</ul>
  </nav>
</header>

<main id="main" tabindex="-1">
  <section class="hero" id="top" aria-labelledby="hero-title">
    <div class="hero-visual${footage ? ' hero-visual--footage' : ''}" id="hero-visual"${footage ? ' data-footage' : ''}>
      ${footage ? heroVideo(footage) : heroFallback()}
    </div>
    <div class="hero-inner wrap">
      <p class="eyebrow mono" data-hero>${esc(hero.eyebrow)}</p>
      <h1 class="hero-title display" id="hero-title" data-hero>${headline}</h1>
      <p class="hero-sub" data-hero>${esc(hero.sub)}</p>
      <div class="hero-actions" data-hero>
        <a class="btn btn--primary magnetic"${linkAttrs(hero.primary.href)}>
          <span>${esc(hero.primary.label)}</span>
          <svg viewBox="0 0 16 16" aria-hidden="true"><path d="M5 11L11 5M6 5h5v5" /></svg>
        </a>
        <a class="btn btn--ghost magnetic" href="${esc(hero.secondary.href)}">
          <span>${esc(hero.secondary.label)}</span>
          <svg viewBox="0 0 16 16" aria-hidden="true"><path d="M8 3v10M4 9l4 4 4-4" /></svg>
        </a>
      </div>
      ${hero.goal ? `<p class="hero-goal" data-hero>${esc(hero.goal)}</p>` : ''}
      <ul class="hero-facts mono" data-hero>${facts}</ul>
    </div>
    <p class="hero-caption mono" id="hero-caption">${esc(footage ? footage.caption : hero.caption)}</p>
  </section>

  <section class="math" id="math" aria-labelledby="math-title">
    <div class="math-pin wrap">
      <h2 class="section-label mono" id="math-title"><span aria-hidden="true">02</span>${esc(math.heading)}</h2>
      <p class="math-body display">${mathWords}</p>
    </div>
  </section>

  <section class="how section" id="how" aria-labelledby="how-title">
    <div class="wrap">
      <h2 class="section-title display" id="how-title" data-reveal><span class="mono section-num" aria-hidden="true">03</span>${esc(how.heading)}</h2>
      <ol class="cards">${steps}</ol>
      ${how.mount ? mountBlock(how.mount) : ''}
      <p class="how-note glass" data-reveal>
        <span class="mono how-note-tag" aria-hidden="true">ADS-B</span>
        ${esc(how.note)}
      </p>
    </div>
  </section>

  <section class="status section" id="status" aria-labelledby="status-title">
    <div class="wrap wrap--narrow">
      <h2 class="section-title display" id="status-title" data-reveal><span class="mono section-num" aria-hidden="true">04</span>${esc(status.heading)}</h2>
      <ol class="timeline">${statusRows}</ol>
    </div>
  </section>

  ${resultsSection(results)}
  <section class="build section" id="build" aria-labelledby="build-title">
    <div class="wrap wrap--narrow">
      <figure class="build-card glass glass--refract" data-reveal>
        <h2 class="mono build-label" id="build-title">${esc(build.heading)}</h2>
        <blockquote class="build-quote"><p>${esc(build.body)}</p></blockquote>
        ${
          build.quote
            ? `<figcaption class="build-motto"><p>&ldquo;${esc(build.quote)}&rdquo;</p>${
                build.signature ? `<span class="mono">${esc(build.signature)}</span>` : ''
              }</figcaption>`
            : ''
        }
      </figure>
    </div>
  </section>

  <section class="roadmap section" id="roadmap" aria-labelledby="roadmap-title">
    <div class="wrap">
      <h2 class="section-title display" id="roadmap-title" data-reveal><span class="mono section-num" aria-hidden="true">05</span>${esc(roadmap.heading)}</h2>
      <div class="roadmap-track">
        <span class="roadmap-line" aria-hidden="true"><span class="roadmap-line-fill"></span></span>
        <ol class="phases">${phases}</ol>
      </div>
      <p class="closing display" data-reveal>${esc(roadmap.closing)}</p>
    </div>
  </section>
  ${sister ? sisterCard(sister) : ''}
</main>

${siteFooter(footer)}`;
}

const BRAND_MARK =
  '<svg class="brand-mark" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="8" /><path d="M12 1v5M12 18v5M1 12h5M18 12h5" /><circle cx="12" cy="12" r="2" class="dot" /></svg>';

function siteFooter(footer, { from = 'home' } = {}) {
  const links = footer.links
    .filter((l) => !(from === 'privacy' && l.href.includes('privacy.html')))
    .map((l) => `<li><a class="u-link"${linkAttrs(l.href)}>${esc(l.label)}</a></li>`)
    .join('');
  return `
<footer class="site-footer">
  <div class="wrap footer-inner">
    <p class="brand brand--footer">
      ${BRAND_MARK}
      <span>${esc(footer.brand)}</span>
    </p>
    <ul class="footer-links">
      ${links}
      <li><span class="mono footer-k">${esc(footer.contactLabel)}</span> <a class="u-link" href="mailto:${esc(footer.email)}">${esc(footer.email)}</a></li>
    </ul>
  </div>
</footer>`;
}

// ---- Privacy page (privacy.html) -------------------------------------------
export function renderPrivacyHead(c) {
  const url = new URL('privacy.html', c.meta.url).href;
  return `${counter(c)}
    <title>${esc(c.privacy.title)} | Skynode</title>
    <meta name="description" content="${esc(c.privacy.intro)}" />
    <link rel="canonical" href="${esc(url)}" />`;
}

export function renderPrivacyBody(c) {
  const p = c.privacy;
  const on = !!(c.analytics && c.analytics.goatcounter);
  const sections = p.sections
    .filter((s) => on || !s.onlyWithAnalytics)
    .map((s) => (on && s.textWithAnalytics ? { ...s, text: s.textWithAnalytics } : s))
    .map(
      (s) => `
        <section class="legal-section">
          <h2 class="mono">${esc(s.heading)}</h2>
          <p>${esc(s.text)}${
            s.link ? ` <a class="u-link"${linkAttrs(s.link.href)}>${esc(s.link.label)}</a>.` : ''
          }</p>
        </section>`
    )
    .join('');
  return `
<a class="skip-link" href="#main">Skip to content</a>
<div class="sky" aria-hidden="true">
  <div class="sky-glow sky-glow--a"></div>
  <div class="sky-glow sky-glow--b"></div>
  <div class="sky-grid"></div>
</div>

<header class="site-header is-pinned">
  <nav class="nav glass" aria-label="Primary">
    <a class="brand" href="./">
      ${BRAND_MARK}
      <span>${esc(c.nav.brand)}</span>
    </a>
    <ul class="nav-links">${c.nav.links
      .map((l) => `<li><a class="nav-link" href="./${esc(l.href)}">${esc(l.label)}</a></li>`)
      .join('')}</ul>
  </nav>
</header>

<main id="main" class="legal" tabindex="-1">
  <div class="wrap wrap--narrow">
    <article class="legal-card glass">
      <p class="mono legal-updated">Updated ${esc(p.updated)}</p>
      <h1 class="display legal-title">${esc(p.title)}</h1>
      <p class="legal-intro">${esc(on && p.introWithAnalytics ? p.introWithAnalytics : p.intro)}</p>
      ${sections}
      <section class="legal-section">
        <h2 class="mono">${esc(c.footer.contactLabel)}</h2>
        <p>${esc(p.contactText)} <a class="u-link" href="mailto:${esc(c.footer.email)}">${esc(c.footer.email)}</a>.</p>
      </section>
    </article>
  </div>
</main>
${siteFooter(c.footer, { from: 'privacy' })}`;
}
