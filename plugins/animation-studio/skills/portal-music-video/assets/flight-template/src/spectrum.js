// What the song sounds like at a moment: eight frequency bands, 0 = bass ... 7 = highs, each 0..1.
// The numbers are written by flight.py data (public/spectrum.json). Without that file every band is 0.5.
const data = await fetch('./public/spectrum.json').then((r) => (r.ok ? r.json() : null)).catch(() => null);

export const BANDS = 8;

/** Fill `out` (length 8) with the levels at song second t. */
export function levelsAt(t, out) {
  if (!data) return out.fill(0.5);
  const f = Math.min(data.frames - 1, Math.max(0, t * data.fps)), i = Math.floor(f), k = f - i, j = Math.min(data.frames - 1, i + 1);
  for (let b = 0; b < BANDS; b++) out[b] = (data.data[i * BANDS + b] * (1 - k) + data.data[j * BANDS + b] * k) / 255;
  return out;
}
