// Turns src/content.js into static HTML at build time (see vite.config.js).
// The page ships as plain HTML, so it is readable before any JavaScript runs.
//
// Design: "Liquid Graphite" (Claude Design handoff, October 2026). Carbon,
// smoke and light; colour appears only when the sensor sees something.

const esc = (s) =>
  String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');

const isExternal = (href) => /^https?:\/\//.test(href);
const linkAttrs = (href) =>
  isExternal(href) ? ` href="${esc(href)}" target="_blank" rel="noopener"` : ` href="${esc(href)}"`;

const pad2 = (n) => String(n).padStart(2, '0');

// The Horizon mark: an arc of sky over the ground line, one lit node rising.
// Stroke weight steps up as the mark gets smaller (brand guide: 1.6 → 3.6).
const mark = (size, stroke = 1.7, cls = 'mark') =>
  `<svg class="${cls}" width="${size}" height="${size}" viewBox="0 0 32 32" aria-hidden="true"><path d="M5 22A11 11 0 0 1 27 22" fill="none" stroke="currentColor" stroke-width="${stroke}" stroke-linecap="round"/><path d="M2.5 22H29.5" stroke="currentColor" stroke-width="${stroke}" stroke-linecap="round"/><circle class="mark-node" cx="23.07" cy="13.57" r="${(1.6 + stroke * 0.65).toFixed(2)}"/></svg>`;

const ARROW_UR = '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M5 11L11 5M6 5h5v5" /></svg>';
const ARROW_DN = '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M8 3v10M4 9l4 4 4-4" /></svg>';

const STATUS_KINDS = { DONE: 'done', 'IN PROGRESS': 'progress', NEXT: 'next' };

// Section label, e.g. "02 · SYSTEM".
const kicker = (n, text, id = '') =>
  `<p class="kicker mono"${id ? ` id="${id}"` : ''}><span class="kicker-n">${pad2(n)}</span><span class="kicker-sep" aria-hidden="true"></span>${esc(text)}</p>`;

// "A [b c] d" -> words, with the bracketed ones marked bright.
function litWords(statement) {
  const out = [];
  String(statement)
    .split(/(\[[^\]]*\])/)
    .forEach((chunk) => {
      const bright = chunk.startsWith('[') && chunk.endsWith(']');
      chunk
        .replace(/^\[|\]$/g, '')
        .split(/\s+/)
        .filter(Boolean)
        .forEach((w) => out.push(`<span class="w${bright ? ' w--hi' : ''}">${esc(w)}</span>`));
    });
  return out.join(' ');
}

// Each sentence (or comma clause) of the headline on its own line; the
// second one in grey.
const headline = (h) =>
  h
    .split(/(?<=[.!?,])\s+/)
    .map((line, i) => `<span class="line${i ? ' line--dim' : ''}"><span class="line-in">${esc(line)}</span></span>`)
    .join(' ');

// ---- Hero ---------------------------------------------------------------------

// Glass readout: values are filled in live by hero.js (concept only).
const heroCard = (hero) => {
  const c = hero.card || {};
  return `
      <aside class="hud glass glass--deep tilt" id="hud" aria-label="${esc(c.label || 'Concept readout')}" data-hero>
        <span class="glass-sheen" aria-hidden="true"></span>
        <div class="hud-top">
          <span class="mono hud-label">${esc(c.label || 'NODE-01 · CONCEPT')}</span>
          <span class="state-pill mono"><span class="state-dot" aria-hidden="true"></span>${esc(c.state || 'TRACKING')}</span>
        </div>
        <div class="hud-main">
          <span class="badge badge--aircraft mono"><span class="badge-shape" aria-hidden="true"></span>${esc(c.target || 'AIRCRAFT')}</span>
          <span class="hud-conf" data-hud="conf">0.97</span>
        </div>
        <dl class="hud-grid">
          <div><dt class="mono">PAN</dt><dd class="mono" data-hud="pan">092.5°</dd></div>
          <div><dt class="mono">TILT</dt><dd class="mono" data-hud="tilt">47.0°</dd></div>
          <div><dt class="mono">CMD</dt><dd class="mono" data-hud="cmd">P92.5 T47</dd></div>
        </dl>
        <div class="hud-spark" aria-hidden="true"><canvas id="hud-spark" width="360" height="40"></canvas></div>
        <p class="hud-caption">${esc(hero.caption)}</p>
      </aside>`;
};

