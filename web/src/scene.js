// Skynode hero scene. Loaded on demand by main.js, never on the critical path.
//
// A faceted glass sensor orb hangs in a starfield. A small aircraft circles
// it; the lens inside the orb turns to follow, and a thin amber reticle
// tracks the aircraft and periodically re-acquires its lock.
// Everything here is generated in code: no models, textures, or HDR files.

import {
  ACESFilmicToneMapping,
  AdditiveBlending,
  BufferAttribute,
  BufferGeometry,
  Color,
  DoubleSide,
  EdgesGeometry,
  ExtrudeGeometry,
  Group,
  IcosahedronGeometry,
  Line,
  LineBasicMaterial,
  LineDashedMaterial,
  LineSegments,
  MathUtils,
  Mesh,
  MeshBasicMaterial,
  MeshPhysicalMaterial,
  MeshStandardMaterial,
  Object3D,
  PerspectiveCamera,
  PlaneGeometry,
  Points,
  RingGeometry,
  SRGBColorSpace,
  Scene,
  ShaderMaterial,
  Shape,
  SphereGeometry,
  TorusGeometry,
  Vector3,
  WebGLRenderer,
} from 'three';
import { makeEnvironment } from './three-env.js';

const AMBER = 0xf0be5a;
const CAMERA_Z = 7;
const FOV = 35;

// ---------------------------------------------------------------------------
// Geometry
// ---------------------------------------------------------------------------
function aircraftGeometry() {
  // Top-down silhouette (nose at +y), the same outline as the static SVG hero.
  const pts = [
    [0, 16], [3, 6], [18, -2], [18, -5], [3, -2], [2, -12], [7, -16], [7, -18],
    [0, -16], [-7, -18], [-7, -16], [-2, -12], [-3, -2], [-18, -5], [-18, -2], [-3, 6],
  ];
  const shape = new Shape();
  shape.moveTo(pts[0][0], pts[0][1]);
  pts.slice(1).forEach(([x, y]) => shape.lineTo(x, y));
  shape.closePath();
  const g = new ExtrudeGeometry(shape, {
    depth: 1.4,
    bevelEnabled: true,
    bevelThickness: 0.7,
    bevelSize: 0.6,
    bevelSegments: 1,
  });
  g.center();
  g.rotateX(Math.PI / 2); // nose now points along +z, which lookAt() aims
  g.scale(0.017, 0.017, 0.017);
  return g;
}

function makeStars(count) {
  const pos = new Float32Array(count * 3);
  const size = new Float32Array(count);
  const phase = new Float32Array(count);
  for (let i = 0; i < count; i++) {
    pos[i * 3] = (Math.random() * 2 - 1) * 70;
    pos[i * 3 + 1] = (Math.random() * 2 - 1) * 42;
    pos[i * 3 + 2] = -12 - Math.random() * 70;
    size[i] = 0.5 + Math.pow(Math.random(), 4) * 2.8;
    phase[i] = Math.random() * Math.PI * 2;
  }
  const geo = new BufferGeometry();
  geo.setAttribute('position', new BufferAttribute(pos, 3));
  geo.setAttribute('aSize', new BufferAttribute(size, 1));
  geo.setAttribute('aPhase', new BufferAttribute(phase, 1));
  const mat = new ShaderMaterial({
    uniforms: { uTime: { value: 0 }, uPR: { value: 1 } },
    vertexShader: /* glsl */ `
      attribute float aSize;
      attribute float aPhase;
      uniform float uTime;
      uniform float uPR;
      varying float vA;
      void main() {
        vec4 mv = modelViewMatrix * vec4(position, 1.0);
        gl_Position = projectionMatrix * mv;
        gl_PointSize = aSize * uPR * (64.0 / -mv.z);
        vA = 0.5 + 0.5 * sin(uTime * (0.5 + fract(aPhase) * 0.8) + aPhase * 7.0);
      }`,
    fragmentShader: /* glsl */ `
      varying float vA;
      void main() {
        float d = length(gl_PointCoord - 0.5);
        float a = smoothstep(0.5, 0.0, d);
        a *= a * (0.35 + 0.65 * vA);
        gl_FragColor = vec4(vec3(0.80, 0.86, 1.0) * a, a);
      }`,
    transparent: true,
    depthWrite: false,
    blending: AdditiveBlending,
  });
  return new Points(geo, mat);
}

