// Inspector: properties of the selected scene / line / word / event, or the project settings.
import { useEffect, useState } from 'react';
import { api } from '../api';
import type { Look, Shot } from '../engine/concert';
import type { Timing } from '../engine/timing';
import { WALL_TYPES } from '../engine/walls';
import type { Anchor, Line, Project, Scene } from '../types';
import { type Selection, store } from './store';
import { copyProject } from './Home';
import { UpdateAudio } from './UpdateAudio';

const SHOTS: Shot[] = ['wide', 'crowd', 'singer', 'pit', 'wing', 'drums', 'guitar', 'bass', 'keys', 'crane', 'wall', 'top', 'orbit'];
const SECTIONS = ['intro', 'verse1', 'chorus', 'verse2', 'bridge', 'final', 'outro'];
const fmt = (t: number) => `${Math.floor(t / 60)}:${(t % 60).toFixed(2).padStart(5, '0')}`;

function JsonField({ value, onChange, rows = 6 }: { value: unknown; onChange: (v: unknown) => void; rows?: number }) {
  const [text, setText] = useState(JSON.stringify(value ?? {}, null, 1));
  const [err, setErr] = useState('');
  useEffect(() => setText(JSON.stringify(value ?? {}, null, 1)), [value]);
  return (
    <div>
      <textarea
        className={err ? 'bad' : ''}
        rows={rows}
        value={text}
        spellCheck={false}
        onChange={(e) => {
          setText(e.target.value);
          try {
            const v = JSON.parse(e.target.value);
            setErr('');
            onChange(v);
          } catch (x) {
            setErr((x as Error).message);
          }
        }}
      />
      {err && <div className="err small">{err}</div>}
    </div>
  );
}

function AnchorField({ a, timing, now, onChange, allowAuto, resolved }: { a: Anchor; timing: Timing; now: number; onChange: (a: Anchor) => void; allowAuto?: boolean; resolved?: number }) {
  const t = a.kind === 'auto' ? (resolved ?? 0) : timing.anchor(a, 0);
  const bpb = timing.p.grid?.beatsPerBar ?? 4;
  const ph = timing.p.grid?.downbeatPhase ?? 0;
  const conv = (kind: string): Anchor => {
    if (kind === 'auto') return { kind: 'auto' };
    if (kind === 'bar') return { kind: 'bar', bar: Math.round((timing.beatAt(t) - ph) / bpb) };
    if (kind === 'beat') return { kind: 'beat', beat: Math.round(timing.beatAt(t)) };
    return { kind: 'time', t: +t.toFixed(3) };
  };
  return (
    <div className="anchor">
      <select value={a.kind} onChange={(e) => onChange(conv(e.target.value))}>
        {allowAuto && <option value="auto">automatisch (nach der Zeile davor)</option>}
        <option value="bar">auf Takt</option>
        <option value="beat">auf Beat</option>
        {a.kind === 'word' && <option value="word">an Wort</option>}
        <option value="time">feste Zeit</option>
      </select>
      {a.kind === 'bar' && <input type="number" value={a.bar} onChange={(e) => onChange({ ...a, bar: +e.target.value })} />}
      {a.kind === 'beat' && <input type="number" value={a.beat} onChange={(e) => onChange({ ...a, beat: +e.target.value })} />}
      {a.kind === 'time' && <input type="number" step={0.01} value={a.t} onChange={(e) => onChange({ kind: 'time', t: +e.target.value })} />}
      {a.kind !== 'auto' && 'offset' in a && <input type="number" step={0.01} title="Versatz (s)" value={a.offset ?? 0} onChange={(e) => onChange({ ...a, offset: +e.target.value })} />}
      <span className="dim">{fmt(t)}</span>
      {a.kind !== 'auto' && (
        <button title="auf Abspielposition setzen" onClick={() => onChange({ kind: 'time', t: +now.toFixed(3) })}>
          ⤓ Playhead
        </button>
      )}
    </div>
  );
}

