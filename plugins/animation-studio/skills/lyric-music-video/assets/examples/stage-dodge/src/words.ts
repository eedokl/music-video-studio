// Lyric words flying at the singer. Each word arrives exactly when it is sung.
// Hazard words get punched / kicked / blocked away; other words are dodged or whiz past.
// Everything is a pure function of song time, so seeking and frame-by-frame export work.

import * as THREE from 'three';
import { LINES, SECTION_COLORS, isFightWord, isSmallWord } from './lyrics';
import type { SectionId } from './lyrics';
import { type Action, type ActionKind, wanderX, wanderZ } from './singer';

const TRAVEL = 1.5; // seconds from spawn to impact
const DIST = 13; // spawn distance
const SCALE = 1.15; // singer scale

interface WordEvent {
  id: number;
  text: string;
  t: number;
  section: SectionId;
  fight: boolean;
  action?: Action;
  dirOut: THREE.Vector3; // unit vector from singer towards where the word comes from
  target: THREE.Vector3;
  seed: number;
}

function hash(n: number) {
  const x = Math.sin(n * 127.1 + 311.7) * 43758.5453;
  return x - Math.floor(x);
}

const AZ = [-105, -70, -42, 42, 70, 105, 155, -155, -25, 25];

function buildEvents(): { events: WordEvent[]; actions: Action[] } {
  const events: WordEvent[] = [];
  const actions: Action[] = [];
  let lastAction = -10;
  let id = 0;
  let lineInChorus = 0;
  LINES.forEach((line, li) => {
    const words = line.text.split(' ');
    let lineHasAction = false;
    const chorusy = line.section === 'chorus' || line.section === 'final';
    if (chorusy) lineInChorus++;
    words.forEach((w, wi) => {
      const t = line.words?.[wi] ?? line.t;
      const seed = hash(id + 1);
      const az = (AZ[Math.floor(hash(id * 3.1) * AZ.length)] * Math.PI) / 180;
      let el = 0.05 + hash(id * 7.7) * 0.5;
      const fight = isFightWord(w);
      let kind: ActionKind | undefined;
      let height = 0;
      const free = t - lastAction > 0.62;

      if (fight && free) {
        const r = hash(id * 5.3);
        if (el > 0.42) kind = az > 0 ? 'punchL' : 'punchR';
        else if (r < 0.25) {
          kind = az > 0 ? 'kickL' : 'kickR';
          el = 0.04;
        } else if (r < 0.33) kind = 'block';
        else kind = az > 0 ? 'punchL' : 'punchR';
        height = el > 0.42 ? 1 : 0.2;
      } else if (!fight && free && !isSmallWord(w) && ((!lineHasAction && wi === words.length - 1) || hash(id * 8.8) < 0.3)) {
        // other words: dodge or duck (always the last word of a line without a fight); spin in choruses
        const r = hash(id * 9.1);
        if (chorusy && lineInChorus % 4 === 0 && wi === words.length - 1) kind = 'spin';
        else if (r < 0.33) kind = 'duck';
        else kind = az > 0 ? 'dodgeR' : 'dodgeL'; // step away from the side it comes from
        if (kind === 'duck') el = 0.15;
      }

      const dirOut = new THREE.Vector3(Math.sin(az) * Math.cos(el), Math.sin(el), Math.cos(az) * Math.cos(el)).normalize();
      const root = new THREE.Vector3(wanderX(t), 0, wanderZ(t));
      const target = root.clone();
      if (kind?.startsWith('punch')) {
        target.y = (1.5 + height * 0.45) * SCALE;
        target.addScaledVector(new THREE.Vector3(dirOut.x, 0, dirOut.z).normalize(), 0.62 * SCALE);
      } else if (kind?.startsWith('kick')) {
        target.y = 0.95 * SCALE;
        target.addScaledVector(new THREE.Vector3(dirOut.x, 0, dirOut.z).normalize(), 0.85 * SCALE);
      } else if (kind === 'block') {
        target.y = 1.45 * SCALE;
        target.addScaledVector(new THREE.Vector3(dirOut.x, 0, dirOut.z).normalize(), 0.45 * SCALE);
      } else if (kind === 'duck') {
        target.y = 1.95 * SCALE;
      } else if (kind?.startsWith('dodge')) {
        target.y = 1.5 * SCALE;
      } else {
        // fly past: miss to the side
        const side = new THREE.Vector3(-dirOut.z, 0, dirOut.x).normalize();
        target.addScaledVector(side, (hash(id * 2.3) < 0.5 ? -1 : 1) * (1.3 + hash(id * 4.4) * 0.8));
        target.y = (1.0 + hash(id * 6.1) * 1.2) * SCALE;
      }

      let action: Action | undefined;
      if (kind) {
        action = { t, kind, height, yaw: Math.atan2(dirOut.x, dirOut.z) };
        actions.push(action);
        lastAction = t;
        lineHasAction = true;
      }
      events.push({ id, text: w.replace(/[,.?]$/, ''), t, section: line.section, fight, action, dirOut, target, seed });
      id++;
    });
    void li;
  });
  return { events, actions };
}

