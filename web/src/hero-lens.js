// The hero lens: a simulated sky view drawn on a canvas, labelled SAMPLE.
// Three short scenes loop, and the glass sighting card beside it follows:
//
//   1. an aircraft crosses            -> CONFIRMED AIRCRAFT  (circle)
//   2. a drone hovers and wanders     -> POSSIBLE DRONE      (square)
//   3. an aircraft with no broadcast  -> NO ADS-B MATCH      (ring)
//
// Nothing here is a real detection. Brackets (not crosshairs) frame the target;
// the shapes match the status shapes used everywhere else on the page.

const TAU = Math.PI * 2;
const clamp = (v, a, b) => Math.min(b, Math.max(a, v));
const lerp = (a, b, t) => a + (b - a) * t;
const ease = (t) => t * t * (3 - 2 * t);

const COLORS = {
  aircraft: '#7A8B7E',
  drone: '#E0A84A',
  'no-adsb': '#A7B3BD',
};
const LABELS = {
  aircraft: 'Confirmed aircraft',
  drone: 'Possible drone',
  'no-adsb': 'No ADS-B match',
};

// Each scene: how long it runs, the status it ends up with, and the path of
// the target through the lens (u = 0..1 through the scene, result in -1..1).
const SCENES = [
  {
    kind: 'aircraft',
    cls: 'aircraft',
    conf: 0.91,
    adsb: 'match',
    len: 7,
    path: (u) => ({ x: lerp(-1.05, 1.05, u), y: -0.38 + Math.sin(u * 2.2) * 0.1 }),
    speck: 3.2,
  },
  {
    kind: 'drone',
    cls: 'drone',
    conf: 0.64,
    adsb: '—',
    len: 8,
    path: (u) => ({
      x: 0.12 + Math.sin(u * 5.1) * 0.34 + Math.sin(u * 11.3) * 0.04,
      y: 0.12 + Math.sin(u * 3.7 + 1) * 0.2 + Math.cos(u * 9.1) * 0.03,
    }),
    speck: 3.6,
  },
  {
    kind: 'no-adsb',
    cls: 'aircraft',
    conf: 0.78,
    adsb: 'none',
    len: 7,
    path: (u) => ({ x: lerp(1.05, -1.05, u), y: 0.3 - Math.sin(u * 2.6) * 0.18 }),
    speck: 3,
  },
];

const pad = (n) => String(n).padStart(2, '0');

