// The preview: concert world + LED wall + letter-synced lyrics + broadcast overlay, all driven by
// the project file and song time. The editor and the MP4 export use exactly this class.

import type { Line, Project, Scene } from '../types';
import { Concert, type Look } from './concert';
import { heldFx, type LyricLine, SungLine, setLead } from './lyric';
import './overlay.css';
import { type TimedScene, Timing } from './timing';
import { drawWall, loadCustom, makeApi, type WallApi } from './walls';
import { clamp, easeOut, mk, prog } from './util';
import { setTracks } from './vocal';

const DEFAULT_LOOK: Look = { beams: ['#ffffff'], wash: '#ffffff', energy: 0.5, pattern: 'sweep' };

export const toLyric = (l: Line): LyricLine => ({
  t: l.words[0]?.t ?? 0,
  e: l.words[l.words.length - 1]?.e ?? 0,
  text: l.words.map((w) => w.w).join(' '),
  words: l.words.map((w) => w.t),
  ends: l.words.map((w) => w.e),
});

export class Player {
  readonly concert: Concert;
  timing!: Timing;
  project!: Project;
  private api!: WallApi;
  private bust = '';
  private lyricsEl: HTMLElement;
  private live: HTMLElement;
  private camLabel: HTMLElement;
  private showTitle: HTMLElement;
  private card: HTMLElement;
  private endCard: HTMLElement;
  private liveDot: HTMLElement;
  private flash: HTMLElement;
  private current: TimedScene | null = null;
  private lyricUpd: ((t: number, pulse: number) => void) | null = null;
  private heldLines: { line: LyricLine; track: string }[] = [];

  constructor(readonly root: HTMLElement, readonly fileUrl: (rel: string) => string, render = false) {
    root.classList.add('mv-player');
    const stage = mk('div', 'mv-stage', root);
    this.concert = new Concert(stage, render);
    mk('div', 'mv-vignette', root);
    this.lyricsEl = mk('div', 'mv-lyrics', root);
    this.live = mk('div', 'mv-live', root);
    const badge = mk('div', 'live-badge', this.live);
    this.liveDot = mk('span', 'live-dot', badge);
    mk('span', '', badge, 'LIVE');
    this.camLabel = mk('div', 'cam-label', this.live);
    this.showTitle = mk('div', 'show-title', this.live);
    this.card = mk('div', 'title-card', this.live);
    this.endCard = mk('div', 'end-card', this.live);
    this.flash = mk('div', 'mv-flash', root);
  }

  /** (re)load a project; bust = version string so edited custom wall modules reload */
  async setProject(p: Project, bust = '') {
    this.project = p;
    this.bust = bust;
    this.timing = new Timing(p);
    setTracks(p.held);
    setLead(p.lyrics?.lead ?? 0.08);
    this.api = makeApi(this.timing, this.fileUrl);
    this.heldLines = (p.held ?? []).flatMap((h) => {
      const l = this.timing.lineById.get(h.line);
      return l && !l.unsung ? [{ line: toLyric(l), track: h.name }] : [];
    });
    this.card.innerHTML = '';
    mk('div', 'tc-small', this.card, 'LIVE');
    mk('div', 'tc-big', this.card, (p.title ?? '').toUpperCase());
    this.endCard.innerHTML = '';
    mk('div', 'tc-big', this.endCard, (p.title ?? '').toUpperCase());
    mk('div', 'tc-sub', this.endCard, 'LIVE');
    this.showTitle.textContent = `${(p.title ?? '').toUpperCase()} · LIVE`;
    this.current = null;
    await loadCustom((p.scenes ?? []).map((s) => s.wall).filter((w): w is NonNullable<typeof w> => !!w), this.fileUrl, bust);
  }

  resize(w: number, h: number) {
    this.concert.resize(w, h);
  }

  lookOf(s: Scene): Look {
    const l = typeof s.look === 'string' ? this.project.looks?.[s.look] : s.look;
    return l ?? DEFAULT_LOOK;
  }

