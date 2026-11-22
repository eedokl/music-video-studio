// Starter world 1: wire frame. White lines on black, a corridor of panels, the lines of the song as sign bridges,
// and at the end a gate that counts down the last eight beats and turns green as we reach it.
import * as THREE from 'three';
import { hash, lines, rectXY, roadSign, seg, sevenSeg } from '../kit.js';
import { makePortal } from '../portal.js';
import { BEAT, STEP } from '../song.js';

export const id = 'gate_wire';
export const beats = 16;
export const carryColor = 0xff5a4d;
export const carryStyle = 'wire';
export const flight = { sway: 0.8, waves: 1 };

const RED = 0xff3b30, GREEN = 0x2bff88, WHITE = 0xe8e8e8;

export function build({ t0, L, beats, lines: sung }) {
  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0x000000);
  scene.fog = new THREE.Fog(0x000000, 16, 92);

  const fl = [];
  for (let x = -9; x <= 9; x += 3) seg(fl, x, 0, 0, x, 0, -L - 36);
  for (let k = 0; k <= beats + 12; k++) seg(fl, -9, 0, -k * STEP, 9, 0, -k * STEP);
  scene.add(lines(fl, { color: 0x8c8c8c, width: 0.03, opacity: 0.55 }));

  // panels left and right, every two beats: a frame with rows of marks
  const pw = [], pr = [];
  for (let k = 1; k < beats; k += 2) {
    for (const side of [-1, 1]) {
      const cx = side * 7.4, cz = -k * STEP, th = -side * 0.75;
      const P = (a, x1, y1, x2, y2) => seg(a, cx + x1 * Math.cos(th), y1, cz - x1 * Math.sin(th), cx + x2 * Math.cos(th), y2, cz - x2 * Math.sin(th));
      P(pw, -1.6, 0.5, 1.6, 0.5), P(pw, 1.6, 0.5, 1.6, 4.9), P(pw, 1.6, 4.9, -1.6, 4.9), P(pw, -1.6, 4.9, -1.6, 0.5);
      for (let i = 0; i < 10; i++) {
        const n = k * 31 + i * 7 + side * 3;
        const x0 = -1.3 + (hash(n) > 0.7 ? 0.3 : 0);
        P(hash(n + 0.5) > 0.62 ? pr : pw, x0, 4.5 - i * 0.4, x0 + 0.5 + hash(n + 1.5) * 2.0, 4.5 - i * 0.4);
      }
    }
  }
  scene.add(lines(pw, { color: WHITE, width: 0.03, opacity: 0.7 }));
  scene.add(lines(pr, { color: RED, width: 0.045 }));

  const signs = sung.map((line) => roadSign(line, t0, L, 24));
  signs.forEach((s) => scene.add(s.group));

  // the gate with a counter on each side
  const GW = 5, GH = 3.4, zg = -L;
  const fa = [];
  rectXY(fa, 0, GH / 2, zg, GW, GH);
  rectXY(fa, 0, GH / 2 + 0.25, zg, GW + 0.9, GH + 0.5);
  const frame = lines(fa, { color: RED, width: 0.07 });
  scene.add(frame);
  const digits = [-1, 1].map((side) => {
    const d = sevenSeg();
    d.group.position.set(side * 4.3, 1.75, zg);
    scene.add(d.group);
    return d;
  });
  const portal = makePortal({ shape: 'rect', w: GW, h: GH });
  portal.mesh.position.set(0, GH / 2, zg);
  scene.add(portal.mesh);

  const cRed = new THREE.Color(RED), cGreen = new THREE.Color(GREEN);
  const update = (tau) => {
    signs.forEach((s) => s.update(tau));
    const lb = tau / BEAT, left = beats - lb; // beats until we fly through
    const pulse = Math.exp(-(lb - Math.floor(lb)) * 4);
    const digit = left > 8 ? null : left > 6 ? 3 : left > 4 ? 2 : left > 2 ? 1 : 0;
    const ok = left <= 2;
    frame.material.color.copy(ok ? cGreen : cRed);
    frame.material.opacity = 0.6 + 0.4 * pulse;
    for (const d of digits) {
      d.show(digit);
      d.mat.color.copy(ok ? cGreen : cRed);
      d.dim.color.copy(ok ? cGreen : cRed);
    }
  };
  return { scene, portal, update };
}
