// The editor page: live preview + transport, inspector, chat and the timeline.
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { api, fileUrl, type Status } from '../api';
import { LegacyPlayer, type Preview } from '../engine/legacyPlayer';
import { Player } from '../engine/player';
import { Timing } from '../engine/timing';
import { Chat } from './Chat';
import { ExportDialog } from './ExportDialog';
import { ExportsPanel } from './ExportsPanel';
import { Inspector } from './Inspector';
import { SceneList } from './SceneList';
import { store, useEditor } from './store';
import { Timeline } from './Timeline';

const fmt = (t: number) => `${Math.floor(t / 60)}:${(t % 60).toFixed(1).padStart(4, '0')}`;

function Analysis({ status }: { status: Status | null }) {
  const job = status?.job;
  const log = useRef<HTMLPreElement>(null);
  useEffect(() => {
    log.current?.scrollTo(0, log.current.scrollHeight);
  }, [job?.log?.length]);
  const steps = job?.steps ?? [];
  const cur = steps.indexOf(job?.step ?? '');
  return (
    <div className="analysis">
      <h2>Analyse läuft …</h2>
      <p className="dim">Stimme freistellen, Text erkennen und abgleichen, Wörter auf die Stimme einrasten, Beats und Takte, Schläge, gehaltene Töne. Das dauert je nach Song 5–15 Minuten.</p>
      <div className="steps">
        {steps.map((s, i) => (
          <span key={s} className={i < cur || job?.status === 'done' ? 'done' : i === cur ? 'cur' : ''}>
            {s}
          </span>
        ))}
      </div>
      {job?.status === 'error' && <div className="err">Fehler: {job.error}</div>}
      <pre ref={log}>{(job?.log ?? []).join('\n')}</pre>
    </div>
  );
}

