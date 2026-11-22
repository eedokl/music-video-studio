// The city of gates, built once and drawable in the manner of five eras. The last hook flies through it in full
// light ("Bot prüft Bot"); in the instrumental after it the same city loses one era every two bars.
//   style 'pbr'  lit, shadows, glowing windows        'tex'  painted textures, no real light (1998)
//         'flat' shaded faces without textures (1993) 'pix'  the same in fat pixels and four levels (1983)
//         'wire' only the edges (1974)
import * as THREE from 'three';
import { boxEdges, canvasTex, clamp, hash, lines, over } from './kit.js';
import { BEAT, STEP, V } from './song.js';

// what the lit city looks like after the picture is developed (shared by the worlds that show it)
export const CITY_LOOK = { bloom: 0.32, threshold: 1.15, tone: 1, exposure: 0.95 };

const GREEN = 0x2bff88;
const FLAT_PAL = [0x8a4fb0, 0xc0508c, 0x5a56c8, 0x7f8fb8, 0x4a86c8];
const PIX_PAL = [0x00c8ff, 0xff3df0, 0xffe14a, 0x35e06a, 0xff7a1a];
const BG = { pbr: 0x030a07, tex: 0x05060a, flat: 0x3b2360, pix: 0x0c0c5c, wire: 0x000000 };

