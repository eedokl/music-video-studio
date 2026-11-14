// Camera director: rock-video style hard cuts on the beat grid, smooth moves inside a shot.

import * as THREE from 'three';
import type { SectionId } from './lyrics';

type Shot = (u: number, s: THREE.Vector3, t: number, pos: THREE.Vector3, look: THREE.Vector3) => number; // returns fov

const SHOTS: Record<string, Shot> = {
  wide: (u, s, t, p, l) => (p.set(Math.sin(t * 0.1) * 2, 3.4 - u * 0.4, 14.5 - u * 2.5), l.set(s.x * 0.4, 2.3, 0), 50),
  medium: (u, s, _t, p, l) => (p.set(s.x + 1.4 - u * 1.0, 2.1, s.z + 5.6), l.set(s.x, 1.75, s.z), 50),
  close: (u, s, _t, p, l) => (p.set(s.x + 0.6 - u * 0.4, 2.15, s.z + 3.4 - u * 0.4), l.set(s.x, 1.9, s.z), 48),
  low: (u, s, _t, p, l) => (p.set(s.x - 2.4 + u * 1.2, 0.45, s.z + 4.2), l.set(s.x, 2.2, s.z), 55),
  orbit: (u, s, _t, p, l) => {
    const a = -1.0 + u * 1.7;
    p.set(s.x + Math.sin(a) * 6.2, 2.5, s.z + Math.cos(a) * 6.2);
    l.set(s.x, 1.7, s.z);
    return 52;
  },
  crane: (u, s, _t, p, l) => (p.set(-7 + u * 14, 8.5 - u * 2.5, 9.5), l.set(s.x, 1.3, s.z), 50),
  crowd: (u, s, _t, p, l) => (p.set(-2.6 + u * 1.2, 1.15, 11.8), l.set(s.x, 2.4, 0), 42),
  reverse: (u, s, _t, p, l) => (p.set(s.x + 1.6 - u * 0.6, 3.2, -3.2), l.set(s.x * 0.3, 1.2, 9), 58),
};

const PLAN: Record<SectionId, { shots: string[]; beats: number }> = {
  intro: { shots: ['crane', 'wide', 'crowd', 'reverse'], beats: 8 },
  verse1: { shots: ['wide', 'medium', 'orbit', 'low', 'crowd', 'close', 'reverse'], beats: 8 },
  chorus: { shots: ['medium', 'low', 'orbit', 'crane', 'reverse', 'close', 'wide'], beats: 4 },
  verse2: { shots: ['medium', 'orbit', 'wide', 'close', 'low', 'crowd', 'reverse'], beats: 8 },
  bridge: { shots: ['close', 'low', 'orbit', 'medium'], beats: 4 },
  final: { shots: ['low', 'medium', 'crane', 'orbit', 'reverse', 'close', 'wide'], beats: 4 },
  outro: { shots: ['crane'], beats: 64 },
};

const hash = (n: number) => {
  const x = Math.sin(n * 77.7 + 3.1) * 43758.5453;
  return x - Math.floor(x);
};

export class Director {
  private pos = new THREE.Vector3();
  private look = new THREE.Vector3();

  /** forced: name of a shot to always use (debug: ?shot=medium) */
  constructor(private camera: THREE.PerspectiveCamera, private forced: string | null = null) {}

  update(t: number, beat: number, section: SectionId, singer: THREE.Vector3, shake: number, pulse: number) {
    const plan = PLAN[section];
    const n = Math.floor(Math.max(0, beat) / plan.beats);
    // pick a shot, never the same twice in a row
    let idx = Math.floor(hash(n) * plan.shots.length);
    const prev = Math.floor(hash(n - 1) * plan.shots.length);
    if (idx === prev) idx = (idx + 1) % plan.shots.length;
    const name = this.forced && SHOTS[this.forced] ? this.forced : section === 'intro' && n === 0 ? 'crane' : plan.shots[idx];
    const u = (Math.max(0, beat) / plan.beats) % 1;
    const fov = SHOTS[name](u, singer, t, this.pos, this.look);
    // hit shake (deterministic jitter)
    this.pos.x += Math.sin(t * 91) * shake * 0.08;
    this.pos.y += Math.cos(t * 77) * shake * 0.08;
    this.camera.position.copy(this.pos);
    this.camera.lookAt(this.look);
    this.camera.fov = fov - pulse * 1.5;
    this.camera.updateProjectionMatrix();
  }
}
