import { useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { api, fileUrl } from './api';
import { Editor } from './editor/Editor';
import { ImportVideo, NewProject, ProjectList } from './editor/Home';
import { LegacyPlayer } from './engine/legacyPlayer';
import { Player } from './engine/player';
import './styles.css';

const params = new URLSearchParams(location.search);

// ---------------- render mode: the MP4 renderer opens ?render=1&project=ID and calls __renderFrame(t)
async function renderMode(pid: string) {
  document.body.classList.add('render');
  const root = document.getElementById('root')!;
  root.className = 'render-root';
  const { project, version } = await api.get(pid);
  const player = project.world === 'legacy' ? new LegacyPlayer(root, pid, true) : new Player(root, fileUrl(pid), true);
  await player.setProject(project, String(version));
  player.resize(window.innerWidth, window.innerHeight);
  const w = window as unknown as Record<string, unknown>;
  w.__renderFrame = (t: number) => player.renderAt(t);
  w.__duration = project.audio.duration;
  await document.fonts.load('400 80px "Anton"');
  await document.fonts.load('400 20px "Space Mono"');
  await document.fonts.load('700 20px "Space Mono"');
  await document.fonts.ready;
  player.renderAt(0);
  w.__ready = true;
}

function useHash() {
  const [h, setH] = useState(location.hash);
  useEffect(() => {
    const f = () => setH(location.hash);
    window.addEventListener('hashchange', f);
    return () => window.removeEventListener('hashchange', f);
  }, []);
  return h;
}

function App() {
  const h = useHash();
  const m = h.match(/^#\/p\/([a-z0-9-]+)/);
  if (m) return <Editor key={m[1]} pid={m[1]} />;
  if (h.startsWith('#/new')) return <NewProject />;
  if (h.startsWith('#/import')) return <ImportVideo />;
  return <ProjectList />;
}

if (params.has('render')) void renderMode(params.get('project') ?? '');
else createRoot(document.getElementById('root')!).render(<App />);
