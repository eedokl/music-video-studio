// World 9 "Generiert 2025" - verse 3. The picture is no longer computed from a scene somebody built: it looks
// as if a model had dreamt it. It arrives as noise and clears in steps; everything is soft, pastel and a little
// wrong: shelves that breathe, goods that melt between ball and box, a hand with seven fingers, words that are
// misspelt for a moment before they settle.
// "Sonntag früh. Der Shop ist leer. Null Euro. Weltweit." - the goods shrink away, every price tag says 0,00.
// Like the mirror hall this world lives in one shader (rays, soft shadows, reflections).
import * as THREE from 'three';
import { clamp, ease, hash, MONO } from '../kit.js';
import { BEAT, LINES, STEP, V } from '../song.js';

export const id = 'ki';
export const beats = 32;
export const year = 2025;
export const carryColor = 0xffffff;
export const carryStyle = 'none';
export const res = 720; // rays are costly: never more than 720 lines, shown soft
export const soft = true;
export const glow = 0.45;
export const rollIn = true;
export const flight = { sway: 2.0, waves: 1, phase: Math.PI, rise: 0.9 };

/** How much of the picture is still noise: full before we are in, cleared in ten steps over the first two seconds. */
export function noise(tau) {
  const k = clamp(1 - (tau + 0.4) / 2.4);
  const steps = Math.ceil(k * 10);
  return { amount: Math.min(0.86, steps / 10), seed: tau < -0.4 ? Math.floor(tau * 6) : steps };
}

const SIGNS = [LINES.sonntag, LINES.leer, LINES.null, LINES.bitte, LINES.status, LINES.stabil, LINES.maschine, LINES.kuehl];
const AHEAD = [22, 22, 22, 22, 22, 22, 14, 22];
const N = SIGNS.length;
const WRONG = { A: 'Λ', E: 'Ξ', O: 'Q', S: '5', I: 'l', T: '7', L: 'I', U: 'V', R: 'P', N: 'И', H: 'M', B: '8', G: '6', D: 'O', M: 'W', '.': ',', Ü: 'U', K: 'X' };

const VERT = /* glsl */ `
  varying vec3 vRd;
  void main() {
    gl_Position = vec4(position.xy, 0.999, 1.0);
    vec4 v = inverse(projectionMatrix) * vec4(position.xy, 1.0, 1.0);
    vRd = (inverse(viewMatrix) * vec4(v.xyz / v.w, 0.0)).xyz;
  }`;