// Real footage, once it exists (see hero.footage in content.js). main.js
// starts playback only for visitors who haven't turned off motion.
const heroFootage = (f) => `
      <figure class="footage glass glass--deep" data-hero>
        <video class="hero-video" muted loop playsinline preload="metadata"${f.poster ? ` poster="${esc(f.poster)}"` : ''} aria-label="${esc(f.caption)}">
          <source src="${esc(f.video)}" />
        </video>
        <figcaption class="hud-caption">${esc(f.caption)}</figcaption>
      </figure>`;

// ---- How it works ----------------------------------------------------------------

// Simulated camera view. Boxes and readouts are animated by sensor.js; the
// static markup is a complete, sensible still on its own.
const sensorBlock = (s) => `
      <figure class="sensor glass" id="sensor" data-reveal>
        <span class="glass-sheen" aria-hidden="true"></span>
        <div class="sensor-head">
          <span class="mono sensor-label"><span class="live-dot" aria-hidden="true"></span>${esc(s.label)}</span>
          <span class="mono sensor-id">NODE-01</span>
        </div>
        <div class="frame" id="sensor-frame" role="img" aria-label="Simulated camera view: a drone locked in a bold red box near the centre, and an aircraft in a thin blue box higher up.">
          <div class="frame-sky" data-sensor="sky"></div>
          <div class="frame-grid" data-sensor="grid"></div>
          <div class="frame-ring" aria-hidden="true"></div>
          <div class="det det--drone is-locked" data-sensor="drone" style="--x:58%;--y:30%">
            <span class="det-label mono">DRONE <b data-sensor="drone-conf">0.91</b></span>
            <svg class="det-obj" viewBox="0 0 40 24" aria-hidden="true"><path d="M8 12h24M14 9h12v6H14z" /><path d="M2 6h12M26 6h12" /><path d="M8 6v6M32 6v6" /></svg>
          </div>
          <div class="det det--aircraft" data-sensor="aircraft" style="--x:22%;--y:24%">
            <span class="det-label mono">AIRCRAFT <b data-sensor="air-conf">0.64</b></span>
            <svg class="det-obj" viewBox="0 0 40 24" aria-hidden="true"><path d="M4 12h32M20 12l-8-9M20 12l-8 9M34 12l3-5M34 12l3 5" /></svg>
          </div>
          <div class="frame-bar mono">
            <span data-sensor="fps">24.8 FPS</span>
            <span data-sensor="pan">PAN 092.5°</span>
            <span data-sensor="tilt">TILT 47.0°</span>
            <span>LINK WI-FI</span>
            <span class="frame-state"><span class="state-dot" aria-hidden="true"></span>TRACKING</span>
          </div>
        </div>
        <figcaption class="sensor-caption">${esc(s.caption)}</figcaption>
      </figure>`;

// Pan-tilt mount: a still image first, replaced by a live 3D view (mount.js).
const mountBlock = (m) => `
      <figure class="mount glass" id="mount" data-reveal>
        <div class="mount-stage" id="mount-stage">
          <img class="mount-still" src="./models/pantilt-still.webp" width="900" height="760" loading="lazy" decoding="async"
            alt="3D render of the Skynode pan-tilt mount from its CAD files: a base holding the pan servo, a yoke on top, and a camera arm between the yoke's uprights." />
          <span class="mono mount-hint" aria-hidden="true">DRAG TO TURN</span>
        </div>
        <figcaption class="mount-info">
          <p class="mono mount-label"><span class="node-dot" aria-hidden="true"></span>${esc(m.label)}</p>
          <ul class="mount-parts">
            ${m.parts
              .map(
                (p, i) =>
                  `<li data-part="${i}"><span class="mono mount-part-name">${esc(p.name)}</span><p>${esc(p.text)}</p></li>`
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
    <div class="wrap">
      <h2 class="h-section" id="results-title" data-reveal>${esc(r.heading)}</h2>
      ${r.intro ? `<p class="lede" data-reveal>${esc(r.intro)}</p>` : ''}
      <dl class="results-grid">
        ${r.items
          .map(
            (it) => `
        <div class="result glass" data-reveal>
          <dt class="mono">${esc(it.label)}</dt>
          <dd class="result-value">${esc(it.value)}</dd>
          ${it.note ? `<dd class="result-note">${esc(it.note)}</dd>` : ''}
        </div>`
          )
          .join('')}
      </dl>
      <p class="results-source mono">${esc(r.source)}</p>
    </div>
  </section>`;
};

