// Lyrics, sections and beat grid for the Azure edition (new recording, same lyrics).
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
  ['verse1', 'RBAC, Bastion host,'],
  ['verse1', 'WAF blocking what we hate most,'],
  ['verse1', 'App Gateway, NSG,'],
  ['verse1', 'Security review at quarter three.'],
  ['verse1', 'Key Vault secrets, certificates,'],
  ['verse1', 'Private Endpoints, network limits,'],
  ['verse1', 'Ingress here, egress there,'],
  ['verse1', 'Somebody changed the firewall pair.'],
  ['verse1', 'LeanIX, Self Check, BTIA,'],
  ['verse1', 'Another audit on the way,'],
  ['verse1', 'CERT ticket, CSC call,'],
  ['verse1', 'Who approved this app at all?'],
  ['chorus', "We didn't build the paperwork,"],
  ['chorus', "But we're keeping all the systems working."],
  ['chorus', 'Every week a brand-new rule,'],
  ['chorus', 'Still we keep the platform cool.'],
  ['chorus', "We didn't build the paperwork,"],
  ['chorus', 'Though sometimes it feels like all-day work.'],
  ['chorus', 'Cloud is fast and risk is real,'],
  ['chorus', 'So we automate the deal.'],
  ['verse2', 'App Registration, secret expired,'],
  ['verse2', 'Service principal just got retired,'],
  ['verse2', 'Proxy, SASE, IDE,'],
  ['verse2', 'Someone needs connectivity.'],
  ['verse2', 'IBC review, architecture board,'],
  ['verse2', 'Another spreadsheet to be stored,'],
  ['verse2', 'Private Link and DNS,'],
  ['verse2', 'Troubleshooting never rests.'],
  ['verse2', 'SSH through BCN,'],
  ['verse2', 'Security says "not again",'],
  ['verse2', 'Operator Self Check green,'],
  ['verse2', 'Deploy the release and keep it clean.'],
  ['bridge', 'One more ticket, one more scan,'],
  ['bridge', 'One more dashboard, one more plan.'],
  ['bridge', 'Everybody wants AI,'],
  ['bridge', 'First we need the network right.'],
  ['final', 'RBAC, Bastion host,'],
  ['final', 'Application Gateway coast-to-coast,'],
  ['final', 'Key Vault, WAF, NSG,'],
  ['final', 'Running cloud securely.'],
  ['final', 'CERT, CSC, BTIA,'],
  ['final', 'LeanIX never goes away,'],
  ['final', 'Proxy, SASE, IDE,'],
  ['final', 'Welcome to cloud engineering.'],
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
