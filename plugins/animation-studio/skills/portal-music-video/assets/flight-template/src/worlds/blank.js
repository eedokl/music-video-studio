// The smallest world: a floor of lines, the song's lines as signs, a portal at the end. Copy it to start a new one.
// (The contract in full: references/world-contract.md of the skill; the header of ../engine.js is the short form.)
import * as THREE from 'three';
import { lines, rectXY, roadSign, seg } from '../kit.js';
import { makePortal } from '../portal.js';
import { BEAT, STEP } from '../song.js';

export const id = 'blank';
export const beats = 16; // the plan may override it
export const carryColor = 0xffffff; // colour of what flies along
export const flight = { sway: 0.8, waves: 1 }; // the camera's path: sideways swing, number of waves

export function build({ t0, L, beats, lines: sung }) {
  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0x000000);
  scene.fog = new THREE.Fog(0x000000, 16, 92);

  // The camera enters at z = 0 and flies towards -z; the portal stands at z = -L. One beat = STEP units, so
  // whatever is spaced in STEPs passes on the beat. Nothing may stand at z > 0.
  const floor = [];
  for (let x = -9; x <= 9; x += 3) seg(floor, x, 0, 0, x, 0, -L - 30);
  for (let k = 0; k <= beats + 10; k++) seg(floor, -9, 0, -k * STEP, 9, 0, -k * STEP);
  scene.add(lines(floor, { color: 0x8c8c8c, width: 0.03, opacity: 0.55 }));

  // every sung line as a sign bridge 24 units ahead of where the camera is when its first word starts
  const signs = sung.map((line) => roadSign(line, t0, L, 24));
  signs.forEach((s) => scene.add(s.group));

  // the way out: a frame and the opening that shows the next world
  const frame = [];
  rectXY(frame, 0, 1.7, -L, 5, 3.4);
  scene.add(lines(frame, { color: 0xffffff, width: 0.07 }));
  const portal = makePortal({ shape: 'rect', w: 5, h: 3.4 });
  portal.mesh.position.set(0, 1.7, -L);
  scene.add(portal.mesh);

  // tau = this world's clock in seconds (negative while it is only seen through the portal before it).
  // Everything is a pure function of tau: no timers, no random numbers, no state from the frame before.
  const update = (tau) => {
    signs.forEach((s) => s.update(tau));
    void BEAT; // tau / BEAT = beats since we entered
  };
  return { scene, portal, update };
}