function SceneInspector({ s, p, timing, now }: { s: Scene; p: Project; timing: Timing; now: number }) {
  const ed = (label: string, fn: (sc: Scene) => void) => store.edit(label, (pp) => fn(pp.scenes.find((x) => x.id === s.id)!));
  const ts = timing.scenes.find((x) => x.scene.id === s.id);
  const lookNames = Object.keys(p.looks ?? {});
  const lines = s.lines.map((id) => p.lyrics.lines.find((l) => l.id === id)).filter(Boolean) as Line[];
  return (
    <div className="insp">
      <h3>Szene</h3>
      <label>Name</label>
      <input value={s.name ?? ''} onChange={(e) => ed('scene-name', (x) => (x.name = e.target.value))} />
      <label>Start {ts && <span className="dim">({fmt(ts.t0)} – {fmt(ts.t1)}, {(ts.t1 - ts.t0).toFixed(1)} s)</span>}</label>
      <AnchorField a={s.start ?? { kind: 'auto' }} timing={timing} now={now} resolved={ts?.t0} allowAuto={s.lines.length > 0} onChange={(a) => ed('scene-start', (x) => (x.start = a))} />
      <label>Zeilen in der Szene</label>
      <div className="small">{lines.map((l) => <div key={l.id} className={l.unsung ? 'dim' : ''}>{l.id}: {l.text}</div>)}</div>
      <input value={s.lines.join(', ')} onChange={(e) => ed('scene-lines', (x) => (x.lines = e.target.value.split(/[\s,]+/).filter(Boolean)))} />
      {p.world === 'legacy' ? (
        <>
          <label>Original-Szene ({p.legacy?.engine})</label>
          <select value={s.legacy ?? ''} onChange={(e) => ed('scene-legacy', (x) => (x.legacy = e.target.value))}>
            {[...new Set((p.legacy?.scenes ?? []).map((x) => x.id))].map((id) => <option key={id}>{id}</option>)}
          </select>
          <div className="small dim">Spielt den Original-Code dieser Szene (Look, Animation, 3D). Zeitpunkt, Zeilen und Reihenfolge kommen aus dem Studio. Bild ändern: über den Assistenten (er bearbeitet den Original-Code).</div>
          <label>Notizen</label>
          <textarea rows={2} value={s.notes ?? ''} onChange={(e) => ed('scene-notes', (x) => (x.notes = e.target.value))} />
        </>
      ) : (<>
      <label>Kamera</label>
      <select value={s.shot} onChange={(e) => ed('scene-shot', (x) => (x.shot = e.target.value as Shot))}>
        {SHOTS.map((k) => <option key={k}>{k}</option>)}
      </select>
      <label>Variation</label>
      <input type="number" step={1} value={s.seed ?? 0} onChange={(e) => ed('scene-seed', (x) => (x.seed = +e.target.value))} />
      <label>Licht-Look</label>
      <select value={typeof s.look === 'string' ? s.look : '(eigener)'} onChange={(e) => ed('scene-look', (x) => (x.look = e.target.value === '(eigener)' ? ({ ...(typeof x.look === 'string' ? p.looks[x.look] : x.look) } as Look) : e.target.value))}>
        {lookNames.map((k) => <option key={k}>{k}</option>)}
        <option>(eigener)</option>
      </select>
      {typeof s.look !== 'string' && <JsonField value={s.look} onChange={(v) => ed('scene-look-json', (x) => (x.look = v as Scene['look']))} />}
      <label>LED-Wand</label>
      <select value={s.wall?.type ?? 'eq'} onChange={(e) => ed('scene-wall', (x) => (x.wall = { type: e.target.value, params: x.wall?.params ?? {} }))}>
        {[...WALL_TYPES, 'custom'].map((k) => <option key={k}>{k}</option>)}
      </select>
      {s.wall?.type === 'custom' && (
        <div className="row2">
          <input placeholder="walls/datei.js" value={s.wall.module ?? ''} onChange={(e) => ed('scene-wall-mod', (x) => (x.wall = { ...(x.wall ?? { type: 'custom' }), module: e.target.value }))} />
          <input placeholder="Funktion" value={s.wall.fn ?? ''} onChange={(e) => ed('scene-wall-fn', (x) => (x.wall = { ...(x.wall ?? { type: 'custom' }), fn: e.target.value }))} />
        </div>
      )}
      <JsonField value={s.wall?.params ?? {}} onChange={(v) => ed('scene-wall-params', (x) => (x.wall = { ...(x.wall ?? { type: 'eq' }), params: v as Record<string, unknown> }))} />
      <label>Liedtext-Stil</label>
      <select value={s.lyr ?? 'low'} onChange={(e) => ed('scene-lyr', (x) => (x.lyr = e.target.value as Scene['lyr']))}>
        <option value="low">unten (Bauchbinde)</option>
        <option value="big">groß in der Mitte</option>
        <option value="side">links</option>
        <option value="none">kein Text</option>
      </select>
      <label>Kamera-Label</label>
      <input value={s.cam ?? ''} onChange={(e) => ed('scene-cam', (x) => (x.cam = e.target.value))} />
      <label>Notizen</label>
      <textarea rows={2} value={s.notes ?? ''} onChange={(e) => ed('scene-notes', (x) => (x.notes = e.target.value))} />
      </>)}
      <div className="buttons">
        <button
          onClick={() =>
            store.edit('scene-split', (pp) => {
              const i = pp.scenes.findIndex((x) => x.id === s.id);
              const id = `s${Date.now().toString(36)}`;
              pp.scenes.splice(i + 1, 0, { ...structuredClone(s), id, name: `${s.name ?? s.id} (2)`, start: { kind: 'time', t: +now.toFixed(3) }, lines: [] });
            })
          }
        >
          Teilen am Playhead
        </button>
        <button
          className="danger"
          onClick={() => {
            store.edit('scene-delete', (pp) => (pp.scenes = pp.scenes.filter((x) => x.id !== s.id)));
            store.select({ kind: 'none' });
          }}
        >
          Szene löschen
        </button>
      </div>
    </div>
  );
}

