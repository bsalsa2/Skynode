// Turns src/content.js into static HTML at build time (see vite.config.js).
// The page ships as plain HTML, so it is readable before any JavaScript runs.
//
// Design: Talo brand v6, "Charcoal + Bronze + Split" (Claude Design handoff,
// October 2026). Charcoal and smoke, frosted glass, one bronze point of
// light. Status colours appear only for what the sensor sees.

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

// The Split mark: a disc cut by the horizon, the lower half shifted like
// light through glass, one bronze point of light above. Below 24 px it uses
// the favicon geometry (bigger dot, smaller shift) so it stays crisp.
const mark = (size, cls = 'mark') => {
  const small = size < 24;
  return `<svg class="${cls}" width="${size}" height="${size}" viewBox="0 0 32 32" aria-hidden="true"><path class="mark-ink" d="M4.17 14A12 12 0 0 1 27.83 14Z"${small ? ' transform="translate(0 -0.5)"' : ''}/><path class="mark-ink" d="M5.67 18H29.33A12 12 0 0 1 5.67 18Z"${small ? ' transform="translate(-0.5 0.5)"' : ''}/><circle class="mark-dot" cx="21" cy="8.5" r="${small ? 2.5 : 2.3}"/></svg>`;
};

const ARROW_UR = '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M5 11L11 5M6 5h5v5" /></svg>';
const ARROW_DN = '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M8 3v10M4 9l4 4 4-4" /></svg>';

const STATUS_KINDS = { DONE: 'done', 'IN PROGRESS': 'progress', NEXT: 'next' };

// Section marker row, e.g. "02-00   [ SYSTEM ]   +", over a hairline.
const kicker = (n, text, id = '', tag = 'p') =>
  `<${tag} class="kicker mono"${id ? ` id="${id}"` : ''}><span class="kicker-n">${pad2(n)}-00</span><span class="kicker-label">[ ${esc(text)} ]</span><span class="kicker-plus" aria-hidden="true">+</span></${tag}>`;

// Status: colour always travels with a shape and a word.
// circle = confirmed aircraft, square = possible drone, ring = no ADS-B match.
const STATUS = {
  aircraft: 'Confirmed aircraft',
  drone: 'Possible drone',
  'no-adsb': 'No ADS-B match',
};
const statusPill = (kind) =>
  `<span class="status-pill status-pill--${kind} mono"><span class="shape shape--${kind}" aria-hidden="true"></span>${esc(STATUS[kind] || STATUS.aircraft)}</span>`;

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

// The headline, broken after its first word ("Watch / the sky.") so it sits
// on two lines like the brand board.
const headline = (h) => {
  const [first, ...rest] = String(h).trim().split(/\s+/);
  return [first, rest.join(' ')]
    .filter(Boolean)
    .map((line) => `<span class="line"><span class="line-in">${esc(line)}</span></span>`)
    .join(' ');
};

// ---- Hero ---------------------------------------------------------------------

// Frosted sighting card. Placeholder values, so it always carries SAMPLE.
// hero-lens.js cycles it through the three statuses along with the lens.
const sightingCard = (hero) => {
  const c = hero.card || {};
  const kind = STATUS[c.status] ? c.status : 'aircraft';
  return `
      <aside class="sighting glass" id="sighting" aria-label="Sample sighting card" data-hero>
        <div class="sighting-top">
          <span class="status-pill status-pill--${kind} mono" data-card="pill"><span class="shape shape--${kind}" aria-hidden="true"></span><span data-card="pill-text">${esc(STATUS[kind])}</span></span>
          <span class="sample-tag mono">${esc(c.label || 'SAMPLE')}</span>
        </div>
        <div class="sighting-head">
          <span class="sighting-title">Sighting</span>
          <span class="mono sighting-time" data-card="time">${esc(c.time || '')}</span>
        </div>
        <dl class="sighting-grid mono">
          <div><dt>CLASS</dt><dd data-card="class">${esc(c.class || '')}</dd></div>
          <div><dt>CONF</dt><dd data-card="conf">${esc(c.conf || '')}</dd></div>
          <div><dt>ADS-B</dt><dd class="sighting-adsb sighting-adsb--${kind}" data-card="adsb">${esc(c.adsb || '')}</dd></div>
        </dl>
        <p class="sighting-caption">${esc(hero.caption)}</p>
      </aside>`;
};

// The glass lens: a simulated sky view (hero-lens.js draws into the canvas).
// Without JavaScript it is simply the Split mark behind glass.
const heroLens = () => `
      <div class="lens" id="lens">
        <span class="lens-sweep" aria-hidden="true"></span>
        ${mark(250, 'mark lens-mark')}
        <canvas class="lens-canvas" id="lens-canvas" aria-hidden="true"></canvas>
        <span class="lens-tag mono">SAMPLE · SIMULATED SKY</span>
      </div>`;

