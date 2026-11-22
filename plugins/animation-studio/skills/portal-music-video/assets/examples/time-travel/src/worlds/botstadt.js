// World 13 "Bot prüft Bot" - the last hook, all voices: the high point of the journey, and the future.
//
// The flight is a tour, not a corridor (lengths in beats; the hook lines are sung where they are named):
//    0 -  6  into the street canyon at lamp height, through the first gates that scan us
//    6 - 14  straight up between the towers and out over the roofs: the city lies there to the horizon, a grid
//            of light under a night sky, traffic crossing in the air - and far ahead the last gate, rings as
//            tall as a mountain around a green sun  ("Sieht gut aus.")
//   14 - 22  a long bank over the roofs, the gaze on that gate
//   22 - 30  the dive back into the canyon, with the changes that are thrown out  ("Raus. Raus. Raus.")
//   30 - 42  low and fast through the gates to the colossus that straddles the road: it looks down, scans us,
//            and we pass between its legs  ("Bot prüft Bot.")
//   42 - 53  up once more, face to face with the rings, which now send out waves of light
//   53 - 56  down to the gatehouse between two giants; its arch holds the portal  ("Alles im Lot.")
// Words: every line of the song is built into the city (roof sign, gate panels, the barrier, the gatehouse); LGTM is
// written by a swarm of drones right in front of the camera.
// The light is painted, not computed: glowing faces, additive haze and beams, bloom in the developed picture.
import * as THREE from 'three';
import { canvasTex, clamp, ease, hash, MONO, over, rausShots, sign, word } from '../kit.js';
import { makePortal } from '../portal.js';
import { BEAT, EYE, HOOK_SYL, HOOKS3, LINES, STEP, V } from '../song.js';
import { levelsAt } from '../spectrum.js';
import { buildCity, CITY_LOOK, cubeLetters, exitGate } from '../stadt.js';

export const id = 'botstadt';
export const beats = 56;
export const year = 2032;
export const carryColor = 0x2bff88;
export const carryStyle = 'orb';
export const glow = 0; // the picture has real bloom here (look), not the blurred copy
export const look = CITY_LOOK;
export const rollIn = true;
export const flight = { fov: 76 };

const GREEN = 0x2bff88;
const L_ = beats * STEP;
const KOLOSS_BEAT = 42, KZ = -KOLOSS_BEAT * STEP, KS = 11; // the colossus: where, and how many times a robot's size
const HERO = [0, 44, -L_ - 40]; // centre of the last gate's rings

// ---- the flight: [beat, sideways, height above the road's eye line]
const KEYS = [[-2, 0, 0], [0, 0, 0], [3, 0, 0.3], [6, 1.5, 8], [10, 4, 30], [14, 2, 46], [19, -5, 44], [22, -6, 30], [26, -2, 6], [28, -0.6, 3.2], [30, 0, 3], [36, 0.6, 3.6], [42, 0, 4.5], [46, 0, 15], [49.5, 0, 13], [52.4, 0, 3.6], [55, 0, 0.3], [56, 0, 0], [58, 0, 0]];
const cr = (a, b, c, d, t) => 0.5 * (2 * b + (c - a) * t + (2 * a - 5 * b + 4 * c - d) * t * t + (3 * b - a - 3 * c + d) * t * t * t);
function at(b) {
  let i = 1;
  while (i < KEYS.length - 3 && KEYS[i + 1][0] <= b) i++;
  const t = clamp((b - KEYS[i][0]) / (KEYS[i + 1][0] - KEYS[i][0]));
  const f = (k) => cr(KEYS[i - 1][k], KEYS[i][k], KEYS[i + 1][k], KEYS[i + 2][k], t);
  return [f(1), Math.max(0, f(2))];
}
const bell = (x, a, b, f = 2.4) => ease((x - a) / f) * (1 - ease((x - (b - f)) / f));
/** The engine asks here where the camera is and where it looks. */
export function path(tau) {
  const b = tau / BEAT;
  const [x, y] = at(b);
  const hero = Math.max(bell(b, 9, 21.5), bell(b, 43.5, 54.4)), kol = bell(b, 23, 38.6, 3);
  return kol > hero ? { x, y, look: [0, 2.4 * KS, KZ + 2], w: 0.85 * kol } : { x, y, look: HERO, w: 0.8 * hero };
}

