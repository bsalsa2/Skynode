// Live 3D view of the pan-tilt mount, built from the real STL files in
// /hardware (packed by scripts/build-models.mjs). The parts sit exactly where
// hardware/pantilt.py's assembly() puts them, and the yoke and camera arm
// move through the pan and tilt axes with smooth, servo-like slews.

import {
  ACESFilmicToneMapping,
  BoxGeometry,
  BufferAttribute,
  BufferGeometry,
  Color,
  DirectionalLight,
  EdgesGeometry,
  Group,
  HemisphereLight,
  Line,
  LineBasicMaterial,
  LineDashedMaterial,
  LineSegments,
  Matrix4,
  Mesh,
  MeshBasicMaterial,
  MeshPhysicalMaterial,
  PerspectiveCamera,
  PlaneGeometry,
  SRGBColorSpace,
  Scene,
  ShaderMaterial,
  Vector3,
  WebGLRenderer,
} from 'three';
import { makeEnvironment } from './three-env.js';

// ---- Geometry constants, from hardware/pantilt.py (mm) --------------------
const WALL = 3;
const FLOOR_GAP = 1;
const HORN_SEAT_Z = 30;
const CAM_H = 30;
const CAM_D = 30;
const HORN_LEN = 32;
const SWING_R = Math.max(Math.hypot(CAM_H / 2 + WALL, CAM_D / 2 + WALL), HORN_LEN / 2 + 3);
const YOKE_Z = WALL + FLOOR_GAP + HORN_SEAT_Z; // yoke plate underside above the base
const TILT_Z = WALL + SWING_R + 2; // tilt axis above the yoke plate underside
const ARM_PRINT_LIFT = CAM_H / 2 + WALL; // the arm's STL is exported resting on z = 0

// SG90 servos (same parameters). Shown as outlines: they're bought, not printed.
const SERVO = { l: 22.5, w: 12, h: 22.7, tabSpan: 32.3, tabT: 2.5, tabZ: 15.9, shaftOffset: 5.9 };
const CAM_W = 40;
const CLEAR = 0.25;
const UPRIGHT_T = SERVO.h - SERVO.tabZ - SERVO.tabT;
const HORN_GAP = HORN_SEAT_Z - SERVO.tabZ - SERVO.tabT - UPRIGHT_T;
const UP_L_X = -(CAM_W / 2 + CLEAR + WALL) - HORN_GAP; // inner face of the tilt-servo upright

const MM = 1 / 50; // scene units per millimetre
const AMBER = 0xf0be5a;
const PAN_RANGE = [-0.75, 0.75];
const TILT_RANGE = [-0.1, 0.62];

const pad4 = (n) => (4 - (n % 4)) % 4;

function parseModels(buffer) {
  const dv = new DataView(buffer);
  const magic = String.fromCharCode(...new Uint8Array(buffer, 0, 4));
  if (magic !== 'SKN1') throw new Error('Unexpected model file');
  const count = dv.getUint32(4, true);
  const step = dv.getFloat32(8, true);
  let o = 12;
  const parts = [];
  for (let p = 0; p < count; p++) {
    const vc = dv.getUint32(o, true);
    const tc = dv.getUint32(o + 4, true);
    const ib = dv.getUint32(o + 8, true);
    o += 12;
    const q = new Int16Array(buffer, o, vc * 3);
    o += vc * 6 + pad4(vc * 6);
    const idx = ib === 2 ? new Uint16Array(buffer, o, tc * 3) : new Uint32Array(buffer, o, tc * 3);
    o += tc * 3 * ib + pad4(tc * 3 * ib);

    const pos = new Float32Array(vc * 3);
    for (let i = 0; i < pos.length; i++) pos[i] = q[i] * step;
    const indexed = new BufferGeometry();
    indexed.setAttribute('position', new BufferAttribute(pos, 3));
    indexed.setIndex(new BufferAttribute(idx, 1));

    const edges = new EdgesGeometry(indexed, 28);
    const flat = indexed.toNonIndexed(); // crisp CAD facets
    flat.computeVertexNormals();
    indexed.dispose();
    parts.push({ geometry: flat, edges });
  }
  return parts;
}

