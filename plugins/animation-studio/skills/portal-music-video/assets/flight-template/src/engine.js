// The flight: a list of worlds, each as long as its part of the song, each ending in a portal onto the next.
// Which worlds, in which order and how long: src/plan.js (ORDER). This file is the same for every film.
//
// World contract (src/worlds/<id>.js):
//   export const id, beats (may be overridden in the plan), carryColor;  year (a number shown in the corner, running
//             towards the next world's year) or label (a text)
//   optional: carryStyle ('wire' | 'solid' | 'gem' | 'crate' | 'orb' | 'none': what the change looks like in this year), res (picture height in pixels, 0 = full),
//             look ({ levels, dither, scan, bloom, threshold, tone, exposure }), glow (0..1),
//             flight ({ sway, waves, phase, rise, hop, fov }) = how the camera flies here,
//             noise(tau) -> { amount, seed } (export; the picture is still partly noise, as while a model generates it),
//             rollIn (true = the camera rolls once around its axis while it enters: a jump in time)
//             dyn(tau) -> any of { res, soft, look, glow, carryStyle, carryColor } (export; overrides them over time),
//             travel(tau) -> distance flown (export; default V * tau; must be V * tau for tau < 0),
//             path(tau, D) -> { x, y, look, w } (export; its own flight: sideways and upward offset in units, and a
//               point the camera turns to with weight w 0..1; x, y and w must be 0 at both portals, the flight
//               still advances by V * tau, so everything along the road stays on the beat),
//             noExit (true = the film ends here: nothing darts ahead to a portal)
//   a built world may also return landing(tau) -> { x, y, z, k }: the change settles at that place (k = 0..1)
//   export function build({ t0, L, D, beats, lines }) -> { scene, portal, update(tau), carry?(tau), onPass?(info) }
//     lines = the song lines the plan gives this world: [{ text, words, at }] (at = song seconds per word).
//     t0 = song time of the world's start, D = its length in seconds, L = its length in units.
//     The camera enters at z = 0 and leaves through the portal at z = -L, always flying towards -z at speed V.
//     tau = the world's own clock in seconds; it is NEGATIVE while the world is only seen through a portal.
//     Build nothing at z > 0: that is the far side of the portal you came through.
//     Every see-through material goes through kit.over() (the alpha channel marks the portal).
//     onPass({ cam, items, side }) is called right before the world is drawn (side 'here' | 'next'), for worlds
//     that draw the travellers themselves (carryStyle 'none').
//
// Every frame draws two worlds: the next one (from where the camera would stand in it), developed in its own
// resolution and look, then the current one, whose portal is a hole the next picture is laid into.
import * as THREE from 'three';
import { boxEdges, canvasTex, clamp, ease, lines } from './kit.js';
import { COMPANION, END_YEAR, ORDER } from './plan.js';
import { BEAT, FROM, STEP, V } from './song.js';

const EYE = 1.6;
const TRAIL = 5; // ghosts behind the change
const MAX_CARRY = 1 + TRAIL + 3;
const ROLL = 1.0; // seconds before and after a jump in time during which the camera rolls
// The camera cannot see a portal that is nearer than its near plane (0.05 units = 8 ms of flight): for that instant
// the old world behind the opening would flash up. So the next world takes over this much BEFORE the crossing; it
// is drawn from in front of its entrance then, which is the very picture the portal showed.
const EARLY = 0.02; // seconds (a portal may stand a few hundredths in front of the world's end, e.g. on the face of a box)