export function Editor({ pid }: { pid: string }) {
  const st = useEditor();
  // the store is shared: right after switching projects it still holds the previous one until
  // load(pid) is done – never build the preview (concert vs imported engine) from that
  const p = st.pid === pid ? st.project : null;
  const [status, setStatus] = useState<Status | null>(null);
  const [playing, setPlaying] = useState(false);
  const [now, setNow] = useState(0);
  const [rate, setRate] = useState(1);
  const [loop, setLoop] = useState(false);
  const [tab, setTab] = useState<'scenes' | 'insp' | 'chat' | 'exports'>('scenes');
  const [exportOpen, setExportOpen] = useState(false);
  const stageRef = useRef<HTMLDivElement>(null);
  const player = useRef<Preview | null>(null);
  const audio = useRef<HTMLAudioElement | null>(null);
  const chatWasRunning = useRef(false);
  const timing = useMemo(() => (p && p.status !== 'analyzing' ? new Timing(p) : null), [p]);
  const ready = !!p && p.status !== 'analyzing' && !!timing && (p.scenes?.length ?? 0) > 0;

  useEffect(() => {
    void store.load(pid);
    return () => store.select({ kind: 'none' });
  }, [pid]);

  // status polling: analysis progress, chat assistant, export, external changes
  useEffect(() => {
    let alive = true;
    const tick = async () => {
      try {
        const s = await api.status(pid);
        if (!alive) return;
        setStatus(s);
        const chatRunning = s.chat.status === 'running';
        if (chatRunning && !chatWasRunning.current) store.lock('Der Assistent bearbeitet das Projekt …');
        if (!chatRunning && chatWasRunning.current) {
          store.lock(null);
          await store.reload();
        }
        chatWasRunning.current = chatRunning;
        const cur = store.get();
        if (!chatRunning && !cur.dirty && !cur.saving && Math.abs(s.version - cur.version) > 1e-6) await store.reload();
      } catch {
        /* server restarting */
      }
    };
    void tick();
    const id = window.setInterval(tick, 1500);
    return () => {
      alive = false;
      window.clearInterval(id);
    };
  }, [pid]);

  // player + audio
  useEffect(() => {
    if (!ready || !stageRef.current || player.current) return;
    player.current = p!.world === 'legacy' ? new LegacyPlayer(stageRef.current, pid) : new Player(stageRef.current, fileUrl(pid));
    const a = new Audio(fileUrl(pid)(p!.audio.mix));
    a.preload = 'auto';
    a.addEventListener('play', () => setPlaying(true));
    a.addEventListener('pause', () => setPlaying(false));
    audio.current = a;
    const ro = new ResizeObserver(() => {
      const r = stageRef.current!.getBoundingClientRect();
      player.current?.resize(Math.round(r.width), Math.round(r.height));
    });
    ro.observe(stageRef.current);
    return () => {
      ro.disconnect();
      a.pause();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ready, pid]);

  useEffect(() => {
    if (ready && player.current && p) void player.current.setProject(p, String(st.version));
  }, [ready, p, st.version]);

  // frame loop
  const loopRef = useRef(loop);
  loopRef.current = loop;
  useEffect(() => {
    let raf = 0;
    let lastUi = 0;
    const frame = (ms: number) => {
      raf = requestAnimationFrame(frame);
      const a = audio.current;
      const pl = player.current;
      if (!a || !pl?.timing) return;
      const off = store.get().project?.settings?.previewOffset ?? 0;
      const t = a.currentTime - off;
      if (loopRef.current && !a.paused) {
        const ts = pl.sceneAt(a.currentTime - 0.05);
        if (ts && a.currentTime >= ts.t1 - 0.02) a.currentTime = ts.t0;
      }
      pl.renderAt(Math.max(0, t));
      if (ms - lastUi > 80) {
        lastUi = ms;
        setNow(a.currentTime);
      }
    };
    raf = requestAnimationFrame(frame);
    return () => cancelAnimationFrame(raf);
  }, []);

  const getTime = useCallback(() => audio.current?.currentTime ?? 0, []);
  const seek = useCallback((t: number) => {
    if (audio.current) audio.current.currentTime = Math.max(0, t);
    setNow(Math.max(0, t));
  }, []);
  // test hook for automated UI checks (headless screenshots)
  (window as unknown as { __seek?: (t: number) => void }).__seek = seek;
  const toggle = () => {
    const a = audio.current;
    if (!a) return;
    if (a.paused) void a.play();
    else a.pause();
  };
  useEffect(() => {
    if (audio.current) audio.current.playbackRate = rate;
  }, [rate]);

  // keyboard shortcuts
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement).tagName;
      if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return;
      const s = store.get();
      const pr = s.project;
      const a = audio.current;
      if (!pr || !a || !timing) return;
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 's') {
        e.preventDefault();
        void store.save();
      } else if (e.code === 'Space') {
        e.preventDefault();
        toggle();
      } else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'z') {
        e.preventDefault();
        if (e.shiftKey) store.doRedo();
        else store.doUndo();
      } else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'y') {
        e.preventDefault();
        store.doRedo();
      } else if (e.key === 'ArrowRight' || e.key === 'ArrowLeft') {
        e.preventDefault();
        if (e.shiftKey) return seek(a.currentTime + (e.key === 'ArrowRight' ? 1 : -1));
        const list = timing.scenes;
        const cur = list.findIndex((x) => a.currentTime + 0.01 >= x.t0 && a.currentTime + 0.01 < x.t1);
        const target = list[Math.max(0, Math.min(list.length - 1, cur + (e.key === 'ArrowRight' ? 1 : a.currentTime - list[cur].t0 > 0.6 ? 0 : -1)))];
        if (target) {
          seek(target.t0 + 0.001);
          store.select({ kind: 'scene', id: target.scene.id });
        }
      } else if (e.key === ',' || e.key === '.') {
        const d = (e.key === '.' ? 1 : -1) * (e.shiftKey ? 0.05 : 0.01);
        const sel = s.selection;
        if (sel.kind === 'word')
          store.edit(`nudge-${sel.line}-${sel.word}`, (pp) => {
            const w = pp.lyrics.lines.find((l) => l.id === sel.line)?.words[sel.word];
            if (w) {
              w.t = +(w.t + d).toFixed(3);
              w.e = +(w.e + d).toFixed(3);
            }
          });
        else if (sel.kind === 'line')
          store.edit(`nudge-${sel.id}`, (pp) => pp.lyrics.lines.find((l) => l.id === sel.id)?.words.forEach((w) => ((w.t = +(w.t + d).toFixed(3)), (w.e = +(w.e + d).toFixed(3)))));
      } else if (e.key.toLowerCase() === 't' && s.selection.kind === 'word') {
        // tap sync: the selected word starts now, then jump to the next word
        const sel = s.selection;
        const tNow = +(a.currentTime - (pr.settings.previewOffset ?? 0)).toFixed(3);
        store.edit('tap', (pp) => {
          const l = pp.lyrics.lines.find((x) => x.id === sel.line);
          const w = l?.words[sel.word];
          if (!l || !w) return;
          const dur = Math.max(0.08, w.e - w.t);
          w.t = tNow;
          w.e = +(tNow + dur).toFixed(3);
          const prev = l.words[sel.word - 1];
          if (prev && prev.e > tNow - 0.02) prev.e = +(tNow - 0.02).toFixed(3);
        });
        const lines = pr.lyrics.lines;
        const li = lines.findIndex((x) => x.id === sel.line);
        if (sel.word + 1 < lines[li].words.length) store.select({ kind: 'word', line: sel.line, word: sel.word + 1 });
        else {
          const nxt = lines.slice(li + 1).find((x) => !x.unsung && x.words.length);
          if (nxt) store.select({ kind: 'word', line: nxt.id, word: 0 });
        }
      } else if (e.key.toLowerCase() === 'l') setLoop((v) => !v);
      else if (e.key === 'Delete' && s.selection.kind === 'line') {
        const id = s.selection.id;
        store.edit('unsung', (pp) => {
          const l = pp.lyrics.lines.find((x) => x.id === id);
          if (l) l.unsung = !l.unsung;
        });
      } else if (e.key === 'Escape') store.select({ kind: 'none' });
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [timing]);

  if (!p) return <div className="center dim">lädt …</div>;
  if (p.status === 'analyzing' || (status?.job?.status === 'running' && !ready))
    return (
      <div className="editor-page">
        <Header title={p.title} />
        <Analysis status={status} />
      </div>
    );
  if (!ready || !timing)
    return (
      <div className="editor-page">
        <Header title={p.title} />
        <div className="center">{p.status === 'error' || status?.job?.status === 'error' ? <Analysis status={status} /> : 'Projekt hat noch keine Szenen.'}</div>
      </div>
    );

  const exp = status?.export;
  const ts = timing.sceneAt(now);
  return (
    <div className="editor-page">
      <Header title={p.title}>
        {status?.job?.status === 'running' && <span className="small warnc">Analyse läuft: {status.job.step} …</span>}
        <span className={`save ${st.error ? 'bad' : ''}`}>{st.error ?? (st.saving ? 'speichert …' : st.dirty ? 'ungespeichert' : 'gespeichert')}</span>
        <button disabled={!st.dirty || st.saving} onClick={() => void store.save()} title="Strg+S – wird sonst automatisch gespeichert">Speichern</button>
        <button disabled={!st.canUndo || !!st.locked} onClick={() => store.doUndo()} title="Strg+Z">↶</button>
        <button disabled={!st.canRedo || !!st.locked} onClick={() => store.doRedo()} title="Strg+Y">↷</button>
        {st.error && <button onClick={() => store.load(pid)}>neu laden</button>}
        <span className="sep" />
        {exp?.status === 'running' ? (
          <span className="small link" onClick={() => setTab('exports')}>{exp.phase && exp.phase !== 'render' ? `MP4: erzeuge Version „${exp.phase}“ …` : `MP4 wird gerendert … ${Math.round((exp.progress ?? 0) * 100)} %`}</span>
        ) : (
          <>
            {exp?.status === 'done' && <button className="link ok small" onClick={() => setTab('exports')}>✓ Export fertig – anzeigen</button>}
            {exp?.status === 'error' && <span className="small err">Export fehlgeschlagen</span>}
            <button title="die aktuelle Szene (±1 s) als schnelle 720p-Vorschau – zum Prüfen in einem Videoplayer" onClick={() => ts && api.exportStart(pid, ['preview'], [Math.max(0, ts.t0 - 1), Math.min(timing.duration, ts.t1 + 1)]).catch((e) => alert(e.message))}>Szene als MP4</button>
            <button className="primary" onClick={() => { setExportOpen(true); setTab('exports'); }}>MP4 exportieren …</button>
          </>
        )}
      </Header>
      <div className="workspace">
        <div className="left">
          <div className="stage-wrap">
            <div className="stage" ref={stageRef} />
            {st.locked && <div className="locked">{st.locked}</div>}
          </div>
          <div className="transport">
            <button className="play" onClick={toggle}>{playing ? '❚❚' : '▶'}</button>
            <span className="time">{fmt(now)} / {fmt(timing.duration)}</span>
            <span className="scene-name">{ts ? `${ts.scene.name ?? ts.scene.id}` : ''}</span>
            <span className="grow" />
            <label className="small">
              <input type="checkbox" checked={loop} onChange={(e) => setLoop(e.target.checked)} /> Szene wiederholen (L)
            </label>
            <select value={rate} onChange={(e) => setRate(+e.target.value)} title="Tempo der Vorschau">
              <option value={0.5}>0,5×</option>
              <option value={0.75}>0,75×</option>
              <option value={1}>1×</option>
            </select>
          </div>
        </div>
        <div className="right">
          <div className="tabs">
            <button className={tab === 'scenes' ? 'on' : ''} onClick={() => setTab('scenes')}>Szenen</button>
            <button className={tab === 'insp' ? 'on' : ''} onClick={() => setTab('insp')}>Eigenschaften</button>
            <button className={tab === 'chat' ? 'on' : ''} onClick={() => setTab('chat')}>Assistent {status?.chat.status === 'running' ? '…' : ''}</button>
            <button className={tab === 'exports' ? 'on' : ''} onClick={() => setTab('exports')}>Exporte {status?.export?.status === 'running' ? `${Math.round((status.export.progress ?? 0) * 100)} %` : ''}</button>
          </div>
          <div className="panel">
            {tab === 'exports' ? (
              <ExportsPanel pid={pid} job={status?.export} onNew={() => setExportOpen(true)} />
            ) : tab === 'scenes' ? (
              <SceneList p={p} timing={timing} sel={st.selection} now={now} onSeek={seek} onOpen={() => setTab('insp')} />
            ) : tab === 'insp' ? (
              <Inspector p={p} timing={timing} sel={st.selection} now={now} onSeek={seek} />
            ) : (
              <Chat p={p} timing={timing} sel={st.selection} now={now} running={status?.chat.status === 'running'} />
            )}
          </div>
        </div>
      </div>
      {exportOpen && <ExportDialog pid={pid} duration={timing.duration} scene={ts ? { name: ts.scene.name ?? ts.scene.id, t0: ts.t0, t1: ts.t1 } : null} onClose={() => setExportOpen(false)} />}
      <Timeline project={p} timing={timing} getTime={getTime} playing={playing} selection={st.selection} locked={!!st.locked} onSeek={seek} />
      <div className="keys dim small">
        Änderungen werden automatisch gespeichert (Strg+S sofort) · Leertaste Play/Pause · ←/→ Szene zurück/vor · Shift+←/→ ±1 s · , / . Wort ±10 ms · T Tap-Sync · L Szene wiederholen · Entf Zeile (nicht) gesungen · Strg+Z/Y
      </div>
    </div>
  );
}

function Header({ title, children }: { title: string; children?: React.ReactNode }) {
  return (
    <header className="top">
      <a href="#/" className="brand">◀ Studio</a>
      <h1>{title}</h1>
      <span className="grow" />
      {children}
    </header>
  );
}