function resplit(l: Line, text: string) {
  const ws = text.trim().split(/\s+/).filter(Boolean);
  if (!ws.length) return;
  if (ws.length === l.words.length) {
    l.words.forEach((w, i) => (w.w = ws[i]));
  } else {
    const a = l.words[0]?.t ?? 0;
    const b = l.words[l.words.length - 1]?.e ?? a + ws.length * 0.4;
    const step = (b - a) / ws.length;
    l.words = ws.map((w, i) => ({ w, t: +(a + i * step).toFixed(3), e: +(a + (i + 0.9) * step).toFixed(3) }));
  }
  l.text = ws.join(' ');
}

function LineInspector({ l, word }: { l: Line; word?: number }) {
  const ed = (label: string, fn: (x: Line) => void) => store.edit(label, (pp) => fn(pp.lyrics.lines.find((x) => x.id === l.id)!));
  const [text, setText] = useState(l.text);
  useEffect(() => setText(l.text), [l.text, l.id]);
  return (
    <div className="insp">
      <h3>Zeile {l.id}</h3>
      <label>Text (Wörter durch Leerzeichen; bei gleicher Wortzahl bleiben die Zeiten)</label>
      <textarea rows={2} value={text} onChange={(e) => setText(e.target.value)} onBlur={() => text !== l.text && ed('line-text', (x) => resplit(x, text))} />
      <label>Abschnitt</label>
      <select value={l.section} onChange={(e) => ed('line-section', (x) => (x.section = e.target.value))}>
        {SECTIONS.map((k) => <option key={k}>{k}</option>)}
      </select>
      <label className="check">
        <input type="checkbox" checked={!!l.unsung} onChange={(e) => ed('line-unsung', (x) => (x.unsung = e.target.checked))} /> nicht gesungen (ausblenden)
      </label>
      {l.heard !== undefined && <div className="small dim">gehört: {Math.round((l.heard ?? 0) * 100)} % der Wörter</div>}
      <label>Wörter (Sekunden, gemessen)</label>
      <div className="words">
        {l.words.map((w, i) => (
          <div key={i} className={`wrow ${i === word ? 'sel' : ''}`} onClick={() => store.select({ kind: 'word', line: l.id, word: i })}>
            <span className="ww">{w.w}</span>
            <input type="number" step={0.01} value={w.t} onChange={(e) => ed('word-t', (x) => (x.words[i].t = +e.target.value))} />
            <input type="number" step={0.01} value={w.e} onChange={(e) => ed('word-e', (x) => (x.words[i].e = +e.target.value))} />
          </div>
        ))}
      </div>
      <div className="small dim">Tipp: Wort wählen, dann , / . = ±10 ms (Shift ±50 ms) · T beim Abspielen = Wortanfang hier setzen und weiter</div>
    </div>
  );
}