// develops a world's picture (old machines: few colours, dither, scan lines) and lays the next world into the hole
const LOOK_FRAG = /* glsl */ `
  uniform sampler2D tCur;
  uniform sampler2D tNext;
  uniform float uUseNext;
  uniform float uLevels;
  uniform float uDither;
  uniform float uScan;
  uniform vec2 uSrc;
  uniform float uNoise;
  uniform float uSeed;
  uniform sampler2D tBloomA;
  uniform sampler2D tBloomB;
  uniform float uBloom;
  uniform float uTone;
  varying vec2 vUv;
  float h21(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
  float bayer(vec2 p) {
    float m[16] = float[16](0., 8., 2., 10., 12., 4., 14., 6., 3., 11., 1., 9., 15., 7., 13., 5.);
    return (m[int(mod(p.x, 4.)) + int(mod(p.y, 4.)) * 4] + 0.5) / 16.;
  }
  void main() {
    vec4 c = texture2D(tCur, vUv);
    vec3 rgb = max(c.rgb, 0.);
    if (uBloom > 0.) rgb += (texture2D(tBloomA, vUv).rgb + texture2D(tBloomB, vUv).rgb) * uBloom * clamp(c.a, 0., 1.); // (not over the portal: the next world brings its own)
    if (uTone > 0.) { // film-like tone curve: bright things roll off softly instead of clipping
      vec3 x = rgb * uTone;
      rgb = clamp((x * (2.51 * x + 0.03)) / (x * (2.43 * x + 0.59) + 0.14), 0., 1.) * (uBloom > 0. ? 1. : step(0.001, c.a));
    }
    if (uLevels > 0.5) {
      vec3 g = pow(rgb, vec3(1. / 2.2));
      g = floor(g * (uLevels - 1.) + 0.5 + (bayer(floor(vUv * uSrc)) - 0.5) * uDither) / (uLevels - 1.);
      rgb = pow(clamp(g, 0., 1.), vec3(2.2)) * step(0.001, c.a);
    }
    if (uScan > 0.) rgb *= 1. - uScan * (0.5 - 0.5 * cos(6.28318 * vUv.y * uSrc.y));
    if (uNoise > 0.001 && c.a > 0.001) { // not generated yet: coarse coloured noise
      vec2 cell = floor(vUv * vec2(240., 135.)) + uSeed * 13.7;
      rgb = mix(rgb, pow(vec3(h21(cell), h21(cell + 17.3), h21(cell + 41.9)), vec3(2.2)), uNoise);
    }
    if (uUseNext > 0.5) rgb += texture2D(tNext, vUv).rgb * (1. - clamp(c.a, 0., 1.));
    gl_FragColor = vec4(rgb, 1.);
    #include <colorspace_fragment>
  }`;

const smooth = (a, b, x) => ease((x - a) / (b - a));

