// Timeline: ruler (seconds + bars), scenes, lyric lines, words, vocal + mix waveform, events/hits.
// Drawn on a canvas for speed. Interactions:
//   click            seek / select            drag scene edge   move the cut (snaps to bars; Shift: beats; Alt: free)
//   drag word        move word (Ctrl: whole line)   drag word edge   change start / end
//   drag line        move whole line           wheel             scroll   Ctrl+wheel  zoom
import { useEffect, useRef, useState } from 'react';
import { api } from '../api';
import type { TimedScene, Timing } from '../engine/timing';
import type { Anchor, Project } from '../types';
import { type Selection, store } from './store';

const LABEL_W = 74;
const ROWS = {
  ruler: [0, 24],
  scenes: [24, 60],
  lines: [60, 84],
  words: [84, 116],
  vocals: [116, 168],
  mix: [168, 208],
  events: [208, 228],
} as const;
const HEIGHT = 228;
type Row = keyof typeof ROWS;

const SECTION_COL: Record<string, string> = { intro: '#3d6bff', verse1: '#00a3cc', chorus: '#e3336e', verse2: '#8b4dff', bridge: '#ff6a3d', final: '#ffb300', outro: '#3d6bff' };
const sceneColor = (ts: TimedScene, p: Project) => {
  const l = p.lyrics.lines.find((x) => x.id === ts.scene.lines[0]);
  return SECTION_COL[l?.section ?? ''] ?? '#56607a';
};

interface Peaks {
  fps: number;
  max: number[];
  min: number[];
}
type Drag =
  | { kind: 'seek' }
  | { kind: 'scene'; id: string }
  | { kind: 'word'; line: string; word: number; mode: 'move' | 'start' | 'end' | 'line'; t0: number; orig: { t: number; e: number }[] }
  | { kind: 'line'; line: string; t0: number; orig: { t: number; e: number }[] }
  | { kind: 'pan'; x0: number; start0: number };

