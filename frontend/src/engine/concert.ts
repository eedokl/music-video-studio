// "Comfort Zone – Live": a stadium concert in three.js. Stage with LED wall and side screens (live
// close-up of the singer), band (singer, guitar, bass, drums, keys), thousands of fans, moving-head
// beams in haze, follow spot, flames, CO2 jets, spark curtain, confetti, fireworks and phone lights.
// Everything is a pure function of song time, so the frame-by-frame MP4 export matches playback.

import * as THREE from 'three';
import { EffectComposer } from 'three/examples/jsm/postprocessing/EffectComposer.js';
import { OutputPass } from 'three/examples/jsm/postprocessing/OutputPass.js';
import { RenderPass } from 'three/examples/jsm/postprocessing/RenderPass.js';
import { UnrealBloomPass } from 'three/examples/jsm/postprocessing/UnrealBloomPass.js';
import { mergeGeometries } from 'three/examples/jsm/utils/BufferGeometryUtils.js';
import { clamp, easeInOut, hash } from './util';

export type Shot =
  | 'wide' // from the back of the arena
  | 'crowd' // inside the crowd, heads in front
  | 'singer' // close-up of the singer
  | 'pit' // photo pit, looking up at the singer with the LED wall behind
  | 'wing' // from the side of the stage, crowd behind the singer
  | 'drums' // behind the drummer, looking out over the band to the crowd
  | 'guitar'
  | 'bass'
  | 'keys'
  | 'crane' // high sweeping crane over the crowd
  | 'wall' // framed on the LED wall (story content), band in silhouette
  | 'top' // straight down over the crowd
  | 'orbit'; // slow orbit around the singer

export interface Look {
  beams: string[]; // moving-head colours
  wash: string; // back light colour
  energy: number; // 0..1 – crowd jumping, light intensity, movement speed
  pattern?: 'sweep' | 'fan' | 'crowd' | 'up' | 'still' | 'chase';
  strobe?: boolean; // strobe the beams on riff hits
  pyro?: boolean; // flames on big hits
  co2?: number[]; // CO2 jet times
  sparks?: [number, number]; // spark curtain from the truss (from, to)
  confetti?: number; // confetti cannon time
  fireworks?: number[]; // firework burst times
  phones?: number; // 0..1 phone lights in the crowd
  ring?: number; // 0..1 phone lights form the 12-star ring
  follow?: number; // 0..1 follow spot on the singer
  blackout?: number; // 0..1 stage lights off
  wallBright?: number; // LED wall brightness (default 1)
}

export interface Perf {
  sing: number; // 0..1 the singer is singing
  hey: number; // 0..1 fist-pump moment
  held: number; // 0..1 held-note loudness (arm goes out)
  bow?: number; // 0..1 band bows at the end
}

export interface ConcertCtx {
  t: number;
  local: number; // seconds since the scene started
  u: number; // 0..1 scene progress
  beat: number;
  pulse: number;
  hit: number; // riff-hit flash envelope
  pyro: number; // big-hit envelope for flames
  shot: Shot;
  seed: number; // per-scene variation of the shot
  look: Look;
  perf: Perf;
  drawWall: (g: CanvasRenderingContext2D, w: number, h: number) => void;
}

const STAGE_Y = 1.6;
const SINGER = new THREE.Vector3(0, STAGE_Y, -1.4);

// ---------- small helpers ----------
function glowTexture(size = 128) {
  const c = document.createElement('canvas');
  c.width = c.height = size;
  const g = c.getContext('2d')!;
  const gr = g.createRadialGradient(size / 2, size / 2, 0, size / 2, size / 2, size / 2);
  gr.addColorStop(0, 'rgba(255,255,255,1)');
  gr.addColorStop(0.25, 'rgba(255,255,255,0.6)');
  gr.addColorStop(1, 'rgba(255,255,255,0)');
  g.fillStyle = gr;
  g.fillRect(0, 0, size, size);
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  return t;
}

/** Volumetric-looking light cone: apex at the origin, opening along +Z. */
const BEAM_LEN = 46;
function beamMaterial() {
  return new THREE.ShaderMaterial({
    uniforms: { color: { value: new THREE.Color('#ffffff') }, intensity: { value: 1 } },
    vertexShader: `
      varying float vD; varying vec3 vN; varying vec3 vV;
      void main() {
        vD = position.z / ${BEAM_LEN.toFixed(1)};
        vec4 mv = modelViewMatrix * vec4(position, 1.0);
        vV = normalize(-mv.xyz);
        vN = normalize(normalMatrix * normal);
        gl_Position = projectionMatrix * mv;
      }`,
    fragmentShader: `
      uniform vec3 color; uniform float intensity;
      varying float vD; varying vec3 vN; varying vec3 vV;
      void main() {
        float edge = pow(abs(dot(normalize(vN), normalize(vV))), 1.6);
        float fall = pow(1.0 - clamp(vD, 0.0, 1.0), 2.2);
        float a = edge * fall * intensity * smoothstep(0.0, 0.02, vD);
        gl_FragColor = vec4(color * a, 1.0);
      }`,
    transparent: true,
    depthWrite: false,
    blending: THREE.AdditiveBlending,
    side: THREE.DoubleSide,
  });
}
function beamGeometry(spread: number) {
  const g = new THREE.CylinderGeometry(0.07, spread, BEAM_LEN, 28, 1, true);
  g.translate(0, -BEAM_LEN / 2, 0);
  g.rotateX(-Math.PI / 2);
  return g;
}

function flameMaterial(hot: string, cool: string) {
  return new THREE.ShaderMaterial({
    uniforms: { time: { value: 0 }, amount: { value: 0 }, hot: { value: new THREE.Color(hot) }, cool: { value: new THREE.Color(cool) } },
    vertexShader: `
      varying vec2 vUv; varying vec3 vN; varying vec3 vV;
      void main() {
        vUv = uv;
        vec4 mv = modelViewMatrix * vec4(position, 1.0);
        vV = normalize(-mv.xyz); vN = normalize(normalMatrix * normal);
        gl_Position = projectionMatrix * mv;
      }`,
    fragmentShader: `
      uniform float time; uniform float amount; uniform vec3 hot; uniform vec3 cool;
      varying vec2 vUv; varying vec3 vN; varying vec3 vV;
      float h(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
      float n(vec2 p) { vec2 i = floor(p), f = fract(p); f = f * f * (3.0 - 2.0 * f);
        return mix(mix(h(i), h(i + vec2(1, 0)), f.x), mix(h(i + vec2(0, 1)), h(i + vec2(1, 1)), f.x), f.y); }
      void main() {
        float y = 1.0 - vUv.y; // 0 at the nozzle, 1 at the tip
        float edge = pow(abs(dot(normalize(vN), normalize(vV))), 1.2);
        float tex = n(vec2(vUv.x * 7.0, y * 5.0 - time * 7.0)) * 0.6 + n(vec2(vUv.x * 15.0, y * 11.0 - time * 13.0)) * 0.4;
        float a = edge * smoothstep(1.0, 0.25, y + tex * 0.35) * amount;
        vec3 col = mix(hot, cool, clamp(y * 1.4 + tex * 0.3, 0.0, 1.0));
        gl_FragColor = vec4(col * a * 1.6, 1.0);
      }`,
    transparent: true,
    depthWrite: false,
    blending: THREE.AdditiveBlending,
    side: THREE.DoubleSide,
  });
}

