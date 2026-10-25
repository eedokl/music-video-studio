// "Comfort Zone" – the scene timeline. Industrial look: concrete, steel, signal red, EU blue/gold.
// Every update is a pure function of song time (frame-exact MP4 export).

import { LEAD, type LineOpts, SungLine } from './lyric';
import { BEAT_OFFSET, BPM, LINES, SONG_END, beatAt } from './lyrics';
import { easeInOut, easeOut, hash, mk, popStyle, prog, slideIn } from './util';
import type { Mode3D } from './world3d';

export interface Ctx {
  t: number;
  u: number;
  local: number;
  beat: number;
  pulse: number;
  screen: DOMRect | null;
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
/** start time of word wi in line li (already shifted by the lyric lead) */
const W = (li: number, wi: number) => (L[li].words?.[wi] ?? L[li].t) - LEAD;
const T0 = (li: number) => L[li].t - LEAD;
const E = (li: number) => L[li].e - LEAD;
/** When the last letter of a line has landed (same maths as SungLine: letters over 65 % of the word, 0.21 s stamp). */
function textDone(li: number) {
  const l = L[li];
  const s = (l.words?.[l.words.length - 1] ?? l.t) - LEAD;
  const e = Math.min(Math.max((l.ends?.[l.ends.length - 1] ?? l.e + 0.25) - LEAD, s + 0.12), s + 1.4);
  return s + (e - s) * 0.65 + 0.21;
}
/** The finished line stays readable this long before the scene may cut. */
const READ_HOLD = 0.3;
const timeAtBeat = (b: number) => BEAT_OFFSET + (b * 60) / BPM;
const clamp01 = (x: number) => Math.min(1, Math.max(0, x));

// ---------- building blocks ----------
function label(root: HTMLElement, left: string, right = '') {
  const h = mk('div', 'hdr', root);
  mk('span', 'hdr-l', h, left);
  if (right) mk('span', 'hdr-r', h, right);
  return h;
}

/** Lyric lines in one block (replace: only the current line). Bumps on the beat. */
function lyrics(parent: HTMLElement, idx: number[], cls = '', replace = false, lineOpts: Record<number, LineOpts> = {}) {
  const box = mk('div', `lyr ${cls}`, parent);
  const tl = idx.map((i) => new SungLine(box, L[i], '', lineOpts[i] ?? {}));
  return (t: number, pulse = 0) => {
    let active = 0;
    idx.forEach((li, k) => {
      if (t >= L[li].t - 0.3) active = k;
    });
    tl.forEach((l, k) => {
      l.update(t);
      if (replace) l.el.style.display = k === active ? 'block' : 'none';
    });
    const singing = idx.some((li) => t >= L[li].t - 0.1 && t <= L[li].e + 0.2) ? 1 : 0.4;
    box.style.setProperty('--bump', (1 + 0.085 * pulse * singing).toFixed(4));
  };
}

function stamp(el: HTMLElement, t: number, at: number, from = 2.2, rot = -6) {
  const k = prog(t, at, at + 0.1);
  el.style.opacity = k > 0 ? '1' : '0';
  const s = k < 1 ? from - (from - 1) * easeOut(k) : 1;
  el.style.transform = `rotate(${rot}deg) scale(${s.toFixed(3)})`;
}

const NS = 'http://www.w3.org/2000/svg';
function svg(parent: HTMLElement, cls: string, viewBox: string, inner: string) {
  const s = document.createElementNS(NS, 'svg');
  s.setAttribute('class', cls);
  s.setAttribute('viewBox', viewBox);
  s.innerHTML = inner;
  parent.appendChild(s);
  return s;
}

/** EU-style ring of 12 stars (SVG) */
function starRing(r = 80, size = 14, cls = '') {
  let g = '';
  for (let i = 0; i < 12; i++) {
    const a = (i / 12) * Math.PI * 2;
    const x = 100 + Math.cos(a) * r;
    const y = 100 + Math.sin(a) * r;
    let d = '';
    for (let k = 0; k < 10; k++) {
      const rr = k % 2 ? size * 0.4 : size;
      const b = (k / 10) * Math.PI * 2 - Math.PI / 2;
      d += `${k ? 'L' : 'M'}${(x + Math.cos(b) * rr).toFixed(1)} ${(y + Math.sin(b) * rr).toFixed(1)}`;
    }
    g += `<path class="st ${cls}" data-i="${i}" d="${d}Z"/>`;
  }
  return g;
}

// skyline of Brussels (Berlaymont = cross-shaped block in the middle)
const SKYLINE = `
  <path class="sky-far" d="M0 300 V220 h60 v-30 h40 v40 h50 v-60 h30 v60 h70 v-20 h40 v-70 h20 v70 h60 v30 h80 v-50 h40 v50 h70 v-90 h30 v90 h60 v-40 h50 v40 h80 v-60 h40 v60 h90 V300 Z"/>
  <g class="berlaymont">
    <path d="M520 300 V150 h40 v-30 h160 v30 h40 V300 Z"/>
    <path d="M470 300 V190 h330 V300 Z" opacity="0.9"/>
    ${Array.from({ length: 9 }, (_, i) => `<rect x="${532 + i * 26}" y="132" width="14" height="160" class="win"/>`).join('')}
  </g>
  <path class="sky-near" d="M0 300 V250 h120 v-20 h60 v20 h140 v-30 h50 v30 h160 v-10 h300 v-25 h70 v25 h300 V300 Z"/>`;

// ---------- scenes ----------
export const SCENES: SceneDef[] = [
  // ======================= INTRO =======================
  {
    id: 'intro-press',
    lines: [],
    start: 0,
    theme: 'dark',
    build(root) {
      const ring = svg(root, 'press-ring', '0 0 200 200', starRing(84, 9));
      const stars = [...ring.querySelectorAll<SVGPathElement>('.st')];
      const title = mk('div', 'press-title', root);
      const letters = [...'COMFORT ZONE'].map((ch) => mk('span', 'pl', title, ch === ' ' ? ' ' : ch));
      const sub = mk('div', 'press-sub mono', root, 'EUROPA · 2031');
      const bar = mk('div', 'press-bar', root);
      const b0 = Math.ceil(beatAt(1.4));
      return (c) => {
        letters.forEach((l, i) => stamp(l, c.t, timeAtBeat(b0 + i), 2.6, 0));
        stars.forEach((st, i) => st.classList.toggle('on', c.t >= timeAtBeat(b0 + i)));
        ring.style.transform = `translate(-50%, -50%) rotate(${(c.t * 4).toFixed(2)}deg)`;
        slideIn(sub, c.t, timeAtBeat(b0 + letters.length) + 0.2);
        bar.style.transform = `scaleX(${easeOut(prog(c.t, timeAtBeat(b0 + letters.length), timeAtBeat(b0 + letters.length) + 0.8)).toFixed(3)})`;
        title.style.transform = `scale(${(1 + 0.03 * c.pulse).toFixed(3)})`;
      };
    },
  },
  {
    id: 'intro-storm',
    lines: [],
    start: 12.4,
    theme: 'dark',
    three: 'storm',
    opts: { energy: 0.4 },
    build(root) {
      const t = mk('div', 'storm-caption', root, 'Out of the comfort zone');
      return (c) => {
        t.style.opacity = (prog(c.t, 14, 15.5) * (1 - prog(c.t, 24.6, 25.7))).toFixed(3);
        t.style.letterSpacing = `${(0.3 + c.local * 0.02).toFixed(3)}em`;
      };
    },
  },
  {
    id: 'brussels',
    lines: [0],
    start: 25.7,
    theme: 'dark',
    build(root) {
      const sky = mk('div', 'grey-sky', root);
      svg(sky, 'skyline', '0 0 1280 300', SKYLINE);
      const rain = mk('div', 'rain-overlay', root);
      const clock = mk('div', 'flipclock mono', root);
      const day = mk('div', 'clock-day mono', root, 'MO · BRÜSSEL');
      const up = lyrics(root, [0], 'bottom big');
      return (c) => {
        up(c.t, c.pulse);
        const mins = c.t < W(0, 3) ? (c.t < 32 ? 58 : 59) : 0;
        const hh = mins === 0 ? '08' : '07';
        clock.textContent = `${hh}:${String(mins).padStart(2, '0')}`;
        clock.classList.toggle('tick', mins === 0);
        rain.style.backgroundPositionY = `${(c.t * 900) % 400}px`;
        popStyle(day, c.t, 26.4, 10);
      };
    },
  },

  // ======================= VERSE 1 =======================
  {
    id: 'meetings',
    lines: [1],
    theme: 'light',
    build(root) {
      label(root, 'KALENDER · KW 42', 'MEETINGS: ∞');
      const grid = mk('div', 'meet-grid', root);
      const cells: HTMLElement[] = [];
      for (let i = 0; i < 40; i++) cells.push(mk('div', 'meet mono', grid, 'MEETING'));
      const up = lyrics(root, [1], 'top big');
      return (c) => {
        up(c.t, c.pulse);
        cells.forEach((m, i) => popStyle(m, c.t, T0(1) - 0.3 + i * 0.07, 0, 0.18));
      };
    },
  },
  {
    id: 'slides',
    lines: [2],
    theme: 'light',
    build(root) {
      const deck = mk('div', 'deck', root);
      const titles = ['STRATEGIE 2030', 'ROADMAP ZUR ROADMAP', 'VISION v12 (FINAL)', 'SYNERGIEN', 'NEXT STEPS: TBD', 'STRATEGIE 2031'];
      const slides = titles.map((ti, i) => {
        const s = mk('div', 'slide', deck);
        mk('div', 'slide-t', s, ti);
        for (let k = 0; k < 4; k++) mk('div', 'slide-b', s);
        mk('div', 'slide-n mono', s, `${i + 1} / 214`);
        return s;
      });
      const up = lyrics(root, [2], 'top big');
      const b0 = Math.ceil(beatAt(T0(2) - 0.4));
      return (c) => {
        up(c.t, c.pulse);
        const idx = Math.max(0, Math.min(slides.length - 1, Math.floor(beatAt(c.t) - b0)));
        slides.forEach((s, i) => {
          s.style.display = i === idx ? 'block' : 'none';
        });
        const ph = beatAt(c.t) % 1;
        deck.style.transform = `rotate(-2deg) translateX(${((1 - easeOut(clamp01(ph * 4))) * 30).toFixed(1)}px)`;
      };
    },
  },
  {
    id: 'amphetamines',
    lines: [3],
    theme: 'dark',
    build(root) {
      label(root, 'FUTURE / TIME', 'Δ ∞');
      const chart = svg(root, 'exp-chart', '0 0 1000 500', '<path class="axis" d="M60 460 H960 M60 460 V30"/><path class="curve" d=""/>');
      const curve = chart.querySelector<SVGPathElement>('.curve')!;
      const num = mk('div', 'race mono', root);
      const up = lyrics(root, [3], 'top big glitchy');
      return (c) => {
        up(c.t, c.pulse);
        const k = prog(c.t, T0(3) - 0.3, E(3));
        let d = '';
        for (let i = 0; i <= 60; i++) {
          const x = i / 60;
          if (x > k) break;
          const y = Math.pow(x, 6) * 520;
          d += `${i ? 'L' : 'M'}${(60 + x * 900).toFixed(1)} ${(460 - Math.min(480, y)).toFixed(1)}`;
        }
        curve.setAttribute('d', d);
        num.textContent = `${Math.floor(Math.pow(10, 2 + k * 9)).toLocaleString('de-DE')} TOKENS/S`;
        chart.style.transform = k > 0.7 ? `translate(${(Math.sin(c.t * 80) * 4).toFixed(1)}px, 0)` : '';
      };
    },
  },
  {
    id: 'split',
    lines: [4, 5],
    theme: 'dark',
    build(root) {
      const left = mk('div', 'half sv', root);
      const right = mk('div', 'half eu', root);
      mk('div', 'half-tag mono', left, 'SILICON VALLEY');
      mk('div', 'half-tag mono', right, 'EUROPA');
      const ship = mk('div', 'ship', left);
      const shipBar = mk('div', 'ship-f', ship);
      const shipTxt = mk('div', 'ship-t mono', left);
      const form = mk('div', 'form', right);
      mk('div', 'form-h mono', form, 'ANTRAG NR. 2031/000001');
      ['Vorhaben', 'Risikoklasse', 'Folgenabschätzung', 'Stellungnahme'].forEach((x) => {
        const r = mk('div', 'form-r', form);
        mk('span', 'mono', r, x);
        mk('span', 'form-line', r);
      });
      const spin = mk('div', 'spinner', right);
      const st = mk('div', 'stamp-red', right, 'IN PRÜFUNG');
      const upL = lyrics(left, [4], 'in-half');
      const upR = lyrics(right, [5], 'in-half');
      return (c) => {
        upL(c.t, c.pulse);
        upR(c.t, c.pulse);
        const k = easeOut(prog(c.t, W(4, 3), W(4, 4) + 0.4));
        shipBar.style.width = `${(k * 100).toFixed(1)}%`;
        shipTxt.textContent = k < 1 ? `DEPLOYING… ${(k * 100).toFixed(0)}%` : 'SHIPPED ✓';
        spin.style.transform = `rotate(${(c.t * 360) % 360}deg)`;
        stamp(st, c.t, W(5, 4), 2.4, -8);
      };
    },
  },
  {
    id: 'committees',
    lines: [6],
    theme: 'light',
    build(root) {
      label(root, 'VERFAHREN · TRILOG', 'STATUS: LAUFEND');
      const row = mk('div', 'committees', root);
      const boxes = ['AUSSCHUSS A', 'AUSSCHUSS B', 'AUSSCHUSS C', 'AUSSCHUSS D', 'AUSSCHUSS E'].map((n) => mk('div', 'cbox mono', row, n));
      const lines = svg(root, 'clines', '0 0 1000 300', Array.from({ length: 5 }, (_, i) => `<path d="M${100 + i * 200} 0 C ${100 + i * 200} 150, 500 120, 500 300"/>`).join(''));
      const report = mk('div', 'report', root);
      mk('div', 'report-t', report, 'BERICHT');
      mk('div', 'report-s mono', report, '1.248 Seiten · Entwurf 7');
      const up = lyrics(root, [6], 'top big');
      return (c) => {
        up(c.t, c.pulse);
        boxes.forEach((b, i) => popStyle(b, c.t, W(6, 0) + i * 0.12, 20, 0.2));
        lines.style.opacity = prog(c.t, W(6, 2), W(6, 3)).toFixed(2);
        const at = W(6, 4);
        const k = prog(c.t, at - 0.15, at);
        report.style.opacity = k > 0 ? '1' : '0';
        report.style.transform = `translateX(-50%) translateY(${((1 - easeOut(k)) * -500).toFixed(0)}px)`;
      };
    },
  },
  {
    id: 'never-sleeps',
    lines: [7],
    theme: 'dark',
    three: 'city',
    opts: { energy: 1 },
    build(root) {
      const clk = mk('div', 'clock247 mono', root, '24/7');
      const up = lyrics(root, [7], 'center huge');
      return (c) => {
        up(c.t, c.pulse);
        clk.style.opacity = (0.5 + 0.5 * c.pulse).toFixed(2);
      };
    },
  },

  // ======================= PRE-CHORUS =======================
  {
    id: 'caroline',
    lines: [8, 9],
    theme: 'dark',
    build(root) {
      const win = mk('div', 'window', root);
      const out = mk('div', 'win-out', win);
      svg(out, 'skyline far', '0 0 1280 300', SKYLINE);
      const sky = mk('div', 'win-sky', out);
      const drops = mk('div', 'win-drops', win);
      mk('div', 'win-frame', win);
      // Caroline: silhouette at the window
      svg(root, 'caroline', '0 0 200 400', '<path d="M66 64 q-26 34 -16 96 q4 34 -12 70 q30 12 62 -4 q32 16 62 4 q-16 -36 -12 -70 q10 -62 -16 -96 Z"/><ellipse cx="100" cy="66" rx="32" ry="38"/><path d="M50 160 q50 -24 100 0 l28 240 h-156 Z"/>');
      const up = lyrics(root, [8, 9], 'bottom big elegant', true);
      return (c) => {
        up(c.t, c.pulse);
        sky.style.opacity = (0.15 + 0.6 * prog(c.t, T0(9), E(9))).toFixed(3);
        drops.style.backgroundPositionY = `${(c.t * 120) % 600}px`;
        win.style.transform = `scale(${(1.02 + c.u * 0.06).toFixed(4)})`;
      };
    },
  },
  {
    id: 'yesterday',
    lines: [10, 11],
    theme: 'light',
    build(root) {
      const doc = mk('div', 'minutes', root);
      mk('div', 'min-h', doc, 'PROTOKOLL');
      const date = mk('div', 'min-date mono', doc);
      for (let i = 0; i < 6; i++) mk('div', 'min-l', doc);
      const up = lyrics(root, [10, 11], 'top big elegant');
      return (c) => {
        up(c.t, c.pulse);
        // the date of the meeting runs backwards
        const back = Math.floor(Math.max(0, c.t - T0(11)) * 6);
        const d = new Date(Date.UTC(2026, 9, 24 - back));
        date.textContent = `Sitzung vom ${d.toISOString().slice(0, 10).split('-').reverse().join('.')}`;
        popStyle(doc, c.t, T0(10) - 0.2, 40);
        doc.style.transform += ` rotate(-3deg)`;
      };
    },
  },

  // ======================= CHORUS 1 =======================
  {
    id: 'storm-1',
    lines: [12, 13, 14, 15, 16],
    theme: 'dark',
    three: 'storm',
    opts: { energy: 1 },
    build(root) {
      const year = mk('div', 'big-year', root, '2031');
      const ekg = svg(root, 'ekg', '0 0 1000 120', '<path class="ekg-line" d=""/>');
      const line = ekg.querySelector<SVGPathElement>('.ekg-line')!;
      const up = lyrics(root, [12, 13, 14, 15, 16], 'center huge', true, { 14: { held: 'survive1' } });
      return (c) => chorusOverlay(c, up, year, line, 15, 16);
    },
  },
  {
    id: 'hey-1',
    lines: [17, 18, 19, 20],
    theme: 'dark',
    build(root) {
      return heyScene(root, [17, 18, 19, 20]);
    },
  },

  // ======================= VERSE 2 =======================
  {
    id: 'golden-gate',
    lines: [21],
    theme: 'dark',
    build(root) {
      const sky = mk('div', 'sunset', root);
      svg(sky, 'bridge', '0 0 1280 400', `
        <path class="tower" d="M300 400 V60 h24 V400 Z M300 120 h24 M300 200 h24"/>
        <path class="tower" d="M900 400 V60 h24 V400 Z"/>
        <path class="cable" d="M0 210 Q312 40 312 60 Q612 300 912 60 Q912 40 1280 210"/>
        <path class="deck" d="M0 280 H1280 V296 H0 Z"/>
        ${Array.from({ length: 30 }, (_, i) => `<path class="hanger" d="M${i * 44} 280 V${210 - Math.sin((i / 30) * Math.PI) * 0}"/>`).join('')}
        <path class="sea" d="M0 330 H1280 V400 H0 Z"/>`);
      const lap = mk('div', 'laptop-glow', root);
      const up = lyrics(root, [21], 'top big');
      return (c) => {
        up(c.t, c.pulse);
        sky.style.transform = `scale(${(1.05 - c.u * 0.05).toFixed(4)})`;
        lap.style.opacity = (0.5 + 0.3 * c.pulse).toFixed(2);
      };
    },
  },
  {
    id: 'ai-code',
    lines: [22],
    theme: 'dark',
    build(root) {
      label(root, 'EDITOR · agent.ts', 'AI · AUTOCOMPLETE');
      const ed = mk('div', 'editor mono', root);
      const src = [
        'export async function shipFeature(spec: Spec) {',
        '  const plan = await agent.plan(spec);',
        '  for (const step of plan.steps) {',
        '    const code = await agent.write(step);',
        '    await tests.run(code);',
        '    await git.commit(code, step.title);',
        '  }',
        '  return deploy({ region: "everywhere" });',
        '}',
      ];
      const counter = mk('div', 'loc mono', root);
      const up = lyrics(root, [22], 'top big');
      return (c) => {
        up(c.t, c.pulse);
        const k = prog(c.t, T0(22) - 0.5, E(22) + 0.2);
        const chars = Math.floor(k * src.join('\n').length);
        let n = 0;
        ed.innerHTML = '';
        src.forEach((l, i) => {
          const row = mk('div', 'ed-row', ed);
          mk('span', 'ed-n', row, String(i + 1).padStart(2, ' '));
          const shown = l.slice(0, Math.max(0, chars - n));
          mk('span', '', row, shown);
          if (shown.length < l.length && chars - n >= 0) mk('span', 'ghost', row, l.slice(shown.length));
          n += l.length + 1;
        });
        counter.textContent = `${Math.floor(k * 48213).toLocaleString('de-DE')} lines today`;
      };
    },
  },
  {
    id: 'agents',
    lines: [23],
    theme: 'dark',
    build(root) {
      label(root, 'ORCHESTRATOR', 'AGENTS RUNNING');
      const field = mk('div', 'agents', root);
      const nodes: HTMLElement[] = [];
      for (let i = 0; i < 31; i++) {
        const n = mk('div', 'agent mono', field, 'AGENT');
        const depth = Math.floor(Math.log2(i + 1));
        const idx = i + 1 - Math.pow(2, depth);
        const count = Math.pow(2, depth);
        n.style.left = `${((idx + 0.5) / count) * 100}%`;
        n.style.top = `${depth * 22}%`;
        nodes.push(n);
      }
      const tokens: HTMLElement[] = [];
      for (let i = 0; i < 40; i++) tokens.push(mk('div', 'tok mono', root, ['tok', 'en', '_by', ' to', 'ken', '▁AI', 'ent', '42'][i % 8]));
      const up = lyrics(root, [23], 'top big');
      return (c) => {
        up(c.t, c.pulse);
        nodes.forEach((n, i) => popStyle(n, c.t, T0(23) - 0.2 + Math.floor(Math.log2(i + 1)) * 0.45 + (i % 4) * 0.03, 10, 0.2));
        tokens.forEach((tk, i) => {
          const at = W(23, 3) + i * 0.03;
          const k = prog(c.t, at, at + 1.2);
          tk.style.opacity = k > 0 && k < 1 ? '1' : '0';
          tk.style.left = `${(5 + hash(i) * 90).toFixed(1)}%`;
          tk.style.top = `${(100 - k * 70).toFixed(1)}%`;
        });
      };
    },
  },
  {
    id: 'tablet',
    lines: [24],
    theme: 'dark',
    build(root) {
      const tab = mk('div', 'tablet', root);
      const shards: HTMLElement[] = [];
      const polys = ['0 0, 55% 0, 40% 45%, 0 60%', '55% 0, 100% 0, 100% 40%, 40% 45%', '0 60%, 40% 45%, 50% 100%, 0 100%', '40% 45%, 100% 40%, 100% 100%, 50% 100%'];
      polys.forEach((p) => {
        const s = mk('div', 'shard', tab);
        s.style.clipPath = `polygon(${p})`;
        mk('div', 'tab-t', s, 'GEWISSHEITEN');
        mk('div', 'tab-s', s, 'I · Wohlstand ist sicher\nII · Wir sind vorne\nIII · Das bleibt so');
        shards.push(s);
      });
      const crack = svg(tab, 'crack', '0 0 100 100', '<path d="M55 0 L48 22 L40 45 L52 64 L50 100 M40 45 L70 42 L100 40"/>');
      const up = lyrics(root, [24], 'top big');
      return (c) => {
        up(c.t, c.pulse);
        const at = W(24, 3);
        crack.style.opacity = c.t > W(24, 2) ? '1' : '0';
        const k = prog(c.t, at, at + 1.4);
        shards.forEach((s, i) => {
          const dx = [-1, 1, -1, 1][i] * k * 120;
          const dy = k * k * 600 * (0.6 + i * 0.15);
          s.style.transform = `translate(${dx.toFixed(1)}px, ${dy.toFixed(1)}px) rotate(${(k * [-25, 30, -15, 20][i]).toFixed(1)}deg)`;
        });
      };
    },
  },
  {
    id: 'bubble',
    lines: [25],
    theme: 'light',
    build(root) {
      label(root, 'KONFERENZRAUM 4.12', 'BELEGT');
      const table = mk('div', 'table-top', root);
      const seats: HTMLElement[] = [];
      for (let i = 0; i < 10; i++) {
        const s = mk('div', 'seat', table);
        const a = (i / 10) * Math.PI * 2;
        s.style.left = `${50 + Math.cos(a) * 46}%`;
        s.style.top = `${50 + Math.sin(a) * 40}%`;
        seats.push(s);
      }
      const bubbles = seats.map((s, i) => {
        const b = mk('div', 'say', root, 'BUBBLE!');
        b.style.left = `calc(${s.style.left} * 0.5 + 25% )`;
        b.style.top = `calc(${s.style.top} * 0.55 + 28% )`;
        b.style.fontSize = `${1.2 + hash(i) * 1.4}vw`;
        return b;
      });
      const soap = mk('div', 'soap', root);
      const up = lyrics(root, [25], 'top big');
      return (c) => {
        up(c.t, c.pulse);
        bubbles.forEach((b, i) => popStyle(b, c.t, W(25, 0) + i * 0.13, 10, 0.18));
        const k = prog(c.t, T0(25), E(25) - 0.2);
        const popped = c.t > E(25) - 0.2;
        soap.style.opacity = popped ? (1 - prog(c.t, E(25) - 0.2, E(25))).toFixed(2) : '0.9';
        soap.style.transform = `translate(-50%, -50%) scale(${(0.3 + k * 1.2 + (popped ? 0.6 : 0)).toFixed(3)})`;
      };
    },
  },
  {
    id: 'dream',
    lines: [26],
    theme: 'dark',
    build(root) {
      const tree = svg(root, 'dream-tree', '0 0 600 600', `
        <path class="trunk" d="M300 600 C300 480 290 420 300 340"/>
        <path class="branch" d="M300 420 C260 380 220 360 180 300"/>
        <path class="branch" d="M300 400 C340 360 380 340 430 280"/>
        <path class="branch" d="M300 340 C300 280 300 240 300 170"/>
        <path class="branch" d="M180 300 C150 260 140 230 130 190"/>
        <path class="branch" d="M430 280 C470 240 480 210 490 170"/>
        ${[[180, 300], [430, 280], [300, 170], [130, 190], [490, 170], [240, 240], [360, 230]].map(([x, y], i) => `<circle class="leaf" data-i="${i}" cx="${x}" cy="${y}" r="14"/>`).join('')}`);
      const paths = [...tree.querySelectorAll<SVGPathElement>('path')];
      const leaves = [...tree.querySelectorAll<SVGCircleElement>('.leaf')];
      const up = lyrics(root, [26], 'top big');
      return (c) => {
        up(c.t, c.pulse);
        const k = prog(c.t, T0(26) - 0.3, E(26));
        paths.forEach((p, i) => {
          p.style.strokeDasharray = '600';
          p.style.strokeDashoffset = String(600 * (1 - clamp01(k * 2 - i * 0.18)));
        });
        leaves.forEach((l, i) => {
          const on = k > 0.55 + i * 0.05;
          l.style.opacity = on ? '1' : '0';
          l.setAttribute('r', String(on ? 10 + c.pulse * 6 : 0));
        });
      };
    },
  },
  {
    id: 'geopolitics',
    lines: [27],
    theme: 'dark',
    three: 'globe',
    build(root) {
      const words = ['COMPUTE', 'CAPITAL', 'ENERGY'].map((w, i) => {
        const e = mk('div', 'steel', root, w);
        e.style.top = `${16 + i * 17}%`;
        return e;
      });
      const up = lyrics(root, [27], 'bottom big');
      return (c) => {
        up(c.t, c.pulse);
        words.forEach((w, i) => stamp(w, c.t, W(27, i), 2.4, -4 + i * 3));
      };
    },
  },

  // ======================= SPOKEN PART =======================
  {
    id: 'newsflash',
    lines: [],
    start: textDone(27) + READ_HOLD,
    theme: 'dark',
    build(root) {
      const bn = mk('div', 'breaking', root);
      mk('div', 'brk-a', bn, 'EILMELDUNG');
      mk('div', 'brk-b', bn, 'EUROPA 2031 · SONDERSENDUNG');
      const tick = mk('div', 'ticker mono', root);
      tick.textContent = '+++ KI-ZENTREN ENTSTEHEN WELTWEIT +++ EUROPA BILDET ARBEITSGRUPPE +++ GRÜNDER BUCHEN FLÜGE +++ AUSSCHUSS TAGT +++ '.repeat(3);
      const up = lyrics(root, [57], 'news-lyr');
      return (c) => {
        up(c.t, c.pulse);
        popStyle(bn, c.t, L[27].e + 0.3, 0, 0.2);
        tick.style.transform = `translateX(${(-c.local * 220).toFixed(0)}px)`;
        bn.style.filter = Math.floor(c.t * 4) % 2 ? 'brightness(1.25)' : 'none';
      };
    },
  },
  {
    id: 'gala',
    lines: [28, 29],
    start: textDone(57) + READ_HOLD,
    theme: 'dark',
    build(root) {
      const stage = mk('div', 'gala', root);
      const cl = mk('div', 'curtain l', stage);
      const cr = mk('div', 'curtain r', stage);
      const spot = mk('div', 'spot', stage);
      svg(stage, 'mic', '0 0 100 300', '<rect x="44" y="60" width="12" height="230" rx="4"/><ellipse cx="50" cy="40" rx="20" ry="30"/>');
      const up = lyrics(root, [28, 29], 'bottom big elegant');
      return (c) => {
        up(c.t, c.pulse);
        const k = easeInOut(prog(c.t, T0(28) - 0.6, T0(28) + 1.2));
        cl.style.transform = `translateX(${(-k * 85).toFixed(1)}%)`;
        cr.style.transform = `translateX(${(k * 85).toFixed(1)}%)`;
        spot.style.opacity = (k * (0.8 + 0.2 * c.pulse)).toFixed(2);
      };
    },
  },
  {
    id: 'menu',
    lines: [30, 31],
    theme: 'light',
    build(root) {
      const card = mk('div', 'menu-card', root);
      mk('div', 'menu-h', card, 'Spezialität des Hauses');
      mk('div', 'menu-s', card, 'Europäisches Menü in vier Gängen');
      const courses = [
        ['I.', 'Regulieren', 'an Folgenabschätzung', W(30, 1)],
        ['II.', 'Analysieren', 'auf Arbeitsgruppen-Bett', W(30, 3)],
        ['III.', 'Evaluieren', 'mit Zwischenbericht', W(31, 1)],
        ['IV.', 'Diskutieren', 'open end', W(31, 3)],
      ] as const;
      const rows = courses.map(([n, a, b]) => {
        const r = mk('div', 'course', card);
        mk('span', 'c-n', r, n);
        const tx = mk('span', 'c-t', r);
        mk('b', '', tx, a);
        mk('i', '', tx, ' ' + b);
        mk('span', 'c-p mono', r, '€€€');
        return r;
      });
      const up = lyrics(root, [30, 31], 'top big', true);
      return (c) => {
        up(c.t, c.pulse);
        rows.forEach((r, i) => slideIn(r, c.t, courses[i][3] - 0.05, 20, 0.25));
        popStyle(card, c.t, T0(30) - 0.5, 40);
      };
    },
  },
  {
    id: 'airport',
    lines: [32, 33],
    theme: 'dark',
    build(root) {
      const board = mk('div', 'board', root);
      mk('div', 'board-h mono', board, 'ABFLUG · DEPARTURES');
      const flights = [
        ['LH 0458', 'SAN FRANCISCO', 'GRÜNDER', 'BOARDING'],
        ['UA 0901', 'AUSTIN', 'GRÜNDER', 'BOARDING'],
        ['SQ 0025', 'SINGAPUR', 'GRÜNDERIN', 'GATE B42'],
        ['EK 0046', 'DUBAI', 'GRÜNDER', 'BOARDING'],
        ['DL 0107', 'NEW YORK', 'GRÜNDERIN', 'GATE A12'],
        ['NH 0204', 'TOKIO', 'GRÜNDER', 'BOARDING'],
      ];
      const rows = flights.map((f) => {
        const r = mk('div', 'flight mono', board);
        return f.map((x) => mk('span', 'flap', r, x));
      });
      const up = lyrics(root, [32, 33], 'top big', true);
      const CH = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 ';
      return (c) => {
        up(c.t, c.pulse);
        rows.forEach((cells, i) => {
          cells.forEach((cell, k) => {
            const text = flights[i][k];
            const settle = T0(32) + i * 0.35 + k * 0.08;
            if (c.t >= settle) cell.textContent = text;
            else cell.textContent = [...text].map((_, j) => CH[Math.floor(hash(Math.floor(c.t * 20) + i * 13 + j + k) * CH.length)]).join('');
          });
          cells[3].classList.toggle('blink', flights[i][3] === 'BOARDING' && Math.floor(c.t * 2) % 2 === 0);
        });
      };
    },
  },

  // ======================= CHORUS 2 =======================
  {
    id: 'storm-2',
    lines: [34, 35, 36, 37, 38],
    theme: 'dark',
    three: 'storm',
    opts: { energy: 1, scatter: 1 },
    build(root) {
      const year = mk('div', 'big-year', root, '2031');
      const ekg = svg(root, 'ekg', '0 0 1000 120', '<path class="ekg-line" d=""/>');
      const line = ekg.querySelector<SVGPathElement>('.ekg-line')!;
      const up = lyrics(root, [34, 35, 36, 37, 38], 'center huge', true, { 36: { held: 'survive2' } });
      return (c) => chorusOverlay(c, up, year, line, 37, 38);
    },
  },
  {
    id: 'hey-2',
    lines: [39, 40, 41, 42],
    theme: 'dark',
    build(root) {
      return heyScene(root, [39, 40, 41, 42]);
    },
  },

  // ======================= BRIDGE =======================
  {
    id: 'no-drama',
    lines: [43, 44],
    theme: 'dark',
    build(root) {
      const hz = mk('div', 'horizon', root);
      const up = lyrics(root, [43, 44], 'center quiet');
      return (c) => {
        up(c.t, 0);
        hz.style.transform = `scaleX(${easeOut(prog(c.t, T0(43) - 0.5, T0(44))).toFixed(3)})`;
      };
    },
  },
  {
    id: 'question',
    lines: [45],
    theme: 'dark',
    build(root) {
      const q = svg(root, 'qmark', '0 0 200 300', '<path d="M50 90 C50 30 150 30 150 90 C150 140 100 140 100 190 V210"/><circle cx="100" cy="255" r="12"/>');
      const path = q.querySelector<SVGPathElement>('path')!;
      const dot = q.querySelector<SVGCircleElement>('circle')!;
      const up = lyrics(root, [45], 'bottom big');
      return (c) => {
        up(c.t, c.pulse);
        const k = prog(c.t, T0(45) - 0.3, E(45));
        path.style.strokeDasharray = '400';
        path.style.strokeDashoffset = String(400 * (1 - easeOut(k)));
        dot.style.opacity = k >= 1 ? '1' : '0';
      };
    },
  },
  {
    id: 'revolution',
    lines: [46, 47],
    theme: 'light',
    build(root) {
      label(root, 'INDUSTRIELLE REVOLUTIONEN', '1784 – 2031');
      const tl = mk('div', 'timeline', root);
      const evs = [
        ['1784', 'DAMPF'],
        ['1870', 'STROM'],
        ['1969', 'COMPUTER'],
        ['2031', 'KI'],
      ].map(([y, n], i) => {
        const e = mk('div', `tl-ev${i === 3 ? ' now' : ''}`, tl);
        mk('div', 'tl-y mono', e, y);
        mk('div', 'tl-n', e, n);
        return e;
      });
      const chair = mk('div', 'chair-wrap', root);
      svg(chair, 'chair', '0 0 200 220', '<path d="M50 20 h100 v110 h-100 Z M40 130 h120 v14 h-120 Z M50 144 v70 M150 144 v70"/>');
      mk('div', 'nameplate', chair, 'EUROPA');
      const up = lyrics(root, [46, 47], 'top big', true);
      return (c) => {
        up(c.t, c.pulse);
        evs.forEach((e, i) => slideIn(e, c.t, T0(46) + i * 0.6, 20));
        popStyle(chair, c.t, W(47, 2), 30);
        chair.style.opacity = c.t < W(47, 2) ? '0' : (0.6 + 0.4 * Math.abs(Math.sin(c.t * 2))).toFixed(2);
      };
    },
  },
  {
    id: 'rules',
    lines: [48],
    theme: 'light',
    build(root) {
      const book = mk('div', 'rulebook', root);
      mk('div', 'rb-h', book, 'THE RULES');
      for (let i = 0; i < 7; i++) mk('div', 'rb-l', book);
      const sig = mk('div', 'rb-sig mono', book, 'written by: ______________');
      svg(root, 'pen', '0 0 60 300', '<path d="M30 0 L44 40 V250 L30 300 L16 250 V40 Z"/>');
      const up = lyrics(root, [48], 'top big');
      return (c) => {
        up(c.t, c.pulse);
        popStyle(book, c.t, T0(48) - 0.4, 30);
        sig.style.opacity = c.t > W(48, 3) ? '1' : '0.25';
      };
    },
  },

  // ======================= FINAL CHORUS =======================
  {
    id: 'light-1',
    lines: [49, 50],
    theme: 'dark',
    three: 'storm',
    opts: { energy: 1, light: 1 },
    build(root) {
      const up = lyrics(root, [49, 50], 'center huge', true);
      return (c) => up(c.t, c.pulse);
    },
  },
  {
    id: 'light-2',
    lines: [51, 52],
    theme: 'dark',
    three: 'storm',
    opts: { energy: 1.4, light: 1 },
    build(root) {
      const up = lyrics(root, [51, 52], 'center huge', true, { 52: { held: 'dance' } });
      return (c) => up(c.t, c.pulse);
    },
  },
  {
    id: 'hey-3',
    lines: [53],
    theme: 'dark',
    build(root) {
      return heyScene(root, [53]);
    },
  },
  {
    id: 'no-more',
    lines: [54],
    theme: 'light',
    build(root) {
      const m = mk('div', 'nomore maybe', root, 'MAYBE');
      const l = mk('div', 'nomore later', root, 'LATER');
      const s1 = mk('div', 'strike', m);
      const s2 = mk('div', 'strike', l);
      const up = lyrics(root, [54], 'top big');
      return (c) => {
        up(c.t, c.pulse);
        stamp(m, c.t, W(54, 2), 1.8, -5);
        stamp(l, c.t, W(54, 5), 1.8, 4);
        s1.style.transform = `scaleX(${easeOut(prog(c.t, W(54, 2) + 0.35, W(54, 2) + 0.6)).toFixed(3)}) rotate(-4deg)`;
        s2.style.transform = `scaleX(${easeOut(prog(c.t, W(54, 5) + 0.35, W(54, 5) + 0.6)).toFixed(3)}) rotate(3deg)`;
      };
    },
  },
  {
    id: 'shutter',
    lines: [55, 56],
    theme: 'dark',
    build(root) {
      const odo = mk('div', 'odometer', root);
      // four rolling digits; each strip holds 0–9 twice so 9 → 0 can keep rolling forward
      const digits = [...'2026'].map(() => {
        const d = mk('div', 'odo-d', odo);
        const strip = mk('div', 'odo-strip', d);
        for (let k = 0; k < 20; k++) mk('div', 'odo-n', strip, String(k % 10));
        return strip;
      });
      const up = lyrics(root, [55, 56], 'bottom big', true);
      const sh = mk('div', 'shutter', root);
      for (let i = 0; i < 18; i++) mk('div', 'slat', sh);
      const stencil = mk('div', 'stencil', sh, 'COMFORT ZONE');
      const sub = mk('div', 'stencil-sub mono', sh, 'GESCHLOSSEN · EUROPA 2031');
      // finale: impact sparks + dust, spray-paint nozzle, warning beacon, stars burning through the steel
      const sparks = Array.from({ length: 80 }, () => mk('div', 'impact-spark', root));
      const dust = Array.from({ length: 9 }, () => mk('div', 'impact-dust', root));
      const nozzle = mk('div', 'spray-cloud', sh);
      const drips = Array.from({ length: 26 }, () => mk('div', 'spray-dot', sh));
      const beam = mk('div', 'beacon-sweep', sh);
      const beacon = mk('div', 'beacon', sh);
      const glow = mk('div', 'burn-glow', root);
      const ring = svg(root, 'burn-ring', '0 0 200 200', starRing(80, 11));
      const burn = [...ring.querySelectorAll<SVGElement>('.st')];
      const fade = mk('div', 'fade', root);
      const SLAM = E(56) - 0.2; // the shutter crashes down on the big hit right at the end of the last line
      return (c) => {
        up(c.t, c.pulse);
        // year counter rolls 2026 → 2031 on "2031 is coming"
        const k = easeInOut(prog(c.t, T0(55), E(55)));
        const ones = 6 + k * 5; // 6 → 11 (= 1 of 2031)
        const tens = 2 + clamp01(ones - 9); // 2 → 3 while the ones roll from 9 to 0
        [2, 0, tens, ones].forEach((v, i) => (digits[i].style.transform = `translateY(${(-v * 5).toFixed(3)}%)`));
        odo.style.transform = `translate(-50%, -50%) scale(${(1 + 0.04 * c.pulse).toFixed(3)})`;
        // steel roller shutter slams down, then the stencil holds through the outro and breathes with the beat
        const s = prog(c.t, SLAM - 0.5, SLAM);
        const y = s < 1 ? -100 + 100 * Math.pow(s, 2.2) : Math.sin(Math.min(1, (c.t - SLAM) * 6) * Math.PI) * -2.5;
        sh.style.transform = `translateY(${y.toFixed(2)}%)`;
        const af = c.t - SLAM; // seconds since impact
        // 1) impact: sparks fly from the bottom edge, dust rolls out
        sparks.forEach((sp, i) => {
          const life = 0.9 + hash(i * 3 + 1) * 0.7;
          const k = af / life;
          if (af < 0 || k > 1) {
            sp.style.opacity = '0';
            return;
          }
          const vx = (hash(i + 5) - 0.5) * 90;
          const vy = 25 + hash(i * 7 + 2) * 55;
          sp.style.left = `${(5 + hash(i * 11 + 3) * 90 + vx * af * 0.5).toFixed(2)}vw`;
          sp.style.top = `${(99 - vy * af + 70 * af * af).toFixed(2)}vh`;
          sp.style.opacity = (1 - k).toFixed(2);
        });
        dust.forEach((d, i) => {
          const k = clamp01(af / 2.2);
          d.style.opacity = af < 0 ? '0' : ((1 - k) * 0.55).toFixed(2);
          d.style.left = `${(i * 12 - 8 + (hash(i + 40) - 0.5) * 30 * k).toFixed(1)}vw`;
          d.style.transform = `scale(${(0.4 + 1.6 * easeOut(k)).toFixed(3)})`;
        });
        // 2) the stencil gets spray-painted on, left to right
        const sp = clamp01((af - 0.5) / 1.7);
        stencil.style.opacity = sp > 0 ? '1' : '0';
        stencil.style.clipPath = `inset(-10% ${((1 - sp) * 100).toFixed(1)}% -10% 0)`;
        // once the stars start, the stencil shrinks into the middle of the ring
        const sk = easeInOut(clamp01((af - 2.6) / 1.0));
        stencil.style.transform = `translateY(${(sk * 6).toFixed(2)}vh) scale(${(1 - 0.42 * sk + (sp >= 1 ? 0.025 * c.pulse : 0)).toFixed(3)})`;
        sub.style.translate = `0 ${(-sk * 3).toFixed(2)}vh`;
        sub.style.scale = `${(1 - 0.25 * sk).toFixed(3)}`;
        const edge = 12 + sp * 76; // vw, where the nozzle is
        const spraying = sp > 0 && sp < 1;
        const fr = Math.floor(c.t * 25);
        nozzle.style.opacity = spraying ? '0.9' : '0';
        nozzle.style.left = `${edge.toFixed(1)}vw`;
        nozzle.style.top = `${(40 + Math.sin(c.t * 40) * 1.5).toFixed(2)}%`;
        drips.forEach((dr, i) => {
          dr.style.opacity = spraying ? (0.4 + hash(i + fr * 31) * 0.6).toFixed(2) : '0';
          dr.style.left = `${(edge + (hash(i * 5 + fr * 17) - 0.5) * 7).toFixed(2)}vw`;
          dr.style.top = `${(40 + (hash(i * 9 + fr * 13) - 0.5) * 20).toFixed(2)}%`;
        });
        slideIn(sub, c.t, SLAM + 2.3);
        // 3) a red warning beacon starts turning
        const bk = clamp01((af - 1.8) / 0.4);
        beacon.style.opacity = bk.toFixed(2);
        beacon.style.filter = `brightness(${(0.8 + 0.6 * Math.max(0, Math.cos(c.t * 3.84))).toFixed(2)})`;
        beam.style.opacity = (bk * (0.55 + 0.25 * c.pulse)).toFixed(2);
        beam.style.transform = `rotate(${((c.t * 220) % 360).toFixed(1)}deg)`;
        // 4) the twelve EU stars burn through the steel, one per beat, then glow gold
        const b0 = Math.ceil(beatAt(SLAM + 3.2));
        const out = clamp01((c.t - (SONG_END - 1.3)) / 1.0);
        burn.forEach((st, i) => {
          const at = timeAtBeat(b0 + i);
          const k = clamp01((c.t - at) / 0.5);
          st.style.opacity = (k > 0 ? 1 - out : 0).toFixed(3);
          st.style.fill = k < 1 ? `rgb(255, ${Math.round(90 + 114 * k)}, ${Math.round(20 * k)})` : '#ffcc00';
          st.style.filter = `drop-shadow(0 0 ${(3 + 6 * k + 4 * c.pulse).toFixed(1)}px rgba(255, ${Math.round(120 + 80 * k)}, 0, 0.95))`;
          st.style.transformOrigin = 'center';
          st.style.transformBox = 'fill-box';
          st.style.transform = `scale(${(0.3 + 0.7 * easeOut(k) + (k >= 1 ? 0.08 * c.pulse : 0)).toFixed(3)})`;
        });
        const lastAt = timeAtBeat(b0 + 11) + 0.5;
        const gk = c.t < lastAt ? 0 : Math.exp(-(c.t - lastAt) * 1.6);
        glow.style.opacity = (Math.max(gk, clamp01((c.t - lastAt) / 0.2) * 0.35) * (1 - out)).toFixed(3);
        glow.style.transform = `translate(-50%, -50%) scale(${(0.8 + 0.5 * (1 - gk)).toFixed(3)})`;
        ring.style.transform = `translate(-50%, -50%) scale(${(1 + 0.05 * gk).toFixed(3)}) rotate(${(Math.max(0, c.t - (SLAM + 3.2)) * 3).toFixed(2)}deg)`;
        // everything fades to black – the burning stars stay a moment longer
        fade.style.opacity = prog(c.t, SONG_END - 2.8, SONG_END - 1.3).toFixed(3);
      };
    },
  },
];

// ---------- shared scene pieces ----------
/** chorus overlays: giant glitching "2031" while it is sung, EKG for "are we still alive?" */
function chorusOverlay(c: Ctx, up: (t: number, p?: number) => void, year: HTMLElement, line: SVGPathElement, yearLine: number, aliveLine: number) {
  up(c.t, c.pulse);
  const yOn = c.t >= T0(yearLine) - 0.1 && c.t < T0(aliveLine) + 0.2;
  year.style.opacity = yOn ? (0.25 + 0.2 * c.pulse).toFixed(2) : '0';
  year.style.transform = `translate(-50%, -50%) scale(${(1 + 0.05 * c.pulse).toFixed(3)}) translateX(${(Math.sin(c.t * 60) * c.pulse * 6).toFixed(1)}px)`;
  const aOn = c.t >= T0(aliveLine) - 0.3;
  let d = '';
  const head = (c.t * 300) % 1000;
  for (let x = 0; x <= 1000; x += 10) {
    const ph = (x - head + 1000) % 250;
    const y = ph > 120 && ph < 160 ? 60 - Math.sin(((ph - 120) / 40) * Math.PI * 2) * 45 * (aOn ? 1 : 0) : 60;
    d += `${x ? 'L' : 'M'}${x} ${y.toFixed(1)}`;
  }
  line.setAttribute('d', d);
  (line.parentNode as SVGElement).style.opacity = aOn ? '1' : '0';
}

/** "HEY! HEY! HEY! WAKE UP, BABY!" – every word slammed full screen under a red alarm light */
function heyScene(root: HTMLElement, idx: number[]) {
  const beam = mk('div', 'alarm', root);
  const big = mk('div', 'hey-big', root);
  const up = lyrics(root, idx, 'bottom small-lyr', true);
  const words: { w: string; at: number }[] = [];
  idx.forEach((li) => L[li].text.split(' ').forEach((w, wi) => words.push({ w: w.replace(/[,.!]/g, ''), at: W(li, wi) })));
  return (c: Ctx) => {
    up(c.t, c.pulse);
    let cur = words[0];
    for (const w of words) if (c.t >= w.at - 0.03) cur = w;
    const age = c.t - cur.at;
    big.textContent = c.t >= words[0].at - 0.03 ? cur.w.toUpperCase() : '';
    const s = age < 0.09 ? 2.2 - 1.2 * easeOut(age / 0.09) : 1 + 0.05 * Math.exp(-(age - 0.09) * 8);
    big.style.transform = `translate(-50%, -50%) scale(${s.toFixed(3)}) rotate(${((hash(Math.floor(cur.at * 10)) - 0.5) * 8).toFixed(1)}deg)`;
    big.classList.toggle('red', /wake|baby|now/i.test(cur.w));
    beam.style.transform = `rotate(${((c.t * 300) % 360).toFixed(1)}deg)`;
    root.style.background = `rgba(${Math.floor(40 + 60 * Math.exp(-age * 6))}, 0, 4, 1)`;
  };
}

// ---------- timeline ----------
export interface Timed extends SceneDef {
  t0: number;
  t1: number;
}
export const TIMELINE: Timed[] = SCENES.map((s) => {
  if (s.start !== undefined) return { ...s, t0: s.start, t1: 0 };
  const f = s.lines[0];
  // ideally just before the first word appears – but only once the previous line is complete and was
  // readable for a moment; when the singer flows straight on, the cut may come up to 0.3 s after the first word
  const prevDone = f > 0 ? textDone(f - 1) + READ_HOLD : 0;
  const t0 = Math.min(L[f].t + 0.3, Math.max(L[f].t - 0.28, prevDone));
  return { ...s, t0, t1: 0 };
});
TIMELINE.forEach((s, i) => (s.t1 = i + 1 < TIMELINE.length ? TIMELINE[i + 1].t0 : SONG_END));
export const sceneAt = (t: number) => TIMELINE.find((s) => t >= s.t0 && t < s.t1) ?? TIMELINE[TIMELINE.length - 1];