function EventInspector({ index, p, timing, now }: { index: number; p: Project; timing: Timing; now: number }) {
  const ev = p.events[index];
  if (!ev) return null;
  const ed = (label: string, fn: (pp: Project) => void) => store.edit(label, fn);
  return (
    <div className="insp">
      <h3>Effekt</h3>
      <select value={ev.type} onChange={(e) => ed('ev-type', (pp) => (pp.events[index].type = e.target.value as typeof ev.type))}>
        <option value="co2">CO2-Fontänen</option>
        <option value="sparks">Funkenregen</option>
        <option value="confetti">Konfetti</option>
        <option value="fireworks">Feuerwerk</option>
      </select>
      <label>Zeitpunkt</label>
      <AnchorField a={ev.at} timing={timing} now={now} onChange={(a) => ed('ev-at', (pp) => (pp.events[index].at = a))} />
      {ev.type === 'sparks' && (
        <>
          <label>bis</label>
          <AnchorField a={ev.until ?? { kind: 'time', t: timing.anchor(ev.at, 0) + 2 }} timing={timing} now={now} onChange={(a) => ed('ev-until', (pp) => (pp.events[index].until = a))} />
        </>
      )}
      <div className="buttons">
        <button className="danger" onClick={() => { ed('ev-del', (pp) => pp.events.splice(index, 1)); store.select({ kind: 'none' }); }}>Effekt löschen</button>
      </div>
    </div>
  );
}

function Versions({ pid }: { pid: string }) {
  const [list, setList] = useState<string[] | null>(null);
  const label = (n: string) => {
    const m = n.match(/^(\d{4})(\d{2})(\d{2})-(\d{2})(\d{2})(\d{2})/);
    return m ? `${m[3]}.${m[2]}. ${m[4]}:${m[5]}:${m[6]}` : n;
  };
  if (!list)
    return (
      <div className="buttons">
        <button onClick={() => api.history(pid).then((l) => setList(l.reverse()))}>Versionen anzeigen …</button>
      </div>
    );
  return (
    <div className="small versions">
      {list.length === 0 && <div className="dim">noch keine früheren Versionen</div>}
      {list.slice(0, 30).map((n) => (
        <div key={n} className="vrow">
          <span>{label(n)}</span>
          <button
            onClick={async () => {
              if (!confirm(`Stand vom ${label(n)} wiederherstellen? (Der aktuelle Stand bleibt als Version erhalten.)`)) return;
              await store.save();
              await api.restore(pid, n);
              await store.reload();
              setList(null);
            }}
          >
            wiederherstellen
          </button>
        </div>
      ))}
      <button className="link" onClick={() => setList(null)}>ausblenden</button>
    </div>
  );
}

