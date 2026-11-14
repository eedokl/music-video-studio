// "Pop-Up Video" overlay: lyric bubbles and info nuggets that pop in and out.
// Everything is derived from the current song time, so seeking just works.

import type { Fact, LyricLine } from './lyrics';
import { SECTION_COLORS } from './lyrics';

interface Live {
  el: HTMLElement;
  words: HTMLElement[];
}

const POP_IN = 0.42; // seconds of the bouncy pop-in
const POP_OUT = 0.24;

/** Overshoot ease (like the original cubic-bezier(0.2, 1.6, 0.4, 1)). */
function easeOutBack(x: number): number {
  const c1 = 2.2;
  const c3 = c1 + 1;
  return 1 + c3 * Math.pow(x - 1, 3) + c1 * Math.pow(x - 1, 2);
}

/** Scale/opacity of a bubble visible in [a, b) at time t, or null when hidden. */
function popState(t: number, a: number, b: number): { s: number; o: number } | null {
  if (t < a || t >= b + POP_OUT) return null;
  if (t >= b) {
    const x = (t - b) / POP_OUT;
    return { s: 1 - x * x, o: 1 - x };
  }
  const x = Math.min(1, (t - a) / POP_IN);
  return { s: Math.max(0, easeOutBack(x)), o: Math.min(1, x * 2.5) };
}

// Screen positions (percent of viewport) for lyric bubbles. Facts use the top band.
const LYRIC_SLOTS = [
  { x: 8, y: 60, tail: 'tail-right' },
  { x: 52, y: 66, tail: 'tail-left' },
  { x: 14, y: 42, tail: 'tail-right' },
  { x: 46, y: 48, tail: 'tail-left' },
  { x: 26, y: 72, tail: 'tail-right' },
  { x: 50, y: 36, tail: 'tail-left' },
];
const FACT_SLOTS = [
  { x: 4, y: 6 },
  { x: 62, y: 8 },
  { x: 34, y: 14 },
  { x: 66, y: 22 },
];

const LINE_LEAD = 0.12; // bubble pops slightly before the first word
const LINE_HOLD = 0.6; // stays a bit after the last word

export class PopupLayer {
  private live = new Map<string, Live>();

  constructor(
    private root: HTMLElement,
    private lines: LyricLine[],
    private facts: Fact[],
  ) {}

  update(t: number): void {
    const wanted = new Set<string>();
    const show = (id: string, st: { s: number; o: number }, make: () => Live) => {
      wanted.add(id);
      let item = this.live.get(id);
      if (!item) {
        item = make();
        this.live.set(id, item);
      }
      item.el.style.transform = `scale(${st.s.toFixed(4)})`;
      item.el.style.opacity = st.o.toFixed(3);
      return item;
    };

    this.lines.forEach((line, i) => {
      const next = this.lines[i + 1];
      const end = Math.min(line.e + LINE_HOLD, next ? next.t - 0.05 - POP_OUT : Infinity);
      const st = popState(t, line.t - LINE_LEAD, Math.max(end, line.t + 0.8));
      if (st) this.highlight(show(`l${i}`, st, () => this.makeLyric(line, i)), line, t);
    });

    this.facts.forEach((f, i) => {
      const st = popState(t, f.t, f.t + f.d);
      if (st) show(`f${i}`, st, () => this.makeFact(f, i));
    });

    for (const [id, item] of this.live) {
      if (!wanted.has(id)) {
        item.el.remove();
        this.live.delete(id);
      }
    }
  }

  private makeLyric(line: LyricLine, i: number): Live {
    const slot = LYRIC_SLOTS[i % LYRIC_SLOTS.length];
    const el = document.createElement('div');
    el.className = `bubble lyric ${slot.tail}`;
    el.style.left = `${slot.x}vw`;
    el.style.top = `${slot.y}vh`;
    el.style.setProperty('--accent', SECTION_COLORS[line.section]);
    el.style.setProperty('--tilt', `${((i * 37) % 7) - 3}deg`);
    const words: HTMLElement[] = [];
    line.text.split(' ').forEach((w, wi) => {
      const span = document.createElement('span');
      span.textContent = w;
      span.className = 'w';
      el.appendChild(span);
      if (wi < line.text.split(' ').length - 1) el.appendChild(document.createTextNode(' '));
      words.push(span);
    });
    this.root.appendChild(el);
    return { el, words };
  }

  private makeFact(f: Fact, i: number): Live {
    const slot = FACT_SLOTS[i % FACT_SLOTS.length];
    const el = document.createElement('div');
    el.className = 'bubble fact';
    el.style.left = `${slot.x}vw`;
    el.style.top = `${slot.y}vh`;
    el.style.setProperty('--tilt', `${((i * 53) % 9) - 4}deg`);
    const h = document.createElement('div');
    h.className = 'fact-title';
    h.textContent = f.title;
    const p = document.createElement('div');
    p.className = 'fact-text';
    p.textContent = f.text;
    el.append(h, p);
    this.root.appendChild(el);
    return { el, words: [] };
  }

  /** Karaoke-style: words light up as they are sung. */
  private highlight(item: Live, line: LyricLine, t: number): void {
    const n = item.words.length;
    item.words.forEach((span, wi) => {
      const ws = line.words?.[wi] ?? line.t + ((line.e - line.t) * wi) / n;
      span.classList.toggle('sung', t >= ws);
    });
  }
}
