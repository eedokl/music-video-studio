// Live-concert broadcast technique: the song as a stadium concert seen through TV cameras.
// Each scene = one camera shot + one light look + one LED-wall visual + how the lyrics are shown.
// Scene cuts follow the sung lines: a scene starts just before its first word, but never before
// the previous line is complete and was readable for a moment.

import type { Look, Shot } from './concert';
import { LEAD, type LineOpts } from './lyric';
import { LINES, SONG_END } from './lyrics';
import * as V from './wall';
import type { WallFn } from './wall';

export interface SceneDef {
  id: string;
  lines: number[];
  start?: number;
  shot: Shot;
  seed?: number;
  look: Look;
  wall: WallFn;
  /** lyric block style: 'low' (lower third), 'big' (centre, chants), 'side' */
  lyr?: 'low' | 'big' | 'side' | 'none';
  lineOpts?: Record<number, LineOpts>;
  cam?: string; // camera label in the broadcast HUD
}

const L = LINES;
const W = (li: number, wi = 0) => (L[li].words?.[wi] ?? L[li].t) - LEAD;
const E = (li: number) => L[li].e - LEAD;
/** When the last letter of a line has landed (same maths as SungLine). */
function textDone(li: number) {
  const l = L[li];
  const s = (l.words?.[l.words.length - 1] ?? l.t) - LEAD;
  const e = Math.min(Math.max((l.ends?.[l.ends.length - 1] ?? l.e + 0.25) - LEAD, s + 0.12), s + 1.4);
  return s + (e - s) * 0.65 + 0.21;
}
const READ_HOLD = 0.3;

// ---------- light looks ----------
const CONFETTI = W(46, 3); // "light the sky"
const FIREWORKS = [185.6, 186.9, 188.2, 189.6, 191.0, 193.0, 195.2, 203.1, 204.4, 205.7];
const intro: Look = { beams: ['#3d6bff', '#8fb0ff'], wash: '#1a2a8a', energy: 0.12, pattern: 'still', phones: 0.7, blackout: 0.65 };
const introUp: Look = { beams: ['#3d6bff', '#ffffff'], wash: '#2a3cff', energy: 0.35, pattern: 'up', phones: 0.5 };
const verse1: Look = { beams: ['#ffcc00', '#ffffff', '#ff8a2a'], wash: '#ff7a1a', energy: 0.5, pattern: 'sweep' };
const pre: Look = { beams: ['#3d6bff', '#8fb0ff'], wash: '#1a3cff', energy: 0.3, pattern: 'still', follow: 1 };
const chorus = (co2?: number): Look => ({ beams: ['#e3001b', '#ffcc00', '#ffffff'], wash: '#e3001b', energy: 0.92, pattern: 'fan', pyro: true, strobe: true, co2: co2 === undefined ? [] : [co2] });
const heyLook: Look = { beams: ['#e3001b', '#ffffff'], wash: '#ff2030', energy: 1, pattern: 'chase', pyro: true, strobe: true };
const verse2: Look = { beams: ['#8b4dff', '#3d8bff', '#ffffff'], wash: '#5a2cff', energy: 0.58, pattern: 'crowd' };
const spoken: Look = { beams: ['#ffffff'], wash: '#30303a', energy: 0.18, pattern: 'still', follow: 1 };
const bridge: Look = { beams: ['#3d6bff', '#a8c0ff'], wash: '#0a1c5a', energy: 0.22, pattern: 'up', phones: 0.85, follow: 0.8 };
const final = (extra: Partial<Look> = {}): Look => ({ beams: ['#ffcc00', '#ffffff', '#3d6bff'], wash: '#ffb300', energy: 1, pattern: 'fan', pyro: true, strobe: true, confetti: CONFETTI, ...extra });
const outro = (extra: Partial<Look> = {}): Look => ({ beams: ['#ffcc00', '#3d6bff', '#ffffff'], wash: '#ffb300', energy: 0.95, pattern: 'sweep', pyro: true, confetti: CONFETTI, fireworks: FIREWORKS, ...extra });

const HELD_GLOW1: Record<number, LineOpts> = { 14: { held: 'glow1' } };
const HELD_GLOW2: Record<number, LineOpts> = { 35: { held: 'glow2' } };