function ProjectInspector({ p, timing, now, onSeek }: { p: Project; timing: Timing; now: number; onSeek: (t: number) => void }) {
  const ed = (label: string, fn: (pp: Project) => void) => store.edit(label, fn);
  const [upd, setUpd] = useState(false);
  const jump = (id: string) => {
    const l = p.lyrics.lines.find((x) => x.id === id);
    if (!l) return;
    store.select({ kind: 'line', id });
    onSeek(Math.max(0, l.words[0].t - 1));
  };
  const lu = p.lastUpdate;
  const unsung = p.lyrics.lines.filter((l) => l.unsung);
  const weak = p.lyrics.lines.filter((l) => !l.unsung && (l.heard ?? 1) < 0.5);
  return (
    <div className="insp">
      <h3>Projekt</h3>
      {p.audio.stemCheck && p.audio.stemCheck.status !== 'ok' && (
        <div className="warn">
          Stems: {p.audio.stemCheck.status === 'shifted' ? `um ${p.audio.stemCheck.medianLag.toFixed(2)} s verschoben – ausgeglichen` : 'andere Fassung als der Song – Summe der Stems wird als Tonspur genutzt'}
        </div>
      )}
      <label>Text-Vorlauf: Buchstaben erscheinen {Math.round(p.lyrics.lead * 1000)} ms vor dem Wort</label>
      <input type="range" min={-0.2} max={0.4} step={0.01} value={p.lyrics.lead} onChange={(e) => ed('lead', (pp) => (pp.lyrics.lead = +e.target.value))} />
      <label>Lesezeit vor Szenenwechsel: {p.settings.readHold.toFixed(2)} s</label>
      <input type="range" min={0} max={1.2} step={0.05} value={p.settings.readHold} onChange={(e) => ed('readhold', (pp) => (pp.settings.readHold = +e.target.value))} />
      <label>Audio-Latenz der Vorschau: {Math.round((p.settings.previewOffset ?? 0) * 1000)} ms (nur Vorschau, nicht im Export)</label>
      <input type="range" min={-0.3} max={0.3} step={0.005} value={p.settings.previewOffset ?? 0} onChange={(e) => ed('pvoff', (pp) => (pp.settings.previewOffset = +e.target.value))} />
      <label>Tempo-Raster ({p.grid.bpm.toFixed(1)} BPM, Abweichung {p.grid.residualMs ?? '–'} ms, Quelle {p.grid.source})</label>
      <div className="buttons">
        <button className={p.grid.mode === 'fixed' ? 'on' : ''} onClick={() => api.gridMode(p.id, 'fixed').then(() => store.reload())}>festes Tempo</button>
        <button className={p.grid.mode === 'follow' ? 'on' : ''} onClick={() => api.gridMode(p.id, 'follow').then(() => store.reload())}>erkannten Beats folgen</button>
      </div>
      <label>Takt-Eins verschieben (Phase {p.grid.downbeatPhase} von {p.grid.beatsPerBar})</label>
      <div className="buttons">
        <button onClick={() => ed('phase', (pp) => (pp.grid.downbeatPhase = (pp.grid.downbeatPhase + pp.grid.beatsPerBar - 1) % pp.grid.beatsPerBar))}>◀ Beat</button>
        <button onClick={() => ed('phase', (pp) => (pp.grid.downbeatPhase = (pp.grid.downbeatPhase + 1) % pp.grid.beatsPerBar))}>Beat ▶</button>
      </div>
      {(unsung.length > 0 || weak.length > 0) && (
        <>
          <label>Prüfen</label>
          <div className="small">
            {unsung.map((l) => <div key={l.id} className="link" onClick={() => { store.select({ kind: 'line', id: l.id }); onSeek(l.words[0].t - 1); }}>✕ nicht gesungen: {l.text}</div>)}
            {weak.map((l) => <div key={l.id} className="link warnc" onClick={() => { store.select({ kind: 'line', id: l.id }); onSeek(l.words[0].t - 1); }}>⚠ unsicher ({Math.round((l.heard ?? 0) * 100)} % gehört): {l.text}</div>)}
          </div>
        </>
      )}
      {lu && (
        <>
          <label>Letzte Audio-Aktualisierung (Wörter im Mittel um {lu.medianShift >= 0 ? '+' : ''}{lu.medianShift.toFixed(2)} s verschoben)</label>
          <div className="small">
            {lu.added.map((x) => <div key={'a' + x.id} className="link ok" onClick={() => jump(x.id)}>+ neu: {x.text}</div>)}
            {lu.changed.map((x) => <div key={'c' + x.id} className="link warnc" onClick={() => jump(x.id)}>~ geändert: {x.text}</div>)}
            {lu.removed.map((x) => <div key={'r' + x.id} className="dim">− gestrichen: {x.text}</div>)}
            {!lu.added.length && !lu.changed.length && !lu.removed.length && <div className="dim">Text unverändert – nur das Timing wurde neu gemessen.</div>}
            {lu.legacyNote && <div className="warn">Neue Zeilen erscheinen bei importierten Videos erst, wenn eine Original-Szene sie zeigt – den Assistenten bitten, sie in die passende Szene einzubauen.</div>}
          </div>
          <div className="buttons"><button onClick={() => ed('clear-update', (pp) => delete pp.lastUpdate)}>Hinweis ausblenden</button></div>
        </>
      )}
      <label>Gespeicherte Versionen</label>
      <Versions pid={p.id} />
      <label>Analyse</label>
      <div className="buttons">
        <button className="primary" onClick={() => setUpd(true)}>Audio aktualisieren …</button>
        <button title="Kopie mit eigenem Namen – z. B. für die nächste Version, dann Audio aktualisieren" onClick={() => void store.save().then(() => copyProject(p.id, p.title))}>Als neues Projekt kopieren …</button>
      </div>
      {upd && <UpdateAudio pid={p.id} onClose={() => setUpd(false)} />}
      <div className="buttons">
        <button title="Transkription, Abgleich, Einrasten, Stimme und gehaltene Töne neu messen – Szenen, Effekte und Looks bleiben" onClick={() => confirm('Timing neu messen? Szenen und Effekte bleiben erhalten; manuelle Wort-Korrekturen werden durch die neue Messung ersetzt.') && api.analyze(p.id, 'transcribe', true).catch((e) => alert(e.message))}>Timing neu messen (Szenen behalten)</button>
      </div>
      {p.world === 'legacy' ? (
        <>
          <label>Original-Engine: {p.legacy?.engine}</label>
          <div className="buttons">
            <button onClick={() => api.legacyBuild(p.id).then(() => store.reload()).catch((e) => alert(e.message))}>Engine neu bauen</button>
          </div>
        </>
      ) : (<>
      <label>Storyboard</label>
      <div className="buttons">
        <button onClick={() => confirm('Alle Szenen und Effekte durch ein neues automatisches Storyboard ersetzen? (Rückgängig über den Verlauf)') && api.storyboard(p.id).then(() => store.reload())}>Automatisch neu erstellen</button>
        <button onClick={() => store.edit('event-add', (pp) => pp.events.push({ type: 'co2', at: { kind: 'time', t: +now.toFixed(3) } }))}>Effekt am Playhead</button>
      </div>
      </>)}
      <div className="small dim">{timing.scenes.length} Szenen · {p.lyrics.lines.length} Zeilen · {p.events?.length ?? 0} Effekte</div>
    </div>
  );
}

export function Inspector({ p, timing, sel, now, onSeek }: { p: Project; timing: Timing; sel: Selection; now: number; onSeek: (t: number) => void }) {
  if (sel.kind === 'scene') {
    const s = p.scenes.find((x) => x.id === sel.id);
    if (s) return <SceneInspector s={s} p={p} timing={timing} now={now} />;
  }
  if (sel.kind === 'line' || sel.kind === 'word') {
    const l = p.lyrics.lines.find((x) => x.id === (sel.kind === 'line' ? sel.id : sel.line));
    if (l) return <LineInspector l={l} word={sel.kind === 'word' ? sel.word : undefined} />;
  }
  if (sel.kind === 'event') return <EventInspector index={sel.index} p={p} timing={timing} now={now} />;
  return <ProjectInspector p={p} timing={timing} now={now} onSeek={onSeek} />;
}
