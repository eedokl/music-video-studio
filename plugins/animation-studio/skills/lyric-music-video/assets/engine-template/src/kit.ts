// Motion-graphics kit: a fixed 1920 x 1080 stage, appear/pop/stamp helpers, self-drawing SVG lines, subtitle lyrics,
// big kinetic type, a split-flap board, a chess board with moves and a scrolling list with a counter.
// Optional - import what a scene needs (styles: kit.css, imported here). Everything is a pure function of song time.
//
// The rule these helpers serve: TEXT FOLLOWS THE WORDS, GRAPHICS FOLLOW THE BEAT. Lyrics appear on W(line, word);
// every graphic event (a move, a tick, a stamp, a row, a card) lands on the beat grid: snapBeat(time, div, dir) from
// lyrics.ts, sequences in steps of BEAT, BEAT / 2 or BEAT / 4, and hit(t, at) gives a short accent on landing.
//
// Import cycle: this file imports W / T0 from scenes.ts, and scenes.ts (or a scene file it imports) imports this
// file. That is fine as long as nothing here or in a scene file USES an import of scenes.ts at module top level -
// only inside functions ("Cannot access 'timeAtBeat' before initialization" otherwise).

import './kit.css';
import { LEAD } from './lyric';
import { LINES } from './lyrics';
import { T0, W } from './scenes';
import { clamp, easeInOut, easeOut, easeOutBack, hash, mk, prog } from './util';

const NS = 'http://www.w3.org/2000/svg';
type El = HTMLElement | SVGElement;

// ---------- stage and placement ----------
/** A 1920 x 1080 stage scaled to the window: lay scenes out in pixels (parent: the scene root). */
export function stage(root: HTMLElement) {
  const st = mk('div', 'kit-st', root);
  st.style.transform = `scale(${(innerWidth / 1920).toFixed(5)})`;
  return st;
}
/** An absolutely placed box (class "a" = position absolute, no wrapping; add white-space: normal where text wraps). */
export function box(p: HTMLElement, cls: string, x: number, y: number, text?: string, w?: number, h?: number) {
  const e = mk('div', `a ${cls}`, p, text);
  e.style.left = `${x}px`;
  e.style.top = `${y}px`;
  if (w !== undefined) e.style.width = `${w}px`;
  if (h !== undefined) e.style.height = `${h}px`;
  return e;
}
export const op = (e: El, k: number) => (e.style.opacity = clamp(k).toFixed(3));
/** Fade + rise at time a. */
export function up(e: El, t: number, a: number, dy = 16, d = 0.2) {
  const k = easeOut(prog(t, a, a + d));
  op(e, k);
  e.style.transform = `translateY(${((1 - k) * dy).toFixed(1)}px)`;
}
/** Pop in with a small overshoot at time a. */
export function pop(e: El, t: number, a: number, d = 0.22, extra = '') {
  const x = prog(t, a, a + d);
  op(e, x * 3);
  e.style.transform = `${extra} scale(${(x <= 0 ? 0.6 : 0.6 + 0.4 * easeOutBack(x)).toFixed(4)})`;
}
/** A rubber stamp slamming down at time a (start it ~0.1 s before the beat it should hit). */
export function stamp(e: El, t: number, a: number, rot = -8) {
  const x = prog(t, a, a + 0.16);
  op(e, x <= 0 ? 0 : 0.95);
  e.style.transform = `rotate(${rot}deg) scale(${(2.3 - 1.3 * easeOut(x)).toFixed(3)})`;
}
/** A short accent after something landed at time a: 1 -> 0 (scale(1 + 0.1 * hit(t, a)), a glow, ...). */
export const hit = (t: number, a: number, d = 0.3) => (t < a ? 0 : Math.max(0, 1 - (t - a) / d));

// ---------- self-drawing lines ----------
export function svg(p: HTMLElement) {
  const s = document.createElementNS(NS, 'svg');
  s.setAttribute('viewBox', '0 0 1920 1080');
  s.setAttribute('class', 'a kit-sv');
  p.appendChild(s);
  return s;
}
/** A path; with draw = true it is hidden until reveal(path, 0..1). */
export function path(s: SVGElement, d: string, stroke: string, width = 4, draw = true, glow = false) {
  const e = document.createElementNS(NS, 'path');
  e.setAttribute('d', d);
  e.setAttribute('stroke', stroke);
  e.setAttribute('stroke-width', String(width));
  if (draw) {
    e.setAttribute('pathLength', '1');
    e.style.strokeDasharray = '1';
    e.style.strokeDashoffset = '1';
  }
  if (glow) e.style.filter = `drop-shadow(0 0 10px ${stroke})`;
  s.appendChild(e);
  return e;
}
export const reveal = (e: SVGElement, k: number) => (e.style.strokeDashoffset = (1 - clamp(k)).toFixed(4));
export const poly = (pts: number[][]) => pts.map((p, i) => `${i ? 'L' : 'M'}${p[0].toFixed(1)} ${p[1].toFixed(1)}`).join('');