export function buildCity(scene, { L, beats, seed = 0, clear = [], bridges = () => true, levels = null }) {
  const len = L + 80;
  const cleared = (z) => clear.some(([a, b]) => z <= a && z >= b); // stretches of road kept free: [zNear, zFar]
  scene.background = new THREE.Color(BG.pbr);
  scene.fog = new THREE.Fog(BG.pbr, 50, 400);
  const hemi = new THREE.HemisphereLight(0xa8ffd0, 0x06100a, 0.8);
  const key = new THREE.DirectionalLight(0xeafff2, 2.2);
  key.shadow.mapSize.set(2048, 2048);
  Object.assign(key.shadow.camera, { left: -34, right: 34, top: 34, bottom: -34, near: 1, far: 110 });
  key.shadow.bias = -0.002;
  scene.add(hemi, key, key.target);

  // ---- what stands there: towers left and right, a gate across the road every four beats
  const towers = [], gateParts = [], neon = [], roofs = [];
  for (let k = 1; k <= beats + 14; k++) {
    for (const side of [-1, 1]) {
      const n = seed + k * 13 + side * 3;
      const w = 3 + hash(n) * 2.6, h = 4 + hash(n + 1) * 15, x = side * (8.4 + hash(n + 2) * 4.5), z = -k * STEP;
      // the districts beyond the two rows at the road: fewer, far taller, out to the horizon (seen from above)
      if (k % 2 === 0) for (let r = 0; r < 3; r++) {
        const m = n + 40 + r * 7, x3 = side * (34 + r * 24 + hash(m) * 14), h3 = 16 + hash(m + 1) ** 2 * 78, w3 = 6 + hash(m + 2) * 6;
        towers.push([x3, h3 / 2, z - r, w3, h3, 4.6]);
        roofs.push([x3, h3 + 0.1, z - r, w3 * 0.97, 0.2, 4.45]);
        if (h3 > 48) towers.push([x3, h3 + 3, z - r, w3 * 0.5, 6, 2.6]), neon.push([x3, h3 + 13, z - r, 0.3, 14, 0.3]);
      }
      if (cleared(z)) continue;
      towers.push([x, h / 2, z, w, h, 2.3]);
      // a building is more than a box: a narrower upper storey, a roof edge, something on the roof
      const kind = hash(n + 9);
      let top = h;
      if (kind > 0.3) {
        const h1 = 2 + hash(n + 10) * 6;
        towers.push([x, top + h1 / 2, z, w * 0.68, h1, 1.7]);
        top += h1;
        if (kind > 0.7) towers.push([x, top + 1.2, z, w * 0.4, 2.4, 1.1]), (top += 2.4);
      } else towers.push([x, top + 0.12, z, w + 0.35, 0.24, 2.65]); // a roof slab that juts out
      // what a roof looks like from above: a dark deck, a box or two of machinery
      const rw = kind > 0.7 ? w * 0.4 : kind > 0.3 ? w * 0.68 : w + 0.3, rd = kind > 0.7 ? 1.1 : kind > 0.3 ? 1.7 : 2.6;
      roofs.push([x, top + 0.3, z, rw * 0.97, 0.12, rd * 0.97]);
      if (hash(n + 20) > 0.4) roofs.push([x + (hash(n + 21) - 0.5) * rw * 0.5, top + 0.7, z, 0.7, 0.7, 0.6]);
      if (hash(n + 11) > 0.5) neon.push([x + (hash(n + 12) - 0.5) * w * 0.4, top + 1.6 + hash(n + 13) * 2, z, 0.07, 3.2 + hash(n + 13) * 4, 0.07]); // antenna
      if (hash(n + 14) > 0.6) neon.push([x - side * (w / 2 + 0.04), h / 2, z + 1.19, 0.09, h, 0.09]); // a strip of light up the corner
      if (k % 2 === 0) {
        const h2 = 12 + hash(n + 5) * 26, x2 = side * (18 + hash(n + 6) * 9);
        towers.push([x2, h2 / 2, z - 1, 4.5, h2, 3.2]);
        towers.push([x2, h2 + 1.5, z - 1, 3.2, 3, 2.3], [x2, h2 + 4, z - 1, 1.8, 2, 1.4]); // a stepped crown
        roofs.push([x2, h2 + 0.08, z - 1, 4.4, 0.16, 3.1], [x2, h2 + 5.06, z - 1, 1.75, 0.12, 1.35]);
        neon.push([x2, h2 + 7.5, z - 1, 0.1, 5, 0.1]);
      }
    }
    // a bridge between the towers, high above the road, every eight beats
    if (k % 8 === 6 && k < beats - 4 && bridges(k) && !cleared(-k * STEP)) towers.push([0, 13.2 + hash(seed + k) * 4, -k * STEP, 19, 1.3, 1.9]);
    // cross streets: from above the city is a grid of light
    if (k % 4 === 2) neon.push([0, 0.03, -k * STEP, 260, 0.02, 0.24]);
    if (k % 4 === 0 && k < beats - 1 && !cleared(-k * STEP)) {
      gateParts.push([-5.2, 3.2, -k * STEP, 0.3, 6.4, 0.3], [5.2, 3.2, -k * STEP, 0.3, 6.4, 0.3], [0, 6.55, -k * STEP, 10.7, 0.3, 0.3]);
    }
  }
  const unit = new THREE.BoxGeometry(1, 1, 1);
  const dummy = new THREE.Object3D();
  const inst = (list, mat) => {
    const m = new THREE.InstancedMesh(unit, mat, list.length);
    list.forEach(([x, y, z, w, h, d], i) => {
      dummy.position.set(x, y, z), dummy.scale.set(w, h, d), dummy.rotation.set(0, 0, 0), dummy.updateMatrix();
      m.setMatrixAt(i, dummy.matrix);
    });
    m.frustumCulled = false;
    scene.add(m);
    return m;
  };

  for (const x of [-16, 16, -30, 30, -54, 54, -78, 78]) neon.push([x, 0.03, -len / 2, 0.24, 0.02, len]); // avenues
  gateParts.push(...neon);
  const windows = canvasTex(64, 128, (g) => {
    g.fillStyle = '#0a120e', g.fillRect(0, 0, 64, 128);
    for (let y = 0; y < 31; y++) for (let x = 0; x < 10; x++) {
      const r = hash(x * 7.1 + y * 3.3), floorLit = hash(y * 1.7) > 0.25; // whole floors are dark, as in a real tower
      if (r > 0.42 && floorLit) g.fillStyle = r > 0.92 ? '#ffffff' : r > 0.72 ? '#59d0ff' : r > 0.5 ? '#2bff88' : '#12804a', g.fillRect(2 + x * 6, 2 + y * 4, 4, 2);
    }
  }, { pixel: true });
  const tile = canvasTex(32, 32, (g) => {
    g.fillStyle = '#39424c', g.fillRect(0, 0, 32, 32);
    g.fillStyle = '#1c2228', g.fillRect(0, 0, 32, 2), g.fillRect(0, 0, 2, 32);
  }, { pixel: true, repeat: true });
  tile.repeat.set(40, len / 2);

  const MAT = {
    tower: {
      pbr: new THREE.MeshStandardMaterial({ color: 0x7c8a84, map: windows, emissiveMap: windows, emissive: 0xffffff, emissiveIntensity: 2.2, roughness: 0.28, metalness: 0.6 }),
      tex: new THREE.MeshBasicMaterial({ map: windows, fog: true }),
      flat: new THREE.MeshLambertMaterial({ flatShading: true }),
    },
    gate: {
      pbr: new THREE.MeshStandardMaterial({ color: 0x06160c, emissive: GREEN, emissiveIntensity: 2.4 }),
      tex: new THREE.MeshBasicMaterial({ color: GREEN, fog: true }),
      flat: new THREE.MeshLambertMaterial({ color: GREEN, flatShading: true }),
    },
    ground: {
      // wet asphalt: a little see-through, so that the upside-down city under it reads as its reflection
      pbr: over(new THREE.MeshStandardMaterial({ color: 0x0a120e, roughness: 0.16, metalness: 0.75, opacity: 0.82 })),
      tex: new THREE.MeshBasicMaterial({ map: tile, fog: true }),
      flat: new THREE.MeshLambertMaterial({ color: 0x4a3f78 }),
      pix: new THREE.MeshLambertMaterial({ color: 0x2233c8 }),
    },
    roof: {
      pbr: new THREE.MeshStandardMaterial({ color: 0x141c20, roughness: 0.55, metalness: 0.4 }),
      tex: new THREE.MeshBasicMaterial({ color: 0x1a2026, fog: true }),
      flat: new THREE.MeshLambertMaterial({ color: 0x2a2f4a, flatShading: true }),
    },
    bot: {
      pbr: new THREE.MeshStandardMaterial({ color: 0xe8f4ec, roughness: 0.35, emissive: 0x0a3a20 }),
      tex: new THREE.MeshLambertMaterial({ color: 0xd8e4ff }),
      flat: new THREE.MeshLambertMaterial({ color: 0x40e0ff, flatShading: true }),
      pix: new THREE.MeshLambertMaterial({ color: 0xffe14a, flatShading: true }),
    },
  };
  // The city listens: in the lit style the windows are a level meter. The bass lights the lowest floors, the highs
  // the top ones (levels(tau, out) fills eight bands, 0 = bass; see src/spectrum.js).
  const bands = { value: new Array(8).fill(0.5) }, music = { value: levels ? 1 : 0 };
  MAT.tower.pbr.onBeforeCompile = (sh) => {
    sh.uniforms.uBands = bands;
    sh.uniforms.uMusic = music;
    sh.vertexShader = sh.vertexShader.replace('#include <common>', '#include <common>\nvarying float vWY;')
      .replace('#include <project_vertex>', '#include <project_vertex>\n#ifdef USE_INSTANCING\n  vWY = (modelMatrix * instanceMatrix * vec4(transformed, 1.0)).y;\n#else\n  vWY = (modelMatrix * vec4(transformed, 1.0)).y;\n#endif');
    sh.fragmentShader = sh.fragmentShader.replace('#include <common>', '#include <common>\nuniform float uBands[8];\nuniform float uMusic;\nvarying float vWY;')
      .replace('#include <emissivemap_fragment>', '#include <emissivemap_fragment>\n  { float lv = uBands[int(clamp(vWY / 46.0, 0.0, 0.999) * 8.0)]; totalEmissiveRadiance *= mix(1.0, 0.12 + 3.0 * smoothstep(0.3, 0.95, lv), uMusic); }');
  };
  MAT.tower.pbr.customProgramCacheKey = () => 'city-level-meter';
  const towerMesh = inst(towers, MAT.tower.pbr);
  const gateMesh = inst(gateParts, MAT.gate.pbr);
  towerMesh.castShadow = towerMesh.receiveShadow = gateMesh.castShadow = true;
  const roofMesh = inst(roofs, MAT.roof.pbr);
  const ground = new THREE.Mesh(new THREE.PlaneGeometry(760, len + 320), MAT.ground.pbr);
  ground.rotation.x = -Math.PI / 2;
  ground.position.set(0, 0, -(len + 320) / 2);
  ground.receiveShadow = true;
  ground.renderOrder = -1;
  scene.add(ground);
  // the reflection: the same towers and gates once more, upside down below the street
  const mirror = new THREE.Group();
  mirror.scale.y = -1;
  for (const [src, mat] of [[towerMesh, new THREE.MeshBasicMaterial({ map: windows, color: 0x8a9a92, fog: true })], [gateMesh, new THREE.MeshBasicMaterial({ color: 0x1fb866, fog: true })]]) {
    const m = new THREE.InstancedMesh(unit, mat, src.count);
    m.instanceMatrix.copy(src.instanceMatrix);
    m.frustumCulled = false;
    mirror.add(m);
  }
  scene.add(mirror);

  // ---- the night sky over the lit city: a glow at the horizon, clouds lit from below, a few stars
  const sky = new THREE.Mesh(
    new THREE.SphereGeometry(320, 32, 16),
    new THREE.ShaderMaterial({
      side: THREE.BackSide, depthWrite: false, fog: false,
      uniforms: { uT: { value: 0 } },
      vertexShader: 'varying vec3 vDir; void main() { vDir = position; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }',
      fragmentShader: `
        uniform float uT; varying vec3 vDir;
        float h2(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
        float vn(vec2 p) { vec2 i = floor(p), f = fract(p); f = f * f * (3. - 2. * f); return mix(mix(h2(i), h2(i + vec2(1., 0.)), f.x), mix(h2(i + vec2(0., 1.)), h2(i + vec2(1., 1.)), f.x), f.y); }
        float fbm(vec2 p) { float a = 0.5, s = 0.; for (int i = 0; i < 5; i++) { s += a * vn(p); p = p * 2.03 + 7.1; a *= 0.5; } return s; }
        void main() {
          vec3 d = normalize(vDir);
          float y = max(d.y, 0.);
          vec3 col = mix(vec3(0.015, 0.075, 0.05), vec3(0.003, 0.008, 0.016), smoothstep(0., 0.55, y));
          col += vec3(0.06, 0.42, 0.24) * exp(-y * 8.);
          float c = fbm(d.xz / (y + 0.14) * 1.2 + vec2(uT * 0.012, 0.));
          float cl = smoothstep(0.48, 0.78, c) * smoothstep(0.015, 0.22, y);
          col = mix(col, vec3(0.03, 0.2, 0.12) * (0.5 + 1.1 * c) * (0.5 + exp(-y * 4.)), cl * 0.85);
          vec3 g = floor(d * 240.);
          col += vec3(0.9) * step(0.9985, h2(g.xy + g.z * 17.)) * (1. - cl) * step(0.08, y);
          gl_FragColor = vec4(col, 1.);
        }`,
    }),
  );
  sky.frustumCulled = false;
  sky.renderOrder = -5;
  scene.add(sky);
  // the same light as a small picture all around: polished fronts and the wet street mirror it
  const EW = 64, EH = 32, env = new Uint16Array(EW * EH * 4);
  for (let j = 0; j < EH; j++) for (let i = 0; i < EW; i++) {
    const y = Math.cos(((j + 0.5) / EH) * Math.PI), up = Math.max(y, 0), glow = Math.exp(-Math.abs(y) * 7);
    const win = y > -0.25 && y < 0.5 && hash(i * 3.1 + j * 7.7) > 0.8 ? 1.6 : 0; // lit windows somewhere around us
    const rgb = [0.01 + 0.12 * glow + win * 0.4, 0.03 + 0.6 * glow + win * 0.8, 0.02 + 0.34 * glow + win * 0.6].map((v) => v * (1 - 0.6 * up));
    env.set([...rgb.map((v) => THREE.DataUtils.toHalfFloat(v)), THREE.DataUtils.toHalfFloat(1)], (j * EW + i) * 4);
  }
  const envTex = new THREE.DataTexture(env, EW, EH, THREE.RGBAFormat, THREE.HalfFloatType);
  envTex.mapping = THREE.EquirectangularReflectionMapping;
  envTex.magFilter = envTex.minFilter = THREE.LinearFilter;
  envTex.needsUpdate = true;
  scene.environment = envTex;
  scene.environmentIntensity = 0.5;

  // the bots: small boxes streaming through the gates, checking each other
  const NB = 90;
  const bots = new THREE.InstancedMesh(unit, MAT.bot.pbr, NB);
  bots.castShadow = true;
  bots.frustumCulled = false;
  scene.add(bots);

  // traffic in the air: lights crossing above the roofs in lanes
  const NA = 280;
  const air = new THREE.InstancedMesh(new THREE.BoxGeometry(0.9, 0.12, 0.12), new THREE.MeshBasicMaterial({ color: new THREE.Color(0x9dffc8).multiplyScalar(2.2), fog: false }), NA);
  air.frustumCulled = false;
  scene.add(air);

  // the same city as edges
  const edge = (list) => {
    const out = [], a = [];
    for (const [x, y, z, w, h, d] of list) {
      a.length = 0;
      boxEdges(a, w, h, d);
      for (let i = 0; i < a.length; i += 3) out.push(a[i] + x, a[i + 1] + y, a[i + 2] + z);
    }
    return out;
  };
  const fl = [];
  for (let x = -9; x <= 9; x += 3) fl.push(x, 0, 0, x, 0, -len);
  for (let k = 0; k <= beats + 14; k++) fl.push(-9, 0, -k * STEP, 9, 0, -k * STEP);
  const wire = new THREE.Group();
  wire.add(lines(edge(towers), { color: 0xe8e8e8, width: 0.035, opacity: 0.7 }), lines(edge(gateParts), { color: GREEN, width: 0.06 }), lines(fl, { color: 0x8c8c8c, width: 0.03, opacity: 0.55 }));
  wire.visible = false;
  scene.add(wire);

  const col = new THREE.Color();
  let style = '';
  const setStyle = (s) => {
    if (s === style) return;
    style = s;
    const solid = s !== 'wire';
    wire.visible = !solid;
    towerMesh.visible = gateMesh.visible = ground.visible = bots.visible = roofMesh.visible = solid;
    mirror.visible = sky.visible = air.visible = s === 'pbr';
    scene.fog.near = s === 'pbr' ? 50 : 30;
    scene.fog.far = s === 'pbr' ? 400 : 150;
    if (solid) roofMesh.material = MAT.roof[s === 'pix' ? 'flat' : s];
    scene.environmentIntensity = s === 'pbr' ? 0.5 : 0;
    scene.background.setHex(BG[s]);
    scene.fog.color.setHex(BG[s]);
    if (!solid) return;
    const k = s === 'pix' ? 'flat' : s;
    towerMesh.material = MAT.tower[k];
    gateMesh.material = MAT.gate[k];
    ground.material = MAT.ground[s];
    bots.material = MAT.bot[s];
    const pal = s === 'pix' ? PIX_PAL : FLAT_PAL;
    towers.forEach((_, i) => towerMesh.setColorAt(i, s === 'pbr' || s === 'tex' ? col.setHex(0xffffff) : col.setHex(pal[Math.floor(hash(i * 3.7 + seed) * pal.length)])));
    towerMesh.instanceColor.needsUpdate = true;
    key.castShadow = false; // measured: shadows cost 2 ms a frame here and hardly show on a dark, mirroring street
    hemi.intensity = s === 'pbr' ? 0.45 : 1.7;
    key.intensity = s === 'pbr' ? 2.2 : 2.8;
  };
  setStyle('pbr');

  const update = (tau) => {
    const cz = -V * tau, lb = tau / BEAT;
    const pulse = Math.exp(-(lb - Math.floor(lb)) * 4);
    key.position.set(14, 30, cz - 4);
    key.target.position.set(0, 0, cz - 22);
    MAT.gate.pbr.emissiveIntensity = 1.6 + 2.2 * pulse;
    MAT.tower.pbr.emissiveIntensity = levels ? 2.0 : 1.9 + 0.7 * pulse;
    if (levels) levels(tau, bands.value);
    const solid = style !== 'wire'; // (the engine's warm-up shows everything once: set it right again)
    wire.visible = !solid;
    towerMesh.visible = gateMesh.visible = ground.visible = bots.visible = roofMesh.visible = solid;
    mirror.visible = sky.visible = air.visible = style === 'pbr';
    if (air.visible) {
      for (let i = 0; i < NA; i++) {
        const lane = i % 14, dir = lane % 2 ? 1 : -1;
        const x = ((((i * 37.3 + tau * (26 + (lane % 5) * 6)) % 300) + 300) % 300 - 150) * dir;
        dummy.position.set(x, 20 + (lane % 4) * 9 + hash(i) * 2, -(10 + lane * (len / 14)) - (i % 3) * 1.4);
        dummy.rotation.set(0, 0, 0), dummy.scale.set(1 + hash(i * 3) * 2, 1, 1);
        dummy.updateMatrix();
        air.setMatrixAt(i, dummy.matrix);
      }
      air.instanceMatrix.needsUpdate = true;
    }
    sky.position.z = cz; // the sky travels with us
    sky.material.uniforms.uT.value = tau;
    if (!solid) return;
    for (let i = 0; i < NB; i++) {
      const z = -((((i * 5.37 + tau * (9 + hash(i) * 7)) % len) + len) % len);
      dummy.position.set((hash(i * 3.3) - 0.5) * 8.6, 0.4 + hash(i * 5.1) * 4.6, z);
      dummy.rotation.set(0, Math.floor(lb + hash(i) * 4) * (Math.PI / 2), 0);
      dummy.scale.setScalar(0.35 + hash(i * 6.6) * 0.45);
      dummy.updateMatrix();
      bots.setMatrixAt(i, dummy.matrix);
    }
    bots.instanceMatrix.needsUpdate = true;
  };
  void clamp;
  return { setStyle, update };
}