export class Engine {
  constructor(canvas, glow) {
    this.canvas = canvas;
    this.glow = glow;
    this.glowCtx = glow.getContext('2d');
    this.renderer = new THREE.WebGLRenderer({ canvas, antialias: false, powerPreference: 'high-performance' });
    this.renderer.localClippingEnabled = true;
    this.renderer.shadowMap.enabled = true;
    this.renderer.shadowMap.type = THREE.PCFShadowMap;
    this.camera = new THREE.PerspectiveCamera(60, 16 / 9, 0.05, 400);
    this.camera.rotation.order = 'YXZ';
    this.camNext = this.camera.clone();
    this.res = new THREE.Vector2();
    this.full = new THREE.WebGLRenderTarget(16, 16, { type: THREE.HalfFloatType, depthBuffer: false });

    let beat = 0;
    if (ORDER.length < 2) throw new Error('plan.js: a flight needs at least two worlds');
    this.worlds = ORDER.map((entry) => {
      // a plan entry is a world module, or { mod, beats, lines } to set its length and its lines there
      const en = entry.mod ? entry : { mod: entry };
      const mod = en.mod, beats = en.beats ?? mod.beats;
      const D = beats * BEAT, L = beats * STEP;
      const w = { mod, start: beat * BEAT, D, L, ...mod.build({ t0: FROM + beat * BEAT, D, L, beats, lines: en.lines ?? [] }) };
      w.rts = {}; // its pictures: 'p' hard pixels, 's' smooth (made when first needed)
      beat += beats;
      return w;
    });
    this.total = beat * BEAT; // the whole song; after the last world the film starts again

    this.lookMat = new THREE.ShaderMaterial({
      vertexShader: 'varying vec2 vUv; void main() { vUv = uv; gl_Position = vec4(position.xy, 0., 1.); }',
      fragmentShader: LOOK_FRAG,
      uniforms: { tCur: { value: null }, tNext: { value: null }, uUseNext: { value: 0 }, uLevels: { value: 0 }, uDither: { value: 0 }, uScan: { value: 0 }, uSrc: { value: new THREE.Vector2() }, uNoise: { value: 0 }, uSeed: { value: 0 }, tBloomA: { value: null }, tBloomB: { value: null }, uBloom: { value: 0 }, uTone: { value: 0 } },
      depthTest: false,
      depthWrite: false,
    });
    this.lookScene = new THREE.Scene();
    const quad = new THREE.Mesh(new THREE.PlaneGeometry(2, 2), this.lookMat);
    quad.frustumCulled = false;
    this.lookScene.add(quad);
    this.lookCam = new THREE.OrthographicCamera(-1, 1, 1, -1, 0, 1);
    this.lookQuad = quad;
    // bloom: what is brighter than a threshold, blurred small and wide, is added back to the picture
    const small = (w, h) => new THREE.WebGLRenderTarget(w, h, { type: THREE.HalfFloatType, depthBuffer: false });
    this.bloomRT = [small(640, 360), small(640, 360), small(256, 144), small(256, 144)];
    const VS = 'varying vec2 vUv; void main() { vUv = uv; gl_Position = vec4(position.xy, 0., 1.); }';
    this.brightMat = new THREE.ShaderMaterial({
      vertexShader: VS, depthTest: false, depthWrite: false,
      uniforms: { t: { value: null }, uThr: { value: 1 } },
      fragmentShader: 'uniform sampler2D t; uniform float uThr; varying vec2 vUv; void main() { vec3 c = max(texture2D(t, vUv).rgb, 0.); float l = max(c.r, max(c.g, c.b)); gl_FragColor = vec4(c * max(l - uThr, 0.) / max(l, 1e-4), 1.); }',
    });
    this.blurMat = new THREE.ShaderMaterial({
      vertexShader: VS, depthTest: false, depthWrite: false,
      uniforms: { t: { value: null }, uDir: { value: new THREE.Vector2() } },
      fragmentShader: 'uniform sampler2D t; uniform vec2 uDir; varying vec2 vUv; void main() { vec3 c = texture2D(t, vUv).rgb * 0.227; c += (texture2D(t, vUv + uDir * 1.385).rgb + texture2D(t, vUv - uDir * 1.385).rgb) * 0.316; c += (texture2D(t, vUv + uDir * 3.231).rgb + texture2D(t, vUv - uDir * 3.231).rgb) * 0.070; gl_FragColor = vec4(c, 1.); }',
    });

    // what travels with the camera through every portal: the change (a cube with a trail of ghosts) and whatever
    // a world sends along. In the wire-frame years it is a wire cube, later a solid one.
    this.clipHere = new THREE.Plane(new THREE.Vector3(0, 0, 1), 0); // keep what is on this side of the portal
    this.clipNext = [new THREE.Plane(new THREE.Vector3(0, 0, -1), 0)]; // next world: keep what is beyond it
    // The current world is drawn with one plane too, one that cuts nothing: with the same number of planes in
    // both roles a world keeps its compiled shaders when the camera crosses into it (no hitch at the portal).
    this.clipNone = [new THREE.Plane(new THREE.Vector3(0, 0, -1), 1e6)];
    const cube = [];
    boxEdges(cube, 0.7, 0.7, 0.7);
    // one body per style: wire cube (1970s), solid cube (1983), faceted crystal (1993), wooden crate with a
    // texture (1998), glowing polished ball (2007). The ray-traced worlds draw their own (carryStyle 'none').
    const crateTex = canvasTex(64, 64, (g) => {
      g.fillStyle = '#b07a3c', g.fillRect(0, 0, 64, 64);
      for (let i = 0; i < 4; i++) g.fillStyle = i % 2 ? '#a36f34' : '#bb8546', g.fillRect(8, 8 + i * 12, 48, 12);
      g.strokeStyle = '#5a3a18', g.lineWidth = 6, g.strokeRect(3, 3, 58, 58);
      g.lineWidth = 4, g.beginPath(), g.moveTo(8, 8), g.lineTo(56, 56), g.stroke();
      g.fillStyle = '#1c120a', g.font = 'bold 17px monospace', g.textAlign = 'center', g.fillText('LGTM', 32, 38);
    }, { pixel: true });
    const BODY = {
      wire: () => lines(cube, { width: 0.035 }),
      solid: () => new THREE.Mesh(new THREE.BoxGeometry(0.7, 0.7, 0.7), new THREE.MeshLambertMaterial({ flatShading: true })),
      gem: () => new THREE.Mesh(new THREE.IcosahedronGeometry(0.52, 0), new THREE.MeshLambertMaterial({ flatShading: true })),
      crate: () => new THREE.Mesh(new THREE.BoxGeometry(0.78, 0.78, 0.78), new THREE.MeshLambertMaterial({ map: crateTex })),
      orb: () => new THREE.Mesh(new THREE.SphereGeometry(0.42, 32, 20), new THREE.MeshStandardMaterial({ roughness: 0.2, metalness: 0.55, emissiveIntensity: 0.1 })),
    };
    this.styles = Object.keys(BODY);
    const mkCarry = (clip) => {
      const g = new THREE.Group();
      for (let i = 0; i < MAX_CARRY; i++) {
        const slot = new THREE.Group();
        for (const style of this.styles) {
          const body = BODY[style]();
          body.castShadow = style !== 'wire';
          if (clip) body.material.clippingPlanes = [clip];
          slot.add(body);
        }
        g.add(slot);
      }
      return g;
    };
    this.carryHere = mkCarry(this.clipHere);
    this.carryNext = mkCarry(null);
    this.resize();
  }