// ---------- lyrics as a subtitle line ----------
/** One line at a time: each word rises in when it is sung; only the word being sung is white and underlined,
 *  sung words cool to grey. Returns the updater (song time). Style: .kit-subs in kit.css. */
export function subs(st: HTMLElement, lines: number[], y = 950) {
  const L = LINES;
  const bx = box(st, 'kit-subs', 0, y);
  const rows = lines.map((li) => {
    const r = mk('div', 'row', bx);
    if (L[li].text.length > 66) r.style.fontSize = '0.88em';
    return { li, r, ws: L[li].text.split(' ').map((w) => mk('span', 'w', r, w)) };
  });
  return (t: number) => {
    let act = 0;
    rows.forEach((r, k) => {
      if (t >= T0(r.li) - 0.3) act = k;
    });
    rows.forEach((r, k) => {
      r.r.style.display = k === act ? 'block' : 'none';
      if (k !== act) return;
      r.ws.forEach((s, i) => {
        const a = W(r.li, i);
        const kk = easeOut(prog(t, a - 0.02, a + 0.18));
        op(s, kk);
        s.style.transform = `translateY(${((1 - kk) * 14).toFixed(1)}px)`;
        const end = Math.max((L[r.li].ends?.[i] ?? a + 0.3) - LEAD, a + 0.25) + 0.1;
        const next = i + 1 < r.ws.length ? W(r.li, i + 1) : 1e9;
        const off = Math.min(end, next);
        const hot = t < a ? 0 : 1 - prog(t, off, off + (next < end ? 0.12 : 0.35));
        s.style.setProperty('--hot', hot.toFixed(2));
      });
    });
  };
}

// ---------- big kinetic type ----------
export type KWord = [text: string, time: number, cls?: string];
/** Rows of big words: each slams in from a large blurred ghost at its time; the block bumps and brightens with
 *  `pulse` (pass c.pulse). Word classes: r / c / g (accent colours in kit.css) or your own. */
export function kinetic(st: HTMLElement, rows: { y: number; size: number; words: KWord[] }[], z = 0) {
  const els = rows.map((r) => {
    const row = box(st, 'kit-krow', 0, r.y);
    row.style.fontSize = `${r.size}px`;
    if (z) row.style.zIndex = String(z);
    return { row, ws: r.words.map(([txt, at, cls]) => ({ s: mk('span', `kw ${cls ?? ''}`, row, txt), at })) };
  });
  return (t: number, pulse = 0) => {
    for (const r of els) {
      r.row.style.transform = `scale(${(1 + 0.016 * pulse).toFixed(4)})`;
      r.row.style.filter = pulse > 0.02 ? `brightness(${(1 + 0.22 * pulse).toFixed(3)})` : '';
      for (const { s, at } of r.ws) {
        const x = prog(t, at, at + 0.2);
        const e = easeOut(x);
        op(s, x <= 0 ? 0 : 0.3 + 0.7 * e);
        s.style.transform = `scale(${(2.2 - 1.2 * e).toFixed(3)})`;
        s.style.filter = x > 0 && x < 1 ? `blur(${((1 - e) * 8).toFixed(1)}px)` : '';
      }
    }
  };
}

// ---------- props ----------
const FLAP = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-:';
/** One cell of a split-flap board with n characters. update(text, age, seed): age = seconds since it started
 *  flipping (negative = blank); the letters settle left to right. */
export function flap(p: HTMLElement, x: number, y: number, n: number, cls = '') {
  const e = box(p, `kit-flap ${cls}`, x, y);
  const sp = Array.from({ length: n }, () => mk('span', '', e, ' '));
  return (txt: string, age: number, seed = 0) => {
    sp.forEach((s, j) => {
      const settle = 0.25 + j * 0.035;
      s.textContent = age < 0 ? ' ' : age >= settle ? (txt[j] ?? ' ') : FLAP[Math.floor(hash(seed + j * 3.1 + Math.floor(age * 24) * 7.7) * FLAP.length)];
    });
  };
}

