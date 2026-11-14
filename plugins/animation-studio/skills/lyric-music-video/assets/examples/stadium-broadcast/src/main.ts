import './style.css';
import { AudioEngine } from './audio';
import { Concert, type Perf } from './concert';
import hitsData from './hits.json';
import { heldFx, SungLine } from './lyric';
import { LINES, SONG_END, beatAt } from './lyrics';
import { HELD_LINES, HEY_WORDS, type Timed, TIMELINE, sceneAt, W, E } from './scenes';
import { clamp, easeOut, hash, mk, prog } from './util';

const HITS = hitsData as { hits: number[]; big: number[]; loud: number[] };
const $ = <T extends HTMLElement>(id: string) => document.getElementById(id) as T;

// ?render=1 → MP4 export mode (frames rendered on request by scripts/render.mjs)
const params = new URLSearchParams(location.search);
const RENDER = params.has('render');
const STATIC_GRAIN = params.has('staticgrain');
if (RENDER) document.body.classList.add('render');

const concert = new Concert($('stage3d'), RENDER);
const root = $('scene');
const flashEl = $('flash');
const grain = $('grain');
const audio = new AudioEngine(`${import.meta.env.BASE_URL}song.wav`);
window.addEventListener('resize', () => {
  concert.resize();
  current = null;
});

// film grain tile
{
  const c = document.createElement('canvas');
  c.width = c.height = 256;
  const g = c.getContext('2d')!;
  const img = g.createImageData(256, 256);
  for (let i = 0; i < img.data.length; i += 4) {
    const v = Math.floor(hash(i * 0.37) * 255);
    img.data[i] = img.data[i + 1] = img.data[i + 2] = v;
    img.data[i + 3] = 26;
  }
  g.putImageData(img, 0, 0);
  grain.style.backgroundImage = `url(${c.toDataURL()})`;
}

// ---------- broadcast overlay (persistent) ----------
const hud = $('live');
const liveBadge = mk('div', 'live-badge', hud);
const liveDot = mk('span', 'live-dot', liveBadge);
mk('span', '', liveBadge, 'LIVE');
const camLabel = mk('div', 'cam-label', hud);
const showTitle = mk('div', 'show-title', hud, 'THE SHOW · LIVE FROM HARBOR ARENA');
const card = mk('div', 'title-card', hud);
mk('div', 'tc-small', card, 'LIVE FROM HARBOR ARENA');
mk('div', 'tc-big', card, 'THE SHOW');
mk('div', 'tc-sub', card, 'ONE NIGHT · ONE STAGE');
const endCard = mk('div', 'end-card', hud);
mk('div', 'tc-big', endCard, 'THE SHOW');
mk('div', 'tc-sub', endCard, 'LIVE · HARBOR ARENA');

// ---------- lyrics of the current scene ----------
let current: Timed | null = null;
let lyricUpd: ((t: number, pulse: number) => void) | null = null;
function buildLyrics(s: Timed) {
  root.innerHTML = '';
  lyricUpd = null;
  if (!s.lines.length || s.lyr === 'none') return;
  const box = mk('div', `lyr lyr-${s.lyr ?? 'low'}`, root);
  const lines = s.lines.map((li) => new SungLine(box, LINES[li], '', s.lineOpts?.[li] ?? {}));
  lyricUpd = (t, pulse) => {
    lines.forEach((l) => l.update(t));
    const singing = s.lines.some((li) => t >= W(li) - 0.1 && t <= E(li) + 0.2) ? 1 : 0.4;
    box.style.setProperty('--bump', (1 + 0.06 * pulse * singing).toFixed(4));
  };
}

/** riff hit flash (big hits brighter) */
function hitAt(t: number) {
  let flash = 0;
  let pyro = 0;
  for (const h of HITS.hits) {
    if (h > t + 0.01) break;
    const big = HITS.big.includes(h);
    const d = t - h;
    const f = Math.exp(-d * (big ? 7 : 12)) * (big ? 1 : 0.45);
    if (f > flash) flash = f;
    if (big && d < 1.6) pyro = Math.max(pyro, d < 0.06 ? d / 0.06 : d < 0.45 ? 1 : Math.exp(-(d - 0.45) * 4.5));
  }
  return { flash, pyro };
}

function perfAt(t: number): Perf {
  let sing = 0;
  for (const l of LINES) {
    const a = l.t - 0.15;
    if (t >= a && t <= l.e) sing = 1;
  }
  let hey = 0;
  for (const h of HEY_WORDS) {
    const d = t - h;
    if (d > -0.12 && d < 1.2) hey = Math.max(hey, d < 0 ? 1 + d / 0.12 : Math.exp(-d * 2.2));
  }
  let held = 0;
  for (const [li, tr] of HELD_LINES) {
    const fx = heldFx(t, LINES[li], tr);
    held = Math.max(held, clamp(fx.env * 1.4), fx.release * 0.6);
  }
  const bow = prog(t, 213.2, 214.4) * (1 - prog(t, 216.0, 217.2));
  return { sing, hey: clamp(hey), held, bow };
}

function step(t: number) {
  const s = sceneAt(t);
  if (s !== current) {
    current = s;
    buildLyrics(s);
    camLabel.textContent = s.cam ?? '';
  }
  const beat = beatAt(t);
  const pulse = Math.exp(-(beat - Math.floor(beat)) * 5);
  const local = t - s.t0;
  const u = prog(t, s.t0, s.t1);
  const hit = hitAt(t);
  const wallCtx = { t, local, beat, pulse, hit: hit.flash };
  concert.update({
    t,
    local,
    u,
    beat,
    pulse,
    hit: hit.flash,
    pyro: hit.pyro,
    shot: s.shot,
    seed: s.seed ?? 0,
    look: s.look,
    perf: perfAt(t),
    drawWall: (g, w, h) => s.wall(g, w, h, wallCtx),
  });
  lyricUpd?.(t, pulse);

  // broadcast overlay
  liveDot.style.opacity = Math.floor(t * 1.2) % 2 === 0 ? '1' : '0.25';
  const hudOn = clamp((t - 1) / 1) * (1 - prog(t, 217.4, 217.8));
  hud.style.setProperty('--hud', hudOn.toFixed(3));
  const ck = prog(t, 5.2, 5.8) * (1 - prog(t, 9.0, 9.6));
  card.style.opacity = ck.toFixed(3);
  card.style.transform = `translateY(${((1 - easeOut(prog(t, 5.2, 5.8))) * 30).toFixed(1)}px)`;
  showTitle.style.opacity = (hudOn * (1 - ck)).toFixed(3);
  const ek = prog(t, 217.9, 218.8);
  endCard.style.opacity = ek.toFixed(3);
  endCard.style.transform = `scale(${(0.94 + 0.06 * easeOut(ek)).toFixed(3)})`;

  // camera flash on riff hits (only a touch – the stage lights do the rest)
  flashEl.style.opacity = (hit.flash * 0.18).toFixed(3);
  root.style.setProperty('--rgb', `${(hit.flash * 0.06 + pulse * 0.01).toFixed(3)}em`);
  if (!STATIC_GRAIN) grain.style.backgroundPosition = `${Math.floor(hash(Math.floor(t * 30)) * 256)}px ${Math.floor(hash(Math.floor(t * 30) + 7) * 256)}px`;
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
    await document.fonts.load('400 80px "Anton"');
    await document.fonts.load('400 20px "Space Mono"');
    await document.fonts.load('700 20px "Space Mono"');
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
    const t = started ? audio.time : 46 + ((now / 1000) % 8); // chorus loop behind the start card
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
