// Simulated sensor view (labelled as a simulation on the page). It shows
// what "tracking" means: a drone wanders, the camera pans and tilts to keep
// it in the centre ring (with servo lag, so the box never sits dead still),
// and an aircraft drifts through the frame in a thin box. The HUD bar shows
// the pan/tilt the node would be commanding.
//
// Coordinates are in percent of the frame. Runs only while on screen.

const clamp = (v, a, b) => Math.min(b, Math.max(a, v));

export function createSensor({ root, reduceMotion }) {
  const $ = (k) => root.querySelector(`[data-sensor="${k}"]`);
  const el = {
    frame: root.querySelector('.frame'),
    sky: $('sky'),
    grid: $('grid'),
    drone: $('drone'),
    aircraft: $('aircraft'),
    droneConf: $('drone-conf'),
    airConf: $('air-conf'),
    fps: $('fps'),
    pan: $('pan'),
    tilt: $('tilt'),
  };
  if (!el.frame || !el.drone) return;

  // World state
  const cam = { x: 0, y: 0, vx: 0, vy: 0 };
  const drone = { x: 8, y: -20 };
  const air = { x: -40, y: -44, v: 4.2 };
  let t = Math.random() * 100;
  let hudClock = 0;

  // Smooth wander from a few incommensurate sines (no jumps, never repeats).
  function wander(time) {
    return {
      x: Math.sin(time * 0.21) * 22 + Math.sin(time * 0.53 + 1.3) * 9 + Math.sin(time * 1.7) * 1.4,
      y: Math.sin(time * 0.17 + 0.6) * 9 + Math.sin(time * 0.71 + 2.1) * 5 + Math.cos(time * 1.9) * 0.9 - 14,
    };
  }

  function step(dt) {
    t += dt;
    const d = wander(t);
    drone.x = d.x;
    drone.y = d.y;

    // Camera: critically damped spring toward the drone (pan-tilt servo).
    const k = 5.5;
    const c = 2 * Math.sqrt(k);
    cam.vx += (k * (drone.x - cam.x) - c * cam.vx) * dt;
    cam.vy += (k * (drone.y - cam.y) - c * cam.vy) * dt;
    cam.x += cam.vx * dt;
    cam.y += cam.vy * dt;

    // Aircraft crosses the world slowly; respawn when it leaves the view.
    air.x += air.v * dt;
    const ax = 50 + air.x - cam.x;
    if (ax > 120) {
      air.x = cam.x - 75;
      air.y = cam.y - 30 + Math.random() * 8;
    }
  }

  function render() {
    const dx = 50 + drone.x - cam.x;
    const dy = 50 + drone.y - cam.y;
    el.drone.style.left = `${dx.toFixed(2)}%`;
    el.drone.style.top = `${dy.toFixed(2)}%`;

    const ax = 50 + air.x - cam.x;
    const ay = 50 + air.y - cam.y;
    if (el.aircraft) {
      el.aircraft.style.left = `${ax.toFixed(2)}%`;
      el.aircraft.style.top = `${ay.toFixed(2)}%`;
      // Only show it while the whole box and label fit in the frame.
      el.aircraft.style.opacity = ax > 12 && ax < 86 && ay > 14 && ay < 70 ? '1' : '0';
    }

    // The world moves opposite the camera. The grid repeats, so it can
    // scroll forever; the sky gradient only shifts a little (it's far away).
    const r = el.frame.getBoundingClientRect();
    el.grid.style.backgroundPosition = `${((-cam.x / 100) * r.width).toFixed(1)}px ${((-cam.y / 100) * r.height).toFixed(1)}px`;
    el.sky.style.transform = `translate3d(${clamp(-cam.x * 0.25, -12, 12).toFixed(2)}%, ${clamp(-cam.y * 0.6, -14, 14).toFixed(2)}%, 0)`;
  }

  function hud(dt) {
    hudClock += dt;
    if (hudClock < 0.14 && !reduceMotion) return;
    hudClock = 0;
    const pan = 92.5 + cam.x * 0.55;
    const tilt = 47 - cam.y * 0.45;
    el.pan.textContent = `PAN ${pan.toFixed(1).padStart(5, '0')}°`;
    el.tilt.textContent = `TILT ${tilt.toFixed(1)}°`;
    el.fps.textContent = `${(24.8 + (Math.random() - 0.5) * 0.8).toFixed(1)} FPS`;
    // Confidence dips a touch when the target moves fast across the frame.
    const speed = Math.hypot(cam.vx, cam.vy);
    el.droneConf.textContent = clamp(0.93 - speed * 0.004 + (Math.random() - 0.5) * 0.02, 0.8, 0.96).toFixed(2);
    if (el.airConf) el.airConf.textContent = (0.64 + (Math.random() - 0.5) * 0.06).toFixed(2);
  }

  if (reduceMotion) {
    // A single representative still.
    t = 4.2;
    step(0);
    cam.x = drone.x - 6;
    cam.y = drone.y + 4;
    air.x = cam.x - 30;
    air.y = cam.y - 30;
    render();
    hud(0);
    return;
  }

  // Settle the camera before the first visible frame.
  for (let i = 0; i < 120; i++) step(1 / 60);

  let onScreen = false;
  let running = false;
  let last = 0;
  function frame(now) {
    const dt = Math.min(0.05, (now - last) / 1000);
    last = now;
    step(dt);
    render();
    hud(dt);
    if (onScreen && !document.hidden) requestAnimationFrame(frame);
    else running = false;
  }
  function wake() {
    if (running || !onScreen || document.hidden) return;
    running = true;
    last = performance.now();
    requestAnimationFrame(frame);
  }
  render();
  new IntersectionObserver(([entry]) => {
    onScreen = entry.isIntersecting;
    wake();
  }).observe(el.frame);
  document.addEventListener('visibilitychange', wake);
}