const START = 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR';
const GLYPH: Record<string, string> = { k: '♚', q: '♛', r: '♜', b: '♝', n: '♞', p: '♟' };
/** A chess board (class wood | neon | your own on .kit-bd) from a FEN position. moves([[fromFile, fromRank, toFile,
 *  toRank, time, highlight?], ...]) returns the updater - give the times in beats (one move per BEAT). */
export function chess(p: HTMLElement, x: number, y: number, size: number, cls: string, fen = START) {
  const c = size / 8;
  const bd = box(p, `kit-bd ${cls}`, x, y, undefined, size, size);
  for (let r = 0; r < 8; r++) for (let f = 0; f < 8; f++) box(bd, `sq ${(f + r) % 2 ? 'd' : 'l'}`, f * c, r * c, undefined, c, c);
  const marks = box(bd, '', 0, 0);
  const pcs: { el: HTMLElement; f: number; r: number }[] = [];
  fen.split('/').forEach((row, ri) => {
    let f = 0;
    for (const ch of row) {
      if (/\d/.test(ch)) {
        f += Number(ch);
        continue;
      }
      const e = box(bd, `pc ${ch === ch.toUpperCase() ? 'w' : 'b'}`, f * c, ri * c, GLYPH[ch.toLowerCase()], c, c);
      e.style.fontSize = `${c * 0.8}px`;
      e.style.lineHeight = `${c}px`;
      pcs.push({ el: e, f, r: 7 - ri });
      f++;
    }
  });
  function moves(list: [number, number, number, number, number, string?][]) {
    const ms = list.map(([f0, r0, f1, r1, at, col]) => {
      const pc = pcs.find((q) => q.f === f0 && q.r === r0)!;
      pc.f = f1;
      pc.r = r1;
      const h1 = box(marks, '', f0 * c, (7 - r0) * c, undefined, c, c);
      const h2 = box(marks, '', f1 * c, (7 - r1) * c, undefined, c, c);
      h1.style.background = h2.style.background = col ?? 'rgba(233,161,59,0.55)';
      return { pc, f0, r0, f1, r1, at, h1, h2 };
    });
    return (t: number) => {
      ms.forEach((m, i) => {
        if (t >= m.at) {
          const k = easeInOut(prog(t, m.at, m.at + 0.28));
          m.pc.el.style.left = `${(m.f0 + (m.f1 - m.f0) * k) * c}px`;
          m.pc.el.style.top = `${(7 - (m.r0 + (m.r1 - m.r0) * k)) * c}px`;
        }
        const on = t >= m.at && t < (ms[i + 1]?.at ?? 1e9) ? 1 : 0;
        op(m.h1, on * 0.6);
        op(m.h2, on);
      });
    };
  }
  return { bd, c, moves };
}

/** A document window whose numbered lines arrive one by one while the list scrolls smoothly.
 *  update(nf): nf = how many lines are there (fractional - e.g. items.length * prog(t, a, b)); returns the count.
 *  Mark lines with li.classList / className "li cut" for a red strike-through. */
export function scrollList(p: HTMLElement, x: number, y: number, title: string, items: string[], w = 900, h = 660, lineH = 42) {
  const d = box(p, 'kit-doc', x, y, undefined, w, h);
  mk('div', 'bar', d, title);
  const lst = mk('div', 'lst', d);
  const lis = items.map((s, i) => {
    const li = mk('div', 'li', lst);
    mk('b', '', li, `${i + 1}.`);
    li.appendChild(document.createTextNode(s));
    return li;
  });
  mk('div', 'fade', d);
  const view = h - 110;
  return {
    el: d,
    lis,
    /** lines appear up to nf; the list follows the last line */
    update(nf: number) {
      lis.forEach((li, i) => {
        const k = clamp((nf - i) * 1.6);
        op(li, k);
        li.style.transform = `translateX(${((1 - k) * 18).toFixed(1)}px)`;
      });
      lst.style.transform = `translateY(${(-Math.max(0, nf * lineH - view + 40)).toFixed(1)}px)`;
      return Math.min(items.length, Math.ceil(nf));
    },
    /** all lines shown; scroll so that line nf (fractional) stays in view (e.g. while lines are struck out) */
    follow(nf: number) {
      lst.style.transform = `translateY(${(-clamp(nf * lineH - view * 0.55, 0, Math.max(0, items.length * lineH - view + 30))).toFixed(1)}px)`;
    },
  };
}