// Real footage, once it exists (see hero.footage in content.js). main.js
// starts playback only for visitors who haven't turned off motion.
const heroFootage = (f) => `
      <figure class="footage glass" data-hero>
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
        <div class="frame" id="sensor-frame" role="img" aria-label="Simulated camera view: a drone locked in a bold amber box near the centre, and an aircraft in a thin green box higher up.">
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
            alt="3D render of the Talo pan-tilt mount from its CAD files: a base holding the pan servo, a yoke on top, and a camera arm between the yoke's uprights." />
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

// Known limits: what Talo can't do, stated plainly. Hidden if empty.
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

// ---- Story (pinned, scroll-driven) ----------------------------------------------

// One animated scene per stage. They are pure markup + CSS animation: the
// active scene is switched by main.js while you scroll. All values are SAMPLE.
const SCENES = [
  // 01 SEE: range rings, a slow sweep, light arriving. Nothing leaves.
  () => `
        <svg class="sc sc-see" viewBox="0 0 400 300" aria-hidden="true">
          <g class="sc-rings"><circle cx="200" cy="170" r="40"/><circle cx="200" cy="170" r="80"/><circle cx="200" cy="170" r="120"/><circle cx="200" cy="170" r="160"/></g>
          <path class="sc-horizon" d="M0 232H400"/>
          <g class="sc-sweep"><path d="M200 170L200 10" /></g>
          <g class="sc-rays"><path d="M60 24L170 150"/><path d="M200 8L200 138"/><path d="M340 24L230 150"/></g>
          <circle class="sc-eye" cx="200" cy="170" r="9"/>
          <circle class="sc-eye-dot" cx="204" cy="166" r="2.6"/>
          <text class="sc-text" x="200" y="266" text-anchor="middle">RECEIVES LIGHT ONLY</text>
        </svg>`,
  // 02 DETECT: boxes snap onto things, each with class + confidence.
  () => `
        <div class="sc sc-detect" aria-hidden="true">
          <div class="sc-sky"></div>
          <div class="sc-box sc-box--aircraft" style="--x:24%;--y:30%;--d:0.2s"><span class="sc-chip mono"><i class="shape shape--aircraft"></i>AIRCRAFT 0.91</span></div>
          <div class="sc-box sc-box--drone" style="--x:62%;--y:56%;--d:0.7s"><span class="sc-chip mono"><i class="shape shape--drone"></i>DRONE 0.64</span></div>
          <div class="sc-box sc-box--noadsb" style="--x:76%;--y:22%;--d:1.2s"><span class="sc-chip mono"><i class="shape shape--no-adsb"></i>AIRCRAFT 0.78</span></div>
          <div class="sc-scan"></div>
        </div>`,
  // 03 TRACK: the target drifts, the mount follows, the ring settles on it.
  () => `
        <div class="sc sc-track" aria-hidden="true">
          <div class="sc-sky sc-sky--pan"></div>
          <div class="sc-ring"></div>
          <div class="sc-box sc-box--drone sc-box--follow"><span class="sc-chip mono"><i class="shape shape--drone"></i>LOCKED</span></div>
          <div class="sc-readout mono"><span>PAN <b>092.5°</b></span><span>TILT <b>47.0°</b></span><span>CMD <b>P92.5 T47.0</b></span></div>
        </div>`,
  // 04 LOG: rows arrive one by one.
  () => `
        <div class="sc sc-log" aria-hidden="true">
          <div class="sc-row sc-row--head mono"><span>TIME</span><span>CLASS</span><span>CONF</span><span>PAN/TILT</span></div>
          <div class="sc-row mono" style="--d:0.1s"><span>14:32:07Z</span><span><i class="shape shape--aircraft"></i>aircraft</span><span>0.91</span><span>092/47</span></div>
          <div class="sc-row mono" style="--d:0.5s"><span>13:58:41Z</span><span><i class="shape shape--drone"></i>drone</span><span>0.64</span><span>140/31</span></div>
          <div class="sc-row mono" style="--d:0.9s"><span>13:12:19Z</span><span><i class="shape shape--no-adsb"></i>aircraft</span><span>0.78</span><span>061/52</span></div>
          <div class="sc-row sc-row--clear mono" style="--d:1.3s"><span>13:00:00Z</span><span>sky clear</span><span>·</span><span>·</span></div>
        </div>`,
  // 05 CHECK: what the camera saw lines up against what ADS-B says.
  () => `
        <div class="sc sc-check" aria-hidden="true">
          <div class="sc-col"><p class="sc-col-h mono">CAMERA SAW</p>
            <span class="sc-pill status-pill status-pill--aircraft mono" style="--d:0.1s"><i class="shape shape--aircraft"></i>aircraft</span>
            <span class="sc-pill status-pill status-pill--aircraft mono" style="--d:0.5s"><i class="shape shape--aircraft"></i>aircraft</span>
            <span class="sc-pill status-pill status-pill--drone mono" style="--d:0.9s"><i class="shape shape--drone"></i>drone</span></div>
          <svg class="sc-links" viewBox="0 0 80 200" preserveAspectRatio="none"><path d="M0 30C40 30 40 30 80 30" style="--d:0.5s"/><path d="M0 100C40 100 40 100 80 100" style="--d:0.9s;stroke-dasharray:3 5"/></svg>
          <div class="sc-col"><p class="sc-col-h mono">ADS-B SAID</p>
            <span class="sc-pill sc-pill--plain mono" style="--d:0.4s">flight overhead</span>
            <span class="sc-pill sc-pill--plain sc-pill--none mono" style="--d:0.8s">no flight</span>
            <span class="sc-pill sc-pill--plain sc-pill--none mono" style="--d:1.2s">n/a</span></div>
          <div class="sc-result"><span class="status-pill status-pill--aircraft mono"><i class="shape shape--aircraft"></i>Confirmed aircraft</span><span class="status-pill status-pill--no-adsb mono"><i class="shape shape--no-adsb"></i>No ADS-B match</span></div>
        </div>`,
];

const storySection = (st, n) => `
  <section class="story" id="story" aria-labelledby="story-title">
    <div class="story-pin">
      <div class="wrap story-inner">
        <header class="story-head">
          ${kicker(n, st.kicker)}
          <h2 class="h-section" id="story-title">${esc(st.heading)}</h2>
          <p class="lede">${esc(st.intro)}</p>
        </header>
        <div class="story-body">
          <ol class="story-steps">
            ${st.stages
              .map(
                (s, i) => `
            <li class="story-step${i === 0 ? ' is-active' : ''}" data-stage="${i}">
              <div class="story-step-top"><span class="mono story-num">${esc(s.number)}</span><h3 class="story-title">${esc(s.title)}</h3></div>
              <p class="story-text">${esc(s.body)}</p>
              <span class="mono chip story-fact">${esc(s.fact)}</span>
            </li>`
              )
              .join('')}
          </ol>
          <figure class="story-device glass" aria-label="Simulated detection pipeline">
            <span class="glass-sheen" aria-hidden="true"></span>
            <div class="device-head">
              <span class="mono device-label"><span class="live-dot" aria-hidden="true"></span>${esc(st.device)}</span>
              <span class="mono device-step" id="story-step">01 / 0${st.stages.length}</span>
            </div>
            <div class="device-screen">
              ${SCENES.slice(0, st.stages.length)
                .map((fn, i) => `<div class="scene${i === 0 ? ' is-active' : ''}" data-scene="${i}">${fn()}</div>`)
                .join('')}
            </div>
            <div class="device-rail" aria-hidden="true">${st.stages
              .map((s, i) => `<span class="rail-dot${i === 0 ? ' is-active' : ''}" data-rail="${i}"><b class="mono">${esc(s.title)}</b></span>`)
              .join('<span class="rail-line"><span></span></span>')}</div>
            <figcaption class="device-note">${esc(st.note)}</figcaption>
          </figure>
        </div>
      </div>
    </div>
  </section>`;

const labelsSection = (l, n) => `
  <section class="labels section" id="labels" aria-labelledby="labels-title">
    ${stage('how-stage labels-stage')}
    <div class="wrap">
      <header class="section-head">
        ${kicker(n, l.kicker)}
        <h2 class="h-section" id="labels-title">${esc(l.heading)}</h2>
        <p class="lede" data-reveal>${esc(l.intro)}</p>
      </header>
      <ul class="label-grid">
        ${l.items
          .map(
            (it) => `
        <li class="label-card glass tilt">
          <span class="glass-sheen" aria-hidden="true"></span>
          <span class="label-shape label-shape--${it.kind}" aria-hidden="true"><i class="shape shape--${it.kind}"></i></span>
          ${statusPill(it.kind)}
          <p class="mono label-shapename">${esc(it.shape)}</p>
          <p class="label-rule">${esc(it.rule)}</p>
        </li>`
          )
          .join('')}
      </ul>
      <p class="mono label-note" data-reveal>${esc(l.note)}</p>
    </div>
  </section>`;

const tickerStrip = (items) => {
  const row = items.map((t) => `<li>${esc(t)}</li>`).join('');
  return `
  <div class="ticker" aria-label="Key facts">
    <ul class="ticker-track mono">${row}${row.replace(/<li>/g, '<li aria-hidden="true">')}</ul>
  </div>`;
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

// The stage every glass surface sits on: smoke and bronze light behind fine
// diagonal hairlines. Glass over flat colour shows nothing.
const stage = (cls = '') =>
  `<div class="stage${cls ? ` ${cls}` : ''}" aria-hidden="true"><div class="stage-bronze"></div><div class="stage-smoke"></div><div class="stage-lines"></div></div>`;

function siteNav(c, { home = true } = {}) {
  const pre = home ? '' : './';
  const links = c.nav.links
    .map(
      (l, i) =>
        `<li><a class="nav-link mono" href="${pre}${esc(l.href)}"><span class="nav-n">${pad2(i + 1)}</span>${esc(l.label)}</a></li>`
    )
    .join('');
  return `
