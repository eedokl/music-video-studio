// Lyrics (placeholder text, one entry per sung line), sections and beat grid.
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
  ["verse1", "Grey town, Monday morning,"],
  ["verse1", "meeting again, same old room."],
  ["verse1", "Slides, plans, strategies,"],
  ["verse1", "while tomorrow races past us."],
  ["verse1", "The fast town shouts: \"Go!\""],
  ["verse1", "Old town says: \"We'll check later.\""],
  ["verse1", "Five committees and one report,"],
  ["verse1", "while the rivals never sleep tonight."],
  ["verse1", "And the clerk looks out the window,"],
  ["verse1", "sees grey sky above town."],
  ["verse1", "She sighs:"],
  ["verse1", "\"Maybe we're planning yesterday...\""],
  ["chorus", "Leave the safe harbour, sail into the wind,"],
  ["chorus", "we ordered the future, and it arrived early."],
  ["chorus", "Leave the safe harbour, how will you breathe?"],
  ["chorus", "Year twenty thirty, here –"],
  ["chorus", "are we wide awake?"],
  ["chorus", "Hey! Hey! Hey! Rise up, people!"],
  ["chorus", "Hey! Hey! Rise up now!"],
  ["chorus", "Hey! Hey! Hey! Rise up, people!"],
  ["chorus", "Rise up now!"],
  ["verse2", "The coder sits by the bay,"],
  ["verse2", "machines write her code all day."],
  ["verse2", "task after task, line by line,"],
  ["verse2", "every old promise cracks."],
  ["verse2", "\"Bubble!\" shouts the boardroom crowd,"],
  ["verse2", "while outside fresh seeds take root."],
  ["verse2", "Power, Money, Speed, that's the game today, friends."],
  ["verse2", "Dear honoured guests..."],
  ["verse2", "Tonight's house speciality, served:"],
  ["verse2", "First: postpone. Then: review."],
  ["verse2", "Then: rephrase. Then: delay."],
  ["verse2", "...and then we act surprised,"],
  ["verse2", "when the builders board their planes."],
  ["chorus", "Leave the safe harbour, sail into the wind,"],
  ["chorus", "we ordered the future, and it arrived early."],
  ["chorus", "Leave the safe harbour, how will you breathe?"],
  ["chorus", "Year twenty thirty, here –"],
  ["chorus", "are we wide awake?"],
  ["chorus", "Hey! Hey! Hey! Rise up, people!"],
  ["chorus", "Hey! Hey! Rise up now!"],
  ["chorus", "Hey! Hey! Hey! Rise up, people!"],
  ["chorus", "Rise up now!"],
  ["bridge", "Stay calm,"],
  ["bridge", "nothing's burning."],
  ["bridge", "One small question:"],
  ["bridge", "When the next great wave arrives,"],
  ["bridge", "and our seat stays empty—"],
  ["bridge", "who will write the new rules?"],
  ["final", "Leave the safe harbour, sail into the light,"],
  ["final", "maybe we're falling, maybe we learn to fly."],
  ["final", "Leave the safe harbour, catch the morning tide,"],
  ["final", "Come on, old town, let's go."],
  ["final", "Hey! Hey!"],
  ["final", "No more \"someday\". No more \"soon\"."],
  ["final", "Twenty thirty is coming fast,"],
  ["final", "the clock keeps running."],
  ["verse2", "Breaking!"],
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
export const SONG_END = 249.6;
const firstOf = (s: SectionId) => LINES.find((l) => l.section === s)!.t;
const lastOf = (s: SectionId) => [...LINES].reverse().find((l) => l.section === s)!.e;
export const SECTIONS: { id: SectionId; t: number }[] = [
  { id: 'intro', t: 0 },
  { id: 'verse1', t: firstOf('verse1') - 1.5 },
  { id: 'chorus', t: firstOf('chorus') - 1 },
  { id: 'verse2', t: firstOf('verse2') - 1.5 },
  { id: 'bridge', t: firstOf('bridge') - 1 },
  { id: 'final', t: firstOf('final') - 1 },
  { id: 'outro', t: lastOf('final') + 1.5 },
];

export function sectionAt(t: number): { id: SectionId; p: number } {
  let i = 0;
  while (i + 1 < SECTIONS.length && SECTIONS[i + 1].t <= t) i++;
  const start = SECTIONS[i].t;
  const end = i + 1 < SECTIONS.length ? SECTIONS[i + 1].t : SONG_END;
  return { id: SECTIONS[i].id, p: Math.min(1, Math.max(0, (t - start) / (end - start))) };
}

// Beat grid detected from the audio
export const BPM = 97.4;
export const BEAT_OFFSET = 0.028;
export const beatAt = (t: number) => ((t - BEAT_OFFSET) * BPM) / 60;