function makeReticle() {
  const mat = new MeshBasicMaterial({
    color: AMBER,
    transparent: true,
    opacity: 0.95,
    depthTest: false,
    depthWrite: false,
    toneMapped: false,
    side: DoubleSide,
  });
  const group = new Group();
  const ring = new Mesh(new RingGeometry(0.34, 0.35, 96), mat);
  group.add(ring);

  const ticks = new Group();
  for (let i = 0; i < 4; i++) {
    const tick = new Mesh(new PlaneGeometry(0.01, 0.08), mat);
    const a = (i * Math.PI) / 2;
    tick.position.set(Math.sin(a) * 0.41, Math.cos(a) * 0.41, 0);
    tick.rotation.z = -a;
    ticks.add(tick);
  }
  group.add(ticks);

  const brackets = new Group();
  const bracketMat = mat.clone();
  bracketMat.opacity = 0.7;
  for (let i = 0; i < 4; i++) {
    const arc = new Mesh(
      new RingGeometry(0.22, 0.228, 24, 1, i * (Math.PI / 2) + 0.35, Math.PI / 2 - 0.7),
      bracketMat
    );
    brackets.add(arc);
  }
  group.add(brackets);

  group.traverse((o) => (o.renderOrder = 10));
  return { group, ring, ticks, brackets, bracketMat };
}

