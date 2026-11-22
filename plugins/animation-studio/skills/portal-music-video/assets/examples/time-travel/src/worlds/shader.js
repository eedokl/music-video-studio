// World 7 "Sieht gut aus 2007" - the second hook. Real light: a glossy floor, cast shadows, glowing letters built
// from cubes that light their surroundings, dust in the air, a stream of changes rushing ahead of us.
import * as THREE from 'three';
import { clamp, hash, rausShots, roadSign, sign } from '../kit.js';
import { makePortal } from '../portal.js';
import { BEAT, HOOK_SYL, HOOKS2, LINES, STEP, V } from '../song.js';

export const id = 'shader';
export const beats = 32;
export const year = 2007;
export const flight = { sway: 3.0, waves: 1.5, rise: 0.3 };
export const rollIn = true; // a jump in time
export const carryColor = 0x2bff88;
export const carryStyle = 'orb';
export const glow = 0.7;

const BG = 0x05060c, GREEN = 0x2bff88;
const GLYPH = {
  L: ['10000', '10000', '10000', '10000', '10000', '10000', '11111'],
  G: ['01110', '10001', '10000', '10111', '10001', '10001', '01110'],
  T: ['11111', '00100', '00100', '00100', '00100', '00100', '00100'],
  M: ['10001', '11011', '10101', '10101', '10001', '10001', '10001'],
};