/** A gate frame around a portal, as boxes (hidden in wire style by the caller) and as lines. */
export function exitGate(scene, L, w = 5, h = 3.4) {
  const g = new THREE.Group();
  const mat = new THREE.MeshStandardMaterial({ color: 0x06160c, emissive: 0xffffff, emissiveIntensity: 1.6 });
  for (const [x, y, bw, bh] of [[-w / 2 - 0.2, h / 2, 0.4, h + 0.4], [w / 2 + 0.2, h / 2, 0.4, h + 0.4], [0, h + 0.2, w + 0.8, 0.4]]) {
    const b = new THREE.Mesh(new THREE.BoxGeometry(bw, bh, 0.4), mat);
    b.position.set(x, y, -L - 0.25);
    g.add(b);
  }
  scene.add(g);
  return g;
}

// LGTM out of glowing cubes, one letter per syllable
const GLYPH = {
  L: ['10000', '10000', '10000', '10000', '10000', '10000', '11111'],
  G: ['01110', '10001', '10000', '10111', '10001', '10001', '01110'],
  T: ['11111', '00100', '00100', '00100', '00100', '00100', '00100'],
  M: ['10001', '11011', '10101', '10101', '10001', '10001', '10001'],
};
export function cubeLetters(scene, hooks, syl, t0, { y = 2.9, spread = 2.7, ahead = 22, gain = 1 } = {}) {
  const geo = new THREE.BoxGeometry(0.42, 0.42, 0.42), dummy = new THREE.Object3D(), list = [];
  for (const h of hooks) {
    [...'LGTM'].forEach((ch, i) => {
      const cells = [];
      GLYPH[ch].forEach((row, r) => [...row].forEach((c, x) => c === '1' && cells.push([(x - 2) * 0.46, (6 - r) * 0.46])));
      const m = new THREE.InstancedMesh(geo, new THREE.MeshStandardMaterial({ color: 0x0c3a22, emissive: GREEN, emissiveIntensity: 1.0, roughness: 0.5 }), cells.length);
      cells.forEach(([x, yy], n) => {
        dummy.position.set(x, yy, 0), dummy.updateMatrix();
        m.setMatrixAt(n, dummy.matrix);
      });
      m.position.set((i - 1.5) * spread, y, -V * (h - t0) - ahead - i * 3);
      m.castShadow = true;
      m.visible = false;
      scene.add(m);
      list.push({ m, at: h + syl[i] - t0 });
    });
  }
  return (tau, pulse) => {
    for (const l of list) {
      const age = tau - l.at;
      l.m.visible = age >= 0;
      l.m.scale.setScalar(1 + 0.25 * (1 - clamp(age / 0.14)));
      l.m.material.emissiveIntensity = gain * (0.8 + 0.5 * pulse + 1.5 * (1 - clamp(age / 0.3)));
    }
  };
}
