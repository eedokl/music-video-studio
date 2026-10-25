// Lyrics (as performed), sections and beat grid for "Comfort Zone".
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
  ["verse1", "Brüssel City, Montag früh,"],
  ["verse1", "another meeting, same old view."],
  ["verse1", "PowerPoint und Strategien,"],
  ["verse1", "while the future's on amphetamines."],
  ["verse1", "Silicon Valley sagt: \"Let's go!\""],
  ["verse1", "Europa sagt: \"Wir prüfen das noch.\""],
  ["verse1", "Fünf Ausschüsse und ein Bericht,"],
  ["verse1", "doch die Konkurrenz schläft heute nicht."],
  ["verse1", "Und Caroline schaut aus dem Fenster raus,"],
  ["verse1", "sieht den Himmel über'm Berlaymont-Haus."],
  ["verse1", "She says:"],
  ["verse1", "\"Maybe we're discussing 'yesterday'...\""],
  ["chorus", "Out of the comfort zone, into the storm,"],
  ["chorus", "wir wollten die Zukunft, now it's already born."],
  ["chorus", "Out of the comfort zone, can you survive?"],
  ["chorus", "Europe twenty thirty one –"],
  ["chorus", "are we still alive?"],
  ["chorus", "Hey! Hey! Hey! Wake up, Baby!"],
  ["chorus", "Hey! Hey! Wake up now!"],
  ["chorus", "Hey! Hey! Hey! Wake up, Baby!"],
  ["chorus", "Wake up now!"],
  ["verse2", "Christian sitzt in San Francisco Bay,"],
  ["verse2", "AI schreibt seinen Code all day."],
  ["verse2", "Agent für Agent, token by token,"],
  ["verse2", "alte Gewissheiten werden gebrochen."],
  ["verse2", "\"Bubble!\" rufen sie im Konferenzraum,"],
  ["verse2", "doch draußen wächst ein neuer Traum."],
  ["verse2", "Compute, Capital, Energy, that's the new geopolitics, baby."],
  ["verse2", "Ladies and Gentlemen..."],
  ["verse2", "Willkommen zur europäischen Spezialität:"],
  ["verse2", "Zuerst regulieren. Dann analysieren."],
  ["verse2", "Dann evaluieren. Dann diskutieren."],
  ["verse2", "...und dann wundern wir uns,"],
  ["verse2", "warum alle Gründer am Flughafen stehen."],
  ["chorus", "Out of the comfort zone, into the storm,"],
  ["chorus", "wir wollten die Zukunft, now it's already born."],
  ["chorus", "Out of the comfort zone, can you survive?"],
  ["chorus", "Europe twenty thirty one –"],
  ["chorus", "are we still alive?"],
  ["chorus", "Hey! Hey! Hey! Wake up, Baby!"],
  ["chorus", "Hey! Hey! Wake up now!"],
  ["chorus", "Hey! Hey! Hey! Wake up, Baby!"],
  ["chorus", "Wake up now!"],
  ["bridge", "Kein Drama,"],
  ["bridge", "kein Weltuntergang."],
  ["bridge", "Nur eine Frage:"],
  ["bridge", "Wenn die nächste industrielle Revolution stattfindet,"],
  ["bridge", "und keiner von uns erscheint—"],
  ["bridge", "who gets to write the rules?"],
  ["final", "Out of the comfort zone, into the light,"],
  ["final", "maybe we're losing, maybe we still can fight."],
  ["final", "Out of the comfort zone, one last chance,"],
  ["final", "Europa, komm schon, start the dance."],
  ["final", "Hey! Hey!"],
  ["final", "No more \"maybe\". No more \"later\"."],
  ["final", "Twenty thirty one is coming,"],
  ["final", "and time doesn't wait."],
  ["verse2", "Newsflash!"],
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