// Known limits: what Skynode can't do, stated plainly. Hidden if empty.
const limitsSection = (l, next) => {
  if (!l || !Array.isArray(l.items) || l.items.length === 0) return '';
  return `
  <section class="limits section" id="limits" aria-labelledby="limits-title">
    <div class="wrap">
      <header class="section-head">
        ${kicker(next(), l.kicker || 'Honest limits')}
        <h2 class="h-section" id="limits-title">${esc(l.heading)}</h2>
      </header>
      <ul class="limits-list">
        ${l.items
          .map(
            (it) => `
        <li class="limit glass" data-reveal>
          <span class="mono limit-tag">${esc(it.tag)}</span>
          <p>${esc(it.text)}</p>
        </li>`
          )
          .join('')}
      </ul>
    </div>
  </section>`;
};

const SUN =
  '<svg viewBox="0 0 32 32" aria-hidden="true"><circle cx="16" cy="16" r="5"/><path d="M16 4v4M16 24v4M4 16h4M24 16h4M7.5 7.5l2.8 2.8M21.7 21.7l2.8 2.8M7.5 24.5l2.8-2.8M21.7 10.3l2.8-2.8"/></svg>';

const sisterCard = (s) => `
    <a class="sister glass tilt"${linkAttrs(s.href)} data-reveal>
      <span class="glass-sheen" aria-hidden="true"></span>
      <span class="sister-mark">${SUN}</span>
      <span class="sister-text">
        <span class="mono sister-label">${esc(s.label)}</span>
        <span class="sister-name">${esc(s.name)}</span>
        ${s.description ? `<span class="sister-desc">${esc(s.description)}</span>` : ''}
      </span>
      <span class="sister-cta">${esc(s.linkLabel)} ${ARROW_UR}</span>
    </a>`;

// GoatCounter visit counter, only when content.js has a code.
const counter = (c) => {
  const code = c.analytics && c.analytics.goatcounter;
  return code
    ? `
    <script data-goatcounter="https://${esc(code)}.goatcounter.com/count" async src="https://gc.zgo.at/count.js"></script>`
    : '';
};

// SVG filter for liquid-glass refraction (Chromium only; see main.js).
const LIQUID_FILTER = `
<svg class="svg-defs" width="0" height="0" aria-hidden="true" focusable="false">
  <filter id="sn-liquid" x="0" y="0" width="100%" height="100%" color-interpolation-filters="sRGB">
    <feTurbulence type="fractalNoise" baseFrequency="0.004 0.007" numOctaves="2" seed="7" result="n" />
    <feGaussianBlur in="n" stdDeviation="3" result="b" />
    <feDisplacementMap in="SourceGraphic" in2="b" scale="70" xChannelSelector="R" yChannelSelector="G" />
  </filter>
</svg>`;

// Star field shared by the hero and the privacy page.
const STARS = '<div class="stars" aria-hidden="true"><div class="stars-a"></div><div class="stars-b"></div></div>';