  private buildLyrics(ts: TimedScene) {
    this.lyricsEl.innerHTML = '';
    this.lyricUpd = null;
    const s = ts.scene;
    const lines = s.lines.map((id) => this.timing.lineById.get(id)).filter((l): l is Line => !!l && !l.unsung && l.words.length > 0);
    if (!lines.length || s.lyr === 'none') return;
    const box = mk('div', `lyr lyr-${s.lyr ?? 'low'}`, this.lyricsEl);
    const sung = lines.map((l) => new SungLine(box, toLyric(l), '', s.held?.[l.id] ? { held: s.held[l.id] } : {}));
    const lead = this.timing.lead;
    this.lyricUpd = (t: number, pulse: number) => {
      sung.forEach((x) => x.update(t));
      const singing = lines.some((l) => t >= l.words[0].t - lead - 0.1 && t <= l.words[l.words.length - 1].e - lead + 0.2) ? 1 : 0.4;
      box.style.setProperty('--bump', (1 + 0.06 * pulse * singing).toFixed(4));
    };
  }

  sceneAt(t: number) {
    return this.timing?.sceneAt(t) ?? null;
  }

  renderAt(t: number) {
    if (!this.timing) return;
    const ts = this.timing.sceneAt(t);
    if (!ts) return;
    if (ts !== this.current) {
      this.current = ts;
      this.buildLyrics(ts);
      this.camLabel.textContent = ts.scene.cam ?? '';
    }
    const tm = this.timing;
    const beat = tm.beatAt(t);
    const pulse = Math.exp(-(beat - Math.floor(beat)) * 5);
    const local = t - ts.t0;
    const u = prog(t, ts.t0, ts.t1);
    const hit = tm.hit(t);
    const look: Look = { ...this.lookOf(ts.scene), ...tm.eventLook(t) };
    const perf = tm.perf(t, (tt) => {
      let env = 0;
      let release = 0;
      for (const h of this.heldLines) {
        const fx = heldFx(tt, h.line, h.track);
        env = Math.max(env, fx.env);
        release = Math.max(release, fx.release);
      }
      return { env, release };
    });
    const wallCtx = { t, local, beat, pulse, hit: hit.flash };
    const spec = ts.scene.wall;
    this.concert.update({
      t, local, u, beat, pulse, hit: hit.flash, pyro: hit.pyro,
      shot: ts.scene.shot ?? 'wide', seed: ts.scene.seed ?? ts.index, look, perf,
      drawWall: (g, w, h) => drawWall(spec, g, w, h, wallCtx, this.api, this.bust),
    });
    this.lyricUpd?.(t, pulse);

    // broadcast overlay
    const dur = tm.duration;
    const firstT = tm.sung[0]?.words[0].t ?? dur;
    this.liveDot.style.opacity = Math.floor(t * 1.2) % 2 === 0 ? '1' : '0.25';
    const hudOn = clamp((t - 1) / 1) * (1 - prog(t, dur - 2.3, dur - 1.9));
    this.live.style.setProperty('--hud', hudOn.toFixed(3));
    const cardOn = firstT > 7 ? prog(t, firstT * 0.5, firstT * 0.5 + 0.6) * (1 - prog(t, firstT - 1.2, firstT - 0.6)) : 0;
    this.card.style.opacity = cardOn.toFixed(3);
    this.card.style.transform = `translateY(${((1 - easeOut(prog(t, firstT * 0.5, firstT * 0.5 + 0.6))) * 30).toFixed(1)}px)`;
    this.showTitle.style.opacity = (hudOn * (1 - cardOn)).toFixed(3);
    const ek = prog(t, dur - 1.6, dur - 0.8);
    this.endCard.style.opacity = ek.toFixed(3);
    this.flash.style.opacity = (hit.flash * 0.18).toFixed(3);
    this.lyricsEl.style.setProperty('--rgb', `${(hit.flash * 0.06 + pulse * 0.01).toFixed(3)}em`);
  }
}
