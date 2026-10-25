// The scene timeline. Each scene is a small piece of "office / cloud software" built in
// HTML (or a 3D line-art view) with the lyric typed into it as big bold text.
// Every update is a pure function of song time.

import { TypedLine } from './lyric';
import { LINES, SONG_END } from './lyrics';
import { Mascot } from './mascot';
import { easeOut, easeOutBack, hash, mk, popStyle, prog, slideIn, typed } from './util';
import type { Mode3D } from './world3d';

export interface Ctx {
  t: number;
  u: number; // 0..1 progress through the scene
  local: number; // seconds since scene start
  beat: number;
  pulse: number;
  screen: DOMRect | null; // projected stage screen (3D stage scenes)
}
type Upd = (c: Ctx) => void;

export interface SceneDef {
  id: string;
  lines: number[];
  theme: 'dark' | 'light';
  three?: Mode3D;
  opts?: Record<string, number | string | boolean>;
  start?: number;
  build: (root: HTMLElement) => Upd;
}

const L = LINES;
/** start time of word wi in line li */
const W = (li: number, wi: number) => L[li].words?.[wi] ?? L[li].t;

// ---------- building blocks ----------
function header(root: HTMLElement, left: string, right = '') {
  const h = mk('div', 'hdr', root);
  mk('span', 'hdr-l', h, left);
  mk('span', 'hdr-r', h, right);
  return h;
}

/** Lyric lines stacked in one block. replace: only the current line is shown. */
function lyrics(parent: HTMLElement, idx: number[], cls = '', replace = false) {
  const box = mk('div', `lyr ${cls}`, parent);
  const tl = idx.map((i) => new TypedLine(box, L[i]));
  return (t: number) => {
    let active = 0;
    idx.forEach((li, k) => {
      if (t >= L[li].t - 0.3) active = k;
    });
    tl.forEach((l, k) => {
      l.update(t, k === tl.length - 1 ? 99 : 0.4);
      if (replace) l.el.style.display = k === active ? 'block' : 'none';
    });
  };
}

function mascot(parent: HTMLElement, px: number, cls = '') {
  const wrap = mk('div', `mascot-wrap ${cls}`, parent);
  return { wrap, m: new Mascot(wrap, px) };
}

function rowsIn(rows: HTMLElement[], t: number, times: number[]) {
  rows.forEach((r, i) => slideIn(r, t, times[i] ?? times[times.length - 1]));
}

