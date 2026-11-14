// Procedural rock singer: a jointed low-poly figure animated purely from song time.
// Base dance comes from the beat grid; actions (punch, kick, dodge, duck, block, spin)
// are blended in around the moment a word reaches her.

import * as THREE from 'three';

// ---------- pose ----------
const KEYS = [
  'rootX', 'rootZ', 'hipY', 'yaw', 'leanX', 'leanZ', 'chestYaw', 'headX', 'headZ',
  'shLx', 'shLy', 'shLz', 'elL', 'shRx', 'shRy', 'shRz', 'elR',
  'hpLx', 'hpLz', 'knL', 'hpRx', 'hpRz', 'knR',
] as const;
export type Pose = Record<(typeof KEYS)[number], number>;

const zeroPose = (): Pose => Object.fromEntries(KEYS.map((k) => [k, 0])) as Pose;

function blend(a: Pose, b: Partial<Pose>, w: number): void {
  if (w <= 0) return;
  for (const k in b) {
    const key = k as keyof Pose;
    a[key] += (b[key]! - a[key]) * w;
  }
}

export type ActionKind = 'punchL' | 'punchR' | 'kickL' | 'kickR' | 'dodgeL' | 'dodgeR' | 'duck' | 'block' | 'spin';

export interface Action {
  t: number; // moment of impact
  kind: ActionKind;
  height: number; // 0 = chest, 1 = high
  yaw: number; // direction the threat comes from (body turns toward it)
}

const smooth = (a: number, b: number, x: number) => {
  const t = Math.min(1, Math.max(0, (x - a) / (b - a)));
  return t * t * (3 - 2 * t);
};

/** 0..1: anticipation before impact, short hold, recovery after. */
export function envelope(t: number, te: number): number {
  return smooth(te - 0.34, te - 0.04, t) * (1 - smooth(te + 0.14, te + 0.6, t));
}

/** Where she stands (without action offsets) – words aim at this. */
export function wanderX(t: number) {
  return 1.9 * Math.sin(t * 0.21) + 0.8 * Math.sin(t * 0.53 + 1);
}
export function wanderZ(t: number) {
  return 0.6 + 0.5 * Math.sin(t * 0.17 + 2);
}

function actionPose(a: Action): Partial<Pose> {
  const yaw = Math.max(-1.1, Math.min(1.1, a.yaw));
  switch (a.kind) {
    case 'punchL':
    case 'punchR': {
      const L = a.kind === 'punchL';
      const s = L ? 1 : -1;
      const arm = L
        ? { shLx: -1.55 - a.height * 0.9, shLy: 0, shLz: 0.1, elL: -0.08 }
        : { shRx: -1.55 - a.height * 0.9, shRy: 0, shRz: -0.1, elR: -0.08 };
      return {
        ...arm,
        yaw: yaw * 0.8,
        chestYaw: -s * 0.45,
        leanX: 0.18,
        hipY: -0.12,
        hpLx: L ? -0.55 : 0.25, knL: L ? 0.7 : 0.3,
        hpRx: L ? 0.25 : -0.55, knR: L ? 0.3 : 0.7,
      };
    }
    case 'kickL':
    case 'kickR': {
      const L = a.kind === 'kickL';
      return {
        yaw: yaw * 0.7,
        leanX: -0.4,
        leanZ: L ? -0.15 : 0.15,
        hpLx: L ? -1.55 : 0.05, knL: L ? 0.1 : 0.2,
        hpRx: L ? 0.05 : -1.55, knR: L ? 0.2 : 0.1,
        hpLz: L ? 0.15 : 0, hpRz: L ? 0 : -0.15,
        shLx: -0.3, shLz: 1.1, elL: -0.4,
        shRx: -0.3, shRz: -1.1, elR: -0.4,
        hipY: 0.02,
      };
    }
    case 'dodgeL':
    case 'dodgeR': {
      const s = a.kind === 'dodgeL' ? 1 : -1; // her left = +x
      return {
        rootX: s * 1.0,
        leanZ: -s * 0.5,
        hipY: -0.18,
        yaw: -s * 0.3,
        hpLx: -0.4, knL: 0.8, hpRx: -0.4, knR: 0.8,
        hpLz: s > 0 ? 0.35 : 0.05, hpRz: s > 0 ? -0.05 : -0.35,
        shLx: -0.9, shLz: 0.9, elL: -1.4,
        shRx: -0.9, shRz: -0.9, elR: -1.4,
      };
    }
    case 'duck':
      return {
        hipY: -0.42, leanX: 0.55, headX: 0.35,
        hpLx: -1.3, knL: 1.6, hpRx: -1.3, knR: 1.6,
        hpLz: 0.2, hpRz: -0.2,
        shLx: -2.5, shLz: 0.3, elL: -1.9,
        shRx: -2.5, shRz: -0.3, elR: -1.9,
      };
    case 'block':
      return {
        yaw: yaw * 0.6, leanX: 0.1, hipY: -0.1,
        shLx: -1.45, shLy: 0, shLz: -0.55, elL: -1.75,
        shRx: -1.45, shRy: 0, shRz: 0.55, elR: -1.75,
        hpLx: -0.3, knL: 0.5, hpRx: 0.1, knR: 0.3,
      };
    case 'spin':
      // full Michael-Jackson-style spin, one arm up
      return { yaw: 0, shLx: -2.9, shLz: 0.2, elL: -0.2, leanX: -0.1 };
  }
}

