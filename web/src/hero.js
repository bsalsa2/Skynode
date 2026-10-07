// Hero sky, concept only. Twinkling stars, and every so often a small
// aircraft crosses high above the horizon. The node acquires it: a 1.5 px
// aircraft-blue box closes in, trails it with a little servo lag, and the
// glass readout card shows the pan/tilt it would command to follow.
//
// Plain 2D canvas, no libraries. Pauses whenever the hero is off screen or
// the tab is hidden. With reduced motion it draws one still frame.

const AIRCRAFT = '#8FD3FF';
const AIRCRAFT_ON = '#04141E';
const TAU = Math.PI * 2;

const rand = (a, b) => a + Math.random() * (b - a);
const clamp = (v, a, b) => Math.min(b, Math.max(a, v));
const smooth = (x) => x * x * (3 - 2 * x);

export function createHeroSky({ hero, canvas, card, reduceMotion, finePointer }) {
  const ctx = canvas.getContext('2d');
  if (!ctx) return;
  const parallax = [
    [hero.querySelector('.moon'), 18],
    [hero.querySelector('.stars'), 6],
    [hero.querySelector('.planet-body'), 8],
  ].filter(([el]) => el);

  // Readout card fields.
  const out = card
    ? {
        conf: card.querySelector('[data-hud="conf"]'),
        pan: card.querySelector('[data-hud="pan"]'),
        tilt: card.querySelector('[data-hud="tilt"]'),
        cmd: card.querySelector('[data-hud="cmd"]'),
      }
    : null;
  const spark = card?.querySelector('#hud-spark');
  const sctx = spark?.getContext('2d');

  let w = 0;
  let h = 0;
  let dpr = 1;
  let stars = [];

  function layout() {
    const r = hero.getBoundingClientRect();
    w = Math.max(1, r.width);
    h = Math.max(1, r.height);
    dpr = Math.min(window.devicePixelRatio || 1, 2);
    canvas.width = Math.round(w * dpr);
    canvas.height = Math.round(h * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    // Stars live in the sky above the horizon; denser near the top.
    const count = Math.round(clamp((w * h) / 7000, 60, 260));
    stars = Array.from({ length: count }, () => ({
      x: Math.random() * w,
      y: Math.pow(Math.random(), 1.6) * h * 0.72,
      r: 0.35 + Math.pow(Math.random(), 5) * 1.25,
      a: 0.25 + Math.random() * 0.6,
      f: 0.3 + Math.random() * 1.1,
      p: Math.random() * TAU,
    }));
    if (spark) {
      const sr = spark.getBoundingClientRect();
      spark.width = Math.round(sr.width * dpr);
      spark.height = Math.round(sr.height * dpr);
    }
  }

  // ---- The pass: one aircraft crossing, then a quiet gap ------------------
  let pass = null;
  let gap = reduceMotion ? 0 : 1.2;
  function newPass() {
    const ltr = Math.random() < 0.6;
    const yTop = clamp(h * 0.08, 96, 150);
    const y0 = rand(yTop, yTop + Math.min(90, h * 0.08));
    return {
      t: 0,
      dur: rand(26, 34), // seconds to cross the full width
      ltr,
      y0,
      lift: rand(-30, 26), // gentle arc
      strobe: rand(0, 1),
      lock: 0, // 0..1 lock-on progress
      box: null,
    };
  }
  const passPos = (p, t) => {
    const u = t / p.dur;
    const x = p.ltr ? -40 + u * (w + 80) : w + 40 - u * (w + 80);
    const y = p.y0 - Math.sin(u * Math.PI) * p.lift;
    return { x, y, u };
  };

  // ---- Readout: what the node would command to follow the target --------
  const rest = { pan: 92.5, tilt: 47.0 };
  const ro = { pan: rest.pan, tilt: rest.tilt, conf: 0.97 };
  const history = [];
  let readoutClock = 0;
  let confNoise = 0;

  function aimAt(x, y) {
    // The node sits on the horizon, centre-left of the hero, looking up.
    const nodeX = w * 0.5;
    const nodeY = h * 0.68;
    const pan = 90 + ((x - nodeX) / Math.max(w, 1)) * 110;
    const tilt = clamp((Math.atan2(nodeY - y, Math.abs(x - nodeX) + h * 0.35) * 180) / Math.PI, 8, 82);
    return { pan, tilt };
  }

  function writeReadout() {
    if (!out) return;
    out.conf.textContent = ro.conf.toFixed(2);
    out.pan.textContent = `${ro.pan.toFixed(1).padStart(5, '0')}°`;
    out.tilt.textContent = `${ro.tilt.toFixed(1)}°`;
    out.cmd.textContent = `P${ro.pan.toFixed(1)} T${Math.round(ro.tilt)}`;
  }

  function drawSpark() {
    if (!sctx) return;
    const W = spark.width;
    const H = spark.height;
    sctx.clearRect(0, 0, W, H);
    if (history.length < 2) return;
    // Baseline
    sctx.strokeStyle = 'rgba(255,255,255,0.08)';
    sctx.lineWidth = 1;
    sctx.beginPath();
    sctx.moveTo(0, H - 0.5);
    sctx.lineTo(W, H - 0.5);
    sctx.stroke();
    // Tilt trace, fading out to the left.
    const grad = sctx.createLinearGradient(0, 0, W, 0);
    grad.addColorStop(0, 'rgba(255,255,255,0)');
    grad.addColorStop(1, 'rgba(255,255,255,0.85)');
    sctx.strokeStyle = grad;
    sctx.lineWidth = 1.25 * dpr;
    sctx.lineJoin = 'round';
    sctx.beginPath();
    // Newest sample at the right edge; older ones scroll off to the left.
    const n = 90;
    const start = Math.max(0, history.length - n);
    const xAt = (i) => W - ((history.length - 1 - i) / (n - 1)) * W;
    for (let i = start; i < history.length; i++) {
      const x = xAt(i);
      const y = H - 3 * dpr - ((history[i] - 20) / 45) * (H - 6 * dpr);
      if (i === start) sctx.moveTo(x, y);
      else sctx.lineTo(x, y);
    }
    sctx.stroke();
    const lx = xAt(history.length - 1) - 2 * dpr;
    const ly = H - 3 * dpr - ((history[history.length - 1] - 20) / 45) * (H - 6 * dpr);
    sctx.fillStyle = '#fff';
    sctx.beginPath();
    sctx.arc(lx, ly, 2 * dpr, 0, TAU);
    sctx.fill();
  }

  // ---- Drawing ------------------------------------------------------------
  function roundRect(x, y, bw, bh, r) {
    ctx.beginPath();
    ctx.moveTo(x + r, y);
    ctx.arcTo(x + bw, y, x + bw, y + bh, r);
    ctx.arcTo(x + bw, y + bh, x, y + bh, r);
    ctx.arcTo(x, y + bh, x, y, r);
    ctx.arcTo(x, y, x + bw, y, r);
    ctx.closePath();
  }

  let time = 0;
  function draw(dt) {
    time += dt;
    ctx.clearRect(0, 0, w, h);

    // Stars
    for (const s of stars) {
      const a = s.a * (0.55 + 0.45 * Math.sin(time * s.f + s.p));
      ctx.globalAlpha = a;
      ctx.fillStyle = '#fff';
      ctx.beginPath();
      ctx.arc(s.x, s.y, s.r, 0, TAU);
      ctx.fill();
    }
    ctx.globalAlpha = 1;

    // Aircraft pass
    if (!pass) {
      gap -= dt;
      if (gap <= 0) pass = newPass();
    }
    let target = null;
    if (pass) {
      pass.t += dt;
      const { x, y, u } = passPos(pass, pass.t);
      if (u > 1) {
        pass = null;
        gap = rand(3, 6);
      } else {
        // Craft: a steady white light and a strobe.
        const strobePhase = (time + pass.strobe) % 1.3;
        const flash = strobePhase < 0.08 ? 1 - strobePhase / 0.08 : 0;
        ctx.fillStyle = 'rgba(255,255,255,0.95)';
        ctx.beginPath();
        ctx.arc(x, y, 1.6, 0, TAU);
        ctx.fill();
        if (flash > 0) {
          const g = ctx.createRadialGradient(x, y, 0, x, y, 14);
          g.addColorStop(0, `rgba(255,255,255,${0.9 * flash})`);
          g.addColorStop(1, 'rgba(255,255,255,0)');
          ctx.fillStyle = g;
          ctx.beginPath();
          ctx.arc(x, y, 14, 0, TAU);
          ctx.fill();
        }

        // Lock: acquire once it's properly in view, release near the edge.
        const inView = x > w * 0.06 && x < w * 0.94;
        pass.lock = clamp(pass.lock + (inView ? dt / 0.9 : -dt / 0.5), 0, 1);
        if (!pass.box) pass.box = { x, y };
        const k = 1 - Math.exp(-dt * 5.5); // servo lag
        pass.box.x += (x - pass.box.x) * k;
        pass.box.y += (y - pass.box.y) * k;

        if (pass.lock > 0) {
          const e = smooth(pass.lock);
          const s = 1 + (1 - e) * 1.4; // closes in while acquiring
          const bw = 34 * s;
          const bh = 24 * s;
          const bx = pass.box.x - bw / 2;
          const by = pass.box.y - bh / 2;
          ctx.globalAlpha = e;
          ctx.save();
          ctx.shadowColor = 'rgba(143,211,255,0.55)';
          ctx.shadowBlur = 14;
          ctx.strokeStyle = AIRCRAFT;
          ctx.lineWidth = 1.5;
          roundRect(bx, by, bw, bh, 3);
          ctx.stroke();
          ctx.restore();

          if (e > 0.6) {
            const label = `AIRCRAFT ${ro.conf.toFixed(2)}`;
            ctx.font = '500 11px "IBM Plex Mono", ui-monospace, monospace';
            const tw = ctx.measureText(label).width;
            const lx = bx - 0.75;
            const ly = by - 21;
            ctx.globalAlpha = (e - 0.6) / 0.4;
            ctx.fillStyle = AIRCRAFT;
            roundRect(lx, ly, tw + 14, 17, 3);
            ctx.fill();
            ctx.fillStyle = AIRCRAFT_ON;
            ctx.textBaseline = 'middle';
            ctx.fillText(label, lx + 7, ly + 9);
          }
          ctx.globalAlpha = 1;
          if (pass.lock > 0.5) target = pass.box;
        }
      }
    }

    // Readout follows the locked target, or drifts back to rest.
    const goal = target ? aimAt(target.x, target.y) : rest;
    const kk = 1 - Math.exp(-dt * (target ? 3 : 0.8));
    ro.pan += (goal.pan - ro.pan) * kk;
    ro.tilt += (goal.tilt - ro.tilt) * kk;
    confNoise += (rand(-1, 1) - confNoise) * Math.min(1, dt * 2);
    const confGoal = target ? 0.955 + confNoise * 0.02 + (pass ? smooth(pass.lock) * 0.01 : 0) : 0.97;
    ro.conf += (confGoal - ro.conf) * Math.min(1, dt * 3);

    readoutClock += dt;
    if (readoutClock > 0.12 || reduceMotion) {
      readoutClock = 0;
      writeReadout();
      history.push(ro.tilt);
      if (history.length > 200) history.splice(0, history.length - 200);
      drawSpark();
    }
  }

  // ---- Pointer parallax (CSS `translate`, independent of scroll transforms)
  const pointer = { x: 0, y: 0, sx: 0, sy: 0 };
  if (finePointer && !reduceMotion) {
    window.addEventListener(
      'pointermove',
      (e) => {
        pointer.x = (e.clientX / window.innerWidth) * 2 - 1;
        pointer.y = (e.clientY / window.innerHeight) * 2 - 1;
      },
      { passive: true }
    );
  }
  function applyParallax(dt) {
    if (!finePointer || reduceMotion) return;
    const k = 1 - Math.exp(-dt * 2.2);
    pointer.sx += (pointer.x - pointer.sx) * k;
    pointer.sy += (pointer.y - pointer.sy) * k;
    for (const [el, px] of parallax) {
      el.style.translate = `${(-pointer.sx * px).toFixed(2)}px ${(-pointer.sy * px * 0.6).toFixed(2)}px`;
    }
  }

  // ---- Loop ---------------------------------------------------------------
  let onScreen = true;
  let running = false;
  let last = 0;
  function frame(now) {
    const dt = Math.min(0.05, (now - last) / 1000);
    last = now;
    draw(dt);
    applyParallax(dt);
    if (onScreen && !document.hidden) requestAnimationFrame(frame);
    else running = false;
  }
  function wake() {
    if (reduceMotion || running || !onScreen || document.hidden) return;
    running = true;
    last = performance.now();
    requestAnimationFrame(frame);
  }

  layout();
  if (reduceMotion) {
    // One still: an aircraft mid-pass, locked.
    pass = newPass();
    pass.t = pass.dur * 0.62;
    pass.lock = 1;
    pass.box = passPos(pass, pass.t);
    draw(0);
  }
  canvas.classList.add('is-ready');

  new IntersectionObserver(([entry]) => {
    onScreen = entry.isIntersecting;
    wake();
  }).observe(hero);
  document.addEventListener('visibilitychange', wake);
  let resizeRaf = 0;
  new ResizeObserver(() => {
    cancelAnimationFrame(resizeRaf);
    resizeRaf = requestAnimationFrame(() => {
      layout();
      if (reduceMotion) draw(0);
    });
  }).observe(hero);
  wake();
}
