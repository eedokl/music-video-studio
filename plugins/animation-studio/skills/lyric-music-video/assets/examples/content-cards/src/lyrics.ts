// Lyrics (placeholder text), sections and beat grid. Each line keeps the word count of the timing data.
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
  ["intro", "Station... waking... up..."],
  ["intro", "Lights... flickering..."],
  ["intro", "Starting... the shift."],
  ["verse1", "Radio Operator – turn the static into a voice,"],
  ["verse1", "Power Engineer – trim the load, keep the lights in line."],
  ["verse1", "Water Recycler – keep the water flowing clean,"],
  ["verse1", "Rover Robotics Engineer – put a brain in the rover."],
  ["verse1", "Flight Software, Autopilot Team – code that makes it steer,"],
  ["verse1", "Station Architect – draw the blueprint, every bolt, every beam."],
  ["verse1", "Feel it humming, deck to deck,"],
  ["verse1", "Every crew is lighting up the dark –"],
  ["chorus", "One station! All aboard!"],
  ["chorus", "From the engine to the stars!"],
  ["chorus", "Every bolt and wire, we own it,"],
  ["chorus", "Every hatch, we make it ours!"],
  ["chorus", "One station! All aboard!"],
  ["chorus", "Hey! Hey!"],
  ["chorus", "Built together, built to fly –"],
  ["chorus", "We are the orbit, burning bright!"],
  ["verse2", "Habitat Designer – build the decks that hold the weight,"],
  ["verse2", "Research Lead – see tomorrow, test the theory, calibrate."],
  ["verse2", "Greenhouse Lead – from seedling to harvest line,"],
  ["verse2", "Safety Officer – own the drills, the checklists, the design."],
  ["verse2", "Night Inspector – walk it every night, catch every leak,"],
  ["verse2", "Station Machinist – forge the parts that power us all."],
  ["verse2", "Life-Support Manager – oxygen, water, the backbone strong."],
  ["verse2", "Feel it humming, deck to deck,"],
  ["verse2", "Every crew is lighting up the dark –"],
  ["chorus", "One station! All aboard!"],
  ["chorus", "From the engine to the stars!"],
  ["chorus", "Every bolt and wire, we own it,"],
  ["chorus", "Every hatch, we make it ours!"],
  ["chorus", "One station! All aboard!"],
  ["chorus", "Hey! Hey!"],
  ["chorus", "Built together, built to fly –"],
  ["chorus", "We are the orbit, burning bright!"],
  ["bridge", "Mission Commander – set the course, choose the way,"],
  ["bridge", "Crew Coach – clear the path, make the team play."],
  ["bridge", "No badges. No stripes. Just crew."],
  ["bridge", "And roles can change as we fly."],
  ["bridge", "One! Three! Seven! Ten! All!"],
  ["bridge", "The finest crew you've ever seen!"],
  ["final", "One station! All aboard!"],
  ["final", "From the engine to the stars!"],
  ["final", "Every bolt and wire, we own it,"],
  ["final", "Every hatch, we make it ours!"],
  ["final", "One station! All aboard!"],
  ["final", "Hey! Hey!"],
  ["final", "Built together, built to fly –"],
  ["final", "We are the orbit, burning bright!"],
  ["outro", "Orbit... stable."],
  ["outro", "Shift... complete."],
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
