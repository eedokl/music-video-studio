// Lyrics, sections and beat grid for "One Signal, Fifteen Roles".
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
  ["intro", "Raw data... incoming..."],
  ["intro", "Noise... detected..."],
  ["intro", "Initiating... the chain."],
  ["verse1", "DSP Engineer – turn the noise into a sign,"],
  ["verse1", "DSP Embedded – squeeze it down, make it run in time."],
  ["verse1", "Data Ops – keep the pipelines flowing clean,"],
  ["verse1", "Embedded AI Engineer – put a brain in the machine."],
  ["verse1", "CS Engineer, Embedded AI – code that makes it learn,"],
  ["verse1", "AI Architect – draw the blueprint, every bit, every turn."],
  ["verse1", "Feel it rising, wire to wire,"],
  ["verse1", "Every role is lighting up the fire –"],
  ["chorus", "One signal! Fifteen roles!"],
  ["chorus", "From the sensor to the soul!"],
  ["chorus", "Every line of code, we own it,"],
  ["chorus", "Every chip, we make it whole!"],
  ["chorus", "One signal! Fifteen roles!"],
  ["chorus", "Hey! Hey!"],
  ["chorus", "Built together, built to last –"],
  ["chorus", "We are the future, coded fast!"],
  ["verse2", "Software Architect – build the frame that holds the weight,"],
  ["verse2", "CS Expert – see tomorrow, push the concept, innovate."],
  ["verse2", "Algorithm Lead – from prototype to production line,"],
  ["verse2", "Test Architect – own the strategy, the frameworks, the design."],
  ["verse2", "Test Engineer – run it every night, catch every fall,"],
  ["verse2", "Tool Engineer – forge the tools that power us all."],
  ["verse2", "IT Manager – servers, licenses, the backbone strong."],
  ["verse2", "Feel it rising, wire to wire,"],
  ["verse2", "Every role is lighting up the fire –"],
  ["chorus", "One signal! Fifteen roles!"],
  ["chorus", "From the sensor to the soul!"],
  ["chorus", "Every line of code, we own it,"],
  ["chorus", "Every chip, we make it whole!"],
  ["chorus", "One signal! Fifteen roles!"],
  ["chorus", "Hey! Hey!"],
  ["chorus", "Built together, built to last –"],
  ["chorus", "We are the future, coded fast!"],
  ["bridge", "Product Owner – set the vision, choose the way,"],
  ["bridge", "Agile Master – clear the path, make the team play."],
  ["bridge", "No titles. No ranks. Just roles."],
  ["bridge", "And roles can change as we grow."],
  ["bridge", "One! Two! Five! Ten! Fifteen!"],
  ["bridge", "The biggest team you've ever seen!"],
  ["final", "One signal! Fifteen roles!"],
  ["final", "From the sensor to the soul!"],
  ["final", "Every line of code, we own it,"],
  ["final", "Every chip, we make it whole!"],
  ["final", "One signal! Fifteen roles!"],
  ["final", "Hey! Hey!"],
  ["final", "Built together, built to last –"],
  ["final", "We are the future, coded fast!"],
  ["outro", "Signal... processed."],
  ["outro", "Product... delivered."],
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
export const SONG_END = 212.4;
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
export const BPM = 123.0;
export const BEAT_OFFSET = 0.022;
export const beatAt = (t: number) => ((t - BEAT_OFFSET) * BPM) / 60;
