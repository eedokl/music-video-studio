// Editor state: the project being edited, undo/redo, selection, autosave.
// React components subscribe with useEditor(); all changes go through edit().

import { useSyncExternalStore } from 'react';
import { api } from '../api';
import type { Project } from '../types';

export type Selection =
  | { kind: 'none' }
  | { kind: 'scene'; id: string }
  | { kind: 'line'; id: string }
  | { kind: 'word'; line: string; word: number }
  | { kind: 'event'; index: number };

interface State {
  pid: string;
  project: Project | null;
  version: number;
  rev: number; // bumps on every change (re-render trigger for the preview)
  selection: Selection;
  dirty: boolean;
  saving: boolean;
  locked: string | null; // reason the editor is read-only (chat assistant working)
  error: string | null;
  canUndo: boolean;
  canRedo: boolean;
}

class EditorStore {
  state: State = { pid: '', project: null, version: 0, rev: 0, selection: { kind: 'none' }, dirty: false, saving: false, locked: null, error: null, canUndo: false, canRedo: false };
  private subs = new Set<() => void>();
  private undo: Project[] = [];
  private redo: Project[] = [];
  private saveTimer: number | undefined;
  private lastLabel = '';
  private lastLabelAt = 0;

  subscribe = (f: () => void) => {
    this.subs.add(f);
    return () => this.subs.delete(f);
  };
  get = () => this.state;
  private set(p: Partial<State>) {
    this.state = { ...this.state, ...p, canUndo: this.undo.length > 0, canRedo: this.redo.length > 0 };
    this.subs.forEach((f) => f());
  }

  async load(pid: string) {
    const { project, version } = await api.get(pid);
    this.undo = [];
    this.redo = [];
    this.set({ pid, project, version, rev: this.state.rev + 1, dirty: false, error: null });
  }
  /** reload after the server changed the project (chat, re-analysis) */
  async reload() {
    if (!this.state.pid) return;
    const { project, version } = await api.get(this.state.pid);
    if (this.state.project) this.undo.push(this.state.project);
    this.set({ project, version, rev: this.state.rev + 1, dirty: false });
  }

  /** change the project. Consecutive edits with the same label within 1.5 s merge into one undo step. */
  edit(label: string, fn: (p: Project) => void) {
    const p = this.state.project;
    if (!p || this.state.locked) return;
    const next = structuredClone(p);
    fn(next);
    const now = performance.now();
    if (!(label === this.lastLabel && now - this.lastLabelAt < 1500)) this.undo.push(p);
    if (this.undo.length > 200) this.undo.shift();
    this.lastLabel = label;
    this.lastLabelAt = now;
    this.redo = [];
    this.set({ project: next, rev: this.state.rev + 1, dirty: true });
    this.scheduleSave();
  }
  doUndo() {
    const prev = this.undo.pop();
    if (!prev || !this.state.project || this.state.locked) return;
    this.redo.push(this.state.project);
    this.lastLabel = '';
    this.set({ project: prev, rev: this.state.rev + 1, dirty: true });
    this.scheduleSave();
  }
  doRedo() {
    const nxt = this.redo.pop();
    if (!nxt || !this.state.project || this.state.locked) return;
    this.undo.push(this.state.project);
    this.set({ project: nxt, rev: this.state.rev + 1, dirty: true });
    this.scheduleSave();
  }
  select(s: Selection) {
    this.set({ selection: s });
  }
  lock(reason: string | null) {
    this.set({ locked: reason });
  }

  private scheduleSave() {
    window.clearTimeout(this.saveTimer);
    this.saveTimer = window.setTimeout(() => void this.save(), 700);
  }
  async save() {
    window.clearTimeout(this.saveTimer);
    const { project, pid, version, dirty } = this.state;
    if (!project || !dirty) return;
    this.set({ saving: true });
    try {
      const r = await api.put(pid, project, version);
      const cur = this.state.project;
      if (r.lineMap && cur?.legacy && JSON.stringify(cur.legacy.lineMap) !== JSON.stringify(r.lineMap)) {
        // imported engine: the server re-mapped the original lines onto the edited words
        const next = { ...cur, legacy: { ...cur.legacy, lineMap: r.lineMap as NonNullable<Project['legacy']>['lineMap'] } };
        this.set({ project: next, rev: this.state.rev + 1, version: r.version, saving: false, dirty: cur !== project, error: null });
        return;
      }
      this.set({ version: r.version, saving: false, dirty: this.state.project !== project, error: null });
    } catch (e) {
      const err = e as Error & { status?: number };
      this.set({ saving: false, error: err.status === 409 ? 'Das Projekt wurde auf dem Server geändert – bitte neu laden.' : `Speichern fehlgeschlagen: ${err.message}` });
    }
  }
}

export const store = new EditorStore();
export const useEditor = () => useSyncExternalStore(store.subscribe, store.get);
