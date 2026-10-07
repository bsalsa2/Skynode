// Shared studio lighting for the 3D views: a dark room with a few soft light
// panels, baked into a prefiltered environment map. Generated in code; no
// HDR files to download.

import {
  BackSide,
  BoxGeometry,
  Color,
  DoubleSide,
  Mesh,
  MeshBasicMaterial,
  PMREMGenerator,
  PlaneGeometry,
  Scene,
} from 'three';

export function makeEnvironment(renderer) {
  const env = new Scene();
  const disposables = [];
  const add = (geo, mat, setup) => {
    const m = new Mesh(geo, mat);
    setup?.(m);
    env.add(m);
    disposables.push(geo, mat);
  };
  add(new BoxGeometry(12, 12, 12), new MeshBasicMaterial({ color: 0x030304, side: BackSide }));
  const panel = (w, h, hex, intensity, pos) =>
    add(
      new PlaneGeometry(w, h),
      new MeshBasicMaterial({ color: new Color(hex).multiplyScalar(intensity), side: DoubleSide }),
      (m) => {
        m.position.set(...pos);
        m.lookAt(0, 0, 0);
      }
    );
  panel(7, 2.2, 0xe8ebf2, 2.4, [0, 5.5, 1.5]); // overhead softbox
  panel(2.4, 6, 0x8a8e99, 1.1, [-5.5, 0.5, -1]); // smoke fill, left
  panel(1.6, 3.6, 0xdce2f0, 1.6, [5.5, -0.8, 2]); // horizon rim, right
  panel(3.2, 1.2, 0xffffff, 1.8, [2.2, 1.4, 5.5]); // small key, front
  panel(10, 1.5, 0x1c1d21, 1.0, [0, -5.5, 0]); // faint floor bounce

  const pmrem = new PMREMGenerator(renderer);
  const texture = pmrem.fromScene(env, 0.035).texture;
  pmrem.dispose();
  disposables.forEach((d) => d.dispose());
  return texture;
}

