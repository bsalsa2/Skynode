/*
 * Skynode live dashboard.
 *
 * The brain (python -m brain.run) serves this page and answers a few
 * questions over HTTP. This script asks them and draws the answers:
 *
 *   /api/state      what the camera sees right now   (asked 4 times a second)
 *   /api/stats      sighting counts, hour by hour     (every 15 s)
 *   /api/sightings  the sighting log, newest first    (every 5 s on Overview)
 *   /api/config     the brain's settings, read-only   (when you open Settings)
 *   /stream.mjpg    the live picture: an endless stream of JPEG frames
 *
 * Two rules keep it sturdy:
 * - Never trust an answer to be complete. Every number goes through num()
 *   first, so the page shows "—" instead of "NaN" or "undefined".
 * - Text from the brain is always inserted with textContent (never as HTML),
 *   so an odd class name or file name can't break or hijack the page.
 *
 * No libraries and no build step: edit this file, reload the page.
 */
(function () {
  'use strict';

  // ---------------------------------------------------------------------------
  // Liquid-glass refraction: only Chromium can use an SVG filter inside
  // backdrop-filter. Safari and Firefox would drop the whole backdrop, so we
  // only switch it on where a Chromium-only API exists. Same check as the website.
  // ---------------------------------------------------------------------------
  if ('userAgentData' in navigator && window.CSS && CSS.supports && CSS.supports('backdrop-filter', 'url(#sn-liquid) blur(1px)')) {
    document.documentElement.classList.add('has-refraction');
  }

  const STATE_EVERY_MS = 250; // live state while the node answers
  const STATE_OFFLINE_MS = 2000; // back off while it doesn't
  const STATS_EVERY_MS = 15000;
  const RECENT_EVERY_MS = 5000;
  const LOG_EVERY_MS = 15000;
  const LOG_PAGE = 48; // cards per "Load more" (divides into 2, 3 and 4 columns)

  // ---------------------------------------------------------------------------
  // Small helpers
  // ---------------------------------------------------------------------------
  const $ = (id) => document.getElementById(id);

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined && text !== null) node.textContent = text;
    return node;
  }

  // Only touch the page when the text really changed (it's redrawn 4x a second).
  function setText(node, text) {
    if (node && node.textContent !== text) node.textContent = text;
  }

  // A real, finite number, or null. Everything numeric goes through this.
  function num(value) {
    return typeof value === 'number' && Number.isFinite(value) ? value : null;
  }
  function str(value) {
    return typeof value === 'string' ? value : '';
  }
  function count(value) {
    const n = num(value);
    return n === null || n < 0 ? 0 : Math.round(n);
  }
  function isObject(value) {
    return value !== null && typeof value === 'object' && !Array.isArray(value);
  }
  function capitalise(text) {
    return text ? text.charAt(0).toUpperCase() + text.slice(1) : text;
  }
  function plural(n, one, many) {
    return `${n} ${n === 1 ? one : many}`;
  }

  // Build "?a=1&b=two", skipping empty values.
  function query(params) {
    const parts = [];
    for (const [key, value] of Object.entries(params)) {
      if (value === undefined || value === null || value === '') continue;
      parts.push(`${encodeURIComponent(key)}=${encodeURIComponent(value)}`);
    }
    return parts.length ? `?${parts.join('&')}` : '';
  }

  async function getJSON(url, timeoutMs = 4000) {
    const abort = new AbortController();
    const timer = setTimeout(() => abort.abort(), timeoutMs);
    try {
      const response = await fetch(url, {
        cache: 'no-store',
        signal: abort.signal,
        headers: { Accept: 'application/json' },
      });
      if (!response.ok) throw new Error(`${url} answered ${response.status}`);
      return await response.json();
    } finally {
      clearTimeout(timer);
    }
  }

  // ---- Formatting (browser's local time, 24 h clock) ------------------------
  const pad2 = (n) => String(n).padStart(2, '0');

  function toDate(seconds) {
    const t = num(seconds);
    return t === null ? null : new Date(t * 1000);
  }
  function clock(seconds) {
    const d = toDate(seconds);
    return d ? `${pad2(d.getHours())}:${pad2(d.getMinutes())}:${pad2(d.getSeconds())}` : '—';
  }
  function hhmm(seconds) {
    const d = toDate(seconds);
    return d ? `${pad2(d.getHours())}:${pad2(d.getMinutes())}` : '—';
  }
  const shortDay = new Intl.DateTimeFormat(undefined, { weekday: 'short', day: 'numeric', month: 'short' });
  const longDay = new Intl.DateTimeFormat(undefined, { weekday: 'short', day: 'numeric', month: 'short', year: 'numeric' });

  function startOfDay(date) {
    return new Date(date.getFullYear(), date.getMonth(), date.getDate()).getTime();
  }
  // "today", "yesterday", or a short date like "Mon 5 Oct".
  function dayWord(seconds) {
    const d = toDate(seconds);
    if (!d) return '—';
    const days = Math.round((startOfDay(new Date()) - startOfDay(d)) / 86400000);
    if (days === 0) return 'today';
    if (days === 1) return 'yesterday';
    return shortDay.format(d);
  }
  function fullDateTime(seconds) {
    const d = toDate(seconds);
    return d ? `${longDay.format(d)}, ${clock(seconds)}` : '—';
  }
  // 4.2s, 38s, 2m 05s, 1h 02m
  function duration(seconds) {
    const s = num(seconds);
    if (s === null || s < 0) return '—';
    if (s < 10) return `${s.toFixed(1)}s`;
    if (s < 60) return `${Math.round(s)}s`;
    if (s < 3600) return `${Math.floor(s / 60)}m ${pad2(Math.floor(s % 60))}s`;
    return `${Math.floor(s / 3600)}h ${pad2(Math.floor((s % 3600) / 60))}m`;
  }
  // 45s, 12m, 6h 12m, 3d 4h
  function uptime(seconds) {
    const s = num(seconds);
    if (s === null || s < 0) return '—';
    if (s < 60) return `${Math.floor(s)}s`;
    if (s < 3600) return `${Math.floor(s / 60)}m`;
    if (s < 86400) return `${Math.floor(s / 3600)}h ${Math.floor((s % 3600) / 60)}m`;
    return `${Math.floor(s / 86400)}d ${Math.floor((s % 86400) / 3600)}h`;
  }
  // Servo angles: "092.5°" (pan is padded to 3 digits like the design).
  function angle(value, digits) {
    const v = num(value);
    if (v === null) return '—';
    const [whole, tenth] = Math.abs(v).toFixed(1).split('.');
    return `${v < 0 ? '−' : ''}${whole.padStart(digits, '0')}.${tenth}°`;
  }
  function confidence(value) {
    const v = num(value);
    return v === null ? '—' : v.toFixed(2);
  }
  function percent(ratio) {
    const r = num(ratio);
    if (r === null) return '—';
    const p = Math.min(100, Math.max(0, r * 100));
    return p >= 99.95 ? '100%' : `${p.toFixed(1)}%`;
  }
  // "wifi 192.168.1.42:5005" -> "WI-FI", "usb COM5" -> "USB", "none (...)" -> "NONE"
  function shortLink(text) {
    const first = str(text).trim().toLowerCase().split(/[\s(]+/)[0];
    if (!first) return '—';
    if (first === 'wifi' || first === 'wi-fi') return 'WI-FI';
    return first.toUpperCase().slice(0, 12);
  }

  // ---- What the sensor saw ----------------------------------------------------
  const CATEGORIES = ['drone', 'aircraft', 'other', 'clear'];

  function isCheck(item) {
    return item.kind === 'check';
  }
  function categoryOf(item) {
    if (isCheck(item)) return 'clear';
    const c = str(item.category);
    return CATEGORIES.includes(c) ? c : 'other';
  }
  // The word on a badge. "Other" things show their own class name (e.g. BIRD).
  function categoryWord(item) {
    const c = categoryOf(item);
    if (c === 'other') return (str(item.class_name) || 'other').toUpperCase();
    return c.toUpperCase();
  }
  // A box as [x1, y1, x2, y2] in 0..1 picture coordinates, or null if it's not usable.
  function validBox(box) {
    if (!Array.isArray(box) || box.length !== 4) return null;
    const v = box.map(num);
    if (v.some((x) => x === null)) return null;
    const [x1, y1, x2, y2] = v.map((x) => Math.min(1, Math.max(0, x)));
    return x2 > x1 && y2 > y1 ? [x1, y1, x2, y2] : null;
  }
  // Snapshot file names are simple ("20261007-140217-001.jpg"); anything else is ignored.
  function snapshotName(item) {
    const name = str(item.snapshot);
    return /^[0-9A-Za-z_-]+\.jpg$/.test(name) ? name : null;
  }
  // Read-aloud summary used for buttons and the announcer.
  function describe(item) {
    if (isCheck(item)) return `Sky check, clear, ${dayWord(item.start)} ${clock(item.start)}`;
    const word = capitalise(categoryWord(item).toLowerCase());
    return `${word}, ${dayWord(item.start)} ${clock(item.start)}, ${duration(item.duration_s)}, confidence ${confidence(item.confidence)}`;
  }

  // Badge: shape + colour + word (square = drone, circle = aircraft, dash = clear).
  function badge(item, boxed) {
    const c = categoryOf(item);
    const node = el('span', `badge c-${c}${boxed ? ' badge--box' : ''}`);
    node.append(el('span', `shape shape--${c}`), el('span', 'badge-word', categoryWord(item)));
    return node;
  }

  function meter(value) {
    const track = el('span', 'meter');
    const fill = el('span', 'meter-fill');
    const v = num(value);
    fill.style.width = `${v === null ? 0 : Math.round(Math.min(1, Math.max(0, v)) * 100)}%`;
    track.append(fill);
    return track;
  }

  // ---------------------------------------------------------------------------
  // Snapshots with the box drawn on top
  // ---------------------------------------------------------------------------
  // A `.thumb` box has a fixed shape (4:3 or 16:9). The picture inside may be
  // another shape, so `.thumb-fit` is sized to the picture's shape and the
  // detection box is placed in % of that. Modes:
  //   contain  the whole picture, letterboxed (detail dialog)
  //   zoom     fill the thumb and zoom in on the box so small things are visible,
  //            at most maxZoom times (more zoom = a smaller, softer crop)
  function layoutFit(fit, frameAspect, imageAspect, box, mode, maxZoom = 3) {
    let w;
    let h;
    const wider = imageAspect > frameAspect;
    if (mode === 'contain' ? wider : !wider) {
      w = 100;
      h = (frameAspect / imageAspect) * 100;
    } else {
      h = 100;
      w = (imageAspect / frameAspect) * 100;
    }
    let left = (100 - w) / 2;
    let top = (100 - h) / 2;
    if (mode === 'zoom' && box) {
      const boxW = ((box[2] - box[0]) * w) / 100; // share of the thumb's width at zoom 1
      const boxH = ((box[3] - box[1]) * h) / 100;
      const zoom = Math.min(maxZoom, Math.max(1, Math.min(0.4 / Math.max(boxW, 0.001), 0.6 / Math.max(boxH, 0.001))));
      w *= zoom;
      h *= zoom;
      left = Math.min(0, Math.max(100 - w, 50 - ((box[0] + box[2]) / 2) * w));
      top = Math.min(0, Math.max(100 - h, 50 - ((box[1] + box[3]) / 2) * h));
    }
    fit.style.left = `${left}%`;
    fit.style.top = `${top}%`;
    fit.style.width = `${w}%`;
    fit.style.height = `${h}%`;
  }

  function placeBox(node, box) {
    node.style.left = `${box[0] * 100}%`;
    node.style.top = `${box[1] * 100}%`;
    node.style.width = `${(box[2] - box[0]) * 100}%`;
    node.style.height = `${(box[3] - box[1]) * 100}%`;
  }

  // Fill `holder` (a .thumb or the dialog's media box) with one sighting's picture.
  function fillSnapshot(holder, item, frameAspect, mode, eager, maxZoom) {
    holder.replaceChildren();
    holder.classList.add(`c-${categoryOf(item)}`);
    if (isCheck(item)) {
      holder.append(el('span', 'thumb-dash'));
      return null;
    }
    const fit = el('span', 'thumb-fit');
    const box = validBox(item.box);
    if (box) {
      const boxNode = el('span', 'thumb-box');
      placeBox(boxNode, box);
      fit.append(boxNode);
    }
    holder.append(fit);
    layoutFit(fit, frameAspect, 16 / 9, box, mode, maxZoom); // until the picture tells us its real shape
    const name = snapshotName(item);
    if (!name) return null;
    const img = el('img', 'thumb-img');
    img.alt = '';
    img.decoding = 'async';
    if (!eager) img.loading = 'lazy';
    img.addEventListener('load', () => {
      if (img.naturalWidth && img.naturalHeight) {
        layoutFit(fit, frameAspect, img.naturalWidth / img.naturalHeight, box, mode, maxZoom);
      }
      img.classList.add('is-loaded');
    });
    img.addEventListener('error', () => img.remove()); // keep the graphite placeholder
    img.src = `/snapshots/${encodeURIComponent(name)}`;
    fit.prepend(img);
    return name;
  }

  // ---------------------------------------------------------------------------
  // App state
  // ---------------------------------------------------------------------------
  const app = {
    tab: 'overview',
    reachable: null, // could we reach the brain? null = still asking the first time
    online: false, // reachable AND camera frames are arriving
    failures: 0,
    state: null, // last good /api/state answer
    lastHeard: null, // browser time (s) of the last good answer
    wasLocked: false,
    stats: null,
    statsAt: 0,
    recentAt: 0,
    recentSig: null,
    recentTopId: null,
    configAt: 0,
    config: null,
  };

  // ---------------------------------------------------------------------------
  // Tabs (hash routing: #overview #sightings #nodes #settings)
  // ---------------------------------------------------------------------------
  const TABS = ['overview', 'sightings', 'nodes', 'settings'];

  function tabFromHash() {
    const name = location.hash.replace('#', '');
    return TABS.includes(name) ? name : 'overview';
  }

  function showTab(name) {
    const changed = app.tab !== name;
    app.tab = name;
    for (const t of TABS) {
      const on = t === name;
      const button = $(`tab-${t}`);
      button.setAttribute('aria-selected', String(on));
      button.tabIndex = on ? 0 : -1;
      $(`panel-${t}`).hidden = !on;
    }
    if (changed) window.scrollTo(0, 0);
    if (name === 'overview') {
      renderTiles();
      renderChart();
      if (Date.now() - app.recentAt > RECENT_EVERY_MS) loadRecent();
      if (Date.now() - app.statsAt > STATS_EVERY_MS) loadStats();
    } else if (name === 'sightings') {
      if (!log.loadedOnce) loadLog('reset');
      else loadLog('refresh');
    } else if (name === 'nodes') {
      renderNode();
    } else if (name === 'settings') {
      loadConfig();
    }
    syncStream();
  }

  function goToTab(name, focus) {
    if (location.hash !== `#${name}`) location.hash = name;
    else showTab(name);
    if (focus) $(`tab-${name}`).focus();
  }

  function setUpTabs() {
    const list = document.querySelector('.tabs');
    list.addEventListener('click', (event) => {
      const button = event.target.closest('[role="tab"]');
      if (button) goToTab(button.id.replace('tab-', ''), false);
    });
    // Arrow keys move between tabs (the usual tablist keyboard pattern).
    list.addEventListener('keydown', (event) => {
      const index = TABS.indexOf(app.tab);
      let next = null;
      if (event.key === 'ArrowRight') next = (index + 1) % TABS.length;
      else if (event.key === 'ArrowLeft') next = (index - 1 + TABS.length) % TABS.length;
      else if (event.key === 'Home') next = 0;
      else if (event.key === 'End') next = TABS.length - 1;
      if (next === null) return;
      event.preventDefault();
      goToTab(TABS[next], true);
    });
    window.addEventListener('hashchange', () => showTab(tabFromHash()));
  }

  // ---------------------------------------------------------------------------
  // Node status: header pill, node label
  // ---------------------------------------------------------------------------
  function nodeStatus() {
    if (app.reachable === null) return 'connecting';
    return app.online ? 'online' : 'offline';
  }

  function renderPill(pill, text) {
    const status = nodeStatus();
    if (pill.dataset.state !== status) pill.dataset.state = status;
    setText(text, status.toUpperCase());
  }

  function renderHeader() {
    renderPill($('status-pill'), $('status-text'));
    const node = (app.state && app.state.node) || {};
    const name = str(node.name) || 'NODE-01';
    const location = str(node.location).trim();
    setText($('node-label'), location ? `${name} · ${location}` : name);
    const title = `${name} · Skynode`;
    if (document.title !== title) document.title = title;
  }

  // ---------------------------------------------------------------------------
  // Live camera: the picture, the boxes on top, and the heads-up bar
  // ---------------------------------------------------------------------------
  const cam = {
    frame: $('frame'),
    img: $('stream'),
    layer: $('frame-layer'),
    msg: $('frame-msg'),
    hud: $('hud'),
    mode: 'off', // off | connecting | live | snapshot | nopicture
    gen: 0, // bumped on every start/stop so late events from an old stream are ignored
    timer: 0,
    retry: 0,
    aspect: 0,
    target: null, // the locked target's box (moves smoothly)
    others: [], // reusable boxes for everything else
  };

  // Only pull the stream while someone can see it: it costs the brain CPU and
  // it allows only a few viewers at once.
  function wantStream() {
    return app.tab === 'overview' && !document.hidden && app.online;
  }

  function syncStream() {
    if (wantStream()) {
      if (cam.mode === 'off') startStream();
    } else if (cam.mode !== 'off') {
      stopStream();
    }
    renderFrame();
  }

  function startStream() {
    const gen = ++cam.gen;
    cam.mode = 'connecting';
    cam.img.onload = () => {
      if (gen === cam.gen && cam.mode === 'connecting') {
        cam.mode = 'live';
        renderFrame();
      }
    };
    // The stream can be refused (too many viewers, or no OpenCV on the brain).
    // Fall back to one still picture a second.
    cam.img.onerror = () => {
      if (gen === cam.gen) startStills(gen);
    };
    cam.img.src = `/stream.mjpg?t=${Date.now()}`;
  }

  function startStills(gen) {
    cam.img.onload = () => {
      if (gen !== cam.gen) return;
      cam.mode = 'snapshot';
      renderFrame();
      cam.timer = setTimeout(nextStill, 1000);
    };
    cam.img.onerror = () => {
      if (gen !== cam.gen) return;
      cam.mode = 'nopicture';
      renderFrame();
      cam.timer = setTimeout(nextStill, 4000);
    };
    function nextStill() {
      if (gen === cam.gen) cam.img.src = `/snapshot.jpg?t=${Date.now()}`;
    }
    nextStill();
    // Try the real stream again later; a viewer slot may have freed up.
    cam.retry = setTimeout(() => {
      if (gen !== cam.gen) return;
      stopStream();
      syncStream();
    }, 30000);
  }

  function stopStream() {
    cam.gen += 1;
    clearTimeout(cam.timer);
    clearTimeout(cam.retry);
    cam.img.onload = null;
    cam.img.onerror = null;
    cam.img.removeAttribute('src'); // closes the stream connection
    cam.mode = 'off';
  }

  function renderFrame() {
    // Chromium doesn't always fire "load" for a never-ending MJPEG stream, so
    // also notice the first frame by its size.
    if (cam.mode === 'connecting' && cam.img.naturalWidth > 0) cam.mode = 'live';

    let state = 'connecting';
    let message = 'Connecting…';
    if (app.reachable === false) {
      state = 'offline';
      message = 'Camera offline. Start the brain to see the live view.';
    } else if (app.reachable && !app.online) {
      state = 'stalled';
      message = 'No new frames from the camera. The brain is running, so check that the camera is plugged in.';
    } else if (cam.mode === 'live' || cam.mode === 'snapshot') {
      state = 'live';
    } else if (cam.mode === 'nopicture') {
      state = 'nopicture';
      message = 'The live picture isn’t available right now. Detection and logging carry on.';
    }
    if (cam.frame.dataset.state !== state) cam.frame.dataset.state = state;
    setText(cam.msg, message);
    cam.hud.hidden = !app.online;

    const pill = $('live-pill');
    const live = app.online && app.state ? app.state.live : null;
    if (app.online) {
      if (pill.dataset.state !== 'live') pill.dataset.state = 'live';
      const at = (live && num(live.frame_time)) || num(app.state.now);
      setText($('live-text'), `LIVE · ${clock(at)}`);
    } else {
      if (pill.dataset.state !== 'off') pill.dataset.state = 'off';
      setText($('live-text'), app.reachable === null ? 'CONNECTING' : 'OFFLINE');
    }
  }

  // Size the box layer to the part of the 16:9 frame the picture really covers
  // (a 4:3 webcam is letterboxed by object-fit: contain).
  function placeLayer(aspect) {
    if (aspect === cam.aspect) return;
    cam.aspect = aspect;
    layoutFit(cam.layer, 16 / 9, aspect, null, 'contain');
  }

  function boxNode(animated) {
    const node = el('div', 'box');
    node.append(el('span', 'box-label'));
    if (!animated) node.style.transition = 'none';
    cam.layer.append(node);
    return node;
  }

  function drawBox(node, item) {
    const { d, box, locked, tracked } = item;
    const c = CATEGORIES.includes(d.category) ? d.category : 'other';
    let cls = `box c-${c}`;
    if (locked) cls += ' box--locked';
    else if (!tracked) cls += ' box--faint';
    if (box[1] < 0.07) cls += ' box--below'; // no room for the label above
    if (box[0] > 0.78) cls += ' box--end'; // keep the label inside the picture
    if (node.className !== cls) node.className = cls;
    placeBox(node, box);
    const label = node.firstChild;
    label.hidden = !tracked;
    if (tracked) setText(label, `${(str(d.class_name) || c).toUpperCase()} ${confidence(d.confidence)}`);
    node.hidden = false;
  }

  function renderOverlay(live) {
    const size = live && Array.isArray(live.frame_size) ? live.frame_size : [];
    const w = num(size[0]);
    const h = num(size[1]);
    placeLayer(w && h ? w / h : 16 / 9);

    const items = [];
    let target = null;
    const detections = live && Array.isArray(live.detections) ? live.detections.slice(0, 20) : [];
    for (const d of detections) {
      if (!isObject(d)) continue;
      const box = validBox(d.box);
      if (!box) continue;
      const item = { d, box, locked: d.is_target === true, tracked: d.tracked_class === true || d.is_target === true };
      if (item.locked && !target) target = item;
      else items.push(item);
    }
    if (!target && live && isObject(live.target)) {
      const box = validBox(live.target.box);
      if (box) target = { d: live.target, box, locked: true, tracked: true };
    }

    // Everything else first (faint, then tracked), so the locked box is drawn on top.
    items.sort((a, b) => Number(a.tracked) - Number(b.tracked));
    while (cam.others.length < items.length) cam.others.push(boxNode(false));
    cam.others.forEach((node, i) => {
      if (items[i]) drawBox(node, items[i]);
      else node.hidden = true;
    });

    if (!cam.target) cam.target = boxNode(true);
    if (target) {
      const appearing = cam.target.hidden;
      if (appearing) cam.target.style.transition = 'none'; // don't slide in from where it was last time
      cam.layer.append(cam.target); // keep it last = on top
      drawBox(cam.target, target);
      if (appearing) {
        void cam.target.offsetWidth;
        cam.target.style.transition = '';
      }
    } else {
      cam.target.hidden = true;
    }
  }

  function renderHud(live) {
    if (!live) return;
    const fps = num(live.fps);
    setText($('hud-fps'), `${fps === null ? '—' : fps.toFixed(1)} FPS`);
    setText($('hud-pan'), `PAN ${angle(live.pan, 3)}`);
    setText($('hud-tilt'), `TILT ${angle(live.tilt, 1)}`);
    const node = (app.state && app.state.node) || {};
    setText($('hud-link'), `LINK ${shortLink(live.link || node.link)}`);
    const tracking = isTracking(app.state, live);
    const state = $('hud-state');
    const word = tracking ? 'tracking' : 'watching';
    if (state.dataset.state !== word) state.dataset.state = word;
    setText($('hud-state-text'), word.toUpperCase());
  }

  // ---------------------------------------------------------------------------
  // Polling /api/state
  // ---------------------------------------------------------------------------
  let stateTimer = 0;

  function scheduleState(delay) {
    clearTimeout(stateTimer);
    stateTimer = setTimeout(pollState, delay);
  }

  async function pollState() {
    if (document.hidden) return; // visibilitychange starts us again
    try {
      const state = await getJSON('/api/state', 2500);
      if (!isObject(state)) throw new Error('state is not an object');
      onState(state);
    } catch (error) {
      onStateFailed();
    }
    scheduleState(app.reachable ? STATE_EVERY_MS : STATE_OFFLINE_MS);
  }

  // Is the node tracking something? live.locked only says whether THIS frame
  // had a target. state.current is the sighting the logger has open, and it
  // stays open while the tracker coasts through a frame or two where the
  // detector missed the target. So use either: no flicker to WATCHING, and
  // current going away means the sighting has just been closed and logged.
  function isTracking(state, live) {
    return !!(live && live.locked === true) || isObject(state && state.current);
  }

  function onState(state) {
    const wasReachable = app.reachable;
    app.state = state;
    app.lastHeard = Date.now() / 1000;
    app.failures = 0;
    app.reachable = true;
    app.online = state.online === true;
    const live = isObject(state.live) ? state.live : null;

    // A lock just ended, so a sighting was probably just logged: show it now.
    const locked = isTracking(state, live);
    if (app.wasLocked && !locked) {
      app.recentAt = 0;
      app.statsAt = 0;
      setTimeout(slowTick, 300);
    }
    app.wasLocked = locked;

    if (wasReachable === false) {
      // Back after being away: refresh everything straight away.
      app.recentAt = 0;
      app.statsAt = 0;
      app.configAt = 0;
      setTimeout(slowTick, 0);
    }

    renderHeader();
    syncStream();
    if (app.online && live) {
      renderOverlay(live);
      renderHud(live);
    }
    if (app.tab === 'overview') renderUptimeTile();
    if (app.tab === 'nodes') renderNode();
  }

  function onStateFailed() {
    app.failures += 1;
    // One slow answer isn't an outage; two in a row is.
    if (app.failures < 2 && app.reachable !== null) return;
    app.reachable = false;
    app.online = false;
    app.wasLocked = false;
    renderHeader();
    syncStream();
    if (app.tab === 'overview') renderUptimeTile();
    if (app.tab === 'nodes') renderNode();
  }

  // Slower refreshes, checked once a second.
  function slowTick() {
    if (document.hidden || !app.reachable) return;
    const now = Date.now();
    if (app.tab === 'overview') {
      if (now - app.statsAt >= STATS_EVERY_MS) loadStats();
      if (now - app.recentAt >= RECENT_EVERY_MS) loadRecent();
    }
    if (app.tab === 'sightings' && log.loadedOnce && now - log.refreshedAt >= LOG_EVERY_MS) loadLog('refresh');
    if ((app.tab === 'settings' || !app.config) && now - app.configAt >= 60000) loadConfig();
  }

  // ---------------------------------------------------------------------------
  // Stat tiles
  // ---------------------------------------------------------------------------
  function lastSeenNote(seconds, now) {
    const t = num(seconds);
    if (t === null) return 'none';
    const reference = num(now) || Date.now() / 1000;
    if (reference - t <= 24 * 3600) return `last at ${hhmm(t)}`;
    return `last on ${shortDay.format(new Date(t * 1000))}`;
  }

  function renderTiles() {
    const s = app.stats;
    const total = s ? num(s.total) : null;
    const drones = s ? num(s.drone) : null;
    const aircraft = s ? num(s.aircraft) : null;
    setText($('tile-total'), total === null ? '—' : String(Math.round(total)));
    setText($('tile-drone'), drones === null ? '—' : String(Math.round(drones)));
    setText($('tile-aircraft'), aircraft === null ? '—' : String(Math.round(aircraft)));
    $('tile-drone').classList.toggle('is-drone', drones !== null && drones > 0);

    let totalNote = ' ';
    let droneNote = ' ';
    let aircraftNote = ' ';
    if (s) {
      const previous = num(s.previous_total);
      if (total !== null && previous !== null) {
        const diff = Math.round(total - previous);
        if (diff > 0) totalNote = `+${diff} vs yesterday`;
        else if (diff < 0) totalNote = `−${-diff} vs yesterday`;
        else totalNote = 'same as yesterday';
      } else if (total !== null) {
        totalNote = 'no data for yesterday yet';
      }
      const last = isObject(s.last) ? s.last : {};
      droneNote = lastSeenNote(last.drone, s.now);
      aircraftNote = lastSeenNote(last.aircraft, s.now);
    }
    setText($('tile-total-note'), totalNote);
    setText($('tile-drone-note'), droneNote);
    setText($('tile-aircraft-note'), aircraftNote);
    renderUptimeTile();
  }

  // Uptime = how much of the time since the brain started it was really
  // watching (gaps of more than a second between frames don't count).
  function renderUptimeTile() {
    const node = (app.state && app.state.node) || null;
    setText($('tile-uptime'), node ? percent(node.watch_ratio) : '—');
    let note = ' ';
    if (app.reachable === false) note = 'node offline';
    else if (node && num(node.uptime_s) !== null) note = `${uptime(node.uptime_s)} since start`;
    setText($('tile-uptime-note'), note);
  }

  async function loadStats() {
    app.statsAt = Date.now();
    try {
      const stats = await getJSON('/api/stats?hours=24');
      if (!isObject(stats)) return;
      app.stats = stats;
      renderTiles();
      renderChart();
    } catch (error) {
      // Keep the last numbers; the status pill already says if the node is away.
    }
  }

  // ---------------------------------------------------------------------------
  // Recent sightings (Overview)
  // ---------------------------------------------------------------------------
  const announcer = $('announcer');

  function recentRow(item) {
    const c = categoryOf(item);
    const li = el('li');
    const button = el('button', `row c-${c}`);
    button.type = 'button';
    button.dataset.id = str(item.id);
    button.setAttribute('aria-label', `${describe(item)}. Show details.`);

    const thumb = el('span', 'thumb');
    // A 64x48 thumb can zoom in further than a big card before it looks soft:
    // a plane far away is only a few pixels of the snapshot.
    fillSnapshot(thumb, item, 64 / 48, 'zoom', false, 6);

    const main = el('span', 'row-main');
    const time = isCheck(item) ? `${clock(item.start)} · sky check` : `${clock(item.start)} · ${duration(item.duration_s)}`;
    main.append(badge(item, false), el('span', 'row-time', time));

    const right = el('span', 'row-conf');
    right.append(el('span', 'row-conf-value', isCheck(item) ? '—' : confidence(item.confidence)), meter(isCheck(item) ? 0 : item.confidence));

    button.append(thumb, main, right);
    button.addEventListener('click', () => openDetail(item, button));
    li.append(button);
    return li;
  }

  function renderRecent(items) {
    const signature = items.map((i) => `${i.id}:${i.end}`).join('|');
    if (signature === app.recentSig) return;
    const first = app.recentSig === null;
    app.recentSig = signature;

    // Say new sightings out loud for screen readers (calmly, once).
    const top = items[0];
    if (!first && top && !isCheck(top) && top.id !== app.recentTopId) {
      setText(announcer, `${capitalise(categoryWord(top).toLowerCase())} detected at ${clock(top.start)}, confidence ${confidence(top.confidence)}.`);
    }
    app.recentTopId = top ? top.id : null;

    // Rebuilding the list mustn't steal keyboard focus from a row.
    const list = $('recent-list');
    const focused = document.activeElement && list.contains(document.activeElement) ? document.activeElement.dataset.id : null;
    list.replaceChildren(...items.map(recentRow));
    if (focused) {
      const again = list.querySelector(`[data-id="${CSS.escape(focused)}"]`);
      if (again) again.focus();
    }
    const empty = $('recent-empty');
    empty.hidden = items.length > 0;
    setText(empty, 'No sightings in the last 24 hours. The node is watching.');
  }

  async function loadRecent() {
    app.recentAt = Date.now();
    try {
      const data = await getJSON(`/api/sightings${query({ limit: 7, hours: 24 })}`);
      const items = isObject(data) && Array.isArray(data.items) ? data.items.filter(isObject).slice(0, 7) : [];
      renderRecent(items);
    } catch (error) {
      if (app.recentSig === null) {
        const empty = $('recent-empty');
        empty.hidden = false;
        setText(empty, 'Can’t load sightings right now.');
      }
    }
  }

  // ---------------------------------------------------------------------------
  // Sightings by hour (stacked columns)
  // ---------------------------------------------------------------------------
  // Series stack up from the baseline in this order. Colours come from CSS
  // (--chart-*), checked for contrast and colour-blind safety; don't swap them.
  const SERIES = [
    { key: 'aircraft', label: 'Aircraft', color: 'var(--chart-aircraft)' },
    { key: 'other', label: 'Other', color: 'var(--chart-other)' },
    { key: 'drone', label: 'Drone', color: 'var(--chart-drone)' },
  ];
  const LEGEND_ORDER = ['aircraft', 'drone', 'other'];

  const chart = {
    plot: $('chart-plot'),
    grid: $('chart-grid'),
    colsBox: $('chart-cols'),
    xAxis: $('chart-x'),
    tip: $('chart-tip'),
    cols: [],
    rows: [],
    top: 10,
    showOther: false,
    active: -1, // column with the tooltip open
    focus: 23, // column that gets Tab focus (roving tabindex)
  };

  // 24 hourly buckets, oldest first. If the brain hasn't answered yet, draw
  // empty hours ending at the current one so the axis still makes sense.
  function chartRows() {
    const buckets = app.stats && Array.isArray(app.stats.buckets) ? app.stats.buckets.filter(isObject).slice(-24) : [];
    if (buckets.length === 24) {
      return buckets.map((b) => {
        const row = { start: num(b.start), aircraft: count(b.aircraft), drone: count(b.drone), other: count(b.other) };
        row.total = row.aircraft + row.drone + row.other;
        return row;
      });
    }
    const hour = new Date();
    hour.setMinutes(0, 0, 0);
    const rows = [];
    for (let i = 23; i >= 0; i -= 1) {
      rows.push({ start: hour.getTime() / 1000 - i * 3600, aircraft: 0, drone: 0, other: 0, total: 0 });
    }
    return rows;
  }

  // Clean gridline steps (1, 2, 5, 10, 20, 50 …) with at most 4 bands.
  function niceScale(max) {
    if (max <= 0) return { step: 5, top: 10 };
    for (let power = 1; ; power *= 10) {
      for (const m of [1, 2, 5]) {
        const step = m * power;
        const bands = Math.max(2, Math.ceil(max / step));
        if (bands <= 4) return { step, top: step * bands };
      }
    }
  }

  function hourRange(row, isLast) {
    if (row.start === null) return '—';
    return isLast ? `${hhmm(row.start)}–now` : `${hhmm(row.start)}–${hhmm(row.start + 3600)}`;
  }

  function buildColumns() {
    for (let i = 0; i < 24; i += 1) {
      const col = el('button', 'col');
      col.type = 'button';
      col.tabIndex = i === chart.focus ? 0 : -1;
      const bar = el('span', 'col-bar');
      // One segment per series, made once and only updated afterwards: if the
      // segment under the mouse were replaced, Chromium can lose track of the
      // hover and never tell the column the pointer left (tooltip stuck open).
      for (const s of SERIES) {
        const seg = el('span', 'col-seg');
        seg.style.setProperty('--s', s.color);
        seg.hidden = true;
        bar.append(seg);
      }
      col.append(bar);
      col.addEventListener('pointerenter', () => showTip(i));
      col.addEventListener('pointerleave', () => {
        // Hand the tooltip back to the keyboard-focused column, if there is one.
        const focused = chart.cols.indexOf(document.activeElement);
        if (focused >= 0) showTip(focused);
        else hideTip();
      });
      col.addEventListener('focus', () => {
        setChartFocus(i);
        showTip(i);
      });
      col.addEventListener('blur', () => hideTip());
      chart.colsBox.append(col);
      chart.cols.push(col);
    }
    // Left/right arrows walk the hours; Home/End jump to the ends.
    chart.colsBox.addEventListener('keydown', (event) => {
      let next = null;
      if (event.key === 'ArrowRight') next = Math.min(23, chart.focus + 1);
      else if (event.key === 'ArrowLeft') next = Math.max(0, chart.focus - 1);
      else if (event.key === 'Home') next = 0;
      else if (event.key === 'End') next = 23;
      else if (event.key === 'Escape') hideTip();
      if (next === null) return;
      event.preventDefault();
      chart.cols[next].focus();
    });
  }

  function setChartFocus(i) {
    chart.focus = i;
    chart.cols.forEach((col, j) => {
      col.tabIndex = j === i ? 0 : -1;
    });
  }

  function renderChart() {
    if (!chart.cols.length) buildColumns();
    const rows = chartRows();
    chart.rows = rows;
    const max = Math.max(0, ...rows.map((r) => r.total));
    const { step, top } = niceScale(max);
    chart.top = top;
    chart.showOther = rows.some((r) => r.other > 0);

    // Gridlines and tick labels.
    const lines = [];
    for (let v = 0; v <= top; v += step) {
      const line = el('span', `chart-line${v === 0 ? ' chart-line--base' : ''}`);
      line.style.bottom = `${(v / top) * 100}%`;
      const tick = el('span', 'chart-tick', String(v));
      tick.style.bottom = `${(v / top) * 100}%`;
      lines.push(line, tick);
    }
    chart.grid.replaceChildren(...lines);

    // Columns: show the segment of each series that has something in this hour.
    rows.forEach((row, i) => {
      const col = chart.cols[i];
      const bar = col.firstChild;
      bar.style.setProperty('--h', `${(row.total / top) * 100}%`);
      let topSeg = null;
      SERIES.forEach((s, k) => {
        const seg = bar.children[k];
        seg.hidden = !row[s.key];
        seg.classList.remove('is-top');
        if (row[s.key]) {
          seg.style.setProperty('--v', String(row[s.key]));
          topSeg = seg;
        }
      });
      if (topSeg) topSeg.classList.add('is-top'); // the data end gets the rounded corners
      const parts = SERIES.filter((s) => s.key !== 'other' || chart.showOther).map((s) => `${row[s.key]} ${s.label.toLowerCase()}`);
      col.setAttribute('aria-label', `${hourRange(row, i === 23)}: ${plural(row.total, 'sighting', 'sightings')} (${parts.join(', ')})`);
    });

    // X axis: the first hour, three evenly spaced, and NOW.
    const labels = [0, 6, 12, 18, 23].map((i) => {
      const label = el('span', '', i === 23 ? 'NOW' : hhmm(rows[i].start));
      label.style.left = `${((i + 0.5) / 24) * 100}%`;
      return label;
    });
    chart.xAxis.replaceChildren(...labels);

    // Legend: neutral words, coloured swatch beside them.
    const legend = LEGEND_ORDER.filter((key) => key !== 'other' || chart.showOther).map((key) => {
      const s = SERIES.find((x) => x.key === key);
      const li = el('li');
      const swatch = el('span', 'swatch');
      swatch.style.setProperty('--s', s.color);
      li.append(swatch, document.createTextNode(s.label.toUpperCase()));
      return li;
    });
    $('chart-legend').replaceChildren(...legend);

    $('chart-empty').hidden = !(app.stats && max === 0);
    renderChartTable(rows);
    if (chart.active >= 0) showTip(chart.active);
  }

  function showTip(i) {
    const row = chart.rows[i];
    if (!row) return;
    chart.active = i;
    chart.cols.forEach((col, j) => col.classList.toggle('is-active', j === i));

    const tip = chart.tip;
    const value = el('div', 'tip-value');
    value.append(el('b', '', String(row.total)), document.createTextNode(row.total === 1 ? 'sighting' : 'sightings'));
    const list = el('div', 'tip-rows');
    for (const key of LEGEND_ORDER) {
      if (key === 'other' && !chart.showOther) continue;
      const s = SERIES.find((x) => x.key === key);
      const line = el('div', 'tip-row');
      const swatch = el('span', 'tip-key');
      swatch.style.setProperty('--s', s.color);
      line.append(swatch, el('span', '', s.label), el('b', '', String(row[key])));
      list.append(line);
    }
    tip.replaceChildren(value, list, el('div', 'tip-hour', hourRange(row, i === 23)));
    tip.hidden = false;

    // Sit beside the column (right of it, or left near the right edge), so it
    // never covers the bar being read.
    const col = chart.cols[i];
    const bar = col.firstChild;
    const barLeft = col.offsetLeft + bar.offsetLeft - 6; // past the hover wash
    const barRight = col.offsetLeft + bar.offsetLeft + bar.offsetWidth + 6;
    const plotWidth = chart.plot.clientWidth;
    const tipWidth = tip.offsetWidth;
    let x = barRight + 8;
    if (x + tipWidth > plotWidth) x = barLeft - 8 - tipWidth;
    x = Math.max(-24, x);
    const y = Math.max(0, (chart.plot.clientHeight - tip.offsetHeight) / 2);
    tip.style.transform = `translate(${Math.round(x)}px, ${Math.round(y)}px)`;
  }

  function hideTip() {
    chart.active = -1;
    chart.tip.hidden = true;
    chart.cols.forEach((col) => col.classList.remove('is-active'));
  }

  function renderChartTable(rows) {
    const body = $('chart-table-body');
    body.replaceChildren(
      ...rows.map((row, i) => {
        const tr = el('tr');
        tr.append(el('th', '', hourRange(row, i === 23)));
        tr.firstChild.scope = 'row';
        for (const value of [row.aircraft, row.drone, row.other, row.total]) {
          tr.append(el('td', value === 0 ? 'is-zero' : '', String(value)));
        }
        return tr;
      })
    );
  }

  function setUpChartToggle() {
    const toggle = $('chart-table-toggle');
    toggle.addEventListener('click', () => {
      const showTable = toggle.getAttribute('aria-pressed') !== 'true';
      toggle.setAttribute('aria-pressed', String(showTable));
      $('chart').hidden = showTable;
      $('chart-table').hidden = !showTable;
      hideTip();
    });
  }

  // ---------------------------------------------------------------------------
  // Sightings tab: filters, cards, "Load more"
  // ---------------------------------------------------------------------------
  const log = {
    range: '24', // '24' | '168' | 'all'
    filter: 'all', // all | drone | aircraft | other | check
    items: [],
    more: false,
    gen: 0, // bumped when the filters change; older answers are thrown away
    busy: false,
    loadedOnce: false,
    failed: false,
    refreshedAt: 0,
  };

  function logParams() {
    const params = {};
    if (log.range !== 'all') params.hours = log.range;
    if (log.filter === 'check') {
      params.kind = 'check';
    } else {
      params.kind = 'sighting';
      if (log.filter !== 'all') params.category = log.filter;
    }
    return params;
  }

  function sightingCard(item) {
    const c = categoryOf(item);
    const li = el('li');
    const button = el('button', `scard c-${c}`);
    button.type = 'button';
    button.dataset.id = str(item.id);
    button.setAttribute('aria-label', `${describe(item)}. Show details.`);

    const thumb = el('span', 'thumb');
    fillSnapshot(thumb, item, 4 / 3, 'zoom', false);

    const body = el('span', 'scard-body');
    const top = el('span', 'scard-top');
    top.append(badge(item, true), el('span', 'scard-time', clock(item.start)));

    const conf = el('span', 'conf');
    const head = el('span', 'conf-head');
    head.append(el('span', '', 'CONFIDENCE'), el('b', '', isCheck(item) ? '—' : confidence(item.confidence)));
    conf.append(head, meter(isCheck(item) ? 0 : item.confidence));

    const meta = el('span', 'scard-meta');
    const when = isCheck(item) ? `${dayWord(item.start)} · sky check` : `${dayWord(item.start)} · ${duration(item.duration_s)}`;
    meta.append(el('span', '', when), el('span', '', `PAN ${angle(item.pan, 3)} · TILT ${angle(item.tilt, 1)}`));

    body.append(top, conf, meta);
    button.append(thumb, body);
    button.addEventListener('click', () => openDetail(item, button));
    li.append(button);
    return li;
  }

  function logEmptyText() {
    const span = log.range === '24' ? 'in the last 24 hours' : log.range === '168' ? 'in the last 7 days' : 'in the log yet';
    switch (log.filter) {
      case 'drone':
        return [`No drones ${span}.`, 'When the node logs one, it shows up here with its picture.'];
      case 'aircraft':
        return [`No aircraft ${span}.`, 'Planes and helicopters the node follows are logged here.'];
      case 'other':
        return [`Nothing else ${span}.`, 'Other tracked classes, like birds, show up here.'];
      case 'check': {
        const logger = app.config && isObject(app.config.config) && isObject(app.config.config.logger) ? app.config.config.logger : null;
        const every = logger ? num(logger.heartbeat_min) : null;
        if (every === 0) return [`No sky checks ${span}.`, 'Sky checks are turned off (heartbeat_min = 0 in brain/config.toml).'];
        const how = every === 1 ? 'every minute' : every ? `every ${plural(every, 'minute', 'minutes')}` : 'regularly';
        return [`No sky checks ${span}.`, `While nothing is tracked, the node logs a “clear” check ${how}.`];
      }
      default:
        return [`No sightings ${span}.`, 'The node is watching.'];
    }
  }

  function renderLogEmpty() {
    const empty = $('log-empty');
    if (log.items.length && !log.failed) {
      empty.hidden = true;
      return;
    }
    const [title, line] = log.failed ? ['Can’t reach the node right now.', 'The list refreshes when it’s back.'] : logEmptyText();
    empty.replaceChildren(el('span', 'empty-title', title), document.createTextNode(line));
    empty.hidden = log.items.length > 0;
  }

  function renderLogFoot() {
    $('log-foot').hidden = !log.more;
  }

  function updateExportLink() {
    $('export-csv').href = `/api/sightings.csv${query(logParams())}`;
  }

  // mode: 'reset' (filters changed), 'more' (next page), 'refresh' (new ones on top)
  async function loadLog(mode) {
    if (mode !== 'reset' && log.busy) return;
    if (mode === 'reset') log.gen += 1;
    const gen = log.gen;
    const cards = $('log-cards');
    const more = $('log-more');
    log.busy = true;
    log.refreshedAt = Date.now();

    const params = Object.assign(logParams(), { limit: LOG_PAGE });
    const last = log.items[log.items.length - 1];
    if (mode === 'more' && last) params.before = str(last.id);
    if (mode === 'reset') $('log').setAttribute('aria-busy', 'true');
    if (mode === 'more') {
      more.disabled = true;
      setText(more, 'Loading…');
    }

    try {
      const data = await getJSON(`/api/sightings${query(params)}`, 8000);
      if (gen !== log.gen) return; // the filters changed while we waited
      const items = isObject(data) && Array.isArray(data.items) ? data.items.filter(isObject) : [];
      const hasMore = isObject(data) && data.more === true;
      log.failed = false;

      if (mode === 'more') {
        const known = new Set(log.items.map((i) => i.id));
        const fresh = items.filter((i) => !known.has(i.id));
        log.items = log.items.concat(fresh);
        log.more = hasMore;
        cards.append(...fresh.map(sightingCard));
      } else if (mode === 'refresh' && log.items.length) {
        // Only add what's new at the top, so the grid (and your scroll) stays put.
        const known = new Set(log.items.map((i) => i.id));
        const fresh = [];
        for (const item of items) {
          if (known.has(item.id)) break;
          fresh.push(item);
        }
        if (fresh.length === items.length && items.length) {
          log.items = items; // too many new ones to stitch; start over from page one
          log.more = hasMore;
          cards.replaceChildren(...items.map(sightingCard));
        } else if (fresh.length) {
          log.items = fresh.concat(log.items);
          cards.prepend(...fresh.map(sightingCard));
        }
      } else {
        log.items = items;
        log.more = hasMore;
        cards.replaceChildren(...items.map(sightingCard));
      }
      log.loadedOnce = true;
    } catch (error) {
      if (gen !== log.gen) return;
      if (mode !== 'refresh' || !log.items.length) log.failed = true;
      log.loadedOnce = true;
    } finally {
      if (gen === log.gen) {
        log.busy = false;
        $('log').setAttribute('aria-busy', 'false');
        more.disabled = false;
        setText(more, 'Load more');
        renderLogEmpty();
        renderLogFoot();
      }
    }
  }

  function setUpFilters() {
    const pick = (group, attr, onPick) => {
      group.addEventListener('click', (event) => {
        const button = event.target.closest('button');
        if (!button || button.getAttribute('aria-pressed') === 'true') return;
        for (const b of group.querySelectorAll('button')) b.setAttribute('aria-pressed', String(b === button));
        onPick(button.dataset[attr]);
        updateExportLink();
        loadLog('reset');
      });
    };
    pick($('filter-range'), 'range', (value) => {
      log.range = value;
    });
    pick($('filter-kind'), 'filter', (value) => {
      log.filter = value;
    });
    $('log-more').addEventListener('click', () => loadLog('more'));
    updateExportLink();
  }

  // ---------------------------------------------------------------------------
  // Detail dialog (one sighting)
  // ---------------------------------------------------------------------------
  const detail = $('detail');
  let detailOpener = null;

  function fact(label, value, wide) {
    const box = el('div', `fact${wide ? ' fact--wide' : ''}`);
    box.append(el('dt', '', label), el('dd', '', value));
    return box;
  }

  function openDetail(item, opener) {
    const check = isCheck(item);
    const c = categoryOf(item);
    $('detail-badge').replaceChildren(badge(item, true));
    const className = str(item.class_name);
    setText($('detail-title'), check ? 'Sky check' : capitalise(className) || 'Sighting');

    const media = $('detail-media');
    media.className = 'detail-media';
    const name = fillSnapshot(media, item, 16 / 9, 'contain', true);
    if (!name) {
      media.append(el('p', 'detail-media-msg', check ? 'Sky checks don’t save a picture.' : 'No picture was saved for this sighting.'));
    }

    const frames = num(item.frames);
    const categoryText = check ? 'Clear (sky check)' : capitalise(c);
    $('detail-facts').replaceChildren(
      fact('CLASS', className || '—'),
      fact('CATEGORY', categoryText),
      fact('STARTED', fullDateTime(item.start), true),
      fact('ENDED', check ? '—' : clock(item.end)),
      fact('DURATION', check ? '—' : duration(item.duration_s)),
      fact('PEAK CONFIDENCE', check ? '—' : confidence(item.confidence)),
      fact('FRAMES', check || frames === null ? '—' : String(Math.round(frames))),
      fact('PAN', angle(item.pan, 3)),
      fact('TILT', angle(item.tilt, 1)),
      fact('ID', str(item.id) || '—', true)
    );

    const raw = $('detail-raw');
    raw.hidden = !name;
    if (name) raw.href = `/snapshots/${encodeURIComponent(name)}`;
    setText($('detail-when'), `${dayWord(item.start)} · ${clock(item.start)}`);
    setText($('detail-note'), check ? 'Logged while nothing was tracked.' : 'The box shows where it was on the most confident frame.');

    detailOpener = opener || null;
    if (typeof detail.showModal === 'function') detail.showModal();
    else detail.setAttribute('open', '');
    $('detail-close').focus();
  }

  function setUpDetail() {
    $('detail-close').addEventListener('click', () => detail.close());
    // A click on the dimmed area around the dialog closes it.
    detail.addEventListener('click', (event) => {
      if (event.target !== detail) return;
      const r = detail.getBoundingClientRect();
      const inside = event.clientX >= r.left && event.clientX <= r.right && event.clientY >= r.top && event.clientY <= r.bottom;
      if (!inside) detail.close();
    });
    detail.addEventListener('close', () => {
      $('detail-media').replaceChildren(); // stop loading the big picture
      // Give focus back to the row or card that opened it. The list may have
      // been redrawn meanwhile, so look it up again by its id if needed.
      let back = detailOpener;
      if (back && !document.contains(back) && back.dataset.id) {
        back = document.querySelector(`.${back.classList[0]}[data-id="${CSS.escape(back.dataset.id)}"]`);
      }
      if (back && document.contains(back)) back.focus();
      detailOpener = null;
    });
  }

  // ---------------------------------------------------------------------------
  // Nodes tab
  // ---------------------------------------------------------------------------
  function renderNode() {
    const state = app.state || {};
    const node = isObject(state.node) ? state.node : {};
    const live = app.online && isObject(state.live) ? state.live : null;
    const status = nodeStatus();
    const card = $('node-card');
    if (card.dataset.state !== status) card.dataset.state = status;
    renderPill($('node-pill'), $('node-pill-text'));

    setText($('node-name'), str(node.name) || 'NODE-01');
    setText($('node-location'), str(node.location).trim() || 'No location set');
    const away = app.reachable === false;
    setText($('nf-uptime'), away ? '—' : uptime(node.uptime_s));
    setText($('nf-watch'), percent(node.watch_ratio));
    const fps = live ? num(live.fps) : null;
    setText($('nf-fps'), fps === null ? '—' : `${fps.toFixed(1)} fps`);
    const size = live && Array.isArray(live.frame_size) ? live.frame_size.map(num) : [];
    setText($('nf-size'), size[0] && size[1] ? `${Math.round(size[0])} × ${Math.round(size[1])}` : '—');
    setText($('nf-model'), str(node.model) || '—');
    const classes = Array.isArray(node.target_classes) ? node.target_classes.map(str).filter(Boolean) : [];
    setText($('nf-classes'), classes.length ? classes.join(', ') : '—');
    setText($('nf-camera'), str(node.camera) || '—');
    setText($('nf-link'), str((live && live.link) || node.link) || '—');

    let foot = ' ';
    if (away && app.lastHeard) foot = `Can’t reach the node. Last heard from at ${clock(app.lastHeard)}.`;
    else if (away) foot = 'Can’t reach the node.';
    else if (num(node.started_at) !== null) {
      foot = `Started ${dayWord(node.started_at)} at ${hhmm(node.started_at)}`;
      if (live && num(live.frame_time) !== null) foot += ` · last frame ${clock(live.frame_time)}`;
      else if (!app.online) foot += ' · no frames from the camera right now';
    }
    setText($('node-foot'), foot);
  }

  // ---------------------------------------------------------------------------
  // Settings tab (read-only view of brain/config.toml after defaults)
  // ---------------------------------------------------------------------------
  const SECTION_ORDER = ['camera', 'model', 'tracker', 'control', 'link', 'logger', 'dashboard'];
  const SECTION_TITLES = {
    camera: 'Camera',
    model: 'Model',
    tracker: 'Tracker',
    control: 'Control',
    link: 'Link to the Pico',
    logger: 'Sighting log',
    dashboard: 'Dashboard',
    display: 'Preview window',
  };

  // Show values the way config.toml writes them: "text", 12.5, true, [a, b].
  function tomlValue(value) {
    if (typeof value === 'string') return JSON.stringify(value);
    if (typeof value === 'number') return Number.isFinite(value) ? String(value) : '—';
    if (typeof value === 'boolean') return String(value);
    if (value === null || value === undefined) return '—';
    if (Array.isArray(value)) return `[${value.map(tomlValue).join(', ')}]`;
    return JSON.stringify(value);
  }

  function settingRows(values, prefix) {
    const rows = [];
    for (const [key, value] of Object.entries(values)) {
      if (isObject(value)) {
        rows.push(...settingRows(value, `${prefix}${key}.`));
        continue;
      }
      const row = el('div', 'set-row');
      row.append(el('dt', '', prefix + key), el('dd', typeof value === 'string' ? 'is-str' : '', tomlValue(value)));
      rows.push(row);
    }
    return rows;
  }

  let settingsCards = [];
  let settingsColumns = 0;

  // Masonry: drop each section into the currently shortest column, so cards of
  // different heights pack without gaps.
  function layoutSettings() {
    const width = document.querySelector('.page').clientWidth;
    const columns = width >= 1180 ? 3 : width >= 760 ? 2 : 1;
    if (columns === settingsColumns || !settingsCards.length) return;
    settingsColumns = columns;
    const stacks = [];
    const heights = [];
    for (let i = 0; i < columns; i += 1) {
      stacks.push(el('div', 'set-col'));
      heights.push(0);
    }
    for (const card of settingsCards) {
      const shortest = heights.indexOf(Math.min(...heights));
      stacks[shortest].append(card);
      heights[shortest] += Number(card.dataset.weight);
    }
    const holder = $('settings-grid');
    holder.style.setProperty('--cols', String(columns));
    holder.replaceChildren(...stacks);
  }

  function renderSettings() {
    const holder = $('settings-grid');
    const empty = $('settings-empty');
    const config = app.config && isObject(app.config.config) ? app.config.config : null;
    if (!config || !Object.keys(config).length) {
      holder.replaceChildren();
      settingsCards = [];
      empty.hidden = false;
      setText(empty, app.config ? 'No settings to show.' : 'Can’t load the settings right now.');
      return;
    }
    const names = Object.keys(config).filter((k) => isObject(config[k]));
    names.sort((a, b) => {
      const ia = SECTION_ORDER.indexOf(a);
      const ib = SECTION_ORDER.indexOf(b);
      return (ia < 0 ? 99 : ia) - (ib < 0 ? 99 : ib) || a.localeCompare(b);
    });
    settingsCards = names.map((name) => {
      const card = el('section', 'card set-card glass glass--flat');
      const title = el('h3', 'set-title', SECTION_TITLES[name] || capitalise(name));
      title.append(el('span', '', `[${name}]`));
      const list = el('dl');
      list.append(...settingRows(config[name], ''));
      card.append(title, list);
      card.dataset.weight = String(list.children.length + 3); // rough height, in rows
      return card;
    });
    settingsColumns = 0;
    layoutSettings();
    empty.hidden = true;
  }

  async function loadConfig() {
    app.configAt = Date.now();
    try {
      const data = await getJSON('/api/config');
      if (isObject(data)) app.config = data;
    } catch (error) {
      // keep whatever we had
    }
    renderSettings();
    if (app.tab === 'sightings') renderLogEmpty(); // the sky-check note reads the logger settings
  }

  // ---------------------------------------------------------------------------
  // Start
  // ---------------------------------------------------------------------------
  function start() {
    setUpTabs();
    setUpChartToggle();
    setUpFilters();
    setUpDetail();
    buildColumns();
    renderChart();
    renderHeader();
    renderFrame();
    showTab(tabFromHash());

    // Pause while the tab is hidden; catch up straight away when it's back.
    document.addEventListener('visibilitychange', () => {
      syncStream();
      if (!document.hidden) {
        scheduleState(0);
        app.recentAt = 0;
        app.statsAt = 0;
        slowTick();
      }
    });
    window.addEventListener('resize', () => {
      if (chart.active >= 0) showTip(chart.active);
      layoutSettings();
    });
    setInterval(slowTick, 1000);
    pollState();
  }

  start();
})();