function dashedLine(points, opacity) {
  const geo = new BufferGeometry().setFromPoints(points);
  const line = new Line(
    geo,
    new LineDashedMaterial({
      color: AMBER,
      dashSize: 2.2,
      gapSize: 2.2,
      transparent: true,
      opacity,
      toneMapped: false,
    })
  );
  line.computeLineDistances();
  return line;
}

// A servo outline whose output shaft is the local z axis, body bottom at z = 0.
function ghostServo() {
  const g = new Group();
  const fill = new MeshBasicMaterial({
    color: 0xbfd0ff,
    transparent: true,
    opacity: 0.05,
    depthWrite: false,
  });
  const line = new LineBasicMaterial({ color: 0xbfd0ff, transparent: true, opacity: 0.38 });
  const cx = SERVO.l / 2 - SERVO.shaftOffset;
  const add = (geo, z) => {
    geo.translate(cx, 0, z);
    g.add(new Mesh(geo, fill));
    g.add(new LineSegments(new EdgesGeometry(geo), line));
  };
  add(new BoxGeometry(SERVO.l, SERVO.w, SERVO.h), SERVO.h / 2);
  add(new BoxGeometry(SERVO.tabSpan, SERVO.w, SERVO.tabT), SERVO.tabZ + SERVO.tabT / 2);
  return g;
}