const FRAG = (P, NCELL) => /* glsl */ `
  uniform float uT, uBeat, uL, uFlat, uClip, uCubeScale, uEmpty, uTags, uCold;
  uniform vec3 uFlatCol, uCube, uHand;
  uniform mat3 uCubeRot;
  uniform sampler2D uText, uTag;
  uniform float uSignZ[${N}], uSignY[${N}], uSignCut[${N}], uSignNew[${N}];
  uniform vec2 uSignHalf;
  varying vec3 vRd;
  const float P = ${P.toFixed(4)};
  const vec3 KEY = normalize(vec3(0.3, 0.85, 0.35));
  const vec2 PC = vec2(0.0, 1.9);
  const float PR = 2.42;

  float hash1(float n) { return fract(sin(n * 127.1) * 43758.5453); }
  float smin(float a, float b, float k) { float h = clamp(0.5 + 0.5 * (b - a) / k, 0., 1.); return mix(b, a, h) - k * h * (1. - h); }
  float sdBox(vec3 p, vec3 b) { vec3 q = abs(p) - b; return length(max(q, 0.)) + min(max(q.x, max(q.y, q.z)), 0.); }
  float sdCaps(vec3 p, vec3 a, vec3 b, float r) { vec3 pa = p - a, ba = b - a; return length(pa - ba * clamp(dot(pa, ba) / dot(ba, ba), 0., 1.)) - r; }
  vec3 pal(float x) { return 0.55 + 0.45 * cos(6.28318 * (vec3(0.0, 0.33, 0.67) + x)); }
  // the dream breathes: everything sways a little, except right at the two portals
  vec3 warp(vec3 p) {
    float w = smoothstep(3., 12., -p.z) * smoothstep(3., 12., p.z + uL);
    p.x += 0.22 * sin(p.z * 0.33 + uT * 0.6) * w;
    p.y += 0.13 * sin(p.z * 0.47 + p.x * 0.3 + uT * 0.8) * w;
    return p;
  }
  float sdHand(vec3 p) { // seven fingers
    vec3 q = p - uHand;
    float bound = length(q - vec3(0., 1.7, 0.)) - 2.4;
    if (bound > 0.8) return bound;
    float d = sdCaps(q, vec3(0.), vec3(0., 1.5, 0.), 0.26);
    d = smin(d, sdBox(q - vec3(0., 2.0, 0.), vec3(0.5, 0.42, 0.14)) - 0.12, 0.2);
    for (int i = 0; i < 7; i++) {
      float a = (float(i) - 3.) * 0.3, w = 0.14 * sin(uT * 2.5 + float(i));
      vec3 b = vec3(sin(a) * 0.45, 2.3 + cos(a) * 0.15, 0.);
      d = smin(d, sdCaps(q, b, b + vec3(sin(a + w), cos(a + w), -0.15) * 0.95, 0.105), 0.07);
    }
    return d;
  }
  float gCell;
  // x = distance, y = material: 0 floor, 1 shelf, 2 goods, 3 ring, 4 price rail, 5 hand, 6 the change
  vec2 map(vec3 p0) {
    vec3 p = warp(p0);
    vec2 r = vec2(p.y, 0.);
    float ax = abs(p.x);
    float id = clamp(floor(p.z / P + 0.5), -${NCELL.toFixed(1)}, -1.);
    float lz = p.z - id * P;
    gCell = id * 2. + (p.x < 0. ? -1. : 1.);
    float d = 1e5, tag = 1e5, prod = 1e5;
    for (int i = 0; i < 3; i++) {
      float by = 1.0 + float(i) * 1.35;
      d = min(d, sdBox(vec3(ax - 5.3, p.y - by, lz), vec3(1.1, 0.06, 2.5)) - 0.04);
      tag = min(tag, sdBox(vec3(ax - 4.14, p.y - (by - 0.24), lz), vec3(0.02, 0.17, 2.4)));
      if (uEmpty < 0.99 && abs(lz) < 2.3) {
        float k = floor((lz + 0.6) / 1.2);
        float h = hash1(gCell * 7. + float(i) * 3. + k);
        float rr = 0.34 * (0.7 + 0.3 * h) * (1. - uEmpty);
        vec3 c = vec3(ax - 5.0, p.y - (by + 0.1 + rr), lz - k * 1.2);
        prod = min(prod, mix(length(c) - rr, sdBox(c, vec3(rr * 0.8)) - 0.03, 0.5 + 0.5 * sin(uT * 1.3 + h * 20.)));
      }
    }
    d = min(d, sdBox(vec3(ax - 5.3, p.y - 2.0, abs(lz) - 2.5), vec3(0.07, 2.0, 0.07)) - 0.03);
    float sh = prod < 10. ? smin(d, prod, 0.22) : d; // (blending with the "no goods" value 1e5 would cost all precision)
    if (sh < r.x) r = vec2(sh, prod < d ? 2. : 1.);
    if (tag < r.x) r = vec2(tag, 4.);
    float hd = sdHand(p);
    if (hd < r.x) r = vec2(hd, 5.);
    vec3 q = p0 - vec3(PC, -uL);
    float a = atan(q.y, q.x);
    float t = length(vec2(length(q.xy) - (PR + 0.16 + 0.05 * sin(a * 5. + uT * 2.)), q.z)) - 0.16;
    if (t < r.x) r = vec2(t, 3.);
    vec3 cq = uCubeRot * (p0 - uCube);
    float s = 0.33 * uCubeScale;
    float c = mix(sdBox(cq, vec3(s)) - 0.03, length(cq) - s * 1.25, 0.5 + 0.5 * sin(uT * 2.1));
    c = max(c, uClip > 0. ? -(p0.z + uL) : p0.z);
    if (c < r.x) r = vec2(c, 6.);
    return r;
  }
  float march(vec3 ro, vec3 rd, out float m) {
    float t = 0.02;
    for (int i = 0; i < 100; i++) {
      vec2 h = map(ro + rd * t);
      if (h.x < 0.0015 * t) { m = h.y; return t; }
      t += h.x * 0.7;
      if (t > 150.) break;
    }
    m = -1.;
    return -1.;
  }
  vec3 normal(vec3 p) {
    vec2 e = vec2(0.003, 0.);
    return normalize(vec3(map(p + e.xyy).x - map(p - e.xyy).x, map(p + e.yxy).x - map(p - e.yxy).x, map(p + e.yyx).x - map(p - e.yyx).x));
  }
  float shadow(vec3 ro) {
    float res = 1., t = 0.1;
    for (int i = 0; i < 44; i++) {
      float h = map(ro + KEY * t).x;
      res = min(res, 6. * h / t);
      t += clamp(h, 0.03, 0.7);
      if (res < 0.01 || t > 12.) break;
    }
    return clamp(res, 0., 1.);
  }
  vec3 sky(vec3 rd) {
    vec3 c = mix(vec3(1.0, 0.55, 0.42), vec3(0.30, 0.28, 0.78), smoothstep(-0.1, 0.5, rd.y));
    c = mix(c, vec3(0.45, 0.9, 0.8), 0.3 * (0.5 + 0.5 * rd.x));
    return mix(c, vec3(0.42, 0.62, 0.85), uCold);
  }
  // the words: dark type hanging in the air; a word that has just appeared is still misspelt
  vec3 words(vec3 ro, vec3 rd, float tmax, vec3 col, inout float cover) {
    for (int i = 0; i < ${N}; i++) {
      if (uSignCut[i] <= 0.) continue;
      float t = (uSignZ[i] - ro.z) / rd.z;
      if (t <= 0. || t >= tmax) continue;
      vec3 q = ro + rd * t;
      vec2 uv = vec2(q.x / uSignHalf.x, (q.y - uSignY[i]) / uSignHalf.y) * 0.5 + 0.5;
      if (uv.x < 0. || uv.x > uSignCut[i] || uv.y < 0. || uv.y > 1.) continue;
      float row = float(i) + (uv.x > uSignNew[i] ? ${N}.0 : 0.);
      float a = textureLod(uText, vec2(uv.x, 1. - (row + 1. - uv.y) / ${2 * N}.0), 0.).a;
      col = mix(col, vec3(0.07, 0.03, 0.16), a);
      cover = max(cover, a);
    }
    return col;
  }
  void main() {
    vec3 ro = cameraPosition, rd = normalize(vRd);
    if (uClip < 0. && ro.z > 0.) {
      if (rd.z > -0.0001) { gl_FragColor = vec4(uFlatCol, 1.); return; }
      ro += rd * (ro.z / -rd.z + 0.001);
    }
    vec3 col = vec3(0.), att = vec3(1.);
    float alpha = 1.;
    for (int b = 0; b < 2; b++) {
      float m;
      float t = march(ro, rd, m);
      float tmax = t > 0. ? t : 1e4;
      vec3 p = ro + rd * t, n = vec3(0., 1., 0.), c, refl = vec3(0.);
      if (t < 0.) c = sky(rd);
      else {
        n = normal(p);
        vec3 ng = n;
        // the surface boils a little from frame to frame, as generated video does
        n = normalize(n + 0.02 * sin(p * 9. + floor(uT * 10.) * 3.1));
        vec3 wp = warp(p);
        map(p);
        float cell = gCell;
        float sh = shadow(p + ng * 0.06);
        vec3 light = vec3(1.0, 0.90, 0.80) * 1.15 * (max(dot(n, KEY), 0.) * 0.75 + 0.25) * (0.2 + 0.8 * sh) + sky(n) * 0.38;
        vec3 alb, glowC = vec3(0.);
        if (m < 0.5) { alb = mix(vec3(0.92, 0.55, 0.66), vec3(0.45, 0.75, 0.9), 0.5 + 0.5 * sin(wp.z * 0.15 + wp.x * 0.22)); refl = vec3(0.3); }
        else if (m < 1.5) { alb = vec3(0.92, 0.66, 0.52); refl = vec3(0.06); }
        else if (m < 2.5) { alb = pal(cell * 0.37 + dot(n, -rd) * 0.7 + uT * 0.08); refl = vec3(0.28); }
        else if (m < 3.5) { alb = vec3(0.); glowC = vec3(3.2); }
        else if (m < 4.5) { // price rail: 0,00 on every tag, once the song says "Null Euro"
          alb = vec3(0.97);
          float side = wp.x < 0. ? -1. : 1.;
          float cid = clamp(floor(wp.z / P + 0.5), -${NCELL.toFixed(1)}, -1.);
          float lz = wp.z - cid * P;
          float row = clamp(floor((wp.y + 0.24 - 1.0) / 1.35 + 0.5), 0., 2.);
          vec2 uv = vec2(fract(side * lz / 1.2 + 0.5), (wp.y - (1.0 + row * 1.35 - 0.24) + 0.17) / 0.34);
          if (uTags > hash1(cell * 3.3 + row)) alb = mix(alb, vec3(0.85, 0.05, 0.1), textureLod(uTag, uv, 0.).a);
        }
        else if (m < 5.5) { alb = vec3(1.0, 0.70, 0.64); refl = vec3(0.1); light += vec3(0.35, 0.08, 0.06); }
        else { alb = pal(dot(n, -rd) * 0.9 + uT * 0.25); refl = vec3(0.3); glowC = alb * 0.35; }
        float fres = pow(clamp(1. - dot(-rd, n), 0., 1.), 5.);
        refl += (1. - refl) * fres * (m > 2.5 && m < 3.5 ? 0. : 0.6);
        c = alb * light * (1. - refl) + glowC;
        c = mix(c, sky(rd), 1. - exp(-t * 0.011)); // soft haze
      }
      bool through = false;
      float tp = (-uL - ro.z) / rd.z;
      if (rd.z < 0. && tp > 0. && tp < tmax && length((ro + rd * tp).xy - PC) < PR) {
        through = true;
        tmax = tp;
        if (b == 0 && uFlat < 0.5) { c = vec3(0.); alpha = 0.; }
        else c = b == 0 ? uFlatCol : vec3(1.6);
      }
      float cover = 0.;
      c = words(ro, rd, tmax, c, cover);
      if (b == 0) alpha = max(alpha, cover);
      col += att * c;
      if (t < 0. || through) break;
      att *= refl;
      if (max(att.r, max(att.g, att.b)) < 0.03) break;
      ro = p + n * 0.15;
      rd = reflect(rd, n);
    }
    // "Die Maschine bleibt ganz kühl": the colour drains to ice
    col = mix(col, vec3(dot(col, vec3(0.3, 0.6, 0.1))) * vec3(0.62, 0.85, 1.15), uCold * 0.8);
    col *= 0.6;
    col = (col * (2.51 * col + 0.03)) / (col * (2.43 * col + 0.59) + 0.14);
    gl_FragColor = vec4(clamp(col, 0., 1.) * step(0.001, alpha), alpha);
  }`;

