// LED wall visuals (1280×720 canvas). Built-in types are configured by params in project.json;
// custom visuals are JS modules inside the project folder (walls/<name>.js) that export
//   function myWall(g, w, h, c, params, api) { ... }
// c = { t, local, beat, pulse, hit }, api = drawing helpers + anchor resolution (see WallApi).

import type { Anchor, WallSpec } from '../types';
import type { Timing } from './timing';
import { clamp, easeInOut, easeOut, easeOutBack, hash, prog } from './util';

export interface WallCtx {
  t: number;
  local: number;
  beat: number;
  pulse: number;
  hit: number;
}
export type WallFn = (g: CanvasRenderingContext2D, w: number, h: number, c: WallCtx, params: Record<string, any>, api: WallApi) => void;

export const GOLD = '#ffcc00';
export const BLUE = '#0a3fbf';
export const RED = '#e3001b';
export const HEAVY = '"Anton", Impact, sans-serif';
export const MONO = '"Space Mono", Consolas, monospace';

// ---------- drawing helpers (also handed to custom modules) ----------
export function txt(g: CanvasRenderingContext2D, s: string, x: number, y: number, size: number, color: string, align: CanvasTextAlign = 'center', font = HEAVY, alpha = 1) {
  if (alpha <= 0 || size <= 0) return;
  g.save();
  g.globalAlpha = clamp(alpha);
  g.font = `${size}px ${font}`;
  g.textAlign = align;
  g.textBaseline = 'middle';
  g.fillStyle = color;
  g.shadowColor = color;
  g.shadowBlur = size * 0.25;
  g.fillText(s, x, y);
  g.restore();
}
/** text that shrinks to fit maxW */
export function fitTxt(g: CanvasRenderingContext2D, s: string, x: number, y: number, size: number, maxW: number, color: string, align: CanvasTextAlign = 'center', font = HEAVY, alpha = 1) {
  g.save();
  g.font = `${size}px ${font}`;
  const m = g.measureText(s).width;
  g.restore();
  txt(g, s, x, y, m > maxW ? (size * maxW) / m : size, color, align, font, alpha);
}
export function star(g: CanvasRenderingContext2D, x: number, y: number, r: number, color: string, alpha = 1, rot = 0) {
  if (alpha <= 0 || r <= 0) return;
  g.save();
  g.globalAlpha = clamp(alpha);
  g.translate(x, y);
  g.rotate(rot);
  g.beginPath();
  for (let k = 0; k < 10; k++) {
    const rr = k % 2 ? r * 0.4 : r;
    const a = (k / 10) * Math.PI * 2 - Math.PI / 2;
    g.lineTo(Math.cos(a) * rr, Math.sin(a) * rr);
  }
  g.closePath();
  g.fillStyle = color;
  g.shadowColor = color;
  g.shadowBlur = r * 0.8;
  g.fill();
  g.restore();
}
export function starRing(g: CanvasRenderingContext2D, x: number, y: number, R: number, r: number, color: string, alpha = 1, rot = 0, count = 12) {
  for (let i = 0; i < count; i++) {
    const a = (i / 12) * Math.PI * 2 - Math.PI / 2 + rot;
    star(g, x + Math.cos(a) * R, y + Math.sin(a) * R, r, color, alpha);
  }
}
export function bg(g: CanvasRenderingContext2D, w: number, h: number, a: string, b: string) {
  const gr = g.createLinearGradient(0, 0, 0, h);
  gr.addColorStop(0, a);
  gr.addColorStop(1, b);
  g.fillStyle = gr;
  g.fillRect(0, 0, w, h);
}
export function radial(g: CanvasRenderingContext2D, x: number, y: number, r: number, color: string, alpha: number) {
  if (alpha <= 0) return;
  g.save();
  g.globalAlpha = clamp(alpha);
  const gr = g.createRadialGradient(x, y, 0, x, y, r);
  gr.addColorStop(0, color);
  gr.addColorStop(1, 'rgba(0,0,0,0)');
  g.fillStyle = gr;
  g.fillRect(x - r, y - r, r * 2, r * 2);
  g.restore();
}
export const typed = (s: string, t: number, a: number, b: number) => s.slice(0, Math.round(clamp((t - a) / (b - a)) * s.length));