export function Timeline(props: {
  project: Project;
  timing: Timing;
  getTime: () => number;
  playing: boolean;
  selection: Selection;
  locked: boolean;
  onSeek: (t: number) => void;
}) {
  const { project, timing, getTime, onSeek } = props;
  const canvas = useRef<HTMLCanvasElement>(null);
  const wrap = useRef<HTMLDivElement>(null);
  const view = useRef({ start: 0, zoom: 90 }); // seconds at left edge, px per second
  const [peaks, setPeaks] = useState<{ mix?: Peaks; vocals?: Peaks }>({});
  const drag = useRef<Drag | null>(null);
  const propsRef = useRef(props);
  propsRef.current = props;
  const [hover, setHover] = useState('');
  const lastNow = useRef(0);

  useEffect(() => {
    let alive = true;
    void api.peaks(project.id, 'mix').then((p) => alive && setPeaks((o) => ({ ...o, mix: p }))).catch(() => {});
    if (project.audio.vocals) void api.peaks(project.id, 'vocals').then((p) => alive && setPeaks((o) => ({ ...o, vocals: p }))).catch(() => {});
    return () => {
      alive = false;
    };
  }, [project.id, project.audio.vocals]);

  const tx = (t: number) => LABEL_W + (t - view.current.start) * view.current.zoom;
  const xt = (x: number) => view.current.start + (x - LABEL_W) / view.current.zoom;

  // ---------------------------------------------------------------- drawing
  useEffect(() => {
    let raf = 0;
    const draw = () => {
      raf = requestAnimationFrame(draw);
      const c = canvas.current;
      const w = wrap.current;
      if (!c || !w) return;
      const { project: p, timing: tm, selection: sel, playing } = propsRef.current;
      const W = w.clientWidth;
      const dpr = window.devicePixelRatio || 1;
      if (c.width !== Math.round(W * dpr) || c.height !== Math.round(HEIGHT * dpr)) {
        c.width = Math.round(W * dpr);
        c.height = Math.round(HEIGHT * dpr);
        c.style.width = `${W}px`;
        c.style.height = `${HEIGHT}px`;
      }
      const g = c.getContext('2d')!;
      g.setTransform(dpr, 0, 0, dpr, 0, 0);
      const now = getTime();
      const v = view.current;
      const span = (W - LABEL_W) / v.zoom;
      if (playing && (now > v.start + span * 0.85 || now < v.start)) v.start = Math.max(0, now - span * 0.15);
      // a jump (keyboard, transport, chat) while paused: bring the playhead into view
      if (!playing && Math.abs(now - lastNow.current) > 0.5 && (now < v.start || now > v.start + span)) v.start = Math.max(0, now - span * 0.2);
      lastNow.current = now;
      v.start = Math.max(-0.5, Math.min(v.start, tm.duration - span * 0.5));
      const t0 = v.start;
      const t1 = v.start + span;

      g.fillStyle = '#0e1016';
      g.fillRect(0, 0, W, HEIGHT);
      // row backgrounds
      (Object.keys(ROWS) as Row[]).forEach((r, i) => {
        const [a, b] = ROWS[r];
        g.fillStyle = i % 2 ? '#12151d' : '#10131a';
        g.fillRect(LABEL_W, a, W, b - a);
      });
      g.save();
      g.beginPath();
      g.rect(LABEL_W, 0, W - LABEL_W, HEIGHT);
      g.clip();

      // beat grid
      const b0 = Math.floor(tm.beatAt(t0));
      const b1 = Math.ceil(tm.beatAt(t1));
      const bpb = p.grid?.beatsPerBar ?? 4;
      const ph = p.grid?.downbeatPhase ?? 0;
      for (let b = b0; b <= b1; b++) {
        const t = tm.timeAtBeat(b);
        const x = tx(t);
        const down = (((b - ph) % bpb) + bpb) % bpb === 0;
        if (!down && v.zoom < 35) continue;
        g.fillStyle = down ? 'rgba(255,255,255,0.13)' : 'rgba(255,255,255,0.045)';
        g.fillRect(Math.round(x), ROWS.ruler[1], 1, HEIGHT);
        if (down) {
          g.fillStyle = '#7b8496';
          g.font = '10px Inter, sans-serif';
          g.fillText(String(Math.round((b - ph) / bpb) + 1), x + 3, 21);
        }
      }
      // ruler seconds
      const step = v.zoom > 120 ? 1 : v.zoom > 40 ? 5 : v.zoom > 12 ? 10 : 30;
      g.fillStyle = '#cfd5e2';
      g.font = '11px Inter, sans-serif';
      for (let s = Math.ceil(t0 / step) * step; s < t1; s += step) {
        const x = tx(s);
        g.fillRect(Math.round(x), 0, 1, 6);
        g.fillText(`${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, '0')}`, x + 3, 11);
      }

      // scenes
      const [sa, sb] = ROWS.scenes;
      tm.scenes.forEach((ts) => {
        if (ts.t1 < t0 || ts.t0 > t1) return;
        const x0 = tx(ts.t0);
        const x1 = tx(ts.t1);
        const selected = sel.kind === 'scene' && sel.id === ts.scene.id;
        g.fillStyle = sceneColor(ts, p);
        g.globalAlpha = selected ? 0.95 : 0.55;
        g.fillRect(x0 + 1, sa + 3, Math.max(1, x1 - x0 - 2), sb - sa - 6);
        g.globalAlpha = 1;
        if (selected) {
          g.strokeStyle = '#fff';
          g.lineWidth = 2;
          g.strokeRect(x0 + 1, sa + 3, x1 - x0 - 2, sb - sa - 6);
        }
        // anchor kind marker on the start edge
        const k = ts.scene.start?.kind ?? 'auto';
        g.fillStyle = k === 'auto' ? '#9fe870' : k === 'bar' || k === 'beat' ? '#ffcc00' : k === 'word' ? '#5ac8ff' : '#ff8a8a';
        g.fillRect(x0, sa + 3, 3, sb - sa - 6);
        if (x1 - x0 > 30) {
          g.fillStyle = '#fff';
          g.font = '600 11px Inter, sans-serif';
          g.save();
          g.beginPath();
          g.rect(x0 + 4, sa, x1 - x0 - 8, sb - sa);
          g.clip();
          g.fillText(ts.scene.name || ts.scene.id, x0 + 7, sa + 15);
          g.font = '10px Inter, sans-serif';
          g.fillStyle = 'rgba(255,255,255,0.75)';
          g.fillText(ts.scene.legacy !== undefined ? `${ts.scene.legacy}${ts.scene.three ? ` · 3D ${ts.scene.three}` : ''}` : `${ts.scene.shot} · ${typeof ts.scene.wall?.fn === 'string' ? ts.scene.wall.fn : ts.scene.wall?.type ?? ''}`, x0 + 7, sa + 28);
          g.restore();
        }
      });

      // lines + words
      const [la, lb] = ROWS.lines;
      const [wa, wb] = ROWS.words;
      const lead = tm.lead;
      for (const l of p.lyrics.lines) {
        if (!l.words.length) continue;
        const ls = l.words[0].t - lead;
        const le = l.words[l.words.length - 1].e - lead;
        if (le < t0 || ls > t1) continue;
        const x0 = tx(ls);
        const x1 = tx(le);
        const lsel = (sel.kind === 'line' && sel.id === l.id) || (sel.kind === 'word' && sel.line === l.id);
        if (l.unsung) {
          g.fillStyle = 'rgba(120,120,130,0.25)';
          g.fillRect(x0, la + 3, x1 - x0, lb - la - 6);
          g.strokeStyle = 'rgba(200,200,210,0.35)';
          g.lineWidth = 1;
          for (let x = x0; x < x1; x += 8) {
            g.beginPath();
            g.moveTo(x, lb - 3);
            g.lineTo(Math.min(x + 8, x1), la + 3);
            g.stroke();
          }
        } else {
          g.fillStyle = lsel ? '#3b4a6e' : '#252c3d';
          g.fillRect(x0, la + 3, x1 - x0, lb - la - 6);
          if ((l.heard ?? 1) < 0.5) {
            g.strokeStyle = '#ff9f43';
            g.lineWidth = 1.5;
            g.strokeRect(x0 + 0.5, la + 3.5, x1 - x0 - 1, lb - la - 7);
          }
        }
        if (x1 - x0 > 24) {
          g.save();
          g.beginPath();
          g.rect(x0, la, x1 - x0, lb - la);
          g.clip();
          g.fillStyle = l.unsung ? '#9aa0ad' : '#e6e9f0';
          g.font = '11px Inter, sans-serif';
          g.fillText((l.unsung ? '✕ ' : '') + l.text, x0 + 4, la + 16);
          g.restore();
        }
        l.words.forEach((wd, i) => {
          const a = tx(wd.t - lead);
          const b = Math.max(a + 2, tx(wd.e - lead));
          if (b < LABEL_W || a > W) return;
          const ws = sel.kind === 'word' && sel.line === l.id && sel.word === i;
          g.fillStyle = l.unsung ? '#3a3d46' : ws ? '#ffcc00' : i % 2 ? '#3e6fd8' : '#2f5bbd';
          g.fillRect(a, wa + 4, b - a - 1, wb - wa - 8);
          if (b - a > 18) {
            g.save();
            g.beginPath();
            g.rect(a, wa, b - a - 2, wb - wa);
            g.clip();
            g.fillStyle = ws ? '#111' : '#fff';
            g.font = '11px Inter, sans-serif';
            g.fillText(wd.w, a + 3, wa + 20);
            g.restore();
          }
        });
      }

      // waveforms
      const wave = (pk: Peaks | undefined, [a, b]: readonly [number, number], col: string) => {
        if (!pk) return;
        const mid = (a + b) / 2;
        // normalise to the loudest part so quiet stems are readable
        const peak = (pk as Peaks & { peak?: number }).peak ?? ((pk as Peaks & { peak?: number }).peak = Math.max(0.05, ...pk.max.slice(0, 200000).map(Math.abs)));
        const amp = ((b - a) / 2 - 3) / (peak * 1.4);
        g.fillStyle = col;
        for (let x = LABEL_W; x < W; x++) {
          const ta = xt(x);
          const tb = xt(x + 1);
          const ia = Math.max(0, Math.floor(ta * pk.fps));
          const ib = Math.min(pk.max.length, Math.max(ia + 1, Math.ceil(tb * pk.fps)));
          if (ia >= pk.max.length || ib <= 0) continue;
          let mx = 0;
          let mn = 0;
          for (let i = ia; i < ib; i++) {
            if (pk.max[i] > mx) mx = pk.max[i];
            if (pk.min[i] < mn) mn = pk.min[i];
          }
          g.fillRect(x, mid - mx * amp * 1.4, 1, Math.max(1, (mx - mn) * amp * 1.4));
        }
      };
      wave(peaks.vocals, ROWS.vocals, '#5ac8ff');
      wave(peaks.mix, ROWS.mix, '#7d8699');

      // events + hits
      const [ea, eb] = ROWS.events;
      for (const h of p.hits?.hits ?? []) {
        if (h < t0 || h > t1) continue;
        const big = p.hits.big?.includes(h);
        g.fillStyle = big ? '#ff5a3d' : '#7a4a40';
        g.fillRect(tx(h), big ? ea + 2 : ea + 10, big ? 2 : 1, big ? eb - ea - 4 : eb - ea - 12);
      }
      (p.events ?? []).forEach((ev, i) => {
        const at = tm.anchor(ev.at, -1);
        const x = tx(at);
        const col = ev.type === 'co2' ? '#e8f0ff' : ev.type === 'sparks' ? '#ffcc00' : ev.type === 'confetti' ? '#ff6ad5' : '#ff4040';
        const selE = sel.kind === 'event' && sel.index === i;
        if (ev.type === 'sparks' && ev.until) {
          g.fillStyle = 'rgba(255,204,0,0.35)';
          g.fillRect(x, ea + 6, tx(tm.anchor(ev.until, at)) - x, eb - ea - 12);
        }
        g.fillStyle = col;
        g.beginPath();
        g.moveTo(x, ea + 3);
        g.lineTo(x + 5, (ea + eb) / 2);
        g.lineTo(x, eb - 3);
        g.lineTo(x - 5, (ea + eb) / 2);
        g.closePath();
        g.fill();
        if (selE) {
          g.strokeStyle = '#fff';
          g.stroke();
        }
      });

      // playhead
      const px = tx(now);
      g.fillStyle = '#ff3b3b';
      g.fillRect(Math.round(px) - 1, 0, 2, HEIGHT);
      g.restore();

      // labels column
      g.fillStyle = '#0b0d12';
      g.fillRect(0, 0, LABEL_W, HEIGHT);
      g.fillStyle = '#8b93a7';
      g.font = '600 10px Inter, sans-serif';
      const names: Record<Row, string> = { ruler: 'ZEIT / TAKT', scenes: 'SZENEN', lines: 'ZEILEN', words: 'WÖRTER', vocals: 'STIMME', mix: 'MIX', events: 'EFFEKTE' };
      (Object.keys(ROWS) as Row[]).forEach((r) => g.fillText(names[r], 8, (ROWS[r][0] + ROWS[r][1]) / 2 + 4));
    };
    draw();
    return () => cancelAnimationFrame(raf);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [peaks, getTime]);

  // ---------------------------------------------------------------- hit testing + edits
  const rowAt = (y: number): Row | null => (Object.keys(ROWS) as Row[]).find((r) => y >= ROWS[r][0] && y < ROWS[r][1]) ?? null;

  function snapStart(t: number, e: PointerEvent | React.PointerEvent): { t: number; anchor: Anchor } {
    const tm = propsRef.current.timing;
    const p = propsRef.current.project;
    if (e.altKey) return { t, anchor: { kind: 'time', t: Math.round(t * 1000) / 1000 } };
    const bpb = p.grid?.beatsPerBar ?? 4;
    const ph = p.grid?.downbeatPhase ?? 0;
    if (e.shiftKey) {
      const b = Math.round(tm.beatAt(t));
      return { t: tm.timeAtBeat(b), anchor: { kind: 'beat', beat: b } };
    }
    const bar = Math.round((tm.beatAt(t) - ph) / bpb);
    const tb = tm.barStart(bar);
    if (Math.abs(tx(tb) - tx(t)) < 14) return { t: tb, anchor: { kind: 'bar', bar } };
    return { t, anchor: { kind: 'time', t: Math.round(t * 1000) / 1000 } };
  }

  const onDown = (e: React.PointerEvent) => {
    const rect = canvas.current!.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    if (x < LABEL_W) return;
    (e.target as HTMLElement).setPointerCapture(e.pointerId);
    const t = xt(x);
    const { project: p, timing: tm, locked } = propsRef.current;
    const row = rowAt(y);
    const lead = tm.lead;
    if (e.button === 1 || (e.button === 0 && e.altKey && row !== 'scenes')) {
      drag.current = { kind: 'pan', x0: x, start0: view.current.start };
      return;
    }
    if (row === 'scenes') {
      const ts = tm.scenes.find((s) => t >= s.t0 && t < s.t1);
      const edge = tm.scenes.find((s, i) => i > 0 && Math.abs(tx(s.t0) - x) < 6);
      if (edge && !locked) {
        store.select({ kind: 'scene', id: edge.scene.id });
        drag.current = { kind: 'scene', id: edge.scene.id };
        return;
      }
      if (ts) {
        store.select({ kind: 'scene', id: ts.scene.id });
        onSeek(ts.t0 + 0.001);
      }
      return;
    }
    if (row === 'words' || row === 'lines') {
      for (const l of p.lyrics.lines) {
        if (!l.words.length) continue;
        if (row === 'lines') {
          if (t >= l.words[0].t - lead && t <= l.words[l.words.length - 1].e - lead) {
            store.select({ kind: 'line', id: l.id });
            if (!locked) drag.current = { kind: 'line', line: l.id, t0: t, orig: l.words.map((w) => ({ t: w.t, e: w.e })) };
            return;
          }
          continue;
        }
        const i = l.words.findIndex((w) => x >= tx(w.t - lead) - 3 && x <= Math.max(tx(w.t - lead) + 4, tx(w.e - lead)) + 3);
        if (i >= 0) {
          const wd = l.words[i];
          const a = tx(wd.t - lead);
          const b = tx(wd.e - lead);
          const mode = e.ctrlKey ? 'line' : x - a < 5 ? 'start' : b - x < 5 && b - a > 12 ? 'end' : 'move';
          store.select({ kind: 'word', line: l.id, word: i });
          if (!locked) drag.current = { kind: 'word', line: l.id, word: i, mode, t0: t, orig: l.words.map((w) => ({ t: w.t, e: w.e })) };
          return;
        }
      }
      onSeek(t);
      drag.current = { kind: 'seek' };
      return;
    }
    if (row === 'events') {
      const i = (p.events ?? []).findIndex((ev) => Math.abs(tx(tm.anchor(ev.at, -1)) - x) < 6);
      if (i >= 0) {
        store.select({ kind: 'event', index: i });
        return;
      }
    }
    onSeek(Math.max(0, t));
    drag.current = { kind: 'seek' };
  };

  const onMove = (e: React.PointerEvent) => {
    const rect = canvas.current!.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    const t = xt(x);
    const d = drag.current;
    if (!d) {
      const row = rowAt(y);
      const tm = propsRef.current.timing;
      if (row === 'scenes' && tm.scenes.some((s, i) => i > 0 && Math.abs(tx(s.t0) - x) < 6)) setHover('col');
      else if (row === 'words') setHover('word');
      else setHover('');
      return;
    }
    if (d.kind === 'pan') {
      view.current.start = d.start0 - (x - d.x0) / view.current.zoom;
      return;
    }
    if (d.kind === 'seek') {
      onSeek(Math.max(0, t));
      return;
    }
    if (d.kind === 'scene') {
      const s = snapStart(t, e);
      store.edit(`scene-start-${d.id}`, (p) => {
        const sc = p.scenes.find((x) => x.id === d.id);
        if (sc) sc.start = s.anchor;
      });
      return;
    }
    const dt = Math.round((t - d.t0) * 1000) / 1000;
    store.edit(`word-${d.kind === 'word' ? d.line : d.line}`, (p) => {
      const l = p.lyrics.lines.find((x) => x.id === d.line);
      if (!l) return;
      if (d.kind === 'line' || (d.kind === 'word' && d.mode === 'line')) {
        l.words.forEach((w, i) => {
          w.t = +(d.orig[i].t + dt).toFixed(3);
          w.e = +(d.orig[i].e + dt).toFixed(3);
        });
        return;
      }
      const i = d.word;
      const w = l.words[i];
      const o = d.orig[i];
      const prevE = i > 0 ? l.words[i - 1].t + 0.03 : -1e9;
      const nextT = i + 1 < l.words.length ? l.words[i + 1].t - 0.03 : 1e9;
      if (d.mode === 'move') {
        const nt = Math.min(Math.max(o.t + dt, prevE), nextT - 0.05);
        w.t = +nt.toFixed(3);
        w.e = +(nt + (o.e - o.t)).toFixed(3);
      } else if (d.mode === 'start') {
        w.t = +Math.min(Math.max(o.t + dt, prevE), o.e - 0.05).toFixed(3);
      } else {
        w.e = +Math.max(o.e + dt, w.t + 0.05).toFixed(3);
      }
    });
  };
  const onUp = () => {
    drag.current = null;
  };
  const onWheel = (e: React.WheelEvent) => {
    const v = view.current;
    const rect = canvas.current!.getBoundingClientRect();
    const x = e.clientX - rect.left;
    if (e.ctrlKey || e.metaKey) {
      const t = xt(x);
      v.zoom = Math.min(1200, Math.max(4, v.zoom * Math.exp(-e.deltaY * 0.0015)));
      v.start = t - (x - LABEL_W) / v.zoom;
    } else {
      v.start += ((Math.abs(e.deltaX) > Math.abs(e.deltaY) ? e.deltaX : e.deltaY) / v.zoom) * 1.2;
    }
  };
  // Ctrl+wheel must not zoom the page
  useEffect(() => {
    const c = canvas.current;
    const stop = (e: WheelEvent) => (e.ctrlKey || e.metaKey) && e.preventDefault();
    c?.addEventListener('wheel', stop, { passive: false });
    return () => c?.removeEventListener('wheel', stop);
  }, []);
  /** keep the selected scene / time in view (used by keyboard navigation) */
  useEffect(() => {
    const s = props.selection;
    if (s.kind !== 'scene') return;
    const ts = timing.scenes.find((x) => x.scene.id === s.id);
    const v = view.current;
    const span = ((wrap.current?.clientWidth ?? 800) - LABEL_W) / v.zoom;
    if (ts && (ts.t0 < v.start || ts.t0 > v.start + span)) v.start = Math.max(0, ts.t0 - span * 0.2);
  }, [props.selection, timing]);

  return (
    <div className="timeline" ref={wrap}>
      <canvas
        ref={canvas}
        onPointerDown={onDown}
        onPointerMove={onMove}
        onPointerUp={onUp}
        onPointerCancel={onUp}
        onWheel={onWheel}
        style={{ cursor: hover === 'col' ? 'col-resize' : hover === 'word' ? 'pointer' : 'default' }}
      />
      <div className="timeline-zoom">
        <button onClick={() => (view.current.zoom = Math.max(4, view.current.zoom / 1.5))}>−</button>
        <button onClick={() => (view.current.zoom = Math.min(1200, view.current.zoom * 1.5))}>+</button>
        <span>Strg+Mausrad: Zoom · Alt+Ziehen: verschieben</span>
      </div>
    </div>
  );
}
