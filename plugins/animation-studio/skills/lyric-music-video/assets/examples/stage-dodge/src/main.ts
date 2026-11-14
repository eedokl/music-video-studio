import * as THREE from 'three';
import { EffectComposer } from 'three/examples/jsm/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/examples/jsm/postprocessing/RenderPass.js';
import { UnrealBloomPass } from 'three/examples/jsm/postprocessing/UnrealBloomPass.js';
import { OutputPass } from 'three/examples/jsm/postprocessing/OutputPass.js';
import './style.css';
import { AudioEngine } from './audio';
import { Director } from './director';
import { LINES, SECTION_COLORS, SONG_END, beatAt, sectionAt } from './lyrics';
import type { SectionId } from './lyrics';
import { Singer, wanderX, wanderZ } from './singer';
import { Stage } from './stage';
import { ACTIONS, WordField, actionsNear } from './words';

const $ = <T extends HTMLElement>(id: string) => document.getElementById(id) as T;

// ?render=1 → MP4 export mode: no UI, frames rendered on request by scripts/render.mjs
const params = new URLSearchParams(location.search);
const RENDER = params.has('render');
if (RENDER) document.body.classList.add('render');

const renderer = new THREE.WebGLRenderer({ antialias: true, powerPreference: 'high-performance', preserveDrawingBuffer: RENDER });
renderer.setPixelRatio(RENDER ? 1 : Math.min(window.devicePixelRatio, 1.75));
renderer.setSize(window.innerWidth, window.innerHeight);
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.05;
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
$('stage').appendChild(renderer.domElement);

const scene = new THREE.Scene();
scene.background = new THREE.Color('#020205');
scene.fog = new THREE.FogExp2("#05050a", 0.018);
const camera = new THREE.PerspectiveCamera(50, window.innerWidth / window.innerHeight, 0.05, 300);

const stage = new Stage();
const singer = new Singer();
const words = new WordField();
scene.add(stage.group, singer.root, words.group);
const director = new Director(camera, new URLSearchParams(location.search).get('shot'));

const composer = new EffectComposer(renderer);
composer.addPass(new RenderPass(scene, camera));
const bloom = new UnrealBloomPass(new THREE.Vector2(window.innerWidth, window.innerHeight), 0.5, 0.45, 0.86);
composer.addPass(bloom);
composer.addPass(new OutputPass());

const songUrl = `${import.meta.env.BASE_URL}song.wav`;
const audio = new AudioEngine(songUrl);

window.addEventListener('resize', () => {
  camera.aspect = window.innerWidth / window.innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(window.innerWidth, window.innerHeight);
  composer.setSize(window.innerWidth, window.innerHeight);
});

// ---------- UI ----------
const startEl = $('start');
const title = $('title');
const credits = $('credits');
const caption = $('caption');
const bar = $('bar');
const fill = $('fill');
const timeEl = $('time');
const playBtn = $('play') as HTMLButtonElement;
const startAt = Number(params.get('t') ?? 0);

