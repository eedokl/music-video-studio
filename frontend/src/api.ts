import type { Project } from './types';

export const fileUrl = (pid: string) => (rel: string) => `/api/projects/${pid}/files/${rel.split('/').map(encodeURIComponent).join('/')}`;

async function j<T>(r: Response): Promise<T> {
  if (!r.ok) {
    let msg = `${r.status}`;
    try {
      msg = (await r.json()).detail ?? msg;
    } catch {
      /* not json */
    }
    throw Object.assign(new Error(msg), { status: r.status });
  }
  return r.json() as Promise<T>;
}

export interface JobState {
  status: 'running' | 'done' | 'error' | 'idle' | 'cancelled';
  step?: string;
  steps?: string[];
  log?: string[];
  error?: string | null;
  progress?: number;
  phase?: string;
  files?: string[];
}
export interface Status {
  version: number;
  job: JobState | null;
  chat: { status: 'running' | 'idle' };
  export: JobState;
}
export interface ChatMsg {
  role: 'user' | 'assistant';
  text: string;
  context?: string;
  ok?: boolean;
  changed?: boolean;
  images?: string[];
  t: number;
}

export const api = {
  list: () => fetch('/api/projects').then((r) => j<{ id: string; title: string; duration: number; updated: number; status: string }[]>(r)),
  async get(pid: string) {
    const r = await fetch(`/api/projects/${pid}`);
    const p = await j<Project>(r);
    return { project: p, version: Number(r.headers.get('X-Version') ?? 0) };
  },
  put: (pid: string, p: Project, base: number) =>
    fetch(`/api/projects/${pid}?base=${base}`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(p) }).then((r) => j<{ version: number; lineMap?: unknown[] }>(r)),
  status: (pid: string) => fetch(`/api/projects/${pid}/status`).then((r) => j<Status>(r)),
  create: (fd: FormData) => fetch('/api/projects', { method: 'POST', body: fd }).then((r) => j<{ id: string }>(r)),
  analyze: (pid: string, step = 'prepare', keep = false) => fetch(`/api/projects/${pid}/analyze?step=${step}&keep=${keep}`, { method: 'POST' }).then((r) => j(r)),
  storyboard: (pid: string) => fetch(`/api/projects/${pid}/storyboard`, { method: 'POST' }).then((r) => j<{ version: number }>(r)),
  gridMode: (pid: string, mode: string) => fetch(`/api/projects/${pid}/grid`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ mode }) }).then((r) => j<{ version: number }>(r)),
  legacyBuild: (pid: string) => fetch(`/api/projects/${pid}/legacy/build`, { method: 'POST' }).then((r) => j<{ log: string }>(r)),
  lyricsText: (pid: string) => fetch(`/api/projects/${pid}/lyrics-text`).then((r) => j<{ lyrics: string }>(r)),
  updateAudio: (pid: string, fd: FormData) => fetch(`/api/projects/${pid}/update-audio`, { method: 'POST', body: fd }).then((r) => j<{ matched: number; new: number; changed: number; removed: number }>(r)),
  history: (pid: string) => fetch(`/api/projects/${pid}/history`).then((r) => j<string[]>(r)),
  restore: (pid: string, name: string) => fetch(`/api/projects/${pid}/history/${encodeURIComponent(name)}`, { method: 'POST' }).then((r) => j<{ version: number }>(r)),
  duplicate: (pid: string, title: string) => fetch(`/api/projects/${pid}/duplicate`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ title }) }).then((r) => j<{ id: string }>(r)),
  importVideo: (path: string, title: string) => fetch('/api/projects/import-video', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ path, title }) }).then((r) => j<{ id: string }>(r)),
  exports: (pid: string) => fetch(`/api/projects/${pid}/exports`).then((r) => j<{ files: { name: string; size: number; mtime: number; kind: string }[]; folder: string }>(r)),
  deleteExport: (pid: string, name: string) => fetch(`/api/projects/${pid}/exports/${encodeURIComponent(name)}`, { method: 'DELETE' }).then((r) => j(r)),
  openFolder: (pid: string) => fetch(`/api/projects/${pid}/exports/open-folder`, { method: 'POST' }).then((r) => j(r)),
  cancelExport: (pid: string) => fetch(`/api/projects/${pid}/export`, { method: 'DELETE' }).then((r) => j(r)),
  peaks: (pid: string, src: string) => fetch(`/api/projects/${pid}/peaks?src=${src}`).then((r) => j<{ fps: number; max: number[]; min: number[] }>(r)),
  chatHistory: (pid: string) => fetch(`/api/projects/${pid}/chat`).then((r) => j<{ messages: ChatMsg[]; state: { status: string } }>(r)),
  chat: (pid: string, text: string, context: string) =>
    fetch(`/api/projects/${pid}/chat`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ text, context }) }).then((r) => j(r)),
  chatReset: (pid: string) => fetch(`/api/projects/${pid}/chat`, { method: 'DELETE' }).then((r) => j(r)),
  exportStart: (pid: string, variants: string[], range?: [number, number]) =>
    fetch(`/api/projects/${pid}/export`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ variants, start: range?.[0] ?? null, end: range?.[1] ?? null }) }).then((r) => j(r)),
};