export const SCENES: SceneDef[] = [
  // ======================= INTRO: the arena waits, the band walks on =======================
  { id: 'arena-dark', lines: [], start: 0, shot: 'crowd', seed: 2, look: intro, wall: V.intro, lyr: 'none', cam: 'CAM 7 · FOH' },
  { id: 'lights-up', lines: [], start: 4.6, shot: 'wide', seed: 1, look: introUp, wall: V.intro, lyr: 'none', cam: 'CAM 1 · WIDE' },

  // ======================= VERSE 1 =======================
  { id: 'monday', lines: [0, 1], shot: 'wall', seed: 3, look: verse1, wall: V.clock, cam: 'CAM 2 · LED' },
  { id: 'slides', lines: [2, 3], shot: 'pit', seed: 4, look: verse1, wall: V.deck, cam: 'CAM 5 · PIT' },
  { id: 'go-vs-wait', lines: [4, 5], shot: 'wide', seed: 5, look: { ...verse1, pattern: 'crowd' }, wall: V.split, cam: 'CAM 1 · WIDE' },
  { id: 'committees', lines: [6, 7], shot: 'wall', seed: 6, look: verse1, wall: V.committees, cam: 'CAM 2 · LED' },
  { id: 'officer', lines: [8, 9], shot: 'orbit', seed: 0.4, look: pre, wall: V.windowSky, cam: 'CAM 4 · STEADY' },
  { id: 'yesterday', lines: [10, 11], shot: 'singer', seed: 8, look: pre, wall: V.windowSky, cam: 'CAM 3 · CLOSE' },

  // ======================= CHORUS 1 =======================
  { id: 'chorus1-storm', lines: [12, 13], shot: 'crane', seed: 9, look: chorus(W(12)), wall: V.storm, cam: 'CAM 6 · CRANE' },
  { id: 'chorus1-count', lines: [14, 15], shot: 'pit', seed: 10, look: { ...chorus(), sparks: [W(14, 7), E(14) + 0.4] }, wall: V.bigCount, lineOpts: HELD_GLOW1, cam: 'CAM 5 · PIT' },
  { id: 'chorus1-hey', lines: [16], shot: 'crowd', seed: 11, look: heyLook, wall: V.hey, lyr: 'big', cam: 'CAM 7 · CROWD' },
  { id: 'chorus1-wake', lines: [17], shot: 'drums', seed: 12, look: heyLook, wall: V.hey, lyr: 'big', cam: 'CAM 8 · DRUMS' },
  { id: 'riff', lines: [], start: textDone(17) + READ_HOLD, shot: 'guitar', seed: 13, look: { ...chorus(), energy: 0.8, pattern: 'sweep' }, wall: V.eq, lyr: 'none', cam: 'CAM 9 · GUITAR' },

  // ======================= VERSE 2 =======================
  { id: 'harbour', lines: [18, 19], shot: 'wall', seed: 14, look: verse2, wall: V.harbourBridge, cam: 'CAM 2 · LED' },
  { id: 'agents', lines: [20, 21], shot: 'pit', seed: 15, look: verse2, wall: V.agents, cam: 'CAM 5 · PIT' },
  { id: 'bubble', lines: [22, 23], shot: 'wide', seed: 16, look: { ...verse2, pattern: 'fan' }, wall: V.bubble, cam: 'CAM 1 · WIDE' },
  { id: 'geopolitics', lines: [24, 25], shot: 'wall', seed: 17, look: { ...verse2, energy: 0.7 }, wall: V.triad, cam: 'CAM 2 · LED' },

  // ======================= SPOKEN: Newsflash =======================
  { id: 'newsflash', lines: [26, 27], shot: 'singer', seed: 18, look: spoken, wall: V.news, cam: 'CAM 3 · CLOSE' },
  { id: 'specialty', lines: [28], shot: 'wing', seed: 19, look: spoken, wall: V.menu, cam: 'CAM 10 · WING' },
  { id: 'menu', lines: [29, 30], shot: 'wall', seed: 20, look: { ...spoken, energy: 0.3 }, wall: V.menu, cam: 'CAM 2 · LED' },
  { id: 'founders', lines: [31, 32], shot: 'wide', seed: 21, look: { ...spoken, beams: ['#ffcc00', '#ffffff'], energy: 0.35, pattern: 'sweep' }, wall: V.departures, cam: 'CAM 1 · WIDE' },

  // ======================= CHORUS 2 =======================
  { id: 'chorus2-storm', lines: [33, 34], shot: 'crane', seed: 22, look: chorus(W(33)), wall: V.storm, cam: 'CAM 6 · CRANE' },
  { id: 'chorus2-count', lines: [35, 36], shot: 'pit', seed: 23, look: { ...chorus(), sparks: [W(35, 7), E(35) + 0.4] }, wall: V.bigCount, lineOpts: HELD_GLOW2, cam: 'CAM 5 · PIT' },
  { id: 'chorus2-hey', lines: [37], shot: 'crowd', seed: 24, look: heyLook, wall: V.hey, lyr: 'big', cam: 'CAM 7 · CROWD' },
  // the long held "now!": orbit around the singer, spark curtain
  { id: 'chorus2-now', lines: [37], start: W(37, 7) - 0.05, shot: 'orbit', seed: 2.2, look: { ...chorus(), sparks: [W(37, 7), E(37) + 0.5], pattern: 'up' }, wall: V.bigCount, lyr: 'big', lineOpts: { 37: { held: 'now' } }, cam: 'CAM 4 · STEADY' },

  // ======================= BRIDGE =======================
  { id: 'no-drama', lines: [38, 39], shot: 'wide', seed: 25, look: bridge, wall: V.logo, cam: 'CAM 1 · WIDE' },
  { id: 'revolution', lines: [40, 41], shot: 'wall', seed: 26, look: bridge, wall: V.revolutions, cam: 'CAM 2 · LED' },
  { id: 'rules', lines: [42], shot: 'singer', seed: 27, look: { ...bridge, follow: 1 }, wall: V.rulebook, cam: 'CAM 3 · CLOSE' },

  // ======================= FINAL CHORUS =======================
  { id: 'into-the-light', lines: [43, 44], shot: 'crane', seed: 28, look: final({ co2: [W(43)], confetti: undefined }), wall: V.sunrise, cam: 'CAM 6 · CRANE' },
  { id: 'light-the-sky', lines: [45, 46], shot: 'crowd', seed: 29, look: final(), wall: V.dance, cam: 'CAM 7 · CROWD' },
  { id: 'final-hey', lines: [47], shot: 'drums', seed: 30, look: { ...heyLook, confetti: CONFETTI }, wall: V.hey, lyr: 'big', cam: 'CAM 8 · DRUMS' },
  { id: 'no-more', lines: [48], shot: 'pit', seed: 31, look: final(), wall: V.maybeLater, cam: 'CAM 5 · PIT' },
  { id: 'countdown', lines: [49], shot: 'wall', seed: 32, look: final({ pattern: 'chase' }), wall: V.countdown, cam: 'CAM 2 · LED' },
  { id: 'wait', lines: [50], shot: 'singer', seed: 33, look: final({ follow: 1, pattern: 'up', sparks: [W(50, 3), E(50) + 0.6] }), wall: V.countdown, lineOpts: { 50: { held: 'wait' } }, cam: 'CAM 3 · CLOSE' },

  // ======================= OUTRO: the finale =======================
  { id: 'fireworks', lines: [], start: textDone(50) + READ_HOLD, shot: 'wide', seed: 34, look: outro({ co2: [textDone(50) + READ_HOLD] }), wall: V.finale, lyr: 'none', cam: 'CAM 1 · WIDE' },
  { id: 'band-jump', lines: [], start: 197.95, shot: 'drums', seed: 35, look: outro({ strobe: true, pattern: 'chase' }), wall: V.finale, lyr: 'none', cam: 'CAM 8 · DRUMS' },
  { id: 'crane-finale', lines: [], start: 203.0, shot: 'crane', seed: 36, look: outro({ co2: [203.07], pattern: 'fan' }), wall: V.finale, lyr: 'none', cam: 'CAM 6 · CRANE' },
  { id: 'light-ring', lines: [], start: 207.15, shot: 'top', seed: 37, look: outro({ phones: 0.5, ring: 1, energy: 0.6, pattern: 'up' }), wall: V.finale, lyr: 'none', cam: 'CAM 11 · SKY' },
  { id: 'thanks', lines: [], start: 212.2, shot: 'wide', seed: 38, look: outro({ phones: 0.6, ring: 0.5, energy: 0.5, pattern: 'up', fireworks: [] }), wall: V.thanks, lyr: 'none', cam: 'CAM 1 · WIDE' },
  { id: 'blackout', lines: [], start: 217.55, shot: 'wide', seed: 39, look: outro({ phones: 0.4, ring: 1, energy: 0, blackout: 1, fireworks: [], pyro: false }), wall: V.thanks, lyr: 'none', cam: 'CAM 1 · WIDE' },
];