/** Lattice truss along +X (length len), as thin lines. */
function truss(len: number, size = 0.55, color = '#9aa0aa') {
  const p: number[] = [];
  const s = size / 2;
  const corners = [
    [-s, -s],
    [s, -s],
    [s, s],
    [-s, s],
  ];
  const seg = Math.max(1, Math.round(len / size));
  for (let i = 0; i < 4; i++) {
    const [a, b] = corners[i];
    p.push(0, a, b, len, a, b);
  }
  for (let k = 0; k <= seg; k++) {
    const x = (k / seg) * len;
    for (let i = 0; i < 4; i++) {
      const [a, b] = corners[i];
      const [c, d] = corners[(i + 1) % 4];
      p.push(x, a, b, x, c, d);
      if (k < seg) p.push(x, a, b, x + len / seg, c, d);
    }
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.Float32BufferAttribute(p, 3));
  return new THREE.LineSegments(g, new THREE.LineBasicMaterial({ color, transparent: true, opacity: 0.75 }));
}

interface Figure {
  root: THREE.Group;
  hips: THREE.Group;
  torso: THREE.Group;
  head: THREE.Group;
  armA: THREE.Group; // at -x
  armB: THREE.Group; // at +x
  foreA: THREE.Group;
  foreB: THREE.Group;
  legA: THREE.Group;
  legB: THREE.Group;
  kneeA: THREE.Group;
  kneeB: THREE.Group;
}
function figure(mat: THREE.Material, hair = false): Figure {
  const cap = (r: number, l: number) => new THREE.Mesh(new THREE.CapsuleGeometry(r, l, 4, 10), mat);
  const root = new THREE.Group();
  const hips = new THREE.Group();
  hips.position.y = 0.98;
  root.add(hips);
  const leg = (x: number) => {
    const g = new THREE.Group();
    g.position.set(x, 0, 0);
    const up = cap(0.085, 0.36);
    up.position.y = -0.24;
    g.add(up);
    const knee = new THREE.Group();
    knee.position.y = -0.48;
    const low = cap(0.075, 0.36);
    low.position.y = -0.24;
    knee.add(low);
    g.add(knee);
    hips.add(g);
    return { g, knee };
  };
  const la = leg(-0.12);
  const lb = leg(0.12);
  const torso = new THREE.Group();
  hips.add(torso);
  const chest = cap(0.2, 0.42);
  chest.position.y = 0.36;
  chest.scale.set(1, 1, 0.72);
  torso.add(chest);
  const head = new THREE.Group();
  head.position.y = 0.82;
  const skull = new THREE.Mesh(new THREE.SphereGeometry(0.125, 16, 12), mat);
  head.add(skull);
  if (hair) {
    const h = new THREE.Mesh(new THREE.SphereGeometry(0.15, 12, 10, 0, Math.PI * 2, 0, Math.PI * 0.62), mat);
    h.position.set(0, 0.02, -0.02);
    h.scale.set(1.05, 1.1, 1.15);
    head.add(h);
  }
  torso.add(head);
  const arm = (x: number) => {
    const g = new THREE.Group();
    g.position.set(x, 0.66, 0);
    const up = cap(0.055, 0.24);
    up.position.y = -0.16;
    g.add(up);
    const fore = new THREE.Group();
    fore.position.y = -0.32;
    const low = cap(0.05, 0.24);
    low.position.y = -0.15;
    fore.add(low);
    g.add(fore);
    torso.add(g);
    return { g, fore };
  };
  const aa = arm(-0.27);
  const ab = arm(0.27);
  return { root, hips, torso, head, armA: aa.g, armB: ab.g, foreA: aa.fore, foreB: ab.fore, legA: la.g, legB: lb.g, kneeA: la.knee, kneeB: lb.knee };
}

// ---------- the concert ----------
interface Head {
  base: THREE.Vector3;
  fixture: THREE.Mesh;
  beam: THREE.Mesh;
  mat: THREE.ShaderMaterial;
  lens: THREE.Sprite;
  row: 'top' | 'back' | 'floor';
  i: number;
}

export class Concert {
  readonly renderer: THREE.WebGLRenderer;
  readonly scene = new THREE.Scene();
  readonly camera = new THREE.PerspectiveCamera(40, 16 / 9, 0.1, 600);
  private composer: EffectComposer;
  private bloom: UnrealBloomPass;
  private glow = glowTexture();
  private tmp = new THREE.Object3D();
  private v = new THREE.Vector3();
  private col = new THREE.Color();

  // stage
  private wallCanvas = document.createElement('canvas');
  private wallG: CanvasRenderingContext2D;
  private wallTex: THREE.CanvasTexture;
  private wallMat!: THREE.MeshBasicMaterial;
  private ledPattern!: CanvasPattern;
  private sideScreens: THREE.Mesh[] = [];
  private imagRT = new THREE.WebGLRenderTarget(640, 360, { colorSpace: THREE.SRGBColorSpace });
  private imagCam = new THREE.PerspectiveCamera(20, 16 / 9, 0.1, 200);
  private edgeStrip!: THREE.MeshBasicMaterial;
  private heads: Head[] = [];
  private backLights: THREE.SpotLight[] = [];
  private frontWash!: THREE.SpotLight;
  private followSpot!: THREE.SpotLight;
  private followBeam!: THREE.Mesh;
  private followMat!: THREE.ShaderMaterial;
  private hemi!: THREE.HemisphereLight;

  // band
  private singer!: Figure;
  private guitarist!: Figure;
  private bassist!: Figure;
  private drummer!: Figure;
  private keys!: Figure;
  private cymbals: THREE.Mesh[] = [];

  // effects
  private flames: { mesh: THREE.Mesh; mat: THREE.ShaderMaterial; x: number }[] = [];
  private jets: { mesh: THREE.Mesh; mat: THREE.ShaderMaterial; x: number }[] = [];
  private fireLights: THREE.PointLight[] = [];
  private sparks!: THREE.Points;
  private sparkPos!: Float32Array;
  private confetti!: THREE.InstancedMesh;
  private fw!: THREE.Points;
  private fwPos!: Float32Array;
  private fwCol!: Float32Array;

  // crowd
  private crowdN = 0;
  private crowd: { x: number; z: number; ph: number; amp: number; arms: number; h: number; rot: number }[] = [];
  private bodies!: THREE.InstancedMesh;
  private arms!: THREE.InstancedMesh;
  private phones!: THREE.Points;
  private phonePos!: Float32Array;
  private ringPts!: THREE.Points;