// ---------- rig ----------
export class Singer {
  readonly root = new THREE.Group();
  private hips = new THREE.Group();
  private spine = new THREE.Group();
  private neck = new THREE.Group();
  private shL = new THREE.Group();
  private shR = new THREE.Group();
  private elL = new THREE.Group();
  private elR = new THREE.Group();
  private hpL = new THREE.Group();
  private hpR = new THREE.Group();
  private knL = new THREE.Group();
  private knR = new THREE.Group();
  private hair: THREE.Group[] = [];
  private belt!: THREE.MeshStandardMaterial;
  readonly handL = new THREE.Object3D();
  readonly handR = new THREE.Object3D();
  readonly footL = new THREE.Object3D();
  readonly footR = new THREE.Object3D();
  pose = zeroPose();

  constructor() {
    const skin = new THREE.MeshStandardMaterial({ color: '#e7b293', roughness: 0.55 });
    const leather = new THREE.MeshStandardMaterial({ color: '#121214', roughness: 0.28, metalness: 0.35 });
    const legs = new THREE.MeshStandardMaterial({ color: '#1b1b24', roughness: 0.5 });
    const skirt = new THREE.MeshStandardMaterial({ color: '#b0102a', roughness: 0.4, metalness: 0.1 });
    const boots = new THREE.MeshStandardMaterial({ color: '#0a0a0a', roughness: 0.2, metalness: 0.5 });
    const hairMat = new THREE.MeshStandardMaterial({ color: '#d0261a', roughness: 0.45, emissive: '#300000' });
    const glass = new THREE.MeshStandardMaterial({ color: '#050505', roughness: 0.05, metalness: 1 });
    const chrome = new THREE.MeshStandardMaterial({ color: '#cfd3da', roughness: 0.15, metalness: 1 });
    this.belt = new THREE.MeshStandardMaterial({ color: '#111', emissive: '#00e5ff', emissiveIntensity: 2 });

    const cap = (r: number, len: number, mat: THREE.Material, y: number) => {
      const m = new THREE.Mesh(new THREE.CapsuleGeometry(r, len, 6, 14), mat);
      m.position.y = y;
      m.castShadow = true;
      return m;
    };

    // hips / pelvis
    this.hips.position.y = 1.0;
    this.root.add(this.hips);
    const pelvis = cap(0.15, 0.08, legs, 0);
    pelvis.scale.set(1.1, 1, 0.8);
    const sk = new THREE.Mesh(new THREE.CylinderGeometry(0.16, 0.27, 0.26, 20, 1, true), skirt);
    sk.position.y = -0.06;
    sk.material.side = THREE.DoubleSide;
    sk.castShadow = true;
    const beltM = new THREE.Mesh(new THREE.TorusGeometry(0.155, 0.018, 8, 32), this.belt);
    beltM.rotation.x = Math.PI / 2;
    beltM.position.y = 0.07;
    this.hips.add(pelvis, sk, beltM);

    // spine / torso (leather jacket)
    this.spine.position.y = 0.08;
    this.hips.add(this.spine);
    const torso = cap(0.15, 0.3, leather, 0.27);
    torso.scale.set(1.15, 1, 0.75);
    const collarL = new THREE.Mesh(new THREE.BoxGeometry(0.1, 0.18, 0.03), leather);
    collarL.position.set(0.06, 0.45, 0.11);
    collarL.rotation.z = 0.4;
    const collarR = collarL.clone();
    collarR.position.x = -0.06;
    collarR.rotation.z = -0.4;
    this.spine.add(torso, collarL, collarR);
    // studs on the shoulders
    for (const sx of [-1, 1]) {
      for (let i = 0; i < 4; i++) {
        const stud = new THREE.Mesh(new THREE.ConeGeometry(0.012, 0.03, 6), chrome);
        stud.position.set(sx * (0.12 + i * 0.03), 0.5, 0.02);
        this.spine.add(stud);
      }
    }

    // neck + head
    this.neck.position.y = 0.53;
    this.spine.add(this.neck);
    this.neck.add(cap(0.045, 0.06, skin, 0.03));
    const head = new THREE.Mesh(new THREE.SphereGeometry(0.115, 24, 18), skin);
    head.scale.set(0.92, 1.08, 1);
    head.position.y = 0.17;
    head.castShadow = true;
    const shades = new THREE.Mesh(new THREE.BoxGeometry(0.2, 0.045, 0.04), glass);
    shades.position.set(0, 0.19, 0.1);
    const lips = new THREE.Mesh(new THREE.SphereGeometry(0.022, 10, 8), new THREE.MeshStandardMaterial({ color: '#9c0f1f', roughness: 0.3 }));
    lips.scale.set(1.4, 0.6, 0.6);
    lips.position.set(0, 0.1, 0.105);
    const hairCap = new THREE.Mesh(new THREE.SphereGeometry(0.128, 20, 14, 0, Math.PI * 2, 0, Math.PI * 0.6), hairMat);
    hairCap.position.y = 0.19;
    hairCap.rotation.x = -0.35;
    hairCap.castShadow = true;
    this.neck.add(head, shades, lips, hairCap);
    // long hair strands hanging from the back of the head
    for (let i = 0; i < 9; i++) {
      const g = new THREE.Group();
      const a = ((i - 4) / 4) * 1.3;
      g.position.set(Math.sin(a) * 0.1, 0.22, -Math.cos(a) * 0.07);
      g.rotation.y = a * 0.3;
      const strand = cap(0.042, 0.34, hairMat, -0.2);
      strand.scale.set(1, 1, 0.6);
      g.add(strand);
      this.neck.add(g);
      this.hair.push(g);
    }

    // arms
    const buildArm = (side: 1 | -1, sh: THREE.Group, el: THREE.Group, hand: THREE.Object3D) => {
      sh.position.set(side * 0.21, 0.45, 0);
      this.spine.add(sh);
      const shoulderPad = new THREE.Mesh(new THREE.SphereGeometry(0.075, 14, 10), leather);
      shoulderPad.castShadow = true;
      sh.add(shoulderPad, cap(0.055, 0.2, leather, -0.15));
      el.position.y = -0.3;
      sh.add(el);
      el.add(cap(0.044, 0.18, skin, -0.13));
      const fist = new THREE.Mesh(new THREE.SphereGeometry(0.052, 12, 10), skin);
      fist.position.y = -0.29;
      fist.castShadow = true;
      el.add(fist);
      hand.position.y = -0.3;
      el.add(hand);
      // fingerless glove band
      const band = new THREE.Mesh(new THREE.CylinderGeometry(0.05, 0.05, 0.04, 12), leather);
      band.position.y = -0.24;
      el.add(band);
    };
    buildArm(1, this.shL, this.elL, this.handL);
    buildArm(-1, this.shR, this.elR, this.handR);

    // microphone in the right hand
    const mic = new THREE.Group();
    const body = new THREE.Mesh(new THREE.CylinderGeometry(0.018, 0.012, 0.17, 12), new THREE.MeshStandardMaterial({ color: '#111', metalness: 0.6, roughness: 0.3 }));
    const grille = new THREE.Mesh(new THREE.SphereGeometry(0.032, 14, 10), chrome);
    grille.position.y = 0.1;
    mic.add(body, grille);
    mic.position.set(0, -0.3, 0.03);
    mic.rotation.x = -0.25;
    this.elR.add(mic);

    // legs
    const buildLeg = (side: 1 | -1, hp: THREE.Group, kn: THREE.Group, foot: THREE.Object3D) => {
      hp.position.set(side * 0.09, -0.04, 0);
      this.hips.add(hp);
      hp.add(cap(0.072, 0.32, legs, -0.23));
      kn.position.y = -0.47;
      hp.add(kn);
      kn.add(cap(0.066, 0.3, boots, -0.22));
      const f = new THREE.Mesh(new THREE.BoxGeometry(0.1, 0.07, 0.22), boots);
      f.position.set(0, -0.47, 0.05);
      f.castShadow = true;
      const heel = new THREE.Mesh(new THREE.BoxGeometry(0.04, 0.06, 0.04), boots);
      heel.position.set(0, -0.52, -0.04);
      kn.add(f, heel);
      foot.position.y = -0.5;
      kn.add(foot);
    };
    buildLeg(1, this.hpL, this.knL, this.footL);
    buildLeg(-1, this.hpR, this.knR, this.footR);

    this.root.scale.setScalar(1.15);
  }

