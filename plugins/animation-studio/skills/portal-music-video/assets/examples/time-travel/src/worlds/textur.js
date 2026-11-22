// World 6 "Zeile für Zeile 1998" - the sequence. Textures arrive: a corridor papered with code, tiled floor,
// lamps with halos. The code runs along the walls; on "Schneller. Schneller." it starts to race.
// At the end: Friday, 17:00, and the door.
import * as THREE from 'three';
import { canvasTex, FLAT, hash, MONO, over, sign } from '../kit.js';
import { makePortal } from '../portal.js';
import { BEAT, LINES, STEP, V } from '../song.js';

export const id = 'textur';
export const beats = 32;
export const year = 1998;
export const flight = { sway: 2.6, waves: 2, rise: 0.5 };
export const rollIn = true; // a jump in time
export const carryColor = 0xd8e4ff;
export const carryStyle = 'crate';
export const res = 540;
export const look = { levels: 0 };
export const glow = 0.5;

const BG = 0x05060a;
const TOKENS = ['if (ok)', 'merge();', '// TODO', 'return true;', 'LGTM', 'approve()', 'test.skip', 'push --force', 'deploy();', 'ship it', '} else {', 'const bot =', 'await ai', '// fix later', 'while (1)', 'catch {}'];
const COLS = ['#35e06a', '#35e06a', '#ffb000', '#cfd8e8', '#35e06a', '#ff5040'];

function codeTex(seed) {
  return canvasTex(256, 256, (g) => {
    g.fillStyle = '#0a0f16', g.fillRect(0, 0, 256, 256);
    g.font = 'bold 13px monospace';
    for (let r = 0; r < 16; r++) {
      let x = 6 + Math.floor(hash(seed + r * 3.3) * 4) * 12;
      for (let i = 0; i < 3 && x < 230; i++) {
        const n = seed * 7 + r * 13 + i * 29;
        const tk = TOKENS[Math.floor(hash(n) * TOKENS.length)];
        g.fillStyle = tk === 'test.skip' || tk === 'push --force' ? '#ff5040' : COLS[Math.floor(hash(n + 2) * COLS.length)];
        g.fillText(tk, x, 13 + r * 16);
        x += g.measureText(tk).width + 10;
      }
    }
    g.fillStyle = '#1c2632', g.fillRect(0, 0, 256, 1), g.fillRect(0, 0, 1, 256);
  }, { pixel: true, repeat: true });
}

