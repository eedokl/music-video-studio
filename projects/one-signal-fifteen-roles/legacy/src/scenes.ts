// "One Signal, Fifteen Roles" – scene timeline. One scene per role while it is sung,
// built from the content of the BST/ESW Roles page. Pure functions of song time.

import { LEAD, type LineOpts, SungLine } from './lyric';
import { LINES, SONG_END } from './lyrics';
import { FAMILIES, ROLE_ORDER, type Role, STAGES, SUNG, glow, img, role } from './roles';
import { easeInOut, easeOut, easeOutBack, hash, mk, popStyle, prog, slideIn } from './util';
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
const W = (li: number, wi: number) => (L[li].words?.[wi] ?? L[li].t) - LEAD;
const T0 = (li: number) => L[li].t - LEAD;
const E = (li: number) => L[li].e - LEAD;
const clamp01 = (x: number) => Math.min(1, Math.max(0, x));
const SUPER = 'linear-gradient(90deg, #e0000a, #9e2896 25%, #007bc0 50%, #18837e 75%, #00884a)';

// ---------- building blocks ----------
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
    box.style.setProperty('--bump', (1 + 0.07 * pulse * singing).toFixed(4));
  };
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

/** role icon (the page's line icon), recoloured to the family colour via a CSS mask */
function icon(parent: HTMLElement, r: Role, cls = 'icon') {
  const e = mk('div', cls, parent);
  e.style.setProperty('--icon', `url("${img(r.icon)}")`);
  e.style.setProperty('--fc', glow(r.family));
  return e;
}

/** the signal chain (6 stages + enablers) with the role's stages lit */
function chain(parent: HTMLElement, lit: string[], color: string) {
  const bar = mk('div', 'chain', parent);
  const nodes = STAGES.map((s, i) => {
    const n = mk('div', `stage${lit.includes(s.id) ? ' lit' : ''}`, bar);
    mk('span', 'st-n', n, String(i + 1));
    mk('span', 'st-l', n, s.label);
    return n;
  });
  const en = mk('div', `stage enabler${lit.includes('enabler') ? ' lit' : ''}`, bar);
  mk('span', 'st-l', en, 'Enablers');
  bar.style.setProperty('--fc', color);
  const pulseDot = mk('div', 'chain-pulse', bar);
  return (t: number) => {
    pulseDot.style.left = `${((t * 0.35) % 1) * 100}%`;
    void nodes;
  };
}

// ---------- the role scene template ----------
type Visual = (area: HTMLElement, r: Role, li: number) => (c: Ctx, k: number) => void;

function roleScene(li: number, name: string, visual: Visual): SceneDef {
  const r = role(name);
  const n = ROLE_ORDER.indexOf(r) + 1;
  return {
    id: `role-${n}`,
    lines: [li],
    theme: 'dark',
    build(root) {
      const fc = glow(r.family);
      root.style.setProperty('--fc', fc);
      root.classList.add('role-scene');
      const ch = chain(root, r.stages, fc);
      const area = mk('div', 'visual', root);
      const vis = visual(area, r, li);
      const card = mk('div', 'card', root);
      mk('div', 'card-bar', card);
      const head = mk('div', 'card-head', card);
      icon(head, r);
      const meta = mk('div', 'card-meta', head);
      mk('div', 'eyebrow', meta, FAMILIES[r.family].label);
      mk('div', 'count mono', meta, `ROLE ${String(n).padStart(2, '0')} / 15`);
      mk('div', 'card-name', card, r.name);
      const quote = mk('div', 'card-quote', card, `“${r.quote}”`);
      const tasks = r.tasks.slice(0, 2).map((x) => mk('div', 'task', card, x));
      // the page's illustration: framed, dealt in like a card, drifting inside its frame, bumping on the beat
      const pic = mk('div', 'card-pic', card);
      const picImg = mk('img', 'pic-img', pic) as HTMLImageElement;
      picImg.src = img(r.illustration);
      const shine = mk('div', 'pic-shine', pic);
      const up = lyrics(root, [li], 'role-lyr');
      const a = T0(li) - 0.25;
      return (c) => {
        up(c.t, c.pulse);
        ch(c.t);
        const k = prog(c.t, T0(li), E(li) + 0.3);
        vis(c, k);
        const ck = easeOut(prog(c.t, a, a + 0.35));
        card.style.opacity = ck.toFixed(3);
        card.style.transform = `translateX(${((1 - ck) * 6).toFixed(2)}vw)`;
        slideIn(quote, c.t, a + 0.35, 12, 0.3);
        tasks.forEach((tk, i) => slideIn(tk, c.t, a + 0.8 + i * 0.35, 12, 0.3));
        // deal-in: flip from the side with a little bounce
        const pk = prog(c.t, a + 0.45, a + 0.95);
        const pe = easeOutBack(pk);
        const ph = c.beat - Math.floor(c.beat);
        const bump = pk >= 1 ? 1 + 0.07 * Math.exp(-ph * 6) : 1;
        const tilt = pk >= 1 ? Math.sin(c.beat * Math.PI) * 2.5 : 0;
        const floatY = Math.sin(c.t * 1.7) * 0.25;
        pic.style.opacity = pk > 0 ? '1' : '0';
        pic.style.transform = `perspective(60vw) translateY(${floatY.toFixed(2)}vw) rotateY(${((1 - pe) * -75).toFixed(1)}deg) rotate(${(tilt + (1 - pe) * 12).toFixed(2)}deg) scale(${(bump * (0.6 + 0.4 * pe)).toFixed(3)})`;
        // slow camera drift inside the frame
        const kb = prog(c.t, a, E(li) + 0.6);
        picImg.style.transform = `scale(${(1.08 + 0.18 * kb).toFixed(3)}) translate(${(-3 + 6 * kb).toFixed(2)}%, ${(2 - 4 * kb).toFixed(2)}%)`;
        // light glint when it lands and on every 4th beat
        const g1 = prog(c.t, a + 0.85, a + 1.35);
        const g2 = c.beat % 4 < 1 && pk >= 1 ? (c.beat % 4) : -1;
        const g = g1 > 0 && g1 < 1 ? g1 : g2 >= 0 ? g2 : -1;
        shine.style.opacity = g >= 0 ? '1' : '0';
        shine.style.transform = `translateX(${(-120 + 260 * Math.max(0, g)).toFixed(1)}%) skewX(-20deg)`;
        area.style.transform = `scale(${(1 + 0.012 * c.pulse).toFixed(4)})`;
      };
    },
  };
}