  resize() {
    const r = this.canvas.getBoundingClientRect();
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    const w = Math.max(2, Math.round(r.width * dpr)), h = Math.max(2, Math.round(r.height * dpr));
    this.renderer.setPixelRatio(1);
    this.renderer.setSize(w, h, false);
    this.full.setSize(w, h);
    this.res.set(w, h);
  }

  /** What a world looks like at its clock tau: its exports, overridden by dyn(tau). */
  state(w, tau) {
    const m = w.mod, d = m.dyn?.(tau) ?? {};
    return {
      res: d.res ?? m.res ?? 0,
      soft: d.soft ?? m.soft ?? false,
      look: d.look ?? m.look ?? {},
      glow: d.glow ?? m.glow ?? 0.85,
      carryStyle: COMPANION ? d.carryStyle ?? m.carryStyle ?? 'wire' : 'none',
      carryColor: d.carryColor ?? m.carryColor ?? 0xffffff,
    };
  }

  /** The picture a world is drawn into for that state (w.rt), in the right size and with hard or smooth pixels. */
  target(w, st) {
    const pixel = st.res > 0 && !st.soft;
    const key = pixel ? 'p' : 's';
    w.rts[key] ??= new THREE.WebGLRenderTarget(16, 16, {
      type: THREE.HalfFloatType,
      samples: pixel ? 0 : 4,
      magFilter: pixel ? THREE.NearestFilter : THREE.LinearFilter,
      minFilter: pixel ? THREE.NearestFilter : THREE.LinearFilter,
    });
    const rt = w.rts[key];
    const rh = Math.min(st.res || this.res.y, this.res.y), rw = Math.round((rh * 16) / 9);
    if (rt.width !== rw || rt.height !== rh) rt.setSize(rw, rh);
    w.rt = rt;
    w.st = st;
    return rt;
  }

