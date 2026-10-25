// Replaces the original lyrics.ts: same exports, but lines, song length and beat grid come from
// the studio project (see studio_data.ts). The original file is kept as lyrics_orig.ts for types,
// section colours and anything else it exports.
export * from './lyrics_orig';
import type { LyricLine, SectionId } from './lyrics_orig';
import { studio } from './studio_data';

export const LINES = studio.lines as unknown as LyricLine[];
export const SONG_END: number = studio.project.audio.duration;
export const BPM: number = studio.project.grid?.bpm ?? 120;
export const BEAT_OFFSET: number = studio.project.grid?.offset ?? 0;
export const beatAt = (t: number) => studio.timing.beatAt(t);

const firstOf = (s: string) => LINES.find((l) => l.section === s && l.t < 1e5)?.t ?? SONG_END;
const lastOf = (s: string) => [...LINES].reverse().find((l) => l.section === s && l.t < 1e5)?.e ?? SONG_END;
export const SECTIONS: { id: SectionId; t: number }[] = (
  [
    { id: 'intro', t: 0 },
    { id: 'verse1', t: firstOf('verse1') - 1.5 },
    { id: 'chorus', t: firstOf('chorus') - 1 },
    { id: 'verse2', t: firstOf('verse2') - 1.5 },
    { id: 'bridge', t: firstOf('bridge') - 1 },
    { id: 'final', t: firstOf('final') - 1 },
    { id: 'outro', t: lastOf('final') + 1.5 },
  ] as { id: SectionId; t: number }[]
).filter((s) => s.t < SONG_END);

export function sectionAt(t: number): { id: SectionId; p: number } {
  let i = 0;
  while (i + 1 < SECTIONS.length && SECTIONS[i + 1].t <= t) i++;
  const start = SECTIONS[i].t;
  const end = i + 1 < SECTIONS.length ? SECTIONS[i + 1].t : SONG_END;
  return { id: SECTIONS[i].id, p: Math.min(1, Math.max(0, (t - start) / (end - start))) };
}
