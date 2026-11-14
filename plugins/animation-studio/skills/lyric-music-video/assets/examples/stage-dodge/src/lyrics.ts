// Lyrics (placeholder text), sections and beat grid.
// Line timings live in timing.json (generated from the audio with Whisper word timestamps).
// To adjust a line by hand, edit its "t" (start) / "e" (end) in timing.json.

import timing from './timing.json';

export type SectionId = 'intro' | 'verse1' | 'chorus' | 'verse2' | 'bridge' | 'final' | 'outro';

export const SECTION_COLORS: Record<SectionId, string> = {
  intro: '#ff2a2a',
  verse1: '#00d5ff',
  chorus: '#ff2a6d',
  verse2: '#a24dff',
  bridge: '#ff6a00',
  final: '#ffd000',
  outro: '#ff2a2a',
};

export interface LyricLine {
  t: number;
  e: number;
  text: string;
  section: SectionId;
  words?: number[]; // start time of each word
}


const RAW: [SectionId, string][] = [
  ['verse1', 'Alarms, traffic jam,'],
  ['verse1', 'Deadline chasing me wherever I am,'],
  ['verse1', 'Inbox, spam, noise,'],
  ['verse1', 'Another meeting starts at three.'],
  ['verse1', 'Parking tickets, unpaid invoices,'],
  ['verse1', 'Printer jams, broken links,'],
  ['verse1', 'Reminders here, alerts there,'],
  ['verse1', 'Somebody moved my office chair.'],
  ['verse1', 'Passwords, updates, backups too,'],
  ['verse1', 'Another survey on its way,'],
  ['verse1', 'Spam folder, missed call,'],
  ['verse1', 'Who planned this mess at all?'],
  ['chorus', 'We never asked for chaos,'],
  ['chorus', 'But we keep the show rolling on.'],
  ['chorus', 'Every day a brand-new storm,'],
  ['chorus', 'Still we keep the music warm.'],
  ['chorus', 'We never asked for chaos,'],
  ['chorus', 'Yet somehow we turn it into gold.'],
  ['chorus', 'Life is fast and noise is loud,'],
  ['chorus', 'So we outdance the crowd.'],
  ['verse2', 'Phone update, battery drained,'],
  ['verse2', 'Weekend plans got washed away,'],
  ['verse2', 'Pop-ups, ads, spam,'],
  ['verse2', 'Someone wants attention.'],
  ['verse2', 'Group chat, endless thread,'],
  ['verse2', 'Another form to be signed,'],
  ['verse2', 'Static noise and lag,'],
  ['verse2', 'Buffering never rests.'],
  ['verse2', 'Queues, delays, rain,'],
  ['verse2', 'Manager says "not again",'],
  ['verse2', 'Every checkbox ticked green,'],
  ['verse2', 'Play the chorus and keep it clean.'],
  ['bridge', 'One more message, one more ping,'],
  ['bridge', 'One more form, one more thing.'],
  ['bridge', 'Everybody wants more,'],
  ['bridge', 'First we need the rhythm right.'],
  ['final', 'Alarms, traffic jam,'],
  ['final', 'Deadlines chasing coast-to-coast,'],
  ['final', 'Inbox, spam, noise, delay,'],
  ['final', 'Dancing through everything.'],
  ['final', 'Tickets, passwords, alerts,'],
  ['final', 'Reminders never go away,'],
  ['final', 'Pop-ups, ads, spam,'],
  ['final', 'Welcome to the noise.'],
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
export const SONG_END = 189.6;
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

// Beat grid (detected from the audio): 128.6 BPM, first beat at 0.404 s
export const BPM = 128.6;
export const BEAT_OFFSET = 0.404;
export const beatAt = (t: number) => ((t - BEAT_OFFSET) * BPM) / 60;

/** Hazard words: she fights these. Everything else she dodges or lets fly past. */
const FIGHT = [
  'alarms', 'traffic', 'jam', 'deadline', 'deadlines', 'inbox', 'spam', 'noise', 'meeting', 'tickets',
  'invoices', 'jams', 'links', 'reminders', 'alerts', 'passwords', 'updates', 'backups', 'survey', 'folder', 'chaos',
  'storm', 'update', 'battery', 'drained', 'popups', 'ads', 'thread', 'form', 'static', 'lag', 'buffering', 'queues',
  'delays', 'rain', 'message', 'ping', 'delay', 'printer', 'mess',
];
export const isFightWord = (w: string) => FIGHT.includes(w.toLowerCase().replace(/[^a-z]/g, ''));
const SMALL = ['the', 'a', 'at', 'we', 'to', 'and', 'of', 'is', 'on', 'it', 'all', 'this', 'but', 'so', "we're", 'there', 'here', 'be', 'like'];
export const isSmallWord = (w: string) => SMALL.includes(w.toLowerCase().replace(/[^a-z']/g, ''));