  /** Sideways and upward offset of the flight path in a world; zero (and flat) at both portals. */
  offset(world, tau) {
    const f = world.mod.flight ?? {};
    const u = clamp(tau / world.D);
    const win = smooth(0, 0.14, u) * (1 - smooth(0.86, 1, u));
    const own = world.mod.path?.(clamp(tau, 0, world.D), world.D);
    if (own) return [own.x, own.y, 60 + ((f.fov ?? 60) - 60) * win, own.look, own.w ?? 0];
    const x = (f.sway ?? 0.5) * Math.sin(2 * Math.PI * (f.waves ?? 1) * u + (f.phase ?? 0)) * win;
    const y = ((f.rise ?? 0) * Math.sin(Math.PI * u) ** 2 + (f.hop ?? 0) * Math.sin((Math.PI * tau) / (2 * BEAT)) ** 2) * win;
    return [x, y, 60 + ((f.fov ?? 60) - 60) * win];
  }

  /** The camera in a world at its clock tau: it follows the path, looks where it flies and banks into the curves. */
  pose(cam, world, tau, rollIn, rollOut) {
    const e = 0.15;
    const [x, y, fov, look, lw] = this.offset(world, tau), [x0, y0] = this.offset(world, tau - e), [x1, y1] = this.offset(world, tau + e);
    if (cam.fov !== fov) (cam.fov = fov), cam.updateProjectionMatrix();
    let yaw = Math.atan2(-(x1 - x0) / (2 * e), V) * 0.7, pitch = Math.atan2((y1 - y0) / (2 * e), V) * 0.6;
    const bank = yaw; // the camera banks with the curve it flies, not with where it looks
    if (look && lw > 0) { // a guided gaze: turn towards the point the world names
      const dx = look[0] - x, dy = look[1] - (EYE + y), dz = look[2] + (world.mod.travel?.(tau) ?? V * tau);
      yaw += (Math.atan2(-dx, -dz) - yaw) * lw;
      pitch += (Math.atan2(dy, Math.hypot(dx, dz)) - pitch) * lw;
    }
    // a jump in time: one full roll, half of it before the portal, half after
    let roll = bank * 1.1;
    if (rollIn && tau < ROLL) roll += 2 * Math.PI * ease((tau + ROLL) / (2 * ROLL));
    if (rollOut && tau > world.D - ROLL) roll += 2 * Math.PI * ease((tau - world.D + ROLL) / (2 * ROLL));
    cam.position.set(x, EYE + y, -(world.mod.travel?.(tau) ?? V * tau));
    cam.rotation.set(pitch, yaw, roll);
  }

  /** Where the change flies, relative to the camera, at second s of the film (d = seconds to the nearest portal). */
  cubeAt(s, d) {
    const b = s / BEAT, ph = (2 * Math.PI * b) / 8;
    const fb = b - Math.floor(b);
    const pulse = Math.exp(-fb * 5) * ease(fb / 0.16); // a soft attack: no jump on the beat
    return {
      x: 1.9 * Math.sin(ph),
      y: -0.55 + 0.45 * Math.sin(2 * ph + 0.6) + 0.16 * pulse,
      z: -5.5 - 0.8 * Math.cos(ph) - 7 * Math.exp(-((d / 0.9) ** 2)), // it darts ahead through every portal
      spin: (Math.floor(b) + ease(fb * 1.4)) * (Math.PI / 2),
      scale: 1 + 0.18 * pulse,
    };
  }