<header class="site-header" id="top-nav">
  <nav class="nav glass" aria-label="Primary">
    <a class="brand" href="${home ? '#top' : './'}" aria-label="${esc(c.nav.brand)}, home">
      ${mark(28)}
      <span class="wordmark">${esc(c.nav.brand)}</span>
    </a>
    <ul class="nav-links">${links}</ul>
    <a class="btn btn--primary btn--sm"${linkAttrs(c.hero.primary.href)}>${esc(c.hero.primary.label)}</a>
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
    <link rel="icon" href="./favicon-32.png" type="image/png" sizes="32x32" />
    <link rel="apple-touch-icon" href="./apple-touch-icon.png" />
    <meta property="og:type" content="website" />
    <meta property="og:site_name" content="Talo Labs" />
    <meta property="og:title" content="${esc(title)}" />
    <meta property="og:description" content="${esc(description)}" />
    <meta property="og:url" content="${esc(url)}" />
    <meta property="og:image" content="${esc(image)}" />
    <meta property="og:image:width" content="1200" />
    <meta property="og:image:height" content="630" />
    <meta property="og:image:alt" content="Talo: A clear view of your airspace. Passive detection, drones and aircraft." />
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
<div class="progress" id="progress" aria-hidden="true"><span></span></div>
${siteNav(c)}