  /**
   * t: song time, beat: beat position (e.g. 12.25 = quarter past beat 12),
   * energy: 0..1 dance intensity, singing: mic at mouth, actions: nearby actions.
   */
  update(t: number, beat: number, energy: number, singing: number, headbang: number, actions: Action[], accent: THREE.Color) {
    const p = zeroPose();
    const ph = beat - Math.floor(beat);
    const bounce = 0.5 - 0.5 * Math.cos(ph * Math.PI * 2); // 0 on the beat, 1 between
    const sway = Math.sin(beat * Math.PI); // left/right every 2 beats
    const e = 0.5 + energy * 0.8;

    // base groove: bounce on the beat, hip sway, head nod
    p.rootX = wanderX(t);
    p.rootZ = wanderZ(t);
    p.hipY = -0.05 - 0.07 * e * (1 - bounce);
    p.knL = 0.25 + 0.25 * e * (1 - bounce) + Math.max(0, sway) * 0.2;
    p.knR = 0.25 + 0.25 * e * (1 - bounce) + Math.max(0, -sway) * 0.2;
    p.hpLx = -p.knL * 0.5;
    p.hpRx = -p.knR * 0.5;
    p.hpLz = 0.08;
    p.hpRz = -0.08;
    p.leanZ = sway * 0.08 * e;
    p.leanX = 0.06;
    p.yaw = Math.sin(t * 0.4) * 0.35;
    p.headX = 0.12 * (1 - bounce) * e + headbang * 0.55 * (1 - bounce) - headbang * 0.1;
    p.headZ = -sway * 0.08;

    // right arm: mic to the mouth while singing, otherwise lowered
    const micUp = { shRx: -0.75, shRy: 0.15, shRz: 0.15, elR: -2.15 };
    const micDown = { shRx: -0.3, shRy: 0, shRz: -0.2, elR: -0.9 };
    p.shRx = micDown.shRx + (micUp.shRx - micDown.shRx) * singing;
    p.shRy = micDown.shRy + (micUp.shRy - micDown.shRy) * singing;
    p.shRz = micDown.shRz + (micUp.shRz - micDown.shRz) * singing;
    p.elR = micDown.elR + (micUp.elR - micDown.elR) * singing;

    // left arm: fist pump on every other beat, higher when energy is high
    const pump = Math.pow(Math.max(0, Math.cos(beat * Math.PI)), 3);
    p.shLx = -0.35 - (0.6 + energy * 1.6) * pump;
    p.shLz = 0.35 + energy * 0.2;
    p.elL = -1.0 + pump * 0.6;

    for (const a of actions) {
      const w = envelope(t, a.t);
      if (w <= 0) continue;
      const target = actionPose(a);
      // dodges move away from the wander position
      if (target.rootX !== undefined) target.rootX = p.rootX + target.rootX;
      if (a.kind === 'spin') {
        // one full turn, always forward (ends where it started)
        p.yaw += Math.PI * 2 * smooth(a.t - 0.34, a.t + 0.45, t);
        delete target.yaw;
      }
      blend(p, target, w);
    }
    this.pose = p;
    this.apply(p, t, beat, headbang);
    this.belt.emissive.copy(accent);
  }