// ---------------------------------------------------------------------------
// Scene
// ---------------------------------------------------------------------------
export async function createScene({ container, reduceMotion, finePointer, getStory, onTooSlow }) {
  const staticMode = reduceMotion; // one still frame inside the hero box
  const coarse = !finePointer;

  const renderer = new WebGLRenderer({
    antialias: true,
    alpha: true,
    powerPreference: 'high-performance',
  });
  let dpr = Math.min(window.devicePixelRatio || 1, 2);
  renderer.setPixelRatio(dpr);
  renderer.outputColorSpace = SRGBColorSpace;
  renderer.toneMapping = ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.05;
  renderer.setClearColor(0x000000, 0);

  const canvas = renderer.domElement;
  canvas.setAttribute('aria-hidden', 'true');
  container.appendChild(canvas);

  const scene = new Scene();
  scene.environment = makeEnvironment(renderer);

  const camera = new PerspectiveCamera(FOV, 1, 0.1, 200);
  camera.position.set(0, 0, CAMERA_Z);
  const lookTarget = new Vector3(0, 0, -12);

  // ---- The rig: everything that moves with the scroll story -------------
  const rig = new Group();
  scene.add(rig);

  const orbGeo = new IcosahedronGeometry(1, 1);
  const orb = new Mesh(
    orbGeo,
    new MeshPhysicalMaterial({
      color: 0xd4defc,
      metalness: 0,
      roughness: 0.12,
      transmission: 1,
      thickness: 0.9,
      ior: 1.42,
      attenuationColor: new Color(0x8ea2e6),
      attenuationDistance: 3.2,
      emissive: new Color(0x0c1633),
      emissiveIntensity: 0.7,
      clearcoat: 1,
      clearcoatRoughness: 0.05,
      iridescence: 0.4,
      iridescenceIOR: 1.25,
      specularIntensity: 1,
      envMapIntensity: 1.25,
      flatShading: true,
    })
  );
  rig.add(orb);
  const edges = new LineSegments(
    new EdgesGeometry(orbGeo),
    new LineBasicMaterial({ color: 0xdfe8ff, transparent: true, opacity: 0.16 })
  );
  edges.scale.setScalar(1.003);
  orb.add(edges);

  // Inner glow: drawn after the glass, so the orb reads as lit from within
  // even though it sits on a dark, transparent background.
  const glow = new Mesh(
    new PlaneGeometry(2.6, 2.6),
    new ShaderMaterial({
      uniforms: { uColor: { value: new Color(0x6f8fff) }, uAmber: { value: new Color(AMBER) } },
      vertexShader: /* glsl */ `
        varying vec2 vUv;
        void main() {
          vUv = uv;
          gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
        }`,
      fragmentShader: /* glsl */ `
        uniform vec3 uColor;
        uniform vec3 uAmber;
        varying vec2 vUv;
        void main() {
          float d = length(vUv - 0.5) * 2.0;
          float halo = smoothstep(1.0, 0.0, d);
          float core = smoothstep(0.32, 0.0, d);
          float a = pow(halo, 2.2) * 0.3 + core * 0.06;
          vec3 col = mix(uColor, uAmber, core / max(a * 4.0, 0.001) * 0.2);
          gl_FragColor = vec4(col, a);
        }`,
      transparent: true,
      depthWrite: false,
    })
  );
  glow.renderOrder = 2;
  rig.add(glow);

  // Lens core: the "camera" inside the sensor. It turns to follow the target.
  const core = new Group();
  rig.add(core);
  core.add(
    new Mesh(
      new SphereGeometry(0.34, 32, 16),
      new MeshStandardMaterial({ color: 0x0a1022, metalness: 0.75, roughness: 0.28 })
    )
  );
  const lensRing = new Mesh(
    new TorusGeometry(0.19, 0.022, 12, 48),
    new MeshStandardMaterial({
      color: AMBER,
      emissive: AMBER,
      emissiveIntensity: 0.55,
      metalness: 0.6,
      roughness: 0.3,
    })
  );
  lensRing.position.z = 0.29;
  core.add(lensRing);
  const lensGlass = new Mesh(
    new SphereGeometry(0.16, 24, 12),
    new MeshStandardMaterial({ color: 0x04060c, metalness: 1, roughness: 0.05 })
  );
  lensGlass.position.z = 0.23;
  lensGlass.scale.z = 0.6;
  core.add(lensGlass);
  const pupil = new Mesh(
    new SphereGeometry(0.045, 16, 8),
    new MeshBasicMaterial({ color: AMBER, toneMapped: false })
  );
  pupil.position.z = 0.31;
  core.add(pupil);
  const aim = new Object3D(); // helper for smooth core aiming
  rig.add(aim);

  // Pan and tilt gimbal rings.
  const ringMat = new MeshBasicMaterial({ color: 0xcfdcff, transparent: true, opacity: 0.2 });
  const panRing = new Mesh(new TorusGeometry(1.3, 0.004, 6, 180), ringMat);
  panRing.rotation.x = Math.PI / 2;
  rig.add(panRing);
  const tiltRing = new Mesh(
    new TorusGeometry(1.4, 0.004, 6, 180),
    new MeshBasicMaterial({ color: 0xcfdcff, transparent: true, opacity: 0.11 })
  );
  rig.add(tiltRing);

  // The aircraft.
  const aircraft = new Mesh(
    aircraftGeometry(),
    new MeshPhysicalMaterial({
      color: 0xe8eeff,
      metalness: 0.35,
      roughness: 0.22,
      clearcoat: 1,
      emissive: 0x1c2c58,
      emissiveIntensity: 0.7,
      flatShading: true,
    })
  );
  rig.add(aircraft);
  const ORBIT = { rx: 1.85, rz: 1.3, y: 0.5, incline: 0.3, speed: 0.24 };
  const orbitPoint = (t, out) =>
    out.set(
      Math.cos(t) * ORBIT.rx,
      ORBIT.y + Math.sin(t) * ORBIT.rz * ORBIT.incline + Math.sin(t * 2.0) * 0.06,
      Math.sin(t) * ORBIT.rz
    );

  // Reticle + tracking line (HUD layer: always drawn on top).
  const reticle = makeReticle();
  scene.add(reticle.group);
  const lineGeo = new BufferGeometry();
  lineGeo.setAttribute('position', new BufferAttribute(new Float32Array(6), 3));
  const trackLine = new Line(
    lineGeo,
    new LineDashedMaterial({
      color: AMBER,
      dashSize: 0.05,
      gapSize: 0.07,
      transparent: true,
      opacity: 0.4,
      depthTest: false,
      depthWrite: false,
      toneMapped: false,
    })
  );
  trackLine.renderOrder = 9;
  trackLine.frustumCulled = false;
  scene.add(trackLine);

  // Stars.
  const stars = makeStars(coarse ? 650 : 1400);
  scene.add(stars);

  // ---- Layout: match the static SVG hero so the swap is seamless --------
  const halfH = Math.tan(MathUtils.degToRad(FOV / 2)) * CAMERA_Z;
  let poses = [];
  const heroBox = document.getElementById('hero-visual');

  function layout() {
    const w = container.clientWidth || window.innerWidth;
    const h = container.clientHeight || window.innerHeight;
    renderer.setSize(w, h, false);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
    stars.material.uniforms.uPR.value = renderer.getPixelRatio();

    const halfW = halfH * camera.aspect;
    if (staticMode) {
      const s = Math.min(1, (halfW * 0.92) / 2.5);
      poses = [{ x: 0, y: -0.1, z: 0, s }];
      return;
    }
    // Where the static hero box sits, in page coordinates (scroll = 0).
    const r = heroBox.getBoundingClientRect();
    const boxCx = r.left + r.width / 2;
    const boxCy = r.top + window.scrollY + r.height / 2;
    const toWorldX = (px) => ((px / w) * 2 - 1) * halfW;
    const toWorldY = (py) => (1 - (py / h) * 2) * halfH;
    const boxW = (r.width / w) * 2 * halfW;
    const s0 = boxW * 0.235;
    const wide = w > 900;

    const p0 = { x: toWorldX(boxCx), y: toWorldY(boxCy), z: 0, s: s0 };
    const p1 = wide
      ? { x: halfW * 0.86, y: -0.25, z: -2.6, s: s0 * 1.05 }
      : { x: 0, y: halfH * 0.42, z: -3.5, s: s0 };
    const p2 = wide
      ? { x: 0, y: -0.2, z: -1.6, s: s0 * 1.15 }
      : { x: 0, y: -0.1, z: -2.2, s: s0 * 1.1 };
    const p3 = { x: 0, y: p2.y + 2.8, z: -5, s: s0 * 0.8 };
    poses = [p0, p1, p2, p3];
  }

  const ease = (x) => x * x * (3 - 2 * x);
  function poseAt(p) {
    if (poses.length === 1) return poses[0];
    const i = Math.min(poses.length - 2, Math.floor(p));
    const f = ease(MathUtils.clamp(p - i, 0, 1));
    const a = poses[i];
    const b = poses[i + 1];
    return {
      x: MathUtils.lerp(a.x, b.x, f),
      y: MathUtils.lerp(a.y, b.y, f),
      z: MathUtils.lerp(a.z, b.z, f),
      s: MathUtils.lerp(a.s, b.s, f),
    };
  }

  // ---- Input -------------------------------------------------------------
  const pointer = { x: 0, y: 0 };
  const drift = { x: 0, y: 0 };
  if (finePointer && !staticMode) {
    window.addEventListener(
      'pointermove',
      (e) => {
        pointer.x = (e.clientX / window.innerWidth) * 2 - 1;
        pointer.y = (e.clientY / window.innerHeight) * 2 - 1;
      },
      { passive: true }
    );
  }

  // ---- Per-frame update ----------------------------------------------------
  const tmp = new Vector3();
  const next = new Vector3();
  const aircraftWorld = new Vector3();
  const pupilWorld = new Vector3();
  const reticlePos = new Vector3();
  let firstFrame = true;
  let time = staticMode ? 0 : Math.random() * 10;
  let lockClock = 0;
  let smoothP = 0;

  function update(dt, story) {
    time += dt;
    const k = (rate) => 1 - Math.exp(-dt * rate);

    // Scroll story (smoothed so wheel steps feel continuous).
    smoothP = firstFrame ? story.p : MathUtils.lerp(smoothP, story.p, k(5));
    const pose = poseAt(smoothP);
    rig.position.set(pose.x, pose.y, pose.z);
    rig.scale.setScalar(pose.s);
    rig.rotation.x = 0.12 + smoothP * 0.22;
    rig.rotation.z = Math.sin(smoothP * 1.4) * 0.08;
    rig.rotation.y = smoothP * 0.6;

    // Camera drift: mouse parallax, or a slow loop on touch devices.
    if (coarse || staticMode) {
      pointer.x = staticMode ? 0.25 : Math.sin(time * 0.13) * 0.7;
      pointer.y = staticMode ? -0.15 : Math.cos(time * 0.09) * 0.5;
    }
    drift.x = firstFrame ? pointer.x : MathUtils.lerp(drift.x, pointer.x, k(1.6));
    drift.y = firstFrame ? pointer.y : MathUtils.lerp(drift.y, pointer.y, k(1.6));
    camera.position.set(drift.x * 0.5, -drift.y * 0.32, CAMERA_Z);
    camera.lookAt(lookTarget);

    // Orb: slow rotation.
    orb.rotation.y = time * 0.09;
    orb.rotation.x = Math.sin(time * 0.05) * 0.25;
    panRing.rotation.z = time * 0.02;

    // Aircraft on its orbit, nose along the path, banked into the turn.
    const t = staticMode ? 0.55 : time * ORBIT.speed;
    orbitPoint(t, aircraft.position);
    orbitPoint(t + 0.04, next);
    rig.localToWorld(next);
    aircraft.lookAt(next);
    aircraft.rotateZ(-0.42);
    aircraft.getWorldPosition(aircraftWorld);

    // Lens core aims at the aircraft (smoothly, like a pan-tilt servo).
    aim.lookAt(aircraftWorld);
    if (firstFrame) core.quaternion.copy(aim.quaternion);
    else core.quaternion.slerp(aim.quaternion, k(3.2));
    tmp.set(0, 0, 1).applyQuaternion(core.quaternion);
    tiltRing.rotation.set(0, Math.atan2(tmp.x, tmp.z) + Math.PI / 2, 0);

    // Reticle trails the aircraft, then re-acquires lock every few seconds.
    if (firstFrame) reticlePos.copy(aircraftWorld);
    else reticlePos.lerp(aircraftWorld, k(4.5));
    reticle.group.position.copy(reticlePos);
    reticle.group.quaternion.copy(camera.quaternion);
    glow.quaternion.copy(camera.quaternion);
    const retScale = Math.max(0.55, Math.sqrt(pose.s));
    lockClock += dt;
    if (lockClock > 5.5) lockClock = 0;
    const acquire = staticMode ? 0 : Math.exp(-lockClock * 4);
    reticle.group.scale.setScalar(retScale * (1 + acquire * 0.5));
    reticle.ring.rotation.z = -time * 0.25;
    reticle.ticks.rotation.z = time * 0.1;
    reticle.brackets.rotation.z = time * 0.6 + acquire * 2;
    reticle.bracketMat.opacity = 0.55 + 0.35 * (1 - acquire) * (0.7 + 0.3 * Math.sin(time * 6));

    // Tracking line from lens to reticle.
    pupil.getWorldPosition(pupilWorld);
    const arr = lineGeo.attributes.position.array;
    pupilWorld.toArray(arr, 0);
    reticlePos.toArray(arr, 3);
    lineGeo.attributes.position.needsUpdate = true;
    trackLine.computeLineDistances();

    stars.material.uniforms.uTime.value = time;
    stars.rotation.y = time * 0.004;
    firstFrame = false;
  }

  // ---- Loop with pausing ---------------------------------------------------
  let running = false;
  let stopped = false;
  let last = 0;
  let frames = 0;
  let frameTimeSum = 0;
  const shouldRun = (story) => !document.hidden && story.fade > 0.001;

  // Ease the scene back while it sits behind the How-it-works cards.
  function applyFade(story) {
    const behindCards = 1 - 0.35 * Math.max(0, 1 - Math.abs(story.p - 2) / 0.6);
    const o = story.fade * behindCards;
    canvas.style.opacity = o < 0.999 ? o.toFixed(3) : '';
  }

  function frame(now) {
    const dt = Math.min(0.05, (now - last) / 1000);
    last = now;
    const story = getStory();
    applyFade(story);
    update(dt, story);
    renderer.render(scene, camera);

    // Adaptive resolution: if frames are slow, step the pixel ratio down.
    frames++;
    frameTimeSum += dt;
    if (frames === 90) {
      const avg = frameTimeSum / frames;
      if (avg > 1 / 40 && dpr > 1) {
        dpr = Math.max(1, dpr - 0.5);
        renderer.setPixelRatio(dpr);
        layout();
      } else if (avg > 1 / 22 && dpr <= 1) {
        // Still slow at 1x: stop for good and hand back to the static hero.
        stopped = true;
        running = false;
        canvas.style.opacity = '0';
        onTooSlow?.();
        return;
      }
      frames = 0;
      frameTimeSum = 0;
    }

    if (shouldRun(story)) requestAnimationFrame(frame);
    else running = false;
  }

  function wake() {
    if (running || stopped) return;
    const story = getStory();
    applyFade(story);
    if (!shouldRun(story)) return;
    running = true;
    last = performance.now();
    requestAnimationFrame(frame);
  }

  // ---- Boot ----------------------------------------------------------------
  layout();
  const still = { p: 0, fade: 1 };
  update(0, staticMode ? still : getStory());
  // Compile shaders off the main thread where the browser allows it.
  if (renderer.compileAsync) await renderer.compileAsync(scene, camera);
  renderer.render(scene, camera);

  let resizeRaf = 0;
  new ResizeObserver(() => {
    cancelAnimationFrame(resizeRaf);
    resizeRaf = requestAnimationFrame(() => {
      layout();
      if (staticMode) {
        update(0, still);
        renderer.render(scene, camera);
      } else wake();
    });
  }).observe(container);

  if (!staticMode) {
    window.addEventListener('scroll', wake, { passive: true });
    document.addEventListener('visibilitychange', wake);
    wake();
  }
}