// ---------- per-role visuals (left side) ----------
const V: Record<string, Visual> = {
  // turn the noise into a sign
  dsp(area) {
    const s = svg(area, 'vis-svg', '0 0 600 300', '<text class="vt" x="20" y="34">raw accelerometer</text><text class="vt fc" x="20" y="34" opacity="0">filtered (DSP)</text><path class="wave" d=""/><path class="axis" d="M20 150 H580"/>');
    const p = s.querySelector<SVGPathElement>('.wave')!;
    const [raw, fil] = [...s.querySelectorAll<SVGTextElement>('.vt')];
    return (c, k) => {
      const f = easeInOut(clamp01(k * 1.5));
      let d = '';
      for (let x = 0; x <= 560; x += 4) {
        const clean = Math.sin(x / 40 - c.t * 3) * 70;
        const noise = (hash(x * 0.37 + Math.floor(c.t * 20)) - 0.5) * 140;
        d += `${x ? 'L' : 'M'}${20 + x} ${(150 - clean - noise * (1 - f)).toFixed(1)}`;
      }
      p.setAttribute('d', d);
      raw.setAttribute('opacity', (1 - f).toFixed(2));
      fil.setAttribute('opacity', f.toFixed(2));
    };
  },
  // squeeze it down, make it run in time
  embedded(area) {
    const s = svg(area, 'vis-svg', '0 0 600 300', `<rect class="chip" x="210" y="70" width="180" height="160" rx="10"/>${Array.from({ length: 6 }, (_, i) => `<path class="pin" d="M${230 + i * 28} 70 v-22 M${230 + i * 28} 230 v22 M210 ${90 + i * 24} h-22 M390 ${90 + i * 24} h22"/>`).join('')}<path class="wave" d=""/><text class="vt" x="300" y="160" text-anchor="middle">DSP</text>`);
    const p = s.querySelector<SVGPathElement>('.wave')!;
    const gauges = [['RAM', 64, 12, 'KB'], ['CPU', 80, 9, '%'], ['LATENCY', 12, 0.8, 'ms']].map(([n]) => mk('div', 'gauge mono', area, String(n)));
    return (c, k) => {
      const sq = easeInOut(clamp01(k * 1.3));
      const w = 560 - sq * 380;
      const x0 = 300 - w / 2;
      let d = '';
      for (let i = 0; i <= 80; i++) d += `${i ? 'L' : 'M'}${(x0 + (i / 80) * w).toFixed(1)} ${(150 - Math.sin(i / 6 - c.t * 4) * 50 * (1 - sq * 0.6)).toFixed(1)}`;
      p.setAttribute('d', d);
      const vals: [string, number, number, string][] = [['RAM', 64, 12, 'KB'], ['CPU', 80, 9, '%'], ['LATENCY', 12, 0.8, 'ms']];
      gauges.forEach((g, i) => {
        const [nm, a, b, u] = vals[i];
        const v = a + (b - a) * sq;
        g.textContent = `${nm}  ${v < 10 ? v.toFixed(1) : Math.round(v)} ${u}`;
        g.classList.toggle('ok', sq > 0.95);
      });
    };
  },
  // keep the pipelines flowing clean
  dataops(area) {
    const stages = ['COLLECT', 'CLEAN', 'STORE', 'DATASET'];
    const row = mk('div', 'pipe', area);
    stages.forEach((s) => mk('div', 'pipe-st mono', row, s));
    const packets = Array.from({ length: 14 }, () => mk('div', 'packet', area));
    const badge = mk('div', 'quality mono', area, 'DATA QUALITY ✓ 99.8 %');
    return (c, k) => {
      packets.forEach((p, i) => {
        const x = ((c.t * 0.35 + i / 14) % 1) * 100;
        p.style.left = `${x}%`;
        p.style.opacity = x < 30 && i % 4 === 0 ? '0.35' : '1';
        p.classList.toggle('dirty', x < 30 && i % 4 === 0);
      });
      badge.style.opacity = k > 0.5 ? '1' : '0';
    };
  },
  // put a brain in the machine
  eai(area) {
    const nodes: [number, number][] = [];
    const layers = [3, 5, 5, 2];
    layers.forEach((n, l) => {
      for (let i = 0; i < n; i++) nodes.push([210 + l * 60, 150 + (i - (n - 1) / 2) * 30]);
    });
    let lines = '';
    let off = 0;
    layers.slice(0, -1).forEach((n, l) => {
      for (let i = 0; i < n; i++) for (let j = 0; j < layers[l + 1]; j++) {
        const a = nodes[off + i];
        const b = nodes[off + n + j];
        lines += `<path class="syn" d="M${a[0]} ${a[1]} L${b[0]} ${b[1]}"/>`;
      }
      off += n;
    });
    const s = svg(area, 'vis-svg', '0 0 600 300', `<rect class="chip" x="180" y="40" width="240" height="220" rx="14"/>${lines}${nodes.map(([x, y], i) => `<circle class="neuron" data-i="${i}" cx="${x}" cy="${y}" r="9"/>`).join('')}<text class="vt" x="300" y="285" text-anchor="middle">on-device AI</text>`);
    const ns = [...s.querySelectorAll<SVGCircleElement>('.neuron')];
    const syn = [...s.querySelectorAll<SVGPathElement>('.syn')];
    const st = mk('div', 'status mono', area);
    return (c, k) => {
      ns.forEach((n, i) => n.classList.toggle('on', k * ns.length * 1.3 > i));
      syn.forEach((p, i) => p.classList.toggle('on', k > 0.3 && (Math.floor(c.t * 8) + i) % 5 === 0));
      st.textContent = k > 0.7 ? 'on-device AI: active · class = "walking"' : 'on-device AI: idle';
    };
  },
  // code that makes it learn
  cseai(area) {
    const ed = mk('div', 'mini-ed mono', area);
    const code = ['void infer(const int8_t* x) {', '  tflm::Invoke(model, x);', '  label = argmax(out);', '}', '// learning on the edge'];
    const s = svg(area, 'loss', '0 0 300 200', '<path class="axis" d="M20 180 H290 M20 180 V10"/><path class="curve" d=""/><text class="vt" x="200" y="30">loss</text>');
    const p = s.querySelector<SVGPathElement>('.curve')!;
    return (c, k) => {
      const chars = Math.floor(k * 1.4 * code.join('').length);
      let n = 0;
      ed.innerHTML = '';
      code.forEach((l) => {
        mk('div', '', ed, l.slice(0, Math.max(0, chars - n)));
        n += l.length;
      });
      let d = '';
      for (let i = 0; i <= 50 * k; i++) d += `${i ? 'L' : 'M'}${20 + i * 5.4} ${(180 - 160 * Math.exp(-i / 12) - 10 - (hash(i) - 0.5) * 12).toFixed(1)}`;
      p.setAttribute('d', d);
      void c;
    };
  },
  // draw the blueprint, every bit, every turn
  aiarch(area) {
    area.classList.add('blueprint');
    const s = svg(area, 'vis-svg', '0 0 600 300', `
      ${[['AI MODEL', 30], ['RUNTIME', 170], ['HAL', 310], ['SENSOR', 450]].map(([n, x]) => `<g><rect class="bp" x="${x}" y="110" width="120" height="70"/><text class="bpt" x="${Number(x) + 60}" y="151" text-anchor="middle">${n}</text></g>`).join('')}
      <path class="bp" d="M150 145 H170 M290 145 H310 M430 145 H450"/>
      <path class="bp" d="M90 110 V60 H510 V110"/><text class="bpt small" x="300" y="52" text-anchor="middle">memory · latency · power budget</text>`);
    const all = [...s.querySelectorAll<SVGElement>('.bp')];
    return (c, k) => {
      all.forEach((e, i) => {
        e.style.strokeDasharray = '700';
        e.style.strokeDashoffset = String(700 * (1 - clamp01(k * 2.2 - i * 0.12)));
      });
      void c;
    };
  },
  // build the frame that holds the weight
  swarch(area) {
    const layers = ['HARDWARE', 'DRIVERS', 'MIDDLEWARE', 'SERVICES', 'APPLICATION'].map((n, i) => {
      const e = mk('div', 'layer mono', area, n);
      e.style.bottom = `${8 + i * 17}%`;
      return e;
    });
    mk('div', 'pillar l', area);
    mk('div', 'pillar r', area);
    return (c, k) => {
      layers.forEach((e, i) => {
        const at = i / layers.length;
        const p = easeOutBack(clamp01((k * 1.3 - at) * 5));
        e.style.opacity = p > 0 ? '1' : '0';
        e.style.transform = `translateY(${((1 - p) * -120).toFixed(0)}%)`;
      });
      void c;
    };
  },
  // see tomorrow, push the concept, innovate
  csexpert(area) {
    const s = svg(area, 'vis-svg', '0 0 600 300', `
      <circle class="idea" cx="120" cy="150" r="42"/><text class="bpt" x="120" y="156" text-anchor="middle">IDEA</text>
      ${[['CONCEPT', 300, 80], ['ARCHITECTURE', 300, 220], ['TOMORROW', 500, 150]].map(([n, x, y]) => `<g class="node"><path class="link" d="M162 150 C230 150 ${Number(x) - 90} ${y} ${Number(x) - 60} ${y}"/><rect class="nbox" x="${Number(x) - 60}" y="${Number(y) - 22}" width="120" height="44" rx="22"/><text class="bpt" x="${x}" y="${Number(y) + 6}" text-anchor="middle">${n}</text></g>`).join('')}`);
    const nodes = [...s.querySelectorAll<SVGGElement>('.node')];
    const idea = s.querySelector<SVGCircleElement>('.idea')!;
    return (c, k) => {
      nodes.forEach((n, i) => (n.style.opacity = clamp01(k * 3 - i * 0.7).toFixed(2)));
      idea.setAttribute('r', String(42 + c.pulse * 8));
    };
  },
  // from prototype to production line
  alglead(area) {
    const proto = svg(area, 'proto', '0 0 200 140', '<rect x="5" y="5" width="190" height="130" rx="6" class="paper"/><path class="sketch" d="M15 90 C40 20 60 120 90 60 S140 40 185 80"/><text x="15" y="25" class="vt">prototype</text>');
    void proto;
    const belt = mk('div', 'belt', area);
    const boxes = Array.from({ length: 6 }, () => mk('div', 'box mono', area, '✓'));
    mk('div', 'belt-l mono', area, 'PRODUCTION LINE');
    return (c, k) => {
      belt.style.backgroundPositionX = `${(-c.t * 120) % 40}px`;
      boxes.forEach((b, i) => {
        const x = ((c.t * 0.25 + i / 6) % 1) * 100;
        b.style.left = `${8 + x * 0.84}%`;
        b.classList.toggle('done', x > 55);
        b.style.opacity = k > 0.15 ? '1' : '0';
      });
    };
  },
  // own the strategy, the frameworks, the design
  testarch(area) {
    const tiers = [['SYSTEM', 30], ['INTEGRATION', 60], ['UNIT', 90]].map(([n, w], i) => {
      const e = mk('div', 'tier mono', area, String(n));
      e.style.width = `${w}%`;
      e.style.top = `${16 + i * 24}%`;
      return e;
    });
    const fw = mk('div', 'fw mono', area, 'FRAMEWORK · CI/CD · STANDARDS');
    return (c, k) => {
      tiers.slice().reverse().forEach((e, i) => popStyle(e, c.t, c.t - k * 3 + i * 0.5, 20, 0.25));
      fw.style.opacity = k > 0.6 ? '1' : '0';
    };
  },
  // run it every night, catch every fall
  testeng(area) {
    mk('div', 'moon', area);
    mk('div', 'nightly mono', area, 'NIGHTLY RUN #2412');
    const grid = mk('div', 'tgrid', area);
    const cells = Array.from({ length: 48 }, () => mk('div', 'tc', grid));
    return (c, k) => {
      const n = Math.floor(k * 1.3 * cells.length);
      cells.forEach((cl, i) => {
        cl.className = 'tc' + (i < n ? (i === 29 && k < 0.85 ? ' fail' : ' pass') : '');
      });
      void c;
    };
  },
  // forge the tools that power us all
  tool(area) {
    const s = svg(area, 'vis-svg', '0 0 600 300', '<path class="anvil" d="M170 200 h260 l-40 30 h-180 Z M230 230 h140 v40 h-140 Z"/><g class="hammer"><rect x="300" y="60" width="16" height="130" rx="6" class="handle"/><rect x="262" y="40" width="92" height="44" rx="6" class="head"/></g>');
    const hammer = s.querySelector<SVGGElement>('.hammer')!;
    const sparks = Array.from({ length: 16 }, () => mk('div', 'spark', area));
    const tools = ['⚙', '🔧', '{ }', '▶'].map((x) => mk('div', 'toolchip', area, x));
    return (c, k) => {
      const ph = c.beat - Math.floor(c.beat);
      hammer.setAttribute('transform', `rotate(${(-35 + 35 * (1 - Math.min(1, ph * 3))).toFixed(1)} 308 190)`);
      sparks.forEach((sp, i) => {
        const a = (i / 16) * Math.PI - Math.PI;
        const r = ph * 160;
        sp.style.left = `calc(50% + ${(Math.cos(a) * r).toFixed(0)}px)`;
        sp.style.top = `calc(64% + ${(Math.sin(a) * r * 0.6 + ph * ph * 120).toFixed(0)}px)`;
        sp.style.opacity = (1 - ph).toFixed(2);
      });
      tools.forEach((tl, i) => popStyle(tl, c.t, c.t - k * 3.4 + 0.6 + i * 0.55, 20, 0.25));
    };
  },
  // servers, licenses, the backbone strong
  itmgr(area) {
    const rack = mk('div', 'rack', area);
    const leds: HTMLElement[] = [];
    for (let i = 0; i < 8; i++) {
      const u = mk('div', 'ru', rack);
      for (let j = 0; j < 4; j++) leds.push(mk('span', 'led', u));
    }
    const lic = mk('div', 'licenses mono', area);
    ['MATLAB ✓', 'COMPILER ✓', 'JENKINS ✓', 'JIRA ✓', 'GIT ✓'].forEach((x) => mk('div', 'lic', lic, x));
    const up = mk('div', 'uptime mono', area);
    return (c, k) => {
      leds.forEach((l, i) => l.classList.toggle('on', hash(i * 3 + Math.floor(c.t * 6)) > 0.35));
      [...lic.children].forEach((e, i) => slideIn(e as HTMLElement, c.t, c.t - k * 3.6 + 0.4 + i * 0.4, 10, 0.25));
      up.textContent = `UPTIME 99.9${Math.floor(k * 9)} %`;
    };
  },
  // set the vision, choose the way
  po(area) {
    mk('div', 'vision mono', area, '★ PRODUCT VISION');
    const items = ['Customer feature A', 'Tech debt', 'Feature B', 'Nice-to-have', 'Compliance'].map((x) => mk('div', 'bl mono', area, x));
    const order = [0, 4, 2, 1, 3];
    return (c, k) => {
      const kk = easeInOut(clamp01((k - 0.25) * 2));
      items.forEach((e, i) => {
        const pos = i + (order.indexOf(i) - i) * kk;
        e.style.top = `${26 + pos * 13}%`;
        e.classList.toggle('top', kk > 0.9 && order.indexOf(i) === 0);
      });
      void c;
    };
  },
  // clear the path, make the team play
  am(area) {
    const cols = ['TO DO', 'DOING', 'DONE'].map((n, i) => {
      const col = mk('div', 'kcol', area);
      col.style.left = `${4 + i * 32}%`;
      mk('div', 'kh mono', col, n);
      return col;
    });
    void cols;
    const cards = Array.from({ length: 5 }, (_, i) => mk('div', 'kcard', area, `Story ${i + 1}`));
    const blocker = mk('div', 'kcard blocker', area, 'BLOCKER');
    return (c, k) => {
      const gone = clamp01((k - 0.2) * 4);
      blocker.style.opacity = (1 - gone).toFixed(2);
      blocker.style.transform = `translate(${gone * 30}px, ${-gone * 60}px) rotate(${gone * 20}deg)`;
      cards.forEach((cd, i) => {
        const p = clamp01((k - 0.35 - i * 0.08) * 3);
        const col = p >= 1 ? 2 : p > 0 ? 1 : 0;
        cd.style.left = `${6 + col * 32}%`;
        cd.style.top = `${26 + i * 12}%`;
      });
      void c;
    };
  },
};

