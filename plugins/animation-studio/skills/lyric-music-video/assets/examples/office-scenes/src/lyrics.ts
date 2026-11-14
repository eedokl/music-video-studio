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
}


const RAW: [SectionId, string][] = [
  ['verse1', 'Access, jump host,'],
  ['verse1', 'Shield blocking all we fear most,'],
  ['verse1', 'Front Gate, rulesets,'],
  ['verse1', 'Safety check in quarter three.'],
  ['verse1', 'Secret Locker, keys, certificates,'],
  ['verse1', 'Private doorways, network fences,'],
  ['verse1', 'Inbound here, outbound there,'],
  ['verse1', 'Someone quietly edited the rule.'],
  ['verse1', 'Inventory, self review, risk-form,'],
  ['verse1', 'Auditors knocking on the door,'],
  ['verse1', 'Alert ticket, hotline call,'],
  ['verse1', 'Whose idea was this thing anyway?'],
  ['chorus', 'We never asked for paperwork,'],
  ['chorus', 'Yet we keep every single server running.'],
  ['chorus', 'Each Monday brings another rule,'],
  ['chorus', 'Still the dashboards glow so cool.'],
  ['chorus', 'We never asked for paperwork,'],
  ['chorus', 'Though often it becomes our whole day.'],
  ['chorus', 'Clouds move fast and risks are real,'],
  ['chorus', 'So we automate the chores.'],
  ['verse2', 'Client login, token expired,'],
  ['verse2', 'Robot account just got retired,'],
  ['verse2', 'Proxy, tunnel, editor,'],
  ['verse2', 'Everyone needs connection.'],
  ['verse2', 'Design review, architecture board,'],
  ['verse2', 'One more spreadsheet gets stored,'],
  ['verse2', 'Name lookups and DNS,'],
  ['verse2', 'Debugging never sleeps.'],
  ['verse2', 'Shell through jumpbox,'],
  ['verse2', 'Security sighs "not again",'],
  ['verse2', 'Every self check green,'],
  ['verse2', 'Ship the release and keep it tidy.'],
  ['bridge', 'Fresh new ticket, fresh new scan,'],
  ['bridge', 'Fresh new dashboard, fresh new plan.'],
  ['bridge', 'Everyone demands AI,'],
  ['bridge', 'But first the network must work.'],
  ['final', 'Access, jump host,'],
  ['final', 'Front Gate coast-to-coast,'],
  ['final', 'Secret Locker, Shield, rulesets,'],
  ['final', 'Running everything securely.'],
  ['final', 'Alert, hotline, risk-form,'],
  ['final', 'Inventory never goes away,'],
  ['final', 'Proxy, tunnel, editor,'],
  ['final', 'Welcome to platform life.'],
];

interface Timing {
  t: number;
  e: number;
  words: number[];
}
const T = timing as Timing[];

export const LINES: LyricLine[] = RAW.map(([section, text], i) => ({
  section,
  text,
  t: T[i].t,
  e: T[i].e,
  words: T[i].words,
}));

// Section boundaries: each section starts a moment before its first line.
export const SONG_END = 193.9;
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
export const BPM = 137.2;
export const BEAT_OFFSET = 0.422;
export const beatAt = (t: number) => ((t - BEAT_OFFSET) * BPM) / 60;
