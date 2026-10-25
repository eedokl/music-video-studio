// Big typed lyric text: each word is typed in when it is sung,
// the word being sung is highlighted green, a block caret follows the typing.

import type { LyricLine } from './lyrics';
import { clamp, mk } from './util';

export class TypedLine {
  readonly el: HTMLElement;
  private chars: { span: HTMLElement; word: number; k: number; n: number }[] = [];
  private starts: number[];
  private ends: number[];

  constructor(parent: HTMLElement, private line: LyricLine, cls = '') {
    this.el = mk('div', `typed ${cls}`, parent);
    const words = line.text.split(' ');
    this.starts = words.map((_, i) => line.words?.[i] ?? line.t + ((line.e - line.t) * i) / words.length);
    this.ends = this.starts.map((s, i) => (i + 1 < words.length ? this.starts[i + 1] : Math.max(line.e, s + 0.3)));
    words.forEach((w, wi) => {
      const ws = mk('span', 'tw', this.el);
      [...w].forEach((ch, k) => this.chars.push({ span: mk('span', 'tc', ws, ch), word: wi, k, n: w.length }));
      if (wi < words.length - 1) this.el.appendChild(document.createTextNode(' '));
    });
  }

  /** hold: keep the caret blinking this long after the line ends */
  update(t: number, hold = 0.4) {
    let last: HTMLElement | null = null;
    for (const c of this.chars) {
      const ws = this.starts[c.word];
      const we = this.ends[c.word];
      const typeDur = Math.max(0.06, Math.min(0.24, (we - ws) * 0.75));
      const visible = t >= ws + (typeDur * c.k) / c.n;
      c.span.style.visibility = visible ? 'visible' : 'hidden';
      const now = visible && t < we && t < this.line.e + 0.05;
      c.span.classList.toggle('now', now);
      if (visible) last = c.span;
      c.span.classList.remove('caret');
    }
    const blink = Math.floor(t * 3) % 2 === 0;
    if (last && t < this.line.e + hold && (t < this.line.e || blink)) last.classList.add('caret');
    return clamp((t - this.line.t) / Math.max(0.1, this.line.e - this.line.t));
  }
}

export function __setLead(_v: number) {}
