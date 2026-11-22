// World 5 "Feierabend 1993" - verse 2. Shaded polygons: light and dark sides, low-poly hills, no textures yet.
// "Der Mensch geht heim. Die Maschine bleibt." A blocky man walks home past us; the machines stay at the desks.
// "Der Test war rot. Der Test ist fort." The red cube sinks away - and every screen turns green.
import * as THREE from 'three';
import { clamp, ease, hash, roadSign } from '../kit.js';
import { makePortal } from '../portal.js';
import { BEAT, LINES, STEP, V } from '../song.js';

export const id = 'polygon';
export const beats = 32;
export const year = 1993;
export const flight = { sway: 2.4, waves: 1, rise: 1.1 };
export const rollIn = true; // a jump in time
export const carryColor = 0x40e0ff;
export const carryStyle = 'gem';
export const res = 360;
export const look = { levels: 24, dither: 1.0, scan: 0 };
export const glow = 0.3;

const BG = 0x3b2360, AMBER = 0xffb000, RED = 0xff2a1a, GREEN = 0x2bff88;

export function build({ t0, L }) {
  const scene = new THREE.Scene();
  scene.background = new THREE.Color(BG);
  scene.fog = new THREE.Fog(BG, 35, 125);
  scene.add(new THREE.AmbientLight(0x9080d0, 1.5));
  const sun = new THREE.DirectionalLight(0xffc890, 3.2);
  sun.position.set(7, 6, 5);
  scene.add(sun);
  const flat = (color) => new THREE.MeshLambertMaterial({ color, flatShading: true });
  const box = (w, h, d, col, x, y, z, parent = scene) => {
    const m = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), typeof col === 'number' ? flat(col) : col);
    m.position.set(x, y, z);
    parent.add(m);
    return m;
  };

  const len = L + 70;
  const ground = new THREE.Mesh(new THREE.PlaneGeometry(140, len), flat(0x4a3f78));
  ground.rotation.x = -Math.PI / 2;
  ground.position.set(0, 0, -len / 2);
  scene.add(ground);
  const road = new THREE.Mesh(new THREE.PlaneGeometry(5.4, len), flat(0x7566b4));
  road.rotation.x = -Math.PI / 2;
  road.position.set(0, 0.02, -len / 2);
  scene.add(road);

  // hills
  for (let i = 0; i < 26; i++) {
    const side = i % 2 ? 1 : -1;
    const h = 6 + hash(i * 3.1) * 16;
    const cone = new THREE.Mesh(new THREE.ConeGeometry(h * 0.8, h, 4 + Math.floor(hash(i * 5.3) * 3)), flat([0x8a4fb0, 0xc0508c, 0x5a56c8][i % 3]));
    cone.position.set(side * (22 + hash(i * 7.7) * 34), h / 2, -hash(i * 1.9) * len);
    cone.rotation.y = hash(i) * 3;
    scene.add(cone);
  }

  // desks with monitors; behind every second desk a machine that stays
  const screen = new THREE.MeshBasicMaterial({ color: AMBER, fog: true });
  const machines = [];
  for (let k = 1; k < beats - 2; k += 2) {
    for (const side of [-1, 1]) {
      const z = -k * STEP, x = side * 5.4;
      box(1.4, 0.14, 2.6, 0xb08a5a, x, 1.0, z);
      box(0.2, 1.0, 0.2, 0x70583a, x, 0.5, z - 1.1), box(0.2, 1.0, 0.2, 0x70583a, x, 0.5, z + 1.1);
      box(0.9, 0.85, 1.0, 0xd8d0c0, x + side * 0.1, 1.5, z);
      box(0.05, 0.6, 0.75, screen, x - side * 0.37, 1.52, z);
      if (k % 4 === 1) {
        const g = new THREE.Group();
        g.position.set(side * 8.6, 0, z);
        box(1.8, 3.2, 1.6, 0x7f8fb8, 0, 1.6, 0, g);
        box(1.3, 1.1, 1.3, 0xaab8dc, 0, 3.8, 0, g);
        box(0.05, 0.3, 0.9, screen, -side * 0.68, 3.9, 0, g); // the eye
        box(0.3, 1.8, 0.3, 0x5f6c90, -side * 0.6, 2.0, 1.0, g), box(0.3, 1.8, 0.3, 0x5f6c90, -side * 0.6, 2.0, -1.0, g);
        scene.add(g);
        machines.push({ g, ph: k });
      }
    }
  }

  // the man who goes home
  const man = new THREE.Group();
  box(0.7, 0.95, 0.4, 0x3a6ad8, 0, 1.45, 0, man);
  box(0.45, 0.45, 0.45, 0xf0c090, 0, 2.2, 0, man);
  const legs = [-1, 1].map((s) => {
    const p = new THREE.Group();
    p.position.set(s * 0.18, 1.0, 0);
    box(0.28, 1.0, 0.3, 0x28304a, 0, -0.5, 0, p);
    man.add(p);
    return p;
  });
  const arms = [-1, 1].map((s) => {
    const p = new THREE.Group();
    p.position.set(s * 0.48, 1.85, 0);
    box(0.22, 0.85, 0.24, 0x3a6ad8, 0, -0.4, 0, p);
    man.add(p);
    return p;
  });
  box(0.5, 0.4, 0.14, 0x6a4a2a, 0.5, 1.0, 0.1, man); // briefcase
  scene.add(man);

  // the red test
  const zt = -V * (LINES.rot.at[0] - t0) - 22;
  box(1.9, 1.2, 1.9, 0x8f84c8, 3.3, 0.6, zt);
  const test = box(1.5, 1.5, 1.5, new THREE.MeshLambertMaterial({ color: RED, emissive: 0x500000, flatShading: true }), 3.3, 2.2, zt);

  // the words
  const o = { board: 0x1c1238 };
  const signs = [
    roadSign(LINES.mensch, t0, L, 24, o), roadSign(LINES.bleibt, t0, L, 24, o),
    roadSign(LINES.prueft, t0, L, 24, o), roadSign(LINES.schreibt, t0, L, 22, o),
    roadSign(LINES.rot, t0, L, 24, o), roadSign(LINES.fort, t0, L, 24, o),
    roadSign(LINES.jetzt, t0, L, 22, o), roadSign(LINES.ort, t0, L, 20, { ...o, y: 5.4 }),
  ];
  signs.forEach((s) => scene.add(s.group));

  // the way out: a lift door in a wall
  box(22, 9.5, 2, 0x6f60b8, 0, 4.75, -L - 1.08);
  box(5.9, 4.0, 0.3, 0xe8e0ff, 0, 2.0, -L - 0.18);
  const portal = makePortal({ shape: 'rect', w: 5, h: 3.4, flat: 0x05060a });
  portal.mesh.position.set(0, 1.7, -L);
  scene.add(portal.mesh);

  const T = (songT) => songT - t0;
  const cA = new THREE.Color(AMBER), cR = new THREE.Color(RED), cG = new THREE.Color(GREEN), cK = new THREE.Color(0x1a1a1a);
  const update = (tau) => {
    signs.forEach((s) => s.update(tau));
    const lb = tau / BEAT;
    const pulse = Math.exp(-(lb - Math.floor(lb)) * 4);
    // he walks towards us and past, at walking pace
    man.position.set(-2.3, 0, -34 + 2.2 * tau);
    man.rotation.y = 0;
    const sw = Math.sin(tau * 7);
    legs[0].rotation.x = sw * 0.6, legs[1].rotation.x = -sw * 0.6;
    arms[0].rotation.x = -sw * 0.5, arms[1].rotation.x = sw * 0.5;
    for (const m of machines) m.g.scale.y = 1 + 0.04 * pulse;
    // screens: amber - red on "rot" - dark on "fort" - green on "Grün"
    if (tau < T(LINES.rot.at[3])) screen.color.copy(cA);
    else if (tau < T(LINES.fort.at[3])) screen.color.copy(cR);
    else if (tau < T(LINES.jetzt.at[0])) screen.color.copy(cK);
    else screen.color.copy(cG).multiplyScalar(0.75 + 0.25 * pulse);
    // the test sinks into its base between "Der Test ist" and "fort"
    const gone = ease((tau - T(LINES.fort.at[0])) / (LINES.fort.at[3] - LINES.fort.at[0]));
    test.position.y = 2.2 - 2.4 * gone;
    test.rotation.y = tau * 1.2;
    test.visible = gone < 1;
    void clamp;
  };
  return { scene, portal, update };
}
