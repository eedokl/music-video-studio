// Shared builders for the worlds: fat lines, words as road signs, seven-segment digits, small helpers.
import * as THREE from 'three';
import { LineMaterial } from 'three/addons/lines/LineMaterial.js';
import { LineSegments2 } from 'three/addons/lines/LineSegments2.js';
import { LineSegmentsGeometry } from 'three/addons/lines/LineSegmentsGeometry.js';
import * as song from './song.js';

const V = song.V;

export const clamp = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));
export const ease = (x) => {
  const u = clamp(x);
  return u * u * (3 - 2 * u);
};
export const hash = (n) => {
  const x = Math.sin(n * 127.1 + 311.7) * 43758.5453;
  return x - Math.floor(x);
};

/**
 * EVERY see-through material of a world must go through this. The picture's alpha channel says "here is the
 * portal" (the engine lays the next world in there), so alpha has to be blended as coverage, not squared.
 */
export function over(mat) {
  mat.transparent = true;
  mat.blending = THREE.CustomBlending;
  mat.blendEquation = THREE.AddEquation;
  mat.blendSrc = THREE.SrcAlphaFactor;
  mat.blendDst = THREE.OneMinusSrcAlphaFactor;
  mat.blendSrcAlpha = THREE.OneFactor;
  mat.blendDstAlpha = THREE.OneMinusSrcAlphaFactor;
  return mat;
}

/** Fat lines from a flat list [x1,y1,z1, x2,y2,z2, ...]; width in world units, so far lines get thin. */
export function lines(pos, { color = 0xffffff, width = 0.04, opacity = 1 } = {}) {
  const g = new LineSegmentsGeometry();
  g.setPositions(pos);
  const m = over(new LineMaterial({ color, linewidth: width, worldUnits: true, fog: true, opacity, depthWrite: false }));
  const o = new LineSegments2(g, m);
  o.frustumCulled = false;
  return o;
}
export const seg = (a, x1, y1, z1, x2, y2, z2) => a.push(x1, y1, z1, x2, y2, z2);
/** Rectangle in the XY plane, centre (cx, cy), at depth z. */
export function rectXY(a, cx, cy, z, w, h) {
  const x0 = cx - w / 2, x1 = cx + w / 2, y0 = cy - h / 2, y1 = cy + h / 2;
  seg(a, x0, y0, z, x1, y0, z);
  seg(a, x1, y0, z, x1, y1, z);
  seg(a, x1, y1, z, x0, y1, z);
  seg(a, x0, y1, z, x0, y0, z);
}
/** Regular polygon (a "circle") in the XY plane. */
export function ringXY(a, cx, cy, z, r, n = 48) {
  for (let i = 0; i < n; i++) {
    const p = (i / n) * Math.PI * 2, q = ((i + 1) / n) * Math.PI * 2;
    seg(a, cx + Math.cos(p) * r, cy + Math.sin(p) * r, z, cx + Math.cos(q) * r, cy + Math.sin(q) * r, z);
  }
}
/** The 12 edges of a box centred on the origin. */
export function boxEdges(a, w, h, d) {
  const x = w / 2, y = h / 2, z = d / 2;
  for (const sy of [-1, 1]) for (const sz of [-1, 1]) seg(a, -x, sy * y, sz * z, x, sy * y, sz * z);
  for (const sx of [-1, 1]) for (const sz of [-1, 1]) seg(a, sx * x, -y, sz * z, sx * x, y, sz * z);
  for (const sx of [-1, 1]) for (const sy of [-1, 1]) seg(a, sx * x, sy * y, -z, sx * x, sy * y, z);
}

/** A canvas as a texture. pixel = true keeps hard pixels (old machines). */
export function canvasTex(w, h, draw, { pixel = false, repeat = false } = {}) {
  const c = document.createElement('canvas');
  c.width = w;
  c.height = h;
  draw(c.getContext('2d'), w, h);
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  if (pixel) {
    t.magFilter = THREE.NearestFilter;
    t.minFilter = THREE.NearestMipmapLinearFilter;
  } else t.anisotropy = 8;
  if (repeat) t.wrapS = t.wrapT = THREE.RepeatWrapping;
  return t;
}

// The two typefaces of the signs (canvas font strings, always 200px). Fonts of the system by default; a film sets its
// own in song.js (FONT_FLAT / FONT_MONO) and supplies them (index.html: a stylesheet with @font-face).
export const FLAT = song.FONT_FLAT ?? '900 200px "Arial Black", Arial, sans-serif';
export const MONO = song.FONT_MONO ?? '700 200px Consolas, "Courier New", monospace';

/** One word as a flat plane; origin = left end of the baseline. `size` = height of a capital letter in world units. */
export function word(text, { font = FLAT, size = 1, color = 0xffffff } = {}) {
  const c = document.createElement('canvas');
  const g = c.getContext('2d');
  g.font = font;
  const wpx = Math.ceil(g.measureText(text).width);
  c.width = wpx + 40;
  c.height = 280;
  g.font = font;
  g.fillStyle = '#fff';
  g.fillText(text, 20, 210);
  const tex = new THREE.CanvasTexture(c);
  tex.colorSpace = THREE.SRGBColorSpace;
  tex.anisotropy = 8;
  const unit = size / 142; // a capital of a 200 px font is about 142 px high
  const geo = new THREE.PlaneGeometry(c.width * unit, c.height * unit);
  geo.translate((c.width / 2 - 20) * unit, (c.height / 2 - 70) * unit, 0);
  const mat = over(new THREE.MeshBasicMaterial({ map: tex, color, depthWrite: false, fog: true, side: THREE.DoubleSide }));
  const mesh = new THREE.Mesh(geo, mat);
  mesh.renderOrder = 5;
  return { mesh, width: wpx * unit };
}

