import './style.css';
import { AudioEngine } from './audio';
import { SONG_END, beatAt } from './lyrics';
import { type Timed, TIMELINE, sceneAt } from './scenes';
import { prog } from './util';
import { World3D } from './world3d';

const $ = <T extends HTMLElement>(id: string) => document.getElementById(id) as T;

// ?render=1 → MP4 export mode (frames rendered on request by scripts/render.mjs)
const params = new URLSearchParams(location.search);
const RENDER = params.has('render');
if (RENDER) document.body.classList.add('render');

const world = new World3D($('stage3d'), $('labels'), RENDER);
const root = $('scene');
const audio = new AudioEngine(`${import.meta.env.BASE_URL}song.wav`);
window.addEventListener('resize', () => {
  world.resize();
  current = null; // rebuild layout on resize
});

let current: Timed | null = null;
let upd: ((c: Parameters<ReturnType<Timed['build']>>[0]) => void) | null = null;

function step(t: number) {
  const s = sceneAt(t);
  if (s !== current) {
    current = s;
    root.innerHTML = '';
    root.className = `scene ${s.theme}${s.three ? ' over3d' : ''}`;
    world.setMode(s.three ?? 'none');
    upd = s.build(root);
  }
  const beat = beatAt(t);
  const pulse = Math.exp(-(beat - Math.floor(beat)) * 5);
  const u = prog(t, s.t0, s.t1);
  const screen = world.update({ t, u, beat, pulse, opts: s.opts ?? {} });
  upd!({ t, u, local: t - s.t0, beat, pulse, screen });
  // quick "cut-in" at the start of every scene
  const k = prog(t, s.t0, s.t0 + 0.16);
  root.style.transform = `scale(${(1.03 - 0.03 * k).toFixed(4)})`;
  root.style.opacity = (0.4 + 0.6 * k).toFixed(3);
}

// ---------- UI ----------
const startEl = $('start');
const bar = $('bar');
const fill = $('fill');
const timeEl = $('time');
const playBtn = $('play') as HTMLButtonElement;
const startAt = Number(params.get('t') ?? 0);
const fmt = (s: number) => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, '0')}`;

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
});
let idle = 0;
window.addEventListener('pointermove', () => {
  idle = 0;
  document.body.classList.remove('idle');
});

if (RENDER) {
  const w = window as unknown as Record<string, unknown>;
  w.__renderFrame = (t: number) => step(t);
  w.__duration = SONG_END;
  w.__scenes = TIMELINE.map((s) => ({ id: s.id, t0: s.t0, t1: s.t1 }));
  void (async () => {
    await document.fonts.load('900 80px "Inter Tight"');
    await document.fonts.load('400 20px "JetBrains Mono"');
    await document.fonts.ready;
    current = null;
    w.__ready = true;
  })();
} else {
  void document.fonts.ready.then(() => (current = null));
  let last = performance.now();
  const frame = (now: number) => {
    const dt = Math.min(0.1, (now - last) / 1000);
    last = now;
    const started = startEl.classList.contains('gone');
    const t = started ? audio.time : 7 + ((now / 1000) % 6); // demo loop of the intro behind the start card
    step(t);
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
