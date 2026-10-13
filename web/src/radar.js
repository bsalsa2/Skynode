// Simulated radar view (labelled SAMPLE on the page). A slow sweep over a
// polar grid; blips brighten as the beam passes and fade after. The blips are
// made up: an aircraft on a straight track and a possible drone that loiters.
//
// Restrained on purpose: one canvas, drawn only while on screen, and a single
// still frame (no sweep) for visitors who turn off motion.

const TAU = Math.PI * 2;

export function createRadar({ root, reduceMotion }) {
  const canvas = root.querySelector('canvas');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  const css = getComputedStyle(document.documentElement);
  const color = (name, fallback) => css.getPropertyValue(name).trim() || fallback;
  const C = {
    line: color('--varn-steel-blue', '#4b5b6b'),
    beam: color('--varn-fog', '#a7b3bd'),
    aircraft: color('--varn-sage', '#7a8b7e'),
    drone: color('--varn-amber', '#e0a84a'),
    text: color('--varn-fog', '#a7b3bd'),
  };

  // Targets in polar-ish world units (0..1 of the radius).
  const targets = [
    { kind: 'aircraft', label: 'AIRCRAFT', x: -0.8, y: -0.35, vx: 0.022, vy: 0.006, lit: 0 },
    { kind: 'drone', label: 'DRONE?', cx: 0.32, cy: 0.18, r: 0.07, a: 0, x: 0, y: 0, lit: 0 },
  ];
  let angle = -Math.PI / 2;
  let size = 0;
  let dpr = 1;

  function resize() {
    dpr = Math.min(window.devicePixelRatio || 1, 2);
    size = canvas.clientWidth;
    canvas.width = canvas.height = Math.round(size * dpr);
  }

  function move(dt) {
    for (const t of targets) {
      if (t.kind === 'aircraft') {
        t.x += t.vx * dt;
        t.y += t.vy * dt;
        if (t.x > 0.9) Object.assign(t, { x: -0.85, y: -0.3 - Math.random() * 0.3 });
      } else {
        t.a += dt * 0.35;
        t.x = t.cx + Math.cos(t.a) * t.r;
        t.y = t.cy + Math.sin(t.a * 1.3) * t.r * 0.7;
      }
    }
  }

  function draw(dt) {
    const s = size;
    const R = s / 2 - 6;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, s, s);
    ctx.save();
    ctx.translate(s / 2, s / 2);

    // Grid: rings, cross, compass ticks
    ctx.strokeStyle = C.line;
    ctx.lineWidth = 1;
    ctx.globalAlpha = 0.7;
    for (const f of [1, 0.66, 0.33]) {
      ctx.beginPath();
      ctx.arc(0, 0, R * f, 0, TAU);
      ctx.stroke();
    }
    ctx.beginPath();
    ctx.moveTo(-R, 0);
    ctx.lineTo(R, 0);
    ctx.moveTo(0, -R);
    ctx.lineTo(0, R);
    ctx.globalAlpha = 0.35;
    ctx.stroke();

    // Sweep: a thin leading edge and a short fading wedge behind it
    if (!reduceMotion) {
      const wedge = 0.5;
      const grad = ctx.createConicGradient ? ctx.createConicGradient(angle - wedge, 0, 0) : null;
      if (grad) {
        grad.addColorStop(0, 'rgba(167,179,189,0)');
        grad.addColorStop(wedge / TAU, 'rgba(167,179,189,0.16)');
        grad.addColorStop(wedge / TAU + 0.0001, 'rgba(167,179,189,0)');
        ctx.globalAlpha = 1;
        ctx.fillStyle = grad;
        ctx.beginPath();
        ctx.moveTo(0, 0);
        ctx.arc(0, 0, R, angle - wedge, angle);
        ctx.closePath();
        ctx.fill();
      }
      ctx.strokeStyle = C.beam;
      ctx.globalAlpha = 0.6;
      ctx.beginPath();
      ctx.moveTo(0, 0);
      ctx.lineTo(Math.cos(angle) * R, Math.sin(angle) * R);
      ctx.stroke();
    }

    // Blips: lit when the beam crosses them, then fade (always visible a little)
    ctx.font = `500 10px "Geist Mono", ui-monospace, monospace`;
    for (const t of targets) {
      const a = Math.atan2(t.y, t.x);
      const diff = (((angle - a) % TAU) + TAU) % TAU;
      if (reduceMotion) t.lit = 1;
      else if (diff < 0.08) t.lit = 1;
      else t.lit = Math.max(0, t.lit - dt * 0.45);
      const px = t.x * R;
      const py = t.y * R;
      const alpha = 0.45 + 0.55 * t.lit;
      ctx.globalAlpha = alpha;
      ctx.fillStyle = C[t.kind];
      ctx.strokeStyle = C[t.kind];
      // Shapes match the status key: circle = aircraft, square = possible drone
      if (t.kind === 'aircraft') {
        ctx.beginPath();
        ctx.arc(px, py, 3.5, 0, TAU);
        ctx.fill();
      } else {
        ctx.fillRect(px - 3.5, py - 3.5, 7, 7);
      }
      ctx.globalAlpha = alpha * 0.9;
      ctx.fillStyle = C.text;
      ctx.fillText(t.label, px + 8, py - 6);
    }
    ctx.restore();
  }

  resize();
  move(0);
  draw(0);
  if (reduceMotion) return;

  let raf = 0;
  let last = 0;
  const frame = (now) => {
    const dt = Math.min(0.05, (now - (last || now)) / 1000);
    last = now;
    angle = (angle + dt * 1.1) % TAU;
    move(dt);
    draw(dt);
    raf = requestAnimationFrame(frame);
  };
  // Only animate while visible.
  new IntersectionObserver(([e]) => {
    cancelAnimationFrame(raf);
    last = 0;
    if (e.isIntersecting) raf = requestAnimationFrame(frame);
  }).observe(canvas);
  window.addEventListener('resize', () => {
    resize();
    draw(0);
  });
}