/**
 * A line of the song as a sign bridge across the road: every word appears when it is sung.
 * `at` = word times in seconds of the world's own clock. The camera flies under it.
 * posts = wire frame bridge (the 1970s), board = a solid panel behind the words (later machines).
 */
export function sign(words, at, { z, y = 4.5, size = 1.5, font = FLAT, color = 0xffffff, lineColor = 0xffffff, posts = true, board = null } = {}) {
  const group = new THREE.Group();
  const gap = size * 0.42;
  const parts = words.map((w) => word(w, { font, size, color }));
  const total = parts.reduce((s, p) => s + p.width, 0) + gap * (parts.length - 1);
  let x = -total / 2;
  for (const p of parts) {
    p.mesh.position.set(x, y, z);
    p.mesh.visible = false;
    group.add(p.mesh);
    x += p.width + gap;
  }
  if (board !== null) {
    const b = new THREE.Mesh(new THREE.BoxGeometry(total + 1.2, size + 0.9, 0.25), new THREE.MeshLambertMaterial({ color: board, flatShading: true }));
    b.position.set(0, y + size * 0.5, z - 0.2);
    group.add(b);
    for (const sx of [-1, 1]) {
      const p = new THREE.Mesh(new THREE.BoxGeometry(0.3, y, 0.3), new THREE.MeshLambertMaterial({ color: board, flatShading: true }));
      p.position.set(sx * (total / 2 + 0.3), y / 2, z - 0.2);
      group.add(p);
    }
  } else if (posts) {
    const a = [];
    const hw = total / 2 + 0.5;
    seg(a, -hw, y - 0.3, z, hw, y - 0.3, z);
    seg(a, -hw, 0, z, -hw, y + size + 0.3, z);
    seg(a, hw, 0, z, hw, y + size + 0.3, z);
    group.add(lines(a, { color: lineColor, width: 0.035, opacity: 0.5 }));
  }
  const update = (tau) => {
    parts.forEach((p, i) => {
      const age = tau - at[i];
      p.mesh.visible = age >= 0;
      const k = 1 + 0.14 * (1 - clamp(age / 0.1));
      p.mesh.scale.set(k, k, 1);
    });
  };
  return { group, update, width: total };
}

/** A song line as a sign that stands `ahead` units before the camera when its first word is sung (never behind the portal). */
export function roadSign(line, t0, L, ahead, opts = {}) {
  const z = Math.max(-V * (line.at[0] - t0) - ahead, -L + 1.5);
  // long lines are set smaller so that they fit the picture while they are read
  const size = Math.min(1.5, 25 / line.words.join(' ').length);
  return sign(line.words, line.at.map((x) => x - t0), { z, size, ...opts });
}

/** "Raus. Raus. Raus.": extra changes that overtake the camera and leave through the exit. Offsets relative to the camera. */
export function rausShots(at, t0) {
  const SHOTS = [[-1.5, -0.6], [1.5, -0.6], [0, 1.0]];
  return (tau) =>
    at
      .map((a, i) => ({ age: tau - (a - t0), i }))
      .filter((r) => r.age >= 0 && r.age < 2.5)
      .map((r) => ({ x: SHOTS[r.i][0], y: SHOTS[r.i][1], z: 2 - 26 * r.age, spin: r.age * 5 }));
}

const SEG = { 0: 'abcdef', 1: 'bc', 2: 'abged', 3: 'abgcd' };
/** A seven-segment display standing in the XY plane. show(null) = dark. */
export function sevenSeg({ w = 1.3, h = 2.4, th = 0.2, color = 0xff3b30 } = {}) {
  const group = new THREE.Group();
  const mat = new THREE.MeshBasicMaterial({ color, fog: true });
  const dim = over(new THREE.MeshBasicMaterial({ color, fog: true, opacity: 0.1, depthWrite: false }));
  const def = {
    a: [0, h / 2, w - th * 1.4, th], g: [0, 0, w - th * 1.4, th], d: [0, -h / 2, w - th * 1.4, th],
    f: [-w / 2, h / 4, th, h / 2 - th * 1.4], b: [w / 2, h / 4, th, h / 2 - th * 1.4],
    e: [-w / 2, -h / 4, th, h / 2 - th * 1.4], c: [w / 2, -h / 4, th, h / 2 - th * 1.4],
  };
  const on = {};
  for (const [k, [x, y, sw, sh]] of Object.entries(def)) {
    const geo = new THREE.PlaneGeometry(sw, sh);
    const off = new THREE.Mesh(geo, dim);
    off.position.set(x, y, 0);
    on[k] = new THREE.Mesh(geo, mat);
    on[k].position.set(x, y, 0.01);
    group.add(off, on[k]);
  }
  const show = (digit) => {
    for (const k of Object.keys(on)) on[k].visible = digit !== null && SEG[digit].includes(k);
  };
  show(null);
  return { group, show, mat, dim };
}
