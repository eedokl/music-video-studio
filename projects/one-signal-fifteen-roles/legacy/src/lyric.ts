// Sung lyric: every letter appears at the moment it is sung (spread over the word's real
// duration from the audio), the word being sung is tinted, and the caller bumps the block on the beat.
//  - mode 'pop'  : letters pop in (default)
//  - mode 'type' : typewriter with a blinking block cursor (PC screen ending)
//  - held        : the last word is a long held note – its vowel stretches with the voice

import type { LyricLine } from './lyrics';
import { clamp, easeOut, easeOutBack, mk } from './util';
import { type TrackName, vocalEnv, vocalPitch } from './vocal';

/** Show text this much earlier than the transcribed word times (they lag the singing slightly). */
export let LEAD = 0.08;
export function __setLead(v: number) {
  LEAD = v;
}
/** Letters are spread over this part of the sung word. */
const SPREAD = 0.65;
const isLetter = (c: string) => /[\p{L}\p{N}]/u.test(c);

interface Ch {
  span: HTMLElement;
  at: number;
}

export interface LineOpts {
  mode?: 'pop' | 'type';
  held?: TrackName;
  heldWord?: number; // which word is held (default: the last one)
  heldVowel?: number; // which letter of that word to stretch (default: vowel of the last syllable)
}

export class SungLine {
  readonly el: HTMLElement;
  private chars: Ch[] = [];
  private words: { span: HTMLElement; s: number; e: number }[] = [];
  private held: HeldWord | null = null;
  private mode: 'pop' | 'type';

  constructor(parent: HTMLElement, line: LyricLine, cls = '', opts: LineOpts = {}) {
    this.mode = opts.mode ?? 'pop';
    this.el = mk('div', `sung ${cls}`, parent);
    const ws = line.text.split(' ');
    const starts = ws.map((_, i) => line.words?.[i] ?? line.t + ((line.e - line.t) * i) / ws.length);
    ws.forEach((w, i) => {
      const s = starts[i] - LEAD;
      const next = (i + 1 < ws.length ? starts[i + 1] : line.e + 0.25) - LEAD;
      // sung duration of the word: from the audio when available, never past the next word
      let e = (line.ends?.[i] ?? next + LEAD) - LEAD;
      if (opts.held && i === (opts.heldWord ?? ws.length - 1)) {
        this.held = new HeldWord(this.el, w, s, e, opts.held, opts.heldVowel);
        this.words.push({ span: this.held.el, s, e });
        if (i < ws.length - 1) this.el.appendChild(document.createTextNode(' '));
        return;
      }
      e = Math.min(Math.max(e, s + 0.12), Math.max(next, s + 0.12), s + 1.4);
      const span = mk('span', 'sw', this.el);
      this.words.push({ span, s, e });
      const letters = [...w];
      const n = letters.filter(isLetter).length || 1;
      let k = 0;
      letters.forEach((c) => {
        const L = isLetter(c);
        // letters are spread over the first part of the sung word; punctuation follows the last letter
        const at = s + ((e - s) * SPREAD * Math.min(k, n - 1)) / Math.max(1, n - 1);
        if (L) k++;
        this.chars.push({ span: mk('span', 'sc', span, c), at: L ? at : at + 0.02 });
      });
      if (i < ws.length - 1) this.el.appendChild(document.createTextNode(' '));
    });
  }

  update(t: number) {
    let last: HTMLElement | null = null;
    for (const c of this.chars) {
      const age = t - c.at;
      if (this.mode === 'type') {
        c.span.style.visibility = age >= 0 ? 'visible' : 'hidden';
        c.span.classList.remove('caret');
        if (age >= 0) last = c.span;
        continue;
      }
      if (age < 0) {
        c.span.style.opacity = '0';
        c.span.style.transform = 'scale(1.9)';
        continue;
      }
      // stamped in like a metal press: big → slam → tiny rebound
      const k = clamp(age / 0.09);
      c.span.style.opacity = clamp(age / 0.03).toFixed(2);
      const sc = k < 1 ? 1.9 - 0.95 * easeOut(k) : 0.95 + 0.05 * easeOutBack(clamp((age - 0.09) / 0.12));
      c.span.style.transform = `scale(${sc.toFixed(3)})`;
    }
    if (this.mode === 'type' && last) last.classList.add('caret');
    for (const w of this.words) w.span.classList.toggle('now', t >= w.s && t < w.e + 0.05);
    this.held?.update(t);
  }
}

/**
 * A long held note: "all?" → "aaaaall?", "right" → "riiiiiight".
 * The vowel copies appear while the note is held, wave with the vocal loudness and pitch,
 * a glowing ribbon traces the pitch under the word, and the ending letters land on the release.
 */
class HeldWord {
  readonly el: HTMLElement;
  private pre: HTMLElement[] = [];
  private vowels: HTMLElement[] = [];
  private post: HTMLElement[] = [];
  private svg: SVGSVGElement;
  private path: SVGPathElement;
  private glow: SVGPathElement;
  private ring: HTMLElement;