async function begin() {
  startEl.classList.add('gone');
  if (startAt > 0) audio.seek(startAt);
  await audio.start();
}
$('go').addEventListener('click', () => void begin());
playBtn.addEventListener('click', () => audio.toggle());
bar.addEventListener('click', (e) => {
  const r = bar.getBoundingClientRect();
  audio.seek(((e.clientX - r.left) / r.width) * audio.duration);
});
window.addEventListener('keydown', (e) => {
  if (e.code === 'Space') {
    e.preventDefault();
    if (startEl.classList.contains('gone')) audio.toggle();
    else void begin();
  }
  if (e.code === 'ArrowRight') audio.seek(audio.time + 5);
  if (e.code === 'ArrowLeft') audio.seek(audio.time - 5);
  if (e.code === 'KeyF') void document.documentElement.requestFullscreen?.();
  if (e.code === 'KeyH') document.body.classList.toggle('clean');
});
let idle = 0;
window.addEventListener('pointermove', () => {
  idle = 0;
  document.body.classList.remove('idle');
});
const fmt = (s: number) => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, '0')}`;
const window01 = (t: number, a: number, b: number, f: number) => Math.max(0, Math.min(1, (t - a) / f, (b - t) / f));
function setCard(el: HTMLElement, k: number) {
  el.style.opacity = k.toFixed(3);
  el.style.transform = `scale(${(0.92 + 0.08 * k).toFixed(4)})`;
}

// ---------- caption (current line, words light up as sung) ----------
let captionLine = -2;
let captionWords: HTMLElement[] = [];
function updateCaption(t: number) {
  const li = LINES.findIndex((l, i) => t >= l.t - 0.25 && t < Math.min(l.e + 0.6, LINES[i + 1]?.t - 0.25 || Infinity));
  if (li !== captionLine) {
    captionLine = li;
    caption.innerHTML = '';
    captionWords = [];
    if (li >= 0) {
      caption.style.setProperty('--accent', SECTION_COLORS[LINES[li].section]);
      LINES[li].text.split(' ').forEach((w) => {
        const s = document.createElement('span');
        s.textContent = w + ' ';
        caption.appendChild(s);
        captionWords.push(s);
      });
    }
  }
  if (li >= 0) {
    const l = LINES[li];
    captionWords.forEach((s, i) => s.classList.toggle('sung', t >= (l.words?.[i] ?? l.t)));
    caption.style.opacity = window01(t, l.t - 0.25, Math.min(l.e + 0.6, LINES[li + 1]?.t - 0.25 || Infinity), 0.15).toFixed(3);
  } else caption.style.opacity = '0';
}

// ---------- frame ----------
const ENERGY: Record<SectionId, number> = { intro: 0.3, verse1: 0.6, chorus: 1, verse2: 0.65, bridge: 0.85, final: 1, outro: 0.35 };
const HEADBANG: Record<SectionId, number> = { intro: 0, verse1: 0.1, chorus: 0.4, verse2: 0.15, bridge: 1, final: 0.5, outro: 0 };
const TITLE_END = LINES[0].t - 1.2;
const CREDITS_AT = LINES[LINES.length - 1].e + 2;
const singerPos = new THREE.Vector3();
let energy = 0.3;
let headbang = 0;
let singing = 0;

function step(t: number, dt: number, showUi: boolean) {
  const b = audio.update(dt);
  const sec = sectionAt(t);
  const beat = beatAt(t);
  const pulse = Math.exp(-(beat - Math.floor(beat)) * 5);

  const k = 1 - Math.exp(-dt * 2.5);
  energy += (ENERGY[sec.id] - energy) * k;
  headbang += (HEADBANG[sec.id] - headbang) * k;
  const inLine = LINES.some((l) => t >= l.t - 0.35 && t <= l.e + 0.25);
  singing += ((inLine ? 1 : 0) - singing) * (1 - Math.exp(-dt * 6));

  singerPos.set(wanderX(t), 0, wanderZ(t));
  const hit = words.update(t, beat, camera);
  singer.update(t, beat, energy, singing, headbang, actionsNear(t), stage.accent);
  stage.update(t, beat, b, sec.id, singerPos, hit);
  director.update(t, beat, sec.id, singerPos, hit, pulse * (sec.id === 'chorus' || sec.id === 'final' ? 1 : 0.4));

  bloom.strength = 0.35 + b.bass * 0.25 + hit * 0.35;
  composer.render();

  if (showUi) {
    updateCaption(t);
    setCard(title, window01(t, 0.8, TITLE_END, 1.0));
    setCard(credits, window01(t, CREDITS_AT, Infinity, 1.2));
  }
}

if (RENDER) {
  const w = window as unknown as Record<string, unknown>;
  w.__renderFrame = (t: number, dt: number) => {
    audio.renderTime = t;
    step(t, dt, true);
  };
  w.__duration = SONG_END;
  w.__actions = ACTIONS;
  void (async () => {
    await audio.loadOffline(songUrl);
    await document.fonts.load('130px "Black Ops One"');
    await document.fonts.ready;
    w.__ready = true;
  })();
} else {
  void document.fonts.load('130px "Black Ops One"');
  const clock = new THREE.Clock();
  let demo = 0;
  const frame = () => {
    const dt = Math.min(clock.getDelta(), 0.1);
    const started = startEl.classList.contains('gone');
    demo += dt;
    // behind the start screen the band keeps rocking (demo loop of the first chorus)
    const t = started ? audio.time : LINES[12].t + (demo % 14);
    step(t, dt, started);
    if (started) {
      fill.style.width = `${(t / audio.duration) * 100}%`;
      timeEl.textContent = `${fmt(t)} / ${fmt(audio.duration || SONG_END)}`;
      playBtn.textContent = audio.playing ? 'Pause' : 'Play';
    }
    idle += dt;
    document.body.classList.toggle('idle', idle > 2.5 && audio.playing);
    requestAnimationFrame(frame);
  };
  requestAnimationFrame(frame);
}
