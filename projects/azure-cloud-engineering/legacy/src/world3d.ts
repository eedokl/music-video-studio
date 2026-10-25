// Line-art 3D scenes used by some of the 2D scenes: keynote stage, exploded-view
// Key Vault, connectivity tunnel, network topology, globe. All driven by time.

import * as THREE from 'three';
import { clamp, easeInOut, easeOut, hash, prog } from './util';

export type Mode3D = 'none' | 'city' | 'vault' | 'tunnel' | 'network' | 'globe';

const LINE = '#7fa6dd';
const GREEN = '#4fd1ff'; // accent 1 (cyan)
const BLUE = '#ff7a59'; // accent 2 (coral)
const RED = '#ff4d6d';

function edges(geo: THREE.BufferGeometry, color = LINE, opacity = 0.9) {
  return new THREE.LineSegments(new THREE.EdgesGeometry(geo), new THREE.LineBasicMaterial({ color, transparent: true, opacity }));
}
function solid(geo: THREE.BufferGeometry, color: string, edge = '#0b0e14') {
  const g = new THREE.Group();
  g.add(new THREE.Mesh(geo, new THREE.MeshStandardMaterial({ color, roughness: 0.6, metalness: 0.1, flatShading: true })));
  g.add(edges(geo, edge, 0.8));
  return g;
}
function gridFloor(size = 60, div = 60, y = 0) {
  const g = new THREE.GridHelper(size, div, '#24457f', '#16305f');
  g.position.y = y;
  return g;
}

export interface Ctx3D {
  t: number;
  u: number; // 0..1 progress in the scene
  beat: number;
  pulse: number;
  opts: Record<string, number | string | boolean>;
}

export class World3D {
  readonly renderer: THREE.WebGLRenderer;
  readonly scene = new THREE.Scene();
  readonly camera = new THREE.PerspectiveCamera(40, 16 / 9, 0.1, 500);
  private groups: Record<Exclude<Mode3D, 'none'>, THREE.Group>;
  private mode: Mode3D = 'none';
  private labels = new Map<string, HTMLElement>();
  private v = new THREE.Vector3();
  // vault
  private parts: { obj: THREE.Object3D; home: THREE.Vector3; dir: THREE.Vector3; label: string; anchor: THREE.Vector3 }[] = [];
  private cage!: THREE.Group;
  // tunnel
  private tNodes: { g: THREE.Group; mat: THREE.LineBasicMaterial; x: number; name: string }[] = [];
  private packet!: THREE.Mesh;
  private tLinks: THREE.Line[] = [];
  // network
  private nNodes: { m: THREE.Mesh; p: THREE.Vector3; order: number }[] = [];
  private nEdges!: THREE.LineSegments;
  private nEdgeOrder: number[] = [];
  // globe
  private globe = new THREE.Group();
  private arcs: { line: THREE.Line; n: number; a: number }[] = [];