// ---------- scenes ----------
export const SCENES: SceneDef[] = [
  // ======================= INTRO =======================
  {
    id: 'intro-chat',
    lines: [],
    start: 0,
    theme: 'dark',
    build(root) {
      const app = mk('div', 'chat', root);
      const side = mk('div', 'chat-side', app);
      mk('div', 'side-h mono', side, 'CHANNELS');
      ['# platform-team', '# security', '# incidents', '# deploys', '# random'].forEach((c, i) => mk('div', `side-i mono${i === 0 ? ' on' : ''}`, side, c));
      mk('div', 'side-h mono', side, 'DIRECT MESSAGES');
      ['● Lisa (Security)', '● Tom (Network)', '● Audit Office', '● NIMBUS-01'].forEach((c) => mk('div', 'side-i mono dm', side, c));
      const main = mk('div', 'chat-main', app);
      header(main, 'CHAT  ·  # platform-team  ·  214 members', 'FRIDAY 16:58');
      const feed = mk('div', 'feed', main);
      const msg = (who: string, tag: string, text: string) => {
        const m = mk('div', 'msg', feed);
        mk('div', 'av mono', m, who[0]);
        const b = mk('div', 'msg-b', m);
        const h = mk('div', 'msg-h', b);
        mk('b', '', h, who);
        mk('span', 'mono dim', h, tag);
        mk('div', 'mono msg-t', b, text);
        return m;
      };
      const msgs = [
        msg('SEC-SCANNER', '16:41', '✓ scanned 1,284 resources · 3 new findings'),
        msg('Lisa', 'Security · 16:44', 'friendly reminder: quarterly security review is due.'),
        msg('Tom', 'Network · 16:52', 'who changed the firewall again?'),
      ];
      const big = mk('div', 'msg big-msg', feed);
      mk('div', 'av mono', big, 'P');
      const bb = mk('div', 'msg-b', big);
      const bh = mk('div', 'msg-h', bb);
      mk('b', '', bh, 'Platform Team');
      mk('span', 'mono dim', bh, 'BST/ESW5 · 16:58');
      const title = mk('div', 'title-typed', bb);
      const sub = mk('div', 'mono subtitle', bb, 'BST/ESW5 presents a song about RBAC, firewalls and the paperwork in between.');
      const typing = mk('div', 'mono typing', main, 'Platform Team is typing ●●●');
      const TITLE = 'Welcome to Cloud Engineering.';
      return (c) => {
        rowsIn(msgs, c.t, [0.8, 2.4, 4.0]);
        slideIn(big, c.t, 6.6);
        const x = prog(c.t, 6.8, 10.2);
        const s = typed(TITLE, x);
        const k = s.lastIndexOf(' ');
        title.innerHTML = '';
        mk('span', '', title, s.slice(0, k + 1));
        mk('span', 'now', title, s.slice(k + 1));
        if (x < 1 || Math.floor(c.t * 3) % 2) mk('span', 'caretbox', title);
        slideIn(sub, c.t, 10.6);
        typing.style.opacity = c.t > 5.4 && c.t < 6.7 ? '1' : '0';
      };
    },
  },

  // ======================= VERSE 1 =======================
  {
    id: 'iam',
    lines: [0],
    theme: 'dark',
    build(root) {
      header(root, 'CLOUD PORTAL  ›  rg-platform-prod  ›  ACCESS CONTROL (IAM)', 'ROLE ASSIGNMENTS · 4');
      const up = lyrics(root, [0], 'left big');
      const tbl = mk('div', 'panel table right-panel', root);
      const hr = mk('div', 'tr th mono', tbl);
      ['PRINCIPAL', 'ROLE', 'SCOPE'].forEach((x) => mk('span', '', hr, x));
      const data = [
        ['NIMBUS-01', 'Contributor', 'rg-platform-prod', ''],
        ['Lisa M.', 'Security Reader', 'subscription', ''],
        ['Tom K.', 'Network Contributor', 'vnet-hub', ''],
        ['deploy-pipeline', 'Owner', 'subscription', 'warn'],
      ];
      const rows = data.map(([a, b, s, w]) => {
        const r = mk('div', `tr mono ${w}`, tbl);
        mk('span', '', r, a);
        mk('span', '', r, b + (w ? '  ⚠ too broad' : ''));
        mk('span', '', r, s);
        return r;
      });
      const bas = mk('div', 'panel bastion right-panel2', root);
      mk('div', 'mono dim', bas, 'BASTION · bas-hub-01');
      const btn = mk('div', 'btn green', bas, 'Connect via Bastion');
      const T0 = W(0, 0);
      return (c) => {
        up(c.t);
        rowsIn(rows, c.t, [T0 - 0.2, T0 + 0.15, T0 + 0.5, T0 + 0.85]);
        popStyle(bas, c.t, W(0, 1) - 0.1, 20);
        btn.style.boxShadow = `0 0 ${(10 + c.pulse * 30).toFixed(0)}px rgba(53,224,122,${(0.3 + c.pulse * 0.4).toFixed(2)})`;
      };
    },
  },
  {
    id: 'waf',
    lines: [1],
    theme: 'dark',
    build(root) {
      header(root, 'WAF  ·  policy-frontdoor  ·  REQUEST LOG', 'MODE: PREVENTION');
      const plane = mk('div', 'logplane', root);
      const inner = mk('div', 'logplane-in mono', plane);
      const reqs = [
        ['GET', "/login?user=admin'--", '403', 'BLOCKED · SQLi'],
        ['GET', '/api/health', '200', 'ALLOWED'],
        ['POST', '/search?q=<script>alert(1)</script>', '403', 'BLOCKED · XSS'],
        ['GET', '/assets/app.js', '200', 'ALLOWED'],
        ['GET', '/../../etc/passwd', '403', 'BLOCKED · LFI'],
        ['GET', '/api/orders/42', '200', 'ALLOWED'],
        ['POST', '/wp-admin/install.php', '403', 'BLOCKED · BOT'],
        ['GET', '/favicon.ico', '200', 'ALLOWED'],
      ];
      const rows: HTMLElement[] = [];
      for (let i = 0; i < 40; i++) {
        const [m, p, s, r] = reqs[i % reqs.length];
        const row = mk('div', `lrow ${s === '403' ? 'bad' : ''}`, inner);
        row.textContent = `12:04:${String(10 + i).padStart(2, '0')}  ${m.padEnd(5)} ${p.padEnd(42)} ${s}  ${r}`;
        rows.push(row);
      }
      const counter = mk('div', 'counter mono', root);
      const up = lyrics(root, [1], 'top big');
      return (c) => {
        up(c.t);
        inner.style.transform = `translateY(${(-c.local * 70).toFixed(1)}px)`;
        counter.textContent = `BLOCKED TODAY  ${Math.floor(18000 + c.local * 260).toLocaleString('en-US')}`;
      };
    },
  },
  {
    id: 'diagram',
    lines: [2],
    theme: 'dark',
    build(root) {
      header(root, 'FIG. 3  ·  HUB-SPOKE NETWORK  ·  NOT TO SCALE', 'REV 14');
      const svgWrap = mk('div', 'diagram', root);
      svgWrap.innerHTML = `
      <svg viewBox="0 0 1600 700" class="dg">
        <g class="n n0"><rect x="40" y="290" width="220" height="120" rx="60"/><text x="150" y="358">INTERNET</text></g>
        <path class="w w0" d="M260 350 H460"/>
        <g class="n n1"><rect x="460" y="270" width="260" height="160" rx="10"/><text x="590" y="340">APP GATEWAY</text><text class="s" x="590" y="372">WAF_v2 · TLS</text></g>
        <path class="w w1" d="M720 350 H860"/>
        <g class="n n2"><rect class="vnet" x="860" y="80" width="680" height="540" rx="14"/><text x="1200" y="125">VNET-HUB 10.20.0.0/16</text></g>
        <g class="n n3"><rect x="920" y="170" width="560" height="170" rx="8"/><text x="1080" y="262">snet-app</text><g class="shield"><path d="M1380 205 l40 14 v30 c0 26 -20 40 -40 48 c-20 -8 -40 -22 -40 -48 v-30 z"/><text class="s" x="1380" y="320">NSG</text></g></g>
        <g class="n n4"><rect x="920" y="380" width="560" height="170" rx="8"/><text x="1080" y="472">snet-data</text><g class="shield"><path d="M1380 415 l40 14 v30 c0 26 -20 40 -40 48 c-20 -8 -40 -22 -40 -48 v-30 z"/><text class="s" x="1380" y="530">NSG</text></g></g>
      </svg>`;
      const parts = [...svgWrap.querySelectorAll<SVGGElement>('.n')];
      const wires = [...svgWrap.querySelectorAll<SVGPathElement>('.w')];
      const up = lyrics(root, [2], 'top big');
      return (c) => {
        up(c.t);
        const a = L[2].t - 0.3;
        parts.forEach((p, i) => p.style.opacity = easeOut(prog(c.t, a + i * 0.45, a + i * 0.45 + 0.4)).toFixed(3));
        wires.forEach((w, i) => {
          const k = prog(c.t, a + 0.2 + i * 0.6, a + 0.7 + i * 0.6);
          w.style.strokeDasharray = '300';
          w.style.strokeDashoffset = String(300 * (1 - k));
        });
        svgWrap.querySelectorAll<SVGGElement>('.shield').forEach((s) => (s.style.opacity = (0.6 + c.pulse * 0.4).toFixed(2)));
      };
    },
  },
  {
    id: 'stage-q3',
    lines: [3],
    theme: 'dark',
    three: 'stage',
    build(root) {
      const scr = mk('div', 'screen', root);
      const cal = mk('div', 'cal', scr);
      mk('div', 'cal-h', cal, 'SEPTEMBER · Q3');
      const g = mk('div', 'cal-g', cal);
      const days: HTMLElement[] = [];
      for (let d = 1; d <= 30; d++) days.push(mk('span', '', g, String(d)));
      const up = lyrics(scr, [3], 'onscreen');
      return (c) => {
        place(scr, c.screen);
        up(c.t);
        const mark = c.t >= W(3, 4);
        days[18].classList.toggle('mark', mark);
        popStyle(cal, c.t, L[3].t - 0.4, 10);
      };
    },
  },
  {
    id: 'vault',
    lines: [4],
    theme: 'dark',
    three: 'vault',
    build(root) {
      header(root, 'FIG. 4  ·  KEY VAULT  ·  EXPLODED VIEW', 'kv-platform-prod');
      const up = lyrics(root, [4], 'bottom big');
      return (c) => up(c.t);
    },
  },
  {
    id: 'vault-cage',
    lines: [5],
    theme: 'dark',
    three: 'vault',
    opts: { cage: true },
    build(root) {
      header(root, 'FIG. 5  ·  KEY VAULT  ·  PRIVATE ENDPOINT', 'NETWORK: RESTRICTED');
      const up = lyrics(root, [5], 'bottom big');
      return (c) => up(c.t);
    },
  },
  {
    id: 'ingress',
    lines: [6],
    theme: 'dark',
    build(root) {
      header(root, 'TRAFFIC ANALYTICS  ·  vnet-hub  ·  LAST 15 MIN', 'FLOWS 12,408');
      const box = mk('div', 'vnetbox mono', root, 'VNET-HUB');
      const arrows: HTMLElement[] = [];
      for (let i = 0; i < 5; i++) arrows.push(mk('div', 'arrow in', root));
      for (let i = 0; i < 5; i++) arrows.push(mk('div', 'arrow out', root));
      const li = mk('div', 'tag-big in mono', root, '→ INGRESS  4,201/s');
      const lo = mk('div', 'tag-big out mono', root, 'EGRESS  3,877/s →');
      const up = lyrics(root, [6], 'top big');
      return (c) => {
        up(c.t);
        popStyle(box, c.t, L[6].t - 0.4, 0);
        arrows.forEach((a, i) => {
          const isIn = i < 5;
          const k = i % 5;
          const on = c.t > (isIn ? W(6, 0) : W(6, 2)) - 0.2;
          a.style.opacity = on ? '1' : '0';
          a.style.top = `${38 + k * 7}%`;
          a.style.backgroundPositionX = `${((c.t * 160 + k * 40) % 80).toFixed(0)}px`;
        });
        popStyle(li, c.t, W(6, 0), 10);
        popStyle(lo, c.t, W(6, 2), 10);
      };
    },
  },
  {
    id: 'diff',
    lines: [7],
    theme: 'dark',
    build(root) {
      header(root, 'PULL REQUEST #4711  ·  firewall-rules.tf  ·  +2 −2', 'CHANGED BY: ???');
      const code = mk('div', 'panel code mono', root);
      const lines: [string, string][] = [
        [' ', 'resource "firewall_rule" "allow_https" {'],
        [' ', '  priority = 100'],
        ['-', '  source   = "10.0.0.0/8"'],
        ['+', '  source   = "0.0.0.0/0"'],
        ['-', '  action   = "Deny"'],
        ['+', '  action   = "Allow"'],
        [' ', '}'],
      ];
      const rows = lines.map(([k, s]) => {
        const r = mk('div', `cl ${k === '-' ? 'del' : k === '+' ? 'add' : ''}`, code);
        mk('span', 'gut', r, k);
        mk('span', '', r, s);
        return r;
      });
      const who = mk('div', 'panel who mono', root);
      who.innerHTML = 'Author: <b>unknown</b><br>Reviewers: <b>none</b><br>Merged: <b class="red">yes</b>';
      const { wrap, m } = mascot(root, 9, 'mascot-br');
      const up = lyrics(root, [7], 'top big');
      return (c) => {
        up(c.t);
        rowsIn(rows, c.t, rows.map((_, i) => L[7].t - 0.5 + i * 0.25));
        popStyle(who, c.t, W(7, 3), 16);
        slideIn(wrap, c.t, W(7, 2));
        m.update(c.t, c.beat, c.t > W(7, 3) ? 'alarm' : 'idle');
      };
    },
  },
  {
    id: 'forms',
    lines: [8],
    theme: 'light',
    build(root) {
      header(root, 'COMPLIANCE HUB  ·  app-portal  ·  OPEN TASKS 3', 'DUE: FRIDAY');
      const up = lyrics(root, [8], 'top big');
      const cards = [
        ['LeanIX', 'Fact sheet: app-portal', 'Completeness 62%', 0.62],
        ['Self Check', 'Operator Self Check 2026', '14 / 40 answered', 0.35],
        ['BTIA', 'Business Impact Assessment', 'Status: draft', 0.1],
      ].map(([a, b, s, p], i) => {
        const cd = mk('div', 'card', root);
        cd.style.left = `${4 + i * 32.5}vw`;
        mk('div', 'card-k mono', cd, String(a));
        mk('div', 'card-t', cd, String(b));
        mk('div', 'card-s mono', cd, String(s));
        const bar = mk('div', 'bar', cd);
        const fill = mk('div', 'bar-f', bar);
        fill.dataset.p = String(p);
        return cd;
      });
      const times = [W(8, 0), W(8, 1), W(8, 3)];
      return (c) => {
        up(c.t);
        cards.forEach((cd, i) => {
          popStyle(cd, c.t, times[i] - 0.1, 30);
          const f = cd.querySelector<HTMLElement>('.bar-f')!;
          f.style.width = `${(Number(f.dataset.p) * 100 * easeOut(prog(c.t, times[i], times[i] + 0.8))).toFixed(1)}%`;
        });
      };
    },
  },
  {
    id: 'calendar',
    lines: [9],
    theme: 'light',
    build(root) {
      header(root, 'CALENDAR  ·  WEEK 43', 'WORKING HOURS 08–18');
      const grid = mk('div', 'week', root);
      ['MON', 'TUE', 'WED', 'THU', 'FRI'].forEach((d) => mk('div', 'wd mono', grid, d));
      const names = ['Audit kick-off', 'Pre-audit sync', 'Evidence review', 'Audit follow-up', 'Audit prep', 'Audit (cont.)', 'Audit Q&A', 'Audit wrap-up', 'Audit retro', 'Audit audit'];
      const ev = names.map((n, i) => {
        const e = mk('div', 'ev', root);
        e.textContent = n;
        e.style.left = `${8 + (i % 5) * 17.6}%`;
        e.style.top = `${30 + Math.floor(i / 5) * 22 + hash(i) * 8}%`;
        return e;
      });
      const up = lyrics(root, [9], 'top big');
      return (c) => {
        up(c.t);
        ev.forEach((e, i) => popStyle(e, c.t, L[9].t - 0.2 + i * 0.28, 20, 0.25));
      };
    },
  },
  {
    id: 'tickets',
    lines: [10],
    theme: 'dark',
    build(root) {
      header(root, 'SERVICE DESK  ·  BOARD: PLATFORM', 'OPEN 37');
      const board = mk('div', 'board', root);
      const cols = ['NEW', 'IN PROGRESS', 'WAITING', 'DONE'].map((n) => {
        const col = mk('div', 'col', board);
        mk('div', 'col-h mono', col, n);
        return col;
      });
      ['INC-8812 · VPN slow', 'REQ-1203 · new subnet', 'CHG-0991 · patch window'].forEach((x, i) => mk('div', 'tcard mono', cols[i % 2 ? 2 : 3], x));
      const cert = mk('div', 'tcard mono hot', root, 'CERT-2291 · critical CVE in base image');
      const call = mk('div', 'call', root);
      mk('div', 'mono dim', call, 'INCOMING CALL');
      mk('div', 'call-n', call, 'CSC — Cyber Security Center');
      const btns = mk('div', 'call-b', call);
      mk('span', 'btn green', btns, 'Accept');
      mk('span', 'btn red', btns, 'Decline');
      const up = lyrics(root, [10], 'top big');
      return (c) => {
        up(c.t);
        const a = W(10, 1);
        const k = easeOut(prog(c.t, a, a + 0.5));
        cert.style.left = `${8 + k * 23}%`;
        cert.style.top = `${48 + (1 - k) * 0 + 0}%`;
        popStyle(cert, c.t, L[10].t - 0.3, 20);
        const ring = c.t > W(10, 2) - 0.1;
        popStyle(call, c.t, W(10, 2) - 0.1, 30);
        if (ring) call.style.transform += ` rotate(${(Math.sin(c.t * 40) * 1.5).toFixed(2)}deg)`;
      };
    },
  },
  {
    id: 'approval',
    lines: [11],
    theme: 'dark',
    build(root) {
      header(root, 'APP INVENTORY  ·  shadow-gpt-prod', 'OWNER: ???');
      const dlg = mk('div', 'panel dialog', root);
      mk('div', 'dlg-h', dlg, 'shadow-gpt-prod');
      const rows = [
        ['Created', '3 months ago'],
        ['Users', '1,204'],
        ['Data classification', 'not set'],
        ['Approved by', '—'],
        ['Approval history', '(empty)'],
      ].map(([a, b]) => {
        const r = mk('div', 'kv mono', dlg);
        mk('span', 'dim', r, a);
        mk('span', b === '—' || b === '(empty)' ? 'red' : '', r, b);
        return r;
      });
      const qs: HTMLElement[] = [];
      for (let i = 0; i < 9; i++) qs.push(mk('div', 'q', root, '?'));
      const { wrap, m } = mascot(root, 11, 'mascot-bl');
      const up = lyrics(root, [11], 'top big');
      return (c) => {
        up(c.t);
        popStyle(dlg, c.t, L[11].t - 0.4, 30);
        rowsIn(rows, c.t, rows.map((_, i) => L[11].t - 0.2 + i * 0.35));
        qs.forEach((q, i) => {
          const a = W(11, 2) + i * 0.15;
          const k = prog(c.t, a, a + 2.5);
          q.style.opacity = (k > 0 ? 1 - k : 0).toFixed(2);
          q.style.left = `${60 + hash(i) * 35}%`;
          q.style.top = `${80 - k * 50 - hash(i * 2) * 20}%`;
          q.style.fontSize = `${3 + hash(i * 3) * 4}vw`;
        });
        slideIn(wrap, c.t, W(11, 1));
        m.update(c.t, c.beat, 'shrug');
      };
    },
  },

  // ======================= CHORUS 1 =======================
  {
    id: 'stage-chorus',
    lines: [12, 13],
    theme: 'dark',
    three: 'stage',
    opts: { energy: 1 },
    build(root) {
      const scr = mk('div', 'screen', root);
      const up = lyrics(scr, [12, 13], 'onscreen', true);
      return (c) => {
        place(scr, c.screen);
        up(c.t);
      };
    },
  },
  {
    id: 'rules',
    lines: [14],
    theme: 'light',
    build(root) {
      header(root, 'LGTM PLATFORM  ·  POLICY UPDATES', 'SLIDE 7 / 48');
      const up = lyrics(root, [14], 'left big');
      const list = mk('div', 'rules', root);
      mk('div', 'rules-h', list, 'New rules this week');
      const R = ['Tag every resource', 'No public IPs', 'MFA for break-glass', 'Rotate keys every 90 days', 'Rotate keys every 60 days', 'Rotate keys every 30 days', 'Diagnostic settings: on', 'Private endpoints only', 'Encrypt the encryption', 'Document the documentation', 'Approve the approvals', 'Snacks require a ticket'];
      const items = R.map((r, i) => {
        const it = mk('div', 'rule mono', list);
        mk('span', 'num', it, String(i + 1).padStart(2, '0'));
        mk('span', '', it, r);
        return it;
      });
      return (c) => {
        up(c.t);
        rowsIn(items, c.t, items.map((_, i) => L[14].t - 0.2 + i * 0.28));
      };
    },
  },
  {
    id: 'cool',
    lines: [15],
    theme: 'dark',
    build(root) {
      header(root, 'PLATFORM HEALTH  ·  ALL REGIONS', 'STATUS: OPERATIONAL');
      const grid = mk('div', 'tiles', root);
      const T = [
        ['UPTIME', '99.98', '%'],
        ['INCIDENTS', '0', ''],
        ['P95 LATENCY', '42', 'ms'],
        ['CPU', '31', '%'],
        ['FAILED DEPLOYS', '0', ''],
        ['TEMPERATURE', 'cool', '❄'],
      ];
      const tiles = T.map(([a, b, u2]) => {
        const tl = mk('div', 'tile', grid);
        mk('div', 'mono dim', tl, a);
        const v = mk('div', 'tile-v', tl);
        v.textContent = b;
        mk('span', 'unit', v, ' ' + u2);
        const sp = mk('div', 'spark', tl);
        return { tl, sp };
      });
      const up = lyrics(root, [15], 'bottom big');
      return (c) => {
        up(c.t);
        tiles.forEach(({ tl, sp }, i) => {
          popStyle(tl, c.t, L[15].t - 0.5 + i * 0.12, 20);
          sp.style.backgroundPositionX = `${(-c.t * 60 - i * 30).toFixed(0)}px`;
        });
      };
    },
  },
  {
    id: 'signs-paper',
    lines: [16],
    theme: 'light',
    build(root) {
      header(root, 'TOWN HALL  ·  Q&A', 'LIVE');
      const up = lyrics(root, [16], 'top big');
      return signs(root, 'PAPERWORK', () => L[16].t + 0.3, () => L[16].e, up);
    },
  },
  {
    id: 'timesheet',
    lines: [17],
    theme: 'light',
    build(root) {
      header(root, 'TIMESHEET  ·  WEEK 43', 'TOTAL 0.0 h');
      const hdr = root.querySelector<HTMLElement>('.hdr-r')!;
      const grid = mk('div', 'ts', root);
      const cells: HTMLElement[] = [];
      mk('div', 'ts-h mono', grid, '');
      ['MON', 'TUE', 'WED', 'THU', 'FRI'].forEach((d) => mk('div', 'ts-h mono', grid, d));
      for (let h = 8; h < 18; h++) {
        mk('div', 'ts-h mono', grid, `${h}:00`);
        for (let d = 0; d < 5; d++) cells.push(mk('div', 'ts-c', grid));
      }
      const up = lyrics(root, [17], 'top big');
      return (c) => {
        up(c.t);
        const n = Math.floor(easeOut(prog(c.t, L[17].t, L[17].e)) * cells.length);
        cells.forEach((cl, i) => {
          const on = i < n;
          cl.classList.toggle('on', on);
          cl.textContent = on && i % 5 === 0 ? 'compliance' : '';
        });
        hdr.textContent = `TOTAL ${(n * 0.95).toFixed(1)} h`;
      };
    },
  },
  {
    id: 'gauges',
    lines: [18],
    theme: 'dark',
    build(root) {
      header(root, 'CLOUD SCORECARD', 'LIVE');
      const g = mk('div', 'gauges', root);
      const make = (label: string, red: boolean) => {
        const w = mk('div', 'gauge', g);
        w.innerHTML = `<svg viewBox="0 0 200 120"><path class="arc" d="M20 110 A80 80 0 0 1 180 110"/><path class="arc ${red ? 'redz' : 'greenz'}" d="M140 41 A80 80 0 0 1 180 110"/><line class="needle" x1="100" y1="110" x2="100" y2="40"/><circle cx="100" cy="110" r="7" class="hub"/></svg>`;
        mk('div', 'mono g-l', w, label);
        return w.querySelector<SVGLineElement>('.needle')!;
      };
      const speed = make('DEPLOY SPEED', false);
      const risk = make('RISK', true);
      const up = lyrics(root, [18], 'top big');
      return (c) => {
        up(c.t);
        const a1 = -80 + 155 * easeOutBack(prog(c.t, W(18, 2), W(18, 2) + 0.6));
        const a2 = -80 + 150 * easeOutBack(prog(c.t, W(18, 6), W(18, 6) + 0.6));
        speed.setAttribute('transform', `rotate(${(a1 + Math.sin(c.t * 30) * 1.2).toFixed(2)} 100 110)`);
        risk.setAttribute('transform', `rotate(${(a2 + Math.sin(c.t * 25) * 1.5).toFixed(2)} 100 110)`);
      };
    },
  },
  {
    id: 'pipeline',
    lines: [19],
    theme: 'dark',
    build(root) {
      header(root, 'PIPELINE  ·  platform-infra  ·  #1842', 'TRIGGERED BY: NIMBUS-01');
      const st = mk('div', 'stages', root);
      const names = ['plan', 'policy check', 'security scan', 'deploy', 'verify'];
      const stages = names.map((n) => mk('div', 'stage mono', st, n));
      const term = mk('div', 'panel term mono', root);
      const { wrap, m } = mascot(root, 9, 'mascot-br');
      const up = lyrics(root, [19], 'top big');
      const out = [
        '$ terraform apply -auto-approve',
        'azurerm_key_vault.platform: Refreshing state...',
        'azurerm_firewall_policy.hub: Modifying...',
        'azurerm_private_endpoint.kv: Creating...',
        'Policy check: 42 passed, 0 failed',
        'Apply complete! Resources: 12 added, 3 changed, 0 destroyed.',
      ];
      return (c) => {
        up(c.t);
        const a = L[19].t;
        stages.forEach((s, i) => {
          const t0 = a + i * 0.9;
          s.classList.toggle('run', c.t >= t0 && c.t < t0 + 0.9);
          s.classList.toggle('ok', c.t >= t0 + 0.9);
        });
        const n = Math.floor(prog(c.t, a - 0.3, a + 5) * out.length * 1.0001);
        term.innerHTML = '';
        out.slice(0, Math.max(1, n)).forEach((l, i) => mk('div', i === out.length - 1 ? 'green' : '', term, i === 0 ? typed(l, prog(c.t, a - 0.8, a - 0.2)) : l));
        slideIn(wrap, c.t, a + 4.5);
        m.update(c.t, c.beat, c.t > a + 4.6 ? 'happy' : 'idle');
      };
    },
  },

  // ======================= VERSE 2 =======================
  {
    id: 'appreg',
    lines: [20],
    theme: 'dark',
    build(root) {
      header(root, 'CLOUD PORTAL  ›  APP REGISTRATIONS  ›  portal-backend  ›  CERTIFICATES & SECRETS', '');
      const tbl = mk('div', 'panel table wide', root);
      const hr = mk('div', 'tr th mono', tbl);
      ['DESCRIPTION', 'EXPIRES', 'VALUE'].forEach((x) => mk('span', '', hr, x));
      const rows = [
        ['prod-client-secret', '2026-10-23', 'Qx8~••••••••'],
        ['ci-secret', '2027-01-10', 'Mf2~••••••••'],
      ].map(([a, b, v]) => {
        const r = mk('div', 'tr mono', tbl);
        mk('span', '', r, a);
        mk('span', '', r, b);
        mk('span', '', r, v);
        return r;
      });
      const stamp = mk('div', 'stamp', root, 'EXPIRED');
      const up = lyrics(root, [20], 'top big');
      return (c) => {
        up(c.t);
        rowsIn(rows, c.t, [L[20].t - 0.4, L[20].t - 0.2]);
        const a = W(20, 3);
        const k = easeOutBack(prog(c.t, a, a + 0.35));
        stamp.style.opacity = k > 0 ? '1' : '0';
        stamp.style.transform = `rotate(-12deg) scale(${(2.2 - 1.2 * k).toFixed(3)})`;
        rows[0].classList.toggle('expired', c.t > a);
      };
    },
  },
  {
    id: 'retired',
    lines: [21],
    theme: 'light',
    build(root) {
      header(root, 'IDENTITY  ·  SERVICE PRINCIPALS', 'ACTIVE 3 → 2');
      const up = lyrics(root, [21], 'top big');
      const org = mk('div', 'org', root);
      const top = mk('div', 'onode', org, 'Tenant');
      const kids = mk('div', 'orow', org);
      const nodes = ['sp-deploy', 'sp-backup', 'sp-legacy-2019', 'sp-monitoring'].map((n) => mk('div', 'onode mono', kids, n));
      const sel = mk('div', 'select-box', root);
      mk('span', 'sel-l mono', sel, 'retired');
      void top;
      return (c) => {
        up(c.t);
        const a = W(21, 2);
        const n = nodes[2];
        const r = n.getBoundingClientRect();
        sel.style.left = `${r.left - 8}px`;
        sel.style.top = `${r.top - 8}px`;
        sel.style.width = `${r.width + 16}px`;
        sel.style.height = `${r.height + 16}px`;
        sel.style.opacity = c.t > a - 0.2 ? '1' : '0';
        n.style.opacity = (1 - 0.8 * prog(c.t, W(21, 4), W(21, 4) + 0.6)).toFixed(2);
        n.style.textDecoration = c.t > W(21, 4) ? 'line-through' : 'none';
      };
    },
  },
  {
    id: 'tunnel',
    lines: [22, 23],
    theme: 'dark',
    three: 'tunnel',
    build(root) {
      header(root, 'FIG. 6  ·  DEVELOPER CONNECTIVITY', 'STATUS: DEGRADED');
      const up = lyrics(root, [22, 23], 'top big');
      return (c) => up(c.t);
    },
  },
  {
    id: 'meeting',
    lines: [24],
    theme: 'dark',
    build(root) {
      header(root, 'VIDEO CALL  ·  Architecture Board  ·  47 participants', '01:12:44');
      const grid = mk('div', 'call-grid', root);
      const tiles = ['IBC', 'ARCH', 'SEC', 'NET', 'EA', 'YOU'].map((n) => {
        const tl = mk('div', 'vt', grid);
        mk('div', 'vt-av', tl, n);
        mk('div', 'mono vt-n', tl, n === 'YOU' ? 'You (muted)' : `${n} Board`);
        return tl;
      });
      const up = lyrics(root, [24], 'bottom big');
      return (c) => {
        up(c.t);
        tiles.forEach((tl, i) => {
          popStyle(tl, c.t, L[24].t - 0.5 + i * 0.1, 10);
          tl.classList.toggle('speak', Math.floor(c.beat) % 6 === i);
        });
      };
    },
  },
  {
    id: 'sheet',
    lines: [25],
    theme: 'light',
    build(root) {
      header(root, 'evidence_v3_final_FINAL(2).xlsx', 'AUTOSAVE ON');
      const sh = mk('div', 'sheet', root);
      const cells: HTMLElement[] = [];
      mk('div', 'sh-h', sh, '');
      'ABCDEFGH'.split('').forEach((x) => mk('div', 'sh-h mono', sh, x));
      for (let r = 1; r <= 14; r++) {
        mk('div', 'sh-h mono', sh, String(r));
        for (let k = 0; k < 8; k++) cells.push(mk('div', 'sh-c mono', sh));
      }
      const vals = ['✓', 'tbd', 'n/a', 'see tab 7', '✓', 'pending', '✓', 'ask Tom'];
      const up = lyrics(root, [25], 'top big over');
      return (c) => {
        up(c.t);
        const n = Math.floor(prog(c.t, L[25].t - 0.5, L[25].e + 0.4) * cells.length);
        cells.forEach((cl, i) => (cl.textContent = i < n ? vals[Math.floor(hash(i) * vals.length)] : ''));
      };
    },
  },
  {
    id: 'dns',
    lines: [26, 27],
    theme: 'dark',
    build(root) {
      header(root, 'TERMINAL  ·  bash  ·  jump-01', '');
      const term = mk('div', 'panel term big-term mono', root);
      const note = mk('div', 'sticky', root, "It's not DNS.\nThere's no way it's DNS.\n…it was DNS.");
      const up = lyrics(root, [26, 27], 'top big');
      const script: [number, string, string][] = [
        [L[26].t - 0.6, '$ nslookup kv-platform.vault.azure.net', 'cmd'],
        [L[26].t + 0.2, 'Name:    kv-platform.privatelink.vaultcore.azure.net', ''],
        [L[26].t + 0.4, 'Address: 52.236.189.12   ← public?!', 'red'],
        [W(26, 2), '$ az network private-dns zone list -o table', 'cmd'],
        [W(26, 3), 'privatelink.vaultcore.azure.net   links: 0', 'red'],
        [L[27].t, '$ az network private-dns link vnet create ...', 'cmd'],
        [L[27].t + 1.2, '$ nslookup kv-platform.vault.azure.net', 'cmd'],
        [L[27].t + 1.6, 'Address: 10.20.4.7   ✓ private', 'green'],
      ];
      return (c) => {
        up(c.t);
        term.innerHTML = '';
        script.forEach(([at, s, k]) => {
          if (c.t < at) return;
          mk('div', k, term, k === 'cmd' ? typed(s, prog(c.t, at, at + 0.6)) : s);
        });
        popStyle(note, c.t, L[27].t + 0.8, 20);
      };
    },
  },
  {
    id: 'ssh',
    lines: [28, 29],
    theme: 'dark',
    build(root) {
      header(root, 'TERMINAL  ·  ssh', '');
      const term = mk('div', 'panel term big-term mono', root);
      const bubble = mk('div', 'bubble', root);
      mk('div', 'mono dim', bubble, 'Security · now');
      mk('div', 'bubble-t', bubble, 'not again.');
      const up = lyrics(root, [28, 29], 'top big');
      const script: [number, string, string][] = [
        [L[28].t - 0.5, '$ ssh -J bcn-jump.corp admin@10.20.4.7', 'cmd'],
        [W(28, 2), 'bcn-jump.corp: connecting...', ''],
        [L[28].e - 0.2, 'admin@10.20.4.7: Permission denied (publickey).', 'red'],
        [L[29].t + 0.3, '$ ssh -J bcn-jump.corp admin@10.20.4.7', 'cmd'],
        [L[29].t + 1.1, 'Security Alert #7781 opened automatically.', 'red'],
      ];
      return (c) => {
        up(c.t);
        term.innerHTML = '';
        script.forEach(([at, s, k]) => {
          if (c.t >= at) mk('div', k, term, k === 'cmd' ? typed(s, prog(c.t, at, at + 0.7)) : s);
        });
        popStyle(bubble, c.t, W(29, 2) - 0.1, 20);
      };
    },
  },
  {
    id: 'deploy',
    lines: [30, 31],
    theme: 'dark',
    build(root) {
      header(root, 'RELEASE  ·  2026.10  ·  OPERATOR SELF CHECK', '');
      const list = mk('div', 'panel checks', root);
      const items = ['Backups verified', 'Monitoring alerts on', 'Secrets in Key Vault', 'Private endpoints only', 'NSG rules reviewed', 'Runbook updated'].map((x) => {
        const r = mk('div', 'chk mono', list);
        mk('span', 'box', r, '');
        mk('span', '', r, x);
        return r;
      });
      const prog1 = mk('div', 'deploybar', root);
      const fill = mk('div', 'deploybar-f', prog1);
      const lbl = mk('div', 'mono deploy-l', root);
      const { wrap, m } = mascot(root, 10, 'mascot-br');
      const up = lyrics(root, [30, 31], 'top big');
      return (c) => {
        up(c.t);
        items.forEach((r, i) => {
          const at = L[30].t - 0.3 + i * 0.4;
          slideIn(r, c.t, at - 0.3);
          r.classList.toggle('done', c.t >= at);
        });
        const k = easeOut(prog(c.t, L[31].t, L[31].e));
        fill.style.width = `${(k * 100).toFixed(1)}%`;
        lbl.textContent = k < 1 ? `Deploying release 2026.10 … ${(k * 100).toFixed(0)}%` : 'Release 2026.10 deployed · clean ✓';
        lbl.classList.toggle('green', k >= 1);
        slideIn(wrap, c.t, L[31].t);
        m.update(c.t, c.beat, k >= 1 ? 'happy' : 'idle');
      };
    },
  },

  // ======================= BRIDGE =======================
  {
    id: 'windows',
    lines: [32, 33],
    theme: 'dark',
    build(root) {
      const titles: [number, string, string][] = [
        [W(32, 2), 'Ticket #5530', 'Status: New · Priority: High'],
        [W(32, 5), 'Vulnerability scan', '1,442 findings · 12 critical'],
        [W(33, 2), 'Dashboard: Compliance', '73% · trending ↗'],
        [W(33, 5), 'Plan v7 (final)', 'Q1 · Q2 · Q3 · Q4 · ???'],
      ];
      const wins: { el: HTMLElement; at: number }[] = [];
      titles.forEach(([at, t1, body], i) => {
        for (let k = 0; k < 3; k++) {
          const w = mk('div', 'win', root);
          const bar = mk('div', 'win-b mono', w);
          mk('span', 'dots', bar, '● ● ●');
          mk('span', '', bar, t1 + (k ? ` (${k + 1})` : ''));
          mk('div', 'win-c mono', w, body);
          w.style.left = `${10 + i * 14 + k * 3 + hash(i * 7 + k) * 6}%`;
          w.style.top = `${32 + i * 6 + k * 4}%`;
          wins.push({ el: w, at: at + k * 0.18 });
        }
      });
      const up = lyrics(root, [32, 33], 'top big over');
      return (c) => {
        up(c.t);
        wins.forEach((w) => popStyle(w.el, c.t, w.at - 0.1, 20, 0.25));
      };
    },
  },
  {
    id: 'signs-ai',
    lines: [34],
    theme: 'light',
    build(root) {
      header(root, 'ALL HANDS  ·  STRATEGY 2027', 'LIVE');
      const up = lyrics(root, [34], 'top big');
      return signs(root, 'AI', () => L[34].t + 0.4, () => W(34, 2) + 0.4, up, 3);
    },
  },
  {
    id: 'network',
    lines: [35],
    theme: 'dark',
    three: 'network',
    build(root) {
      header(root, 'FIG. 7  ·  NETWORK TOPOLOGY  ·  HUB → SPOKES', 'HEALTH CHECK');
      const up = lyrics(root, [35], 'bottom big');
      return (c) => up(c.t);
    },
  },

  // ======================= FINAL CHORUS =======================
  {
    id: 'globe',
    lines: [36, 37],
    theme: 'dark',
    three: 'globe',
    build(root) {
      header(root, 'GLOBAL EDGE  ·  APPLICATION GATEWAYS  ·  10 REGIONS', 'ALL HEALTHY');
      const up = lyrics(root, [36, 37], 'left big', true);
      return (c) => up(c.t);
    },
  },
  {
    id: 'badges',
    lines: [38, 39],
    theme: 'dark',
    build(root) {
      header(root, 'SECURITY POSTURE', 'SCORE 94 / 100');
      const row = mk('div', 'badges', root);
      const b = ['KEY VAULT', 'WAF', 'NSG'].map((n) => {
        const e = mk('div', 'badge', row);
        mk('div', 'badge-i', e, '✓');
        mk('div', 'mono', e, n);
        return e;
      });
      const shield = mk('div', 'shield-big', root, 'SECURE');
      const up = lyrics(root, [38, 39], 'top big', true);
      return (c) => {
        up(c.t);
        b.forEach((e, i) => popStyle(e, c.t, W(38, i === 0 ? 0 : i + 1) - 0.1, 0));
        popStyle(shield, c.t, W(39, 2) - 0.2, 0);
        shield.style.boxShadow = `0 0 ${(30 + c.pulse * 60).toFixed(0)}px rgba(53,224,122,0.5)`;
      };
    },
  },
  {
    id: 'stack',
    lines: [40, 41],
    theme: 'light',
    build(root) {
      header(root, 'MY TASKS', 'OVERDUE 3');
      const cards = [
        ['CERT', 'CERT-2291 · patch base image'],
        ['CSC', 'CSC follow-up call · 15:00'],
        ['BTIA', 'BTIA review · draft v4'],
      ].map(([k, s], i) => {
        const e = mk('div', 'slap', root);
        mk('div', 'card-k mono', e, k);
        mk('div', 'card-t', e, s);
        e.style.left = `${12 + i * 26}%`;
        e.style.setProperty('--r', `${(hash(i) - 0.5) * 10}deg`);
        return e;
      });
      const sticky = mk('div', 'sticky lean', root, 'LeanIX:\nplease update\nyour fact sheet');
      const up = lyrics(root, [40, 41], 'top big', true);
      return (c) => {
        up(c.t);
        cards.forEach((e, i) => {
          const at = W(40, i) - 0.1;
          const k = easeOutBack(prog(c.t, at, at + 0.25));
          e.style.opacity = k > 0 ? '1' : '0';
          e.style.transform = `rotate(var(--r)) scale(${(1.6 - 0.6 * k).toFixed(3)})`;
        });
        // the sticky note gets torn off, and keeps coming back
        const a = L[41].t;
        const cyc = (c.t - a) % 1.4;
        const gone = c.t > a + 0.6 && cyc > 0.7 && cyc < 1.1;
        sticky.style.opacity = c.t < a - 0.3 ? '0' : gone ? '0' : '1';
        sticky.style.transform = `rotate(${gone ? 30 : 4}deg) translateY(${gone ? 80 : 0}px)`;
      };
    },
  },
  {
    id: 'tunnel-ok',
    lines: [42],
    theme: 'dark',
    three: 'tunnel',
    opts: { success: true },
    build(root) {
      header(root, 'FIG. 8  ·  DEVELOPER CONNECTIVITY', 'STATUS: HEALTHY');
      const up = lyrics(root, [42], 'top big');
      return (c) => up(c.t);
    },
  },
  {
    id: 'finale',
    lines: [43],
    theme: 'dark',
    three: 'stage',
    opts: { energy: 1 },
    build(root) {
      const scr = mk('div', 'screen', root);
      const up = lyrics(scr, [43], 'onscreen');
      const credits = mk('div', 'credits', scr);
      mk('div', 'mono dim', credits, 'A SONG FOR EVERYONE WHO KEEPS THE PLATFORM RUNNING');
      mk('div', 'cr-big', credits, 'BST/ESW5');
      const { wrap, m } = mascot(credits, 6, 'inline');
      const fade = mk('div', 'fade', root);
      void wrap;
      return (c) => {
        place(scr, c.screen);
        up(c.t);
        const cr = c.t > L[43].e + 2;
        (scr.querySelector('.lyr') as HTMLElement).style.display = cr ? 'none' : 'block';
        credits.style.display = cr ? 'flex' : 'none';
        m.update(c.t, c.beat, 'happy');
        fade.style.opacity = prog(c.t, SONG_END - 2.5, SONG_END - 0.3).toFixed(3);
      };
    },
  },
];

