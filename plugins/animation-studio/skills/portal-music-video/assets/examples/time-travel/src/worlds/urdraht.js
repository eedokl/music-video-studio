// World 2 "Erstes Drahtgitter 1970" - the first vocoder hook. The line on the tube has learnt to draw:
// green vectors, nothing else. Two rails, a few gates, and the four letters, stroke by stroke.
import * as THREE from 'three';
import { clamp, lines, rectXY, seg } from '../kit.js';
import { makePortal } from '../portal.js';
import { BEAT, HOOK_SYL, HOOKS0, STEP, V } from '../song.js';

export const id = 'urdraht';
export const beats = 32;
export const year = 1970;
export const carryColor = 0x4dff88;
export const carryStyle = 'wire';
export const glow = 1.0;
export const flight = { sway: 0.6, waves: 1 };

const GREEN = 0x4dff88;
// the letters as strokes in a box 0.9 wide and 1.4 high
const STROKES = {
  L: [[0, 1.4, 0, 0], [0, 0, 0.8, 0]],
  G: [[0.8, 1.2, 0.6, 1.4], [0.6, 1.4, 0.2, 1.4], [0.2, 1.4, 0, 1.2], [0, 1.2, 0, 0.2], [0, 0.2, 0.2, 0], [0.2, 0, 0.8, 0], [0.8, 0, 0.8, 0.7], [0.8, 0.7, 0.45, 0.7]],
  T: [[0, 1.4, 0.9, 1.4], [0.45, 1.4, 0.45, 0]],
  M: [[0, 0, 0, 1.4], [0, 1.4, 0.45, 0.6], [0.45, 0.6, 0.9, 1.4], [0.9, 1.4, 0.9, 0]],
};

export function build({ t0, L }) {
  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0x000000);
  scene.fog = new THREE.Fog(0x000000, 20, 100);

  // two rails and a tie on every beat
  const fl = [];
  for (const x of [-3, 3]) seg(fl, x, 0, 0, x, 0, -L - 30);
  for (let k = 0; k <= beats + 8; k++) seg(fl, -3, 0, -k * STEP, 3, 0, -k * STEP);
  scene.add(lines(fl, { color: GREEN, width: 0.035, opacity: 0.6 }));
  const ga = [];
  for (let k = 4; k < beats - 2; k += 4) rectXY(ga, 0, 2.7, -k * STEP, 9, 5.4);
  const gates = lines(ga, { color: GREEN, width: 0.05, opacity: 0.5 });
  scene.add(gates);

  // LGTM, one letter per syllable
  const letters = [];
  for (const h of HOOKS0) {
    [...'LGTM'].forEach((ch, i) => {
      const a = [];
      const s = 1.8, x0 = -4.8 + i * 3.2 - 0.45 * s, z = -V * (h - t0) - 22 - i * 3;
      for (const [x1, y1, x2, y2] of STROKES[ch]) seg(a, x0 + x1 * s, 2.3 + y1 * s, z, x0 + x2 * s, 2.3 + y2 * s, z);
      const o = lines(a, { color: 0xb8ffd0, width: 0.1 });
      o.visible = false;
      scene.add(o);
      letters.push({ o, at: h + HOOK_SYL[i] - t0 });
    });
  }

  const fa = [];
  rectXY(fa, 0, 1.7, -L, 5, 3.4);
  rectXY(fa, 0, 1.95, -L, 5.9, 3.9);
  scene.add(lines(fa, { color: GREEN, width: 0.08 }));
  const portal = makePortal({ shape: 'rect', w: 5, h: 3.4, flat: 0x000000 });
  portal.mesh.position.set(0, 1.7, -L);
  scene.add(portal.mesh);

  const update = (tau) => {
    const lb = tau / BEAT;
    gates.material.opacity = 0.3 + 0.5 * Math.exp(-(lb - Math.floor(lb)) * 4);
    for (const l of letters) {
      const age = tau - l.at;
      l.o.visible = age >= 0;
      l.o.material.linewidth = 0.1 + 0.12 * (1 - clamp(age / 0.25)); // the fresh stroke burns brighter
    }
  };
  return { scene, portal, update };
}
