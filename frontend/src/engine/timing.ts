// The timing model: resolves anchors (beat / bar / word / time) to seconds, derives the scene
// timeline and everything that depends on time (beat phase, riff hits, singer cues, effect events).
// Pure functions of the project + song time → preview and export are identical.

import type { Anchor, Line, Project, Scene } from '../types';
import type { Look, Perf } from './concert';

export interface TimedScene {
  scene: Scene;
  index: number;
  t0: number;
  t1: number;
}

const clamp = (x: number, a = 0, b = 1) => Math.min(b, Math.max(a, x));

export class Timing {
  readonly lines: Line[];
  readonly sung: Line[];
  readonly lineById = new Map<string, Line>();
  readonly scenes: TimedScene[];
  readonly lead: number;
  readonly readHold: number;
  readonly duration: number;
  private beats: number[];
  private period: number;
  private heyWords: number[] = [];

  constructor(readonly p: Project) {
    this.lines = p.lyrics?.lines ?? [];
    this.sung = this.lines.filter((l) => !l.unsung && l.words.length);
    this.lines.forEach((l) => this.lineById.set(l.id, l));
    this.lead = p.lyrics?.lead ?? 0.08;
    this.readHold = p.settings?.readHold ?? 0.3;
    this.duration = p.audio?.duration || 1;
    this.beats = p.grid?.beats?.length ? p.grid.beats : [];
    this.period = p.grid?.bpm ? 60 / p.grid.bpm : 0.5;
    for (const l of this.sung) l.words.forEach((w) => /^\W*hey/i.test(w.w) && this.heyWords.push(w.t - this.lead));
    this.scenes = this.buildScenes();
  }

  // ---------- beat grid ----------
  /** fractional beat index at time t (follows the active grid, extrapolates outside) */
  beatAt(t: number): number {
    const b = this.beats;
    if (b.length < 2) return t / this.period;
    if (t <= b[0]) return (t - b[0]) / (b[1] - b[0]);
    if (t >= b[b.length - 1]) return b.length - 1 + (t - b[b.length - 1]) / (b[b.length - 1] - b[b.length - 2]);
    let lo = 0;
    let hi = b.length - 1;
    while (hi - lo > 1) {
      const m = (lo + hi) >> 1;
      if (b[m] <= t) lo = m;
      else hi = m;
    }
    return lo + (t - b[lo]) / (b[hi] - b[lo]);
  }
  timeAtBeat(i: number): number {
    const b = this.beats;
    if (b.length < 2) return i * this.period;
    if (i <= 0) return b[0] + i * (b[1] - b[0]);
    if (i >= b.length - 1) return b[b.length - 1] + (i - (b.length - 1)) * (b[b.length - 1] - b[b.length - 2]);
    const k = Math.floor(i);
    return b[k] + (i - k) * (b[k + 1] - b[k]);
  }
  barStart(bar: number): number {
    const g = this.p.grid;
    return this.timeAtBeat((g?.downbeatPhase ?? 0) + bar * (g?.beatsPerBar ?? 4));
  }
  /** bar number (fractional) at time t */
  barAt(t: number): number {
    const g = this.p.grid;
    return (this.beatAt(t) - (g?.downbeatPhase ?? 0)) / (g?.beatsPerBar ?? 4);
  }
  pulse(t: number): number {
    const b = this.beatAt(t);
    return Math.exp(-(b - Math.floor(b)) * 5);
  }

  // ---------- anchors ----------
  /** word start/end as shown on screen (lyric lead applied) */
  wordTime(lineId: string, word: number, edge: 'start' | 'end' = 'start'): number | null {
    const l = this.lineById.get(lineId);
    const w = l?.words[Math.max(0, Math.min(word, (l?.words.length ?? 1) - 1))];
    if (!w) return null;
    return (edge === 'end' ? w.e : w.t) - this.lead;
  }
  anchor(a: Anchor | undefined, fallback = 0): number {
    if (!a) return fallback;
    switch (a.kind) {
      case 'time':
        return a.t;
      case 'beat':
        return this.timeAtBeat(a.beat) + (a.offset ?? 0);
      case 'bar':
        return this.barStart(a.bar) + (a.offset ?? 0);
      case 'word':
        return (this.wordTime(a.line, a.word, a.edge) ?? fallback) + (a.offset ?? 0);
      default:
        return fallback;
    }
  }
  /** when the last letter of a line has landed (same maths as SungLine) */
  textDone(l: Line): number {
    const last = l.words[l.words.length - 1];
    const s = last.t - this.lead;
    const e = Math.min(Math.max(last.e - this.lead, s + 0.12), s + 1.4);
    return s + (e - s) * 0.65 + 0.21;
  }

