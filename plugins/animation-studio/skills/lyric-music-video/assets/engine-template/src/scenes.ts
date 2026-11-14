// Scene timeline – REPLACE these example scenes with scenes invented for the song.
// Rules that keep the MP4 export frame-exact:
//  * every visual property is computed from the song time `c.t` (or `c.u`, `c.beat`, `c.pulse`)
//  * no CSS transitions/animations, no setTimeout, no Math.random (use hash(n) for deterministic noise)
//  * build() creates the DOM once when the scene starts; the returned function runs every frame

import { LEAD, type LineOpts, SungLine } from './lyric';
import heldData from './held.json';
import { BEAT_OFFSET, BPM, LINES, SONG_END } from './lyrics';
import { easeOut, easeOutBack, hash, mk, popStyle, prog, slideIn } from './util';
import type { Mode3D } from './world3d';

export interface Ctx {
  t: number; // song time (s)
  u: number; // 0..1 progress through this scene
  local: number; // seconds since the scene started
  beat: number; // beat position (12.5 = halfway between beat 12 and 13)
  pulse: number; // 1 on every beat, decays quickly
  screen: DOMRect | null;
}
type Upd = (c: Ctx) => void;

export interface SceneDef {
  id: string;
  lines: number[]; // lyric line indexes this scene shows (the first one decides when the scene starts)
  theme: 'dark' | 'light';
  three?: Mode3D; // optional 3D background: 'storm' | 'city' | 'network' | 'globe' | 'vault' | 'tunnel'
  opts?: Record<string, number | string | boolean>;
  start?: number; // explicit start time (intros, instrumental breaks)
  build: (root: HTMLElement) => Upd;
}

const L = LINES;
/** time when word wi of line li appears on screen (already shifted by the lyric lead) */
export const W = (li: number, wi: number) => (L[li].words?.[wi] ?? L[li].t) - LEAD;
export const T0 = (li: number) => L[li].t - LEAD;
export const E = (li: number) => L[li].e - LEAD;
// measured held notes (held.json): a line whose LAST word is one of them is only complete on the release
const HELD_SPANS = Object.values(heldData as Record<string, { t0: number; fps: number; env: number[] }>).map(
  (h) => [h.t0, h.t0 + h.env.length / h.fps] as const,
);
/** The line's last word is a measured held note (HeldWord lands its ending letters on the release). */
export function heldLast(li: number) {
  const l = L[li];
  const s = l.words?.[l.words.length - 1] ?? l.t;
  const e = l.ends?.[l.ends.length - 1] ?? l.e;
  return e - s > 0.6 && HELD_SPANS.some(([a, b]) => s < b && e > a);
}
/** When the last letter of a line has landed (same maths as SungLine: letters over 65 % of the word, 0.21 s stamp;
 *  a held last word: its ending letters land on the release, so a cut waits for the whole held note). */
export function textDone(li: number, held = heldLast(li)) {
  const l = L[li];
  const s = (l.words?.[l.words.length - 1] ?? l.t) - LEAD;
  const end = (l.ends?.[l.ends.length - 1] ?? l.e + 0.25) - LEAD;
  if (held) return Math.max(s + 0.33, end + 0.1);
  const e = Math.min(Math.max(end, s + 0.12), s + 1.4);
  return s + (e - s) * 0.65 + 0.21;
}
/** A finished line stays readable this long before the scene may cut. */
export const READ_HOLD = 0.3;
/** song time of a beat number (for on-beat events: beatAt(t) gives the beat number of a time) */
export const timeAtBeat = (b: number) => BEAT_OFFSET + (b * 60) / BPM;

/** Lyric block: letters appear as they are sung; bumps on the beat; replace = show only the current line. */
export function lyrics(parent: HTMLElement, idx: number[], cls = '', replace = false, lineOpts: Record<number, LineOpts> = {}) {
  const box = mk('div', `lyr ${cls}`, parent);
  const tl = idx.map((i) => new SungLine(box, L[i], '', lineOpts[i] ?? {}));
  return (t: number, pulse = 0) => {
    let active = 0;
    idx.forEach((li, k) => {
      if (t >= L[li].t - 0.3) active = k;
    });
    tl.forEach((l, k) => {
      l.update(t);
      if (replace) l.el.style.display = k === active ? 'block' : 'none';
    });
    const singing = idx.some((li) => t >= L[li].t - 0.1 && t <= L[li].e + 0.2) ? 1 : 0.4;
    box.style.setProperty('--bump', (1 + 0.07 * pulse * singing).toFixed(4));
  };
}

// ---------- example scenes (delete / replace) ----------
export const SCENES: SceneDef[] = [
  {
    id: 'title',
    lines: [],
    start: 0,
    theme: 'dark',
    build(root) {
      const title = mk('div', 'title', root, 'SONG TITLE');
      return (c) => {
        popStyle(title, c.t, 0.5, 30, 0.5);
        title.style.transform += ` scale(${(1 + 0.04 * c.pulse).toFixed(3)})`;
      };
    },
  },
  {
    id: 'first-line',
    lines: [0],
    theme: 'dark',
    three: 'storm',
    opts: { energy: 1 },
    build(root) {
      const up = lyrics(root, [0], 'center huge');
      const sparks = Array.from({ length: 20 }, (_, i) => mk('div', 'spark', root, ''));
      return (c) => {
        up(c.t, c.pulse);
        sparks.forEach((s, i) => {
          const k = easeOut(prog(c.t, T0(0) + i * 0.05, T0(0) + 1 + i * 0.05));
          s.style.left = `${(50 + Math.cos(hash(i) * 6.28) * k * 40).toFixed(1)}%`;
          s.style.top = `${(50 + Math.sin(hash(i) * 6.28) * k * 40).toFixed(1)}%`;
          s.style.opacity = (1 - k).toFixed(2);
        });
      };
    },
  },
  {
    id: 'end',
    lines: [],
    start: Math.max(L[L.length - 1].e + 0.5, SONG_END - 3),
    theme: 'dark',
    build(root) {
      const t = mk('div', 'title', root, 'THE END');
      const fade = mk('div', 'fade', root);
      return (c) => {
        slideIn(t, c.t, c.t - c.local + 0.2);
        t.style.transform += ` scale(${easeOutBack(Math.min(1, c.local)).toFixed(3)})`;
        fade.style.opacity = prog(c.t, SONG_END - 1.5, SONG_END - 0.1).toFixed(3);
      };
    },
  },
];

// ---------- timeline (keep) ----------
export interface Timed extends SceneDef {
  t0: number;
  t1: number;
}
export const TIMELINE: Timed[] = SCENES.map((s) => {
  if (s.start !== undefined) return { ...s, t0: s.start, t1: 0 };
  const f = s.lines[0];
  // ideally just before the first word – but only once the previous line is complete and readable;
  // when the singer flows straight on, the cut may come up to 0.3 s after the first word
  const prevDone = f > 0 ? textDone(f - 1) + READ_HOLD : 0;
  const t0 = Math.min(L[f].t + 0.3, Math.max(L[f].t - 0.28, prevDone));
  return { ...s, t0, t1: 0 };
}).sort((a, b) => a.t0 - b.t0);
TIMELINE.forEach((s, i) => (s.t1 = i + 1 < TIMELINE.length ? TIMELINE[i + 1].t0 : SONG_END));
export const sceneAt = (t: number) => TIMELINE.find((s) => t >= s.t0 && t < s.t1) ?? TIMELINE[TIMELINE.length - 1];
