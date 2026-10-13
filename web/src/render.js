// Turns src/content.js into static HTML at build time (see vite.config.js).
// The page ships as plain HTML, so it is readable before any JavaScript runs.
//
// Layout: the approved homepage design (docs/design/home-mockup.webp), in the
// Varn brand system (brand/). Hero, how it works, test results, the road
// ahead, footer. Everything simulated is labelled SAMPLE.
//
// Image paths are written as plain URLs; Vite fingerprints and bundles them
// because the content plugin runs before its HTML processing.

import { MARK_PATH, MARK_SMALL_PATH, MARK_VIEWBOX, WORDMARK_PATH, WORDMARK_VIEWBOX } from './logo.js';

const HERO_SKY = './src/assets/hero-sky.webp';
const FEED_SKY = './src/assets/feed-sky.webp';

const esc = (s) =>
  String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');

const linkAttrs = (href) =>
  /^https?:/.test(href) ? ` href="${esc(href)}" target="_blank" rel="noopener"` : ` href="${esc(href)}"`;

// ---- Brand ---------------------------------------------------------------------

// The Varn mark (brand/varn_mark.svg). Below 24 px wide it uses the small mark.
const mark = (width, cls = 'mark') =>
  `<svg class="${cls}" viewBox="${MARK_VIEWBOX}" aria-hidden="true"><path d="${width < 24 ? MARK_SMALL_PATH : MARK_PATH}"/></svg>`;

// VARN in Space Grotesk, as outlines, so it never depends on a loaded font.
const wordmark = (cls = 'wordmark') =>
  `<svg class="${cls}" viewBox="${WORDMARK_VIEWBOX}" aria-hidden="true"><path d="${WORDMARK_PATH}"/></svg>`;

const lockup = (cls) => `<span class="lockup ${cls}">${mark(48)}${wordmark()}</span>`;

// ---- Icons (24 px line icons, drawn for this site) --------------------------------

const ICONS = {
  arrow: '<path d="M5 12h14M13 6l6 6-6 6"/>',
  eye: '<path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/>',
  brain:
    '<path d="M12 4.5A2.5 2.5 0 0 0 9.5 2 2.5 2.5 0 0 0 7 4.5v.3A3 3 0 0 0 4.5 8a3 3 0 0 0 .3 5.5A3 3 0 0 0 8 18.4 2.5 2.5 0 0 0 12 20zM12 4.5A2.5 2.5 0 0 1 14.5 2 2.5 2.5 0 0 1 17 4.5v.3A3 3 0 0 1 19.5 8a3 3 0 0 1-.3 5.5 3 3 0 0 1-3.2 4.9A2.5 2.5 0 0 1 12 20"/><path d="M8.5 9.5c1 0 1.8.6 2 1.5M15.5 9.5c-1 0-1.8.6-2 1.5M8.5 14.5c.8 0 1.6-.3 2-1M15.5 14.5c-.8 0-1.6-.3-2-1"/>',
  shield: '<path d="M12 3l7 3v5.5c0 4.3-3 8-7 9.5-4-1.5-7-5.2-7-9.5V6z"/><path d="M9 12l2 2 4-4.5"/>',
  crosshair: '<circle cx="12" cy="12" r="7.5"/><path d="M12 2v5M12 17v5M2 12h5M17 12h5"/>',
  plane:
    '<path d="M12 2.5c.8 0 1.4.7 1.4 1.5v5.3l7.1 4.1v1.9l-7.1-2.1v4.4l2 1.5v1.4L12 19.6l-3.4.9v-1.4l2-1.5v-4.4l-7.1 2.1v-1.9l7.1-4.1V4c0-.8.6-1.5 1.4-1.5z" transform="rotate(45 12 12)"/>',
  database:
    '<ellipse cx="12" cy="5.5" rx="7.5" ry="3"/><path d="M4.5 5.5v13c0 1.7 3.4 3 7.5 3s7.5-1.3 7.5-3v-13"/><path d="M4.5 12c0 1.7 3.4 3 7.5 3s7.5-1.3 7.5-3"/>',
};
const icon = (name, cls = 'icon') =>
  `<svg class="${cls}" viewBox="0 0 24 24" aria-hidden="true">${ICONS[name] || ''}</svg>`;

const GITHUB =
  '<svg class="icon-gh" viewBox="0 0 16 16" aria-hidden="true"><path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.01 8.01 0 0 0 16 8c0-4.42-3.58-8-8-8z"/></svg>';

