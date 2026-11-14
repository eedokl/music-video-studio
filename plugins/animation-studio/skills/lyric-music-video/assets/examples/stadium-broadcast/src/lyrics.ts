// Lyrics (as performed, placeholder text), sections and beat grid.
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
  ["verse1", "Monday morning, city grey,"],
  ["verse1", "another coffee, same old day."],
  ["verse1", "Slides and spreadsheets,"],
  ["verse1", "while the clock runs fast."],
  ["verse1", "The radio says: \"Let's go!\""],
  ["verse1", "The council says: \"We'll see tomorrow.\""],
  ["verse1", "Seven meetings and one memo,"],
  ["verse1", "and the rivals never sleep tonight."],
  ["verse1", "And the officer looks out the window,"],
  ["verse1", "sees the morning sky outside."],
  ["verse1", "She says:"],
  ["verse1", "\"Maybe we're already late...\""],
  ["chorus", "Out into the open air, into the rain,"],
  ["chorus", "we were waiting for tomorrow, now it's here."],
  ["chorus", "Out into the open air, can you glow?"],
  ["chorus", "Ten nine eight seven – are we wide awake?"],
  ["chorus", "Hey! Hey! Lights up, people, lights up now!"],
  ["chorus", "Hey! Lights up, people, lights up now!"],
  ["verse2", "Somebody sits beside the harbour bay,"],
  ["verse2", "robots write her code all day."],
  ["verse2", "Agent by agent, line by line,"],
  ["verse2", "old certainties are breaking."],
  ["verse2", "\"Bubble!\" they shout in rooms,"],
  ["verse2", "but outside grows a brand-new dream."],
  ["verse2", "Power, Money, Speed,"],
  ["verse2", "that's the new game, baby."],
  ["verse2", "Newsflash!"],
  ["verse2", "Ladies and Gentlemen..."],
  ["verse2", "Welcome to our specialty:"],
  ["verse2", "First waiting. Then measuring."],
  ["verse2", "Then reviewing. Then debating."],
  ["verse2", "...and then we wonder why"],
  ["verse2", "all the builders board a plane."],
  ["chorus", "Out into the open air, into the rain,"],
  ["chorus", "we were waiting for tomorrow, now it's here."],
  ["chorus", "Out into the open air, can you glow?"],
  ["chorus", "Ten nine eight seven – are we wide awake?"],
  ["chorus", "Hey! Hey! Lights up, people, lights up now!"],
  ["bridge", "No drama, no disaster."],
  ["bridge", "Just one question:"],
  ["bridge", "When the next big wave arrives,"],
  ["bridge", "and none of us appear—"],
  ["bridge", "who will write the rule book?"],
  ["final", "Out into the open air, into the light,"],
  ["final", "maybe we are falling, maybe we can climb."],
  ["final", "Out into the open air, one more try,"],
  ["final", "Everybody, come on, light the sky."],
  ["final", "Hey! Hey!"],
  ["final", "No more \"someday\". No more \"soon\"."],
  ["final", "The final count is coming,"],
  ["final", "the night won't wait."],
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
export const SONG_END = 219.88;
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
export const BPM = 95.7;
export const BEAT_OFFSET = 0.116;
export const beatAt = (t: number) => ((t - BEAT_OFFSET) * BPM) / 60;
