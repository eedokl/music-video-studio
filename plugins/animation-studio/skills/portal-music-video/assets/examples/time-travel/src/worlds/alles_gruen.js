// World 2 "Alles grün" - every check passes, every light is green.
// A plain of ticked boxes that light up row by row on the beat. At its end stands the black box:
// "Keiner weiß, was es tut" - then it opens, and inside is production.
import * as THREE from 'three';
import { boxEdges, ease, lines, rectXY, ringXY, seg, sign } from '../kit.js';
import { makePortal } from '../portal.js';
import { BEAT, LINES, STEP, V } from '../song.js';

export const id = 'alles_gruen';
export const beats = 16;
export const year = 1977;
export const flight = { sway: 1.6, waves: 1, phase: Math.PI, rise: -0.45 };
export const carryColor = 0x2bff88; // approved

const GREEN = 0x2bff88, BG = 0x00140a;

export function build({ t0, L }) {
  const scene = new THREE.Scene();
  scene.background = new THREE.Color(BG);
  scene.fog = new THREE.Fog(BG, 14, 80);

  // road edges
  const ed = [];
  for (const x of [-1.2, 1.2]) seg(ed, x, 0, 0, x, 0, -L);
  scene.add(lines(ed, { color: GREEN, width: 0.03, opacity: 0.35 }));

  // rows of ticked boxes, one row per beat
  const rows = [];
  for (let k = 1; k <= beats + 10; k++) {
    const a = [];
    const z = -k * STEP;
    for (const x of [-11.5, -8.5, -5.5, -2.7, 2.7, 5.5, 8.5, 11.5]) {
      seg(a, x - 0.55, 0, z - 0.55, x + 0.55, 0, z - 0.55);
      seg(a, x + 0.55, 0, z - 0.55, x + 0.55, 0, z + 0.55);
      seg(a, x + 0.55, 0, z + 0.55, x - 0.55, 0, z + 0.55);
      seg(a, x - 0.55, 0, z + 0.55, x - 0.55, 0, z - 0.55);
      seg(a, x - 0.3, 0, z, x - 0.08, 0, z + 0.25); // the tick
      seg(a, x - 0.08, 0, z + 0.25, x + 0.33, 0, z - 0.28);
    }
    const o = lines(a, { color: GREEN, width: 0.05, opacity: 0.12 });
    scene.add(o);
    rows.push({ k, o });
  }

  // traffic lights, all green
  const tl = [];
  const lamp = new THREE.MeshBasicMaterial({ color: GREEN, fog: true });
  for (let k = 2; k < beats - 1; k += 4) {
    for (const side of [-1, 1]) {
      const x = side * 4.1, z = -k * STEP;
      seg(tl, x, 0, z, x, 3.0, z);
      rectXY(tl, x, 3.95, z, 0.8, 1.9);
      ringXY(tl, x, 4.55, z, 0.22, 10);
      ringXY(tl, x, 3.95, z, 0.22, 10);
      const m = new THREE.Mesh(new THREE.CircleGeometry(0.24, 20), lamp);
      m.position.set(x, 3.35, z);
      scene.add(m);
    }
  }
  scene.add(lines(tl, { color: GREEN, width: 0.035, opacity: 0.8 }));

  // the words
  const tw = (line) => line.at.map((x) => x - t0);
  const camZ = (songT) => -V * (songT - t0);
  const mk = (line, ahead) => sign(line.words, tw(line), { z: camZ(line.at[0]) - ahead, lineColor: GREEN });
  const signs = [mk(LINES.gruen, 20), mk(LINES.gut, 22)];

  // the black box
  const BW = 11.5, BH = 8.6, BD = 3, zb = -L;
  // its two lines are written on the box itself
  for (const [line, y] of [[LINES.keiner, 5.9], [LINES.tut, 4.2]]) signs.push(sign(line.words, tw(line), { z: zb + 0.08, y, size: 1.05, posts: false }));
  signs.forEach((s) => scene.add(s.group));
  const box = new THREE.Mesh(
    new THREE.BoxGeometry(BW, BH, BD),
    new THREE.MeshBasicMaterial({ color: 0x000000, fog: false, polygonOffset: true, polygonOffsetFactor: 2, polygonOffsetUnits: 2 }),
  );
  box.position.set(0, BH / 2, zb - BD / 2);
  scene.add(box);
  const be = [];
  boxEdges(be, BW, BH, BD);
  const edges = lines(be, { color: 0xffffff, width: 0.06 });
  edges.position.copy(box.position);
  scene.add(edges);
  const PW = 4.6, PH = 3.4;
  const portal = makePortal({ shape: 'rect', w: PW, h: PH, veil: 0x000000, rim: 0xffffff, flat: 0x03050d });
  portal.mesh.position.set(0, PH / 2, zb + 0.04);
  scene.add(portal.mesh);

  const update = (tau) => {
    signs.forEach((s) => s.update(tau));
    const lb = tau / BEAT;
    // the row six beats ahead of the camera switches on, flashes and settles
    for (const r of rows) {
      const age = lb - (r.k - 6);
      r.o.material.opacity = age < 0 ? 0.12 : 0.55 + 0.45 * Math.exp(-age * 1.2);
    }
    lamp.color.setHex(GREEN).multiplyScalar(0.7 + 0.3 * Math.exp(-(lb - Math.floor(lb)) * 4));
    // the box opens on "was es tut" (local beat 12), two beats long
    portal.setOpen(ease((lb - 12) / 2));
  };
  return { scene, portal, update };
}
