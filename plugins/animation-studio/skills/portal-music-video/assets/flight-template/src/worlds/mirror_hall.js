// Starter world 3: ray tracing. Nothing here is a polygon: every pixel sends a ray into the scene and the ray
// bounces - chrome spheres mirror each other, the floor mirrors the sky, shadows are soft. The whole world (spheres,
// floor, sky, the song's lines, what flies along, even the portal's opening) lives in one shader; that is how a
// world looks that draws itself instead of handing meshes to the engine (carryStyle 'none', onPass).
import * as THREE from 'three';
import { MONO } from '../kit.js';
import { BEAT, STEP, V } from '../song.js';

export const id = 'mirror_hall';
export const beats = 16;
export const carryColor = 0xffffff;
export const carryStyle = 'none';
export const res = 720; // rays are costly: never more than 720 lines, shown soft
export const soft = true; // the shader draws the change itself, so that it is mirrored too
export const glow = 0.55;
export const flight = { sway: 2.0, waves: 1, rise: 0.8 };

const MAX_LINES = 8; // lines of the song shown as panes of light (the shader checks every pane for every ray)
const VERT = /* glsl */ `
  varying vec3 vRd;
  void main() {
    gl_Position = vec4(position.xy, 0.999, 1.0);
    vec4 v = inverse(projectionMatrix) * vec4(position.xy, 1.0, 1.0);
    vRd = (inverse(viewMatrix) * vec4(v.xyz / v.w, 0.0)).xyz;
  }`;