  private apply(p: Pose, t: number, beat: number, headbang: number) {
    this.root.position.set(p.rootX, 0, p.rootZ);
    this.root.rotation.y = p.yaw;
    this.hips.position.y = 1.0 + p.hipY;
    this.spine.rotation.set(p.leanX, p.chestYaw, p.leanZ);
    this.neck.rotation.set(p.headX, 0, p.headZ);
    this.shL.rotation.set(p.shLx, p.shLy, p.shLz);
    this.shR.rotation.set(p.shRx, p.shRy, p.shRz);
    this.elL.rotation.x = p.elL;
    this.elR.rotation.x = p.elR;
    this.hpL.rotation.set(p.hpLx, 0, p.hpLz);
    this.hpR.rotation.set(p.hpRx, 0, p.hpRz);
    this.knL.rotation.x = p.knL;
    this.knR.rotation.x = p.knR;
    // hair hangs down (counter the head/torso tilt) and swings with the groove
    this.hair.forEach((g, i) => {
      const swing = Math.sin(beat * Math.PI * 2 + i * 0.6) * (0.12 + headbang * 0.35);
      g.rotation.x = 0.35 - (p.headX + p.leanX) * 0.85 + swing;
      g.rotation.z = -(p.headZ + p.leanZ) * 0.8 + Math.sin(t * 1.3 + i) * 0.06;
    });
  }
}
