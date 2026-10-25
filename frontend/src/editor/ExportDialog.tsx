// Export dialog: choose which MP4 versions to render and which part of the song.
import { useState } from 'react';
import { api } from '../api';

const OPTIONS: { key: string; label: string; note: string }[] = [
  { key: 'full', label: 'Volle Qualität', note: '1920×1080 – Master, groß' },
  { key: 'compressed', label: 'Komprimiert', note: '1920×1080 – sieht gleich aus, ca. 4× kleiner' },
  { key: 'small', label: 'Klein', note: '1280×720 – unter 30 MB für den ganzen Song' },
  { key: 'mail', label: 'Mail', note: '960×540 – ca. 12 MB für den ganzen Song' },
];
const STORE_KEY = 'studio.export.variants';

function loadChoice(): string[] {
  try {
    const v = JSON.parse(localStorage.getItem(STORE_KEY) ?? 'null');
    if (Array.isArray(v) && v.length) return v;
  } catch {
    /* storage unavailable */
  }
  return ['full', 'small', 'mail'];
}

export function ExportDialog({ pid, duration, scene, onClose }: { pid: string; duration: number; scene: { name: string; t0: number; t1: number } | null; onClose: () => void }) {
  const [sel, setSel] = useState<string[]>(loadChoice);
  const [range, setRange] = useState<'all' | 'scene' | 'custom'>('all');
  const [from, setFrom] = useState(scene ? scene.t0.toFixed(1) : '0');
  const [to, setTo] = useState(scene ? scene.t1.toFixed(1) : duration.toFixed(1));
  const [err, setErr] = useState('');
  const toggle = (k: string) => setSel((s) => (s.includes(k) ? s.filter((x) => x !== k) : [...s, k]));
  const span = range === 'all' ? duration : range === 'scene' && scene ? scene.t1 - scene.t0 + 2 : Math.max(0, Number(to) - Number(from));
  const minutes = Math.max(1, Math.round((span * 30 * 0.18) / 60 + sel.filter((k) => k !== 'full').length * (span / 120)));
  const start = async () => {
    if (!sel.length) return setErr('Bitte mindestens eine Version wählen.');
    try {
      localStorage.setItem(STORE_KEY, JSON.stringify(sel));
    } catch {
      /* ignore */
    }
    const r: [number, number] | undefined =
      range === 'scene' && scene ? [Math.max(0, scene.t0 - 1), Math.min(duration, scene.t1 + 1)] : range === 'custom' ? [Number(from), Number(to)] : undefined;
    try {
      await api.exportStart(pid, sel, r);
      onClose();
    } catch (e) {
      setErr((e as Error).message);
    }
  };
  return (
    <div className="modal-bg" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()} onKeyDown={(e) => e.stopPropagation()}>
        <h3>MP4 exportieren</h3>
        <label>Versionen</label>
        {OPTIONS.map((o) => (
          <label key={o.key} className="check">
            <input type="checkbox" checked={sel.includes(o.key)} onChange={() => toggle(o.key)} /> <b>{o.label}</b> <span className="dim small">{o.note}</span>
          </label>
        ))}
        <label>Bereich</label>
        <label className="check">
          <input type="radio" checked={range === 'all'} onChange={() => setRange('all')} /> ganzes Video ({Math.floor(duration / 60)}:{String(Math.round(duration % 60)).padStart(2, '0')})
        </label>
        {scene && (
          <label className="check">
            <input type="radio" checked={range === 'scene'} onChange={() => setRange('scene')} /> aktuelle Szene „{scene.name}“ (±1 s)
          </label>
        )}
        <label className="check">
          <input type="radio" checked={range === 'custom'} onChange={() => setRange('custom')} /> von
          <input className="num" type="number" step={0.1} value={from} onChange={(e) => setFrom(e.target.value)} onFocus={() => setRange('custom')} /> bis
          <input className="num" type="number" step={0.1} value={to} onChange={(e) => setTo(e.target.value)} onFocus={() => setRange('custom')} /> s
        </label>
        <div className="small dim">Dauer ungefähr {minutes} min. Die Dateien landen im Projektordner unter „out“; vorhandene Dateien werden nicht überschrieben.</div>
        {err && <div className="err">{err}</div>}
        <div className="buttons">
          <button onClick={onClose}>Abbrechen</button>
          <button className="primary" onClick={() => void start()}>Export starten</button>
        </div>
      </div>
    </div>
  );
}
