// World 1 "Oszilloskop 1962" - the intro. Before pictures there was one glowing line on a tube.
// The machine's voice makes the line tremble ("Achtung. Wir sind jetzt ein KI-Unternehmen."), the sequencer
// makes it swing. Far away a green point: the first gate. It grows until we fly through it into 1970.
import * as THREE from 'three';
import { clamp, ease, lines, MONO, over, rectXY, sign } from '../kit.js';
import { makePortal } from '../portal.js';
import { BEAT, EYE, LINES, OFFSET, V } from '../song.js';

export const id = 'oszi';
export const beats = OFFSET / BEAT + 72; // from the first sample of the song to beat 72
export const year = 1962;
export const carryStyle = 'none'; // the change does not exist yet
export const glow = 1.0;
export const flight = { sway: 0 };

const GREEN = 0x4dff88;
const VOICE = [LINES.achtung, LINES.ki, LINES.fragen];
const SAID = [[9.08, 9.7], [12.72, 14.9], [18.4, 20.1]]; // when the voice speaks (song seconds)

const FRAG = /* glsl */ `
  uniform float uT, uVoice, uPulse, uMusic, uFade;
  varying vec2 vUv;
  void main() {
    vec2 p = (vUv - 0.5) * vec2(3.556, 2.0); // -1..1 high
    float f = 0.07 * uVoice * sin(p.x * 9.0 + uT * 5.0) * sin(p.x * 31.0 + uT * 13.0)
            + 0.22 * uMusic * uPulse * sin(p.x * 4.2 - uT * 3.0)
            + 0.05 * uMusic * sin(p.x * 12.0 + uT * 7.0);
    float d = abs(p.y - f);
    float line = smoothstep(0.016, 0.0, d) + 0.3 * exp(-d * 16.0);
    float head = fract(uT * 0.45) * 3.9 - 1.95; // the beam sweeps; behind it the trace fades
    line *= 0.4 + 0.6 * exp(-max(head - p.x, 0.0) * 1.4) * step(p.x, head) + 0.25 * step(head, p.x) * exp(-(p.x - head) * 0.4);
    vec2 g = abs(fract(p * 4.0) - 0.5);
    float grid = (smoothstep(0.49, 0.5, max(g.x, g.y))) * 0.07;
    float tube = smoothstep(1.02, 0.86, length(p * vec2(0.52, 0.95))); // the round edge of the tube
    float a = clamp((line + grid) * tube, 0.0, 1.0) * uFade;
    gl_FragColor = vec4(vec3(0.3, 1.0, 0.5) * (1.0 + line), a);
  }`;

export function build({ t0, L, D }) {
  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0x000000);

  // everything on the tube travels with the camera
  const hud = new THREE.Group();
  scene.add(hud);
  const uniforms = { uT: { value: 0 }, uVoice: { value: 0 }, uPulse: { value: 0 }, uMusic: { value: 0 }, uFade: { value: 1 } };
  const scope = new THREE.Mesh(
    new THREE.PlaneGeometry(6.6, 3.72),
    over(new THREE.ShaderMaterial({
      uniforms,
      vertexShader: 'varying vec2 vUv; void main() { vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }',
      fragmentShader: FRAG,
      depthTest: false,
      depthWrite: false,
    })),
  );
  scope.position.z = -3.05;
  scope.renderOrder = 10;
  hud.add(scope);
  const rows = [[1.02, 0.2], [0.72, 0.15], [0.46, 0.15]];
  const texts = VOICE.map((line, i) => {
    const s = sign(line.words, line.at.map((x) => x - t0), { z: -3.0, y: rows[i][0], size: rows[i][1], font: MONO, color: 0x7dffa8, posts: false });
    s.group.traverse((o) => o.isMesh && ((o.material.depthTest = false), (o.material.fog = false), (o.renderOrder = 11)));
    hud.add(s.group);
    return s;
  });

  // the point in the distance: the first gate
  const fa = [];
  rectXY(fa, 0, 1.7, -L, 5, 3.4);
  rectXY(fa, 0, 1.7, -L, 5.7, 4.1);
  const frame = lines(fa, { color: GREEN, width: 0.12 });
  frame.material.fog = false;
  scene.add(frame);
  const portal = makePortal({ shape: 'rect', w: 5, h: 3.4, flat: 0x000000 });
  portal.mesh.position.set(0, 1.7, -L);
  scene.add(portal.mesh);

  const update = (tau) => {
    hud.position.set(0, EYE, -V * tau);
    const song = tau + t0, b = tau / BEAT;
    uniforms.uT.value = tau;
    uniforms.uFade.value = 1 - ease((tau - (D - 2.2)) / 1.9); // the tube goes dark before we fly through the gate
    uniforms.uPulse.value = Math.exp(-(b - Math.floor(b)) * 3);
    uniforms.uMusic.value = ease(song / 6) * (1 - 0.6 * ease((song - 30) / 6)); // the sequencer starts up; the line calms before the gate
    uniforms.uVoice.value = Math.max(...SAID.map(([a, e]) => clamp((song - a) / 0.08) * clamp((e - song) / 0.25)));
    texts.forEach((s) => s.update(tau));
    const gone = song > 27;
    texts.forEach((s) => (s.group.visible = !gone));
  };
  return { scene, portal, update };
}