/** Hands holding up cardboard signs, one letter each (like a town-hall protest). */
function signs(root: HTMLElement, word: string, from: () => number, to: () => number, up: (t: number) => void, scale = 1) {
  const row = mk('div', 'signs', root);
  const letters = [...word].map((ch, i) => {
    const s = mk('div', 'sign', row);
    s.style.setProperty('--w', `${(scale * 7.5).toFixed(2)}vw`);
    mk('div', 'sign-board', s, ch);
    mk('div', 'sign-stick', s);
    const arm = mk('div', 'sign-arm', s);
    arm.style.background = ['#e0b08a', '#8d5a3b', '#f1c9a5', '#5b3a29', '#c68c5e'][i % 5];
    mk('div', `sign-sleeve s${i % 4}`, s);
    return s;
  });
  return (c: Ctx) => {
    up(c.t);
    const a = from();
    const step = Math.min(0.32, (to() - a) / Math.max(1, word.length));
    letters.forEach((s, i) => {
      const at = a + i * step;
      const k = easeOutBack(prog(c.t, at, at + 0.3));
      const bob = Math.sin((c.beat + i * 0.5) * Math.PI) * 6;
      s.style.transform = `translateY(${((1 - k) * 110 + (k > 0.99 ? bob : 0)).toFixed(1)}%) rotate(${((hash(i) - 0.5) * 8).toFixed(1)}deg)`;
    });
  };
}

/** Fit an overlay element to the projected 3D stage screen. */
function place(el: HTMLElement, r: DOMRect | null) {
  if (!r) return;
  el.style.left = `${r.x}px`;
  el.style.top = `${r.y}px`;
  el.style.width = `${r.width}px`;
  el.style.height = `${r.height}px`;
  el.style.fontSize = `${(r.width / 10).toFixed(1)}px`;
}

// ---------- timeline ----------
export interface Timed extends SceneDef {
  t0: number;
  t1: number;
}
export const TIMELINE: Timed[] = SCENES.map((s) => ({ ...s, t0: s.start ?? L[s.lines[0]].t - 0.55, t1: 0 }));
TIMELINE.forEach((s, i) => (s.t1 = i + 1 < TIMELINE.length ? TIMELINE[i + 1].t0 : SONG_END));
export const sceneAt = (t: number) => TIMELINE.find((s) => t >= s.t0 && t < s.t1) ?? TIMELINE[TIMELINE.length - 1];