export interface WallApi {
  /** screen time of word wi of a line ("l12" or index 12) – lyric lead applied */
  W: (line: string | number, wi?: number, edge?: 'start' | 'end') => number;
  /** end of a line (last word end, lead applied) */
  E: (line: string | number) => number;
  at: (a: Anchor | number | undefined, fallback?: number) => number;
  timeAtBeat: (b: number) => number;
  image: (src: string) => HTMLImageElement | null;
  txt: typeof txt;
  fitTxt: typeof fitTxt;
  star: typeof star;
  starRing: typeof starRing;
  bg: typeof bg;
  radial: typeof radial;
  typed: typeof typed;
  clamp: typeof clamp;
  prog: typeof prog;
  easeOut: typeof easeOut;
  easeOutBack: typeof easeOutBack;
  easeInOut: typeof easeInOut;
  hash: typeof hash;
  GOLD: string;
  BLUE: string;
  RED: string;
  HEAVY: string;
  MONO: string;
}

export function makeApi(timing: Timing, fileUrl: (rel: string) => string): WallApi {
  const id = (l: string | number) => (typeof l === 'number' ? `l${l}` : l);
  const images = new Map<string, HTMLImageElement>();
  return {
    W: (l, wi = 0, edge = 'start') => timing.wordTime(id(l), wi, edge) ?? 0,
    E: (l) => {
      const ln = timing.lineById.get(id(l));
      return ln ? ln.words[ln.words.length - 1].e - timing.lead : 0;
    },
    at: (a, fb = 0) => (typeof a === 'number' ? a : timing.anchor(a, fb)),
    timeAtBeat: (b) => timing.timeAtBeat(b),
    image: (src) => {
      let im = images.get(src);
      if (!im) {
        im = new Image();
        im.src = fileUrl(src);
        images.set(src, im);
      }
      return im.complete && im.naturalWidth ? im : null;
    },
    txt, fitTxt, star, starRing, bg, radial, typed, clamp, prog, easeOut, easeOutBack, easeInOut, hash,
    GOLD, BLUE, RED, HEAVY, MONO,
  };
}

// ---------------------------------------------------------------- built-in types
type P = Record<string, any>;
const pop = (t: number, a: number, d = 0.3) => easeOutBack(clamp((t - a) / d));

