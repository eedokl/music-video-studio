// World 12 "Leere 2027" - the second breakdown. "Problem gelöst. Shop gelöscht."
// The generated shop has deleted itself. White, a faint grid, the last fragments drifting up and shrinking
// to nothing on "gelöscht".
import * as THREE from 'three';
import { ease, hash, lines, MONO, ringXY, roadSign, seg } from '../kit.js';
import { makePortal } from '../portal.js';
import { LINES, STEP } from '../song.js';

export const id = 'leere';
export const beats = 16;
export const year = 2027;
export const carryColor = 0x30304a;
export const carryStyle = 'wire';
export const glow = 0.12;
export const rollIn = true;
export const flight = { sway: 1.2, waves: 1, rise: 0.4 };

const BG = 0xeef0f6, INK = 0x1a1030;

export function build({ t0, L }) {
  const scene = new THREE.Scene();
  scene.background = new THREE.Color(BG);
  scene.fog = new THREE.Fog(BG, 10, 70);
  scene.add(new THREE.AmbientLight(0xffffff, 2.2));
  const sun = new THREE.DirectionalLight(0xffffff, 1.6);
  sun.position.set(3, 8, 5);
  scene.add(sun);

  const fl = [];
  for (let x = -12; x <= 12; x += 3) seg(fl, x, 0, 0, x, 0, -L - 30);
  for (let k = 0; k <= beats + 10; k++) seg(fl, -12, 0, -k * STEP, 12, 0, -k * STEP);
  scene.add(lines(fl, { color: 0xb8bccc, width: 0.025, opacity: 0.55 }));

  // what is left of the shop
  const bits = [];
  const pastel = [0xf2c4b8, 0xc8d8f0, 0xd8f0dc, 0xead0f0];
  for (let i = 0; i < 46; i++) {
    const m = new THREE.Mesh(
      new THREE.BoxGeometry(0.4 + hash(i * 1.3) * 1.6, 0.12 + hash(i * 2.1) * 0.5, 0.4 + hash(i * 3.7) * 1.2),
      new THREE.MeshLambertMaterial({ color: pastel[i % 4] }),
    );
    scene.add(m);
    bits.push({ m, x: (hash(i * 5.3) - 0.5) * 16, y: 0.4 + hash(i * 7.9) * 3.2, z: -4 - hash(i * 9.1) * (L - 6), r: hash(i * 4.4) * 6 });
  }

  const o = { font: MONO, color: INK, posts: false };
  const signs = [roadSign(LINES.geloest, t0, L, 18, { ...o, size: 1.2 }), roadSign(LINES.geloescht, t0, L, 18, { ...o, size: 1.2, y: 5.4 })];
  signs.forEach((s) => scene.add(s.group));

  const ra = [];
  ringXY(ra, 0, 1.9, -L, 2.3);
  ringXY(ra, 0, 1.9, -L, 2.65);
  scene.add(lines(ra, { color: INK, width: 0.07 }));
  const portal = makePortal({ shape: 'circle', r: 2.3, flat: 0x030a07 });
  portal.mesh.position.set(0, 1.9, -L);
  scene.add(portal.mesh);

  const tDel = LINES.geloescht.at[0] - t0;
  const update = (tau) => {
    signs.forEach((s) => s.update(tau));
    const gone = ease((tau - tDel) / 0.9);
    for (const b of bits) {
      b.m.position.set(b.x, b.y + Math.max(0, tau) * 0.25, b.z);
      b.m.rotation.set(b.r + tau * 0.2, b.r * 2 + tau * 0.15, 0);
      b.m.scale.setScalar(Math.max(0.001, 1 - gone));
      b.m.visible = gone < 1;
    }
  };
  return { scene, portal, update };
}
