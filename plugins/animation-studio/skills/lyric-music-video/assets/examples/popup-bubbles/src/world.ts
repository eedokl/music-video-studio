// The 3D world: a data-center corridor with a firewall, a padlock vault,
// and a hero "cloud" floating above. The camera path changes per song section.

import * as THREE from 'three';
import type { Bands } from './audio';
import type { SectionId } from './lyrics';

interface Palette {
  top: THREE.Color;
  bottom: THREE.Color;
  grid: THREE.Color;
  accent: THREE.Color;
  led: THREE.Color;
}

const pal = (top: string, bottom: string, grid: string, accent: string, led: string): Palette => ({
  top: new THREE.Color(top),
  bottom: new THREE.Color(bottom),
  grid: new THREE.Color(grid),
  accent: new THREE.Color(accent),
  led: new THREE.Color(led),
});

const PALETTES: Record<SectionId, Palette> = {
  intro: pal('#02030a', '#0b1a3a', '#1e6fff', '#5ab0ff', '#3fa9ff'),
  verse1: pal('#030716', '#0a2a4a', '#00c8ff', '#00e0ff', '#00ffa8'),
  chorus: pal('#120530', '#ff5a8a', '#ff4fd8', '#ffd04f', '#ff7bd5'),
  verse2: pal('#08031a', '#2a0f5a', '#9b5cff', '#c38bff', '#7cf3ff'),
  bridge: pal('#120202', '#3a0a06', '#ff3b2f', '#ff9a2f', '#ff4030'),
  final: pal('#0a0428', '#ff7a3d', '#ffe14f', '#4ffff0', '#ffe14f'),
  outro: pal('#000000', '#071427', '#1e6fff', '#5ab0ff', '#3fa9ff'),
};

const CORRIDOR_START = 24;
const CORRIDOR_END = -120;
const FIREWALL_Z = -58;
const VAULT_Z = -104;
const HERO = new THREE.Vector3(0, 46, -40);

