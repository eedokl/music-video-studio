import * as THREE from 'three';
import { EffectComposer } from 'three/examples/jsm/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/examples/jsm/postprocessing/RenderPass.js';
import { UnrealBloomPass } from 'three/examples/jsm/postprocessing/UnrealBloomPass.js';
import { OutputPass } from 'three/examples/jsm/postprocessing/OutputPass.js';
import './style.css';
import { AudioEngine } from './audio';
import { FACTS, LINES, SECTION_COLORS, SONG_END, keywordsIn, sectionAt } from './lyrics';
import { PopupLayer } from './popups';
import { World } from './world';

const $ = <T extends HTMLElement>(id: string) => document.getElementById(id) as T;

// ?render=1 → MP4 export mode: no UI, frames rendered on request by scripts/render.mjs
const params = new URLSearchParams(location.search);
const RENDER = params.has('render');
if (RENDER) document.body.classList.add('render');

const renderer = new THREE.WebGLRenderer({ antialias: true, powerPreference: 'high-performance', preserveDrawingBuffer: RENDER });
renderer.setPixelRatio(RENDER ? 1 : Math.min(window.devicePixelRatio, 1.75));
renderer.setSize(window.innerWidth, window.innerHeight);
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.1;
$('stage').appendChild(renderer.domElement);

const world = new World(window.innerWidth / window.innerHeight);
const composer = new EffectComposer(renderer);
composer.addPass(new RenderPass(world.scene, world.camera));
const bloom = new UnrealBloomPass(new THREE.Vector2(window.innerWidth, window.innerHeight), 0.6, 0.45, 0.82);
composer.addPass(bloom);
composer.addPass(new OutputPass());

const songUrl = `${import.meta.env.BASE_URL}song.wav`;
const audio = new AudioEngine(songUrl);
const popups = new PopupLayer($('popups'), LINES, FACTS);

window.addEventListener('resize', () => {
  world.camera.aspect = window.innerWidth / window.innerHeight;
  world.camera.updateProjectionMatrix();
  renderer.setSize(window.innerWidth, window.innerHeight);
  composer.setSize(window.innerWidth, window.innerHeight);
});

// ---------- UI ----------
const startEl = $('start');
const title = $('title');
const credits = $('credits');
const bar = $('bar');
const fill = $('fill');
const timeEl = $('time');
const playBtn = $('play') as HTMLButtonElement;
const sectionEl = $('section');

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

// Hide controls when the mouse rests.
let idle = 0;
window.addEventListener('pointermove', () => {
  idle = 0;
  document.body.classList.remove('idle');
});

const fmt = (s: number) => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, '0')}`;

/** 0..1 fade for something shown in [a, b) with fade time f. */
const window01 = (t: number, a: number, b: number, f: number) =>
  Math.max(0, Math.min(1, (t - a) / f, (b - t) / f));

function setCard(el: HTMLElement, k: number) {
  el.style.opacity = k.toFixed(3);
  el.style.transform = `scale(${(0.9 + 0.1 * k).toFixed(4)})`;
}

// ---------- one frame at song time t ----------
let lastLine = -1;
let lastSection = '';
let pendingWords: { at: number; text: string; color: string }[] = [];
const TITLE_END = LINES[0].t - 1.5;
const CREDITS_AT = LINES[LINES.length - 1].e + 2;

function step(t: number, dt: number, started: boolean, sceneTime: number) {
  const b = audio.update(dt);
  const sec = sectionAt(t);

  if (started) {
    popups.update(t);

    // fly the acronyms of a new line through the 3D scene (staggered, in song time)
    const li = LINES.findIndex((l, i) => t >= l.t && (i === LINES.length - 1 || t < LINES[i + 1].t) && t < l.e + 1);
    if (li !== -1 && li !== lastLine && audio.playing) {
      keywordsIn(LINES[li].text).forEach((k, i) =>
        pendingWords.push({ at: t + i * 0.38, text: k.toUpperCase(), color: SECTION_COLORS[LINES[li].section] }),
      );
    }
    lastLine = li;
    pendingWords = pendingWords.filter((w) => {
      if (Math.abs(t - w.at) > 2) return false; // dropped after a seek
      if (t < w.at) return true;
      world.spawnKeyword(w.text, w.color);
      return false;
    });

    if (sec.id !== lastSection) {
      lastSection = sec.id;
      const names: Record<string, string> = {
        intro: 'Intro', verse1: 'Verse 1', chorus: 'Chorus', verse2: 'Verse 2', bridge: 'Bridge', final: 'Final Chorus', outro: 'Outro',
      };
      sectionEl.textContent = names[sec.id];
      sectionEl.style.setProperty('--accent', SECTION_COLORS[sec.id]);
      sectionEl.classList.remove('flash');
      void sectionEl.offsetWidth;
      sectionEl.classList.add('flash');
    }

    setCard(title, window01(t, 1, TITLE_END, 1.2));
    setCard(credits, window01(t, CREDITS_AT, Infinity, 1.2));
  }

  world.update(sceneTime, dt, b, sec.id, started ? sec.p : 0);
  bloom.strength = 0.45 + b.bass * 0.35 + b.beatPulse * 0.25;
  composer.render();
}

if (RENDER) {
  // Driven by the export script: window.__renderFrame(t, dt) draws exactly that moment.
  const w = window as unknown as Record<string, unknown>;
  w.__renderFrame = (t: number, dt: number) => {
    audio.renderTime = t;
    step(t, dt, true, t);
  };
  w.__duration = SONG_END;
  void (async () => {
    await audio.loadOffline(songUrl);
    await document.fonts.ready;
    w.__ready = true;
  })();
} else {
  const clock = new THREE.Clock();
  let virtualTime = 0; // keeps the scene alive behind the start screen
  const frame = () => {
    const dt = Math.min(clock.getDelta(), 0.1);
    const started = startEl.classList.contains('gone');
    virtualTime += dt;
    const t = started ? audio.time : 0;
    step(t, dt, started, started ? t : virtualTime);

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