export function createLens({ lens, canvas, card, reduceMotion }) {
  const ctx = canvas.getContext('2d');
  if (!ctx) return null;
  let w = 0;
  let h = 0;
  let dpr = 1;
  let raf = 0;
  let running = false;
  let last = 0;
  let clock = 0; // seconds into the loop
  let sceneIndex = -1;
  const box = { x: 0, y: 0, a: 0 }; // eased bracket position + alpha
  const trail = [];
  const pointer = { x: 0, y: 0 }; // -1..1, nudges the parallax of the rings
  let pointerEase = { x: 0, y: 0 };

  const hud = card
    ? {
        pill: card.querySelector('[data-card="pill"]'),
        pillText: card.querySelector('[data-card="pill-text"]'),
        shape: card.querySelector('[data-card="pill"] .shape'),
        time: card.querySelector('[data-card="time"]'),
        cls: card.querySelector('[data-card="class"]'),
        conf: card.querySelector('[data-card="conf"]'),
        adsb: card.querySelector('[data-card="adsb"]'),
      }
    : null;

  // Fake "UTC" clock for the card: starts where the static markup does.
  let clockBase = 14 * 3600 + 32 * 60 + 7;
  const stamp = (offset) => {
    const t = (clockBase + Math.floor(offset)) % 86400;
    return `${pad(Math.floor(t / 3600))}:${pad(Math.floor((t % 3600) / 60))}:${pad(t % 60)}Z`;
  };

  function applyCard(scene) {
    if (!hud || !hud.pill) return;
    const k = scene.kind;
    hud.pill.className = `status-pill status-pill--${k} mono`;
    hud.shape.className = `shape shape--${k}`;
    hud.pillText.textContent = LABELS[k];
    hud.cls.textContent = scene.cls;
    hud.conf.textContent = scene.conf.toFixed(2);
    hud.adsb.textContent = scene.adsb;
    hud.adsb.className = `sighting-adsb sighting-adsb--${k}`;
    card.classList.remove('is-swap');
    // restart the little swap animation
    void card.offsetWidth;
    card.classList.add('is-swap');
  }

  function resize() {
    dpr = Math.min(window.devicePixelRatio || 1, 2);
    const r = canvas.getBoundingClientRect();
    w = Math.max(1, r.width);
    h = Math.max(1, r.height);
    canvas.width = Math.round(w * dpr);
    canvas.height = Math.round(h * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }

  function sceneAt(t) {
    let acc = 0;
    for (let i = 0; i < SCENES.length; i++) {
      if (t < acc + SCENES[i].len) return { i, u: (t - acc) / SCENES[i].len };
      acc += SCENES[i].len;
    }
    return { i: 0, u: 0 };
  }
  const total = SCENES.reduce((a, s) => a + s.len, 0);

  function brackets(cx, cy, r, color, alpha) {
    const l = r * 0.42;
    ctx.save();
    ctx.globalAlpha = alpha;
    ctx.strokeStyle = color;
    ctx.lineWidth = 1.6;
    ctx.lineCap = 'round';
    ctx.beginPath();
    for (const [sx, sy] of [
      [-1, -1],
      [1, -1],
      [1, 1],
      [-1, 1],
    ]) {
      const x = cx + sx * r;
      const y = cy + sy * r;
      ctx.moveTo(x, y - sy * l);
      ctx.lineTo(x, y);
      ctx.lineTo(x - sx * l, y);
    }
    ctx.stroke();
    ctx.restore();
  }

  function glyph(kind, x, y, s, color) {
    ctx.save();
    ctx.fillStyle = color;
    ctx.strokeStyle = color;
    if (kind === 'drone') {
      const r = 2;
      ctx.beginPath();
      ctx.roundRect(x - s, y - s, s * 2, s * 2, r);
      ctx.fill();
    } else if (kind === 'no-adsb') {
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.arc(x, y, s, 0, TAU);
      ctx.stroke();
    } else {
      ctx.beginPath();
      ctx.arc(x, y, s, 0, TAU);
      ctx.fill();
    }
    ctx.restore();
  }

  function draw(dt) {
    ctx.clearRect(0, 0, w, h);
    const cx = w / 2;
    const cy = h / 2;
    const R = Math.min(w, h) / 2;
    pointerEase.x += (pointer.x - pointerEase.x) * Math.min(1, dt * 4);
    pointerEase.y += (pointer.y - pointerEase.y) * Math.min(1, dt * 4);

    // Range rings: faint, drifting a little with the pointer.
    ctx.save();
    ctx.translate(pointerEase.x * 8, pointerEase.y * 8);
    ctx.strokeStyle = 'rgba(244,243,239,0.07)';
    ctx.lineWidth = 1;
    for (let i = 1; i <= 4; i++) {
      ctx.beginPath();
      ctx.arc(cx, cy, (R * i) / 4.4, 0, TAU);
      ctx.stroke();
    }
    ctx.restore();
    // Horizon line.
    ctx.strokeStyle = 'rgba(244,243,239,0.1)';
    ctx.beginPath();
    ctx.moveTo(cx - R, cy + R * 0.62);
    ctx.lineTo(cx + R, cy + R * 0.62);
    ctx.stroke();

    const { i, u } = sceneAt(clock % total);
    const scene = SCENES[i];
    if (i !== sceneIndex) {
      sceneIndex = i;
      trail.length = 0;
      applyCard(scene);
      if (hud && hud.time) hud.time.textContent = stamp(clock);
    }

    // Fade in/out at the ends of each scene.
    const vis = clamp(Math.min(u / 0.1, (1 - u) / 0.1), 0, 1);
    const p = scene.path(u);
    const tx = cx + p.x * R * 0.78;
    const ty = cy + p.y * R * 0.78;
    const color = COLORS[scene.kind];

    // Trail
    trail.push({ x: tx, y: ty, t: clock });
    while (trail.length && clock - trail[0].t > 2.2) trail.shift();
    for (const q of trail) {
      const a = clamp(1 - (clock - q.t) / 2.2, 0, 1) * 0.5 * vis;
      ctx.fillStyle = color;
      ctx.globalAlpha = a;
      ctx.beginPath();
      ctx.arc(q.x, q.y, 1.6, 0, TAU);
      ctx.fill();
    }
    ctx.globalAlpha = 1;

    // The target: a small bright speck with a soft glow.
    const glow = ctx.createRadialGradient(tx, ty, 0, tx, ty, 26);
    glow.addColorStop(0, color + '55');
    glow.addColorStop(1, color + '00');
    ctx.globalAlpha = vis;
    ctx.fillStyle = glow;
    ctx.beginPath();
    ctx.arc(tx, ty, 26, 0, TAU);
    ctx.fill();
    ctx.fillStyle = '#F4F3EF';
    ctx.beginPath();
    ctx.arc(tx, ty, scene.speck, 0, TAU);
    ctx.fill();
    ctx.globalAlpha = 1;

    // Bracket lags behind the target, like a tracker catching up.
    const detected = u > 0.14 && u < 0.92;
    box.a += ((detected ? 1 : 0) - box.a) * Math.min(1, dt * 6);
    if (box.a < 0.02 && !detected) {
      box.x = tx;
      box.y = ty;
    } else {
      box.x += (tx - box.x) * Math.min(1, dt * 7);
      box.y += (ty - box.y) * Math.min(1, dt * 7);
    }
    const bs = 22 + Math.sin(clock * 3) * 0.8;
    brackets(box.x, box.y, bs, color, box.a * vis);

    // Label chip above the bracket.
    if (box.a > 0.05) {
      const text = `${scene.cls.toUpperCase()} ${scene.conf.toFixed(2)}`;
      ctx.font = '500 11px "Geist Mono", ui-monospace, monospace';
      const tw = ctx.measureText(text).width;
      const lx = clamp(box.x - bs, 10, w - tw - 40);
      const ly = clamp(box.y - bs - 12, 20, h - 20);
      ctx.save();
      ctx.globalAlpha = box.a * vis;
      ctx.fillStyle = 'rgba(11,15,20,0.78)';
      ctx.strokeStyle = color + '66';
      ctx.beginPath();
      ctx.roundRect(lx, ly - 13, tw + 30, 22, 11);
      ctx.fill();
      ctx.stroke();
      glyph(scene.kind, lx + 13, ly - 2, 4, color);
      ctx.fillStyle = color;
      ctx.textBaseline = 'middle';
      ctx.fillText(text, lx + 24, ly - 1.5);
      ctx.restore();
    }

    // Keep the card clock moving.
    if (hud && hud.time && Math.floor(clock * 2) % 2 === 0) hud.time.textContent = stamp(clock);
  }

  function frame(now) {
    if (!running) return;
    const dt = Math.min(0.05, (now - last) / 1000 || 0.016);
    last = now;
    clock += dt;
    draw(dt);
    raf = requestAnimationFrame(frame);
  }

  function start() {
    if (running || reduceMotion) return;
    running = true;
    last = performance.now();
    raf = requestAnimationFrame(frame);
  }
  function stop() {
    running = false;
    cancelAnimationFrame(raf);
  }

  resize();
  new ResizeObserver(() => {
    resize();
    if (!running) draw(0.016);
  }).observe(canvas);

  if (reduceMotion) {
    // One still frame: the aircraft mid-crossing, bracket in place.
    clock = 3.4;
    box.a = 1;
    const s = SCENES[0].path(3.4 / SCENES[0].len);
    box.x = w / 2 + s.x * (Math.min(w, h) / 2) * 0.78;
    box.y = h / 2 + s.y * (Math.min(w, h) / 2) * 0.78;
    draw(1);
  } else {
    // Only run while visible and the tab is showing.
    let visible = false;
    const io = new IntersectionObserver(
      ([e]) => {
        visible = e.isIntersecting;
        if (visible && !document.hidden) start();
        else stop();
      },
      { threshold: 0.05 }
    );
    io.observe(lens);
    document.addEventListener('visibilitychange', () => (document.hidden || !visible ? stop() : start()));
    lens.addEventListener('pointermove', (e) => {
      const r = lens.getBoundingClientRect();
      pointer.x = ((e.clientX - r.left) / r.width - 0.5) * 2;
      pointer.y = ((e.clientY - r.top) / r.height - 0.5) * 2;
    });
    lens.addEventListener('pointerleave', () => {
      pointer.x = 0;
      pointer.y = 0;
    });
  }
  return { start, stop };
}