const button = (b, cls) =>
  `<a class="btn ${cls}"${linkAttrs(b.href)}><span>${esc(b.label)}</span>${icon('arrow', 'btn-arrow')}</a>`;

// ---- Header --------------------------------------------------------------------

function siteHeader(c, { home = true } = {}) {
  const pre = home ? '' : './';
  const links = c.nav.links
    .map((l, i) => {
      const href = l.href.startsWith('#') ? `${pre}${l.href}` : l.href;
      const current = home && i === 0 ? ' aria-current="page"' : '';
      return `<li><a class="nav-link"${linkAttrs(href)}${current}>${esc(l.label)}</a></li>`;
    })
    .join('');
  return `
<header class="site-header">
  <div class="wrap header-inner">
    <a class="brand" href="${home ? '#top' : './'}" aria-label="${esc(c.nav.brand)}, home">${lockup('lockup--header')}</a>
    <nav class="nav" aria-label="Primary"><ul class="nav-links">${links}</ul></nav>
    <a class="btn-github"${linkAttrs(c.nav.github.href)}>${GITHUB}<span>${esc(c.nav.github.label)}</span></a>
  </div>
</header>`;
}

// ---- Hero ----------------------------------------------------------------------

// The hero photo and its tracking overlay share the mockup's coordinates
// (1024 x 462), so the frame always sits on the drone at any screen size.
// The drone is part of the photo: an illustration, labelled SAMPLE.
const TRACK =
  'M65 287 C135.2 285 370.2 284.7 451 276 C531.8 267.3 525.5 246.7 550 235 C574.5 223.3 576.2 218.5 598 206 C619.8 193.5 652.7 170.8 681 160 C709.3 149.2 748.2 144.7 768 141';
const TRACK_DOTS = [
  [451, 276],
  [550, 235],
  [598, 206],
  [681, 160],
];

function heroScene(h) {
  const dots = TRACK_DOTS.map(([x, y], i) => `<circle class="track-dot" style="--i:${i}" cx="${x}" cy="${y}" r="1.7"/>`).join('');
  return `
    <svg class="hero-scene" viewBox="0 0 1024 462" preserveAspectRatio="xMaxYMid slice" aria-hidden="true">
      <image href="${HERO_SKY}" width="1024" height="462" preserveAspectRatio="none"/>
      <g class="hero-hud">
        <path class="hud-line hud-line--v" d="M780 0V462"/>
        <path class="hud-line hud-line--h" d="M656 190H1004"/>
        <path class="hud-grid" d="M656 136H960M656 244H960M656 136V244M960 136V244"/>
        <defs>
          <linearGradient id="track-fade" gradientUnits="userSpaceOnUse" x1="65" y1="0" x2="470" y2="0">
            <stop offset="0" stop-color="#f4f3ef" stop-opacity="0"/>
            <stop offset="1" stop-color="#f4f3ef" stop-opacity=".8"/>
          </linearGradient>
        </defs>
        <path class="track" pathLength="1" stroke="url(#track-fade)" d="${TRACK}"/>
        ${dots}
        <circle class="track-end" cx="768" cy="141" r="2.6"/>
        <g class="hud-frame">
          <path d="M741 170v-10h10M815 160h10v10M825 210v10h-10M751 220h-10v-10"/>
          <text x="741" y="231">${esc(h.trackLabel)}</text>
        </g>
      </g>
    </svg>`;
}

// "Watch the sky." -> the last word in steel blue.
function headline(text) {
  const words = esc(text).split(' ');
  const last = words.pop();
  return `${words.join(' ')} <span class="accent">${last}</span>`;
}

function hero(c) {
  const h = c.hero;
  const facts = h.facts.map((f) => `<span>${esc(f)}</span>`).join('');
  return `
  <section class="hero" id="top" aria-labelledby="hero-title">
    ${heroScene(h)}
    <div class="hero-shade" aria-hidden="true"></div>
    ${siteHeader(c)}
    <div class="wrap hero-body">
      <div class="hero-copy">
        <p class="eyebrow eyebrow--hero" data-hero>${esc(h.eyebrow)}</p>
        <h1 class="hero-title" id="hero-title" data-hero>${headline(h.headline)}</h1>
        <p class="hero-sub" data-hero>${esc(h.sub)}</p>
        <div class="hero-actions" data-hero>
          ${button(h.primary, 'btn--solid')}
          ${button(h.secondary, 'btn--ghost')}
        </div>
      </div>
      <div class="hero-foot" data-hero>
        <p class="hero-status"><span class="status-dot" aria-hidden="true"></span><span class="hero-stage">${esc(h.stage)}</span><span class="sep" aria-hidden="true">|</span><span class="hero-facts">${facts}</span></p>
        <p class="hero-tagline">${h.tagline.map(esc).join('<br />')}</p>
      </div>
    </div>
  </section>`;
}

