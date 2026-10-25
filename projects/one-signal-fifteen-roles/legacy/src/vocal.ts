// Loudness + pitch of the long held notes ("Fifteen" x2, "roles!"), measured from the audio
// (30 values per second, see held.json). Used to drive the held-word effects.

import { studio } from './studio_data';
const held = studio.held;

interface Track {
  t0: number;
  fps: number;
  env: number[];
  pitch: number[];
}
export type TrackName = string;
const TRACKS = held as unknown as Record<TrackName, Track>;

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
  if (t < tr.t0 || t > tr.t0 + tr.env.length / tr.fps) return 0;
  return sample(tr.env, tr, t);
}

/** Smoothed pitch contour in semitones (about −6..+6) of a held note. */
export function vocalPitch(name: TrackName, t: number) {
  return sample(folded[name], TRACKS[name], t);
}