export function build({ t0, L }) {
  const scene = new THREE.Scene();
  scene.background = new THREE.Color(BG);
  scene.fog = new THREE.Fog(BG, 22, 90);
  // light only for what flies along (the walls are painted, as in 1998)
  scene.add(new THREE.AmbientLight(0xffffff, 1.6));
  const lamp = new THREE.DirectionalLight(0xcfe0ff, 2.2);
  lamp.position.set(0, 8, 3);
  scene.add(lamp);
  const len = L + 20, W = 12, H = 8.5;
  const basic = (map, color = 0xffffff) => new THREE.MeshBasicMaterial({ map, color, fog: true });

  // walls of code
  const walls = [-1, 1].map((side) => {
    const tex = codeTex(side * 11 + 40);
    tex.repeat.set(len / H, 1);
    const m = new THREE.Mesh(new THREE.PlaneGeometry(len, H), basic(tex));
    m.rotation.y = -side * (Math.PI / 2);
    m.position.set(side * (W / 2), H / 2, -len / 2);
    scene.add(m);
    return { tex, side };
  });
  // tiled floor, panelled ceiling
  const tile = canvasTex(32, 32, (g) => {
    g.fillStyle = '#4a5360', g.fillRect(0, 0, 32, 32);
    for (let i = 0; i < 120; i++) g.fillStyle = `rgba(${hash(i) > 0.5 ? 255 : 0},${hash(i) > 0.5 ? 255 : 0},${hash(i) > 0.5 ? 255 : 0},0.08)`, g.fillRect(Math.floor(hash(i * 3) * 32), Math.floor(hash(i * 7) * 32), 2, 2);
    g.fillStyle = '#222830', g.fillRect(0, 0, 32, 2), g.fillRect(0, 0, 2, 32);
  }, { pixel: true, repeat: true });
  tile.repeat.set(W / 2, len / 2);
  const floor = new THREE.Mesh(new THREE.PlaneGeometry(W, len), basic(tile));
  floor.rotation.x = -Math.PI / 2;
  floor.position.set(0, 0, -len / 2);
  scene.add(floor);
  const panel = tile.clone();
  panel.repeat.set(W / 3, len / STEP);
  const ceil = new THREE.Mesh(new THREE.PlaneGeometry(W, len), basic(panel, 0x505868));
  ceil.rotation.x = Math.PI / 2;
  ceil.position.set(0, H, -len / 2);
  scene.add(ceil);

  // lamps: a halo under the ceiling and a pool of light on the floor, every two beats
  const haloTex = canvasTex(64, 64, (g) => {
    const gr = g.createRadialGradient(32, 32, 0, 32, 32, 32);
    gr.addColorStop(0, 'rgba(255,255,255,1)'), gr.addColorStop(0.25, 'rgba(190,220,255,0.55)'), gr.addColorStop(1, 'rgba(120,170,255,0)');
    g.fillStyle = gr, g.fillRect(0, 0, 64, 64);
  });
  const haloMat = new THREE.SpriteMaterial({ map: haloTex, blending: THREE.AdditiveBlending, depthWrite: false, fog: true });
  const poolMat = new THREE.MeshBasicMaterial({ map: haloTex, blending: THREE.AdditiveBlending, transparent: true, depthWrite: false, fog: true, opacity: 0.5 });
  for (let k = 1; k < beats; k += 2) {
    const s = new THREE.Sprite(haloMat);
    s.scale.set(3.2, 3.2, 1);
    s.position.set(0, H - 0.5, -k * STEP);
    const p = new THREE.Mesh(new THREE.PlaneGeometry(7, 7), poolMat);
    p.rotation.x = -Math.PI / 2;
    p.position.set(0, 0.03, -k * STEP);
    scene.add(s, p);
  }

  // the words: the vocoder's line above (machine type), the answer below
  const signs = [];
  LINES.zeile.forEach((ln, i) => {
    const last = i === LINES.zeile.length - 1; // "Freitag. Fünf." stands on the end wall, above the door
    const z = -V * (ln.at[0] - t0) - 22;
    signs.push(sign(ln.words, ln.at.map((x) => x - t0), { z, y: 5.5, size: 1.0, font: MONO, color: 0x35e06a, posts: false }));
    signs.push(sign(ln.answer.words, ln.answer.at.map((x) => x - t0), { z: Math.max(z, -L + 0.3), y: last ? 4.15 : 3.7, size: last ? 0.62 : 1.25, font: FLAT, posts: false }));
  });
  signs.forEach((s) => scene.add(s.group));

  // end wall: the clock says Friday 17:00
  const endTex = canvasTex(512, 256, (g) => {
    g.fillStyle = '#2a303a', g.fillRect(0, 0, 512, 256);
    for (let i = 0; i < 300; i++) g.fillStyle = `rgba(0,0,0,${0.05 + hash(i) * 0.1})`, g.fillRect(hash(i * 3) * 512, hash(i * 5) * 256, 6, 6);
    g.fillStyle = '#0a0a0a', g.fillRect(96, 14, 320, 76);
    g.fillStyle = '#ff3020', g.font = 'bold 56px monospace', g.textAlign = 'center';
    g.fillText('FR 17:00', 256, 72);
  }, { pixel: true });
  const end = new THREE.Mesh(new THREE.PlaneGeometry(W, H), basic(endTex));
  end.position.set(0, H / 2, -L - 0.08);
  scene.add(end);
  const door = new THREE.Mesh(new THREE.PlaneGeometry(5.2, 3.7), new THREE.MeshBasicMaterial({ color: 0x35e06a, fog: true }));
  door.position.set(0, 1.8, -L - 0.04);
  scene.add(door);
  const portal = makePortal({ shape: 'rect', w: 4.6, h: 3.4, flat: 0x05060c });
  portal.mesh.position.set(0, 1.7, -L);
  scene.add(portal.mesh);

  const tFast = LINES.zeile[2].answer.at[0] - t0;
  const update = (tau) => {
    signs.forEach((s) => s.update(tau));
    const lb = tau / BEAT;
    const pulse = Math.exp(-(lb - Math.floor(lb)) * 4);
    haloMat.opacity = 0.6 + 0.4 * pulse;
    poolMat.opacity = 0.3 + 0.3 * pulse;
    // the code runs towards us; from "Schneller" on it accelerates
    const run = 0.03 * tau + 0.035 * Math.max(0, tau - tFast) ** 2;
    for (const w of walls) w.tex.offset.x = -w.side * run;
  };
  void over;
  return { scene, portal, update };
}
