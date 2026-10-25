// Studio bridge for an imported video engine ("legacy world").
// The original scene code keeps working unchanged; only its data modules (lyrics.ts, vocal.ts,
// hits) read from here. Data comes from the studio project, loaded synchronously BEFORE the scene
// modules evaluate (they compute things from LINES at import time), and is updated IN PLACE when
// the editor changes the project (window.__update), so scene closures see the new values.

import { Timing } from '@studio/engine/timing';

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type Any = any;

function loadSync(url: string): Any {
  const x = new XMLHttpRequest();
  x.open('GET', url, false);
  x.send();
  if (x.status !== 200) throw new Error(`cannot load ${url}: ${x.status}`);
  return JSON.parse(x.responseText);
}

export interface OldLine {
  t: number;
  e: number;
  text: string;
  section: string;
  words: number[];
  ends: number[];
}

const pid = new URLSearchParams(location.search).get('project') ?? '';

export const studio = {
  pid,
  project: null as Any,
  timing: null as unknown as Timing,
  /** lines in the ORIGINAL engine's index order (project.legacy.lineMap[i] = studio line id) */
  lines: [] as OldLine[],
  /** held-note tracks by name (as the original vocal.ts expects) */
  held: {} as Record<string, { t0: number; fps: number; env: number[]; pitch: number[] }>,
  lead: 0.08,
  update(p: Any) {
    fill(p);
  },
};

const FAR = 1e6; // unsung lines are moved out of the song: the original scenes never show them

function fill(p: Any) {
  studio.project = p;
  studio.timing = new Timing(p);
  studio.lead = p.lyrics?.lead ?? 0.08;
  const byId = new Map<string, Any>((p.lyrics?.lines ?? []).map((l: Any) => [l.id, l]));
  // entry: "l12" (whole studio line), {id, from, to} (words of a studio line – after lines were
  // merged or split in an updated song) or null (no longer sung)
  const map: (string | { id: string; from: number; to: number } | null)[] = p.legacy?.lineMap ?? [];
  map.forEach((ent, i) => {
    const id = typeof ent === 'string' ? ent : ent?.id;
    const l = id ? byId.get(id) : undefined;
    const tgt = (studio.lines[i] ??= { t: FAR, e: FAR + 1, text: '', section: 'verse1', words: [], ends: [] });
    const ws: Any[] = l?.words ? (ent && typeof ent === 'object' ? l.words.slice(ent.from, ent.to + 1) : l.words) : [];
    if (!l || !ws.length || l.unsung) {
      Object.assign(tgt, { t: FAR, e: FAR + 1, text: '', section: l?.section ?? tgt.section, words: [], ends: [] });
      return;
    }
    Object.assign(tgt, {
      section: l.section,
      text: ws.map((w: Any) => w.w).join(' '),
      t: ws[0].t,
      e: ws[ws.length - 1].e,
      words: ws.map((w: Any) => w.t),
      ends: ws.map((w: Any) => w.e),
    });
  });
  for (const k of Object.keys(studio.held)) delete studio.held[k];
  for (const h of p.held ?? []) studio.held[h.name] = { t0: h.t0, fps: h.fps, env: h.env, pitch: h.pitch };
}

fill(loadSync(`/api/projects/${pid}`));
