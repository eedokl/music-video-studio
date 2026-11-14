// Lyrics (placeholder text), sections and beat grid.
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
  ['verse1', 'Roles, jump host,'],
  ['verse1', 'Shield blocking what we fear most,'],
  ['verse1', 'Gateway, subnets, guards,'],
  ['verse1', 'Big review in quarter three.'],
  ['verse1', 'Locker secrets, keys, certificates,'],
  ['verse1', 'Private links, network walls,'],
  ['verse1', 'Inbound here, outbound there,'],
  ['verse1', 'Someone edited the firewall rule.'],
  ['verse1', 'Catalog, checklist, impact form,'],
  ['verse1', 'Audits lining up all day,'],
  ['verse1', 'Security ticket, hotline call,'],
  ['verse1', 'Did anyone sign off at all?'],
  ['chorus', 'We never asked for paperwork,'],
  ['chorus', 'Yet the systems keep on running smooth.'],
  ['chorus', 'Every day a shiny rule,'],
  ['chorus', 'And we keep the console cool.'],
  ['chorus', 'We never asked for paperwork,'],
  ['chorus', 'Forms that fill up every working hour.'],
  ['chorus', 'Ship it quick but mind the risk,'],
  ['chorus', 'So we script the rest.'],
  ['verse2', 'Client secret, date expired,'],
  ['verse2', 'Old service account now retired,'],
  ['verse2', 'Proxy, tunnel, client,'],
  ['verse2', 'Everyone needs access.'],
  ['verse2', 'Board review, forty faces,'],
  ['verse2', 'One more spreadsheet to complete,'],
  ['verse2', 'Lookups fail on DNS,'],
  ['verse2', 'Debugging never sleeps.'],
  ['verse2', 'SSH via jumpbox,'],
  ['verse2', 'Security sighs "not again",'],
  ['verse2', 'Release checklist all green,'],
  ['verse2', 'Roll the build out nice and clean.'],
  ['bridge', "Here's a ticket, there's a scan,"],
  ['bridge', "Here's a dashboard, there's a plan."],
  ['bridge', 'Every request: AI,'],
  ['bridge', "Wait, let's get the wiring right."],
  ['final', 'Roles, jump host,'],
  ['final', 'Traffic gates worldwide,'],
  ['final', 'Locker, keys, shield, guards,'],
  ['final', 'Everything locked tight.'],
  ['final', 'Tickets, calls, forms,'],
  ['final', 'Catalog reminders every day,'],
  ['final', 'Proxy, tunnel, client,'],
  ['final', 'Welcome to the console.'],
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
export const SONG_END = 181.6;
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
export const BPM = 113.6;
export const BEAT_OFFSET = 0.518;
export const beatAt = (t: number) => ((t - BEAT_OFFSET) * BPM) / 60;