  develop(world, target, next, tau) {
    const u = this.lookMat.uniforms, look = world.st.look;
    u.tCur.value = world.rt.texture;
    u.tNext.value = next;
    u.uUseNext.value = next ? 1 : 0;
    u.uLevels.value = look.levels ?? 0;
    u.uDither.value = look.dither ?? 0;
    u.uScan.value = look.scan ?? 0;
    u.uSrc.value.set(world.rt.width, world.rt.height);
    const nz = world.mod.noise?.(tau);
    u.uNoise.value = nz?.amount ?? 0;
    u.uSeed.value = nz?.seed ?? 0;
    u.uBloom.value = look.bloom ?? 0;
    u.uTone.value = look.tone ? (look.exposure ?? 1) : 0;
    if (look.bloom) {
      const R = this.renderer, q = this.lookQuad, [a, b, c, d] = this.bloomRT;
      const pass = (mat, src, dst, dx, dy) => {
        mat.uniforms.t.value = src.texture;
        if (mat === this.blurMat) mat.uniforms.uDir.value.set(dx / dst.width, dy / dst.height);
        q.material = mat;
        R.setRenderTarget(dst);
        R.render(this.lookScene, this.lookCam);
      };
      this.brightMat.uniforms.uThr.value = look.threshold ?? 1;
      pass(this.brightMat, world.rt, a);
      pass(this.blurMat, a, b, 1, 0), pass(this.blurMat, b, a, 0, 1); // tight
      pass(this.blurMat, a, d, 1.5, 0), pass(this.blurMat, d, c, 0, 1.5), pass(this.blurMat, c, d, 2.5, 0), pass(this.blurMat, d, c, 0, 2.5); // wide
      q.material = this.lookMat;
      u.tBloomA.value = a.texture;
      u.tBloomB.value = c.texture;
    }
    this.renderer.setRenderTarget(target);
    this.renderer.render(this.lookScene, this.lookCam);
  }

  /** Draw every world once in both roles before the film starts, so that no shader is compiled while it plays. */
  warmUp() {
    // words and props that are still hidden would send their textures to the graphics card only when they first
    // show up (a hitch on that very word): show everything once and draw it
    for (const w of this.worlds) {
      w.scene.traverse((o) => {
        o.visible = true;
        for (const m of [o.material].flat()) if (m?.map) this.renderer.initTexture(m.map);
      });
      this.renderer.clippingPlanes = this.clipNone;
      this.renderer.setRenderTarget(this.target(w, this.state(w, 0)));
      this.renderer.render(w.scene, this.camera);
    }
    for (const w of this.worlds) for (const u of [0.002, 0.25, 0.5, 0.75, 0.998]) this.frame(w.start + u * w.D);
    this.renderer.getContext().finish();
  }