  constructor(parent: HTMLElement, preserve: boolean) {
    this.renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false, preserveDrawingBuffer: preserve });
    this.renderer.setPixelRatio(preserve ? 1 : Math.min(window.devicePixelRatio, 1.5));
    this.renderer.setSize(window.innerWidth, window.innerHeight);
    this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
    this.renderer.toneMappingExposure = 1.05;
    parent.appendChild(this.renderer.domElement);
    this.scene.background = new THREE.Color('#040407');
    this.scene.fog = new THREE.FogExp2('#07070c', 0.011);

    this.wallCanvas.width = 1280;
    this.wallCanvas.height = 720;
    this.wallG = this.wallCanvas.getContext('2d')!;
    this.wallTex = new THREE.CanvasTexture(this.wallCanvas);
    this.wallTex.colorSpace = THREE.SRGBColorSpace;
    {
      const p = document.createElement('canvas');
      p.width = p.height = 4;
      const g = p.getContext('2d')!;
      g.fillStyle = 'rgba(0,0,0,0.55)';
      g.fillRect(0, 3, 4, 1);
      g.fillRect(3, 0, 1, 4);
      this.ledPattern = this.wallG.createPattern(p, 'repeat')!;
    }

    this.buildStage();
    this.buildLights();
    this.buildBand();
    this.buildEffects();
    this.buildCrowd();

    this.composer = new EffectComposer(this.renderer);
    this.composer.addPass(new RenderPass(this.scene, this.camera));
    this.bloom = new UnrealBloomPass(new THREE.Vector2(window.innerWidth, window.innerHeight), 0.6, 0.5, 0.82);
    this.composer.addPass(this.bloom);
    this.composer.addPass(new OutputPass());
    this.resize();
  }

  resize(w = window.innerWidth, h = window.innerHeight) {
    this.renderer.setSize(w, h);
    this.composer.setSize(w, h);
    this.camera.aspect = w / h;
    this.camera.updateProjectionMatrix();
  }

  set visible(on: boolean) {
    this.renderer.domElement.style.visibility = on ? 'visible' : 'hidden';
  }

  // ---------- builders ----------
  private buildStage() {
    const s = this.scene;
    const dark = new THREE.MeshStandardMaterial({ color: '#111116', roughness: 0.85, metalness: 0.2 });
    const deckMat = new THREE.MeshStandardMaterial({ color: '#16161c', roughness: 0.32, metalness: 0.45 });
    // arena floor + stage deck + drum riser
    const floor = new THREE.Mesh(new THREE.PlaneGeometry(400, 400), new THREE.MeshStandardMaterial({ color: '#0a0a0e', roughness: 0.95 }));
    floor.rotation.x = -Math.PI / 2;
    s.add(floor);
    const deck = new THREE.Mesh(new THREE.BoxGeometry(28, STAGE_Y, 11), deckMat);
    deck.position.set(0, STAGE_Y / 2, -4.3);
    s.add(deck);
    const riser = new THREE.Mesh(new THREE.BoxGeometry(5.5, 0.7, 3.2), deckMat);
    riser.position.set(0, STAGE_Y + 0.35, -6.1);
    s.add(riser);
    const riser2 = new THREE.Mesh(new THREE.BoxGeometry(3.6, 0.45, 2.4), deckMat);
    riser2.position.set(7.6, STAGE_Y + 0.22, -5.4);
    s.add(riser2);
    // LED strip along the stage front edge
    this.edgeStrip = new THREE.MeshBasicMaterial({ color: '#ffcc00', toneMapped: false });
    const strip = new THREE.Mesh(new THREE.BoxGeometry(28, 0.06, 0.06), this.edgeStrip);
    strip.position.set(0, STAGE_Y - 0.05, 1.21);
    s.add(strip);
    // crowd barrier
    const barrier = new THREE.Mesh(new THREE.BoxGeometry(30, 1.1, 0.25), dark);
    barrier.position.set(0, 0.55, 3.1);
    s.add(barrier);
    // LED wall
    this.wallMat = new THREE.MeshBasicMaterial({ map: this.wallTex, toneMapped: false });
    const wall = new THREE.Mesh(new THREE.PlaneGeometry(21.3, 12), this.wallMat);
    wall.position.set(0, 8.4, -9.4);
    s.add(wall);
    const frame = new THREE.Mesh(new THREE.BoxGeometry(22, 12.7, 0.4), dark);
    frame.position.set(0, 8.4, -9.65);
    s.add(frame);
    // side screens with the live close-up
    for (const sx of [-1, 1]) {
      const m = new THREE.Mesh(new THREE.PlaneGeometry(7.2, 4.05), new THREE.MeshBasicMaterial({ map: this.imagRT.texture, toneMapped: false }));
      m.position.set(sx * 17.2, 9.2, -3.2);
      m.rotation.y = -sx * 0.38;
      s.add(m);
      this.sideScreens.push(m);
      const f = new THREE.Mesh(new THREE.BoxGeometry(7.7, 4.5, 0.3), dark);
      f.position.copy(m.position);
      f.rotation.y = m.rotation.y;
      f.translateZ(-0.2);
      s.add(f);
      // line-array speakers
      for (let k = 0; k < 9; k++) {
        const b = new THREE.Mesh(new THREE.BoxGeometry(1.5, 0.48, 1.1), dark);
        b.position.set(sx * 13.2, 14.6 - k * 0.5, 0.2);
        b.rotation.x = k * 0.035;
        s.add(b);
      }
    }
    // truss: front, back, towers
    const front = truss(30);
    front.position.set(-15, 14, -0.4);
    s.add(front);
    const back = truss(30);
    back.position.set(-15, 15, -8.6);
    s.add(back);
    for (const sx of [-1, 1]) {
      for (const z of [-0.4, -8.6]) {
        const tw = truss(15);
        tw.rotation.z = Math.PI / 2;
        tw.position.set(sx * 15, 0, z);
        s.add(tw);
      }
      const side = truss(8.2);
      side.rotation.y = Math.PI / 2;
      side.position.set(sx * 15, 14.5, -0.4);
      s.add(side);
    }
    // amps + monitors
    for (const x of [-5.6, -4.8, 4.8, 5.6]) {
      const a = new THREE.Mesh(new THREE.BoxGeometry(0.75, 1.3, 0.5), dark);
      a.position.set(x, STAGE_Y + 0.65, -4.4);
      s.add(a);
    }
    for (const x of [-4.6, -1.2, 1.2, 4.6]) {
      const mon = new THREE.Mesh(new THREE.BoxGeometry(0.9, 0.38, 0.6), dark);
      mon.position.set(x, STAGE_Y + 0.19, 0.4);
      mon.rotation.x = -0.45;
      s.add(mon);
    }
  }

  private buildLights() {
    const s = this.scene;
    this.hemi = new THREE.HemisphereLight('#8090c0', '#080810', 0.25);
    s.add(this.hemi);
    // back lights → rim light on the band
    for (const x of [-7, 0, 7]) {
      const l = new THREE.SpotLight('#ffffff', 0, 40, 0.55, 0.6, 1.2);
      l.position.set(x, 14, -9);
      l.target.position.set(x * 0.4, 2, -1);
      s.add(l, l.target);
      this.backLights.push(l);
    }
    this.frontWash = new THREE.SpotLight('#ffe3c0', 0, 60, 0.5, 0.7, 1.1);
    this.frontWash.position.set(0, 13.5, 8);
    this.frontWash.target.position.set(0, 2, -3);
    s.add(this.frontWash, this.frontWash.target);
    // follow spot from the front-of-house tower
    this.followSpot = new THREE.SpotLight('#fff6e8', 0, 90, 0.05, 0.35, 0.9);
    this.followSpot.position.set(0, 17, 48);
    this.followSpot.target.position.copy(SINGER).add(new THREE.Vector3(0, 1.4, 0));
    s.add(this.followSpot, this.followSpot.target);
    this.followMat = beamMaterial();
    const fg = new THREE.CylinderGeometry(0.12, 1.1, 1, 24, 1, true);
    fg.translate(0, -0.5, 0);
    fg.rotateX(-Math.PI / 2);
    this.followBeam = new THREE.Mesh(fg, this.followMat);
    s.add(this.followBeam);

    // moving heads
    const fixMat = new THREE.MeshStandardMaterial({ color: '#1b1b20', roughness: 0.5, metalness: 0.6 });
    const add = (row: Head['row'], x: number, y: number, z: number, i: number, spread: number) => {
      const fixture = new THREE.Mesh(new THREE.BoxGeometry(0.42, 0.5, 0.42), fixMat);
      fixture.position.set(x, y, z);
      s.add(fixture);
      const mat = beamMaterial();
      const beam = new THREE.Mesh(beamGeometry(spread), mat);
      beam.position.set(x, y, z);
      s.add(beam);
      const lens = new THREE.Sprite(new THREE.SpriteMaterial({ map: this.glow, color: '#ffffff', blending: THREE.AdditiveBlending, depthWrite: false, toneMapped: false }));
      lens.position.set(x, y, z);
      lens.scale.setScalar(1.1);
      s.add(lens);
      this.heads.push({ base: new THREE.Vector3(x, y, z), fixture, beam, mat, lens, row, i });
    };
    for (let i = 0; i < 11; i++) add('top', -12.5 + i * 2.5, 13.55, -0.4, i, 1.45);
    for (let i = 0; i < 8; i++) add('back', -12.25 + i * 3.5, 14.55, -8.6, i, 1.7);
    [-12.5, -9.5, 9.5, 12.5, -6.5, 6.5].forEach((x, i) => add('floor', x, STAGE_Y + 0.3, 0.7, i, 1.2));
  }

  private buildBand() {
    const s = this.scene;
    const mat = new THREE.MeshStandardMaterial({ color: '#0d0d11', roughness: 0.85, metalness: 0 });
    const inst = new THREE.MeshStandardMaterial({ color: '#2c2a2a', roughness: 0.35, metalness: 0.5 });
    const chrome = new THREE.MeshStandardMaterial({ color: '#bfc3c9', roughness: 0.2, metalness: 1 });
    // singer + mic stand
    this.singer = figure(mat, true);
    this.singer.root.position.copy(SINGER);
    s.add(this.singer.root);
    const pole = new THREE.Mesh(new THREE.CylinderGeometry(0.018, 0.018, 1.62, 8), chrome);
    pole.position.set(0, STAGE_Y + 0.81, -0.95);
    s.add(pole);
    const base = new THREE.Mesh(new THREE.CylinderGeometry(0.22, 0.25, 0.04, 16), chrome);
    base.position.set(0, STAGE_Y + 0.02, -0.95);
    s.add(base);
    const mic = new THREE.Mesh(new THREE.CapsuleGeometry(0.035, 0.12, 4, 8), chrome);
    mic.position.set(0, STAGE_Y + 1.66, -1.02);
    mic.rotation.x = 1.2;
    s.add(mic);
    // guitarist, bassist
    const axe = (bass: boolean) => {
      const g = new THREE.Group();
      const body = new THREE.Mesh(new THREE.BoxGeometry(bass ? 0.4 : 0.36, 0.34, 0.07), inst);
      g.add(body);
      const neck = new THREE.Mesh(new THREE.BoxGeometry(bass ? 0.95 : 0.72, 0.055, 0.04), inst);
      neck.position.set(-(bass ? 0.62 : 0.5), 0.05, 0);
      g.add(neck);
      g.position.set(0.02, 0.18, 0.2);
      g.rotation.z = 0.42;
      return g;
    };
    this.guitarist = figure(mat, true);
    this.guitarist.root.position.set(-5.2, STAGE_Y, -2.6);
    this.guitarist.root.rotation.y = 0.35;
    this.guitarist.torso.add(axe(false));
    s.add(this.guitarist.root);
    this.bassist = figure(mat);
    this.bassist.root.position.set(5.0, STAGE_Y, -2.9);
    this.bassist.root.rotation.y = -0.35;
    this.bassist.torso.add(axe(true));
    s.add(this.bassist.root);
    // drummer + kit
    this.drummer = figure(mat);
    this.drummer.root.position.set(0, STAGE_Y + 0.7, -6.6);
    this.drummer.hips.position.y = 0.62;
    this.drummer.legA.rotation.x = -1.45;
    this.drummer.legB.rotation.x = -1.45;
    this.drummer.kneeA.rotation.x = 1.45;
    this.drummer.kneeB.rotation.x = 1.45;
    s.add(this.drummer.root);
    const kitY = STAGE_Y + 0.7;
    const drum = (r: number, h: number, x: number, y: number, z: number, rx = 0) => {
      const m = new THREE.Mesh(new THREE.CylinderGeometry(r, r, h, 20), inst);
      m.position.set(x, kitY + y, z);
      m.rotation.x = rx;
      s.add(m);
    };
    drum(0.38, 0.5, 0, 0.38, -5.6, Math.PI / 2); // kick
    drum(0.2, 0.16, -0.45, 0.68, -5.95, 0.25); // snare
    drum(0.16, 0.18, -0.2, 0.92, -5.75, 0.5);
    drum(0.17, 0.2, 0.22, 0.92, -5.75, 0.5);
    drum(0.24, 0.42, 0.62, 0.42, -6.0); // floor tom
    for (const [x, y, z] of [
      [-0.8, 1.25, -5.8],
      [0.8, 1.3, -5.8],
      [-0.6, 0.95, -6.3],
    ]) {
      const c = new THREE.Mesh(new THREE.CylinderGeometry(0.32, 0.32, 0.015, 24), chrome);
      c.position.set(x, kitY + y, z);
      c.rotation.x = 0.35;
      s.add(c);
      this.cymbals.push(c);
    }
    // sticks
    for (const fore of [this.drummer.foreA, this.drummer.foreB]) {
      const st = new THREE.Mesh(new THREE.CylinderGeometry(0.012, 0.012, 0.42, 6), new THREE.MeshStandardMaterial({ color: '#c8b48a' }));
      st.position.set(0, -0.32, 0.12);
      st.rotation.x = 1.1;
      fore.add(st);
    }
    // keys
    this.keys = figure(mat, true);
    this.keys.root.position.set(7.6, STAGE_Y + 0.45, -5.9);
    this.keys.root.rotation.y = -0.5;
    s.add(this.keys.root);
    const kb = new THREE.Mesh(new THREE.BoxGeometry(1.25, 0.08, 0.4), inst);
    kb.position.set(7.35, STAGE_Y + 0.45 + 0.98, -5.45);
    kb.rotation.y = -0.5;
    s.add(kb);
  }

  private buildEffects() {
    const s = this.scene;
    // flame cannons along the stage front + on the towers
    for (const x of [-12, -9, 9, 12]) {
      const mat = flameMaterial('#fff2a8', '#ff3a00');
      const g = new THREE.CylinderGeometry(0.15, 0.55, 1, 16, 6, true);
      g.translate(0, 0.5, 0);
      const m = new THREE.Mesh(g, mat);
      m.position.set(x, STAGE_Y, 0.8);
      m.visible = false;
      s.add(m);
      this.flames.push({ mesh: m, mat, x });
    }
    for (const sx of [-1, 1]) {
      const l = new THREE.PointLight('#ff7a1a', 0, 40, 1.4);
      l.position.set(sx * 10, STAGE_Y + 3, 1.5);
      s.add(l);
      this.fireLights.push(l);
    }
    // CO2 jets
    for (const x of [-7.5, -3, 3, 7.5]) {
      const mat = flameMaterial('#ffffff', '#9fb3c8');
      const g = new THREE.CylinderGeometry(0.1, 1.1, 1, 16, 6, true);
      g.translate(0, 0.5, 0);
      const m = new THREE.Mesh(g, mat);
      m.position.set(x, STAGE_Y, 0.9);
      m.visible = false;
      s.add(m);
      this.jets.push({ mesh: m, mat, x });
    }
    // spark curtain from the front truss
    const NS = 1400;
    this.sparkPos = new Float32Array(NS * 3);
    const sg = new THREE.BufferGeometry();
    sg.setAttribute('position', new THREE.BufferAttribute(this.sparkPos, 3));
    this.sparks = new THREE.Points(sg, new THREE.PointsMaterial({ map: this.glow, color: '#ffd27a', size: 0.22, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, toneMapped: false }));
    this.sparks.visible = false;
    this.sparks.frustumCulled = false;
    s.add(this.sparks);
    // confetti
    const NC = 2200;
    this.confetti = new THREE.InstancedMesh(new THREE.PlaneGeometry(0.16, 0.1), new THREE.MeshBasicMaterial({ side: THREE.DoubleSide, toneMapped: false }), NC);
    const palette = ['#ffcc00', '#ffffff', '#003399', '#e3001b', '#ffd84d'].map((c) => new THREE.Color(c));
    for (let i = 0; i < NC; i++) this.confetti.setColorAt(i, palette[Math.floor(hash(i * 3.1) * palette.length)]);
    this.confetti.visible = false;
    this.confetti.frustumCulled = false;
    s.add(this.confetti);
    // fireworks (up to 10 bursts × 160 sparks)
    const NF = 10 * 160;
    this.fwPos = new Float32Array(NF * 3);
    this.fwCol = new Float32Array(NF * 3);
    const fg = new THREE.BufferGeometry();
    fg.setAttribute('position', new THREE.BufferAttribute(this.fwPos, 3));
    fg.setAttribute('color', new THREE.BufferAttribute(this.fwCol, 3));
    this.fw = new THREE.Points(fg, new THREE.PointsMaterial({ map: this.glow, size: 2.0, vertexColors: true, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, toneMapped: false, fog: false }));
    this.fw.visible = false;
    this.fw.frustumCulled = false;
    s.add(this.fw);
  }

  private buildCrowd() {
    const s = this.scene;
    // positions: dense in front of the stage, wider further back
    let i = 0;
    for (let z = 4.2; z < 50; z += 0.72) {
      const half = 13 + (z - 4) * 0.42;
      for (let x = -half; x < half; x += 0.68) {
        const jx = (hash(i * 1.7) - 0.5) * 0.45;
        const jz = (hash(i * 2.3) - 0.5) * 0.4;
        this.crowd.push({ x: x + jx, z: z + jz, ph: hash(i * 5.1) * 0.35, amp: 0.5 + hash(i * 7.7) * 0.7, arms: hash(i * 9.3), h: 0.9 + hash(i * 3.3) * 0.18, rot: (hash(i * 4.4) - 0.5) * 0.6 });
        i++;
      }
    }
    this.crowdN = this.crowd.length;
    const body = new THREE.CylinderGeometry(0.2, 0.17, 1.15, 7);
    body.translate(0, 0.95, 0);
    const legs = new THREE.CylinderGeometry(0.15, 0.11, 0.8, 6);
    legs.translate(0, 0.4, 0);
    const head = new THREE.SphereGeometry(0.135, 8, 6);
    head.translate(0, 1.66, 0);
    const person = mergeGeometries([body, legs, head])!;
    const cmat = new THREE.MeshStandardMaterial({ color: '#141418', roughness: 0.9 });
    this.bodies = new THREE.InstancedMesh(person, cmat, this.crowdN);
    this.bodies.frustumCulled = false;
    s.add(this.bodies);
    const arm = new THREE.CylinderGeometry(0.045, 0.05, 0.7, 5);
    arm.translate(0, 0.35, 0);
    this.arms = new THREE.InstancedMesh(arm, cmat, this.crowdN * 2);
    this.arms.frustumCulled = false;
    s.add(this.arms);
    this.phonePos = new Float32Array(this.crowdN * 3);
    const pg = new THREE.BufferGeometry();
    pg.setAttribute('position', new THREE.BufferAttribute(this.phonePos, 3));
    this.phones = new THREE.Points(pg, new THREE.PointsMaterial({ map: this.glow, color: '#dfe8ff', size: 0.32, transparent: true, opacity: 0, depthWrite: false, blending: THREE.AdditiveBlending, toneMapped: false }));
    this.phones.frustumCulled = false;
    s.add(this.phones);
    // 12 stars of phone lights over the crowd (seen from above at the end)
    const rp: number[] = [];
    for (let k = 0; k < 12; k++) {
      const a = (k / 12) * Math.PI * 2 - Math.PI / 2;
      const cx = Math.cos(a) * 11;
      const cz = 24 + Math.sin(a) * 11;
      for (let j = 0; j < 90; j++) {
        // points on the star outline and inside
        const seg = Math.floor(hash(k * 100 + j) * 10);
        const f = hash(k * 100 + j + 0.5);
        const r0 = seg % 2 ? 0.9 : 2.2;
        const r1 = seg % 2 ? 2.2 : 0.9;
        const b0 = (seg / 10) * Math.PI * 2 - Math.PI / 2;
        const b1 = ((seg + 1) / 10) * Math.PI * 2 - Math.PI / 2;
        const inner = j % 3 === 0 ? hash(j * 7 + k) * 0.8 : 1;
        const px = (Math.cos(b0) * r0 * (1 - f) + Math.cos(b1) * r1 * f) * inner;
        const pz = (Math.sin(b0) * r0 * (1 - f) + Math.sin(b1) * r1 * f) * inner;
        rp.push(cx + px, 2.25, cz + pz);
      }
    }
    const rg = new THREE.BufferGeometry();
    rg.setAttribute('position', new THREE.Float32BufferAttribute(rp, 3));
    this.ringPts = new THREE.Points(rg, new THREE.PointsMaterial({ map: this.glow, color: '#ffd84d', size: 0.55, transparent: true, opacity: 0, depthWrite: false, blending: THREE.AdditiveBlending, toneMapped: false }));
    s.add(this.ringPts);
  }

  // ---------- per frame ----------
  update(c: ConcertCtx) {
    const { t, look } = c;
    const energy = look.energy;
    const black = look.blackout ?? 0;
    const live = 1 - black;

    // LED wall
    const g = this.wallG;
    const W = this.wallCanvas.width;
    const H = this.wallCanvas.height;
    g.save();
    g.fillStyle = '#000';
    g.fillRect(0, 0, W, H);
    c.drawWall(g, W, H);
    g.restore();
    g.fillStyle = this.ledPattern;
    g.fillRect(0, 0, W, H);
    this.wallTex.needsUpdate = true;
    const wb = (look.wallBright ?? 1) * (0.85 + 0.15 * c.pulse) * (1 - black * 0.85);
    this.wallMat.color.setScalar(wb);

    // stage lights
    const wash = this.col.set(look.wash);
    this.backLights.forEach((l, i) => {
      l.color.copy(wash);
      l.intensity = (260 + 220 * energy) * (0.75 + 0.25 * c.pulse) * live * (1 + c.hit * 0.8) * (i === 1 ? 1.2 : 1);
    });
    this.frontWash.intensity = (22 + 22 * energy) * live;
    const follow = (look.follow ?? 0) * live;
    this.followSpot.intensity = 170 * follow;
    this.followSpot.target.position.set(SINGER.x + Math.sin(t * 0.7) * 0.06, SINGER.y + 1.3, SINGER.z);
    {
      const from = this.followSpot.position;
      const to = this.followSpot.target.position;
      this.followBeam.position.copy(from);
      this.followBeam.lookAt(to);
      const d = from.distanceTo(to);
      this.followBeam.scale.set(1, 1, d);
      this.followMat.uniforms.intensity.value = 0.05 * follow;
      this.followMat.uniforms.color.value.set('#fff2dc');
      this.followBeam.visible = follow > 0.01 && (c.shot === 'wide' || c.shot === 'crane' || c.shot === 'crowd' || c.shot === 'top');
    }
    this.edgeStrip.color.set(look.beams[0] ?? '#ffcc00').multiplyScalar((0.5 + 0.8 * c.pulse) * live + 0.05);
    this.hemi.intensity = 0.14 + 0.2 * c.hit;

    this.updateHeads(c);
    this.updateBand(c);
    this.updateEffects(c);
    this.updateCamera(c);
    this.updateCrowd(c);

    // live close-up for the side screens
    const sway = Math.sin(t * 0.9) * 0.08;
    this.imagCam.position.set(0.5 + sway, SINGER.y + 1.75, 2.6);
    this.imagCam.lookAt(SINGER.x, SINGER.y + 1.62, SINGER.z);
    this.sideScreens.forEach((m) => (m.visible = false));
    this.renderer.setRenderTarget(this.imagRT);
    this.renderer.render(this.scene, this.imagCam);
    this.renderer.setRenderTarget(null);
    this.sideScreens.forEach((m) => {
      m.visible = true;
      (m.material as THREE.MeshBasicMaterial).color.setScalar(0.9 * (1 - black * 0.9));
    });

    this.bloom.strength = 0.5 + 0.25 * energy + c.hit * 0.3;
    this.composer.render();
  }

  private updateHeads(c: ConcertCtx) {
    const { t, look, beat } = c;
    const energy = look.energy;
    const live = 1 - (look.blackout ?? 0);
    const pattern = look.pattern ?? 'sweep';
    const speed = 0.35 + energy * 0.9;
    const shotDim = ({ wall: 0.35, pit: 0.55, singer: 0.4, orbit: 0.55, wing: 0.55, guitar: 0.6, bass: 0.6, keys: 0.6 } as Partial<Record<Shot, number>>)[c.shot] ?? 1;
    const strobe = look.strobe && c.hit > 0.15 ? (Math.floor(t * 24) % 2 === 0 ? 1.6 : 0.15) : 1;
    for (const h of this.heads) {
      const n = h.i;
      const side = h.base.x < 0 ? -1 : 1;
      let tx = 0;
      let ty = 0;
      let tz = 0;
      if (h.row === 'floor') {
        // floor heads shoot up into the air in a fan
        const sw = Math.sin(t * speed * 1.3 + n * 0.9);
        tx = h.base.x + sw * 8 + side * 4;
        ty = 40;
        tz = h.base.z + 6 + Math.cos(t * speed + n) * 6;
      } else if (pattern === 'crowd' || pattern === 'chase') {
        // beams sweep over the audience
        const ph = pattern === 'chase' ? Math.floor(beat) * 0.7 + n * 1.3 : t * speed + n * 0.7;
        tx = Math.sin(ph) * 22;
        ty = 0;
        tz = 16 + Math.cos(ph * 0.8 + n) * 12;
      } else if (pattern === 'up') {
        tx = h.base.x * 1.6 + Math.sin(t * speed + n) * 3;
        ty = 60;
        tz = h.base.z + 14;
      } else if (pattern === 'fan') {
        // symmetric fan that opens and closes on the beat
        const open = 0.5 + 0.5 * Math.sin(beat * Math.PI * 0.5);
        tx = (h.base.x / 12.5) * (6 + open * 22);
        ty = 0;
        tz = 8 + open * 18;
      } else if (pattern === 'still') {
        tx = h.base.x * 0.4;
        ty = 0;
        tz = 6;
      } else {
        const sw = Math.sin(t * speed + n * 0.55);
        tx = h.base.x + sw * 14;
        ty = 0;
        tz = 10 + Math.cos(t * speed * 0.7 + n * 0.8) * 9;
      }
      if (h.row === 'back') tz -= 2;
      this.v.set(tx, ty, tz);
      h.beam.lookAt(this.v);
      h.fixture.lookAt(this.v);
      const colr = look.beams[(n + (h.row === 'back' ? 1 : 0)) % look.beams.length];
      h.mat.uniforms.color.value.set(colr);
      const chaseOn = pattern === 'chase' ? (Math.floor(beat * 2) % 4 === n % 4 ? 1 : 0.15) : 1;
      const base = h.row === 'floor' ? 0.2 + energy * 0.3 : 0.15 + energy * 0.24;
      const inten = base * (0.8 + 0.35 * c.pulse) * strobe * chaseOn * live * shotDim;
      h.mat.uniforms.intensity.value = inten;
      h.beam.visible = inten > 0.01;
      (h.lens.material as THREE.SpriteMaterial).color.set(colr).multiplyScalar(Math.min(2, inten * 3));
      h.lens.visible = inten > 0.01;
    }
  }

  private updateBand(c: ConcertCtx) {
    const { t, beat, pulse, perf, look } = c;
    const e = look.energy;
    const bow = perf.bow ?? 0;
    const bp = beat - Math.floor(beat);
    const nod = Math.sin(bp * Math.PI) * (0.1 + 0.25 * e);
    // singer
    const S = this.singer;
    const singLean = perf.sing * 0.12;
    S.torso.rotation.x = singLean + bow * 0.9;
    S.head.rotation.x = perf.sing * 0.12 - nod * 0.4;
    S.hips.position.y = 0.98 - Math.sin(bp * Math.PI) * 0.025 * e;
    S.root.rotation.y = Math.sin(t * 0.37) * 0.25 * (1 - perf.sing * 0.6);
    // right hand on the mic, left free
    S.armA.rotation.set(-1.35 + perf.sing * -0.15 + bow * 1.2, 0, -0.35);
    S.foreA.rotation.set(-1.25, 0, 0);
    const hey = perf.hey * (0.75 + 0.25 * Math.sin(bp * Math.PI));
    const heldOut = perf.held;
    S.armB.rotation.set(-hey * 2.9 - heldOut * 0.5, 0, 0.25 + heldOut * 1.25 + (1 - hey) * Math.sin(t * 1.3) * 0.08);
    S.foreB.rotation.set(-0.3 * (1 - hey) - heldOut * 0.2, 0, 0);
    S.legA.rotation.x = 0.05;
    S.legB.rotation.x = -0.12;
    // guitarist + bassist: headbang + strum
    const strum = Math.sin(beat * Math.PI * 4);
    for (const [F, ph] of [
      [this.guitarist, 0],
      [this.bassist, 0.5],
    ] as const) {
      const bang = Math.sin((bp + ph * 0.1) * Math.PI) * (0.15 + 0.45 * e);
      F.torso.rotation.x = 0.12 + bang * 0.35 + bow * 0.9;
      F.head.rotation.x = bang * 0.8;
      F.hips.position.y = 0.92 - bang * 0.05;
      F.legA.rotation.set(0.2, 0, -0.18);
      F.legB.rotation.set(-0.2, 0, 0.18);
      F.kneeA.rotation.x = 0.15;
      F.kneeB.rotation.x = 0.15;
      F.armA.rotation.set(-0.75, 0, -0.95); // fretting hand along the neck
      F.foreA.rotation.set(-0.9, 0, 0);
      F.armB.rotation.set(-0.45 + strum * 0.22 * (0.4 + e), 0, 0.15);
      F.foreB.rotation.set(-1.1 + strum * 0.3 * (0.4 + e), 0, 0);
    }
    // drummer
    const D = this.drummer;
    const eighth = beat * 2;
    const ep = eighth - Math.floor(eighth);
    const snare = Math.floor(beat) % 2 === 1 ? Math.exp(-bp * 8) : 0;
    D.armA.rotation.set(-0.95 - Math.exp(-ep * 6) * 0.55 * (0.3 + e) + 0.3, 0, -0.35);
    D.foreA.rotation.set(-0.7, 0, 0);
    D.armB.rotation.set(-0.85 - snare * 0.7 - c.hit * 0.8, 0, 0.35);
    D.foreB.rotation.set(-0.6, 0, 0);
    D.head.rotation.x = nod * 0.8;
    D.torso.rotation.x = 0.1 + nod * 0.2;
    this.cymbals.forEach((cy, i) => {
      cy.rotation.x = 0.35 + Math.sin(t * 30 + i) * 0.12 * c.hit + (i === 2 ? Math.exp(-ep * 10) * 0.05 : 0);
    });
    // keys
    const K = this.keys;
    K.armA.rotation.set(-1.0, 0, -0.15);
    K.armB.rotation.set(-1.0 + Math.sin(t * 6) * 0.06, 0, 0.15);
    K.foreA.rotation.set(-0.6 + Math.sin(beat * Math.PI) * 0.08, 0, 0);
    K.foreB.rotation.set(-0.6, 0, 0);
    K.head.rotation.x = nod * 0.6;
    K.torso.rotation.x = 0.15 + bow * 0.8;
    void pulse;
  }

  private updateEffects(c: ConcertCtx) {
    const { t, look } = c;
    // flames on big hits
    const fireOn = look.pyro ? c.pyro : 0;
    this.flames.forEach((f, i) => {
      const a = fireOn * (0.85 + 0.15 * Math.sin(t * 40 + i));
      f.mesh.visible = a > 0.02;
      f.mesh.scale.set(1 + a * 0.5, 1 + a * (6 + (i % 2) * 1.5), 1 + a * 0.5);
      f.mat.uniforms.amount.value = Math.min(1, a * 1.4);
      f.mat.uniforms.time.value = t;
    });
    this.fireLights.forEach((l) => (l.intensity = fireOn * 900));
    // CO2 jets
    let jet = 0;
    for (const at of look.co2 ?? []) {
      const d = t - at;
      if (d >= 0 && d < 2.2) jet = Math.max(jet, d < 0.15 ? d / 0.15 : Math.exp(-(d - 0.15) * 1.8));
    }
    this.jets.forEach((j, i) => {
      j.mesh.visible = jet > 0.02;
      j.mesh.scale.set(1 + jet * 1.2, 1 + jet * 9, 1 + jet * 1.2);
      j.mat.uniforms.amount.value = jet * 0.55;
      j.mat.uniforms.time.value = t + i;
    });
    // spark curtain
    const sp = look.sparks;
    let spk = 0;
    if (sp) spk = clamp((t - sp[0]) / 0.4) * clamp((sp[1] - t) / 0.6);
    this.sparks.visible = spk > 0.01;
    if (this.sparks.visible) {
      const n = this.sparkPos.length / 3;
      for (let i = 0; i < n; i++) {
        const ph = (t * (0.55 + hash(i) * 0.25) + hash(i * 3.3)) % 1;
        const x = -14 + hash(i * 1.9) * 28;
        this.sparkPos[i * 3] = x + Math.sin(ph * 9 + i) * 0.08;
        this.sparkPos[i * 3 + 1] = 13.6 - ph * ph * 12.2;
        this.sparkPos[i * 3 + 2] = -0.2 + hash(i * 2.7) * 0.5 + ph * 0.6;
      }
      this.sparks.geometry.attributes.position.needsUpdate = true;
      (this.sparks.material as THREE.PointsMaterial).opacity = spk;
    }
    // confetti
    const ct = look.confetti;
    const cd = ct === undefined ? -1 : t - ct;
    this.confetti.visible = cd >= 0 && cd < 22;
    if (this.confetti.visible) {
      const n = this.confetti.count;
      for (let i = 0; i < n; i++) {
        const side = i % 2 ? 1 : -1;
        const burst = 1 - Math.exp(-cd * 3.2);
        const vx = side * (2 + hash(i * 1.3) * 14) * (hash(i * 8.1) < 0.3 ? -0.6 : 1);
        const vy = 14 + hash(i * 2.1) * 12;
        const vz = 3 + hash(i * 3.7) * 22;
        const fall = Math.max(0, cd - 0.6) * (0.9 + hash(i * 4.9) * 0.7);
        const y = STAGE_Y + 0.5 + vy * burst - fall;
        this.tmp.position.set(side * 8 + vx * burst + Math.sin(cd * 1.7 + i) * 0.7, y, 1 + vz * burst + Math.cos(cd * 1.3 + i) * 0.5);
        this.tmp.rotation.set(cd * (2 + hash(i) * 6) + i, cd * (1 + hash(i * 6) * 4), i);
        this.tmp.scale.setScalar(y > 0.05 ? 1 : 0);
        this.tmp.updateMatrix();
        this.confetti.setMatrixAt(i, this.tmp.matrix);
      }
      this.confetti.instanceMatrix.needsUpdate = true;
    }
    // fireworks
    // up to 10 bursts that are visible right now (positions depend on the burst time → stable)
    const bursts = (look.fireworks ?? []).filter((b) => t >= b && t < b + 3.2).slice(0, 10);
    this.fw.visible = bursts.length > 0;
    if (this.fw.visible) {
      const per = 160;
      const cols = ['#ffcc00', '#ffffff', '#3d6bff', '#ff2a3a', '#ffd84d'];
      for (let k = 0; k < 10; k++) {
        const b = bursts[k];
        const d = b === undefined ? -1 : t - b;
        const on = d >= 0 && d < 3.2;
        const sd = b === undefined ? k : Math.round(b * 100);
        const cx = (hash(sd * 5.5) - 0.5) * 50;
        const cy = 24 + hash(sd * 6.6) * 12;
        const cz = -24 - hash(sd * 7.7) * 10;
        this.col.set(cols[sd % cols.length]);
        const fade = on ? Math.pow(1 - d / 3.2, 1.6) * (d < 0.08 ? d / 0.08 : 1) : 0;
        for (let j = 0; j < per; j++) {
          const idx = (k * per + j) * 3;
          // directions on a sphere
          const u = hash(sd * 1000 + j * 1.1) * 2 - 1;
          const ph = hash(sd * 1000 + j * 2.3) * Math.PI * 2;
          const r = Math.sqrt(1 - u * u);
          const sp2 = 9 + hash(sd * 1000 + j * 3.7) * 2;
          const ex = (1 - Math.exp(-Math.max(0, d) * 2.4)) * sp2;
          this.fwPos[idx] = cx + r * Math.cos(ph) * ex;
          this.fwPos[idx + 1] = cy + u * ex - 1.4 * Math.max(0, d) * Math.max(0, d);
          this.fwPos[idx + 2] = cz + r * Math.sin(ph) * ex;
          const tw = 0.7 + 0.3 * Math.sin(t * 40 + j);
          this.fwCol[idx] = this.col.r * fade * tw;
          this.fwCol[idx + 1] = this.col.g * fade * tw;
          this.fwCol[idx + 2] = this.col.b * fade * tw;
        }
      }
      this.fw.geometry.attributes.position.needsUpdate = true;
      this.fw.geometry.attributes.color.needsUpdate = true;
    }
  }

  private updateCrowd(c: ConcertCtx) {
    const { beat, look, t } = c;
    const e = look.energy;
    const phones = look.phones ?? 0;
    const armsUp = 0.15 + e * 0.6 + c.perf.hey * 0.25;
    for (let i = 0; i < this.crowdN; i++) {
      const p = this.crowd[i];
      const near = clamp(1 - (p.z - 4) / 40);
      const b = beat + p.ph;
      const jump = Math.max(0, Math.sin((b - Math.floor(b)) * Math.PI)) * p.amp * e * (0.18 + 0.22 * near);
      const sway = Math.sin(t * 1.1 + p.ph * 20) * (1 - e) * 0.06;
      this.tmp.position.set(p.x + sway, jump, p.z);
      this.tmp.rotation.set(0, Math.PI + p.rot, sway);
      this.tmp.scale.set(1, p.h, 1);
      this.tmp.updateMatrix();
      this.bodies.setMatrixAt(i, this.tmp.matrix);
      const up = p.arms < armsUp;
      const wave = Math.sin(b * Math.PI) * 0.25;
      const shoulderY = jump + 1.42 * p.h;
      for (let k = 0; k < 2; k++) {
        const sx = k ? 0.2 : -0.2;
        const both = k === 1 || p.arms < armsUp * 0.55;
        this.tmp.position.set(p.x + sx + sway, shoulderY, p.z);
        if (up && both) this.tmp.rotation.set(0.15, 0, (k ? -1 : 1) * (0.25 + wave * (k ? 1 : -1)));
        else this.tmp.rotation.set(0, 0, (k ? -1 : 1) * 2.9);
        this.tmp.scale.setScalar(1);
        this.tmp.updateMatrix();
        this.arms.setMatrixAt(i * 2 + k, this.tmp.matrix);
      }
      // phone in the raised right hand
      const cdx = p.x - this.camera.position.x;
      const cdz = p.z - this.camera.position.z;
      const phoneOn = phones > 0 && hash(i * 11.3) < phones * 0.9 && cdx * cdx + cdz * cdz > 36;
      this.phonePos[i * 3] = p.x + 0.35 + sway;
      this.phonePos[i * 3 + 1] = phoneOn ? shoulderY + 0.66 : -10;
      this.phonePos[i * 3 + 2] = p.z;
    }
    this.bodies.instanceMatrix.needsUpdate = true;
    this.arms.instanceMatrix.needsUpdate = true;
    this.phones.geometry.attributes.position.needsUpdate = true;
    (this.phones.material as THREE.PointsMaterial).opacity = phones > 0 ? Math.min(1, phones * 1.5) * (1 - (look.ring ?? 0) * 0.7) : 0;
    const ring = look.ring ?? 0;
    (this.ringPts.material as THREE.PointsMaterial).opacity = ring * (0.85 + 0.15 * c.pulse);
    this.ringPts.visible = ring > 0.01;
  }

  private updateCamera(c: ConcertCtx) {
    const { t, local, u, seed } = c;
    const cam = this.camera;
    const s = seed;
    const hand = (amt: number) => {
      cam.position.x += (Math.sin(t * 1.3 + s) * 0.6 + Math.sin(t * 2.9 + s * 2) * 0.3) * amt;
      cam.position.y += (Math.sin(t * 1.7 + s * 3) * 0.5 + Math.sin(t * 3.7) * 0.2) * amt;
    };
    const look = (x: number, y: number, z: number) => cam.lookAt(x, y, z);
    const side = hash(s) < 0.5 ? -1 : 1;
    const k = easeInOut(u);
    let fov = 40;
    switch (c.shot) {
      case 'wide':
        cam.position.set(side * (4 - k * 8), 9.5 - k * 1.2, 46 - k * 6);
        hand(0.08);
        look(0, (c.look.fireworks?.length ?? 0) > 0 ? 11 : 6.2, -4);
        fov = (c.look.fireworks?.length ?? 0) > 0 ? 50 : 42;
        break;
      case 'crowd':
        cam.position.set(side * 2.5 + (k - 0.5) * 2.5, 2.25 + Math.sin(c.beat * Math.PI) * 0.06, 15 - k * 2);
        hand(0.12);
        look(0, 6, -6);
        fov = 46;
        break;
      case 'singer': {
        const a = side * (0.25 - k * 0.5);
        cam.position.set(SINGER.x + Math.sin(a) * 4.4, SINGER.y + 1.3, SINGER.z + Math.cos(a) * 4.4);
        hand(0.05);
        look(SINGER.x, SINGER.y + 1.65, SINGER.z);
        fov = 30;
        break;
      }
      case 'pit':
        cam.position.set(side * (1.6 - k * 3.2), 1.3, 3.6);
        hand(0.04);
        look(0, 5.2, -6);
        fov = 52;
        break;
      case 'wing':
        cam.position.set(side * 11, 3.3, -3.4 + k * 1.5);
        hand(0.05);
        look(SINGER.x, SINGER.y + 1.5, SINGER.z + 2);
        fov = 36;
        break;
      case 'drums':
        cam.position.set(0.6 + (k - 0.5) * 1.6, STAGE_Y + 3.0, -8.4);
        hand(0.04);
        look(0, 3.2, 12);
        fov = 54;
        break;
      case 'guitar':
        cam.position.set(-5.2 + 2.3 + k * 0.8, STAGE_Y + 1.3, -2.6 + 3.2);
        hand(0.05);
        look(-5.2, STAGE_Y + 1.4, -2.6);
        fov = 32;
        break;
      case 'bass':
        cam.position.set(5 - 2.3 - k * 0.8, STAGE_Y + 1.3, -2.9 + 3.2);
        hand(0.05);
        look(5, STAGE_Y + 1.4, -2.9);
        fov = 32;
        break;
      case 'keys':
        cam.position.set(7.6 - 1.2, STAGE_Y + 2.4, -5.9 + 2.8);
        hand(0.04);
        look(7.5, STAGE_Y + 1.6, -5.7);
        fov = 34;
        break;
      case 'crane': {
        const a = side * (-0.9 + k * 1.8);
        cam.position.set(Math.sin(a) * 30, 16 - Math.sin(k * Math.PI) * 4, 4 + Math.cos(a) * 30);
        look(0, 4.5, -3);
        fov = 44;
        break;
      }
      case 'wall':
        cam.position.set(side * 1.2 * (1 - k), 6.4, 21 - k * 2.5);
        hand(0.04);
        look(0, 7.6, -9);
        fov = 38;
        break;
      case 'top':
        cam.position.set(0, 46 - k * 6, 26);
        cam.up.set(0, 0, -1);
        look(0, 0, 23);
        fov = 50;
        break;
      case 'orbit': {
        const a = side * (-0.7 + Math.min(1.4, local * 0.16));
        cam.position.set(SINGER.x + Math.sin(a) * 6, SINGER.y + 2.1, SINGER.z + Math.cos(a) * 6);
        look(SINGER.x, SINGER.y + 1.4, SINGER.z);
        fov = 38;
        break;
      }
    }
    if (c.shot !== 'top') cam.up.set(0, 1, 0);
    // tiny kick on riff hits
    cam.position.y += c.hit * 0.05 * Math.sin(t * 90);
    if (cam.fov !== fov) {
      cam.fov = fov;
      cam.updateProjectionMatrix();
    }
  }
}
