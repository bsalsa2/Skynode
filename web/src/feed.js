// The simulated dashboard in "How it works" (labelled SAMPLE FEED on the
// page; every value is made up). The drone box follows a slowly wandering
// drone, the plane drifts across, confidences settle around their sample
// values, and a restrained sweep passes over the radar.
//
// Runs only while the panel is on screen. Under reduced motion it draws one
// still frame of the radar and leaves everything else as rendered.

const TAU = Math.PI * 2;

export function createFeed({ root, reduceMotion }) {
  const drone = root.querySelector('[data-det="drone"]');
  const plane = root.querySelector('[data-det="plane"]');
  const conf = {
    drone: root.querySelector('[data-conf="drone"]'),
    plane: root.querySelector('[data-conf="plane"]'),
    uav: root.querySelector('[data-obj="uav"]'),
    planeRow: root.querySelector('[data-obj="plane"]'),
  };
  const canvas = root.querySelector('canvas.radar');
  const ctx = canvas && canvas.getContext('2d');

  // Radar blips in unit-circle coordinates, as in the design.
  const blips = [
    { x: -0.42, y: -0.62, color: '#f06768', r: 2.6, lit: 0 },
    { x: 0.13, y: 0.04, color: '#f5a378', r: 3, lit: 0 },
    { x: -0.18, y: 0.4, color: '#f5a378', r: 2.4, lit: 0 },
    { x: -0.02, y: 0.1, color: '#f4f3ef', r: 3.4, lit: 1, fixed: true },
  ];
  let angle = -Math.PI / 2;
  let size = 0;
  let dpr = 1;

  function resize() {
    if (!canvas) return;
    dpr = Math.min(window.devicePixelRatio || 1, 2);
    size = canvas.clientWidth;
    canvas.width = Math.round(size * dpr);
    canvas.height = Math.round(canvas.clientHeight * dpr);
  }

  function drawRadar(dt) {
    if (!ctx || !size) return;
    const w = canvas.width / dpr;
    const h = canvas.height / dpr;
    const R = Math.min(w, h) * 0.36;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, w, h);
    ctx.save();
    ctx.translate(w / 2, h / 2);
    ctx.lineWidth = 1;
    ctx.strokeStyle = 'rgba(244,243,239,0.55)';
    [1, 0.66, 0.33].forEach((f, i) => {
      ctx.globalAlpha = i === 0 ? 0.9 : 0.45;
      ctx.beginPath();
      ctx.arc(0, 0, R * f, 0, TAU);
      ctx.stroke();
    });
    ctx.globalAlpha = 0.4;
    ctx.beginPath();
    ctx.moveTo(-R * 1.08, 0);
    ctx.lineTo(R * 1.08, 0);
    ctx.moveTo(0, -R * 1.08);
    ctx.lineTo(0, R * 1.08);
    ctx.stroke();

    if (!reduceMotion) {
      const wedge = 0.55;
      if (ctx.createConicGradient) {
        const g = ctx.createConicGradient(angle - wedge, 0, 0);
        g.addColorStop(0, 'rgba(143,214,242,0)');
        g.addColorStop(wedge / TAU, 'rgba(143,214,242,0.18)');
        g.addColorStop(wedge / TAU + 0.001, 'rgba(143,214,242,0)');
        ctx.globalAlpha = 1;
        ctx.fillStyle = g;
        ctx.beginPath();
        ctx.moveTo(0, 0);
        ctx.arc(0, 0, R, angle - wedge, angle);
        ctx.closePath();
        ctx.fill();
      }
      ctx.globalAlpha = 0.5;
      ctx.strokeStyle = 'rgba(143,214,242,0.9)';
      ctx.beginPath();
      ctx.moveTo(0, 0);
      ctx.lineTo(Math.cos(angle) * R, Math.sin(angle) * R);
      ctx.stroke();
    }

    for (const b of blips) {
      if (!b.fixed && !reduceMotion) {
        const a = Math.atan2(b.y, b.x);
        const diff = (((angle - a) % TAU) + TAU) % TAU;
        b.lit = diff < 0.1 ? 1 : Math.max(0, b.lit - dt * 0.4);
      } else if (reduceMotion) b.lit = 1;
      ctx.globalAlpha = 0.5 + 0.5 * b.lit;
      ctx.fillStyle = b.color;
      ctx.beginPath();
      ctx.arc(b.x * R, b.y * R, b.r * (size / 120), 0, TAU);
      ctx.fill();
    }
    ctx.restore();
  }

  resize();
  drawRadar(0);
  window.addEventListener('resize', () => {
    resize();
    drawRadar(0);
  });
  if (reduceMotion) return;

  // Smooth wander from incommensurate sines: never jumps, never repeats.
  let t = Math.random() * 50;
  let planeX = 229;
  let nextConf = 0;
  const jitter = (base, spread) => (base + (Math.random() * 2 - 1) * spread).toFixed(2);

  function step(dt) {
    t += dt;
    const dx = Math.sin(t * 0.31) * 9 + Math.sin(t * 0.83 + 1.1) * 3;
    const dy = Math.sin(t * 0.23 + 0.7) * 5 + Math.cos(t * 0.67) * 2;
    drone?.setAttribute('transform', `translate(${(106 + dx).toFixed(2)} ${(64 + dy).toFixed(2)})`);
    planeX += dt * 3.2;
    if (planeX > 300) planeX = 200;
    const fade = planeX > 285 ? Math.max(0, (300 - planeX) / 15) : Math.min(1, (planeX - 200) / 10);
    if (plane) {
      plane.setAttribute('transform', `translate(${planeX.toFixed(2)} ${(79 - (planeX - 229) * 0.06).toFixed(2)})`);
      plane.style.opacity = String(fade);
    }
    nextConf -= dt;
    if (nextConf <= 0) {
      nextConf = 0.9 + Math.random() * 0.8;
      const d = jitter(0.87, 0.02);
      const p = jitter(0.96, 0.01);
      if (conf.drone) conf.drone.textContent = d;
      if (conf.uav) conf.uav.textContent = d;
      if (conf.plane) conf.plane.textContent = p;
      if (conf.planeRow) conf.planeRow.textContent = p;
    }
    angle = (angle + dt * 1.05) % TAU;
    drawRadar(dt);
  }

  let raf = 0;
  let last = 0;
  const frame = (now) => {
    const dt = Math.min(0.05, (now - (last || now)) / 1000);
    last = now;
    step(dt);
    raf = requestAnimationFrame(frame);
  };
  new IntersectionObserver(([e]) => {
    cancelAnimationFrame(raf);
    last = 0;
    if (e.isIntersecting) raf = requestAnimationFrame(frame);
  }).observe(root);
}