// ---- How it works ----------------------------------------------------------------

// Feed coordinates follow the mockup's camera view (335 x 223).
const FEED_TRACKS = [
  'M35 193 C45 187.2 65 179.2 80 170 C95 160.8 108.7 148.3 125 138 C141.3 127.7 165.5 113.5 178 108',
  'M170 175 C180.8 169.2 199.7 163.8 215 155 C230.3 146.2 247.8 133.7 262 122 C276.2 110.3 287.8 97.8 300 85 C312.2 72.2 326.7 54.2 335 45',
];
const FEED_DOTS = [
  [80, 170],
  [125, 138],
  [215, 155],
  [262, 122],
  [300, 85],
];
const DRONE_SVG =
  '<g class="obj-drone"><path d="M-7 -1.5h14M-4 -1.5v2.5h8v-2.5"/><path d="M-11 -3.5h7M4 -3.5h7"/><circle cx="-7" cy="1.6" r=".9" class="light"/><circle cx="7" cy="1.6" r=".9" class="light"/></g>';
const PLANE_SVG =
  '<g class="obj-plane"><path d="M-15 0c3-1.3 20-1.3 26-.6 2 .2 3.6.6 3.6.9s-1.6.7-3.6.9c-6 .7-23 .7-26-.6z"/><path d="M-2-.4 6-6h2.4L4-.4zM-2 .4 6 5.5h2.4L4 .4zM-13-.3-15.5-4h1.8l3.6 3.6z"/></g>';

function feedPanel(p) {
  const objects = p.objects
    .map(
      (o) => `
              <li class="obj obj--${esc(o.kind)}"><span class="obj-dot" aria-hidden="true"></span><span class="obj-name">${esc(o.name)}</span><span class="obj-val" data-obj="${esc(o.kind)}">${esc(o.value)}</span></li>`
    )
    .join('');
  const tracks = FEED_TRACKS.map((d, i) => `<path class="feed-track" pathLength="1" style="--i:${i}" d="${d}"/>`).join('');
  const dots = FEED_DOTS.map(([x, y]) => `<circle class="feed-dot" cx="${x}" cy="${y}" r="1.4"/>`).join('');
  return `
      <figure class="panel" id="feed" data-reveal>
        <figcaption class="sr-only">${esc(p.feedLabel)}: a simulated detection dashboard. Every value in it is made up.</figcaption>
        <div class="panel-head">
          ${lockup('lockup--panel')}
          <span class="panel-live">${esc(p.feedLabel)}<span class="live-dot" aria-hidden="true"></span></span>
        </div>
        <div class="panel-body">
          <div class="feed">
            <svg class="feed-view" viewBox="0 0 335 223" preserveAspectRatio="xMidYMid slice" aria-hidden="true">
              <image href="${FEED_SKY}" width="335" height="223" preserveAspectRatio="none"/>
              <path class="feed-grid" d="M0 75H335M0 150H335M84 0V223M168 0V223M252 0V223M0 68H335"/>
              ${tracks}
              ${dots}
              <circle class="feed-node" cx="178" cy="108" r="2.6"/>
              <g class="det det--drone" data-det="drone" transform="translate(106 64)">
                <rect class="det-box" x="-17" y="-15" width="34" height="31"/>
                <g class="det-tag"><rect x="-17" y="-34" width="34" height="15"/><text x="-12.5" y="-23">Drone</text></g>
                <text class="det-conf" x="19" y="-23" data-conf="drone">0.87</text>
                ${DRONE_SVG}
              </g>
              <g class="det det--plane" data-det="plane" transform="translate(229 79)">
                <rect class="det-box" x="-24" y="-15" width="48" height="30"/>
                <text class="det-name" x="-21" y="-20">Plane <tspan data-conf="plane">0.96</tspan></text>
                ${PLANE_SVG}
              </g>
              <g class="obj-far" transform="translate(40 116)"><path d="M-4 0h8M-2-1.2h4"/></g>
            </svg>
            <p class="feed-bar">${p.readouts.map((r) => `<span>${esc(r)}</span>`).join('')}</p>
          </div>
          <div class="panel-side">
            <div class="side-card">
              <p class="side-title">${esc(p.objectsLabel)}</p>
              <ul class="objects">${objects}
              </ul>
            </div>
            <div class="side-card radar-card">
              <canvas class="radar" aria-hidden="true"></canvas>
              <span class="compass compass--n">N</span><span class="compass compass--e">E</span><span class="compass compass--s">S</span><span class="compass compass--w">W</span>
            </div>
          </div>
        </div>
        <p class="panel-note">${esc(p.feedNote)}</p>
      </figure>`;
}