const FRAG = (P, NCELL, N) => /* glsl */ `
  uniform float uBeat, uL, uFlat, uClip, uCubeOn, uCubeScale;
  uniform vec3 uFlatCol, uCube;
  uniform mat3 uCubeRot;
  uniform sampler2D uText;
  uniform float uSignZ[${N}], uSignY[${N}], uSignCut[${N}];
  uniform vec2 uSignHalf;
  varying vec3 vRd;
  const float P = ${P.toFixed(4)};
  const vec3 SUN = normalize(vec3(-0.34, 0.26, -0.9));
  const vec2 PC = vec2(0.0, 1.9); // portal centre
  const float PR = 2.42;

  float sdBox(vec3 p, vec3 b) { vec3 q = abs(p) - b; return length(max(q, 0.)) + min(max(q.x, max(q.y, q.z)), 0.); }
  float gId; // which sphere
  float sdSpheres(vec3 p) {
    float id = clamp(floor(p.z / P + 0.5), -${NCELL.toFixed(1)}, -1.);
    float side = p.x < 0. ? -1. : 1.;
    vec3 c = vec3(side * 4.7, 1.5 + 0.42 * sin(uBeat * 1.5708 + id * 1.7 + side), id * P);
    gId = id * 2. + side;
    return length(p - c) - 1.12;
  }
  // x = distance, y = material (0 floor, 1 sphere, 2 the change, 3 ring of light)
  vec2 map(vec3 p) {
    vec2 r = vec2(p.y, 0.);
    float s = sdSpheres(p);
    if (s < r.x) r = vec2(s, 1.);
    vec3 q = p - vec3(PC, -uL);
    float t = length(vec2(length(q.xy) - (PR + 0.14), q.z)) - 0.14;
    if (t < r.x) r = vec2(t, 3.);
    if (uCubeOn > 0.5) {
      float c = sdBox(uCubeRot * (p - uCube), vec3(0.27 * uCubeScale)) - 0.12;
      c = max(c, uClip > 0. ? -(p.z + uL) : p.z); // cut at the portal's plane, like everything that travels through
      if (c < r.x) r = vec2(c, 2.);
    }
    return r;
  }
  float march(vec3 ro, vec3 rd, out float m) {
    float t = 0.02;
    for (int i = 0; i < 96; i++) {
      vec2 h = map(ro + rd * t);
      if (h.x < 0.0015 * t) { m = h.y; return t; }
      t += h.x * 0.9;
      if (t > 170.) break;
    }
    m = -1.;
    return -1.;
  }
  vec3 normal(vec3 p) {
    vec2 e = vec2(0.002, 0.);
    return normalize(vec3(map(p + e.xyy).x - map(p - e.xyy).x, map(p + e.yxy).x - map(p - e.yxy).x, map(p + e.yyx).x - map(p - e.yyx).x));
  }
  float shadow(vec3 ro) {
    float res = 1., t = 0.05;
    for (int i = 0; i < 28; i++) {
      float h = map(ro + SUN * t).x;
      res = min(res, 9. * h / t);
      t += clamp(h, 0.05, 1.2);
      if (res < 0.01 || t > 40.) break;
    }
    return clamp(res, 0., 1.);
  }
  vec3 sky(vec3 rd) {
    float h = max(rd.y, 0.);
    vec3 c = mix(vec3(0.85, 0.30, 0.16), vec3(0.05, 0.07, 0.24), pow(h, 0.3));
    c = mix(c, vec3(0.008, 0.012, 0.05), smoothstep(0.12, 0.8, h));
    float s = max(dot(rd, SUN), 0.);
    return c + vec3(1.0, 0.72, 0.42) * (pow(s, 400.) * 8. + pow(s, 40.) * 0.35);
  }
  // the words stand as panes of light across the road; rays that bounce see them too
  vec3 words(vec3 ro, vec3 rd, float tmax, vec3 col, inout float cover) {
    for (int i = 0; i < ${N}; i++) {
      if (uSignCut[i] <= 0.) continue;
      float t = (uSignZ[i] - ro.z) / rd.z;
      if (t <= 0. || t >= tmax) continue;
      vec3 q = ro + rd * t;
      vec2 uv = vec2(q.x / uSignHalf.x, (q.y - uSignY[i]) / uSignHalf.y) * 0.5 + 0.5;
      if (uv.x < 0. || uv.x > uSignCut[i] || uv.y < 0. || uv.y > 1.) continue;
      float a = textureLod(uText, vec2(uv.x, 1. - (float(i) + 1. - uv.y) / ${N}.0), 0.).a;
      col = mix(col, vec3(0.25, 2.4, 0.9), a);
      cover = max(cover, a);
    }
    return col;
  }
  void main() {
    vec3 ro = cameraPosition, rd = normalize(vRd);
    if (uClip < 0. && ro.z > 0.) { // seen through a portal: this world begins at z = 0
      if (rd.z > -0.0001) { gl_FragColor = vec4(uFlatCol, 1.); return; }
      ro += rd * (ro.z / -rd.z + 0.001);
    }
    vec3 col = vec3(0.), att = vec3(1.);
    float alpha = 1.;
    for (int b = 0; b < 3; b++) {
      float m;
      float t = march(ro, rd, m);
      float tmax = t > 0. ? t : 1e4;
      vec3 p = ro + rd * t, n = vec3(0., 1., 0.), c, refl = vec3(0.);
      if (t < 0.) c = sky(rd);
      else {
        n = normal(p);
        float sh = shadow(p + n * 0.02);
        vec3 light = vec3(1.0, 0.8, 0.6) * 2.4 * max(dot(n, SUN), 0.) * sh + vec3(0.16, 0.2, 0.34) * (0.6 + 0.4 * n.y);
        vec3 alb, extra = vec3(0.);
        if (m < 0.5) { // floor: dark polished tiles
          vec2 g = floor(p.xz / 1.5);
          alb = vec3(mod(g.x + g.y, 2.) < 0.5 ? 0.035 : 0.11);
          vec2 f = abs(fract(p.xz / 1.5) - 0.5);
          alb *= smoothstep(0.5, 0.485, max(f.x, f.y));
          refl = vec3(0.55);
        } else if (m < 1.5) { // spheres: chrome, gold, green
          sdSpheres(p);
          float k = mod(abs(gId), 3.);
          refl = k < 0.5 ? vec3(0.92) : k < 1.5 ? vec3(1.0, 0.76, 0.36) : vec3(0.3, 1.0, 0.62);
          alb = refl * 0.06;
        } else if (m < 2.5) { // the change: green lacquer that glows a little, with bright edges - a mirror cube would show the
          // sky on its faces and read as glass
          alb = vec3(0.08, 0.72, 0.36); refl = vec3(0.16); light += vec3(0.25);
          vec3 cq = abs(uCubeRot * (p - uCube)) / (0.27 * uCubeScale + 0.12);
          float e1 = max(max(min(cq.x, cq.y), min(cq.y, cq.z)), min(cq.x, cq.z)); // near 1 on an edge
          extra = vec3(0.05, 0.3, 0.14) + vec3(0.6, 1.4, 0.9) * smoothstep(0.78, 0.95, e1);
        }
        else { alb = vec3(0.); light = vec3(0.); refl = vec3(0.); }
        float fres = pow(clamp(1. - dot(-rd, n), 0., 1.), 5.);
        refl = refl + (1. - refl) * fres * step(0.5, 2.5 - m);
        c = alb * light * (1. - refl) + (m > 2.5 ? vec3(3.5) : vec3(0.)) + extra;
        c = mix(c, sky(rd), smoothstep(95., 168., t)); // far things fade into the air
      }
      // the portal's opening
      bool through = false;
      float tp = (-uL - ro.z) / rd.z;
      if (rd.z < 0. && tp > 0. && tp < tmax && length((ro + rd * tp).xy - PC) < PR) {
        through = true;
        tmax = tp;
        if (b == 0 && uFlat < 0.5) { c = vec3(0.); alpha = 0.; }
        else c = b == 0 ? uFlatCol : vec3(1.4, 1.6, 2.0);
      }
      float cover = 0.;
      c = words(ro, rd, tmax, c, cover);
      if (b == 0) alpha = max(alpha, cover);
      col += att * c;
      if (t < 0. || through) break;
      att *= refl;
      if (max(att.r, max(att.g, att.b)) < 0.03) break;
      ro = p + n * 0.02;
      rd = reflect(rd, n);
    }
    col *= 0.85;
    col = (col * (2.51 * col + 0.03)) / (col * (2.43 * col + 0.59) + 0.14); // film-like tone curve
    gl_FragColor = vec4(clamp(col, 0., 1.) * step(0.001, alpha), alpha);
  }`;

