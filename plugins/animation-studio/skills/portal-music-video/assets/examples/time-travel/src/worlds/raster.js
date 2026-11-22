// World 4 "Rechenzentrum 1983" - the instrumental. The lines fill up: solid faces, a handful of colours,
// fat pixels, a chequered floor. Mainframes with turning tape reels, balls that bounce on the beat.
import * as THREE from 'three';
import { canvasTex, hash } from '../kit.js';
import { makePortal } from '../portal.js';
import { BEAT, STEP } from '../song.js';

export const id = 'raster';
export const beats = 36;
export const year = 1983;
export const flight = { sway: 2.2, waves: 1.5, hop: 0.35 };
export const rollIn = true; // a jump in time
export const carryColor = 0xffe14a;
export const carryStyle = 'solid';
export const res = 200; // picture height in pixels
export const look = { levels: 4, dither: 1.0, scan: 0.18 };
export const glow = 0.2;

const BG = 0x0c0c5c;
const PAL = [0x00c8ff, 0xff3df0, 0xffe14a, 0x35e06a, 0xff7a1a];

export function build({ L }) {
  const scene = new THREE.Scene();
  scene.background = new THREE.Color(BG);
  scene.fog = new THREE.Fog(BG, 40, 130);
  scene.add(new THREE.AmbientLight(0xffffff, 1.3));
  const sun = new THREE.DirectionalLight(0xffffff, 2.6);
  sun.position.set(-5, 8, 6);
  scene.add(sun);
  const flat = (color) => new THREE.MeshLambertMaterial({ color, flatShading: true });

  // chequered floor: one pair of squares per beat
  const len = L + 60;
  const check = canvasTex(2, 2, (g) => {
    g.fillStyle = '#e8e8ff', g.fillRect(0, 0, 2, 2);
    g.fillStyle = '#2233c8', g.fillRect(0, 0, 1, 1), g.fillRect(1, 1, 1, 1);
  }, { pixel: true, repeat: true });
  check.repeat.set(20, len / STEP);
  const floor = new THREE.Mesh(new THREE.PlaneGeometry(20 * STEP, len), new THREE.MeshBasicMaterial({ map: check, fog: true }));
  floor.rotation.x = -Math.PI / 2;
  floor.position.set(0, 0, -len / 2);
  scene.add(floor);

  // mainframes left and right, each with two tape reels facing the road
  const reels = [];
  const reelGeo = new THREE.CylinderGeometry(0.42, 0.42, 0.12, 8);
  reelGeo.rotateZ(Math.PI / 2);
  for (let k = 1; k < beats - 1; k++) {
    for (const side of [-1, 1]) {
      const n = k * 17 + side * 5;
      const h = 3 + Math.floor(hash(n) * 4) * 1.1;
      const z = -k * STEP;
      const cab = new THREE.Mesh(new THREE.BoxGeometry(2.4, h, 2.2), flat(PAL[Math.floor(hash(n + 1) * PAL.length)]));
      cab.position.set(side * 6.6, h / 2, z);
      scene.add(cab);
      const win = new THREE.Mesh(new THREE.BoxGeometry(0.1, 1.5, 1.9), flat(0x101030));
      win.position.set(side * 5.36, h - 1.2, z);
      scene.add(win);
      for (const dz of [-0.48, 0.48]) {
        const r = new THREE.Mesh(reelGeo, flat(0xf0f0f0));
        r.position.set(side * 5.26, h - 1.2, z + dz);
        scene.add(r);
        reels.push(r);
      }
    }
  }

  // bouncing balls (red and white, of course) with their flat shadows
  const ballTex = canvasTex(8, 4, (g) => {
    for (let y = 0; y < 4; y++) for (let x = 0; x < 8; x++) g.fillStyle = (x + y) % 2 ? '#ffffff' : '#e02020', g.fillRect(x, y, 1, 1);
  }, { pixel: true });
  const balls = [];
  for (let k = 4; k < beats - 3; k += 5) {
    const side = (k / 5) % 2 ? 1 : -1;
    const ball = new THREE.Mesh(new THREE.SphereGeometry(0.95, 10, 7), new THREE.MeshLambertMaterial({ map: ballTex, flatShading: true }));
    const shadow = new THREE.Mesh(new THREE.CircleGeometry(0.95, 10), new THREE.MeshBasicMaterial({ color: 0x080830 }));
    shadow.rotation.x = -Math.PI / 2;
    shadow.position.set(side * 3.3, 0.03, -k * STEP);
    scene.add(ball, shadow);
    balls.push({ ball, shadow, x: side * 3.3, z: -k * STEP, ph: k * 0.37 });
  }

  // a striped sun behind the head office
  const sunTex = canvasTex(4, 32, (g) => {
    for (let y = 0; y < 32; y++) g.fillStyle = y % 4 === 3 && y > 14 ? '#0c0c5c' : y < 12 ? '#ffe14a' : y < 22 ? '#ff7a1a' : '#ff3df0', g.fillRect(0, y, 4, 1);
  }, { pixel: true });
  const disc = new THREE.Mesh(new THREE.CircleGeometry(17, 40), new THREE.MeshBasicMaterial({ map: sunTex, fog: false }));
  disc.position.set(0, 11, -L - 55);
  scene.add(disc);

  // head office: a stepped block with the door
  const steps = [[18, 4.4, 5, 0xff3df0], [12, 3.4, 4, 0x00c8ff], [6.5, 2.6, 3, 0xffe14a]];
  let y0 = 0;
  for (const [w, h, d, col] of steps) {
    const b = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), flat(col));
    b.position.set(0, y0 + h / 2, -L - 0.06 - d / 2);
    scene.add(b);
    y0 += h;
  }
  const frame = new THREE.Mesh(new THREE.BoxGeometry(5.8, 3.9, 0.3), flat(0xffffff));
  frame.position.set(0, 1.95, -L - 0.2);
  scene.add(frame);
  const portal = makePortal({ shape: 'rect', w: 5, h: 3.4, flat: 0x3b2360 });
  portal.mesh.position.set(0, 1.7, -L);
  scene.add(portal.mesh);

  const update = (tau) => {
    const lb = tau / BEAT;
    const step = Math.floor(lb * 2) * (Math.PI / 8); // reels turn in steps, like the pictures of the time
    for (const r of reels) r.rotation.x = step;
    for (const b of balls) {
      const h = Math.abs(Math.sin(Math.PI * (lb / 2 + b.ph)));
      b.ball.position.set(b.x, 0.95 + 3.4 * h, b.z);
      b.ball.rotation.set(0.3, lb * 0.8 + b.ph, 0);
      b.shadow.scale.setScalar(1 - 0.45 * h);
    }
  };
  return { scene, portal, update };
}
