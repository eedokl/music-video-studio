// Main file of an imported video engine inside the studio (replaces the original main.ts).
// Plays the ORIGINAL scenes (SCENES from scenes.ts), but in the order and at the times of the studio
// timeline (studio scenes reference an original scene by `legacy` id). The studio calls
//   window.__renderFrame(t)   draw song time t       window.__update(project)   apply edits
//   window.__ready            set when fonts + data are ready
import './style.css';
import { type SceneDef, SCENES } from './scenes';
import { studio } from './studio_data';
import { hash, prog } from './util';
import { World3D } from './world3d';
import { __setLead } from './lyric';

const params = new URLSearchParams(location.search);
const RENDER = params.has('render');
const STATIC_GRAIN = params.has('staticgrain');
if (RENDER) document.body.classList.add('render');
const $ = <T extends HTMLElement>(id: string) => document.getElementById(id) as T;

const world = new World3D($('stage3d'), $('labels'), true);
const root = $('scene');
const bg = $('bg');
const wipe = $('wipe');
const flashEl = $('flash');
const grain = $('grain');
const byId = new Map(SCENES.map((s) => [s.id, s]));

interface Slot {
  key: string;
  def: SceneDef | null;
  t0: number;
  t1: number;
  first: boolean;
}
let schedule: Slot[] = [];
function rebuildSchedule() {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  schedule = studio.timing.scenes.map((ts, i) => ({ key: ts.scene.id, def: byId.get((ts.scene as any).legacy ?? ts.scene.id) ?? null, t0: ts.t0, t1: ts.t1, first: i === 0 }));
}
rebuildSchedule();
__setLead(studio.lead);

window.addEventListener('resize', () => {
  world.resize();
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
    img.data[i + 3] = 38;
  }
  g.putImageData(img, 0, 0);
  grain.style.backgroundImage = `url(${c.toDataURL()})`;
}

let current: Slot | null = null;
// eslint-disable-next-line @typescript-eslint/no-explicit-any
let upd: ((c: any) => void) | null = null;

function hitAt(t: number) {
  let flash = 0;
  let seed = 0;
  const hits: number[] = studio.project.hits?.hits ?? [];
  const big = new Set<number>(studio.project.hits?.big ?? []);
  for (const h of hits) {
    if (h > t) break;
    const isBig = big.has(h);
    const f = Math.exp(-(t - h) * (isBig ? 7 : 12)) * (isBig ? 1 : 0.45);
    if (f > flash) {
      flash = f;
      seed = h;
    }
  }
  return { flash, seed };
}

function slotAt(t: number) {
  for (let i = schedule.length - 1; i >= 0; i--) if (t >= schedule[i].t0) return schedule[i];
  return schedule[0];
}

function step(t: number) {
  const s = slotAt(t);
  if (!s) return;
  if (s !== current) {
    current = s;
    root.innerHTML = '';
    root.style.cssText = '';
    const def = s.def;
    root.className = `scene ${def?.theme ?? 'dark'}${def?.three ? ' over3d' : ''}`;
    bg.className = `${def?.theme ?? 'dark'}${def?.three ? ' off' : ''}`;
    world.setMode(def?.three ?? 'none');
    upd = def ? def.build(root) : null;
  }
  const beat = studio.timing.beatAt(t);
  const pulse = Math.exp(-(beat - Math.floor(beat)) * 5);
  const u = prog(t, s.t0, s.t1);
  const hit = hitAt(t);
  const opts = { ...(s.def?.opts ?? {}) } as Record<string, number | string | boolean>;
  if (s.def?.three === 'storm') {
    opts.flash = hit.flash;
    opts.boltSeed = hit.seed;
  }
  const screen = world.update({ t, u, beat, pulse, opts });
  upd?.({ t, u, local: t - s.t0, beat, pulse, screen });
  const k = prog(t, s.t0, s.t0 + 0.12);
  wipe.style.opacity = s.first ? '0' : (1 - k).toFixed(3);
  flashEl.style.opacity = (hit.flash * 0.55).toFixed(3);
  const sh = hit.flash * 10 + (beat % 4 < 0.12 ? 2 : 0);
  root.style.transform = sh > 0.2 ? `translate(${(Math.sin(t * 97) * sh).toFixed(1)}px, ${(Math.cos(t * 83) * sh).toFixed(1)}px)` : '';
  root.style.setProperty('--rgb', `${(hit.flash * 0.08 + pulse * 0.012).toFixed(3)}em`);
  if (!STATIC_GRAIN) grain.style.backgroundPosition = `${Math.floor(hash(Math.floor(t * 30)) * 256)}px ${Math.floor(hash(Math.floor(t * 30) + 7) * 256)}px`;
}

const w = window as unknown as Record<string, unknown>;
w.__renderFrame = (t: number) => step(t);
w.__duration = studio.project.audio.duration;
// eslint-disable-next-line @typescript-eslint/no-explicit-any
w.__update = (p: any) => {
  studio.update(p);
  __setLead(studio.lead);
  rebuildSchedule();
  current = null;
};
w.__scenes = () => SCENES.map((s) => ({ id: s.id, lines: s.lines, theme: s.theme, three: s.three ?? null, start: s.start ?? null }));
void (async () => {
  await document.fonts.load('400 80px "Anton"');
  await document.fonts.load('400 20px "Space Mono"');
  await document.fonts.load('italic 700 40px "Playfair Display"');
  await document.fonts.ready;
  current = null;
  step(0);
  w.__ready = true;
})();