export const { events: WORD_EVENTS, actions: ACTIONS } = buildEvents();

// ---------- textures ----------
function makeTexture(text: string, fight: boolean, color: string): { tex: THREE.CanvasTexture; aspect: number } {
  const c = document.createElement('canvas');
  const ctx = c.getContext('2d')!;
  const font = `130px "Black Ops One", Impact, sans-serif`;
  ctx.font = font;
  const tw = Math.ceil(ctx.measureText(text).width);
  const pad = 50;
  c.width = tw + pad * 2;
  c.height = 210;
  ctx.font = font;
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  const cx = c.width / 2;
  const cy = c.height / 2 + 6;
  if (fight) {
    // red "warning stamp" plate
    ctx.fillStyle = '#d0101e';
    ctx.strokeStyle = '#ffffff';
    ctx.lineWidth = 10;
    const r = 26;
    const x = 12, y = 22, w = c.width - 24, h = c.height - 44;
    ctx.beginPath();
    ctx.roundRect(x, y, w, h, r);
    ctx.fill();
    ctx.stroke();
    ctx.fillStyle = '#ffffff';
    ctx.fillText(text, cx, cy);
  } else {
    ctx.shadowColor = color;
    ctx.shadowBlur = 28;
    ctx.lineWidth = 14;
    ctx.strokeStyle = '#000000';
    ctx.strokeText(text, cx, cy);
    ctx.fillStyle = '#ffffff';
    ctx.fillText(text, cx, cy);
    ctx.shadowBlur = 0;
    ctx.fillText(text, cx, cy);
  }
  const tex = new THREE.CanvasTexture(c);
  tex.colorSpace = THREE.SRGBColorSpace;
  tex.anisotropy = 4;
  return { tex, aspect: c.width / c.height };
}

function ringTexture(): THREE.CanvasTexture {
  const c = document.createElement('canvas');
  c.width = c.height = 256;
  const ctx = c.getContext('2d')!;
  const g = ctx.createRadialGradient(128, 128, 60, 128, 128, 126);
  g.addColorStop(0, 'rgba(255,255,255,0)');
  g.addColorStop(0.75, 'rgba(255,240,200,1)');
  g.addColorStop(1, 'rgba(255,255,255,0)');
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, 256, 256);
  return new THREE.CanvasTexture(c);
}

// ---------- live field ----------
interface Live {
  mesh: THREE.Mesh;
  aspect: number;
}

const MAX_SPARKS = 900;

export class WordField {
  readonly group = new THREE.Group();
  private live = new Map<number, Live>();
  private sparks: THREE.Points;
  private rings: THREE.Sprite[] = [];
  private q = new THREE.Quaternion();
  private v = new THREE.Vector3();

