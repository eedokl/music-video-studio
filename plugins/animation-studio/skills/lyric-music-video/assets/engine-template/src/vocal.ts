// Loudness + pitch of long held notes, measured from the audio by song-analysis held_notes.py
// (30 values per second, see held.json). Used to drive the held-word effects.

import held from './held.json';

interface Track {
  t0: number;
  fps: number;
  env: number[];
  pitch: number[];
}
export type TrackName = 'none';
const TRACKS = held as unknown as Record<TrackName, Track>;

/** Held notes picked automatically by analyze_song.py (held.json entries with "auto": true): which word of which
 *  line, its measured span and the letter to stretch. SungLine stretches them unless a scene says otherwise. */
export interface AutoHeld {
  name: TrackName;
  line: number;
  word: number;
  word_t: number;
  word_end: number;
  vowel: number;
}
export const AUTO_HELD: AutoHeld[] = Object.entries(held as Record<string, Partial<AutoHeld> & { auto?: boolean }>)
  .filter(([, h]) => h.auto)
  .map(([name, h]) => ({ ...(h as AutoHeld), name: name as TrackName }));

// pitch detection jumps by octaves on a full band mix: fold to ±6 semitones and smooth
const folded: Record<string, number[]> = {};
for (const [k, tr] of Object.entries(TRACKS)) {
  const f = tr.pitch.map((p) => ((((p + 6) % 12) + 12) % 12) - 6);
  folded[k] = f.map((_, i) => {
    const w = f.slice(Math.max(0, i - 3), i + 4).sort((a, b) => a - b);
    return w[Math.floor(w.length / 2)];
  });
}

function sample(arr: number[], tr: Track, t: number) {
  const x = (t - tr.t0) * tr.fps;
  if (x <= 0) return arr[0];
  if (x >= arr.length - 1) return arr[arr.length - 1];
  const i = Math.floor(x);
  return arr[i] + (arr[i + 1] - arr[i]) * (x - i);
}

/** Vocal loudness 0..1 of a held note at song time t (0 outside the analysed range). */
export function vocalEnv(name: TrackName, t: number) {
  const tr = TRACKS[name];
  if (!tr || t < tr.t0 || t > tr.t0 + tr.env.length / tr.fps) return 0;
  return sample(tr.env, tr, t);
}

/** Smoothed pitch contour in semitones (about −6..+6) of a held note. */
export function vocalPitch(name: TrackName, t: number) {
  if (!folded[name]) return 0;
  return sample(folded[name], TRACKS[name], t);
}