// ---------- timeline ----------
export interface Timed extends SceneDef {
  t0: number;
  t1: number;
}
export const TIMELINE: Timed[] = SCENES.map((s) => {
  if (s.start !== undefined) return { ...s, t0: s.start, t1: 0 };
  const f = s.lines[0];
  const prevDone = f > 0 ? textDone(f - 1) + READ_HOLD : 0;
  const t0 = Math.min(L[f].t + 0.3, Math.max(L[f].t - 0.28, prevDone));
  return { ...s, t0, t1: 0 };
}).sort((a, b) => a.t0 - b.t0);
TIMELINE.forEach((s, i) => (s.t1 = i + 1 < TIMELINE.length ? TIMELINE[i + 1].t0 : SONG_END));
export const sceneAt = (t: number) => TIMELINE.find((s) => t >= s.t0 && t < s.t1) ?? TIMELINE[TIMELINE.length - 1];

/** lines that contain a "Hey!" chant – used for the singer's fist pump and the crowd */
export const HEY_WORDS: number[] = [];
L.forEach((l, li) =>
  l.text.split(' ').forEach((w, wi) => {
    if (/^hey/i.test(w)) HEY_WORDS.push(W(li, wi));
  }),
);
export const HELD_LINES: [number, 'glow1' | 'glow2' | 'now' | 'wait'][] = [
  [14, 'glow1'],
  [35, 'glow2'],
  [37, 'now'],
  [50, 'wait'],
];
export { E, W };
