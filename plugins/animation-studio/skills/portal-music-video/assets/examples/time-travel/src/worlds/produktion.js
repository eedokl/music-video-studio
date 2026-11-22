// World 3 "Produktion" - the hook. A night road through gate after gate, every one of them LGTM.
// The vocoder's syllables stand as giant letters across the road. On "Raus. Raus. Raus." three more changes
// shoot past into the exit - which leads straight back to the review nobody does.
import * as THREE from 'three';
import { clamp, hash, lines, MONO, rectXY, ringXY, seg, sign, word } from '../kit.js';
import { makePortal } from '../portal.js';
import { BEAT, HOOK_SYL, HOOKS, LINES, STEP, V } from '../song.js';

export const id = 'produktion';
export const beats = 28;
export const year = 1980;
export const flight = { sway: 2.2, waves: 2, rise: 0.2 };
export const carryColor = 0xffffff; // shipped

const CYAN = 0x59d0ff, GREEN = 0x2bff88, BG = 0x03050d;

export function build({ t0, L }) {
  const scene = new THREE.Scene();
  scene.background = new THREE.Color(BG);
  scene.fog = new THREE.Fog(BG, 16, 88);

  // road: two edges, one centre dash per beat
  const rd = [];
  for (const x of [-3.6, 3.6]) seg(rd, x, 0, 0, x, 0, -L - 30);
  for (let k = 0; k < beats + 8; k++) seg(rd, 0, 0, -k * STEP - 0.9, 0, 0, -k * STEP - 2.1);
  scene.add(lines(rd, { color: 0xffffff, width: 0.05, opacity: 0.7 }));

  // gates every two beats
  const ga = [];
  for (let k = 2; k < beats - 1; k += 2) rectXY(ga, 0, 2.6, -k * STEP, 8.4, 5.2);
  const gates = lines(ga, { color: CYAN, width: 0.06, opacity: 0.6 });
  scene.add(gates);

  // skyline of bars left and right
  const sk = [];
  for (let k = 0; k < beats + 8; k++) {
    for (const side of [-1, 1]) {
      for (let j = 0; j < 3; j++) {
        const x = side * (6.5 + j * 2.6), z = -k * STEP - j * 0.7;
        seg(sk, x, 0, z, x, 0.6 + hash(k * 13 + j * 5 + side) * (2.5 + j * 2.2), z);
      }
    }
  }
  scene.add(lines(sk, { color: CYAN, width: 0.05, opacity: 0.4 }));

  // LGTM: one giant letter per syllable, staggered into the depth
  const camZ = (songT) => -V * (songT - t0);
  const letters = [];
  for (const h of HOOKS) {
    [...'LGTM'].forEach((ch, i) => {
      const w = word(ch, { font: MONO, size: 2.4, color: GREEN });
      w.mesh.position.set(-4.8 + i * 3.2 - w.width / 2, 2.3, camZ(h) - 22 - i * 3);
      w.mesh.visible = false;
      scene.add(w.mesh);
      letters.push({ mesh: w.mesh, at: h + HOOK_SYL[i] - t0 });
    });
  }

  // the flat voice answers
  const tw = (line) => line.at.map((x) => x - t0);
  const aus = sign(LINES.aus.words, tw(LINES.aus), { z: camZ(LINES.aus.at[0]) - 24, lineColor: CYAN });
  scene.add(aus.group);

  // exit: a round portal, RAUS three times above it
  const R = 2.3, cy = 1.9, zx = -L;
  const ra = [];
  ringXY(ra, 0, cy, zx, R);
  ringXY(ra, 0, cy, zx, R + 0.35);
  const ring = lines(ra, { color: 0xffffff, width: 0.07 });
  scene.add(ring);
  const portal = makePortal({ shape: 'circle', r: R, flat: 0x000000 });
  portal.mesh.position.set(0, cy, zx);
  scene.add(portal.mesh);
  const raus = LINES.raus.words.map((w, i) => {
    const s = sign([w], [LINES.raus.at[i] - t0], { z: zx, y: 4.9 + (2 - i) * 1.5, size: 1.15, posts: false });
    scene.add(s.group);
    return s;
  });

  const update = (tau) => {
    const lb = tau / BEAT;
    const pulse = Math.exp(-(lb - Math.floor(lb)) * 4);
    gates.material.opacity = 0.35 + 0.65 * pulse;
    ring.material.opacity = 0.6 + 0.4 * pulse;
    for (const l of letters) {
      const age = tau - l.at;
      l.mesh.visible = age >= 0;
      const k = 1 + 0.2 * (1 - clamp(age / 0.12));
      l.mesh.scale.set(k, k, 1);
    }
    aus.update(tau);
    raus.forEach((s) => s.update(tau));
  };

  // "Raus": extra changes that overtake the camera and leave through the exit. Offsets are relative to the camera.
  const SHOTS = [[-1.5, -0.6], [1.5, -0.6], [0, 1.0]];
  const carry = (tau) =>
    LINES.raus.at
      .map((at, i) => ({ age: tau - (at - t0), i }))
      .filter((r) => r.age >= 0 && r.age < 2.5)
      .map((r) => ({ x: SHOTS[r.i][0], y: SHOTS[r.i][1], z: 2 - 26 * r.age, spin: r.age * 5 }));
  return { scene, portal, update, carry };
}