const rand = mulberry32(42);
function mulberry32(a: number) {
  return () => {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
const smooth = (x: number) => x * x * (3 - 2 * x);

export class World {
  readonly scene = new THREE.Scene();
  readonly camera: THREE.PerspectiveCamera;

  private palette = {
    top: new THREE.Color(),
    bottom: new THREE.Color(),
    grid: new THREE.Color(),
    accent: new THREE.Color(),
    led: new THREE.Color(),
  };
  private skyMat!: THREE.ShaderMaterial;
  private gridMat!: THREE.ShaderMaterial;
  private firewallMat!: THREE.ShaderMaterial;
  private leds!: THREE.InstancedMesh;
  private ledBase: number[] = [];
  private packets!: THREE.InstancedMesh;
  private packetData: { x: number; y: number; speed: number; phase: number; bad: boolean; lastZ: number }[] = [];
  private rings: { mesh: THREE.Mesh; age: number }[] = [];
  private hero = new THREE.Group();
  private heroMat!: THREE.MeshStandardMaterial;
  private orbits = new THREE.Group();
  private vault = new THREE.Group();
  private vaultGlow!: THREE.MeshStandardMaterial;
  private scanners: THREE.Mesh[] = [];
  private clouds: THREE.Group[] = [];
  private sparks!: THREE.Points;
  private sparkVel: Float32Array;
  private sparkLife: Float32Array;
  private sparkCursor = 0;
  private keywords: { sprite: THREE.Sprite; vel: THREE.Vector3; age: number; life: number }[] = [];
  private corridorLights: THREE.PointLight[] = [];
  private camPos = new THREE.Vector3(0, 80, 60);
  private camLook = new THREE.Vector3(0, 30, -40);
  private tmp = new THREE.Object3D();
  private tmpColor = new THREE.Color();

  constructor(aspect: number) {
    this.camera = new THREE.PerspectiveCamera(60, aspect, 0.1, 1200);
    this.scene.fog = new THREE.FogExp2(0x000000, 0.009);
    this.copyPalette(PALETTES.intro, 1);
    this.buildSky();
    this.buildGrid();
    this.buildLights();
    this.buildRacks();
    this.buildFirewall();
    this.buildPackets();
    this.buildVault();
    this.buildHero();
    this.buildClouds();
    this.buildScanners();
    this.buildStars();
    const SPARKS = 1500;
    this.sparkVel = new Float32Array(SPARKS * 3);
    this.sparkLife = new Float32Array(SPARKS);
    this.buildSparks(SPARKS);
  }

  // ---------- construction ----------

  private buildSky() {
    this.skyMat = new THREE.ShaderMaterial({
      side: THREE.BackSide,
      depthWrite: false,
      fog: false,
      uniforms: { uTop: { value: this.palette.top }, uBottom: { value: this.palette.bottom }, uTime: { value: 0 } },
      vertexShader: `varying vec3 vP; void main(){ vP = normalize(position); gl_Position = projectionMatrix*modelViewMatrix*vec4(position,1.0);} `,
      fragmentShader: `
        uniform vec3 uTop; uniform vec3 uBottom; uniform float uTime; varying vec3 vP;
        float h(vec2 p){ return fract(sin(dot(p, vec2(12.9898,78.233)))*43758.5453); }
        void main(){
          float y = clamp(vP.y*0.5+0.5, 0.0, 1.0);
          vec3 c = mix(uBottom, uTop, smoothstep(0.35, 0.85, y));
          float band = sin(vP.x*6.0 + uTime*0.2 + sin(vP.z*4.0+uTime*0.13)*2.0);
          c += uBottom * 0.25 * smoothstep(0.6,1.0,band) * smoothstep(0.45,0.7,y) * (1.0-smoothstep(0.7,0.95,y));
          gl_FragColor = vec4(c, 1.0);
        }`,
    });
    this.scene.add(new THREE.Mesh(new THREE.SphereGeometry(900, 32, 16), this.skyMat));
  }

  private buildGrid() {
    this.gridMat = new THREE.ShaderMaterial({
      transparent: true,
      depthWrite: false,
      uniforms: { uColor: { value: this.palette.grid }, uTime: { value: 0 }, uPulse: { value: 0 } },
      vertexShader: `varying vec2 vW; void main(){ vec4 w = modelMatrix*vec4(position,1.0); vW = w.xz; gl_Position = projectionMatrix*viewMatrix*w; }`,
      fragmentShader: `
        uniform vec3 uColor; uniform float uTime; uniform float uPulse; varying vec2 vW;
        void main(){
          vec2 p = vW / 4.0; p.y += uTime*1.5;
          vec2 g = abs(fract(p-0.5)-0.5)/fwidth(p);
          float line = 1.0 - min(min(g.x,g.y), 1.0);
          float d = length(vW - vec2(0.0,-40.0));
          float fade = 1.0 - smoothstep(60.0, 280.0, d);
          float wave = 0.5 + 0.5*sin(d*0.15 - uTime*4.0);
          float a = line * fade * (0.45 + uPulse*0.9 + wave*0.15);
          gl_FragColor = vec4(uColor*(0.8+uPulse*0.8), a*0.8);
        }`,
    });
    const grid = new THREE.Mesh(new THREE.PlaneGeometry(800, 800), this.gridMat);
    grid.rotation.x = -Math.PI / 2;
    grid.position.y = -0.01;
    this.scene.add(grid);
    const floor = new THREE.Mesh(
      new THREE.PlaneGeometry(800, 800),
      new THREE.MeshStandardMaterial({ color: 0x04060c, roughness: 0.35, metalness: 0.8 }),
    );
    floor.rotation.x = -Math.PI / 2;
    floor.position.y = -0.05;
    this.scene.add(floor);
  }

  private buildLights() {
    this.scene.add(new THREE.HemisphereLight(0x8fb8ff, 0x101020, 0.6));
    const sun = new THREE.DirectionalLight(0xffffff, 1.2);
    sun.position.set(30, 80, 40);
    this.scene.add(sun);
    for (let z = CORRIDOR_START; z > CORRIDOR_END; z -= 24) {
      const l = new THREE.PointLight(0x00c8ff, 30, 30, 1.6);
      l.position.set(0, 6, z);
      this.scene.add(l);
      this.corridorLights.push(l);
    }
  }

  private buildRacks() {
    const rows: [number, number][] = [];
    for (let z = CORRIDOR_START; z > CORRIDOR_END; z -= 2.2) {
      if (Math.abs(z - FIREWALL_Z) < 3) continue;
      rows.push([-7, z], [7, z], [-11, z], [11, z]);
    }
    const rackMat = new THREE.MeshStandardMaterial({ color: 0x151a26, roughness: 0.4, metalness: 0.7 });
    const racks = new THREE.InstancedMesh(new THREE.BoxGeometry(2.6, 6, 2), rackMat, rows.length);
    const LED_PER = 6;
    this.leds = new THREE.InstancedMesh(
      new THREE.BoxGeometry(0.08, 0.12, 1.6),
      new THREE.MeshBasicMaterial({ toneMapped: false }),
      rows.length * LED_PER,
    );
    let li = 0;
    rows.forEach(([x, z], i) => {
      const hgt = x * x > 60 ? 7.5 : 6;
      this.tmp.position.set(x, hgt / 2, z);
      this.tmp.scale.set(1, hgt / 6, 1);
      this.tmp.rotation.set(0, 0, 0);
      this.tmp.updateMatrix();
      racks.setMatrixAt(i, this.tmp.matrix);
      for (let k = 0; k < LED_PER; k++) {
        const face = x < 0 ? x + 1.32 : x - 1.32;
        this.tmp.position.set(face, 0.8 + k * 0.85 + rand() * 0.2, z + (rand() - 0.5) * 0.3);
        this.tmp.scale.set(1, 1, 0.3 + rand() * 0.7);
        this.tmp.updateMatrix();
        this.leds.setMatrixAt(li, this.tmp.matrix);
        this.leds.setColorAt(li, this.tmpColor.setRGB(0, 1, 0.6));
        this.ledBase.push(rand());
        li++;
      }
    });
    this.scene.add(racks, this.leds);

    // overhead cable trays
    const tray = new THREE.Mesh(
      new THREE.BoxGeometry(0.4, 0.2, CORRIDOR_START - CORRIDOR_END),
      new THREE.MeshStandardMaterial({ color: 0x222833, metalness: 0.9, roughness: 0.3 }),
    );
    for (const x of [-4, 4]) {
      const t = tray.clone();
      t.position.set(x, 7.2, (CORRIDOR_START + CORRIDOR_END) / 2);
      this.scene.add(t);
    }
  }

  private buildFirewall() {
    this.firewallMat = new THREE.ShaderMaterial({
      transparent: true,
      depthWrite: false,
      side: THREE.DoubleSide,
      blending: THREE.AdditiveBlending,
      uniforms: {
        uColor: { value: this.palette.accent },
        uTime: { value: 0 },
        uHit: { value: new THREE.Vector3(0, 0, -99) },
        uPulse: { value: 0 },
      },
      vertexShader: `varying vec2 vUv; void main(){ vUv = uv; gl_Position = projectionMatrix*modelViewMatrix*vec4(position,1.0);} `,
      fragmentShader: `
        uniform vec3 uColor; uniform float uTime; uniform vec3 uHit; uniform float uPulse; varying vec2 vUv;
        float hex(vec2 p){ p = abs(p); return max(dot(p, normalize(vec2(1.0,1.73))), p.x); }
        void main(){
          vec2 p = (vUv - 0.5) * vec2(16.0, 9.0);
          vec2 r = vec2(1.0, 1.73); vec2 h = r*0.5;
          vec2 a = mod(p, r) - h; vec2 b = mod(p - h, r) - h;
          vec2 gv = dot(a,a) < dot(b,b) ? a : b;
          float edge = smoothstep(0.42, 0.5, hex(gv));
          float d = distance(p, uHit.xy);
          float age = uTime - uHit.z;
          float ripple = smoothstep(0.6, 0.0, abs(d - age*14.0)) * exp(-age*2.5);
          float scan = smoothstep(0.0, 0.3, 1.0 - abs(fract(vUv.y - uTime*0.3) - 0.5)*2.0) * 0.3;
          float alpha = edge*(0.35+uPulse*0.6) + ripple*1.2 + scan*edge + 0.04;
          gl_FragColor = vec4(uColor * (1.0 + ripple*2.0), alpha);
        }`,
    });
    const wall = new THREE.Mesh(new THREE.PlaneGeometry(16, 9), this.firewallMat);
    wall.position.set(0, 4.5, FIREWALL_Z);
    this.scene.add(wall);
    const frameMat = new THREE.MeshStandardMaterial({ color: 0x2b3240, metalness: 0.9, roughness: 0.25 });
    for (const x of [-8.2, 8.2]) {
      const post = new THREE.Mesh(new THREE.BoxGeometry(0.5, 9.6, 0.6), frameMat);
      post.position.set(x, 4.8, FIREWALL_Z);
      this.scene.add(post);
    }
    const beam = new THREE.Mesh(new THREE.BoxGeometry(16.9, 0.5, 0.6), frameMat);
    beam.position.set(0, 9.4, FIREWALL_Z);
    this.scene.add(beam);
  }

  private buildPackets() {
    const N = 90;
    this.packets = new THREE.InstancedMesh(
      new THREE.BoxGeometry(0.35, 0.35, 1.4),
      new THREE.MeshBasicMaterial({ toneMapped: false }),
      N,
    );
    for (let i = 0; i < N; i++) {
      const bad = rand() < 0.3;
      this.packetData.push({
        x: (rand() - 0.5) * 9,
        y: 0.8 + rand() * 6.5,
        speed: 10 + rand() * 14,
        phase: rand() * 1000,
        bad,
        lastZ: 0,
      });
      this.packets.setColorAt(i, new THREE.Color(bad ? '#ff2a3a' : '#3dff9a').multiplyScalar(bad ? 1.4 : 0.9));
    }
    this.scene.add(this.packets);
    const ringGeo = new THREE.RingGeometry(0.3, 0.45, 24);
    for (let i = 0; i < 24; i++) {
      const m = new THREE.Mesh(
        ringGeo,
        new THREE.MeshBasicMaterial({ color: 0xff3040, transparent: true, opacity: 0, blending: THREE.AdditiveBlending, depthWrite: false, toneMapped: false }),
      );
      m.visible = false;
      this.scene.add(m);
      this.rings.push({ mesh: m, age: 99 });
    }
  }

  private buildVault() {
    const gold = new THREE.MeshStandardMaterial({ color: 0xffc840, metalness: 1, roughness: 0.25, emissive: 0x402800 });
    this.vaultGlow = new THREE.MeshStandardMaterial({ color: 0x111111, emissive: 0x00e0ff, emissiveIntensity: 2 });
    const body = new THREE.Mesh(new THREE.BoxGeometry(5, 4.2, 1.8), gold);
    const shackle = new THREE.Mesh(new THREE.TorusGeometry(1.7, 0.38, 20, 48, Math.PI), new THREE.MeshStandardMaterial({ color: 0xd8dde6, metalness: 1, roughness: 0.15 }));
    shackle.position.y = 2.1;
    const hole = new THREE.Mesh(new THREE.CylinderGeometry(0.45, 0.45, 2, 24), this.vaultGlow);
    hole.rotation.x = Math.PI / 2;
    hole.position.y = 0.3;
    const slot = new THREE.Mesh(new THREE.BoxGeometry(0.35, 1.1, 2), this.vaultGlow);
    slot.position.y = -0.5;
    const halo = new THREE.Mesh(new THREE.TorusGeometry(4.6, 0.06, 8, 96), this.vaultGlow);
    this.vault.add(body, shackle, hole, slot, halo);
    this.vault.position.set(0, 4.5, VAULT_Z);
    this.scene.add(this.vault);
  }

  private buildHero() {
    this.heroMat = new THREE.MeshStandardMaterial({ color: 0xffffff, roughness: 0.6, emissive: 0x2050ff, emissiveIntensity: 0.4, flatShading: true });
    const puffs: [number, number, number, number][] = [
      [0, 0, 0, 5], [-5, -1, 0.5, 3.8], [5, -1, 0, 4], [-2.5, 2.6, 0, 3.6], [2.8, 2.2, -0.5, 3.4],
      [-8.5, -2.2, 0, 2.6], [8.6, -2.1, 0.4, 2.7], [0, -2.4, 2.5, 3.5], [-3, -2, -2.5, 3.2], [3, -2.2, -2.4, 3.2],
    ];
    const geo = new THREE.IcosahedronGeometry(1, 2);
    for (const [x, y, z, r] of puffs) {
      const m = new THREE.Mesh(geo, this.heroMat);
      m.position.set(x, y, z);
      m.scale.setScalar(r);
      this.hero.add(m);
    }
    this.hero.position.copy(HERO);
    this.scene.add(this.hero);

    // orbiting rings with service nodes
    const ringColors = [0x00e0ff, 0xff4fd8, 0xffd04f];
    ringColors.forEach((c, i) => {
      const g = new THREE.Group();
      const R = 16 + i * 5;
      const ring = new THREE.Mesh(new THREE.TorusGeometry(R, 0.08, 8, 160), new THREE.MeshBasicMaterial({ color: c, toneMapped: false }));
      ring.rotation.x = Math.PI / 2;
      g.add(ring);
      const nodeGeo = new THREE.OctahedronGeometry(0.9);
      for (let k = 0; k < 6 + i * 2; k++) {
        const a = (k / (6 + i * 2)) * Math.PI * 2;
        const n = new THREE.Mesh(nodeGeo, new THREE.MeshBasicMaterial({ color: c, toneMapped: false }));
        n.position.set(Math.cos(a) * R, 0, Math.sin(a) * R);
        g.add(n);
      }
      g.rotation.set(0.35 * (i - 1), 0, 0.25 * i);
      g.userData.speed = 0.15 + i * 0.07 * (i % 2 ? -1 : 1);
      this.orbits.add(g);
    });
    this.orbits.position.copy(HERO);
    this.scene.add(this.orbits);
  }

  private buildClouds() {
    const geo = new THREE.IcosahedronGeometry(1, 1);
    const mat = new THREE.MeshStandardMaterial({ color: 0xdfe8ff, roughness: 1, flatShading: true, transparent: true, opacity: 0.85 });
    for (let i = 0; i < 26; i++) {
      const g = new THREE.Group();
      const n = 4 + Math.floor(rand() * 4);
      for (let k = 0; k < n; k++) {
        const m = new THREE.Mesh(geo, mat);
        m.position.set((k - n / 2) * 1.8 + rand(), rand() * 1.2, rand() * 1.5);
        m.scale.setScalar(1.4 + rand() * 1.6);
        g.add(m);
      }
      const a = rand() * Math.PI * 2;
      const r = 45 + rand() * 120;
      g.position.set(Math.cos(a) * r, 28 + rand() * 40, -40 + Math.sin(a) * r);
      g.scale.setScalar(1.5 + rand() * 2.5);
      g.userData.drift = 0.5 + rand();
      this.clouds.push(g);
      this.scene.add(g);
    }
  }

  private buildScanners() {
    for (let i = 0; i < 2; i++) {
      const m = new THREE.Mesh(
        new THREE.PlaneGeometry(26, 0.25),
        new THREE.MeshBasicMaterial({ color: 0xff3020, transparent: true, opacity: 0, blending: THREE.AdditiveBlending, side: THREE.DoubleSide, depthWrite: false, toneMapped: false }),
      );
      m.rotation.x = -Math.PI / 2;
      m.scale.y = 30;
      this.scanners.push(m);
      this.scene.add(m);
    }
  }

  private buildStars() {
    const N = 2500;
    const pos = new Float32Array(N * 3);
    for (let i = 0; i < N; i++) {
      const v = new THREE.Vector3().randomDirection().multiplyScalar(500 + rand() * 300);
      v.y = Math.abs(v.y) + 40;
      pos.set([v.x, v.y, v.z], i * 3);
    }
    const g = new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.BufferAttribute(pos, 3));
    this.scene.add(new THREE.Points(g, new THREE.PointsMaterial({ color: 0xffffff, size: 1.6, sizeAttenuation: true, fog: false })));
  }

  private buildSparks(N: number) {
    const g = new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.BufferAttribute(new Float32Array(N * 3).fill(-9999), 3));
    g.setAttribute('color', new THREE.BufferAttribute(new Float32Array(N * 3), 3));
    this.sparks = new THREE.Points(
      g,
      new THREE.PointsMaterial({ size: 0.7, vertexColors: true, transparent: true, blending: THREE.AdditiveBlending, depthWrite: false, toneMapped: false }),
    );
    this.sparks.frustumCulled = false;
    this.scene.add(this.sparks);
  }

  // ---------- effects ----------

  private burst(at: THREE.Vector3, color: THREE.Color, count: number, speed: number) {
    const pos = this.sparks.geometry.attributes.position as THREE.BufferAttribute;
    const col = this.sparks.geometry.attributes.color as THREE.BufferAttribute;
    const N = this.sparkLife.length;
    for (let i = 0; i < count; i++) {
      const k = this.sparkCursor;
      this.sparkCursor = (this.sparkCursor + 1) % N;
      const v = new THREE.Vector3().randomDirection().multiplyScalar(speed * (0.4 + Math.random() * 0.6));
      pos.setXYZ(k, at.x, at.y, at.z);
      this.sparkVel.set([v.x, v.y, v.z], k * 3);
      this.sparkLife[k] = 1.2 + Math.random() * 0.8;
      col.setXYZ(k, color.r * 2, color.g * 2, color.b * 2);
    }
  }

  /** Big 3D word flying past the camera (used for the acronyms in each line). */
  spawnKeyword(text: string, color: string) {
    const c = document.createElement('canvas');
    const ctx = c.getContext('2d')!;
    const font = 'bold 120px "Arial Black", Impact, sans-serif';
    ctx.font = font;
    const w = Math.ceil(ctx.measureText(text).width) + 60;
    c.width = w;
    c.height = 170;
    ctx.font = font;
    ctx.textBaseline = 'middle';
    ctx.textAlign = 'center';
    ctx.shadowColor = color;
    ctx.shadowBlur = 30;
    ctx.fillStyle = color;
    ctx.fillText(text, w / 2, 88);
    ctx.shadowBlur = 0;
    ctx.fillStyle = '#ffffff';
    ctx.fillText(text, w / 2, 88);
    const tex = new THREE.CanvasTexture(c);
    tex.colorSpace = THREE.SRGBColorSpace;
    const sprite = new THREE.Sprite(new THREE.SpriteMaterial({ map: tex, transparent: true, depthWrite: false, toneMapped: false }));
    const h = 3.2;
    sprite.scale.set((h * w) / 170, h, 1);
    const fwd = new THREE.Vector3();
    this.camera.getWorldDirection(fwd);
    const right = new THREE.Vector3().crossVectors(fwd, this.camera.up).normalize();
    const up = new THREE.Vector3().crossVectors(right, fwd).normalize();
    const side = Math.random() < 0.5 ? -1 : 1;
    sprite.position
      .copy(this.camera.position)
      .addScaledVector(fwd, 34)
      .addScaledVector(right, side * (5 + Math.random() * 7))
      .addScaledVector(up, (Math.random() - 0.3) * 6);
    const vel = fwd.clone().multiplyScalar(-9).addScaledVector(right, side * 1.5);
    this.scene.add(sprite);
    this.keywords.push({ sprite, vel, age: 0, life: 3.6 });
  }

  private copyPalette(p: Palette, k: number) {
    this.palette.top.lerp(p.top, k);
    this.palette.bottom.lerp(p.bottom, k);
    this.palette.grid.lerp(p.grid, k);
    this.palette.accent.lerp(p.accent, k);
    this.palette.led.lerp(p.led, k);
  }

  // ---------- per-frame ----------

  /** p = progress 0..1 inside the current section. */
  update(t: number, dt: number, b: Bands, section: SectionId, p: number) {
    this.copyPalette(PALETTES[section], 1 - Math.exp(-dt * 1.5));
    const fog = this.scene.fog as THREE.FogExp2;
    fog.color.copy(this.palette.bottom).multiplyScalar(0.35);

    this.skyMat.uniforms.uTime.value = t;
    this.gridMat.uniforms.uTime.value = t;
    this.gridMat.uniforms.uPulse.value = b.beatPulse * 0.6 + b.bass * 0.4;
    this.firewallMat.uniforms.uTime.value = t;
    this.firewallMat.uniforms.uPulse.value = b.beatPulse;

    for (const l of this.corridorLights) {
      l.color.copy(this.palette.accent);
      l.intensity = 12 + b.bass * 30;
    }

    // rack LEDs blink with the music
    const n = this.leds.count;
    for (let i = 0; i < n; i++) {
      const base = this.ledBase[i];
      const on = Math.sin(t * (2 + base * 9) + base * 50) > 0.2 - b.high * 1.2;
      const k = on ? 0.7 + b.beatPulse * 0.9 : 0.05;
      this.tmpColor.copy(this.palette.led).multiplyScalar(k);
      if (base < 0.12) this.tmpColor.setRGB(k * 1.5, k * 0.15, k * 0.1);
      this.leds.setColorAt(i, this.tmpColor);
    }
    this.leds.instanceColor!.needsUpdate = true;

    this.updatePackets(t, section);
    this.updateRings(dt);

    // vault
    this.vault.rotation.y = Math.sin(t * 0.6) * 0.5;
    this.vault.position.y = 4.5 + Math.sin(t * 1.3) * 0.4;
    this.vaultGlow.emissive.copy(this.palette.accent);
    this.vaultGlow.emissiveIntensity = 1.5 + b.beatPulse * 3;

    // hero cloud
    const s = 1 + b.bass * 0.18 + b.beatPulse * 0.08;
    this.hero.scale.setScalar(s);
    this.hero.rotation.y = t * 0.12;
    this.hero.position.y = HERO.y + Math.sin(t * 0.7) * 1.2;
    this.heroMat.emissive.copy(this.palette.accent);
    this.heroMat.emissiveIntensity = 0.12 + b.level * 0.45 + b.beatPulse * 0.2;
    this.orbits.children.forEach((g, i) => {
      g.rotation.y += dt * (g.userData.speed as number) * (1 + b.mid * 2);
      g.scale.setScalar(1 + b.beatPulse * 0.04 * (i + 1));
    });

    for (const c of this.clouds) {
      c.position.x += dt * (c.userData.drift as number) * 1.5;
      if (c.position.x > 180) c.position.x = -180;
    }

    // bridge: security scan beams sweep the corridor
    const scanOn = section === 'bridge' ? 1 : 0;
    this.scanners.forEach((m, i) => {
      const mat = m.material as THREE.MeshBasicMaterial;
      mat.opacity += (scanOn * (0.55 + b.beatPulse * 0.4) - mat.opacity) * (1 - Math.exp(-dt * 3));
      m.visible = mat.opacity > 0.01;
      const ph = (t * 0.35 + i * 0.5) % 1;
      m.position.set(0, 0.3 + ph * 9, CORRIDOR_START - 20 - ((t * 25 + i * 60) % 140));
      m.position.y = 0.4 + (Math.sin(t * 2 + i * 3) * 0.5 + 0.5) * 8;
      m.position.z = -20 - Math.sin(t * 0.5 + i * 2) * 40;
      m.rotation.set(-Math.PI / 2 + Math.sin(t + i) * 0.15, 0, 0);
    });

    // final chorus: fireworks on beats around the hero cloud
    if (b.beat && (section === 'final' || section === 'chorus')) {
      const at = HERO.clone().add(new THREE.Vector3((Math.random() - 0.5) * 60, (Math.random() - 0.2) * 25, (Math.random() - 0.5) * 30));
      const hue = new THREE.Color().setHSL(Math.random(), 1, 0.6);
      this.burst(at, hue, section === 'final' ? 160 : 70, 14);
    }
    this.updateSparks(dt);
    this.updateKeywords(dt);
    this.updateCamera(t, dt, b, section, p);
  }

  private updatePackets(t: number, section: SectionId) {
    const len = CORRIDOR_START - CORRIDOR_END;
    const busy = section === 'chorus' || section === 'final' ? 1.4 : 1;
    this.packetData.forEach((d, i) => {
      const z = CORRIDOR_START - ((t * d.speed * busy + d.phase) % len);
      let visible = true;
      if (d.bad) {
        if (z < FIREWALL_Z) visible = false;
        if (d.lastZ >= FIREWALL_Z && z < FIREWALL_Z && d.lastZ - z < 10) this.blocked(d.x, d.y);
      }
      d.lastZ = z;
      this.tmp.position.set(d.x, d.y, z);
      this.tmp.rotation.set(0, 0, 0);
      this.tmp.scale.setScalar(visible ? 1 : 0);
      this.tmp.updateMatrix();
      this.packets.setMatrixAt(i, this.tmp.matrix);
    });
    this.packets.instanceMatrix.needsUpdate = true;
  }

  /** The firewall blocks a malicious packet: ripple on the wall + spark ring. */
  private blocked(x: number, y: number) {
    this.firewallMat.uniforms.uHit.value.set(x, y - 4.5, this.firewallMat.uniforms.uTime.value);
    const r = this.rings.find((r) => r.age > 0.6);
    if (r) {
      r.age = 0;
      r.mesh.position.set(x, y, FIREWALL_Z + 0.1);
      r.mesh.visible = true;
    }
    this.burst(new THREE.Vector3(x, y, FIREWALL_Z + 0.3), new THREE.Color('#ff3040'), 14, 5);
  }

  private updateRings(dt: number) {
    for (const r of this.rings) {
      if (!r.mesh.visible) continue;
      r.age += dt;
      r.mesh.scale.setScalar(1 + r.age * 8);
      (r.mesh.material as THREE.MeshBasicMaterial).opacity = Math.max(0, 1 - r.age / 0.6);
      if (r.age > 0.6) r.mesh.visible = false;
    }
  }

  private updateSparks(dt: number) {
    const pos = this.sparks.geometry.attributes.position as THREE.BufferAttribute;
    const col = this.sparks.geometry.attributes.color as THREE.BufferAttribute;
    const a = pos.array as Float32Array;
    const c = col.array as Float32Array;
    for (let i = 0; i < this.sparkLife.length; i++) {
      if (this.sparkLife[i] <= 0) continue;
      this.sparkLife[i] -= dt;
      this.sparkVel[i * 3 + 1] -= 6 * dt;
      a[i * 3] += this.sparkVel[i * 3] * dt;
      a[i * 3 + 1] += this.sparkVel[i * 3 + 1] * dt;
      a[i * 3 + 2] += this.sparkVel[i * 3 + 2] * dt;
      const f = Math.exp(-dt * 1.6);
      c[i * 3] *= f;
      c[i * 3 + 1] *= f;
      c[i * 3 + 2] *= f;
      if (this.sparkLife[i] <= 0) a[i * 3 + 1] = -9999;
    }
    pos.needsUpdate = true;
    col.needsUpdate = true;
  }

  private updateKeywords(dt: number) {
    this.keywords = this.keywords.filter((k) => {
      k.age += dt;
      k.sprite.position.addScaledVector(k.vel, dt);
      const m = k.sprite.material as THREE.SpriteMaterial;
      m.opacity = Math.min(1, k.age * 3) * Math.min(1, (k.life - k.age) * 2);
      if (k.age >= k.life) {
        this.scene.remove(k.sprite);
        m.map?.dispose();
        m.dispose();
        return false;
      }
      return true;
    });
  }

  private updateCamera(t: number, dt: number, b: Bands, section: SectionId, p: number) {
    const pos = new THREE.Vector3();
    const look = new THREE.Vector3();
    switch (section) {
      case 'intro': {
        // descend from the sky, past the hero cloud, into the data center
        const e = smooth(p);
        pos.set(Math.sin(e * 2) * 30, 110 - e * 100, 90 - e * 60);
        look.set(0, HERO.y * (1 - e) + 3 * e, -40 + e * 10);
        break;
      }
      case 'verse1':
      case 'verse2': {
        // fly down the corridor, through the firewall, up to the padlock vault
        const z = CORRIDOR_START - 4 - p * (CORRIDOR_START - VAULT_Z - 14);
        const sway = section === 'verse2' ? 2.2 : 1.2;
        pos.set(Math.sin(t * 0.4) * sway, 3.2 + Math.sin(t * 0.7) * 0.8, z);
        look.set(Math.sin(t * 0.3) * 1.5, 3.5, z - 20);
        break;
      }
      case 'chorus':
      case 'final': {
        // orbit the hero cloud
        const r = section === 'final' ? 52 : 42;
        const a = t * 0.18 + p * 1.5;
        pos.set(HERO.x + Math.cos(a) * r, HERO.y + 8 + Math.sin(t * 0.3) * 8, HERO.z + Math.sin(a) * r);
        look.copy(HERO);
        break;
      }
      case 'bridge': {
        // slow push past the scanners, low angle
        pos.set(-5 + p * 10, 1.6 + p * 2, 10 - p * 40);
        look.set(0, 4, -60);
        break;
      }
      case 'outro': {
        const e = smooth(p);
        pos.set(Math.sin(t * 0.1) * 60, 60 + e * 80, 60 + e * 120);
        look.copy(HERO);
        break;
      }
    }
    const k = 1 - Math.exp(-dt * 1.8);
    this.camPos.lerp(pos, k);
    this.camLook.lerp(look, k);
    this.camera.position.copy(this.camPos);
    this.camera.position.y += b.beatPulse * 0.15;
    this.camera.lookAt(this.camLook);
    this.camera.fov = 60 - b.beatPulse * 2.5;
    this.camera.updateProjectionMatrix();
  }
}