function siteNav(c, { home = true } = {}) {
  const pre = home ? '' : './';
  const links = c.nav.links
    .map((l) => `<li><a class="nav-link" href="${pre}${esc(l.href)}">${esc(l.label)}</a></li>`)
    .join('');
  return `
<header class="site-header" id="top-nav">
  <nav class="nav glass" aria-label="Primary">
    <a class="brand" href="${home ? '#top' : './'}" aria-label="${esc(c.nav.brand)}, home">
      ${mark(26, 1.7)}
      <span class="wordmark">${esc(c.nav.brand)}</span>
    </a>
    <ul class="nav-links">${links}</ul>
    <a class="btn btn--primary btn--sm"${linkAttrs(c.hero.primary.href)}>GitHub</a>
  </nav>
</header>`;
}

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
  const { hero, math, how, status, results, limits, build, roadmap, sister, footer } = c;
  const footage = hero.footage && hero.footage.video ? hero.footage : null;

  const facts = hero.facts.map((f) => `<li>${esc(f)}</li>`).join('');

  const stats = (math.stats || [])
    .map(
      (s) => `
        <div class="stat${s.highlight ? ' stat--hi' : ''}">
          <dt class="mono">${esc(s.label)}</dt>
          <dd class="stat-value" data-count="${esc(s.value)}">${esc(s.value)}</dd>
        </div>`
    )
    .join('');

  const steps = how.steps
    .map(
      (s) => `
        <li class="step glass glass--deep tilt" data-reveal>
          <span class="glass-sheen" aria-hidden="true"></span>
          <div class="step-top">
            <span class="mono step-num">${esc(s.number)}</span>
            ${s.metric ? `<span class="mono chip">${esc(s.metric)}</span>` : ''}
          </div>
          <h3 class="step-title">${esc(s.title)}</h3>
          <p>${esc(s.body)}</p>
        </li>`
    )
    .join('');

  const statusRows = status.items
    .map((it) => {
      const kind = STATUS_KINDS[String(it.label).trim().toUpperCase()] || 'next';
      return `
        <li class="status-row status-row--${kind}">
          <span class="status-dot" aria-hidden="true"></span>
          <p>${esc(it.text)}</p>
          <span class="pill pill--${kind} mono">${esc(it.label)}</span>
        </li>`;
    })
    .join('');

  const phases = roadmap.phases
    .map(
      (p, i) => `
        <li class="phase${i === 0 ? ' phase--now' : ''}" data-phase="${i}">
          <span class="phase-node" aria-hidden="true"></span>
          <p class="mono phase-label">${esc(p.phase)}</p>
          <h3 class="phase-title">${esc(p.title)}</h3>
          <p>${esc(p.body)}</p>
        </li>`
    )
    .join('');

  let n = 0; // section numbers follow the order on the page
  return `
<a class="skip-link" href="#main">Skip to content</a>
${LIQUID_FILTER}
${siteNav(c)}

<main id="main" tabindex="-1">
  <section class="hero" id="top" aria-labelledby="hero-title">
    <div class="hero-sky" aria-hidden="true">
      ${STARS}
      <div class="hero-grid"></div>
      <div class="moon" id="moon"><div class="moon-body"></div></div>
      <canvas class="sky-canvas" id="sky-canvas"></canvas>
      <div class="planet" id="planet"><div class="planet-body"></div></div>
    </div>

    <div class="hero-inner wrap">
      <div class="hero-copy">
        <p class="eyebrow mono" data-hero>${esc(hero.eyebrow)}</p>
        <h1 class="hero-title" id="hero-title">${headline(hero.headline)}</h1>
        <p class="hero-sub" data-hero>${esc(hero.sub)}</p>
        <div class="hero-actions" data-hero>
          <a class="btn btn--primary btn--lg magnetic"${linkAttrs(hero.primary.href)}>
            <span>${esc(hero.primary.label)}</span>${ARROW_UR}
          </a>
          <a class="btn btn--glass btn--lg magnetic" href="${esc(hero.secondary.href)}">
            <span>${esc(hero.secondary.label)}</span>${ARROW_DN}
          </a>
        </div>
        ${hero.cost ? `<p class="hero-note" data-hero>${esc(hero.cost)}</p>` : ''}
      </div>
      ${footage ? heroFootage(footage) : heroCard(hero)}
    </div>

    <ul class="hero-facts mono wrap" data-hero>${facts}</ul>
  </section>

  <section class="math section" id="math" aria-labelledby="math-title">
    <div class="wrap math-inner">
      ${kicker(++n, math.heading, 'math-title')}
      ${
        math.statement
          ? `<p class="math-statement">${litWords(math.statement)}</p>`
          : `<p class="math-statement">${litWords(math.body)}</p>`
      }
      ${stats ? `<dl class="stats" data-reveal>${stats}</dl>` : ''}
      ${math.statsNote ? `<p class="stats-note mono" data-reveal>${esc(math.statsNote)}</p>` : ''}
      ${math.statement ? `<p class="lede" data-reveal>${esc(math.body)}</p>` : ''}
      ${
        math.useCases
          ? `<div class="note" data-reveal>
        <span class="mono note-tag">${esc(math.useCases.tag)}</span>
        <p>${esc(math.useCases.text)}</p>
      </div>`
          : ''
      }
    </div>
  </section>

  <section class="how section" id="how" aria-labelledby="how-title">
    <div class="halo" aria-hidden="true"></div>
    <div class="wrap how-inner">
      <header class="section-head">
        ${kicker(++n, how.kicker || 'System')}
        <h2 class="h-section" id="how-title">${esc(how.heading)}</h2>
      </header>
      <ol class="steps">${steps}</ol>
      ${how.sensor ? sensorBlock(how.sensor) : ''}
      ${how.mount ? mountBlock(how.mount) : ''}
      <div class="note" data-reveal>
        <span class="mono note-tag">TEST RANGE</span>
        <p>${esc(how.note)}</p>
      </div>
    </div>
  </section>

  <section class="status section" id="status" aria-labelledby="status-title">
    <div class="wrap wrap--mid">
      <header class="section-head">
        ${kicker(++n, status.kicker || 'Where it stands')}
        <h2 class="h-section" id="status-title">${esc(status.heading)}</h2>
      </header>
      <ol class="status-list">${statusRows}</ol>
    </div>
  </section>
  ${resultsSection(results)}
  ${limitsSection(limits, () => ++n)}
  <section class="build section" id="build" aria-labelledby="build-title">
    <div class="wrap build-inner">
      <div class="build-orb" aria-hidden="true"></div>
      <figure class="build-card glass glass--deep" data-reveal>
        <span class="glass-sheen" aria-hidden="true"></span>
        <h2 class="kicker mono" id="build-title"><span class="kicker-n">${pad2(++n)}</span><span class="kicker-sep" aria-hidden="true"></span>${esc(build.heading)}</h2>
        <blockquote class="build-body"><p>${esc(build.body)}</p></blockquote>
        ${
          build.quote
            ? `<figcaption class="build-motto"><p>&ldquo;${esc(build.quote)}&rdquo;</p>${
                build.signature ? `<span class="mono">&mdash; ${esc(build.signature)}</span>` : ''
              }</figcaption>`
            : ''
        }
      </figure>
    </div>
  </section>

  <section class="roadmap" id="roadmap" aria-labelledby="roadmap-title">
    <div class="wrap">
      <header class="section-head">
        ${kicker(++n, roadmap.kicker || 'Roadmap')}
        <h2 class="h-section" id="roadmap-title">${esc(roadmap.heading)}</h2>
        ${roadmap.intro ? `<p class="lede" data-reveal>${esc(roadmap.intro)}</p>` : ''}
      </header>
      <div class="roadmap-track">
        <span class="roadmap-line" aria-hidden="true"><span class="roadmap-line-fill"></span></span>
        <ol class="phases">${phases}</ol>
      </div>
    </div>
    <div class="outro">
      <div class="outro-planet" id="outro-planet" aria-hidden="true"><div class="planet-body"></div></div>
      <p class="closing">${esc(roadmap.closing)}</p>
    </div>
  </section>
</main>

${siteFooter(c, { sister })}`;
}