  constructor() {
    const g = new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.BufferAttribute(new Float32Array(MAX_SPARKS * 3), 3));
    g.setAttribute('color', new THREE.BufferAttribute(new Float32Array(MAX_SPARKS * 3), 3));
    this.sparks = new THREE.Points(
      g,
      new THREE.PointsMaterial({ size: 0.09, vertexColors: true, transparent: true, blending: THREE.AdditiveBlending, depthWrite: false, toneMapped: false }),
    );
    this.sparks.frustumCulled = false;
    this.group.add(this.sparks);
    const rt = ringTexture();
    for (let i = 0; i < 8; i++) {
      const s = new THREE.Sprite(new THREE.SpriteMaterial({ map: rt, transparent: true, blending: THREE.AdditiveBlending, depthWrite: false, toneMapped: false }));
      s.visible = false;
      this.rings.push(s);
      this.group.add(s);
    }
  }

  /** Returns hit flash 0..1 (for lights / camera shake). */
  update(t: number, beat: number, camera: THREE.Camera): number {
    const ph = beat - Math.floor(beat);
    const bump = 1 + 0.24 * Math.exp(-ph * 8); // words pulse on every beat
    const wanted = new Set<number>();
    let flash = 0;
    let spark = 0;
    let ring = 0;
    const pos = this.sparks.geometry.attributes.position as THREE.BufferAttribute;
    const col = this.sparks.geometry.attributes.color as THREE.BufferAttribute;
    camera.getWorldQuaternion(this.q);

    for (const ev of WORD_EVENTS) {
      const s = t - ev.t;
      if (s < -TRAVEL || s > 1.0) continue;
      const hit = !!ev.action && !ev.action.kind.startsWith('dodge') && ev.action.kind !== 'duck' && ev.action.kind !== 'spin';
      const life = hit ? 0.75 : 0.6;
      if (s > life) continue;
      wanted.add(ev.id);
      let item = this.live.get(ev.id);
      if (!item) {
        const color = SECTION_COLORS[ev.section];
        const { tex, aspect } = makeTexture(ev.text.toUpperCase(), ev.fight, color);
        const mat = new THREE.MeshBasicMaterial({ map: tex, transparent: true, depthWrite: false, side: THREE.DoubleSide, toneMapped: false });
        const mesh = new THREE.Mesh(new THREE.PlaneGeometry(1, 1), mat);
        mesh.renderOrder = 2;
        this.group.add(mesh);
        item = { mesh, aspect };
        this.live.set(ev.id, item);
      }
      const m = item.mesh;
      const mat = m.material as THREE.MeshBasicMaterial;
      let opacity = 1;
      let size = ev.fight ? 0.78 : 0.6;
      let roll = Math.sin(t * 3 + ev.seed * 10) * 0.12;

      if (s < 0) {
        // incoming: straight line with a little arc, wobbling
        const u = 1 + s / TRAVEL; // 0..1
        this.v.copy(ev.target).addScaledVector(ev.dirOut, DIST * (1 - u));
        this.v.y += Math.sin(u * Math.PI) * 1.2 * (ev.seed - 0.3);
        opacity = Math.min(1, u * 4);
        size *= 0.8 + 0.35 * u;
      } else if (hit) {
        // knocked away: fly back out, spin, fade
        const k = new THREE.Vector3(ev.dirOut.x + (ev.seed - 0.5), 0.6 + ev.seed * 0.5, ev.dirOut.z).normalize();
        this.v.copy(ev.target).addScaledVector(k, s * 11);
        this.v.y -= 4 * s * s;
        roll += s * (ev.seed > 0.5 ? 14 : -14);
        opacity = 1 - s / life;
        size *= 1 + s * 1.6;
        flash = Math.max(flash, Math.exp(-s * 9));
        // sparks (analytic, deterministic)
        if (s < 0.9 && spark + 60 <= MAX_SPARKS) {
          for (let i = 0; i < 60; i++) {
            const a = hash(ev.id * 31 + i) * Math.PI * 2;
            const b = hash(ev.id * 17 + i * 3) * 2 - 1;
            const sp = 3 + hash(ev.id * 13 + i * 7) * 5;
            const r = Math.sqrt(1 - b * b);
            const x = ev.target.x + Math.cos(a) * r * sp * s;
            const y = ev.target.y + b * sp * s - 5 * s * s;
            const z = ev.target.z + Math.sin(a) * r * sp * s;
            pos.setXYZ(spark, x, y, z);
            const f = Math.max(0, 1 - s / 0.9) * 2;
            col.setXYZ(spark, f, f * (0.5 + hash(i) * 0.4), f * 0.15);
            spark++;
          }
        }
        if (s < 0.35 && ring < this.rings.length) {
          const rs = this.rings[ring++];
          rs.visible = true;
          rs.position.copy(ev.target);
          rs.scale.setScalar(0.3 + s * 7);
          (rs.material as THREE.SpriteMaterial).opacity = 1 - s / 0.35;
        }
      } else {
        // missed / dodged: keep flying through
        this.v.copy(ev.target).addScaledVector(ev.dirOut, (-DIST / TRAVEL) * s);
        opacity = 1 - s / life;
      }

      m.position.copy(this.v);
      m.quaternion.copy(this.q);
      m.rotateZ(roll);
      const sc = size * bump;
      m.scale.set(sc * item.aspect, sc, 1);
      mat.opacity = Math.max(0, opacity);
    }

    for (let i = spark; i < MAX_SPARKS; i++) pos.setXYZ(i, 0, -999, 0);
    pos.needsUpdate = true;
    col.needsUpdate = true;
    for (let i = ring; i < this.rings.length; i++) this.rings[i].visible = false;

    for (const [id, item] of this.live) {
      if (!wanted.has(id)) {
        const mat = item.mesh.material as THREE.MeshBasicMaterial;
        mat.map?.dispose();
        mat.dispose();
        item.mesh.geometry.dispose();
        this.group.remove(item.mesh);
        this.live.delete(id);
      }
    }
    return flash;
  }
}

/** Actions near time t (for the singer). */
export function actionsNear(t: number): Action[] {
  return ACTIONS.filter((a) => Math.abs(a.t - t) < 0.8);
}