export async function createMount({ container, url, reduceMotion, finePointer, onTooSlow }) {
  const response = await fetch(url);
  if (!response.ok) throw new Error(`Model download failed (${response.status})`);
  const [baseGeo, yokeGeo, armGeo] = parseModels(await response.arrayBuffer());

  const renderer = new WebGLRenderer({ antialias: true, alpha: true });
  let dpr = Math.min(window.devicePixelRatio || 1, 2);
  renderer.setPixelRatio(dpr);
  renderer.outputColorSpace = SRGBColorSpace;
  renderer.toneMapping = ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.1;
  renderer.setClearColor(0x000000, 0);
  const canvas = renderer.domElement;
  canvas.setAttribute('aria-hidden', 'true');
  container.appendChild(canvas);

  const scene = new Scene();
  scene.environment = makeEnvironment(renderer);
  scene.add(new HemisphereLight(0xb4c6ff, 0x0a0e1a, 1.1));
  const key = new DirectionalLight(0xffffff, 2.4);
  key.position.set(3, 5, 2);
  scene.add(key);
  const rim = new DirectionalLight(AMBER, 0.6);
  rim.position.set(-4, 2, -3);
  scene.add(rim);

  const camera = new PerspectiveCamera(26, 1, 0.1, 60);
  const target = new Vector3(0, 0.88, 0);

  // ---- Materials -----------------------------------------------------------
  const mat = (hex, rough) =>
    new MeshPhysicalMaterial({
      color: hex,
      roughness: rough,
      metalness: 0.08,
      clearcoat: 0.45,
      clearcoatRoughness: 0.35,
      envMapIntensity: 0.9,
      emissive: new Color(hex),
      emissiveIntensity: 0,
    });
  const materials = [mat(0x46506a, 0.5), mat(0x7f99e6, 0.4), mat(AMBER, 0.42)];
  const edgeMat = new LineBasicMaterial({ color: 0xe6edff, transparent: true, opacity: 0.16 });

  const part = ({ geometry, edges }, material) => {
    const g = new Group();
    g.add(new Mesh(geometry, material));
    g.add(new LineSegments(edges, edgeMat));
    return g;
  };

  // ---- Assembly (CAD is Z-up; the scene is Y-up) ----------------------------
  const turntable = new Group();
  scene.add(turntable);
  const cad = new Group();
  cad.rotation.x = -Math.PI / 2;
  cad.scale.setScalar(MM);
  turntable.add(cad);

  cad.add(part(baseGeo, materials[0]));
  const panServo = ghostServo(); // sits in the base, shaft up
  panServo.position.z = WALL + FLOOR_GAP;
  cad.add(panServo);
  const pan = new Group(); // turns about the pan servo shaft (CAD z axis)
  pan.position.z = YOKE_Z;
  cad.add(pan);
  pan.add(part(yokeGeo, materials[1]));
  // Tilt servo: through the yoke's window, shaft pointing in along +x, body
  // running toward the back. Its case top is flush with the upright's inner face.
  const tiltServo = ghostServo();
  tiltServo.setRotationFromMatrix(
    new Matrix4().makeBasis(new Vector3(0, -1, 0), new Vector3(0, 0, -1), new Vector3(1, 0, 0))
  );
  tiltServo.position.set(UP_L_X - SERVO.h, 0, TILT_Z);
  pan.add(tiltServo);
  const tilt = new Group(); // turns about the tilt axis (CAD x axis)
  tilt.position.z = TILT_Z;
  pan.add(tilt);
  const arm = part(armGeo, materials[2]);
  arm.position.z = -ARM_PRINT_LIFT;
  tilt.add(arm);

  // Axis guides: the pan shaft (vertical) and the tilt pivot (horizontal).
  cad.add(dashedLine([new Vector3(0, 0, -4), new Vector3(0, 0, YOKE_Z + TILT_Z + 34)], 0.45));
  tilt.add(dashedLine([new Vector3(-52, 0, 0), new Vector3(52, 0, 0)], 0.55));

  // Soft contact shadow.
  const shadow = new Mesh(
    new PlaneGeometry(3.2, 3.2),
    new ShaderMaterial({
      transparent: true,
      depthWrite: false,
      vertexShader: /* glsl */ `
        varying vec2 vUv;
        void main() { vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`,
      fragmentShader: /* glsl */ `
        varying vec2 vUv;
        void main() {
          float d = length(vUv - 0.5) * 2.0;
          gl_FragColor = vec4(0.0, 0.0, 0.0, pow(smoothstep(1.0, 0.0, d), 2.0) * 0.55);
        }`,
    })
  );
  shadow.rotation.x = -Math.PI / 2;
  shadow.position.y = -0.002;
  turntable.add(shadow);

  // ---- Layout ---------------------------------------------------------------
  function layout() {
    const w = container.clientWidth || 1;
    const h = container.clientHeight || 1;
    renderer.setSize(w, h, false);
    camera.aspect = w / h;
    // Pull back on narrow stages so the whole swing stays in frame.
    const dist = 5.6 / Math.min(1, camera.aspect / 1.05);
    const elev = 0.32;
    const azim = -0.62;
    camera.position.set(
      Math.sin(azim) * Math.cos(elev) * dist,
      target.y + Math.sin(elev) * dist,
      -Math.cos(azim) * Math.cos(elev) * dist
    );
    camera.lookAt(target);
    camera.updateProjectionMatrix();
  }

  // ---- Interaction: drag to turn it; mouse hover nudges the view ----------
  let yawDrag = 0;
  let hoverX = 0;
  let dragging = null;
  container.style.touchAction = 'pan-y';
  container.addEventListener('pointerdown', (e) => {
    dragging = { x: e.clientX, start: yawDrag };
    container.setPointerCapture(e.pointerId);
  });
  container.addEventListener('pointermove', (e) => {
    if (dragging) yawDrag = dragging.start + (e.clientX - dragging.x) * 0.012;
    else if (finePointer) {
      const r = container.getBoundingClientRect();
      hoverX = ((e.clientX - r.left) / r.width) * 2 - 1;
    }
    wake();
  });
  const endDrag = () => (dragging = null);
  container.addEventListener('pointerup', endDrag);
  container.addEventListener('pointercancel', endDrag);
  container.addEventListener('pointerleave', () => (hoverX = 0));

  // ---- Highlight a part (hovering its name in the list) --------------------
  let active = -1;
  const setActive = (i) => {
    active = i;
    if (reduceMotion) {
      materials.forEach((m, j) => (m.emissiveIntensity = j === active ? 0.22 : 0));
      renderer.render(scene, camera);
    } else wake();
  };

  // ---- Motion: servo-style slews between targets ---------------------------
  const servo = {
    pan: { x: 0.45, v: 0, target: 0.45 },
    tilt: { x: 0.3, v: 0, target: 0.3 },
  };
  let retarget = 0.6;
  const rand = ([a, b]) => a + Math.random() * (b - a);
  const spring = (s, dt) => {
    const k = 7;
    const c = 2 * Math.sqrt(k) * 1.05; // just over critical damping: no overshoot
    s.v += (k * (s.target - s.x) - c * s.v) * dt;
    s.x += s.v * dt;
  };

  let time = 0;
  let yaw = 0;
  function update(dt) {
    time += dt;
    if (!reduceMotion) {
      retarget -= dt;
      if (retarget <= 0) {
        servo.pan.target = rand(PAN_RANGE);
        servo.tilt.target = rand(TILT_RANGE);
        retarget = 2.2 + Math.random() * 1.6;
      }
      spring(servo.pan, dt);
      spring(servo.tilt, dt);
    }
    pan.rotation.z = servo.pan.x;
    tilt.rotation.x = servo.tilt.x;

    const goalYaw = (reduceMotion ? 0 : Math.sin(time * 0.11) * 0.35) + hoverX * 0.35 + yawDrag;
    yaw += (goalYaw - yaw) * (reduceMotion ? 1 : 1 - Math.exp(-dt * 3));
    turntable.rotation.y = yaw;

    const glow = 1 - Math.exp(-dt * 6);
    materials.forEach((m, j) => {
      const goal = j === active ? 0.22 : 0;
      m.emissiveIntensity += (goal - m.emissiveIntensity) * (reduceMotion ? 1 : glow);
    });
  }

  // ---- Loop: only while on screen and the tab is visible -------------------
  let onScreen = true;
  let running = false;
  let stopped = false;
  let last = 0;
  let frames = 0;
  let frameSum = 0;

  function frame(now) {
    const dt = Math.min(0.05, (now - last) / 1000);
    last = now;
    update(dt);
    renderer.render(scene, camera);

    frames++;
    frameSum += dt;
    if (frames === 90) {
      const avg = frameSum / frames;
      if (avg > 1 / 40 && dpr > 1) {
        dpr = Math.max(1, dpr - 0.5);
        renderer.setPixelRatio(dpr);
        layout();
      } else if (avg > 1 / 22 && dpr <= 1) {
        stopped = true;
        running = false;
        onTooSlow?.();
        return;
      }
      frames = 0;
      frameSum = 0;
    }

    if (onScreen && !document.hidden) requestAnimationFrame(frame);
    else running = false;
  }

  function wake() {
    if (reduceMotion) {
      update(0);
      renderer.render(scene, camera);
      return;
    }
    if (running || stopped || !onScreen || document.hidden) return;
    running = true;
    last = performance.now();
    requestAnimationFrame(frame);
  }

  layout();
  update(0);
  if (renderer.compileAsync) await renderer.compileAsync(scene, camera);
  renderer.render(scene, camera);

  new IntersectionObserver(([entry]) => {
    onScreen = entry.isIntersecting;
    wake();
  }).observe(container);
  document.addEventListener('visibilitychange', wake);
  new ResizeObserver(() => {
    layout();
    if (reduceMotion || !running) {
      update(0);
      renderer.render(scene, camera);
    }
  }).observe(container);
  wake();

  return { setActive };
}