export function build({ t0, L }) {
  const scene = new THREE.Scene();
  const T = (songT) => songT - t0;

  // all lines on one sheet of type: upper half correct, lower half the way the model first spells them
  const ROW = 160, WPX = 2048, FONT = MONO.replace('200px', '110px');
  const c = document.createElement('canvas');
  c.width = WPX;
  c.height = ROW * N * 2;
  const g = c.getContext('2d');
  g.font = FONT;
  g.fillStyle = '#fff';
  const edges = SIGNS.map((line, i) => {
    const text = line.words.join(' ');
    const x0 = (WPX - g.measureText(text).width) / 2;
    g.fillText(text, x0, i * ROW + 112);
    const wrong = [...text].map((ch, k) => (hash(i * 31 + k * 7) > 0.45 && WRONG[ch]) || ch).join('');
    [...wrong].forEach((ch, k) => g.fillText(ch, x0 + g.measureText(text.slice(0, k)).width, (N + i) * ROW + 112));
    // u where the line starts, and where it ends after 1, 2, ... words
    return [x0 - 8, ...line.words.map((_, k) => x0 + g.measureText(line.words.slice(0, k + 1).join(' ')).width + 8)].map((x) => x / WPX);
  });
  const tex = new THREE.CanvasTexture(c);
  tex.generateMipmaps = false;
  tex.minFilter = tex.magFilter = THREE.LinearFilter;
  const unit = 0.85 / (110 * 0.71);
  const signZ = SIGNS.map((line, i) => Math.max(-V * T(line.at[0]) - AHEAD[i], -L + 2));
  const signY = SIGNS.map((_, i) => (signZ[i] <= -L + 2.01 ? 6.1 : 4.7) - (112 - ROW / 2) * unit);

  // price tag
  const tc = document.createElement('canvas');
  tc.width = 256;
  tc.height = 72;
  const tg = tc.getContext('2d');
  tg.font = 'bold 54px monospace';
  tg.textAlign = 'center';
  tg.fillStyle = '#fff';
  tg.fillText('0,00 €', 128, 55);
  const tagTex = new THREE.CanvasTexture(tc);
  tagTex.generateMipmaps = false;
  tagTex.minFilter = tagTex.magFilter = THREE.LinearFilter;

  const uniforms = {
    uT: { value: 0 }, uBeat: { value: 0 }, uL: { value: L }, uFlat: { value: 0 }, uClip: { value: 1 },
    uFlatCol: { value: new THREE.Color(0x8a78c0) },
    uCube: { value: new THREE.Vector3() }, uCubeRot: { value: new THREE.Matrix3() }, uCubeScale: { value: 1 },
    uEmpty: { value: 0 }, uTags: { value: 0 }, uCold: { value: 0 },
    uHand: { value: new THREE.Vector3(2.9, 0, -V * T(LINES.bitte.at[0]) - 15) },
    uText: { value: tex }, uTag: { value: tagTex },
    uSignZ: { value: signZ }, uSignY: { value: signY }, uSignCut: { value: new Array(N).fill(0) }, uSignNew: { value: new Array(N).fill(0) },
    uSignHalf: { value: new THREE.Vector2((WPX * unit) / 2, (ROW * unit) / 2) },
  };
  const quad = new THREE.Mesh(
    new THREE.PlaneGeometry(2, 2),
    new THREE.ShaderMaterial({ vertexShader: VERT, fragmentShader: FRAG(2 * STEP, Math.floor((beats - 4) / 2)), uniforms, depthTest: false, depthWrite: false }),
  );
  quad.frustumCulled = false;
  scene.add(quad);

  const update = (tau) => {
    uniforms.uT.value = tau;
    uniforms.uBeat.value = tau / BEAT;
    // "Der Shop ist leer": the goods shrink away between "Der" and "leer"
    uniforms.uEmpty.value = ease((tau - T(LINES.leer.at[0])) / (LINES.leer.at[3] - LINES.leer.at[0]));
    uniforms.uTags.value = clamp((tau - T(LINES.null.at[0])) / 0.7);
    uniforms.uCold.value = ease((tau - T(LINES.kuehl.at[0])) / 1.2);
    SIGNS.forEach((line, i) => {
      let k = 0;
      while (k < line.at.length && tau >= T(line.at[k])) k++;
      uniforms.uSignCut.value[i] = k ? edges[i][k] : 0;
      // the newest word stays misspelt for a third of a second
      uniforms.uSignNew.value[i] = k && tau - T(line.at[k - 1]) < 0.33 ? edges[i][k - 1] : 2;
    });
  };
  const m4 = new THREE.Matrix4(), eu = new THREE.Euler();
  const onPass = ({ cam, items, side }) => {
    const it = items[0];
    uniforms.uClip.value = side === 'here' ? 1 : -1;
    uniforms.uCube.value.set(cam.position.x + it.x, cam.position.y + it.y, cam.position.z + it.z);
    uniforms.uCubeRot.value.setFromMatrix4(m4.makeRotationFromEuler(eu.set(it.spin * 0.5, it.spin, 0))).transpose();
    uniforms.uCubeScale.value = it.scale ?? 1;
  };
  const portal = { mat: { uniforms: { uFlat: uniforms.uFlat } } };
  return { scene, portal, update, onPass };
}