<main id="main" tabindex="-1">
  <section class="hero" id="top" aria-labelledby="hero-title">
    ${stage('hero-stage')}

    <div class="hero-inner wrap">
      <div class="hero-copy">
        <p class="eyebrow mono" data-hero>[ ${esc(hero.eyebrow)} ]</p>
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
      <div class="hero-visual" id="hero-visual">
        ${footage ? heroFootage(footage) : `${heroLens()}${sightingCard(hero)}`}
      </div>
    </div>

    <div class="hero-foot wrap" data-hero>
      <ul class="hero-facts mono">${facts}</ul>
      <span class="mono hero-labs">${esc(footer.brand)}</span>
    </div>
  </section>

  ${tickerStrip(c.ticker)}

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

  ${storySection(c.story, ++n)}
  ${labelsSection(c.labels, ++n)}

  <section class="how section" id="how" aria-labelledby="how-title">
    ${stage('how-stage')}
    <div class="wrap how-inner">
      <header class="section-head">
        ${kicker(++n, how.kicker || 'System')}
        <h2 class="h-section" id="how-title">${esc(how.heading)}</h2>
      </header>
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
        ${kicker(++n, build.heading, 'build-title', 'h2')}
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
      ${stage('outro-stage')}
      <div class="outro-lens" id="outro-lens" aria-hidden="true">${mark(120, 'mark outro-mark')}</div>
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
      <p class="brand brand--footer">${mark(22)}<span class="wordmark">${esc(c.nav.brand)}</span><span class="mono footer-labs">${esc(footer.brand)}</span></p>
      <ul class="footer-links">
        ${links}
        <li><span class="mono footer-k">${esc(footer.contactLabel)}</span> <a class="u-link"${linkAttrs(`mailto:${footer.email}`)}>${esc(footer.email)}</a></li>
      </ul>
    </div>
  </div>
</footer>`;
}

// ---- Privacy page (privacy.html) -------------------------------------------
export function renderPrivacyHead(c) {
  const url = new URL('privacy.html', c.meta.url).href;
  return `${counter(c)}
    <title>${esc(c.privacy.title)} | Talo</title>
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
${stage('stage-fixed')}
${siteNav(c, { home: false })}

<main id="main" class="legal" tabindex="-1">
  <div class="wrap wrap--narrow">
    <article class="legal-card glass">
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