  constructor(canvasParent: HTMLElement, private labelLayer: HTMLElement, preserve: boolean) {
    this.renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false, preserveDrawingBuffer: preserve });
    this.renderer.setPixelRatio(preserve ? 1 : Math.min(window.devicePixelRatio, 1.75));
    this.renderer.setSize(window.innerWidth, window.innerHeight);
    this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
    canvasParent.appendChild(this.renderer.domElement);
    this.scene.background = new THREE.Color('#0a1a3f');
    this.scene.fog = new THREE.Fog('#0a1a3f', 30, 90);
    this.scene.add(new THREE.HemisphereLight('#cfd8ff', '#101018', 1.2));
    const key = new THREE.DirectionalLight('#ffffff', 1.6);
    key.position.set(6, 10, 8);
    this.scene.add(key);
    this.groups = { city: this.buildCity(), vault: this.buildVault(), tunnel: this.buildTunnel(), network: this.buildNetwork(), globe: this.buildGlobe() };
    Object.values(this.groups).forEach((g) => {
      g.visible = false;
      this.scene.add(g);
    });
    this.resize();
  }

  resize() {
    this.renderer.setSize(window.innerWidth, window.innerHeight);
    this.camera.aspect = window.innerWidth / window.innerHeight;
    this.camera.updateProjectionMatrix();
  }

  setMode(m: Mode3D) {
    if (m === this.mode) return;
    this.mode = m;
    Object.entries(this.groups).forEach(([k, g]) => (g.visible = k === m));
    this.renderer.domElement.style.visibility = m === 'none' ? 'hidden' : 'visible';
    this.labels.forEach((l) => l.remove());
    this.labels.clear();
  }

  /** Screen-space position of a world point (px). */
  project(p: THREE.Vector3) {
    this.v.copy(p).project(this.camera);
    return { x: (this.v.x * 0.5 + 0.5) * window.innerWidth, y: (-this.v.y * 0.5 + 0.5) * window.innerHeight, behind: this.v.z > 1 };
  }

  private label(id: string, text: string, p: THREE.Vector3, opacity: number, cls = '') {
    let el = this.labels.get(id);
    if (!el) {
      el = document.createElement('div');
      el.className = `l3 ${cls}`;
      el.textContent = text;
      this.labelLayer.appendChild(el);
      this.labels.set(id, el);
    }
    const s = this.project(p);
    el.style.left = `${s.x.toFixed(1)}px`;
    el.style.top = `${s.y.toFixed(1)}px`;
    el.style.opacity = (s.behind ? 0 : opacity).toFixed(3);
  }

  // ---------- builders ----------
  private cityTowers!: THREE.InstancedMesh;
  private cityTops!: THREE.InstancedMesh;
  private towers: { x: number; z: number; h: number; ph: number }[] = [];
  private cloud = new THREE.Group();

  private buildCity() {
    const g = new THREE.Group();
    g.add(gridFloor(120, 60, 0));
    const N = 16 * 12;
    this.cityTowers = new THREE.InstancedMesh(new THREE.BoxGeometry(1, 1, 1), new THREE.MeshStandardMaterial({ color: '#1b4fa8', roughness: 0.45, metalness: 0.2 }), N);
    this.cityTops = new THREE.InstancedMesh(new THREE.BoxGeometry(1, 0.08, 1), new THREE.MeshBasicMaterial({ color: '#4fd1ff' }), N);
    for (let i = 0; i < N; i++) {
      const x = (i % 16) - 7.5;
      const z = Math.floor(i / 16) - 5.5;
      const d = Math.hypot(x, z);
      this.towers.push({ x: x * 1.35, z: z * 1.35, h: 0.4 + hash(i) * 2.2 + Math.max(0, 4 - d) * 0.7, ph: hash(i * 3) });
    }
    g.add(this.cityTowers, this.cityTops);
    // a big soft cloud floating above the city
    const mat = new THREE.MeshStandardMaterial({ color: '#ffffff', roughness: 0.9, emissive: '#4f7fd0', emissiveIntensity: 0.25 });
    const puffs: [number, number, number, number][] = [[0, 0, 0, 2.6], [-2.4, -0.5, 0.3, 1.9], [2.5, -0.5, 0, 2.0], [-1.1, 1.3, 0, 1.8], [1.4, 1.1, -0.3, 1.7], [-4.2, -1.1, 0, 1.3], [4.3, -1.0, 0.2, 1.4]];
    puffs.forEach(([x, y, z, r]) => {
      const m = new THREE.Mesh(new THREE.SphereGeometry(r, 24, 16), mat);
      m.position.set(x, y, z);
      this.cloud.add(m);
    });
    this.cloud.position.set(0, 10, -2);
    g.add(this.cloud);
    return g;
  }

  private buildVault() {
    const g = new THREE.Group();
    g.add(gridFloor(60, 60, -2.2));
    const add = (obj: THREE.Object3D, home: [number, number, number], dir: [number, number, number], label: string, anchor: [number, number, number] = [0, 0, 0]) => {
      obj.position.set(...home);
      g.add(obj);
      this.parts.push({ obj, home: new THREE.Vector3(...home), dir: new THREE.Vector3(...dir), label, anchor: new THREE.Vector3(...anchor) });
    };
    add(solid(new THREE.BoxGeometry(3.2, 3.2, 3.2), '#1f6fe0', '#bfe3ff'), [0, 0, 0], [0, 0, 0], 'VAULT BODY', [1.6, 1.6, 0]);
    const door = new THREE.Group();
    door.add(solid(new THREE.BoxGeometry(2.6, 2.6, 0.3), '#2f86ff', '#d6ecff'));
    const wheel = new THREE.Mesh(new THREE.TorusGeometry(0.6, 0.08, 10, 40), new THREE.MeshStandardMaterial({ color: '#d0d6e2', metalness: 0.8, roughness: 0.3 }));
    wheel.position.z = 0.25;
    door.add(wheel);
    add(door, [0, 0, 1.75], [0, 0, 3.2], 'ACCESS POLICY', [1.3, 1.3, 0]);
    for (let i = 0; i < 3; i++) {
      const card = solid(new THREE.BoxGeometry(1.5, 0.08, 1.0), '#4fd1ff', '#0a1a3f');
      add(card, [0, -0.6 + i * 0.55, 0], [-2.8 - i * 0.6, 1.2 + i * 0.9, 0.4], i === 0 ? 'SECRET: db-password' : i === 1 ? 'SECRET: api-key' : 'SECRET: sp-client', [0.75, 0, 0]);
    }
    for (let i = 0; i < 2; i++) {
      const cert = new THREE.Group();
      cert.add(solid(new THREE.CylinderGeometry(0.55, 0.55, 0.12, 28), '#ffd36e', '#3a2c00'));
      cert.rotation.x = Math.PI / 2;
      add(cert, [0.5 - i, 0.5, -0.4], [3.0 + i * 0.6, 1.4 + i * 1.1, -0.5], i === 0 ? 'CERT: *.platform.corp' : 'CERT: gateway-tls', [0.55, 0.55, 0]);
    }
    const key = new THREE.Group();
    key.add(solid(new THREE.TorusGeometry(0.35, 0.1, 8, 24), '#ff7a59', '#3a1000'));
    const stem = solid(new THREE.BoxGeometry(1.2, 0.14, 0.14), '#ff7a59', '#3a1000');
    stem.position.x = 0.9;
    key.add(stem);
    add(key, [0, 1.0, 0.3], [0.2, 3.2, 1.2], 'HSM KEY', [0.4, 0.3, 0]);
    // private network cage (appears in part 2)
    this.cage = new THREE.Group();
    const cageBox = edges(new THREE.BoxGeometry(7.5, 5.5, 7.5), GREEN, 0.9);
    this.cage.add(cageBox);
    const inner = edges(new THREE.BoxGeometry(7.5, 5.5, 7.5, 6, 4, 6), GREEN, 0.18);
    this.cage.add(inner);
    this.cage.position.y = 0.4;
    g.add(this.cage);
    return g;
  }

  private buildTunnel() {
    const g = new THREE.Group();
    g.add(gridFloor(80, 80, -1.2));
    const names = ['LAPTOP', 'PROXY', 'SASE', 'IDE'];
    names.forEach((name, i) => {
      const x = -9 + i * 6;
      const ng = new THREE.Group();
      const mat = new THREE.LineBasicMaterial({ color: LINE });
      const geo = i === 0 ? new THREE.BoxGeometry(2.2, 0.15, 1.5) : i === 3 ? new THREE.BoxGeometry(2.4, 1.6, 0.2) : new THREE.BoxGeometry(1.8, 1.8, 1.8);
      const e = new THREE.LineSegments(new THREE.EdgesGeometry(geo), mat);
      ng.add(e);
      if (i === 0) {
        const lid = new THREE.LineSegments(new THREE.EdgesGeometry(new THREE.BoxGeometry(2.2, 1.4, 0.08)), mat);
        lid.position.set(0, 0.7, -0.75);
        lid.rotation.x = -0.2;
        ng.add(lid);
      }
      ng.position.set(x, 0.3, 0);
      g.add(ng);
      this.tNodes.push({ g: ng, mat, x, name });
      if (i > 0) {
        const pts = [new THREE.Vector3(x - 6 + 1.2, 0.3, 0), new THREE.Vector3(x - 1.1, 0.3, 0)];
        const line = new THREE.Line(new THREE.BufferGeometry().setFromPoints(pts), new THREE.LineDashedMaterial({ color: LINE, dashSize: 0.25, gapSize: 0.18 }));
        line.computeLineDistances();
        g.add(line);
        this.tLinks.push(line);
      }
    });
    this.packet = new THREE.Mesh(new THREE.SphereGeometry(0.22, 16, 12), new THREE.MeshBasicMaterial({ color: BLUE }));
    g.add(this.packet);
    return g;
  }

  private buildNetwork() {
    const g = new THREE.Group();
    g.add(gridFloor(80, 80, -6));
    const layers = [1, 3, 6, 10, 14];
    const pts: THREE.Vector3[] = [];
    layers.forEach((n, li) => {
      for (let i = 0; i < n; i++) {
        const a = (i / n) * Math.PI * 2 + li;
        const r = li * 2.4;
        const p = new THREE.Vector3(Math.cos(a) * r, 4 - li * 2.1 + (hash(li * 10 + i) - 0.5), Math.sin(a) * r);
        pts.push(p);
        const m = new THREE.Mesh(new THREE.OctahedronGeometry(li === 0 ? 0.6 : 0.32), new THREE.MeshBasicMaterial({ color: '#2a4a80' }));
        m.position.copy(p);
        g.add(m);
        this.nNodes.push({ m, p, order: pts.length - 1 });
      }
    });
    // connect each node to nearest node of previous layer
    const seg: number[] = [];
    let start = 0;
    layers.forEach((n, li) => {
      if (li > 0) {
        const prevStart = start - layers[li - 1];
        for (let i = 0; i < n; i++) {
          const p = pts[start + i];
          let best = prevStart;
          let bd = Infinity;
          for (let k = prevStart; k < start; k++) {
            const d = p.distanceTo(pts[k]);
            if (d < bd) {
              bd = d;
              best = k;
            }
          }
          const q = pts[best];
          seg.push(q.x, q.y, q.z, p.x, p.y, p.z);
          this.nEdgeOrder.push(start + i);
        }
      }
      start += n;
    });
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.Float32BufferAttribute(seg, 3));
    geo.setAttribute('color', new THREE.Float32BufferAttribute(new Array(seg.length).fill(0.3), 3));
    this.nEdges = new THREE.LineSegments(geo, new THREE.LineBasicMaterial({ vertexColors: true }));
    g.add(this.nEdges);
    return g;
  }

  private buildGlobe() {
    const g = this.globe;
    const R = 5;
    const sph = new THREE.LineSegments(new THREE.WireframeGeometry(new THREE.SphereGeometry(R, 24, 16)), new THREE.LineBasicMaterial({ color: '#2b5aa8', transparent: true, opacity: 0.7 }));
    g.add(sph);
    const toV = (lat: number, lon: number, r = R) => {
      const la = (lat * Math.PI) / 180;
      const lo = (lon * Math.PI) / 180;
      return new THREE.Vector3(r * Math.cos(la) * Math.cos(lo), r * Math.sin(la), -r * Math.cos(la) * Math.sin(lo));
    };
    // gateways (rough city coordinates)
    const sites: [number, number][] = [[50, 8], [52, 13], [40, -74], [37, -122], [1, 103], [35, 139], [-33, 151], [51, 0], [19, 72], [-23, -46]];
    sites.forEach(([la, lo], i) => {
      const m = new THREE.Mesh(new THREE.SphereGeometry(0.12, 10, 8), new THREE.MeshBasicMaterial({ color: GREEN }));
      m.position.copy(toV(la, lo));
      m.userData.i = i;
      g.add(m);
    });
    const pairs = [[0, 2], [0, 3], [0, 4], [2, 3], [0, 5], [7, 8], [3, 6], [1, 9], [4, 5], [0, 8]];
    pairs.forEach(([a, b], k) => {
      const A = toV(...sites[a]);
      const B = toV(...sites[b]);
      const pts: THREE.Vector3[] = [];
      for (let i = 0; i <= 48; i++) {
        const p = A.clone().lerp(B, i / 48).normalize().multiplyScalar(R + Math.sin((i / 48) * Math.PI) * 1.4);
        pts.push(p);
      }
      const line = new THREE.Line(new THREE.BufferGeometry().setFromPoints(pts), new THREE.LineBasicMaterial({ color: k % 2 ? GREEN : BLUE }));
      line.geometry.setDrawRange(0, 0);
      g.add(line);
      this.arcs.push({ line, n: pts.length, a: k * 0.08 });
    });
    const wrap = new THREE.Group();
    wrap.add(g);
    return wrap;
  }

  // ---------- per frame ----------
  /** Returns the projected rect of the stage screen (only in stage mode). */
  update(c: Ctx3D): DOMRect | null {
    if (this.mode === 'none') return null;
    let rect: DOMRect | null = null;
    const { t, u } = c;
    this.camera.fov = 40;
    this.camera.updateProjectionMatrix();
    switch (this.mode) {
      case 'city': {
        const ph = c.beat - Math.floor(c.beat);
        const energy = Number(c.opts.energy ?? 0.6);
        const m = new THREE.Matrix4();
        const q = new THREE.Quaternion();
        this.towers.forEach((tw, i) => {
          const wave = Math.sin(tw.x * 0.5 + tw.z * 0.4 - t * 2.2) * 0.5 + 0.5;
          const bump = Math.exp(-((ph + tw.ph * 0.25) % 1) * 6) * energy;
          const h = tw.h * (0.7 + 0.3 * wave) + bump * 0.9;
          m.compose(new THREE.Vector3(tw.x, h / 2, tw.z), q, new THREE.Vector3(1, h, 1));
          this.cityTowers.setMatrixAt(i, m);
          m.compose(new THREE.Vector3(tw.x, h + 0.04, tw.z), q, new THREE.Vector3(1, 1, 1));
          this.cityTops.setMatrixAt(i, m);
        });
        this.cityTowers.instanceMatrix.needsUpdate = true;
        this.cityTops.instanceMatrix.needsUpdate = true;
        this.cloud.position.y = 10 + Math.sin(t * 0.8) * 0.4;
        this.cloud.scale.setScalar(1 + c.pulse * 0.04 * energy);
        const a = 0.75 + t * 0.06;
        this.camera.position.set(Math.sin(a) * 26, 18 - easeInOut(u) * 3, Math.cos(a) * 26);
        this.cloud.rotation.y = a; // wide side of the cloud faces the camera
        this.camera.lookAt(0, 3.5, 0);
        break;
      }
      case 'vault': {
        const a = t * 0.12 + 0.6;
        this.camera.position.set(Math.sin(a) * 13, 4.5, Math.cos(a) * 13);
        this.camera.lookAt(0, 0.6, 0);
        this.camera.updateMatrixWorld(true);
        const caged = !!c.opts.cage;
        const ex = caged ? 1 - easeInOut(prog(u, 0.0, 0.35)) : easeInOut(prog(u, 0.08, 0.55));
        this.parts.forEach((p, i) => {
          p.obj.position.copy(p.home).addScaledVector(p.dir, ex);
          p.obj.rotation.y = i === 0 ? 0 : ex * 0.4 * (i % 2 ? 1 : -1);
          if (i > 0) this.label(`p${i}`, p.label, p.obj.position.clone().add(p.anchor), clamp(ex * 3 - 1.2) * (caged ? 0 : 1), 'tag');
        });
        this.cage.visible = caged;
        if (caged) {
          const k = easeOut(prog(u, 0.25, 0.6));
          this.cage.scale.setScalar(0.6 + 0.4 * k);
          this.cage.children.forEach((ch) => ((ch as THREE.LineSegments).material as THREE.LineBasicMaterial).opacity = k * (ch === this.cage.children[0] ? 0.9 : 0.2));
          this.label('cage', 'PRIVATE ENDPOINT  ·  10.20.4.7', new THREE.Vector3(3.75, 3.2, 3.75), k, 'tag green');
          this.label('lim', 'PUBLIC ACCESS: DISABLED', new THREE.Vector3(-3.75, -2.2, 3.75), k, 'tag');
        }
        break;
      }
      case 'tunnel': {
        this.camera.position.set(-1.5 + u * 3, 5.5, 17);
        this.camera.lookAt(u * 2 - 1, 0, 0);
        this.camera.updateMatrixWorld(true);
        const ok = !!c.opts.success;
        const travel = prog(u, 0.05, ok ? 0.75 : 0.45);
        let x = -9 + travel * 18;
        let stuck = false;
        if (!ok && x > -3.9) {
          x = -3.9 - Math.abs(Math.sin(t * 14)) * 0.25; // bounces off the proxy
          stuck = true;
        }
        this.packet.position.set(x, 0.3 + Math.abs(Math.sin(t * 6)) * 0.3, 0);
        (this.packet.material as THREE.MeshBasicMaterial).color.set(stuck ? RED : ok && travel >= 1 ? GREEN : BLUE);
        this.tNodes.forEach((n, i) => {
          const reached = x >= n.x - 1.2 || i === 0;
          n.mat.color.set(stuck && i === 1 ? (Math.floor(t * 4) % 2 ? RED : LINE) : reached && ok ? GREEN : reached ? '#d0d6e2' : LINE);
          this.label(`n${i}`, n.name, new THREE.Vector3(n.x, -0.9, 0.9), 1, 'tag');
        });
        if (stuck) this.label('err', 'ERR_TUNNEL_CONNECTION_FAILED', new THREE.Vector3(-6, 2.2, 0), Math.floor(t * 3) % 2 ? 1 : 0.6, 'tag red');
        if (ok && travel >= 1) this.label('ok', 'CONNECTED  ·  12 ms', new THREE.Vector3(9, 2.0, 0), 1, 'tag green');
        break;
      }
      case 'network': {
        const lit = easeInOut(prog(u, 0.05, 0.8)) * this.nNodes.length;
        const vocal = Number(c.opts.vocal ?? 0);
        const release = Number(c.opts.release ?? 0);
        this.nNodes.forEach((n, i) => {
          const on = i < lit;
          // the held "riiiight": nodes ripple outwards with the voice, everything flashes on the release
          const ripple = vocal * (0.5 + 0.5 * Math.sin(t * 9 - n.p.length() * 0.8));
          const col = (n.m.material as THREE.MeshBasicMaterial).color;
          col.set(on ? (i === 0 ? '#ffffff' : GREEN) : '#2a4a80');
          if (on) col.lerp(new THREE.Color('#ff7a59'), ripple * 0.6).lerp(new THREE.Color('#ffffff'), release * 0.8);
          n.m.scale.setScalar(on ? 1 + c.pulse * 0.3 + ripple * 0.9 + release * 0.5 : 1);
          n.m.rotation.y = t + i;
        });
        const col = this.nEdges.geometry.attributes.color as THREE.BufferAttribute;
        this.nEdgeOrder.forEach((ni, k) => {
          const on = ni < lit;
          const boost = on ? 1 + vocal * 0.6 + release * 1.5 : 1;
          const r = (on ? 0.31 : 0.16) * boost, gg = (on ? 0.82 : 0.29) * boost, b = (on ? 1.0 : 0.5) * boost;
          col.setXYZ(k * 2, r, gg, b);
          col.setXYZ(k * 2 + 1, r, gg, b);
        });
        col.needsUpdate = true;
        const a = t * 0.18;
        const zoom = 1 - vocal * 0.12 - release * 0.08;
        this.camera.position.set(Math.sin(a) * 18 * zoom, (9 - u * 3) * zoom, Math.cos(a) * 18 * zoom);
        this.camera.position.x += Math.sin(t * 61) * release * 0.25;
        this.camera.lookAt(0, -1, 0);
        break;
      }
      case 'globe': {
        this.globe.rotation.y = t * 0.15;
        this.globe.rotation.x = 0.35;
        this.arcs.forEach((a) => {
          const k = easeOut(prog(u, a.a, a.a + 0.3));
          a.line.geometry.setDrawRange(0, Math.floor(k * a.n));
        });
        this.camera.position.set(0, 1.5, 15);
        this.camera.lookAt(2.2, 0, 0);
        break;
      }
    }
    this.renderer.render(this.scene, this.camera);
    return rect;
  }
}
