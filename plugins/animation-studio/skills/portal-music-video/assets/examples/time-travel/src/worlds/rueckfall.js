// World 14 "Rückfall" - the instrumental outro: in the song the layers drop out one by one, and so do the years.
// The same city of gates, but every two bars it loses an era: first the light, then the textures, then the
// colours and the sharpness, and at last the faces - until only the wire frame of 1974 is left.
// The year in the corner runs backwards, and the change ages back with it.
import * as THREE from 'three';
import { lines, rectXY } from '../kit.js';
import { makePortal } from '../portal.js';
import { BEAT } from '../song.js';
import { levelsAt } from '../spectrum.js';
import { buildCity, CITY_LOOK, exitGate } from '../stadt.js';

export const id = 'rueckfall';
export const beats = 32;
export const year = 2040;
export const carryColor = 0x2bff88;
export const flight = { sway: 1.8, waves: 1, rise: 0.5 };

// from which beat on the city is drawn in which manner
const STEPS = [
  [0, 'pbr', { res: 0, look: CITY_LOOK, glow: 0, carryStyle: 'orb', carryColor: 0x2bff88 }],
  [8, 'tex', { res: 540, look: {}, glow: 0.5, carryStyle: 'crate' }],
  [16, 'flat', { res: 360, look: { levels: 24, dither: 1 }, glow: 0.3, carryStyle: 'gem', carryColor: 0x40e0ff }],
  [22, 'pix', { res: 200, look: { levels: 4, dither: 1, scan: 0.18 }, glow: 0.2, carryStyle: 'solid', carryColor: 0xffe14a }],
  [28, 'wire', { res: 0, look: {}, glow: 0.85, carryStyle: 'wire', carryColor: 0xff5a4d }],
];
const stepAt = (tau) => {
  const lb = tau / BEAT;
  let s = STEPS[0];
  for (const st of STEPS) if (lb >= st[0]) s = st;
  return s;
};
export const dyn = (tau) => stepAt(tau)[2];

export function build({ t0, L }) {
  const scene = new THREE.Scene();
  const city = buildCity(scene, { L, beats, seed: 400, levels: (tau, out) => levelsAt(t0 + tau, out) });
  const gate = exitGate(scene, L);
  const fa = [];
  rectXY(fa, 0, 1.7, -L, 5, 3.4);
  rectXY(fa, 0, 1.95, -L, 5.9, 3.9);
  const frame = lines(fa, { color: 0xff3b30, width: 0.07 });
  scene.add(frame);
  const portal = makePortal({ shape: 'rect', w: 5, h: 3.4, flat: 0x000000 });
  portal.mesh.position.set(0, 1.7, -L);
  scene.add(portal.mesh);

  const update = (tau) => {
    const style = stepAt(tau)[1];
    city.setStyle(style);
    gate.visible = style !== 'wire';
    frame.visible = style === 'wire';
    city.update(tau);
  };
  return { scene, portal, update };
}