const BUILTIN: Record<string, WallFn> = {
  title: (g, w, h, c, p) => {
    bg(g, w, h, p.bg1 ?? '#020414', p.bg2 ?? '#000');
    radial(g, w / 2, h / 2, 520, p.glow ?? BLUE, 0.55 + 0.25 * c.pulse);
    if (p.stars !== false) starRing(g, w / 2, h / 2, 250, 22, p.starColor ?? GOLD, clamp(c.local / 1.5), c.t * 0.05);
    const k = p.reveal ? easeOutBack(prog(c.local, p.reveal, p.reveal + 0.8)) : 1;
    fitTxt(g, String(p.title ?? ''), w / 2, h / 2 - 10, 120 * k, w * 0.86, p.color ?? '#fff');
    if (p.subtitle) txt(g, String(p.subtitle), w / 2, h / 2 + 100, 30, GOLD, 'center', MONO, prog(c.local, 0.8, 1.4));
  },
  bigword: (g, w, h, c, p) => {
    const on = p.flash ? Math.floor(c.beat) % 2 === 0 : false;
    const col = p.color ?? RED;
    bg(g, w, h, on ? col : '#000', on ? '#300' : '#000');
    fitTxt(g, String(p.text ?? ''), w / 2, h / 2 - (p.sub ? 30 : 0), 300 * (1 + 0.1 * c.pulse), w * 0.9, on ? '#fff' : col);
    if (p.sub) txt(g, String(p.sub), w / 2, h - 110, 64, on ? '#000' : '#fff');
  },
  words: (g, w, h, c, p, api) => {
    bg(g, w, h, p.bg1 ?? '#05060c', p.bg2 ?? '#000');
    radial(g, w / 2, h * 0.6, 600, p.glow ?? BLUE, 0.35 + 0.2 * c.pulse);
    const items: P[] = p.items ?? [];
    if (p.title) txt(g, String(p.title), w / 2, 80, 40, GOLD, 'center', MONO);
    const n = Math.max(1, items.length);
    items.forEach((it, i) => {
      const a = api.at(it.at, 0);
      const k = pop(c.t, a);
      const y = n === 1 ? h / 2 : 170 + (i * (h - 280)) / Math.max(1, n - 1);
      const cols = [GOLD, '#ffffff', '#5aa0ff', RED];
      fitTxt(g, String(it.text), w / 2, y, (n === 1 ? 200 : n === 2 ? 150 : 110) * k, w * 0.88, it.color ?? cols[i % cols.length], 'center', HEAVY, clamp((c.t - a) / 0.15));
    });
  },
  list: (g, w, h, c, p, api) => {
    bg(g, w, h, '#e6e2d8', '#c9c4b8');
    g.fillStyle = p.color ?? BLUE;
    g.fillRect(0, 0, w, 110);
    fitTxt(g, String(p.title ?? ''), 60, 58, 64, w - 120, '#fff', 'left');
    (p.items ?? []).forEach((it: P, i: number) => {
      const a = api.at(it.at, 0);
      const al = clamp((c.t - a) / 0.2);
      g.globalAlpha = al;
      g.fillStyle = RED;
      g.fillRect(80, 180 + i * 90, 22, 22);
      g.globalAlpha = 1;
      fitTxt(g, String(it.text), 130, 192 + i * 90, 54, w - 200, '#111', 'left', HEAVY, al);
    });
  },
  split: (g, w, h, c, p, api) => {
    const L: P = p.left ?? {};
    const R: P = p.right ?? {};
    g.fillStyle = L.bg ?? '#c2552a';
    g.fillRect(0, 0, w / 2, h);
    g.fillStyle = R.bg ?? '#0a1c5a';
    g.fillRect(w / 2, 0, w / 2, h);
    fitTxt(g, String(L.title ?? ''), w / 4, 120, 56, w / 2 - 60, '#fff');
    fitTxt(g, String(R.title ?? ''), (w * 3) / 4, 120, 56, w / 2 - 60, GOLD);
    const la = api.at(L.at, 0);
    fitTxt(g, String(L.text ?? ''), w / 4, 380, 100 * pop(c.t, la, 0.35), w / 2 - 60, '#fff');
    const ra = api.at(R.at, 0);
    fitTxt(g, String(R.text ?? ''), (w * 3) / 4, 300, 64, w / 2 - 60, '#fff', 'center', HEAVY, clamp((c.t - ra) / 0.2));
    if (R.stamp) {
      const sa = api.at(R.stampAt ?? R.at, 0);
      const st = clamp((c.t - sa) / 0.15);
      if (st > 0) {
        g.save();
        g.translate((w * 3) / 4, 470);
        g.rotate(-0.18);
        const s = 2.2 - 1.2 * easeOut(st);
        g.scale(s, s);
        g.strokeStyle = RED;
        g.lineWidth = 8;
        g.strokeRect(-210, -60, 420, 120);
        fitTxt(g, String(R.stamp), 0, 0, 74, 380, RED);
        g.restore();
      }
    }
  },
  counter: (g, w, h, c, p, api) => {
    bg(g, w, h, '#000', '#06001a');
    const a = api.at(p.at, 0);
    const from = Number(p.from ?? 2026);
    const to = Number(p.to ?? 2031);
    const step = Number(p.step ?? 0.42);
    const v = Math.min(to, from + Math.floor(Math.max(0, c.t - a) / step) * Math.sign(to - from || 1));
    const fin = v === to;
    if (fin) radial(g, w / 2, h / 2, 640, GOLD, 0.45 + 0.35 * c.pulse);
    txt(g, String(v), w / 2, h / 2 - 20, 300 * (fin ? 1 + 0.05 * c.pulse : 1), fin ? GOLD : '#fff');
    if (p.label) fitTxt(g, String(p.label), w / 2, h - 110, 64, w * 0.9, '#fff', 'center', HEAVY, clamp((c.t - api.at(p.labelAt ?? p.at, 0)) / 0.3));
  },
  clock: (g, w, h, c, p, api) => {
    bg(g, w, h, '#0d1430', '#020308');
    g.fillStyle = '#05060c';
    let x = 0;
    let i = 0;
    while (x < w) {
      const bw = 40 + hash(i) * 70;
      const bh = 90 + hash(i * 3) * 170;
      g.fillRect(x, h - bh, bw + 1, bh);
      x += bw;
      i++;
    }
    const flipped = p.flipTo && c.t >= api.at(p.flipAt, 1e9);
    txt(g, String(flipped ? p.flipTo : (p.time ?? '07:59')), w / 2, 210, 190, flipped ? RED : '#fff');
    if (p.label) txt(g, String(p.label), w / 2, 340, 30, GOLD, 'center', MONO);
  },
  chart: (g, w, h, c, p, api) => {
    bg(g, w, h, '#0a0a12', '#000');
    const a = api.at(p.at, 0);
    const k = clamp((c.t - a) / Number(p.dur ?? 2.4));
    g.strokeStyle = 'rgba(255,255,255,0.15)';
    g.lineWidth = 2;
    for (let y = 120; y < h; y += 100) {
      g.beginPath();
      g.moveTo(80, y);
      g.lineTo(w - 80, y);
      g.stroke();
    }
    g.save();
    g.strokeStyle = p.color ?? RED;
    g.lineWidth = 12;
    g.shadowColor = p.color ?? RED;
    g.shadowBlur = 30;
    g.beginPath();
    for (let i = 0; i <= 80 * k; i++) {
      const u = i / 80;
      const px = 80 + u * (w - 160);
      const py = h - 60 - (p.shape === 'down' ? (1 - u) * 520 : (Math.exp(u * 4.6) - 1) * 5.2);
      if (i === 0) g.moveTo(px, py);
      else g.lineTo(px, py);
    }
    g.stroke();
    g.restore();
    if (p.label) fitTxt(g, String(p.label), w - 120, 120, 60, w * 0.5, p.color ?? RED, 'right', HEAVY, clamp((k - 0.6) * 4));
  },
  ticker: (g, w, h, c, p) => {
    bg(g, w, h, '#0a0a12', '#000');
    g.fillStyle = p.color ?? RED;
    g.fillRect(0, 170, w, 170);
    fitTxt(g, String(p.banner ?? 'BREAKING NEWS'), w / 2, 255, 140 * (1 + 0.03 * c.pulse), w * 0.9, '#fff');
    g.fillStyle = '#fff';
    g.fillRect(0, 380, w, 80);
    const msg = `+++ ${p.text ?? ''} `;
    g.save();
    g.font = `48px ${HEAVY}`;
    g.fillStyle = '#111';
    g.textBaseline = 'middle';
    const mw = g.measureText(msg).width || 1;
    const off = (c.t * 260) % mw;
    for (let x = -off; x < w; x += mw) g.fillText(msg, x, 422);
    g.restore();
    if (p.sub) fitTxt(g, String(p.sub), w / 2, 600, 54, w * 0.9, GOLD);
  },
  board: (g, w, h, c, p, api) => {
    bg(g, w, h, '#05070a', '#000');
    txt(g, String(p.title ?? 'DEPARTURES'), 60, 70, 46, GOLD, 'left');
    const a0 = api.at(p.at, 0);
    const rows: string[][] = p.rows ?? [];
    rows.slice(0, 6).forEach((r, i) => {
      const a = a0 + i * 0.35;
      const y = 170 + i * 100;
      g.fillStyle = '#111620';
      g.fillRect(50, y - 40, w - 100, 80);
      const flip = (s: string) => [...s].map((ch, j) => (c.t < a + j * 0.03 ? String.fromCharCode(65 + Math.floor(hash(j + Math.floor(c.t * 20)) * 26)) : ch)).join('');
      const xs = [80, 300, 760, w - 80];
      r.slice(0, 4).forEach((cell, k) => txt(g, flip(String(cell)), xs[k], y, k === 1 ? 46 : 36, k === 3 ? '#4caf50' : k === 1 ? '#fff' : '#f0d060', k === 3 ? 'right' : 'left', k === 1 ? HEAVY : MONO));
    });
  },
  eq: (g, w, h, c, p) => {
    bg(g, w, h, '#02030a', '#000');
    const n = 32;
    for (let i = 0; i < n; i++) {
      const v = 0.25 + 0.55 * Math.abs(Math.sin(c.t * (2 + hash(i) * 3) + i)) * (0.6 + 0.4 * c.pulse) + c.hit * 0.3;
      const bh = v * h * 0.8;
      const x = 40 + i * ((w - 80) / n);
      const gr = g.createLinearGradient(0, h, 0, h - bh);
      gr.addColorStop(0, BLUE);
      gr.addColorStop(1, i % 4 === 0 ? RED : GOLD);
      g.fillStyle = gr;
      g.fillRect(x, h - bh, (w - 80) / n - 8, bh);
    }
    if (p.title) fitTxt(g, String(p.title), w / 2, 110, 80, w * 0.9, '#fff', 'center', HEAVY, 0.9);
  },
  stars: (g, w, h, c, p) => {
    bg(g, w, h, '#020a2a', '#000');
    radial(g, w / 2, h / 2, 700, p.glow ?? BLUE, 0.6 + 0.2 * c.pulse);
    starRing(g, w / 2, h / 2, 260, 26, GOLD, 1, c.t * 0.15);
    fitTxt(g, String(p.text ?? ''), w / 2, h / 2, 110 * (1 + 0.04 * c.pulse), 460, '#fff');
  },
  image: (g, w, h, c, p, api) => {
    bg(g, w, h, '#000', '#000');
    const im = p.src ? api.image(String(p.src)) : null;
    if (im) {
      const z = 1.05 + 0.08 * clamp(c.local / 8);
      const s = Math.max(w / im.naturalWidth, h / im.naturalHeight) * z;
      g.globalAlpha = Number(p.dim ?? 0.85);
      g.drawImage(im, (w - im.naturalWidth * s) / 2 - c.local * 6, (h - im.naturalHeight * s) / 2, im.naturalWidth * s, im.naturalHeight * s);
      g.globalAlpha = 1;
    }
    if (p.title) fitTxt(g, String(p.title), w / 2, h - 90, 70, w * 0.9, '#fff');
  },
};
export const WALL_TYPES = Object.keys(BUILTIN);