/** Several boxes as ONE mesh (one draw call): [w, h, d, x, y, z, colour]. The colour goes into the vertices. */
function boxes(list) {
  const pos = [], nor = [], col = [], idx = [], c = new THREE.Color();
  for (const [w, h, d, x, y, z, hex] of list) {
    const g = new THREE.BoxGeometry(w, h, d), p = g.attributes.position, n = g.attributes.normal, base = pos.length / 3;
    c.setHex(hex);
    for (let i = 0; i < p.count; i++) pos.push(p.getX(i) + x, p.getY(i) + y, p.getZ(i) + z), nor.push(n.getX(i), n.getY(i), n.getZ(i)), col.push(c.r, c.g, c.b);
    for (let i = 0; i < g.index.count; i++) idx.push(g.index.getX(i) + base);
    g.dispose();
  }
  const out = new THREE.BufferGeometry();
  out.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
  out.setAttribute('normal', new THREE.Float32BufferAttribute(nor, 3));
  out.setAttribute('color', new THREE.Float32BufferAttribute(col, 3));
  out.setIndex(idx);
  return out;
}
const STEEL = 0x8f9c96, DARK = 0x1c2622;
// a robot's torso with hip, chest plate, legs and feet; `stance` = how far apart it stands
const bodyGeo = (stance, hip) => boxes([[0.8, 0.9, 0.55, 0, 0, 0, STEEL], [hip, 0.18, 0.4, 0, -0.52, 0, DARK], [0.62, 0.34, 0.06, 0, 0.12, 0.29, DARK],
  [0.22, 0.5, 0.26, -stance, -0.86, 0, DARK], [0.22, 0.5, 0.26, stance, -0.86, 0, DARK], [0.26, 0.12, 0.38, -stance, -1.16, 0.05, STEEL], [0.26, 0.12, 0.38, stance, -1.16, 0.05, STEEL]]);
const PARTS = {
  body: bodyGeo(0.2, 0.5),
  wide: bodyGeo(0.44, 1.1), // the colossus stands astride the road
  head: boxes([[0.56, 0.44, 0.5, 0, 0, 0, STEEL], [0.04, 0.4, 0.04, 0.16, 0.42, 0, DARK]]),
  eye: boxes([[0.44, 0.11, 0.05, 0, 0.02, 0.27, 0xffffff], [0.09, 0.09, 0.09, 0.16, 0.64, 0, 0xffffff]]),
  arm: boxes([[0.18, 0.5, 0.2, 0, -0.25, 0, STEEL], [0.15, 0.46, 0.17, 0, -0.7, 0, DARK], [0.22, 0.16, 0.24, 0, -0.98, 0, STEEL]]),
  jet: new THREE.ConeGeometry(0.3, 1.1, 12, 1, true),
};
const beam = (color, opacity) => new THREE.MeshBasicMaterial({ color, blending: THREE.AdditiveBlending, transparent: true, depthWrite: false, opacity, fog: false, side: THREE.DoubleSide });

/** A robot: torso with legs, head with a visor and antenna, two arms that swing at the shoulder, a jet of light. */
function robot(metal, body = PARTS.body) {
  const g = new THREE.Group();
  g.add(new THREE.Mesh(body, metal));
  const head = new THREE.Group();
  head.position.y = 0.72;
  const eye = new THREE.Mesh(PARTS.eye, new THREE.MeshBasicMaterial({ color: GREEN, fog: false }));
  head.add(new THREE.Mesh(PARTS.head, metal), eye);
  g.add(head);
  const arms = [-1, 1].map((sx) => {
    const m = new THREE.Mesh(PARTS.arm, metal);
    m.position.set(sx * 0.52, 0.34, 0);
    g.add(m);
    return m;
  });
  const jet = new THREE.Mesh(PARTS.jet, beam(0x9dffc8, 0.5));
  jet.rotation.x = Math.PI;
  jet.position.y = -1.75;
  g.add(jet);
  return { g, head, eye, arms, jet };
}

/** The colossus: a figure of human build, in its own units (feet at 0, head top at 3.2), with strips of light along
 *  its legs, body and arms so that its outline reads against the night. */