  constructor(parent: HTMLElement, word: string, private s: number, private e: number, private track: TrackName, vowelAt?: number) {
    this.el = mk('span', 'sw held', parent);
    const chars = [...word];
    // the vowel of the last syllable (a final silent "e" does not count)
    let end = chars.length - 1;
    while (end > 0 && !isLetter(chars[end])) end--;
    if (end > 1 && /e/i.test(chars[end]) && !/[aeiou]/i.test(chars[end - 1])) end--;
    let v = end;
    while (v > 0 && !/[aeiouy]/i.test(chars[v])) v--;
    v = vowelAt ?? Math.max(0, v);
    chars.slice(0, v).forEach((c) => this.pre.push(mk('span', 'sc', this.el, c)));
    const N = Math.min(8, Math.max(5, Math.round((e - s) * 3))); // ~3 vowel copies per held second, max 8
    for (let i = 0; i < N; i++) {
      const sp = mk('span', 'sc hv', this.el, chars[v]);
      const k = i / Math.max(1, N - 1);
      // brand turquoise → blue → purple across the stretch
      const c0 = k < 0.5 ? [63, 208, 200] : [0, 123, 192];
      const c1 = k < 0.5 ? [0, 123, 192] : [190, 60, 180];
      const kk = k < 0.5 ? k * 2 : (k - 0.5) * 2;
      sp.style.color = `rgb(${c0.map((v, j) => Math.round(v + (c1[j] - v) * kk)).join(', ')})`;
      this.vowels.push(sp);
    }
    chars.slice(v + 1).forEach((c) => this.post.push(mk('span', 'sc', this.el, c)));
    const NS = 'http://www.w3.org/2000/svg';
    this.svg = document.createElementNS(NS, 'svg');
    this.svg.setAttribute('class', 'ribbon-svg');
    this.glow = document.createElementNS(NS, 'path');
    this.glow.setAttribute('class', 'rb-glow');
    this.path = document.createElementNS(NS, 'path');
    this.path.setAttribute('class', 'rb-line');
    this.svg.append(this.glow, this.path);
    this.el.appendChild(this.svg);
    this.ring = mk('span', 'held-ring', this.el);
  }

  update(t: number) {
    const { s, e } = this;
    const env = vocalEnv(this.track, t + LEAD);
    const holding = t >= s && t < e;
    const u = clamp((t - s - 0.12) / Math.max(0.2, e - s - 0.35));
    const show = (el: HTMLElement, at: number) => {
      const age = t - at;
      el.style.opacity = age < 0 ? '0' : clamp(age / 0.06).toFixed(2);
    };
    this.pre.forEach((p) => show(p, s));
    // vowel copies: the first one immediately, then more while the note is held
    const visible = t < s ? 0 : 1 + Math.floor(u * (this.vowels.length - 1) + 1e-6);
    this.vowels.forEach((v, i) => {
      const on = i < visible;
      v.style.display = on ? 'inline-block' : 'none';
      if (!on) return;
      const wave = Math.sin(t * 11 - i * 0.9) * (holding ? 0.06 + env * 0.14 : 0.02);
      const lift = holding ? vocalPitch(this.track, t + LEAD - (visible - 1 - i) * 0.08) * -0.02 : 0;
      const sy = holding ? 1 + env * 0.35 : 1;
      v.style.transform = `translateY(${(wave + lift).toFixed(3)}em) scaleY(${sy.toFixed(3)})`;
      v.style.textShadow = holding ? `0 0 ${(0.1 + env * 0.5).toFixed(2)}em currentColor` : 'none';
    });
    // the ending consonants land on the release
    const rel = e - 0.12;
    this.post.forEach((p, i) => show(p, rel + i * 0.05));
    const ra = t - rel;
    const punch = ra >= 0 && ra < 0.5 ? 1 + 0.18 * Math.exp(-ra * 8) * Math.sin(Math.min(Math.PI, ra * 12)) : 1;
    this.el.style.transform = `scale(${punch.toFixed(3)})`;
    // burst ring on the release
    const rk = clamp(ra / 0.7);
    this.ring.style.opacity = ra >= 0 && rk < 1 ? (1 - rk).toFixed(2) : '0';
    this.ring.style.transform = `translate(-50%, -50%) scale(${(0.2 + rk * 3.2).toFixed(3)})`;
    // pitch ribbon under the word, drawn up to "now"
    const w = Math.max(10, this.el.offsetWidth);
    const h = 60;
    this.svg.setAttribute('viewBox', `0 0 ${w} ${h}`);
    let d = '';
    const t1 = Math.min(t, e);
    const steps = 60;
    for (let i = 0; i <= steps; i++) {
      const tt = s + ((t1 - s) * i) / steps;
      const x = ((tt - s) / Math.max(0.1, e - s)) * w;
      const y = h / 2 - vocalPitch(this.track, tt + LEAD) * 3 + Math.sin(tt * 18) * vocalEnv(this.track, tt + LEAD) * 6;
      d += `${i ? 'L' : 'M'}${x.toFixed(1)} ${y.toFixed(1)}`;
    }
    const vis = t >= s + 0.1 && t < e + 0.6;
    const fade = t > e ? 1 - clamp((t - e) / 0.6) : 1;
    this.path.setAttribute('d', vis ? d : '');
    this.glow.setAttribute('d', vis ? d : '');
    this.path.style.strokeWidth = (2 + env * 5).toFixed(2);
    this.glow.style.strokeWidth = (8 + env * 18).toFixed(2);
    this.svg.style.opacity = fade.toFixed(2);
  }
}

/** Loudness of a held note while it sounds, plus a release flash (for scene / 3D effects). */
export function heldFx(t: number, line: LyricLine, track: TrackName) {
  const last = (line.words?.length ?? 1) - 1;
  const s = (line.words?.[last] ?? line.t) - LEAD;
  const e = (line.ends?.[last] ?? line.e) - LEAD;
  const env = t >= s && t < e ? vocalEnv(track, t + LEAD) : 0;
  const ra = t - (e - 0.12);
  return { env, release: ra >= 0 ? Math.exp(-ra * 4) : 0, s, e };
}
