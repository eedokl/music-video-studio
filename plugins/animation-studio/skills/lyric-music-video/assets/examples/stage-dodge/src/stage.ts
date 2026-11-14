// Rock concert stage: platform, LED wall, truss with moving-head beams, amps, drums,
// smoke, pyro and a crowd. All animation is a function of song time + audio bands.

import * as THREE from 'three';
import type { Bands } from './audio';
import type { SectionId } from './lyrics';

const hash = (n: number) => {
  const x = Math.sin(n * 91.7 + 17.3) * 43758.5453;
  return x - Math.floor(x);
};

const ACCENT: Record<SectionId, [string, string]> = {
  intro: ['#ff1e1e', '#3a00ff'],
  verse1: ['#00d5ff', '#0040ff'],
  chorus: ['#ff2a6d', '#ffb000'],
  verse2: ['#a24dff', '#00e5ff'],
  bridge: ['#ff6a00', '#ff0000'],
  final: ['#ffd000', '#ff2a6d'],
  outro: ['#ff1e1e', '#3a00ff'],
};

function canvasTex(w: number, h: number, draw: (ctx: CanvasRenderingContext2D) => void) {
  const c = document.createElement('canvas');
  c.width = w;
  c.height = h;
  draw(c.getContext('2d')!);
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  return t;
}

export class Stage {
  readonly group = new THREE.Group();
  readonly accent = new THREE.Color('#ff1e1e');
  readonly accent2 = new THREE.Color('#3a00ff');
  private wallMat!: THREE.ShaderMaterial;
  private beams: { pivot: THREE.Group; mat: THREE.ShaderMaterial; i: number }[] = [];
  private key!: THREE.SpotLight;
  private rimL!: THREE.SpotLight;
  private rimR!: THREE.SpotLight;
  private pyroLight!: THREE.PointLight;
  private crowdBodies!: THREE.InstancedMesh;
  private crowdHeads!: THREE.InstancedMesh;
  private crowdArms!: THREE.InstancedMesh;
  private crowd: { x: number; z: number; ph: number; arms: boolean; h: number }[] = [];
  private smoke: THREE.Sprite[] = [];
  private pyro!: THREE.Points;
  private floorMat!: THREE.MeshStandardMaterial;
  private tmp = new THREE.Object3D();
  private target = new THREE.Object3D();

  constructor() {
    this.buildPlatform();
    this.buildWall();
    this.buildTruss();
    this.buildBackline();
    this.buildLights();
    this.buildCrowd();
    this.buildSmoke();
    this.buildPyro();
  }

  private buildPlatform() {
    this.floorMat = new THREE.MeshStandardMaterial({ color: '#0d0d10', roughness: 0.22, metalness: 0.4 });
    const deck = new THREE.Mesh(new THREE.BoxGeometry(17, 0.8, 9), this.floorMat);
    deck.position.set(0, -0.4, -0.8);
    deck.receiveShadow = true;
    this.group.add(deck);
    // glowing stage edge
    const edge = new THREE.Mesh(new THREE.BoxGeometry(17, 0.06, 0.06), new THREE.MeshBasicMaterial({ color: '#ffffff', toneMapped: false }));
    edge.position.set(0, -0.03, 3.68);
    edge.userData.edge = true;
    this.group.add(edge);
    // audience floor
    const ground = new THREE.Mesh(new THREE.PlaneGeometry(120, 120), new THREE.MeshStandardMaterial({ color: '#050507', roughness: 0.9 }));
    ground.rotation.x = -Math.PI / 2;
    ground.position.y = -0.8;
    ground.receiveShadow = true;
    this.group.add(ground);
    // wedge monitors at the front edge
    const wedgeMat = new THREE.MeshStandardMaterial({ color: '#151515', roughness: 0.5 });
    for (const x of [-3.5, 0, 3.5]) {
      const w = new THREE.Mesh(new THREE.BoxGeometry(1.0, 0.4, 0.6), wedgeMat);
      w.position.set(x, 0.2, 3.1);
      w.rotation.x = -0.5;
      w.castShadow = true;
      this.group.add(w);
    }
  }

