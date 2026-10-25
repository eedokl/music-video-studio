import './style.css';
import { AudioEngine } from './audio';
import { SONG_END, beatAt } from './lyrics';
import { type Timed, TIMELINE, sceneAt } from './scenes';
import hitsData from './hits.json';
import { hash, prog } from './util';
import { World3D } from './world3d';

const HITS = hitsData as { hits: number[]; big: number[]; loud: number[] };

const $ = <T extends HTMLElement>(id: string) => document.getElementById(id) as T;

// ?render=1 → MP4 export mode (frames rendered on request by scripts/render.mjs)
const params = new URLSearchParams(location.search);
const RENDER = params.has('render');
const STATIC_GRAIN = params.has('staticgrain');
if (RENDER) document.body.classList.add('render');

const world = new World3D($('stage3d'), $('labels'), RENDER);
const root = $('scene');
const bg = $('bg');
const wipe = $('wipe');
const flashEl = $('flash');
const grain = $('grain');
const audio = new AudioEngine(`${import.meta.env.BASE_URL}song.wav`);
window.addEventListener('resize', () => {
  world.resize();
  current = null; // rebuild layout on resize
});

// film grain: one noise tile, shifted every frame
{
  const c = document.createElement('canvas');
  c.width = c.height = 256;
  const g = c.getContext('2d')!;
  const img = g.createImageData(256, 256);
  for (let i = 0; i < img.data.length; i += 4) {
    const v = Math.floor(hash(i * 0.37) * 255);
    img.data[i] = img.data[i + 1] = img.data[i + 2] = v;
    img.data[i + 3] = 38;
  }
  g.putImageData(img, 0, 0);
  grain.style.backgroundImage = `url(${c.toDataURL()})`;
}

let current: Timed | null = null;
let upd: ((c: Parameters<ReturnType<Timed['build']>>[0]) => void) | null = null;

function step(t: number) {
  const s = sceneAt(t);
  if (s !== current) {
    current = s;
    root.innerHTML = '';
    root.className = `scene ${s.theme}${s.three ? ' over3d' : ''}`;
    root.style.cssText = ''; // scenes may set filter/background/vars on the root – never let them leak into the next scene
    bg.className = `${s.theme}${s.three ? ' off' : ''}`;
    world.setMode(s.three ?? 'none');
    upd = s.build(root);
  }
  const beat = beatAt(t);
  const pulse = Math.exp(-(beat - Math.floor(beat)) * 5);
  const u = prog(t, s.t0, s.t1);
  const hit = hitAt(t);
  const opts = s.opts ?? {};
  if (s.three === 'storm') {
    opts.flash = hit.flash;
    opts.boltSeed = hit.seed;
  }
  const screen = world.update({ t, u, beat, pulse, opts });
  upd!({ t, u, local: t - s.t0, beat, pulse, screen });
  // hard cut: a short dip to black into every scene
  const k = prog(t, s.t0, s.t0 + 0.12);
  const first = s === TIMELINE[0];
  wipe.style.opacity = first ? '0' : (1 - k).toFixed(3);
  // riff hits: white flash, screen shake, RGB split on the lyrics
  flashEl.style.opacity = (hit.flash * 0.4).toFixed(3);
  const sh = hit.flash * 10 + (beat % 4 < 0.12 ? 2 : 0);
  root.style.transform = sh > 0.2 ? `translate(${(Math.sin(t * 97) * sh).toFixed(1)}px, ${(Math.cos(t * 83) * sh).toFixed(1)}px)` : '';
  root.style.setProperty('--rgb', `${(hit.flash * 0.08 + pulse * 0.012).toFixed(3)}em`);
  // ?staticgrain → grain stays put (much smaller video files)
  if (!STATIC_GRAIN) grain.style.backgroundPosition = `${Math.floor(hash(Math.floor(t * 30)) * 256)}px ${Math.floor(hash(Math.floor(t * 30) + 7) * 256)}px`;
}

/** Flash strength of the most recent riff hit (big hits are brighter). */
function hitAt(t: number) {
  let flash = 0;
  let seed = 0;
  for (const h of HITS.hits) {
    if (h > t) break;
    const big = HITS.big.includes(h);
    const f = Math.exp(-(t - h) * (big ? 7 : 12)) * (big ? 1 : 0.45);
    if (f > flash) {
      flash = f;
      seed = h;
    }
  }
  return { flash, seed };
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
    await document.fonts.load('800 80px "Barlow Condensed"');
    await document.fonts.load('600 20px "Inter"');
    await document.fonts.load('800 20px "Inter"');
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
    const t = started ? audio.time : 2 + ((now / 1000) % 8); // demo loop of the intro behind the start card
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