function project(c) {
  const p = c.project;
  const steps = p.steps
    .map(
      (s, i) => `
          <li class="step" style="--i:${i}" data-reveal>
            ${icon(s.icon, 'icon step-icon')}
            <h3 class="step-title">${esc(s.title)}</h3>
            <p class="step-text">${esc(s.text)}</p>
          </li>`
    )
    .join('');
  return `
  <section class="project" id="project" aria-labelledby="project-title">
    <div class="wrap project-grid">
      <div class="project-copy">
        <p class="eyebrow" data-reveal>${esc(p.kicker)}</p>
        <h2 class="h2" id="project-title" data-reveal>${p.heading.map(esc).join('<br />')}</h2>
        <p class="body" data-reveal>${esc(p.body)}</p>
        <ul class="steps">${steps}
        </ul>
      </div>
      ${feedPanel(p)}
    </div>
  </section>`;
}

// ---- Test results ----------------------------------------------------------------

function results(c) {
  const r = c.results;
  const cards = r.cards
    .map(
      (card, i) => `
      <article class="card" style="--i:${i}" data-reveal>
        ${icon(card.icon, 'icon card-icon')}
        <h3 class="card-title">${esc(card.title)}</h3>
        <p class="card-value">${esc(card.value)}</p>
        <p class="card-caption">${card.caption.map(esc).join('<br />')}</p>
      </article>`
    )
    .join('');
  const k = r.conditions;
  return `
  <section class="results" id="results" aria-labelledby="results-title">
    <div class="wrap results-grid">
      <div class="results-copy">
        <p class="eyebrow" data-reveal>${esc(r.kicker)}</p>
        <h2 class="h2" id="results-title" data-reveal>${esc(r.heading)}</h2>
        <p class="body" data-reveal>${esc(r.body)}</p>
        <div data-reveal>${button(r.button, 'btn--ink')}</div>
      </div>
      ${cards}
      <article class="card card--list" style="--i:${r.cards.length}" data-reveal>
        ${icon(k.icon, 'icon card-icon')}
        <h3 class="card-title">${esc(k.title)}</h3>
        <ul class="card-list">${k.items.map((it) => `<li>${esc(it)}</li>`).join('')}</ul>
        <a class="card-link"${linkAttrs(k.link.href)}><span>${esc(k.link.label)}</span>${icon('arrow', 'btn-arrow')}</a>
      </article>
    </div>
    <p class="sr-only">Source: ${esc(r.source)}</p>
  </section>`;
}

// ---- The road ahead --------------------------------------------------------------

function roadmap(c) {
  const r = c.roadmap;
  const steps = r.steps
    .map(
      (s, i) => `
          <li class="milestone" style="--i:${i}" data-reveal>
            <span class="milestone-when">${esc(s.when)}</span>
            <span class="milestone-text">${esc(s.text)}</span>
          </li>`
    )
    .join('');
  return `
  <section class="roadmap" id="roadmap" aria-labelledby="roadmap-title">
    <div class="roadmap-photo" aria-hidden="true"></div>
    <div class="wrap roadmap-grid">
      <div class="roadmap-copy">
        <p class="eyebrow" data-reveal>${esc(r.kicker)}</p>
        <h2 class="h2" id="roadmap-title" data-reveal>${esc(r.heading)}</h2>
        <p class="body" data-reveal>${r.body.map(esc).join('<br class="lb" /> ')}</p>
        <div data-reveal>${button(r.button, 'btn--ghost')}</div>
      </div>
      <ol class="timeline" data-reveal>${steps}
      </ol>
    </div>
  </section>`;
}

