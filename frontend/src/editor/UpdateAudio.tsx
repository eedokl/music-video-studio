// "Audio aktualisieren": a new version of the song (e.g. re-rendered in Suno with small lyric or timing
// changes) replaces the audio; the analysis runs again and the existing storyboard is carried over.
import { useEffect, useState } from 'react';
import { api } from '../api';
import { store } from './store';

export function UpdateAudio({ pid, onClose }: { pid: string; onClose: () => void }) {
  const [lyrics, setLyrics] = useState('');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');
  useEffect(() => {
    void api.lyricsText(pid).then((r) => setLyrics(r.lyrics));
  }, [pid]);
  const submit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    // read the form BEFORE any await – React clears e.currentTarget once the handler yields
    const fd = new FormData(e.currentTarget);
    fd.set('lyrics', lyrics);
    setBusy(true);
    setErr('');
    try {
      await store.save();
      await api.updateAudio(pid, fd);
      onClose();
    } catch (x) {
      setErr((x as Error).message);
      setBusy(false);
    }
  };
  return (
    <div className="modal-bg" onClick={onClose}>
      <form className="modal" onClick={(e) => e.stopPropagation()} onSubmit={submit} onKeyDown={(e) => e.stopPropagation()}>
        <h3>Audio aktualisieren</h3>
        <p className="small dim">
          Für eine überarbeitete Fassung des Songs (z. B. in Suno nachgebessert). Die neue Aufnahme wird komplett neu vermessen; Szenen, Effekte und Einstellungen bleiben.
          Zeilen werden über den Text wiedererkannt: unveränderte und leicht geänderte behalten ihre Szene, neue kommen in die Szene der Zeile davor, gestrichene fallen weg.
          Feste Zeitpunkte (Intro, Outro) wandern mit der neuen Aufnahme mit. Manuelle Wort-Korrekturen werden durch die neue Messung ersetzt.
        </p>
        <label>Neue Aufnahme (WAV/MP3)</label>
        <input name="song" type="file" accept=".wav,.mp3,.m4a,.flac" required />
        <label>
          Stems <span className="dim">(optional, aus derselben Suno-Fassung – ZIP oder WAVs)</span>
        </label>
        <input name="stems" type="file" accept=".wav,.zip" multiple />
        <label>Liedtext, wie jetzt gesungen (hier die Änderungen eintragen)</label>
        <textarea rows={14} value={lyrics} onChange={(e) => setLyrics(e.target.value)} />
        {err && <div className="err">{err}</div>}
        <div className="buttons">
          <button type="button" onClick={onClose}>Abbrechen</button>
          <button className="primary" disabled={busy}>{busy ? 'lädt hoch …' : 'Aktualisieren und neu vermessen'}</button>
        </div>
      </form>
    </div>
  );
}