  /** Draw the film at second `sec` of the song. */
  frame(sec) {
    const s = ((sec % this.total) + this.total) % this.total;
    const n = this.worlds.length;
    let i = n - 1;
    while (i > 0 && this.worlds[i].start > s + EARLY) i--;
    const wrap = s + EARLY >= this.total; // the end of the film leads into its beginning
    if (wrap) i = 0;
    const cur = this.worlds[i], next = this.worlds[(i + 1) % n];
    const tau = wrap ? s - this.total : s - cur.start, tauNext = tau - cur.D;
    cur.update(tau);
    next.update(tauNext);
    const stCur = this.state(cur, tau), stNext = this.state(next, tauNext);
    this.target(cur, stCur);
    this.target(next, stNext);

    this.pose(this.camera, cur, tau, !!cur.mod.rollIn, !!next.mod.rollIn);
    // the same eye, seen from the next world: its entrance (z = 0) is this world's portal (z = -L)
    this.camNext.copy(this.camera);
    this.camNext.position.z += cur.L;
    this.camNext.updateMatrixWorld();

    // the travellers: the change with its trail, plus what the world sends along
    const lb = tau / BEAT;
    const near = (t) => Math.min(t - cur.start, cur.mod.noExit ? 1e9 : cur.start + cur.D - t);
    const items = [this.cubeAt(s, near(s))];
    const wide = !['wire', 'none'].includes(stCur.carryStyle);
    for (let k = 1; k <= (wide ? 3 : TRAIL); k++) {
      const dt = k * (wide ? 0.13 : 0.07);
      const g = this.cubeAt(s - dt, near(s - dt));
      items.push({ ...g, z: g.z + V * dt, scale: g.scale * (wide ? 0.62 ** k : 1 - k * 0.15), ghost: true });
    }
    // the change may settle somewhere in this world (the end of the film)
    const land = cur.landing?.(tau);
    if (land && land.k > 0) {
      const c = this.camera.position, it = items[0], k = land.k;
      items[0] = { x: it.x + (land.x - c.x - it.x) * k, y: it.y + (land.y - c.y - it.y) * k, z: it.z + (land.z - c.z - it.z) * k, spin: it.spin * (1 - k) + 0.6 * k, scale: it.scale + (1 - it.scale) * k };
      items[0].scale *= 1 - (land.gone ?? 0); // at the very end it goes dark with everything else
      for (let j = 1; j < items.length; j++) items[j].scale *= 1 - k;
    }
    while (items.length < 1 + TRAIL) items.push(null);
    items.push(...(cur.carry?.(tau) ?? []));
    const place = (group, cam, mod) => {
      const style = mod.carryStyle;
      group.visible = style !== 'none';
      group.children.forEach((slot, k) => {
        const it = items[k];
        slot.visible = !!it;
        if (!it) return;
        slot.position.set(cam.position.x + it.x, cam.position.y + it.y, cam.position.z + it.z);
        slot.rotation.set(it.spin * 0.5, it.spin, 0);
        slot.scale.setScalar(it.scale ?? 1);
        slot.children.forEach((body, j) => {
          body.visible = this.styles[j] === style;
          if (!body.visible) return;
          if (style === 'orb') body.material.color.setHex(mod.carryColor), body.material.emissive.setHex(mod.carryColor);
          else if (style !== 'crate') body.material.color.setHex(mod.carryColor);
        });
      });
    };
    place(this.carryHere, this.camera, stCur);
    place(this.carryNext, this.camNext, stNext);
    this.clipHere.constant = cur.L;
    cur.scene.add(this.carryHere);
    next.scene.add(this.carryNext);

    const R = this.renderer;
    // 1) the next world in its own resolution (its own portal shows only a flat colour), developed to full size
    next.portal.mat.uniforms.uFlat.value = 1;
    next.onPass?.({ cam: this.camNext, items, side: 'next' });
    R.clippingPlanes = this.clipNext;
    R.setRenderTarget(next.rt);
    R.render(next.scene, this.camNext);
    R.clippingPlanes = this.clipNone;
    this.develop(next, this.full, null, tauNext);
    // 2) this world; its portal is a hole
    cur.portal.mat.uniforms.uFlat.value = 0;
    cur.onPass?.({ cam: this.camera, items, side: 'here' });
    R.setRenderTarget(cur.rt);
    R.render(cur.scene, this.camera);
    // 3) to the screen: this world developed, the next one laid into the hole
    this.develop(cur, null, this.full.texture, tau);

    // glow: a small blurred copy laid over the picture (CSS blend mode "screen"); its strength belongs to the era
    const gNow = stCur.glow, gNext = stNext.glow;
    const k = ease((tau - (cur.D - 1.2)) / 1.2);
    this.glow.style.opacity = (gNow + (gNext - gNow) * k).toFixed(3);
    const g = this.glowCtx;
    g.filter = 'blur(5px)';
    g.drawImage(this.canvas, 0, 0, this.glow.width, this.glow.height);

    // the label in the corner: a year that runs towards the next world's year, or a world's own text
    const y0 = cur.mod.year, y1 = i === n - 1 ? END_YEAR ?? y0 : next.mod.year ?? y0;
    const label = typeof y0 === 'number' ? Math.floor(y0 + (y1 - y0) * clamp(tau / cur.D)) : cur.mod.label ?? '';
    return { world: cur.mod.id, tau, beat: lb, label };
  }
}