const VIS_FOR: Record<string, Visual> = {
  'DSP Engineer': V.dsp,
  'DSP Embedded Engineer': V.embedded,
  'DSP Data Operations Engineer': V.dataops,
  'Embedded AI Engineer': V.eai,
  'Computer Science Engineer': V.cseai,
  'Embedded AI Software Architect': V.aiarch,
  'Software Architect': V.swarch,
  'Computer Science Expert': V.csexpert,
  'Algorithm Technical Lead': V.alglead,
  'Software Test Automation Architect': V.testarch,
  'Software Test Automation Engineer': V.testeng,
  'Software Tool and Application Engineer': V.tool,
  'Software IT Manager': V.itmgr,
  'Product Owner': V.po,
  'Agile Master': V.am,
};
const roleScenes = (from: number, to: number) => SUNG.slice(from, to).map(([li, n]) => roleScene(li, n, VIS_FOR[n]));

// ---------- tiles of all 15 roles ----------
function mosaic(parent: HTMLElement, cls = '') {
  const g = mk('div', `mosaic ${cls}`, parent);
  return ROLE_ORDER.map((r) => {
    const tl = mk('div', 'tile', g);
    tl.style.setProperty('--fc', glow(r.family));
    icon(tl, r, 'icon small');
    mk('div', 'tile-n', tl, SUNG.find(([, n]) => role(n) === r)![2]);
    return tl;
  });
}

