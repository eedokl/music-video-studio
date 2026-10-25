// Exports of the project: running export (progress, cancel), finished MP4s (play, download, delete),
// open the folder in Explorer.
import { useEffect, useState } from 'react';
import { api, fileUrl, type JobState } from '../api';

interface ExportFile {
  name: string;
  size: number;
  mtime: number;
  kind: string;
}
const KIND: Record<string, string> = { full: 'Volle Qualität', compressed: 'Komprimiert', small: 'Klein', mail: 'Mail', preview: 'Vorschau' };

export function ExportsPanel({ pid, job, onNew }: { pid: string; job: JobState | undefined; onNew: () => void }) {
  const [files, setFiles] = useState<ExportFile[]>([]);
  const [folder, setFolder] = useState('');
  const [play, setPlay] = useState<string | null>(null);
  const load = () =>
    api.exports(pid).then((r) => {
      setFiles(r.files);
      setFolder(r.folder);
    });
  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pid, job?.status, job?.files?.length]);

  const running = job?.status === 'running';
  return (
    <div className="exports">
      <div className="buttons">
        <button className="primary" disabled={running} onClick={onNew}>Neuer Export …</button>
        <button onClick={() => void api.openFolder(pid)} title={folder}>Ordner öffnen</button>
      </div>
      {running && (
        <div className="exp-run">
          <div className="small">{job?.phase && job.phase !== 'render' ? `erzeuge Version „${KIND[job.phase] ?? job.phase}“ …` : `wird gerendert … ${Math.round((job?.progress ?? 0) * 100)} %`}</div>
          <div className="bar"><div style={{ width: `${Math.round((job?.progress ?? 0) * 100)}%` }} /></div>
          <button className="danger" onClick={() => confirm('Export abbrechen?') && void api.cancelExport(pid)}>Abbrechen</button>
        </div>
      )}
      {job?.status === 'error' && <div className="err small">Export fehlgeschlagen: {job.error}</div>}
      {job?.status === 'cancelled' && <div className="small dim">Export abgebrochen.</div>}
      <div className="small dim">{folder}</div>
      {files.length === 0 && <div className="dim small">Noch keine Exporte.</div>}
      {files.map((f) => (
        <div key={f.name} className="exp-row">
          <div className="exp-main">
            <b title={f.name}>{f.name}</b>
            <span className="small dim">
              {KIND[f.kind] ?? f.kind} · {(f.size / 1048576).toFixed(1)} MB · {new Date(f.mtime * 1000).toLocaleString('de-DE')}
            </span>
          </div>
          <div className="exp-act">
            <button title="abspielen" onClick={() => setPlay(f.name)}>▶</button>
            <a className="button" title="herunterladen" href={fileUrl(pid)(`out/${f.name}`)} download={f.name}>⬇</a>
            <button
              title="löschen"
              className="danger"
              onClick={() => confirm(`„${f.name}“ löschen?`) && void api.deleteExport(pid, f.name).then(load)}
            >
              ✕
            </button>
          </div>
        </div>
      ))}
      {play && (
        <div className="modal-bg" onClick={() => setPlay(null)}>
          <div className="modal player" onClick={(e) => e.stopPropagation()} onKeyDown={(e) => e.stopPropagation()}>
            <div className="player-head">
              <b>{play}</b>
              <button onClick={() => setPlay(null)}>Schließen</button>
            </div>
            <video src={fileUrl(pid)(`out/${play}`)} controls autoPlay />
          </div>
        </div>
      )}
    </div>
  );
}
