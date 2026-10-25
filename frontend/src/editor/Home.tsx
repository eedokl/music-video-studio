// Project list + "new project" form (song, lyrics, storyline, optional Suno stems).
import { useEffect, useState } from 'react';
import { api } from '../api';

export function ProjectList() {
  const [list, setList] = useState<Awaited<ReturnType<typeof api.list>>>([]);
  useEffect(() => void api.list().then(setList), []);
  return (
    <div className="home">
      <header className="top">
        <span className="brand">Music Video Studio</span>
        <span className="grow" />
        <a className="button" href="#/import">Bestehendes Video importieren</a>
        <a className="button primary" href="#/new">+ Neues Projekt</a>
      </header>
      <div className="cards">
        {list.map((p) => (
          <a key={p.id} className="card" href={`#/p/${p.id}`}>
            <button
              className="card-copy"
              title="Als neues Projekt kopieren (z. B. für die nächste Version)"
              onClick={(e) => {
                e.preventDefault();
                e.stopPropagation();
                copyProject(p.id, p.title);
              }}
            >
              Kopieren
            </button>
            <b>{p.title}</b>
            <span className="dim small">
              {p.status === 'analyzing' ? 'Analyse läuft …' : p.status === 'error' ? 'Fehler bei der Analyse' : `${Math.floor((p.duration ?? 0) / 60)}:${String(Math.round((p.duration ?? 0) % 60)).padStart(2, '0')}`} · {new Date(p.updated * 1000).toLocaleString('de-DE')}
            </span>
          </a>
        ))}
        {list.length === 0 && <p className="dim">Noch keine Projekte – lege eines an.</p>}
      </div>
    </div>
  );
}

export function copyProject(id: string, title: string) {
  const name = prompt('Name des neuen Projekts:', `${title} (Kopie)`);
  if (!name) return;
  api
    .duplicate(id, name)
    .then((r) => (location.hash = `#/p/${r.id}`))
    .catch((e) => alert(e.message));
}

const OLD = String.raw`C:\Users\Oliver-2018\Desktop\Claude\cloud-engineering-music-video\ `.trim();

export function ImportVideo() {
  const [path, setPath] = useState('');
  const [title, setTitle] = useState('');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');
  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setErr('');
    try {
      const r = await api.importVideo(path, title);
      location.hash = `#/p/${r.id}`;
    } catch (x) {
      setErr((x as Error).message);
      setBusy(false);
    }
  };
  return (
    <div className="home">
      <header className="top">
        <a href="#/" className="brand">◀ Studio</a>
        <h1>Bestehendes Video importieren</h1>
      </header>
      <form className="newp" onSubmit={submit}>
        <p className="dim">
          Ein früher gebautes Video (eigener Code mit src/scenes.ts, src/lyrics.ts, public/song.wav) wird mit seinen Original-Szenen ins Studio übernommen. Song und Liedtext kommen aus dem Ordner; die Analyse misst das Timing neu (5–15 Minuten), danach werden die Szenen importiert.
        </p>
        <label>Ordner des Video-Projekts</label>
        <input value={path} onChange={(e) => setPath(e.target.value)} placeholder={`${OLD}roles-video`} required />
        <div className="small dim">
          Deine bisherigen Videos liegen in {OLD} (azure-version, roles-video, scenes-version, comfort-zone …). Pop-up und Rock nutzen eine ältere Engine und gehen noch nicht.
        </div>
        <label>Titel <span className="dim">(optional – sonst aus dem Projekt)</span></label>
        <input value={title} onChange={(e) => setTitle(e.target.value)} />
        {err && <div className="err">{err}</div>}
        <button className="primary" disabled={busy}>{busy ? 'startet …' : 'Importieren und analysieren'}</button>
      </form>
    </div>
  );
}

export function NewProject() {
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');
  const submit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setBusy(true);
    setErr('');
    try {
      const r = await api.create(new FormData(e.currentTarget));
      location.hash = `#/p/${r.id}`;
    } catch (x) {
      setErr((x as Error).message);
      setBusy(false);
    }
  };
  return (
    <div className="home">
      <header className="top">
        <a href="#/" className="brand">◀ Studio</a>
        <h1>Neues Projekt</h1>
      </header>
      <form className="newp" onSubmit={submit}>
        <label>Titel</label>
        <input name="title" required placeholder="z. B. Comfort Zone – Live" />
        <label>Song (WAV oder MP3)</label>
        <input name="song" type="file" accept=".wav,.mp3,.m4a,.flac" required />
        <label>
          Stems <span className="dim">(optional – z. B. Suno „Auto Split“: einzelne WAVs oder die ZIP-Datei. Müssen zur selben Fassung wie der Song gehören; das wird geprüft.)</span>
        </label>
        <input name="stems" type="file" accept=".wav,.zip" multiple />
        <label>Liedtext <span className="dim">(mit [Verse], [Chorus] …; so wie gesungen – Wiederholungen ausschreiben)</span></label>
        <textarea name="lyrics" rows={14} required />
        <label>Storyline <span className="dim">(was das Video erzählen soll – nutzt der Assistent für das Storyboard)</span></label>
        <textarea name="storyline" rows={5} />
        <label>Stil <span className="dim">(optional, z. B. der Suno-Style-Prompt)</span></label>
        <input name="stylePrompt" />
        {err && <div className="err">{err}</div>}
        <button className="primary" disabled={busy}>{busy ? 'lädt hoch …' : 'Anlegen und analysieren'}</button>
      </form>
    </div>
  );
}