  private buildWall() {
    const logo = canvasTex(2048, 1024, (ctx) => {
      ctx.fillStyle = '#000';
      ctx.fillRect(0, 0, 2048, 1024);
      // shield
      ctx.save();
      ctx.translate(1024, 430);
      ctx.beginPath();
      ctx.moveTo(0, -300);
      ctx.bezierCurveTo(170, -230, 250, -230, 260, -220);
      ctx.bezierCurveTo(270, 40, 170, 200, 0, 300);
      ctx.bezierCurveTo(-170, 200, -270, 40, -260, -220);
      ctx.bezierCurveTo(-250, -230, -170, -230, 0, -300);
      ctx.lineWidth = 34;
      ctx.strokeStyle = '#fff';
      ctx.stroke();
      // padlock
      ctx.fillStyle = '#fff';
      ctx.fillRect(-90, -20, 180, 150);
      ctx.lineWidth = 30;
      ctx.beginPath();
      ctx.arc(0, -20, 62, Math.PI, 0);
      ctx.stroke();
      ctx.fillStyle = '#000';
      ctx.beginPath();
      ctx.arc(0, 40, 22, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillRect(-9, 40, 18, 55);
      ctx.restore();
      ctx.fillStyle = '#fff';
      ctx.font = '120px "Black Ops One", Impact, sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText('STAGE DODGE', 1024, 900);
    });
    this.wallMat = new THREE.ShaderMaterial({
      uniforms: {
        uTime: { value: 0 },
        uBass: { value: 0 },
        uMid: { value: 0 },
        uHigh: { value: 0 },
        uPulse: { value: 0 },
        uC1: { value: this.accent },
        uC2: { value: this.accent2 },
        uLogo: { value: logo },
        uMode: { value: 0 },
      },
      vertexShader: `varying vec2 vUv; void main(){ vUv = uv; gl_Position = projectionMatrix*modelViewMatrix*vec4(position,1.0);} `,
      fragmentShader: `
        uniform float uTime, uBass, uMid, uHigh, uPulse, uMode; uniform vec3 uC1, uC2; uniform sampler2D uLogo; varying vec2 vUv;
        float h(float n){ return fract(sin(n*12.9898)*43758.5453); }
        void main(){
          vec2 res = vec2(192.0, 88.0);
          vec2 cell = floor(vUv*res); vec2 f = fract(vUv*res) - 0.5;
          float dotMask = smoothstep(0.5, 0.25, length(f));
          vec2 uv = (cell + 0.5)/res;
          // equalizer bars
          float col = floor(uv.x*32.0);
          float lvl = 0.15 + 0.85*(mix(uBass, uHigh, col/32.0)*0.8 + 0.25*sin(uTime*3.0 + col*0.7)*uMid + h(col + floor(uTime*8.0))*0.15);
          float bars = step(uv.y, lvl*0.9) * step(0.15, fract(uv.x*32.0));
          vec3 eq = mix(uC2, uC1, uv.y) * bars;
          // logo
          vec3 logo = texture2D(uLogo, uv).rgb;
          float l = logo.r;
          vec3 c = eq*0.55 + l*mix(uC1, vec3(1.0), 0.35)*(0.7 + uPulse*0.8);
          // scrolling scanline + alarm sweep in mode 1 (bridge)
          c += uC1 * 0.25 * smoothstep(0.02, 0.0, abs(fract(uv.y*2.0 - uTime*0.5) - 0.5));
          c = mix(c, vec3(1.0,0.05,0.0)*(0.5+0.5*sin(uTime*9.0)), uMode*0.35*(1.0-l));
          gl_FragColor = vec4(c * dotMask * 0.85, 1.0);
        }`,
    });
    const wall = new THREE.Mesh(new THREE.PlaneGeometry(16, 7.3), this.wallMat);
    wall.position.set(0, 4.3, -5.2);
    this.group.add(wall);
    const frame = new THREE.Mesh(new THREE.BoxGeometry(16.4, 7.7, 0.3), new THREE.MeshStandardMaterial({ color: '#111', metalness: 0.8, roughness: 0.4 }));
    frame.position.set(0, 4.3, -5.4);
    this.group.add(frame);
  }

  private buildTruss() {
    const mat = new THREE.MeshStandardMaterial({ color: '#9aa0a8', metalness: 1, roughness: 0.35 });
    const tube = (len: number) => new THREE.CylinderGeometry(0.035, 0.035, len, 6);
    const trussBeam = (len: number) => {
      const g = new THREE.Group();
      for (const [y, z] of [[-0.2, -0.2], [-0.2, 0.2], [0.2, -0.2], [0.2, 0.2]]) {
        const m = new THREE.Mesh(tube(len), mat);
        m.position.set(0, y, z);
        g.add(m);
      }
      for (let k = -len / 2; k < len / 2; k += 0.45) {
        const d = new THREE.Mesh(tube(0.57), mat);
        d.position.set(0, 0, 0);
        d.position.y = k;
        d.rotation.x = Math.PI / 4;
        g.add(d);
      }
      return g;
    };
    for (const x of [-8.6, 8.6]) {
      const tower = trussBeam(9);
      tower.position.set(x, 4.2, 1.2);
      this.group.add(tower);
    }
    for (const z of [-1.2, 2.6]) {
      const top = trussBeam(17.6);
      top.rotation.z = Math.PI / 2;
      top.position.set(0, 8.4, z);
      this.group.add(top);
    }
    // moving-head beams
    const beamGeo = new THREE.ConeGeometry(1.3, 11, 32, 1, true);
    beamGeo.translate(0, -5.5, 0);
    const headGeo = new THREE.BoxGeometry(0.35, 0.35, 0.35);
    const headMat = new THREE.MeshStandardMaterial({ color: '#222', metalness: 0.6, roughness: 0.4 });
    for (let i = 0; i < 10; i++) {
      const z = i % 2 ? -1.2 : 2.6;
      const x = -7 + (i / 9) * 14;
      const pivot = new THREE.Group();
      pivot.position.set(x, 8.1, z);
      const mat = new THREE.ShaderMaterial({
        transparent: true,
        depthWrite: false,
        blending: THREE.AdditiveBlending,
        side: THREE.DoubleSide,
        uniforms: { uColor: { value: new THREE.Color() }, uI: { value: 1 } },
        vertexShader: `varying vec2 vUv; varying vec3 vN; varying vec3 vV; void main(){ vUv = uv; vec4 mv = modelViewMatrix*vec4(position,1.0); vN = normalize(normalMatrix*normal); vV = normalize(-mv.xyz); gl_Position = projectionMatrix*mv; }`,
        fragmentShader: `uniform vec3 uColor; uniform float uI; varying vec2 vUv; varying vec3 vN; varying vec3 vV;
          void main(){ float edge = pow(abs(dot(vN, vV)), 1.6); float fall = pow(vUv.y, 1.4); gl_FragColor = vec4(uColor * uI, edge*fall*0.35*uI); }`,
      });
      const cone = new THREE.Mesh(beamGeo, mat);
      cone.rotation.x = Math.PI; // point down
      cone.position.y = 0;
      const head = new THREE.Mesh(headGeo, headMat);
      pivot.add(head);
      const aim = new THREE.Group();
      aim.add(cone);
      cone.rotation.x = 0;
      // flip so the cone (apex at origin, extends -y) hangs down
      pivot.add(aim);
      this.group.add(pivot);
      this.beams.push({ pivot: aim, mat, i });
    }
  }

  private buildBackline() {
    const grille = canvasTex(256, 256, (ctx) => {
      ctx.fillStyle = '#141414';
      ctx.fillRect(0, 0, 256, 256);
      ctx.strokeStyle = '#262626';
      ctx.lineWidth = 3;
      for (let i = -256; i < 512; i += 10) {
        ctx.beginPath();
        ctx.moveTo(i, 0);
        ctx.lineTo(i + 256, 256);
        ctx.stroke();
      }
      ctx.fillStyle = '#c9c9c9';
      ctx.font = 'italic bold 30px serif';
      ctx.fillText('AMP', 12, 236);
    });
    const ampMat = [
      new THREE.MeshStandardMaterial({ color: '#0b0b0b', roughness: 0.6 }),
      new THREE.MeshStandardMaterial({ color: '#0b0b0b', roughness: 0.6 }),
      new THREE.MeshStandardMaterial({ color: '#0b0b0b', roughness: 0.6 }),
      new THREE.MeshStandardMaterial({ color: '#0b0b0b', roughness: 0.6 }),
      new THREE.MeshStandardMaterial({ map: grille, roughness: 0.8 }),
      new THREE.MeshStandardMaterial({ color: '#0b0b0b', roughness: 0.6 }),
    ];
    for (const x of [-6.6, -5.3, 5.3, 6.6]) {
      for (let k = 0; k < 2; k++) {
        const cab = new THREE.Mesh(new THREE.BoxGeometry(1.25, 1.25, 0.8), ampMat);
        cab.position.set(x, 0.63 + k * 1.27, -3.8);
        cab.castShadow = true;
        this.group.add(cab);
      }
      const head = new THREE.Mesh(new THREE.BoxGeometry(1.25, 0.45, 0.7), new THREE.MeshStandardMaterial({ color: '#1a1a1a', roughness: 0.4, metalness: 0.3 }));
      head.position.set(x, 2.8, -3.8);
      this.group.add(head);
    }
    // drum riser + kit
    const riser = new THREE.Mesh(new THREE.BoxGeometry(4, 0.6, 2.6), new THREE.MeshStandardMaterial({ color: '#101014', roughness: 0.4 }));
    riser.position.set(0, 0.3, -3.6);
    this.group.add(riser);
    const kickHead = canvasTex(512, 512, (ctx) => {
      ctx.fillStyle = '#f2f2f2';
      ctx.beginPath();
      ctx.arc(256, 256, 250, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = '#c4001d';
      ctx.font = '96px "Black Ops One", Impact, sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText('THE', 256, 230);
      ctx.fillStyle = '#111';
      ctx.fillText('BAND', 256, 340);
    });
    const shell = new THREE.MeshStandardMaterial({ color: '#7a0010', roughness: 0.25, metalness: 0.5 });
    const kick = new THREE.Mesh(new THREE.CylinderGeometry(0.55, 0.55, 0.55, 32), shell);
    kick.rotation.x = Math.PI / 2;
    kick.position.set(0, 1.15, -3.2);
    const face = new THREE.Mesh(new THREE.CircleGeometry(0.54, 40), new THREE.MeshStandardMaterial({ map: kickHead, color: '#8a8a8a', roughness: 0.8 }));
    face.position.set(0, 1.15, -2.92);
    this.group.add(kick, face);
    const brass = new THREE.MeshStandardMaterial({ color: '#c9a227', metalness: 1, roughness: 0.25 });
    for (const [x, y, r] of [[-1.2, 2.1, 0.45], [1.3, 2.3, 0.5], [0.9, 1.8, 0.35]] as const) {
      const cym = new THREE.Mesh(new THREE.CylinderGeometry(r, r, 0.02, 24), brass);
      cym.position.set(x, y, -3.4);
      cym.rotation.x = 0.3;
      this.group.add(cym);
    }
    for (const [x, y] of [[-0.6, 1.75], [0.6, 1.75], [1.4, 1.2]] as const) {
      const tom = new THREE.Mesh(new THREE.CylinderGeometry(0.25, 0.25, 0.3, 20), shell);
      tom.position.set(x, y, -3.3);
      tom.rotation.x = 0.4;
      this.group.add(tom);
    }
  }

  private buildLights() {
    this.group.add(new THREE.AmbientLight('#1a1a2a', 0.6));
    this.group.add(new THREE.HemisphereLight('#4060ff', '#200000', 0.25));
    this.group.add(this.target);
    this.key = new THREE.SpotLight('#ffffff', 220, 40, 0.32, 0.5, 1.4);
    this.key.position.set(0, 9, 12);
    this.key.target = this.target;
    this.key.castShadow = true;
    this.key.shadow.mapSize.set(2048, 2048);
    this.key.shadow.bias = -0.0005;
    this.group.add(this.key);
    this.rimL = new THREE.SpotLight('#ff0040', 260, 30, 0.45, 0.6, 1.3);
    this.rimL.position.set(-6, 8.2, -2);
    this.rimL.target = this.target;
    this.rimR = new THREE.SpotLight('#0040ff', 260, 30, 0.45, 0.6, 1.3);
    this.rimR.position.set(6, 8.2, -2);
    this.rimR.target = this.target;
    this.group.add(this.rimL, this.rimR);
    this.pyroLight = new THREE.PointLight('#ff7a1a', 0, 25, 1.5);
    this.pyroLight.position.set(0, 2, 3);
    this.group.add(this.pyroLight);
  }

  private buildCrowd() {
    const N = 360;
    for (let i = 0; i < N; i++) {
      const row = Math.floor(i / 30);
      const x = (i % 30) - 14.5 + (hash(i) - 0.5) * 0.8;
      const z = 5.2 + row * 1.05 + (hash(i * 2) - 0.5) * 0.5;
      this.crowd.push({ x: x * 0.95, z, ph: hash(i * 3), arms: hash(i * 4) < 0.45, h: 0.9 + hash(i * 5) * 0.2 });
    }
    const dark = new THREE.MeshStandardMaterial({ color: '#08080a', roughness: 0.9 });
    this.crowdBodies = new THREE.InstancedMesh(new THREE.CapsuleGeometry(0.22, 0.75, 4, 8), dark, N);
    this.crowdHeads = new THREE.InstancedMesh(new THREE.SphereGeometry(0.14, 10, 8), dark, N);
    this.crowdArms = new THREE.InstancedMesh(new THREE.CapsuleGeometry(0.05, 0.6, 3, 6), dark, N * 2);
    this.group.add(this.crowdBodies, this.crowdHeads, this.crowdArms);
  }

  private buildSmoke() {
    const tex = canvasTex(256, 256, (ctx) => {
      const g = ctx.createRadialGradient(128, 128, 0, 128, 128, 128);
      g.addColorStop(0, 'rgba(255,255,255,0.55)');
      g.addColorStop(0.6, 'rgba(255,255,255,0.15)');
      g.addColorStop(1, 'rgba(255,255,255,0)');
      ctx.fillStyle = g;
      ctx.fillRect(0, 0, 256, 256);
    });
    for (let i = 0; i < 14; i++) {
      const s = new THREE.Sprite(new THREE.SpriteMaterial({ map: tex, transparent: true, depthWrite: false, opacity: 0.07 }));
      s.scale.setScalar(5 + hash(i) * 4);
      this.smoke.push(s);
      this.group.add(s);
    }
  }

  private buildPyro() {
    const N = 2 * 220;
    const g = new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.BufferAttribute(new Float32Array(N * 3), 3));
    g.setAttribute('color', new THREE.BufferAttribute(new Float32Array(N * 3), 3));
    this.pyro = new THREE.Points(g, new THREE.PointsMaterial({ size: 0.28, vertexColors: true, transparent: true, blending: THREE.AdditiveBlending, depthWrite: false, toneMapped: false }));
    this.pyro.frustumCulled = false;
    this.group.add(this.pyro);
  }

  /** beat: beat position; singerPos: where the singer is; hit: 0..1 flash from a punched word. */
  update(t: number, beat: number, b: Bands, section: SectionId, singerPos: THREE.Vector3, hit: number) {
    const [c1, c2] = ACCENT[section];
    this.accent.lerp(new THREE.Color(c1), 0.05);
    this.accent2.lerp(new THREE.Color(c2), 0.05);
    const loud = section === 'chorus' || section === 'final';
    const ph = beat - Math.floor(beat);
    const pulse = Math.exp(-ph * 5);

    // LED wall
    const u = this.wallMat.uniforms;
    u.uTime.value = t;
    u.uBass.value = b.bass;
    u.uMid.value = b.mid;
    u.uHigh.value = b.high;
    u.uPulse.value = pulse * (loud ? 1 : 0.5) + hit * 0.6;
    u.uMode.value += ((section === 'bridge' ? 1 : 0) - u.uMode.value) * 0.05;

    // moving heads: sweep in figure-eights, snap on the beat
    for (const bm of this.beams) {
      const k = bm.i;
      const sweep = loud ? 1 : 0.6;
      bm.pivot.rotation.x = Math.sin(t * 0.9 + k) * 0.5 * sweep + (k % 2 ? 0.35 : -0.25);
      bm.pivot.rotation.z = Math.sin(t * 0.6 + k * 1.7 + Math.floor(beat / 4) * 0.8) * 0.6 * sweep;
      bm.mat.uniforms.uColor.value.copy(k % 2 ? this.accent : this.accent2);
      bm.mat.uniforms.uI.value = 0.55 + pulse * (loud ? 0.9 : 0.4) + (section === 'bridge' && Math.floor(beat * 2) % 2 ? 0.8 : 0);
    }

    // real lights follow the singer
    this.target.position.set(singerPos.x, 1.4, singerPos.z);
    this.key.intensity = 60 + hit * 140 + (section === "bridge" ? pulse * 90 : 0);
    this.rimL.color.copy(this.accent);
    this.rimR.color.copy(this.accent2);
    this.rimL.intensity = 80 + pulse * 110 * (loud ? 1 : 0.4);
    this.rimR.intensity = 80 + (1 - pulse) * 60;

    // stage edge glow
    this.group.children.forEach((c) => {
      if (c.userData.edge) ((c as THREE.Mesh).material as THREE.MeshBasicMaterial).color.copy(this.accent).multiplyScalar(1.5 + pulse);
    });

    // crowd jumps on the beat (harder in choruses)
    const jump = loud ? 0.28 : 0.12;
    this.crowd.forEach((p, i) => {
      const hop = Math.pow(Math.max(0, Math.cos((beat + p.ph * 0.15) * Math.PI * 2)), 6) * jump;
      const y = -0.8 + 0.6 * p.h + hop;
      this.tmp.position.set(p.x, y + 0.2, p.z);
      this.tmp.rotation.set(0, 0, Math.sin(t + p.ph * 6) * 0.05);
      this.tmp.scale.set(1, p.h, 1);
      this.tmp.updateMatrix();
      this.crowdBodies.setMatrixAt(i, this.tmp.matrix);
      this.tmp.position.y = y + 0.95 * p.h + 0.15;
      this.tmp.scale.setScalar(1);
      this.tmp.updateMatrix();
      this.crowdHeads.setMatrixAt(i, this.tmp.matrix);
      for (const s of [-1, 1]) {
        const up = p.arms && (loud || hash(i * 9) < 0.3);
        const wave = up ? Math.sin(beat * Math.PI + p.ph * 4) * 0.25 : 0;
        this.tmp.position.set(p.x + s * 0.25, y + (up ? 1.25 : 0.55) * p.h, p.z);
        this.tmp.rotation.set(0, 0, up ? s * (0.25 + wave) : s * 0.1);
        this.tmp.scale.setScalar(up ? 1 : 0.9);
        this.tmp.updateMatrix();
        this.crowdArms.setMatrixAt(i * 2 + (s > 0 ? 1 : 0), this.tmp.matrix);
      }
    });
    this.crowdBodies.instanceMatrix.needsUpdate = true;
    this.crowdHeads.instanceMatrix.needsUpdate = true;
    this.crowdArms.instanceMatrix.needsUpdate = true;

    // smoke drifts across the floor, tinted by the lights
    this.smoke.forEach((s, i) => {
      const x = ((t * (0.15 + hash(i) * 0.2) + hash(i * 3) * 20) % 20) - 10;
      s.position.set(x, 0.4 + hash(i * 5) * 0.8, -3 + hash(i * 7) * 6);
      (s.material as THREE.SpriteMaterial).color.copy(i % 2 ? this.accent : this.accent2).lerp(new THREE.Color('#ffffff'), 0.5);
    });

    // pyro: fire columns on every bar in loud sections
    const pos = this.pyro.geometry.attributes.position as THREE.BufferAttribute;
    const col = this.pyro.geometry.attributes.color as THREE.BufferAttribute;
    const bar = beat / 4;
    const age = ((bar - Math.floor(bar)) * 4 * 60) / 128.6; // seconds since the bar started
    const firing = (loud && Math.floor(bar) % 2 === 0) || (section === 'final' && age < 1.2);
    let glow = 0;
    for (let c = 0; c < 2; c++) {
      const x0 = c ? 5.6 : -5.6;
      for (let i = 0; i < 220; i++) {
        const k = c * 220 + i;
        const born = hash(k) * 0.5;
        const a = age - born;
        if (!firing || a < 0 || a > 0.9) {
          pos.setXYZ(k, 0, -99, 0);
          continue;
        }
        const v = 9 + hash(k * 3) * 5;
        pos.setXYZ(k, x0 + (hash(k * 5) - 0.5) * 0.6 * (1 + a * 2), a * v - 4 * a * a, 3.2 + (hash(k * 7) - 0.5) * 0.6);
        const f = 1 - a / 0.9;
        col.setXYZ(k, 2 * f, (0.6 + hash(k) * 0.5) * f, 0.1 * f);
        glow = Math.max(glow, f);
      }
    }
    pos.needsUpdate = true;
    col.needsUpdate = true;
    this.pyroLight.intensity = firing ? glow * 120 : 0;
  }
}