function chorusScene(id: string, idx: number[], held: Record<number, LineOpts>, variant: 'mosaic' | 'net' | 'final'): SceneDef {
  return {
    id,
    lines: idx,
    theme: 'dark',
    three: variant === 'net' ? 'network' : undefined,
    opts: variant === 'net' ? { vocal: 0, release: 0 } : undefined,
    build(root) {
      root.classList.add('chorus');
      const tiles = variant !== 'net' ? mosaic(root, variant) : [];
      const line = mk('div', 'signal-line', root);
      const conf = variant === 'final' ? Array.from({ length: 60 }, (_, i) => {
        const e = mk('div', 'confetti', root);
        e.style.background = ['#e0000a', '#9e2896', '#007bc0', '#18837e', '#00884a', '#ffffff'][i % 6];
        return e;
      }) : [];
      const up = lyrics(root, idx, 'center huge', true, held);
      const heyLine = idx.find((li) => /^Hey/.test(L[li].text));
      return (c) => {
        up(c.t, c.pulse);
        const b = Math.floor(c.beat);
        tiles.forEach((tl, i) => {
          const on = (b + i) % 5 === 0 || (heyLine !== undefined && c.t >= T0(heyLine) && c.t < E(heyLine) + 0.3);
          tl.classList.toggle('on', on);
          tl.style.transform = `scale(${(1 + (on ? 0.06 * c.pulse : 0)).toFixed(3)})`;
        });
        line.style.transform = `scaleX(${(0.3 + 0.7 * ((c.t * 0.5) % 1)).toFixed(3)})`;
        line.style.opacity = (0.5 + 0.5 * c.pulse).toFixed(2);
        conf.forEach((e, i) => {
          const y = ((c.local * (0.15 + hash(i) * 0.2) + hash(i * 3)) % 1.1) * 110 - 5;
          e.style.left = `${(hash(i * 7) * 100).toFixed(1)}%`;
          e.style.top = `${y.toFixed(1)}%`;
          e.style.transform = `rotate(${(c.t * 200 * (hash(i) - 0.5)).toFixed(0)}deg)`;
        });
        if (variant === 'final') root.style.filter = `hue-rotate(${(Math.sin(c.t * 0.5) * 12).toFixed(1)}deg) brightness(${(1 + 0.08 * c.pulse).toFixed(3)})`;
      };
    },
  };
}