function siteFooter(c, { from = 'home', sister = null } = {}) {
  const footer = c.footer;
  const links = footer.links
    .filter((l) => !(from === 'privacy' && l.href.includes('privacy.html')))
    .map((l) => `<li><a class="u-link"${linkAttrs(l.href)}>${esc(l.label)}</a></li>`)
    .join('');
  return `
<footer class="site-footer">
  <div class="wrap footer-wrap">
    ${sister ? sisterCard(sister) : ''}
    <div class="footer-inner">
      <p class="brand brand--footer">${mark(22, 2)}<span class="wordmark">${esc(footer.brand)}</span></p>
      <ul class="footer-links">
        ${links}
        <li><span class="mono footer-k">${esc(footer.contactLabel)}</span> <a class="u-link"${linkAttrs(`mailto:${footer.email}`)}>${esc(footer.email)}</a></li>
      </ul>
    </div>
  </div>
  <p class="footer-giant" aria-hidden="true">${esc(footer.brand)}</p>
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
${LIQUID_FILTER}
<div class="legal-sky" aria-hidden="true">
  ${STARS}
  <div class="planet planet--legal"><div class="planet-body"></div></div>
</div>
${siteNav(c, { home: false })}

<main id="main" class="legal" tabindex="-1">
  <div class="wrap wrap--narrow">
    <article class="legal-card glass glass--deep">
      <p class="mono legal-updated">Updated ${esc(p.updated)}</p>
      <h1 class="legal-title">${esc(p.title)}</h1>
      <p class="legal-intro">${esc(on && p.introWithAnalytics ? p.introWithAnalytics : p.intro)}</p>
      ${sections}
      <section class="legal-section">
        <h2 class="mono">${esc(c.footer.contactLabel)}</h2>
        <p>${esc(p.contactText)} <a class="u-link" href="mailto:${esc(c.footer.email)}">${esc(c.footer.email)}</a>.</p>
      </section>
    </article>
  </div>
</main>
${siteFooter(c, { from: 'privacy' })}`;
}
