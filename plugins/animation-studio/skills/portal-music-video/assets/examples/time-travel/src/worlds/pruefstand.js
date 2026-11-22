// World 1 "Prüfstand" - the review that does not happen.
// White wire frame, red marks. A corridor of diffs nobody reads; at its end the LGTM gate counts 3-2-1 and turns
// green by itself. Through the gate you already see where it leads: everything green.
import * as THREE from 'three';
import { clamp, hash, lines, MONO, rectXY, seg, sevenSeg, sign, word } from '../kit.js';
import { makePortal } from '../portal.js';
import { BEAT, LINES, STEP, V } from '../song.js';

export const id = 'pruefstand';
export const beats = 20;
export const year = 1974;
export const flight = { sway: 0.7, waves: 1 };
export const carryColor = 0xff5a4d; // the change: unchecked, marked red

const RED = 0xff3b30, GREEN = 0x2bff88, WHITE = 0xe8e8e8;

export function build({ t0, L }) {
  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0x000000);
  scene.fog = new THREE.Fog(0x000000, 16, 92);

  // floor grid: one cross line per beat
  const fl = [];
  for (let x = -9; x <= 9; x += 3) seg(fl, x, 0, 0, x, 0, -L - 36);
  for (let k = 0; k <= beats + 12; k++) seg(fl, -9, 0, -k * STEP, 9, 0, -k * STEP);
  scene.add(lines(fl, { color: 0x8c8c8c, width: 0.03, opacity: 0.55 }));

  // diff panels left and right, every two beats
  const pw = [], pr = [];
  for (let k = 1; k < beats; k += 2) {
    for (const side of [-1, 1]) {
      const cx = side * 7.4, cz = -k * STEP, th = -side * 0.75;
      const P = (a, x1, y1, x2, y2) => seg(a, cx + x1 * Math.cos(th), y1, cz - x1 * Math.sin(th), cx + x2 * Math.cos(th), y2, cz - x2 * Math.sin(th));
      P(pw, -1.6, 0.5, 1.6, 0.5), P(pw, 1.6, 0.5, 1.6, 4.9), P(pw, 1.6, 4.9, -1.6, 4.9), P(pw, -1.6, 4.9, -1.6, 0.5);
      for (let i = 0; i < 10; i++) {
        const n = k * 31 + i * 7 + side * 3;
        const y = 4.5 - i * 0.4;
        const x0 = -1.3 + (hash(n) > 0.7 ? 0.3 : 0);
        P(hash(n + 0.5) > 0.62 ? pr : pw, x0, y, x0 + 0.5 + hash(n + 1.5) * 2.0, y);
      }
    }
  }
  scene.add(lines(pw, { color: WHITE, width: 0.03, opacity: 0.7 }));
  scene.add(lines(pr, { color: RED, width: 0.045 }));

  // the words
  const tw = (line) => line.at.map((x) => x - t0);
  const camZ = (songT) => -V * (songT - t0);
  const mk = (line, ahead, y = 4.5) => sign(line.words, tw(line), { z: Math.max(camZ(line.at[0]) - ahead, -L + 1.5), y });
  const signs = [mk(LINES.pruefe, 24), mk(LINES.frei, 24), mk(LINES.drei, 16), mk(LINES.vorbei, 24, 5.6)];
  signs.forEach((s) => scene.add(s.group));

  // the gate
  const GW = 5, GH = 3.4, zg = -L;
  const fa = [];
  rectXY(fa, 0, GH / 2, zg, GW, GH);
  rectXY(fa, 0, GH / 2 + 0.25, zg, GW + 0.9, GH + 0.5);
  seg(fa, -GW / 2 - 0.45, GH + 1.6, zg, GW / 2 + 0.45, GH + 1.6, zg);
  seg(fa, -GW / 2 - 0.45, GH + 0.5, zg, -GW / 2 - 0.45, GH + 1.6, zg);
  seg(fa, GW / 2 + 0.45, GH + 0.5, zg, GW / 2 + 0.45, GH + 1.6, zg);
  const frame = lines(fa, { color: RED, width: 0.07 });
  scene.add(frame);
  const label = word('LGTM', { font: MONO, size: 0.62 });
  label.mesh.position.set(-label.width / 2, GH + 0.74, zg);
  scene.add(label.mesh);
  const digits = [-1, 1].map((side) => {
    const d = sevenSeg();
    d.group.position.set(side * 4.3, 1.75, zg);
    scene.add(d.group);
    return d;
  });
  const portal = makePortal({ shape: 'rect', w: GW, h: GH, flat: 0x00140a });
  portal.mesh.position.set(0, GH / 2, zg);
  scene.add(portal.mesh);

  const cRed = new THREE.Color(RED), cGreen = new THREE.Color(GREEN), c = new THREE.Color();
  const update = (tau) => {
    signs.forEach((s) => s.update(tau));
    const lb = tau / BEAT;
    // 3 - 2 - 1 - 0, two beats each ("Drei Sekunden"); at 0 the gate approves by itself
    const digit = lb < 12 ? null : lb < 14 ? 3 : lb < 16 ? 2 : lb < 18 ? 1 : 0;
    const ok = lb >= 18;
    const pulse = Math.exp(-(lb - Math.floor(lb)) * 4);
    c.copy(ok ? cGreen : cRed);
    frame.material.color.copy(c);
    frame.material.opacity = ok ? 0.75 + 0.25 * pulse : 0.6 + 0.4 * pulse;
    label.mesh.material.color.copy(c);
    label.mesh.material.opacity = ok ? 1 : 0.3;
    for (const d of digits) {
      d.show(digit);
      d.mat.color.copy(c);
      d.dim.color.copy(c);
    }
    void clamp;
  };
  return { scene, portal, update };
}
