// The portal: a flat opening that shows the NEXT world.
//
// The opening itself draws nothing: it writes alpha 0 ("hole") into the world's picture. The engine has drawn the
// next world before, from the place where the camera would stand in it (same offset to the portal, same view
// direction), in that world's own resolution and look, and lays it into the hole pixel for pixel. So what is seen
// through the portal is exactly the frame that follows the crossing: no cut, even between two graphics eras.
import * as THREE from 'three';

const VERT = /* glsl */ `
  varying vec2 vP;
  void main() {
    vP = position.xy;
    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
  }`;
const FRAG = /* glsl */ `
  uniform vec2 uHalf;
  uniform float uOpen;
  uniform float uFlat;
  uniform vec3 uFlatCol;
  uniform vec3 uVeil;
  uniform vec3 uRim;
  varying vec2 vP;
  void main() {
    if (uFlat > 0.5) { gl_FragColor = vec4(uFlatCol, 1.0); return; }
    // iris: the opening grows from the centre
    float R = length(uHalf) * uOpen * 1.02;
    float d = length(vP);
    float inside = uOpen >= 0.999 ? 1.0 : 1.0 - smoothstep(R - 0.02, R + 0.02, d);
    vec3 col = uVeil * (1.0 - inside);
    if (uOpen > 0.001 && uOpen < 0.999) col += uRim * smoothstep(0.1, 0.0, abs(d - R));
    gl_FragColor = vec4(col, 1.0 - inside);
  }`;

/**
 * shape 'rect' (w, h) or 'circle' (r). The mesh stands in the XY plane; place it on the road at the world's end.
 * flat = the colour it shows when it is itself seen through another portal (no world inside a world inside a world).
 */
export function makePortal({ shape = 'rect', w = 5, h = 3.4, r = 2.3, veil = 0x000000, rim = 0xffffff, flat = 0x101010 } = {}) {
  const geo = shape === 'circle' ? new THREE.CircleGeometry(r, 64) : new THREE.PlaneGeometry(w, h);
  const mat = new THREE.ShaderMaterial({
    vertexShader: VERT,
    fragmentShader: FRAG,
    uniforms: {
      uHalf: { value: shape === 'circle' ? new THREE.Vector2(r, 0) : new THREE.Vector2(w / 2, h / 2) },
      uOpen: { value: 1 },
      uFlat: { value: 0 },
      uFlatCol: { value: new THREE.Color(flat) },
      uVeil: { value: new THREE.Color(veil) },
      uRim: { value: new THREE.Color(rim) },
    },
  });
  const mesh = new THREE.Mesh(geo, mat);
  mesh.frustumCulled = false;
  return { mesh, mat, setOpen: (v) => (mat.uniforms.uOpen.value = v) };
}
