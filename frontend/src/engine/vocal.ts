// Loudness + pitch of the long held notes (30 values per second, measured from the vocal track),
// provided by the project (project.held). Used to drive the held-word effects.

import type { HeldTrack } from '../types';

export type TrackName = string;
let TRACKS: Record<string, HeldTrack> = {};
let folded: Record<string, number[]> = {};

/** pitch detection jumps by octaves: fold to ±6 semitones and smooth */
export function setTracks(list: HeldTrack[] | undefined) {
  TRACKS = {};
  folded = {};
  for (const tr of list ?? []) {
    TRACKS[tr.name] = tr;
    const f = (tr.pitch ?? []).map((p) => ((((p + 6) % 12) + 12) % 12) - 6);
    folded[tr.name] = f.map((_, i) => {
      const w = f.slice(Math.max(0, i - 3), i + 4).sort((a, b) => a - b);
      return w[Math.floor(w.length / 2)] ?? 0;
    });
  }
}

function sample(arr: number[], tr: HeldTrack, t: number) {
  if (!arr.length) return 0;
  const x = (t - tr.t0) * tr.fps;
  if (x <= 0) return arr[0];
  if (x >= arr.length - 1) return arr[arr.length - 1];
  const i = Math.floor(x);
  return arr[i] + (arr[i + 1] - arr[i]) * (x - i);
}

export function vocalEnv(name: TrackName, t: number) {
  const tr = TRACKS[name];
  if (!tr || t < tr.t0 || t > tr.t0 + tr.env.length / tr.fps) return 0;
  return sample(tr.env, tr, t);
}

export function vocalPitch(name: TrackName, t: number) {
  const tr = TRACKS[name];
  return tr ? sample(folded[name], tr, t) : 0;
}

export const hasTrack = (name: string) => !!TRACKS[name];