export function build({ t0, L, beats, lines: sung }) {
  const scene = new THREE.Scene();
  const SIGNS = sung.slice(0, MAX_LINES);
  const N = Math.max(1, SIGNS.length);

  // the four lines on one sheet of type
  const ROW = 256, WPX = 2048, FONT = MONO.replace('200px', '120px');
  const c = document.createElement('canvas');
  c.width = WPX;
  c.height = ROW * N;
  const g = c.getContext('2d');
  g.font = FONT;
  g.fillStyle = '#fff';
  const cuts = SIGNS.map((line, i) => {
    const text = line.words.join(' ');
    const x0 = Math.max(8, (WPX - g.measureText(text).width) / 2); // a line longer than the sheet is cut at its end
    g.fillText(text, x0, i * ROW + 180);
    // where the line ends after 1, 2, ... words
    return line.words.map((_, k) => (x0 + g.measureText(line.words.slice(0, k + 1).join(' ')).width + 8) / WPX);
  });
  const tex = new THREE.CanvasTexture(c);
  tex.generateMipmaps = false;
  tex.minFilter = tex.magFilter = THREE.LinearFilter;
  const unit = 0.78 / (120 * 0.71);
  const signZ = Array.from({ length: N }, (_, i) => (SIGNS[i] ? Math.max(-V * (SIGNS[i].at[0] - t0) - 24, -L + 2) : 0));
  const signY = signZ.map((_, i) => (signZ[i] <= -L + 2.01 ? 6.0 : 4.6) - (180 - ROW / 2) * unit);

  const uniforms = {
    uBeat: { value: 0 }, uL: { value: L }, uFlat: { value: 0 }, uClip: { value: 1 },
    uFlatCol: { value: new THREE.Color(0x101828) },
    uCube: { value: new THREE.Vector3() }, uCubeRot: { value: new THREE.Matrix3() }, uCubeOn: { value: 1 }, uCubeScale: { value: 1 },
    uText: { value: tex }, uSignZ: { value: signZ }, uSignY: { value: signY }, uSignCut: { value: new Array(N).fill(0) },
    uSignHalf: { value: new THREE.Vector2((WPX * unit) / 2, (ROW * unit) / 2) },
  };
  const quad = new THREE.Mesh(
    new THREE.PlaneGeometry(2, 2),
    new THREE.ShaderMaterial({ vertexShader: VERT, fragmentShader: FRAG(2 * STEP, Math.max(1, Math.floor((beats - 4) / 2)), N), uniforms, depthTest: false, depthWrite: false }),
  );
  quad.frustumCulled = false;
  scene.add(quad);

  const update = (tau) => {
    uniforms.uBeat.value = tau / BEAT;
    SIGNS.forEach((line, i) => {
      let k = 0;
      while (k < line.at.length && tau >= line.at[k] - t0) k++;
      uniforms.uSignCut.value[i] = k ? cuts[i][k - 1] : 0;
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
  // the engine only switches the opening between "hole" and "flat colour"
  const portal = { mat: { uniforms: { uFlat: uniforms.uFlat } } };
  return { scene, portal, update, onPass };
}