// ---------- scenes ----------
export const SCENES: SceneDef[] = [
  // ======================= INTRO =======================
  {
    id: 'intro-terminal',
    lines: [0, 1],
    start: 0,
    theme: 'dark',
    build(root) {
      const scope = svg(root, 'scope', '0 0 1000 300', '<path class="noise" d=""/>');
      const p = scope.querySelector<SVGPathElement>('.noise')!;
      const term = mk('div', 'terminal mono', root);
      mk('div', 'prompt', term, 'bst-esw@sensor:~$ ./signal-chain --init');
      const l0 = new SungLine(term, L[0], 'tline', { mode: 'type' });
      const l1 = new SungLine(term, L[1], 'tline', { mode: 'type' });
      return (c) => {
        l0.update(c.t);
        l1.update(c.t);
        let d = '';
        for (let x = 0; x <= 1000; x += 5) d += `${x ? 'L' : 'M'}${x} ${(150 + (hash(x * 0.13 + Math.floor(c.t * 24)) - 0.5) * 220 * (0.4 + c.pulse)).toFixed(1)}`;
        p.setAttribute('d', d);
      };
    },
  },
  {
    id: 'intro-chain',
    lines: [2],
    start: 9.4,
    theme: 'dark',
    build(root) {
      const term = mk('div', 'terminal mono small', root);
      const l2 = new SungLine(term, L[2], 'tline', { mode: 'type' });
      const row = mk('div', 'big-chain', root);
      const nodes = STAGES.map((s, i) => {
        const n = mk('div', 'bc-node', row);
        mk('div', 'bc-num mono', n, String(i + 1));
        mk('div', 'bc-l', n, s.label);
        return n;
      });
      const wire = mk('div', 'bc-wire', root);
      const title = mk('div', 'title', root);
      mk('div', 'title-a', title, 'ONE SIGNAL');
      mk('div', 'title-b', title, 'FIFTEEN ROLES');
      const sub = mk('div', 'title-sub mono', root, 'BST/ESW · WORKING@BST');
      return (c) => {
        l2.update(c.t);
        nodes.forEach((n, i) => popStyle(n, c.t, 12 + i * 0.5, 20, 0.3));
        wire.style.transform = `scaleX(${easeOut(prog(c.t, 12, 15.5)).toFixed(3)})`;
        const tk = prog(c.t, 18, 18.6);
        title.style.opacity = tk.toFixed(2);
        title.style.transform = `translate(-50%, -50%) scale(${(0.8 + 0.2 * easeOutBack(tk) + 0.25 * prog(c.t, 18.6, 26)).toFixed(3)})`;
        slideIn(sub, c.t, 19.5);
        root.style.filter = `brightness(${(1 + 0.6 * prog(c.t, 23, 26)).toFixed(3)})`;
      };
    },
  },

  // ======================= VERSE 1: six roles =======================
  ...roleScenes(0, 6),

  // ======================= PRE-CHORUS =======================
  preChorus('pre-1', [9, 10]),

  // ======================= CHORUS 1 =======================
  chorusScene('chorus-1', [11, 12, 13, 14, 15, 16, 17, 18], { 15: { held: 'fifteen1', heldWord: 2 } }, 'mosaic'),

  // ======================= VERSE 2: seven roles =======================
  ...roleScenes(6, 13),

  preChorus('pre-2', [26, 27]),

  chorusScene('chorus-2', [28, 29, 30, 31, 32, 33, 34, 35], { 32: { held: 'fifteen2', heldWord: 2 } }, 'net'),

  // ======================= BRIDGE =======================
  ...roleScenes(13, 15),
  {
    id: 'no-titles',
    lines: [38, 39],
    theme: 'light',
    build(root) {
      const titles = ['SENIOR', 'LEAD', 'LEVEL 7', 'PRINCIPAL', 'GRADE B', 'HEAD OF'];
      const tags = titles.map((ti, i) => {
        const e = mk('div', 'nametag', root);
        mk('div', 'nt-h', e, 'HELLO, MY TITLE IS');
        mk('div', 'nt-t', e, ti);
        e.style.left = `${8 + (i % 3) * 30}%`;
        e.style.top = `${30 + Math.floor(i / 3) * 26}%`;
        return e;
      });
      const note = mk('div', 'policy', root, 'Competence management roles are independent from salary bands, job titles and performance evaluation. The role can shift according to business needs and personal development.');
      const up = lyrics(root, [38, 39], 'top big', true);
      return (c) => {
        up(c.t, c.pulse);
        tags.forEach((tg, i) => {
          const off = W(38, Math.min(5, i)) + 0.1;
          const k = prog(c.t, off, off + 0.9);
          tg.style.opacity = c.t < T0(38) - 0.2 ? '0' : (1 - k).toFixed(2);
          tg.style.transform = `translateY(${(k * k * 400).toFixed(0)}px) rotate(${(k * (i % 2 ? 25 : -25)).toFixed(1)}deg)`;
        });
        slideIn(note, c.t, T0(39), 30, 0.4);
      };
    },
  },
  {
    id: 'count',
    lines: [40, 41],
    theme: 'dark',
    build(root) {
      const num = mk('div', 'count-big', root);
      const field = mk('div', 'count-field', root);
      const icons = ROLE_ORDER.map((r) => icon(field, r, 'icon cicon'));
      const up = lyrics(root, [40, 41], 'bottom big', true);
      const counts = [1, 2, 5, 10, 15];
      return (c) => {
        up(c.t, c.pulse);
        let n = 0;
        let at = 0;
        counts.forEach((v, i) => {
          const w = W(40, i);
          if (c.t >= w - 0.02) {
            n = v;
            at = w;
          }
        });
        if (c.t >= T0(41)) n = 15;
        num.textContent = n ? String(n) : '';
        const age = c.t - at;
        num.style.transform = `translate(-50%, -50%) scale(${(age < 0.08 ? 1.8 - 0.8 * (age / 0.08) : 1).toFixed(3)})`;
        icons.forEach((ic, i) => {
          const on = i < n;
          const ring = c.t >= T0(41);
          const a = (i / 15) * Math.PI * 2 + c.t * 0.4;
          ic.style.opacity = on ? '1' : '0';
          ic.style.left = ring ? `calc(50% + ${(Math.cos(a) * 30).toFixed(2)}vw)` : `${12 + (i % 5) * 19}%`;
          ic.style.top = ring ? `calc(46% + ${(Math.sin(a) * 30).toFixed(2)}vh)` : `${18 + Math.floor(i / 5) * 24}%`;
        });
      };
    },
  },

  // ======================= FINAL CHORUS =======================
  chorusScene('chorus-3', [42, 43, 44, 45, 46, 47, 48, 49], { 46: { held: 'roles3', heldWord: 3, heldVowel: 1 } }, 'final'),

  // ======================= OUTRO =======================
  {
    id: 'outro',
    lines: [50, 51],
    theme: 'dark',
    build(root) {
      const row = mk('div', 'big-chain', root);
      const nodes = STAGES.map((s, i) => {
        const n = mk('div', 'bc-node', row);
        mk('div', 'bc-num mono', n, String(i + 1));
        mk('div', 'bc-l', n, s.label);
        return n;
      });
      const wire = mk('div', 'bc-wire', root);
      const term = mk('div', 'terminal mono small low', root);
      const l50 = new SungLine(term, L[50], 'tline', { mode: 'type' });
      const l51 = new SungLine(term, L[51], 'tline', { mode: 'type' });
      const fin = mk('div', 'final-card', root);
      mk('div', 'fc-a', fin, 'One signal chain,');
      mk('div', 'fc-b', fin, 'fifteen roles.');
      mk('div', 'fc-c mono', fin, 'BST/ESW · Working@BST · Find your role');
      const band = mk('div', 'super-band', fin);
      band.style.background = SUPER;
      const fade = mk('div', 'fade', root);
      return (c) => {
        l50.update(c.t);
        l51.update(c.t);
        nodes.forEach((n, i) => {
          n.classList.toggle('done', c.t > T0(50) + i * 0.45);
          n.style.opacity = '1';
        });
        wire.style.transform = `scaleX(${easeOut(prog(c.t, T0(50), T0(50) + 2.7)).toFixed(3)})`;
        const fk = prog(c.t, E(51) + 0.6, E(51) + 1.4);
        fin.style.opacity = fk.toFixed(2);
        fin.style.transform = `translate(-50%, -50%) scale(${(0.92 + 0.08 * easeOut(fk)).toFixed(3)})`;
        row.style.opacity = (1 - fk).toFixed(2);
        wire.style.opacity = (1 - fk).toFixed(2);
        term.style.opacity = (1 - fk).toFixed(2);
        band.style.transform = `scaleX(${easeOut(prog(c.t, E(51) + 1.2, E(51) + 2.4)).toFixed(3)})`;
        fade.style.opacity = prog(c.t, SONG_END - 2.5, SONG_END - 0.2).toFixed(3);
      };
    },
  },
];

