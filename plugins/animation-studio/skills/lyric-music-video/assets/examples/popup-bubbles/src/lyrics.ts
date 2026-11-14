// Lyrics, sections and Pop-Up-Video facts.
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

export interface Fact {
  t: number;
  d: number;
  title: string;
  text: string;
}

const RAW: [SectionId, string][] = [
  ['verse1', 'Roles, rights, jumphost,'],
  ['verse1', 'Shield blocking what we hate most,'],
  ['verse1', 'Gateway, port rules,'],
  ['verse1', 'Safety check in quarter three.'],
  ['verse1', 'Lockbox secrets, signed certificates,'],
  ['verse1', 'Private tunnels, network limits,'],
  ['verse1', 'Traffic in, traffic out,'],
  ['verse1', 'Someone moved the firewall route.'],
  ['verse1', 'Checklist, form, sign-off, stamp,'],
  ['verse1', 'One more inspection coming soon,'],
  ['verse1', 'Helpdesk ticket, phone call,'],
  ['verse1', 'Who launched this server after all?'],
  ['chorus', 'We keep the lights on,'],
  ['chorus', 'Night and day the servers keep humming.'],
  ['chorus', 'Every week a shiny rule,'],
  ['chorus', 'Still we keep the console cool.'],
  ['chorus', 'We keep the lights on,'],
  ['chorus', 'Even when the pager wakes us early.'],
  ['chorus', 'Fast is good and safe is better,'],
  ['chorus', 'So we script it all.'],
  ['verse2', 'Login token, password expired,'],
  ['verse2', 'Robot account just got retired,'],
  ['verse2', 'Proxy, tunnel, editor,'],
  ['verse2', 'Nobody gets online.'],
  ['verse2', 'Design review, planning board,'],
  ['verse2', 'Spreadsheets waiting to be stored,'],
  ['verse2', 'Name lookups and routes,'],
  ['verse2', 'Debugging never sleeps.'],
  ['verse2', 'Shell through jumpbox,'],
  ['verse2', 'Security says "try again",'],
  ['verse2', 'Status page shows green,'],
  ['verse2', 'Ship the update and keep it clean.'],
  ['bridge', 'One more alarm, one more scan,'],
  ['bridge', 'One more chart, one more plan.'],
  ['bridge', 'Everyone wants robots,'],
  ['bridge', 'First we need the cables right.'],
  ['final', 'Roles, rights, jumphost,'],
  ['final', 'Gateway traffic coast-to-coast,'],
  ['final', 'Lockbox, shield, port rules,'],
  ['final', 'Running servers safely.'],
  ['final', 'Tickets, forms, sign-offs,'],
  ['final', 'Paperwork never goes away,'],
  ['final', 'Proxy, tunnel, editor,'],
  ['final', 'Welcome to the console.'],
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

/** Words that fly through the 3D scene when a line starts. */
const KEYWORDS = [
  'Roles', 'Jumphost', 'Shield', 'Gateway', 'Port rules', 'Lockbox', 'Tunnel', 'Traffic', 'Firewall',
  'Checklist', 'Sign-off', 'Inspection', 'Ticket', 'Server', 'Lights', 'Console', 'Pager', 'Script',
  'Token', 'Password', 'Robot', 'Proxy', 'Editor', 'Review', 'Spreadsheet', 'Lookups', 'Routes',
  'Debugging', 'Shell', 'Try again', 'Green', 'Update', 'Alarm', 'Scan', 'Chart', 'Robots', 'Cables',
  'Safely', 'Paperwork',
];
export function keywordsIn(text: string): string[] {
  const lower = text.toLowerCase();
  return KEYWORDS.filter((k) => lower.includes(k.toLowerCase())).slice(0, 3);
}

// Pop-Up-Video info nuggets, anchored to a lyric line.
const FACTS_AT: [number, string, string][] = [
  [0, 'Roles', 'Role-based access: you get exactly the rights your role needs. In theory.'],
  [1, 'Shield', 'The web shield filters injections, scripts and other guests nobody invited.'],
  [2, 'Port rules', 'Allow/deny rules per subnet. The last rule is always "deny all".'],
  [4, 'Lockbox', 'Secrets belong here. Not in the README. Not in the pipeline log. Here.'],
  [5, 'Private tunnel', 'Gives a service a private address in your network - the public internet stays outside.'],
  [7, 'Pop fact', 'The firewall change was approved. Nobody remembers by whom.'],
  [9, 'Inspection season', 'Starts when the last inspection ends. Lasts until the next one starts.'],
  [11, 'Pop fact', 'Every forgotten server was once "just a quick proof of concept".'],
  [13, 'Uptime', 'Behind every green dashboard is an engineer with lukewarm coffee.'],
  [16, 'Rules', 'A rule without automation is a wish. A rule with automation is a guardrail.'],
  [19, 'Script it', 'Infrastructure as code: the change is reviewed once and repeated a thousand times.'],
  [20, 'Tokens', 'Passwords expire. Always on a Friday. Prefer identities that rotate themselves.'],
  [21, 'Robot account', "An identity for scripts and pipelines. When it's retired, so is your deployment."],
  [22, 'Proxy', 'Sits between you and the internet and has opinions about every request.'],
  [26, 'It was DNS', "It's not DNS. There's no way it's DNS. ...It was DNS."],
  [28, 'Jump host', 'Shell access via a hardened jump host - no public addresses on your machines.'],
  [30, 'Pop fact', 'Status page green = deployment window open. Enjoy it while it lasts.'],
  [32, 'Bridge', 'Scans, alarms, charts: visibility is the first security control.'],
  [34, 'Robots', 'Every robot project eventually needs: a private tunnel, a firewall rule and DNS.'],
  [37, 'Gateway', 'A traffic gateway with a built-in shield, encryption and path routing.'],
  [39, 'Secure by default', 'Least privilege, private networking, secrets in lockboxes. Repeat weekly.'],
  [43, 'Welcome!', 'Thanks to everyone keeping the console running. Safely.'],
];
export const FACTS: Fact[] = FACTS_AT.map(([i, title, text]) => ({ t: LINES[i].t + 0.3, d: 5.2, title, text }));
