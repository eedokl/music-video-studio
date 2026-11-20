// Lyrics, sections and beat grid. RAW / SONG_END / BPM / BEAT_OFFSET / SEED are filled in by the plugin's
// lyric-music-video install_data.py (from the song project's analysis/).
// Line timings live in timing.json (generated from the audio with Whisper word timestamps).
// To adjust a line by hand, edit its "t" (start) / "e" (end) in timing.json.

import timing from './timing.json';

export type SectionId = 'intro' | 'verse1' | 'chorus' | 'verse2' | 'bridge' | 'final' | 'outro';

export const SECTION_COLORS: Record<SectionId, string> = {
  intro: '#3fa9ff',
  verse1: '#00b4e6',
  chorus: '#ff3fb4',
  verse2: '#8b4dff',
  bridge: '#ff4a2f',
  final: '#ffb300',
  outro: '#3fa9ff',
};

export interface LyricLine {
  t: number;
  e: number;
  text: string;
  section: SectionId;
  words?: number[]; // start time of each word
  ends?: number[]; // end time of each word (from the audio)
}


const RAW: [SectionId, string][] = [
  ["verse1", "Replace me with the real lyrics"],
];

interface Timing {
  t: number;
  e: number;
  words: number[];
  ends: number[];
}
const T = timing as Timing[];

export const LINES: LyricLine[] = RAW.map(([section, text], i) => ({
  section,
  text,
  t: T[i].t,
  e: T[i].e,
  words: T[i].words,
  ends: T[i].ends,
}));

// Section boundaries: each section starts a moment before its first line.
export const SONG_END = 10;
const firstOf = (s: SectionId) => LINES.find((l) => l.section === s)?.t;
const lastLine = LINES[LINES.length - 1];
// sections that exist in this song (a song without a bridge simply has none)
export const SECTIONS: { id: SectionId; t: number }[] = [
  { id: 'intro' as SectionId, t: 0 },
  ...(['verse1', 'chorus', 'verse2', 'bridge', 'final'] as SectionId[])
    .map((id) => ({ id, t: (firstOf(id) ?? -1) - 1 }))
    .filter((s) => s.t > 0),
  { id: 'outro' as SectionId, t: lastLine.e + 1.5 },
].sort((a, b) => a.t - b.t);

export function sectionAt(t: number): { id: SectionId; p: number } {
  let i = 0;
  while (i + 1 < SECTIONS.length && SECTIONS[i + 1].t <= t) i++;
  const start = SECTIONS[i].t;
  const end = i + 1 < SECTIONS.length ? SECTIONS[i + 1].t : SONG_END;
  return { id: SECTIONS[i].id, p: Math.min(1, Math.max(0, (t - start) / (end - start))) };
}

// Beat grid detected from the audio
export const BPM = 120;
export const BEAT_OFFSET = 0;
export const beatAt = (t: number) => ((t - BEAT_OFFSET) * BPM) / 60;
/** song time of beat number b */
export const beatTime = (b: number) => BEAT_OFFSET + (b * 60) / BPM;
/** one beat in seconds (functions, not constants: this file is read before scenes.ts in import cycles) */
export const beatLen = () => 60 / BPM;
/** Snap a time to the beat grid - graphic events land on the beat, lyrics on the words.
 *  div 1 = beats, 2 = half beats, 4 = quarter beats; dir 0 = the nearest grid point, 1 = the next one. */
export const snapBeat = (t: number, div = 1, dir = 0) => {
  const b = beatAt(t) * div;
  return beatTime((dir > 0 ? Math.ceil(b - 0.001) : Math.round(b)) / div);
};

// Creative seed of the project (project.json "seed"): use it for variation, e.g. hash(i + SEED) instead of hash(i),
// so a new seed gives a new take while the same seed renders the same video.
export const SEED = 0;

// Held notes found by analyze_song.py: 'vowels' repeats the held vowel, 'stretch' widens it (project.json held_style)
export const HELD_STYLE = 'vowels' as 'vowels' | 'stretch';
