// Chat with the scene assistant (Claude Code on this machine). The current selection and playhead
// are sent along as context, so "replace this scene with …" knows what "this" is.
import { useEffect, useRef, useState } from 'react';
import { api, type ChatMsg, fileUrl } from '../api';
import type { Timing } from '../engine/timing';
import type { Project } from '../types';
import { type Selection, store } from './store';

const fmt = (t: number) => `${Math.floor(t / 60)}:${(t % 60).toFixed(1).padStart(4, '0')}`;

export function contextOf(p: Project, timing: Timing, sel: Selection, now: number) {
  const out = [`playhead: ${fmt(now)} (${now.toFixed(2)} s)`];
  const ts = timing.sceneAt(now);
  if (ts) out.push(`scene at playhead: ${ts.scene.id} "${ts.scene.name ?? ''}" ${fmt(ts.t0)}–${fmt(ts.t1)}`);
  if (sel.kind === 'scene') {
    const s = timing.scenes.find((x) => x.scene.id === sel.id);
    if (s) out.push(`selected scene: ${s.scene.id} "${s.scene.name ?? ''}" ${fmt(s.t0)}–${fmt(s.t1)}, lines ${s.scene.lines.join(',')}`);
  }
  if (sel.kind === 'line' || sel.kind === 'word') {
    const id = sel.kind === 'line' ? sel.id : sel.line;
    const l = p.lyrics.lines.find((x) => x.id === id);
    if (l) out.push(`selected line: ${l.id} "${l.text}"${sel.kind === 'word' ? `, word ${sel.word} "${l.words[sel.word]?.w}"` : ''}`);
  }
  if (sel.kind === 'event') out.push(`selected event: index ${sel.index} (${p.events[sel.index]?.type})`);
  return out.join('\n');
}

export function Chat({ p, timing, sel, now, running }: { p: Project; timing: Timing; sel: Selection; now: number; running: boolean }) {
  const [msgs, setMsgs] = useState<ChatMsg[]>([]);
  const [text, setText] = useState('');
  const [err, setErr] = useState('');
  const list = useRef<HTMLDivElement>(null);
  const load = () => api.chatHistory(p.id).then((r) => setMsgs(r.messages));
  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [p.id, running]);
  useEffect(() => {
    list.current?.scrollTo(0, list.current.scrollHeight);
  }, [msgs.length, running]);

  const send = async () => {
    const t = text.trim();
    if (!t || running) return;
    setErr('');
    await store.save();
    try {
      await api.chat(p.id, t, contextOf(p, timing, sel, now));
      setText('');
      setMsgs((m) => [...m, { role: 'user', text: t, t: Date.now() / 1000 }]);
      store.lock('Der Assistent bearbeitet das Projekt …');
    } catch (e) {
      setErr((e as Error).message);
    }
  };

  return (
    <div className="chat">
      <div className="chat-head">
        <b>Assistent</b>
        <span className="dim small">Claude Code · kennt Auswahl + Playhead</span>
        <button className="link" onClick={() => confirm('Chatverlauf löschen und neu beginnen?') && api.chatReset(p.id).then(load)}>neu</button>
      </div>
      <div className="chat-list" ref={list}>
        {msgs.length === 0 && (
          <div className="dim small hint">
            Beispiele:
            <br />„Ersetze die ausgewählte Szene durch eine Nahaufnahme der Sängerin mit rotem Licht.“
            <br />„Auf der LED-Wand bei ‚Silicon Valley‘ eine Rakete statt der Kurve.“
            <br />„Erstelle aus der Storyline ein neues Storyboard für den zweiten Refrain.“
          </div>
        )}
        {msgs.map((m, i) => (
          <div key={i} className={`msg ${m.role} ${m.ok === false ? 'bad' : ''}`}>
            {m.text}
            {m.role === 'assistant' && m.changed && <div className="small dim">✓ Projekt geändert</div>}
            {m.images && m.images.length > 0 && (
              <div className="chat-shots">
                {m.images.map((src) => (
                  <a key={src} href={fileUrl(p.id)(src) + `?t=${m.t}`} target="_blank" rel="noreferrer" title="Kontrollbild des Assistenten – in groß öffnen">
                    <img src={fileUrl(p.id)(src) + `?t=${m.t}`} alt={src} />
                  </a>
                ))}
              </div>
            )}
          </div>
        ))}
        {running && <div className="msg assistant thinking">denkt nach und bearbeitet …</div>}
      </div>
      {err && <div className="err small">{err}</div>}
      <div className="chat-input">
        <textarea
          rows={3}
          placeholder="Was soll sich ändern? (Strg+Enter senden)"
          value={text}
          disabled={running}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) void send();
            e.stopPropagation();
          }}
        />
        <button onClick={() => void send()} disabled={running || !text.trim()}>
          Senden
        </button>
      </div>
    </div>
  );
}
