// Packs the pan-tilt STL files from ../hardware into one small binary that
// the website loads (public/models/pantilt.bin): shared vertices, positions
// quantized to 0.01 mm. Runs before every build, so a CAD change shows up on
// the site automatically. If ../hardware isn't available (for example a host
// that only checks out web/), the committed file is used as is.

import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const hardware = join(here, '..', '..', 'hardware');
const out = join(here, '..', 'public', 'models', 'pantilt.bin');
const PARTS = ['pantilt_base', 'pantilt_yoke', 'pantilt_camera_arm'];
const STEP = 0.01; // mm per unit

function readStl(path) {
  const buf = readFileSync(path);
  const tris = [];
  const isAscii =
    buf.subarray(0, 5).toString() === 'solid' && buf.subarray(0, 1024).toString().includes('facet');
  if (isAscii) {
    const nums = [...buf.toString().matchAll(/vertex\s+(\S+)\s+(\S+)\s+(\S+)/g)].map((m) =>
      m.slice(1, 4).map(Number)
    );
    for (let i = 0; i + 2 < nums.length; i += 3) tris.push([nums[i], nums[i + 1], nums[i + 2]]);
  } else {
    const n = buf.readUInt32LE(80);
    for (let i = 0; i < n; i++) {
      const o = 84 + i * 50 + 12;
      const v = (k) => [0, 1, 2].map((c) => buf.readFloatLE(o + k * 12 + c * 4));
      tris.push([v(0), v(1), v(2)]);
    }
  }
  return tris;
}

function pack(tris) {
  const index = new Map();
  const verts = [];
  const faces = [];
  for (const tri of tris) {
    const ids = tri.map((p) => {
      const q = p.map((c) => Math.round(c / STEP));
      if (q.some((c) => c < -32768 || c > 32767)) throw new Error('Part larger than +/-327 mm');
      const key = q.join(',');
      if (!index.has(key)) {
        index.set(key, verts.length / 3);
        verts.push(...q);
      }
      return index.get(key);
    });
    if (ids[0] !== ids[1] && ids[1] !== ids[2] && ids[0] !== ids[2]) faces.push(...ids);
  }
  return { verts, faces };
}

const pad4 = (n) => (4 - (n % 4)) % 4;

if (!PARTS.every((p) => existsSync(join(hardware, `${p}.stl`)))) {
  console.log('[models] ../hardware STL files not found; using committed public/models/pantilt.bin');
  process.exit(0);
}

const packed = PARTS.map((p) => pack(readStl(join(hardware, `${p}.stl`))));
let size = 12;
for (const { verts, faces } of packed) {
  const ib = verts.length / 3 > 65535 ? 4 : 2;
  size += 12 + verts.length * 2 + pad4(verts.length * 2) + faces.length * ib + pad4(faces.length * ib);
}
const buf = Buffer.alloc(size);
buf.write('SKN1', 0, 'ascii');
buf.writeUInt32LE(PARTS.length, 4);
buf.writeFloatLE(STEP, 8);
let o = 12;
for (const { verts, faces } of packed) {
  const ib = verts.length / 3 > 65535 ? 4 : 2;
  buf.writeUInt32LE(verts.length / 3, o);
  buf.writeUInt32LE(faces.length / 3, o + 4);
  buf.writeUInt32LE(ib, o + 8);
  o += 12;
  for (const v of verts) o = buf.writeInt16LE(v, o);
  o += pad4(verts.length * 2);
  for (const f of faces) o = ib === 2 ? buf.writeUInt16LE(f, o) : buf.writeUInt32LE(f, o);
  o += pad4(faces.length * ib);
}

mkdirSync(dirname(out), { recursive: true });
if (existsSync(out) && readFileSync(out).equals(buf)) {
  console.log('[models] public/models/pantilt.bin is up to date');
} else {
  writeFileSync(out, buf);
  const stats = packed.map((p, i) => `${PARTS[i]}: ${p.verts.length / 3} verts, ${p.faces.length / 3} tris`);
  console.log(`[models] wrote public/models/pantilt.bin (${(buf.length / 1024).toFixed(1)} KB)\n  ${stats.join('\n  ')}`);
}
