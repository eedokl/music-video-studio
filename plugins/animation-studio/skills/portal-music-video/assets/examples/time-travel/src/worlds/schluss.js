// World 15 "Wieder 1974" - the outro. Back in the wire frame where it began. The flight slows down and stops in
// front of an empty desk. The vocoder says goodbye ("Läuft gut. Tschüss. Mahlzeit."), the machine calls for Uwe.
// Uwe is not in the office. The change lies on the floor, still unchecked - and the last gate answers by itself:
// LGTM. Everything else goes dark; the four letters shrink to the point of light the film began with.
import * as THREE from 'three';
import { boxEdges, clamp, ease, hash, lines, MONO, rectXY, seg, sign, word } from '../kit.js';
import { BEAT, LINES, SONG_END, STEP, V } from '../song.js';

export const id = 'schluss';
export const beats = 74; // to the end of the song
export const year = 1974;
export const carryColor = 0xff5a4d;
export const carryStyle = 'wire';
export const glow = 0.85;
export const noExit = true;
export const flight = { sway: 0.5, waves: 1 };

const BRAKE = 7; // seconds: the flight comes to rest after about 6 * 7 = 42 units
export const travel = (tau) => (tau < 0 ? V * tau : V * BRAKE * (1 - Math.exp(-tau / BRAKE)));

const RED = 0xff3b30, GREEN = 0x2bff88, WHITE = 0xe8e8e8;
const ZD = -46; // the desk