/** "Feel it rising, wire to wire, every role is lighting up the fire" */
function preChorus(id: string, idx: number[]): SceneDef {
  return {
    id,
    lines: idx,
    theme: 'dark',
    build(root) {
      const wires = svg(root, 'wires', '0 0 1000 560', Array.from({ length: 9 }, (_, i) => `<path class="wire" d="M0 ${40 + i * 60} C300 ${40 + i * 60 + (i % 2 ? 80 : -80)}, 700 ${280 + (i - 4) * 20}, 1000 280"/>`).join(''));
      const ws = [...wires.querySelectorAll<SVGPathElement>('.wire')];
      const ring = mk('div', 'ring', root);
      const icons = ROLE_ORDER.map((r) => icon(ring, r, 'icon ricon'));
      const glowEl = mk('div', 'riser-glow', root);
      const up = lyrics(root, idx, 'center big', true);
      const a = T0(idx[0]);
      const b = E(idx[idx.length - 1]) + 1.2;
      return (c) => {
        up(c.t, c.pulse);
        const k = prog(c.t, a - 0.4, b);
        ws.forEach((w, i) => {
          w.style.strokeDasharray = '1400';
          w.style.strokeDashoffset = String(1400 * (1 - clamp01(k * 1.6 - i * 0.05)));
        });
        icons.forEach((ic, i) => {
          const ang = (i / 15) * Math.PI * 2 - Math.PI / 2;
          ic.style.left = `calc(50% + ${(Math.cos(ang) * 34).toFixed(2)}vw)`;
          ic.style.top = `calc(50% + ${(Math.sin(ang) * 36).toFixed(2)}vh)`;
          ic.classList.toggle('on', k * 15 * 1.2 > i);
        });
        glowEl.style.opacity = (Math.pow(k, 3) * 0.9).toFixed(3);
        ring.style.transform = `rotate(${(c.t * 6).toFixed(1)}deg)`;
      };
    },
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
  const prevE = f > 0 ? L[f - 1].e : 0;
  const t0 = Math.min(L[f].t - 0.3, Math.max(L[f].t - 0.55, prevE + 0.02));
  return { ...s, t0, t1: 0 };
});
TIMELINE.forEach((s, i) => (s.t1 = i + 1 < TIMELINE.length ? TIMELINE[i + 1].t0 : SONG_END));
export const sceneAt = (t: number) => TIMELINE.find((s) => t >= s.t0 && t < s.t1) ?? TIMELINE[TIMELINE.length - 1];