function colossus(metal, glow) {
  const W = 0xffffff, g = new THREE.Group();
  g.add(new THREE.Mesh(boxes([
    [0.26, 1.25, 0.3, -0.42, 0.625, 0, DARK], [0.26, 1.25, 0.3, 0.42, 0.625, 0, DARK], // legs
    [0.34, 0.14, 0.5, -0.42, 0.07, 0.08, STEEL], [0.34, 0.14, 0.5, 0.42, 0.07, 0.08, STEEL], // feet
    [0.3, 0.22, 0.34, -0.42, 0.66, 0.02, STEEL], [0.3, 0.22, 0.34, 0.42, 0.66, 0.02, STEEL], // knees
    [1.1, 0.26, 0.42, 0, 1.38, 0, DARK], // hips
    [0.95, 1.0, 0.55, 0, 2.0, 0, STEEL], // chest
    [0.7, 0.36, 0.06, 0, 2.12, 0.29, DARK], // chest plate
    [1.5, 0.2, 0.5, 0, 2.52, 0, STEEL], // shoulders
    [0.2, 0.14, 0.2, 0, 2.66, 0, DARK], // neck
  ]), metal));
  g.add(new THREE.Mesh(boxes([
    [0.035, 1.2, 0.035, -0.28, 0.65, 0.16, W], [0.035, 1.2, 0.035, 0.28, 0.65, 0.16, W], [0.035, 1.2, 0.035, -0.56, 0.65, 0.16, W], [0.035, 1.2, 0.035, 0.56, 0.65, 0.16, W],
    [0.035, 0.95, 0.035, -0.48, 2.0, 0.28, W], [0.035, 0.95, 0.035, 0.48, 2.0, 0.28, W], [1.5, 0.035, 0.035, 0, 2.63, 0.26, W], [1.1, 0.035, 0.035, 0, 1.25, 0.22, W],
  ]), glow));
  const head = new THREE.Group();
  head.position.y = 2.98;
  head.add(new THREE.Mesh(boxes([[0.52, 0.5, 0.5, 0, 0, 0, STEEL], [0.05, 0.5, 0.05, 0.18, 0.5, 0, DARK]]), metal));
  const eye = new THREE.Mesh(boxes([[0.42, 0.12, 0.05, 0, 0.03, 0.27, W], [0.1, 0.1, 0.1, 0.18, 0.78, 0, W]]), new THREE.MeshBasicMaterial({ color: GREEN, fog: false }));
  head.add(eye);
  g.add(head);
  const arms = [-1, 1].map((sx) => {
    const a = new THREE.Group();
    a.position.set(sx * 0.86, 2.5, 0);
    a.add(new THREE.Mesh(boxes([[0.22, 0.62, 0.24, 0, -0.33, 0, STEEL], [0.19, 0.6, 0.2, 0, -0.92, 0, DARK], [0.26, 0.2, 0.28, 0, -1.3, 0, STEEL]]), metal));
    a.add(new THREE.Mesh(boxes([[0.035, 1.2, 0.035, sx * 0.13, -0.65, 0.13, W]]), glow));
    g.add(a);
    return a;
  });
  return { g, head, eye, arms };
}