// ---- Footer --------------------------------------------------------------------

const FOOT_MARK =
  '<svg class="foot-mark" viewBox="0 0 52 10" aria-hidden="true"><path d="M7 1h44l-6 8H1z"/><path d="M33 1l-6 8M41 1l-6 8"/></svg>';

const CONTOURS =
  '<svg class="foot-contours" viewBox="0 0 1024 150" preserveAspectRatio="none" aria-hidden="true">' +
  [0, 1, 2, 3, 4, 5]
    .map((i) => {
      const y = 40 + i * 14;
      return `<path d="M180 ${y} C260 ${y - 22 - i * 2} 330 ${y + 26} 420 ${y + 4} S560 ${y - 30} 640 ${y - 6}"/>`;
    })
    .join('') +
  '</svg>';

function siteFooter(c, { home = true } = {}) {
  const f = c.footer;
  const links = f.links
    .map((l) => `<a${linkAttrs(l.href)}>${esc(l.label)}</a>`)
    .join('<span class="sep" aria-hidden="true">|</span>');
  const privacy = home ? ` · <a${linkAttrs(f.privacy.href)}>${esc(f.privacy.label)}</a>` : '';
  return `
<footer class="site-footer">
  ${CONTOURS}
  <div class="wrap footer-grid">
    <a class="brand" href="${home ? '#top' : './'}" aria-label="${esc(f.brand)}, home">${lockup('lockup--footer')}</a>
    <p class="footer-tagline">${esc(f.tagline)}</p>
    <nav class="footer-links" aria-label="Footer">${links}</nav>
    <p class="footer-copy">${esc(f.copyright)}${privacy}</p>
    ${FOOT_MARK}
  </div>
</footer>`;
}

// ---- Page ----------------------------------------------------------------------

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
    <link rel="icon" href="./favicon-32.png" type="image/png" sizes="32x32" />
    <link rel="apple-touch-icon" href="./apple-touch-icon.png" />
    <meta property="og:type" content="website" />
    <meta property="og:site_name" content="Varn Labs" />
    <meta property="og:title" content="${esc(title)}" />
    <meta property="og:description" content="${esc(description)}" />
    <meta property="og:url" content="${esc(url)}" />
    <meta property="og:image" content="${esc(image)}" />
    <meta property="og:image:width" content="1200" />
    <meta property="og:image:height" content="630" />
    <meta property="og:image:alt" content="Varn: A clear view of your airspace. Passive detection, drones and aircraft." />
    <meta name="twitter:card" content="summary_large_image" />
    <meta name="twitter:title" content="${esc(title)}" />
    <meta name="twitter:description" content="${esc(description)}" />
    <meta name="twitter:image" content="${esc(image)}" />`;
}

export function renderBody(c) {
  return `
<a class="skip-link" href="#main">Skip to content</a>
<main id="main" tabindex="-1">
  ${hero(c)}
  ${project(c)}
  ${results(c)}
  ${roadmap(c)}
</main>
${siteFooter(c)}`;
}

// ---- Privacy page ----------------------------------------------------------------

export function renderPrivacyHead(c) {
  const url = new URL('privacy.html', c.meta.url).href;
  return `${counter(c)}
    <title>${esc(c.privacy.title)} | Varn</title>
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
      <h2>${esc(s.heading)}</h2>
      <p>${esc(s.text)}${s.link ? ` <a class="u-link"${linkAttrs(s.link.href)}>${esc(s.link.label)}</a>.` : ''}</p>
    </section>`
    )
    .join('');
  return `
<a class="skip-link" href="#main">Skip to content</a>
<div class="legal-top">${siteHeader(c, { home: false })}</div>
<main id="main" class="legal" tabindex="-1">
  <div class="wrap legal-wrap">
    <p class="eyebrow">Updated ${esc(p.updated)}</p>
    <h1 class="h2 legal-title">${esc(p.title)}</h1>
    <p class="body legal-intro">${esc(on && p.introWithAnalytics ? p.introWithAnalytics : p.intro)}</p>
    ${sections}
    <section class="legal-section">
      <h2>${esc(c.footer.contactLabel)}</h2>
      <p>${esc(p.contactText)} <a class="u-link" href="mailto:${esc(c.footer.email)}">${esc(c.footer.email)}</a>.</p>
    </section>
  </div>
</main>
${siteFooter(c, { home: false })}`;
}