  private buildScenes(): TimedScene[] {
    const sungIndex = new Map(this.sung.map((l, i) => [l.id, i]));
    const list = (this.p.scenes ?? []).map((scene, index) => {
      let t0: number;
      if (scene.start?.kind === 'auto' || !scene.start) {
        const first = scene.lines.map((id) => this.lineById.get(id)).find((l) => l && !l.unsung && l.words.length);
        if (first) {
          const i = sungIndex.get(first.id) ?? 0;
          const prevDone = i > 0 ? this.textDone(this.sung[i - 1]) + this.readHold : 0;
          const ft = first.words[0].t;
          t0 = Math.min(ft + 0.3, Math.max(ft - 0.28, prevDone));
        } else t0 = index === 0 ? 0 : Number.NaN;
      } else t0 = this.anchor(scene.start, 0);
      return { scene, index, t0, t1: 0 };
    });
    // scenes whose lines are all unsung (e.g. a "Hey! Hey!" nobody sings) have no start of their own:
    // they get zero length at the start of the next scene, so the previous scene simply keeps running
    for (let i = list.length - 1; i >= 0; i--) {
      if (Number.isNaN(list[i].t0)) {
        const next = list.slice(i + 1).find((x) => !Number.isNaN(x.t0));
        list[i].t0 = next ? next.t0 : this.duration;
      }
    }
    list.sort((a, b) => a.t0 - b.t0);
    if (list.length) list[0].t0 = Math.min(0, list[0].t0);
    list.forEach((s, i) => (s.t1 = i + 1 < list.length ? list[i + 1].t0 : this.duration));
    return list;
  }
  sceneAt(t: number): TimedScene | null {
    const s = this.scenes;
    for (let i = s.length - 1; i >= 0; i--) if (t >= s[i].t0) return s[i];
    return s[0] ?? null;
  }

  // ---------- music + performance cues ----------
  hit(t: number) {
    let flash = 0;
    let pyro = 0;
    const hits = this.p.hits?.hits ?? [];
    const big = new Set(this.p.hits?.big ?? []);
    for (const h of hits) {
      if (h > t + 0.01) break;
      const d = t - h;
      if (d > 2) continue;
      const isBig = big.has(h);
      flash = Math.max(flash, Math.exp(-d * (isBig ? 7 : 12)) * (isBig ? 1 : 0.45));
      if (isBig && d < 1.6) pyro = Math.max(pyro, d < 0.06 ? d / 0.06 : d < 0.45 ? 1 : Math.exp(-(d - 0.45) * 4.5));
    }
    return { flash, pyro };
  }

  perf(t: number, heldEnv: (t: number) => { env: number; release: number }): Perf {
    let sing = 0;
    for (const l of this.sung) {
      if (t >= l.words[0].t - 0.15 && t <= l.words[l.words.length - 1].e) {
        sing = 1;
        break;
      }
    }
    let hey = 0;
    for (const h of this.heyWords) {
      const d = t - h;
      if (d > -0.12 && d < 1.2) hey = Math.max(hey, d < 0 ? 1 + d / 0.12 : Math.exp(-d * 2.2));
    }
    const he = heldEnv(t);
    const dur = this.duration;
    const bow = clamp((t - (dur - 6.6)) / 1.2) * (1 - clamp((t - (dur - 3.8)) / 1.2));
    return { sing, hey: clamp(hey), held: Math.max(clamp(he.env * 1.4), he.release * 0.6), bow };
  }

  /** effect events active around time t, in the shape the concert engine expects */
  eventLook(t: number): Partial<Look> {
    const out: Partial<Look> = { co2: [], fireworks: [] };
    let confetti: number | undefined;
    for (const ev of this.p.events ?? []) {
      const at = this.anchor(ev.at, -1);
      if (ev.type === 'co2') out.co2!.push(at);
      else if (ev.type === 'fireworks') out.fireworks!.push(at);
      else if (ev.type === 'confetti') {
        if (at <= t && (confetti === undefined || at > confetti)) confetti = at;
      } else if (ev.type === 'sparks') {
        const until = this.anchor(ev.until, at + 2);
        if (t > at - 0.5 && t < until + 1) out.sparks = [at, until];
      }
    }
    out.fireworks = out.fireworks!.sort((a, b) => a - b);
    if (confetti !== undefined) out.confetti = confetti;
    return out;
  }
}