// ---------------------------------------------------------------- custom modules
const modules = new Map<string, Record<string, WallFn> | 'loading' | 'error'>();

/** load all custom wall modules a project uses (render mode waits for this) */
export async function loadCustom(specs: WallSpec[], fileUrl: (rel: string) => string, bust = '') {
  const need = [...new Set(specs.filter((s) => s.type === 'custom' && s.module).map((s) => s.module!))];
  await Promise.all(
    need.map(async (m) => {
      const key = m + bust;
      if (modules.has(key) && modules.get(key) !== 'error') return;
      modules.set(key, 'loading');
      try {
        modules.set(key, await import(/* @vite-ignore */ fileUrl(m) + `?v=${encodeURIComponent(bust)}`));
      } catch (e) {
        console.error('wall module failed', m, e);
        modules.set(key, 'error');
      }
    }),
  );
}

export function drawWall(spec: WallSpec | undefined, g: CanvasRenderingContext2D, w: number, h: number, c: WallCtx, api: WallApi, bust = '') {
  if (!spec) return BUILTIN.eq(g, w, h, c, {}, api);
  try {
    if (spec.type === 'custom') {
      const mod = modules.get((spec.module ?? '') + bust);
      const fn = mod && typeof mod === 'object' ? mod[spec.fn ?? 'default'] : undefined;
      if (fn) {
        // modules may export setApi(api) to get word times / helpers at module level
        (mod as unknown as { setApi?: (a: WallApi) => void }).setApi?.(api);
        return fn(g, w, h, c, spec.params ?? {}, api);
      }
      return BUILTIN.eq(g, w, h, c, { title: mod === 'error' ? `wall module error: ${spec.module}` : '' }, api);
    }
    (BUILTIN[spec.type] ?? BUILTIN.eq)(g, w, h, c, spec.params ?? {}, api);
  } catch (e) {
    g.fillStyle = '#300';
    g.fillRect(0, 0, w, h);
    txt(g, `wall error: ${(e as Error).message}`.slice(0, 60), w / 2, h / 2, 32, '#fff', 'center', MONO);
  }
}