export function build({ t0, L }) {
  const scene = new THREE.Scene();
  // the road is kept free where the colossus stands, and no bridge crosses the last approach
  const city = buildCity(scene, { L, beats, seed: 0, clear: [[KZ + 13, KZ - 13]], bridges: (k) => k < 40, levels: (tau, out) => levelsAt(t0 + tau, out) });
  const add = (o) => (scene.add(o), o);
  const camAt = (z) => { const [x, y] = at(-z / STEP); return [x, EYE + y]; }; // where the camera is when it passes z
  const metal = new THREE.MeshStandardMaterial({ vertexColors: true, roughness: 0.27, metalness: 0.85 });

  // LGTM in the sky, one letter per syllable, a little above the flight

  // ---- the drone swarm. It flies ahead of us, and every time the vocoder sings L-G-T-M it forms the four letters
  // right in front of the camera, one per syllable, wherever we are flying and looking. After the last hook it
  // settles as the name over the last gate.
  const GLYPH = {
    L: ['10000', '10000', '10000', '10000', '10000', '10000', '11111'],
    G: ['01110', '10001', '10000', '10111', '10001', '10001', '01110'],
    T: ['11111', '00100', '00100', '00100', '00100', '00100', '00100'],
    M: ['10001', '11011', '10101', '10101', '10001', '10001', '10001'],
  };
  const PER = 160, ND = PER * 4;
  const drones = add(new THREE.InstancedMesh(new THREE.BoxGeometry(0.2, 0.2, 0.2), new THREE.MeshBasicMaterial({ color: new THREE.Color(0xb8ffd8).multiplyScalar(2.6), fog: false }), ND));
  drones.frustumCulled = false;
  // where drone k of letter i sits inside its letter (in cells; every cell holds a small square of drones)
  const spots = [...'LGTM'].map((ch) => {
    const cells = [];
    GLYPH[ch].forEach((row, r) => [...row].forEach((v, x) => v === '1' && cells.push([x - 2, 3 - r])));
    return Array.from({ length: PER }, (_, d) => {
      const c = cells[d % cells.length], j = Math.floor(d / cells.length);
      return [c[0] + ((j % 3) - 1) * 0.3, c[1] + ((Math.floor(j / 3) % 3) - 1) * 0.3];
    });
  });
  const hooks = HOOKS3.map((h) => ({ syl: HOOK_SYL.map((x) => h + x - t0), to: h - t0 + 3.7 }));
  let curTau = 0;
  const cR = new THREE.Vector3(), cU = new THREE.Vector3(), cF = new THREE.Vector3(), P = new THREE.Vector3();
  const onPass = ({ cam }) => {
    const tau = curTau, lb = tau / BEAT, pulse = Math.exp(-(lb - Math.floor(lb)) * 4);
    cR.set(1, 0, 0).applyQuaternion(cam.quaternion), cU.set(0, 1, 0).applyQuaternion(cam.quaternion), cF.set(0, 0, -1).applyQuaternion(cam.quaternion);
    const settle = ease((lb - (beats - 5.5)) / 3); // the end: the name over the gatehouse
    for (let d = 0; d < ND; d++) {
      const i = Math.floor(d / PER), k = d % PER, a = d * 0.37, [sx, sy] = spots[i][k];
      // loose: a flowing cloud of lights ahead and above
      let r = Math.sin(a + tau * 0.6) * 11 + Math.sin(a * 1.7 + tau * 1.3) * 3, u = 7 + Math.sin(a * 2.3 + tau * 0.8) * 3.5, fw = 34 + Math.cos(a * 1.3 + tau * 0.5) * 9;
      // formed: four letters in the upper middle of the picture, 13 units in front of us
      let w = 0;
      for (const h of hooks) w = Math.max(w, ease((tau - (h.syl[i] - 0.4)) / 0.4) * (1 - ease((tau - h.to) / 1.2)));
      r += ((i - 1.5) * 2.9 + sx * 0.36 - r) * w, u += (2.9 + sy * 0.36 - u) * w, fw += (13 - fw) * w;
      P.copy(cam.position).addScaledVector(cR, r).addScaledVector(cU, u).addScaledVector(cF, fw);
      if (settle > 0) { // fly to the fixed place over the gate
        P.x += ((i - 1.5) * 6.6 + sx * 1.05 - P.x) * settle, P.y += (19.5 + sy * 1.05 - P.y) * settle, P.z += (-L - 1 - P.z) * settle;
      }
      dummy.position.copy(P);
      dummy.rotation.set(0, 0, 0), dummy.scale.setScalar(1 + 0.5 * pulse);
      dummy.updateMatrix();
      drones.setMatrixAt(d, dummy.matrix);
    }
    drones.instanceMatrix.needsUpdate = true;
  };

  // ---- the gates (the city builds one every four beats): a bar of light that scans, a stamp, two robots, two searchlights
  const fade = canvasTex(4, 64, (g) => {
    const gr = g.createLinearGradient(0, 64, 0, 0);
    gr.addColorStop(0, '#ffffff'), gr.addColorStop(1, '#000000'); // (an alpha map is read from the brightness)
    g.fillStyle = gr, g.fillRect(0, 0, 4, 64);
  });
  const coneGeo = new THREE.CylinderGeometry(1.7, 0.1, 46, 20, 1, true);
  coneGeo.translate(0, 23, 0);
  const gates = [];
  for (let k = 4; k < beats - 1; k += 4) {
    if (Math.abs(k - KOLOSS_BEAT) <= 2) continue; // no gate under the colossus
    const z = -k * STEP;
    const sheet = add(new THREE.Mesh(new THREE.PlaneGeometry(10.1, 0.14), beam(0xbfffd8, 0)));
    sheet.position.set(0, 6.3, z);
    const stamp = word('LGTM', { font: MONO, size: 0.62, color: GREEN });
    stamp.mesh.position.set(-stamp.width / 2, 6.95, z);
    stamp.mesh.material.fog = false;
    add(stamp.mesh);
    const eyes = [], cones = [];
    for (const side of [-1, 1]) {
      const r = robot(metal);
      r.g.position.set(side * 4.9, 2.5, z);
      r.g.scale.setScalar(1.1);
      r.g.rotation.y = -side * 1.1; // half towards each other, half towards whoever comes down the road
      add(r.g);
      eyes.push({ ...r, bot: r.g, side });
      const cone = add(new THREE.Mesh(coneGeo, new THREE.MeshBasicMaterial({ color: 0xbfffd8, alphaMap: fade, blending: THREE.AdditiveBlending, transparent: true, depthWrite: false, opacity: 0.1, side: THREE.DoubleSide, fog: false })));
      cone.position.set(side * 5.2, 6.4, z);
      cones.push({ cone, side });
    }
    gates.push({ k, sheet, stamp: stamp.mesh, eyes, cones, panel: k >= 24 && k <= 32 });
  }

  // lane markings and a haze of light that lies in the canyon (seen from above the road glows)
  for (const x of [-3.4, 3.4]) {
    const s = add(new THREE.Mesh(new THREE.BoxGeometry(0.1, 0.03, L + 60), new THREE.MeshBasicMaterial({ color: 0x59d0ff, fog: true })));
    s.position.set(x, 0.02, -(L + 60) / 2);
  }
  const across = canvasTex(64, 4, (g) => {
    const gr = g.createLinearGradient(0, 0, 64, 0);
    gr.addColorStop(0, '#000'), gr.addColorStop(0.5, '#fff'), gr.addColorStop(1, '#000');
    g.fillStyle = gr, g.fillRect(0, 0, 64, 4);
  });
  for (const [y, op] of [[1.4, 0.1], [7, 0.04]]) {
    const hz = add(new THREE.Mesh(new THREE.PlaneGeometry(30, L + 60), new THREE.MeshBasicMaterial({ color: 0x35ffa0, alphaMap: across, blending: THREE.AdditiveBlending, transparent: true, depthWrite: false, opacity: op, fog: false })));
    hz.rotation.x = -Math.PI / 2;
    hz.position.set(0, y, -(L + 60) / 2);
  }

  // ---- light streaks rushing past, and data rising like sparks
  const NS = 70, streakLen = L + 80;
  const streaks = add(new THREE.InstancedMesh(new THREE.BoxGeometry(0.05, 0.05, 7), beam(0xcfffe4, 0.7), NS));
  streaks.frustumCulled = false;
  const dummy = new THREE.Object3D();
  const NP = 4200, sp = new Float32Array(NP * 3);
  for (let i = 0; i < NP; i++) sp.set([(hash(i * 1.1) - 0.5) * 70, hash(i * 2.3) * 60, -hash(i * 3.7) * streakLen], i * 3);
  const sg = new THREE.BufferGeometry();
  sg.setAttribute('position', new THREE.BufferAttribute(sp, 3));
  const sparks = add(new THREE.Points(sg, new THREE.PointsMaterial({ color: 0x7dffb0, size: 0.11, blending: THREE.AdditiveBlending, transparent: true, depthWrite: false, opacity: 0.8, fog: false })));
  sparks.frustumCulled = false;

  // ---- the colossus: the gatekeeper. It stands astride the road and holds a barrier across it; when the song has said
  // "Bot prüft Bot" its eyes turn green, the barrier swings up and it waves us through between its legs.
  const kolGlow = new THREE.MeshBasicMaterial({ color: 0xff3b30, fog: false }); // its outline: red until it lets us pass
  const kol = colossus(metal, kolGlow);
  kol.g.scale.setScalar(KS);
  kol.g.position.set(0, 0, KZ);
  add(kol.g);
  const chest = word('LGTM', { font: MONO, size: 0.2, color: GREEN });
  chest.mesh.position.set(-chest.width / 2, 2.02, 0.34);
  chest.mesh.material.fog = false;
  kol.g.add(chest.mesh);
  const scanGeo = new THREE.CylinderGeometry(0.02, 0.6, 2.8, 20, 1, true); // a cone of light from its visor to the road
  scanGeo.translate(0, -1.4, 0);
  const scan = new THREE.Mesh(scanGeo, beam(0x9dffc8, 0.16));
  scan.position.set(0, 0, 0.3);
  kol.head.add(scan);
  // the barrier: red and white, hinged at its left hand
  const barrier = new THREE.Group();
  barrier.position.set(-7.2, 5.0, KZ + 0.32 * KS);
  barrier.add(new THREE.Mesh(boxes(Array.from({ length: 12 }, (_, i) => [1.2, 0.5, 0.5, 0.6 + i * 1.2, 0, 0, i % 2 ? 0xffffff : 0xff3b30])), new THREE.MeshBasicMaterial({ vertexColors: true, fog: false })));
  add(barrier);

  // ---- the last gate: a green sun, rings as tall as a mountain, a pillar of light, waves that run out from it
  const sunTex = canvasTex(128, 128, (g) => {
    const gr = g.createRadialGradient(64, 64, 0, 64, 64, 64);
    gr.addColorStop(0, 'rgba(235,255,244,1)'), gr.addColorStop(0.2, 'rgba(90,255,160,0.75)'), gr.addColorStop(0.55, 'rgba(30,200,110,0.2)'), gr.addColorStop(1, 'rgba(0,120,60,0)');
    g.fillStyle = gr, g.fillRect(0, 0, 128, 128);
  });
  const sun = add(new THREE.Sprite(new THREE.SpriteMaterial({ map: sunTex, blending: THREE.AdditiveBlending, depthWrite: false, fog: false })));
  sun.position.set(HERO[0], HERO[1], HERO[2] - 12);
  sun.scale.set(170, 170, 1);
  const hot = (hex, k) => new THREE.MeshBasicMaterial({ color: new THREE.Color(hex).multiplyScalar(k), fog: false });
  const rings = [[30, 0.9, 0xffffff, 1.05], [42, 1.3, GREEN, 0.95], [56, 1.7, 0xbfffd8, 0.75]].map(([R, r, col, k], i) => {
    const m = add(new THREE.Mesh(new THREE.TorusGeometry(R, r, 12, 128), hot(col, k)));
    m.position.set(HERO[0], HERO[1], HERO[2] - i * 6);
    return m;
  });
  const pillar = add(new THREE.Mesh(new THREE.CylinderGeometry(2.2, 6, 420, 24, 1, true), beam(0x9dffc8, 0.1)));
  pillar.position.set(HERO[0], 210, HERO[2]);
  const waves = [0, 1, 2].map(() => {
    const m = add(new THREE.Mesh(new THREE.TorusGeometry(30, 0.5, 8, 96), beam(0xdfffee, 0)));
    m.position.set(HERO[0], HERO[1], HERO[2] + 2);
    return m;
  });
  // pieces of the gate still being set in place, circling it
  const NM = 26;
  const moons = add(new THREE.InstancedMesh(new THREE.BoxGeometry(2.6, 5, 1.2), new THREE.MeshStandardMaterial({ color: 0x9aa8a0, roughness: 0.3, metalness: 0.8, emissive: 0x0d5a34 }), NM));
  moons.frustumCulled = false;

  // the gatehouse: its arch holds the portal; two giants stand guard
  const stone = new THREE.MeshStandardMaterial({ color: 0x27322d, roughness: 0.35, metalness: 0.7 });
  for (const [x, y, w, h] of [[-9.25, 7, 13.5, 14], [9.25, 7, 13.5, 14], [0, 8.9, 5, 10.2]]) {
    const b = add(new THREE.Mesh(new THREE.BoxGeometry(w, h, 6), stone));
    b.position.set(x, y, -L - 3.2);
  }
  for (const x of [-2.75, 2.75, -15.9, 15.9]) {
    const s = add(new THREE.Mesh(new THREE.BoxGeometry(0.22, 14, 0.22), hot(GREEN, 2)));
    s.position.set(x, 7, -L - 0.15);
  }
  exitGate(scene, L);
  const portal = makePortal({ shape: 'rect', w: 5, h: 3.4, flat: 0x030a07 });
  portal.mesh.position.set(0, 1.7, -L);
  scene.add(portal.mesh);
  const giants = [-1, 1].map((side) => {
    const r = robot(metal);
    r.g.scale.setScalar(13);
    r.g.position.set(side * 19, 1.22 * 13, -L - 3);
    r.g.rotation.y = -side * 0.5;
    r.jet.visible = false;
    add(r.g);
    return { ...r, side };
  });

  // ---- the words hang where the flight passes: half-way between two gates, a little above the eye
  // ---- the words are built into the city: neon signs on frames, on a house front, on the colossus, on the gatehouse
  const signs = [];
  const boardMat = new THREE.MeshStandardMaterial({ color: 0x0c1411, roughness: 0.4, metalness: 0.6 });
  /** rows = [[words, song times], ...]; pos = bottom centre of the lowest row; pylons = it stands on legs from the ground */
  const billboard = (rows, pos, rotY, size, pylons, parent = scene) => {
    const g = new THREE.Group();
    g.position.set(...pos);
    g.rotation.y = rotY;
    const parts = rows.map(([words, times], r) => {
      const s = sign(words, times.map((x) => x - t0), { z: 0.22, y: (rows.length - 1 - r) * size * 1.55, size, posts: false });
      s.group.traverse((m) => m.material && (m.material.fog = false));
      g.add(s.group);
      signs.push(s);
      return s;
    });
    const w = Math.max(...parts.map((p) => p.width)) + size * 1.3, h = rows.length * size * 1.55 + size * 0.45, y0 = -size * 0.4;
    const board = new THREE.Mesh(new THREE.BoxGeometry(w, h, 0.3), boardMat);
    board.position.set(0, y0 + h / 2, 0);
    g.add(board);
    for (const [bx, by, bw, bh] of [[0, y0 + h + 0.09, w + 0.36, 0.18], [0, y0 - 0.09, w + 0.36, 0.18], [-w / 2 - 0.09, y0 + h / 2, 0.18, h + 0.36], [w / 2 + 0.09, y0 + h / 2, 0.18, h + 0.36]]) {
      const e = new THREE.Mesh(new THREE.BoxGeometry(bw, bh, 0.36), hot(GREEN, 1.7));
      e.position.set(bx, by, 0);
      g.add(e);
    }
    if (pylons) for (const sx of [-1, 1]) {
      const p = new THREE.Mesh(new THREE.BoxGeometry(0.6, pos[1], 0.6), boardMat);
      p.position.set(sx * w * 0.36, y0 - pos[1] / 2, -0.4);
      g.add(p);
    }
    parent.add(g);
    return g;
  };
  // "Sieht gut aus." - a roof sign on a tall frame, to the left of where we come up over the roofs
  billboard([[LINES.aus3.words, LINES.aus3.at]], [-15, camAt(-15 * STEP)[1] - 2.2, -15 * STEP], 0.5, 1.5, true);
  // "Raus. Raus. Raus." - one word on each of the next three gates, standing on the beam, leaning back so that the
  // dive from above reads them
  LINES.raus3.words.forEach((w, i) => {
    const g = billboard([[[w], [LINES.raus3.at[i]]]], [0, 7.35, -(24 + i * 4) * STEP], 0, 1.5, false);
    g.rotation.x = -0.32;
  });
  // "Bot prüft Bot." - on the barrier the colossus holds across the road
  billboard([[LINES.bot.words, LINES.bot.at]], [7.2, 0.95, 0.12], 0, 1.15, false, barrier);
  // "Alles im Lot." - over the arch of the gatehouse
  billboard([[LINES.lot.words, LINES.lot.at]], [0, 4.5, -L + 0.2], 0, 0.8, false);

  const update = (tau) => {
    const lb = tau / BEAT;
    const pulse = Math.exp(-(lb - Math.floor(lb)) * 4);
    city.update(tau);
    signs.forEach((s) => s.update(tau));
    const [px, pyOff] = at(lb), py = EYE + pyOff, cz = -V * tau; // where the camera is now


    curTau = tau; // the drones are placed in onPass, where the camera is known
    for (const g of gates) {
      const since = lb - g.k; // beats since we flew through this gate
      const run = clamp((since + 3) / 3); // the scan: the last three beats before we pass, top to bottom
      g.sheet.position.y = 6.3 - 6.2 * run;
      g.sheet.material.opacity = since >= -3 && since < 0 && camAt(-g.k * STEP)[1] < 4.6 ? 0.9 : 0; // only when we fly through the gate, not over it
      // the approval runs ahead: a gate lights up two bars before we reach it
      const lit = clamp((since + 8) / 0.4);
      g.stamp.material.opacity = 0.15 + 0.85 * lit * (0.75 + 0.25 * pulse);
      g.stamp.scale.setScalar(1 + 0.3 * (1 - clamp((since + 8) / 0.6)) * lit);
      g.stamp.visible = !g.panel; // a gate that carries a line of the song shows that instead
      for (const e of g.eyes) {
        e.eye.material.color.setHex(lit > 0.5 ? GREEN : 0xff3b30).multiplyScalar(1.3 + 1.2 * pulse);
        e.bot.position.y = 2.5 + 0.14 * Math.sin(lb * Math.PI * 0.5 + g.k + e.side);
        e.head.rotation.x = lit > 0.5 ? 0.22 * Math.max(0, Math.sin(lb * Math.PI)) : 0; // a nod: go ahead
        // the arm on the road side goes up and waves us through once the approval has arrived
        const road = e.side < 0 ? 1 : 0, wave = lit * (2.5 + 0.35 * Math.sin(lb * Math.PI * 2));
        e.arms[road].rotation.z = (e.side < 0 ? 1 : -1) * wave;
        e.arms[1 - road].rotation.x = 0.25 * Math.sin(lb * Math.PI * 0.5 + g.k);
        e.jet.material.opacity = 0.35 + 0.25 * pulse;
      }
      for (const c of g.cones) {
        c.cone.rotation.z = -c.side * (0.5 + 0.38 * Math.sin(lb * (Math.PI / 4) + g.k * 0.7));
        c.cone.rotation.x = 0.3 * Math.sin(lb * (Math.PI / 8) + g.k);
        c.cone.material.opacity = 0.03 + 0.06 * lit + 0.03 * pulse;
      }
    }
    for (let i = 0; i < NS; i++) {
      const z = -((((i * 9.7 + tau * (34 + hash(i) * 30)) % streakLen) + streakLen) % streakLen);
      const [cx, cy] = camAt(z);
      dummy.position.set(cx + (hash(i * 3.3) - 0.5) * 15, Math.max(0.3, cy - 3 + hash(i * 5.1) * 9), z); // they follow the flight's height
      dummy.rotation.set(0, 0, 0), dummy.scale.setScalar(1);
      dummy.updateMatrix();
      streaks.setMatrixAt(i, dummy.matrix);
    }
    streaks.instanceMatrix.needsUpdate = true;
    sparks.position.y = (tau * 0.9) % 4;

    // the colossus: it bends its head to us, its beam follows, its arms open the way
    const toK = clamp((lb - (KOLOSS_BEAT - 12)) / 9);
    const lift = ease((lb - 39.2) / 1.3); // "Bot prüft Bot." has been said: the barrier goes up
    barrier.rotation.z = 1.4 * lift;
    kol.head.rotation.x = 0.12 + 0.5 * ease(toK);
    kol.arms[0].rotation.x = -0.5 - 0.5 * lift; // the arm at the barrier
    kol.arms[1].rotation.z = 2.5 * lift + 0.2 * lift * Math.sin(lb * Math.PI); // the other one waves us through
    kol.eye.material.color.setHex(lift > 0.1 ? GREEN : 0xff3b30).multiplyScalar(1.8 + 1.6 * pulse);
    kolGlow.color.setHex(lift > 0.1 ? GREEN : 0xff3b30).multiplyScalar(1.5 + 0.9 * pulse);
    scan.material.opacity = 0.1 + 0.12 * pulse;
    scan.rotation.z = 0.12 * Math.sin(lb * Math.PI * 0.5);
    chest.mesh.material.opacity = lift > 0.1 ? 1 : 0.2;

    // the last gate
    rings.forEach((r, i) => {
      r.rotation.z = lb * (Math.PI / 24) * (i % 2 ? -1 : 1) + i;
      r.rotation.y = 0.3 * Math.sin(lb * (Math.PI / 12) + i * 2);
      r.rotation.x = 0.2 * Math.sin(lb * (Math.PI / 16) + i);
      r.scale.setScalar(1 + 0.02 * pulse);
    });
    sun.material.opacity = 0.26 + 0.1 * pulse;
    pillar.material.opacity = 0.07 + 0.05 * pulse;
    const loud = clamp((lb - 40) / 4); // from the colossus on, every bar sends a wave out of the gate
    waves.forEach((w, i) => {
      const ph = (((lb / 4 + i / 3) % 1) + 1) % 1;
      w.scale.setScalar(0.4 + ph * 3.2);
      w.material.opacity = loud * 0.28 * (1 - ph) ** 2;
    });
    for (let i = 0; i < NM; i++) {
      const a = (i / NM) * Math.PI * 2 + lb * (Math.PI / 48) * (i % 2 ? 1 : -1.3), R = 66 + (i % 3) * 7;
      dummy.position.set(HERO[0] + Math.cos(a) * R, HERO[1] + Math.sin(a) * R, HERO[2] - 4 + (i % 4) * 3);
      dummy.rotation.set(0, i, a), dummy.scale.setScalar(0.7 + hash(i) * 1.2);
      dummy.updateMatrix();
      moons.setMatrixAt(i, dummy.matrix);
    }
    moons.instanceMatrix.needsUpdate = true;
    const near = clamp((lb - (beats - 14)) / 6); // the last three bars: the giants raise an arm
    for (const gi of giants) {
      gi.arms[gi.side < 0 ? 1 : 0].rotation.z = (gi.side < 0 ? 1 : -1) * near * 2.3;
      gi.head.rotation.y = -gi.side * 0.4 * near;
      gi.head.rotation.x = 0.25 * near;
      gi.jet.visible = false;
      gi.eye.material.color.setHex(GREEN).multiplyScalar(1.4 + 1.2 * pulse);
    }
  };
  return { scene, portal, update, onPass, carry: rausShots(LINES.raus3.at, t0) };
}
