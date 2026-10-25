// Scene list: every scene with time, length, camera, LED visual and its lyric line(s).
// Click = jump there (and select), double-click = jump + open its properties. The current scene
// is highlighted and kept in view while playing.
import { useEffect, useRef, useState } from 'react';
import type { Timing } from '../engine/timing';
import type { Project } from '../types';
import { type Selection, store } from './store';

const fmt = (t: number) => `${Math.floor(t / 60)}:${(t % 60).toFixed(1).padStart(4, '0')}`;
const SECTION: Record<string, string> = { intro: 'Intro', verse1: 'Strophe 1', chorus: 'Refrain', verse2: 'Strophe 2', bridge: 'Bridge', final: 'Finale', outro: 'Outro' };

export function SceneList({ timing, sel, now, onSeek, onOpen }: { p: Project; timing: Timing; sel: Selection; now: number; onSeek: (t: number) => void; onOpen: () => void }) {
  const [q, setQ] = useState('');
  const list = useRef<HTMLDivElement>(null);
  const cur = timing.sceneAt(now);
  const curId = cur?.scene.id;

  useEffect(() => {
    list.current?.querySelector('.srow.cur')?.scrollIntoView({ block: 'nearest' });
  }, [curId]);

  const lines = (ids: string[]) =>
    ids
      .map((id) => timing.lineById.get(id))
      .filter((l) => l && !l.unsung)
      .map((l) => l!.text)
      .join(' / ');
  const needle = q.trim().toLowerCase();
  let lastSec = '';
  return (
    <div className="scenelist">
      <div className="sl-head">
        <input placeholder="Szene oder Liedtext suchen …" value={q} onChange={(e) => setQ(e.target.value)} onKeyDown={(e) => e.stopPropagation()} />
        <span className="dim small">{timing.scenes.length} Szenen</span>
      </div>
      <div className="sl-list" ref={list}>
        {timing.scenes.map((ts, i) => {
          const s = ts.scene;
          const text = lines(s.lines);
          if (needle && !`${s.name ?? ''} ${text} ${s.shot ?? ''} ${s.legacy ?? ''} ${s.wall?.fn ?? s.wall?.type ?? ''}`.toLowerCase().includes(needle)) return null;
          const first = s.lines.map((id) => timing.lineById.get(id)).find(Boolean);
          // scenes without lyrics: intro before the first line, outro after the last, otherwise the current section
          const lastSung = timing.sung[timing.sung.length - 1];
          const sec = first?.section ?? (ts.t0 < (timing.sung[0]?.words[0].t ?? 0) ? 'intro' : lastSung && ts.t0 > lastSung.words[lastSung.words.length - 1].e - 1 ? 'outro' : lastSec || 'intro');
          const header = !needle && sec !== lastSec ? SECTION[sec] ?? sec : null;
          lastSec = sec;
          const selected = sel.kind === 'scene' && sel.id === s.id;
          return (
            <div key={s.id}>
              {header && <div className="sl-sec">{header}</div>}
              <div
                className={`srow ${s.id === curId ? 'cur' : ''} ${selected ? 'sel' : ''}`}
                onClick={() => {
                  onSeek(ts.t0 + 0.001);
                  store.select({ kind: 'scene', id: s.id });
                }}
                onDoubleClick={() => {
                  onSeek(ts.t0 + 0.001);
                  store.select({ kind: 'scene', id: s.id });
                  onOpen();
                }}
                title="Klick: hinspringen · Doppelklick: Eigenschaften"
              >
                <span className="sl-n">{i + 1}</span>
                <span className="sl-t">
                  {fmt(ts.t0)}
                  <br />
                  <span className="dim">{(ts.t1 - ts.t0).toFixed(1)} s</span>
                </span>
                <span className="sl-main">
                  <b>{s.name || s.id}</b>
                  <span className="dim small">
                    {s.legacy !== undefined ? `Original: ${s.legacy}${s.three ? ` · 3D ${s.three}` : ''}` : `${s.shot} · ${s.wall?.type === 'custom' ? s.wall.fn : s.wall?.type}`}
                    {s.start?.kind && s.start.kind !== 'auto' ? ` · Start: ${s.start.kind === 'bar' ? 'Takt' : s.start.kind === 'beat' ? 'Beat' : s.start.kind === 'word' ? 'Wort' : 'fest'}` : ''}
                  </span>
                  {text && <span className="sl-text small">{text}</span>}
                  {ts.t1 - ts.t0 < 0.05 && <span className="small warnc">übersprungen – keine gesungene Zeile (Szene löschen oder Zeilen zuordnen)</span>}
                </span>
              </div>
            </div>
          );
        })}
      </div>
      <div className="dim small sl-foot">Klick: hinspringen · Doppelklick: Eigenschaften · ←/→ springen auch ohne Liste</div>
    </div>
  );
}