export function build({ t0, L }) {
  const scene = new THREE.Scene();
  scene.background = new THREE.Color(BG);
  scene.fog = new THREE.Fog(BG, 28, 125);
  scene.add(new THREE.HemisphereLight(0x8fa4ff, 0x0a0a14, 0.9));
  const key = new THREE.DirectionalLight(0xfff2e0, 2.4);
  key.castShadow = true;
  key.shadow.mapSize.set(2048, 2048);
  Object.assign(key.shadow.camera, { left: -30, right: 30, top: 30, bottom: -30, near: 1, far: 90 });
  key.shadow.bias = -0.0015;
  scene.add(key, key.target);

  const len = L + 70;
  const floor = new THREE.Mesh(new THREE.PlaneGeometry(90, len), new THREE.MeshStandardMaterial({ color: 0x10131c, roughness: 0.24, metalness: 0.35 }));
  floor.rotation.x = -Math.PI / 2;
  floor.position.set(0, 0, -len / 2);
  floor.receiveShadow = true;
  scene.add(floor);
  // lane markings as emissive strips
  const strip = new THREE.MeshStandardMaterial({ color: 0x000000, emissive: 0x59d0ff, emissiveIntensity: 1.4 });
  for (const x of [-3.4, 3.4]) {
    const s = new THREE.Mesh(new THREE.BoxGeometry(0.1, 0.04, len), strip);
    s.position.set(x, 0.02, -len / 2);
    scene.add(s);
  }

  // pillars with a light ring, every two beats
  const pillarMat = new THREE.MeshStandardMaterial({ color: 0xc8d0e4, roughness: 0.35, metalness: 0.15 });
  const ringMat = new THREE.MeshStandardMaterial({ color: 0x000000, emissive: 0x59d0ff, emissiveIntensity: 2 });
  const pGeo = new THREE.CylinderGeometry(0.5, 0.5, 9, 24), rGeo = new THREE.TorusGeometry(0.75, 0.08, 10, 32);
  rGeo.rotateX(Math.PI / 2);
  for (let k = 2; k < beats - 1; k += 2) {
    for (const side of [-1, 1]) {
      const p = new THREE.Mesh(pGeo, pillarMat);
      p.position.set(side * 7.2, 4.5, -k * STEP);
      p.castShadow = p.receiveShadow = true;
      const r = new THREE.Mesh(rGeo, ringMat);
      r.position.set(side * 7.2, 3.0, -k * STEP);
      scene.add(p, r);
    }
  }

  // the stream of changes: lit cubes rushing ahead on both sides
  const N = 150;
  const stream = new THREE.InstancedMesh(new THREE.BoxGeometry(0.5, 0.5, 0.5), new THREE.MeshStandardMaterial({ color: 0xe8ecf8, roughness: 0.4 }), N);
  stream.castShadow = true;
  stream.frustumCulled = false;
  const cols = [0xffffff, 0x2bff88, 0x59d0ff];
  for (let i = 0; i < N; i++) stream.setColorAt(i, new THREE.Color(cols[i % 3]));
  scene.add(stream);
  const dummy = new THREE.Object3D();

  // dust
  const dust = new Float32Array(1800 * 3);
  for (let i = 0; i < 1800; i++) dust.set([(hash(i * 1.1) - 0.5) * 34, hash(i * 2.3) * 9, -hash(i * 3.7) * len], i * 3);
  const dg = new THREE.BufferGeometry();
  dg.setAttribute('position', new THREE.BufferAttribute(dust, 3));
  const points = new THREE.Points(dg, new THREE.PointsMaterial({ color: 0x9fc0ff, size: 0.07, blending: THREE.AdditiveBlending, transparent: true, depthWrite: false, opacity: 0.7 }));
  points.frustumCulled = false;
  scene.add(points);

  // LGTM from glowing cubes; every letter carries its own light
  const camZ = (songT) => -V * (songT - t0);
  const cubeGeo = new THREE.BoxGeometry(0.42, 0.42, 0.42);
  const letters = [];
  for (const h of HOOKS2) {
    [...'LGTM'].forEach((ch, i) => {
      const cells = [];
      GLYPH[ch].forEach((row, r) => [...row].forEach((c, x) => c === '1' && cells.push([(x - 2) * 0.46, (6 - r) * 0.46])));
      const mat = new THREE.MeshStandardMaterial({ color: 0x0c3a22, emissive: GREEN, emissiveIntensity: 1.0, roughness: 0.5 });
      const m = new THREE.InstancedMesh(cubeGeo, mat, cells.length);
      cells.forEach(([x, y], n) => {
        dummy.position.set(x, y, 0), dummy.rotation.set(0, 0, 0), dummy.scale.setScalar(1), dummy.updateMatrix();
        m.setMatrixAt(n, dummy.matrix);
      });
      m.position.set(-4.8 + i * 3.2, 2.9, camZ(h) - 22 - i * 3);
      m.castShadow = true;
      m.visible = false;
      const light = new THREE.PointLight(GREEN, 0, 26, 1.6);
      light.position.set(m.position.x, 4.0, m.position.z + 1.2);
      scene.add(m, light);
      letters.push({ m, light, at: h + HOOK_SYL[i] - t0 });
    });
  }

  const aus = roadSign(LINES.aus2, t0, L, 24, { posts: false });
  scene.add(aus.group);

  // exit: a ring of light, RAUS three times above it
  const R = 2.42, cy = 1.9, zx = -L;
  const ring = new THREE.Mesh(new THREE.TorusGeometry(R + 0.12, 0.14, 16, 72), new THREE.MeshStandardMaterial({ color: 0x000000, emissive: 0xffffff, emissiveIntensity: 2 }));
  ring.position.set(0, cy, zx);
  scene.add(ring);
  const exitLight = new THREE.PointLight(0xffffff, 60, 30, 1.6);
  exitLight.position.set(0, cy, zx + 2);
  scene.add(exitLight);
  const portal = makePortal({ shape: 'circle', r: R, flat: 0x000000 });
  portal.mesh.position.set(0, cy, zx);
  scene.add(portal.mesh);
  const raus = LINES.raus2.words.map((w, i) => {
    const s = sign([w], [LINES.raus2.at[i] - t0], { z: zx, y: 4.9 + (2 - i) * 1.5, size: 1.15, posts: false });
    scene.add(s.group);
    return s;
  });

  const update = (tau) => {
    const lb = tau / BEAT;
    const pulse = Math.exp(-(lb - Math.floor(lb)) * 4);
    const cz = -V * tau;
    // the shadow light travels with the camera
    key.position.set(12, 24, cz - 6);
    key.target.position.set(0, 0, cz - 18);
    ringMat.emissiveIntensity = 1.2 + 2.2 * pulse;
    ring.material.emissiveIntensity = 1.6 + 1.4 * pulse;
    for (let i = 0; i < N; i++) {
      const side = i % 2 ? 1 : -1;
      const z = -(((i * 7.31 + tau * (10 + hash(i) * 8)) % len) + len) % len;
      dummy.position.set(side * (2.4 + hash(i * 3.3) * 3.6), 0.45 + hash(i * 5.1) * 3.2, z);
      dummy.rotation.set(tau * (0.5 + hash(i * 2.2)), tau * (0.4 + hash(i * 4.4)), 0);
      dummy.scale.setScalar(0.6 + hash(i * 6.6) * 0.9);
      dummy.updateMatrix();
      stream.setMatrixAt(i, dummy.matrix);
    }
    stream.instanceMatrix.needsUpdate = true;
    points.position.y = Math.sin(tau * 0.3) * 0.3;
    for (const l of letters) {
      const age = tau - l.at;
      l.m.visible = age >= 0;
      const k = 1 + 0.25 * (1 - clamp(age / 0.14));
      l.m.scale.setScalar(k);
      l.m.material.emissiveIntensity = 0.8 + 0.5 * pulse + 1.5 * (1 - clamp(age / 0.3));
      l.light.intensity = age >= 0 ? 12 + 8 * pulse : 0;
    }
    aus.update(tau);
    raus.forEach((s) => s.update(tau));
  };
  return { scene, portal, update, carry: rausShots(LINES.raus2.at, t0) };
}