export function build({ t0 }) {
  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0x000000);
  scene.fog = new THREE.Fog(0x000000, 16, 92);
  const T = (songT) => songT - t0;
  const fading = []; // everything that goes dark at the end
  const add = (o, base = o.material?.opacity ?? 1) => (scene.add(o), fading.push([o, base]), o);

  const fl = [];
  for (let x = -9; x <= 9; x += 3) seg(fl, x, 0, 0, x, 0, -90);
  for (let k = 0; k <= 30; k++) seg(fl, -9, 0, -k * STEP, 9, 0, -k * STEP);
  add(lines(fl, { color: 0x8c8c8c, width: 0.03, opacity: 0.55 }));

  // the corridor of diffs, as in 1974
  const pw = [], pr = [];
  for (let k = 1; k < 13; k += 2) {
    for (const side of [-1, 1]) {
      const cx = side * 7.4, cz = -k * STEP, th = -side * 0.75;
      const P = (a, x1, y1, x2, y2) => seg(a, cx + x1 * Math.cos(th), y1, cz - x1 * Math.sin(th), cx + x2 * Math.cos(th), y2, cz - x2 * Math.sin(th));
      P(pw, -1.6, 0.5, 1.6, 0.5), P(pw, 1.6, 0.5, 1.6, 4.9), P(pw, 1.6, 4.9, -1.6, 4.9), P(pw, -1.6, 4.9, -1.6, 0.5);
      for (let i = 0; i < 10; i++) {
        const n = k * 31 + i * 7 + side * 3 + 900;
        const x0 = -1.3 + (hash(n) > 0.7 ? 0.3 : 0);
        P(hash(n + 0.5) > 0.62 ? pr : pw, x0, 4.5 - i * 0.4, x0 + 0.5 + hash(n + 1.5) * 2.0, 4.5 - i * 0.4);
      }
    }
  }
  add(lines(pw, { color: WHITE, width: 0.03, opacity: 0.7 }));
  add(lines(pr, { color: RED, width: 0.045 }));

  // the empty desk: top, legs, terminal, and a chair pushed back
  const da = [];
  const boxAt = (w, h, d, x, y, z) => {
    const a = [];
    boxEdges(a, w, h, d);
    for (let i = 0; i < a.length; i += 3) da.push(a[i] + x, a[i + 1] + y, a[i + 2] + z);
  };
  boxAt(3.0, 0.1, 1.3, 0, 1.0, ZD);
  for (const sx of [-1.4, 1.4]) for (const sz of [-0.55, 0.55]) seg(da, sx, 0, ZD + sz, sx, 1.0, ZD + sz);
  boxAt(1.1, 0.85, 0.9, -0.5, 1.5, ZD);
  boxAt(0.8, 0.08, 0.8, 1.9, 0.6, ZD - 1.9), boxAt(0.8, 0.9, 0.08, 1.9, 1.1, ZD - 2.3);
  add(lines(da, { color: WHITE, width: 0.04 }));

  // the words
  const o = { font: MONO, color: GREEN, posts: false };
  const signs = [
    sign(LINES.laeuft1.words, LINES.laeuft1.at.map(T), { ...o, z: -travel(T(LINES.laeuft1.at[0])) - 18, size: 0.85, lineColor: GREEN, posts: true }),
    sign(LINES.laeuft2.words, LINES.laeuft2.at.map(T), { ...o, z: ZD - 1, y: 5.6, size: 0.6 }),
    sign(LINES.uwe.words, LINES.uwe.at.map(T), { ...o, z: ZD + 0.8, y: 2.75, size: 0.42 }),
    sign(LINES.melden.words, LINES.melden.at.map(T), { ...o, z: ZD + 0.8, y: 2.15, size: 0.42 }),
  ];
  // nobody answers
  const t1 = T(LINES.melden.at[1]) + 5.5, t2 = t1 + 8 * BEAT, t3 = t2 + 4 * BEAT, tOut = t3 + 8 * BEAT;
  signs.push(sign(['UWE', 'IST', 'NICHT', 'IM', 'BÜRO.', '(FREITAG,', '17:00)'], new Array(7).fill(t1), { z: ZD + 0.8, y: 3.75, size: 0.17, font: MONO, color: WHITE, posts: false }));
  signs.push(sign(['AUTOMATISCHE', 'ANTWORT:'], [t2, t2], { z: ZD + 0.8, y: 3.4, size: 0.17, font: MONO, color: WHITE, posts: false }));
  signs.forEach((s) => (scene.add(s.group), s.group.traverse((m) => m.material && fading.push([m, m.material.opacity ?? 1]))));

  // the last gate, behind the desk; its four letters light up by themselves
  const zg = ZD - 6;
  const ga = [];
  rectXY(ga, 0, 1.7, zg, 5, 3.4);
  rectXY(ga, 0, 1.95, zg, 5.9, 3.9);
  const gate = add(lines(ga, { color: RED, width: 0.07 }));
  const label = new THREE.Group();
  label.position.set(0, 1.75, zg);
  scene.add(label);
  const letters = [...'LGTM'].map((ch, i) => {
    const w = word(ch, { font: MONO, size: 0.9, color: GREEN });
    w.mesh.position.set((i - 1.5) * 1.05 - w.width / 2, -0.45, 0);
    w.mesh.visible = false;
    label.add(w.mesh);
    return w.mesh;
  });
  const dot = new THREE.Mesh(new THREE.CircleGeometry(0.06, 16), new THREE.MeshBasicMaterial({ color: 0x9dffc0, fog: false }));
  dot.position.set(0, 1.75, zg + 0.02);
  dot.visible = false;
  scene.add(dot);

  const cGreen = new THREE.Color(GREEN), cRed = new THREE.Color(RED);
  const tEnd = SONG_END - t0;
  const update = (tau) => {
    signs.forEach((s) => s.update(tau));
    const lb = tau / BEAT;
    const pulse = Math.exp(-(lb - Math.floor(lb)) * 4);
    const out = ease((tau - tOut) / (2 * BEAT)); // everything but the letters goes dark
    for (const [m, base] of fading) m.material.opacity = base * (1 - out);
    letters.forEach((m, i) => (m.visible = tau >= t3 + (i * BEAT) / 2));
    const ok = tau >= t3 + 2 * BEAT;
    gate.material.color.copy(ok ? cGreen : cRed);
    gate.material.opacity = (ok ? 0.9 : 0.55 + 0.35 * pulse) * (1 - out);
    // the picture shrinks to a point, as on a tube that is switched off
    const shrink = ease((tau - (tEnd - 3.2)) / 2.4);
    label.scale.set(1 - shrink * 0.97, Math.max(0.03, 1 - shrink * 1.6), 1);
    dot.visible = shrink > 0.5;
    dot.scale.setScalar(1 + 2 * clamp((tau - (tEnd - 1.6)) / 0.5) * (1 - clamp((tau - (tEnd - 0.9)) / 0.8)));
    label.visible = tau < tEnd - 0.8;
    dot.material.opacity = 1;
    dot.material.color.setHex(0x9dffc0).multiplyScalar(1 - clamp((tau - (tEnd - 0.6)) / 0.5));
  };
  // the change comes to rest on the floor in front of the desk
  const landing = (tau) => ({ x: 1.9, y: 0.37, z: ZD + 1.1, k: ease((tau - 7) / 6), gone: ease((tau - tOut) / (2 * BEAT)) });
  // no portal: the film ends here
  const portal = { mat: { uniforms: { uFlat: { value: 0 } } } };
  return { scene, portal, update, landing };
}
