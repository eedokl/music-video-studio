// Project format (see docs/project-format.md) – shared by preview, editor and export.
import type { Look, Shot } from './engine/concert';

export type Anchor =
  | { kind: 'auto' }
  | { kind: 'beat'; beat: number; offset?: number }
  | { kind: 'bar'; bar: number; offset?: number }
  | { kind: 'word'; line: string; word: number; edge?: 'start' | 'end'; offset?: number }
  | { kind: 'time'; t: number };

export interface Word {
  w: string;
  t: number;
  e: number;
}
export interface Line {
  id: string;
  section: string;
  text: string;
  unsung?: boolean;
  singer?: 'lead' | 'backing' | 'all';
  heard?: number;
  words: Word[];
}
export interface WallSpec {
  type: string;
  params?: Record<string, unknown>;
  module?: string;
  fn?: string;
}
export interface Scene {
  id: string;
  name?: string;
  start: Anchor;
  lines: string[];
  shot?: Shot;
  seed?: number;
  look?: string | Look;
  wall?: WallSpec;
  /** legacy world: id of the original scene this studio scene plays */
  legacy?: string;
  theme?: string;
  three?: string | null;
  lyr?: 'low' | 'big' | 'side' | 'none';
  held?: Record<string, string>;
  cam?: string;
  notes?: string;
}
export interface StudioEvent {
  type: 'co2' | 'sparks' | 'confetti' | 'fireworks';
  at: Anchor;
  until?: Anchor;
}
export interface HeldTrack {
  name: string;
  line: string;
  word: number;
  t0: number;
  fps: number;
  env: number[];
  pitch: number[];
}
export interface Grid {
  mode: 'fixed' | 'follow';
  bpm: number;
  offset: number;
  detected: number[];
  fixed: number[];
  beats: number[];
  beatsPerBar: number;
  downbeatPhase: number;
  residualMs?: number;
  source?: string;
}
export interface Project {
  format: number;
  id: string;
  title: string;
  storyline?: string;
  stylePrompt?: string;
  world?: 'concert' | 'legacy' | string;
  /** imported engine: original scenes + old line index → studio line id */
  legacy?: { engine: string; lineMap: (string | null)[]; scenes: { id: string; three?: string | null; theme?: string | null }[]; built?: number };
  status?: 'analyzing' | 'ready' | 'error';
  audio: { mix: string; vocals?: string; stems?: Record<string, string>; duration: number; stemCheck?: { status: string; medianLag: number; spread: number; lenStems: number; lenMix: number } };
  grid: Grid;
  lyrics: { lead: number; lines: Line[] };
  hits: { hits: number[]; big: number[] };
  held: HeldTrack[];
  looks: Record<string, Look>;
  scenes: Scene[];
  events: StudioEvent[];
  settings: { readHold: number; previewOffset?: number };
  lastUpdate?: { added: { id: string; text: string }[]; changed: { id: string; text: string }[]; removed: { id: string; text: string }[]; medianShift: number; legacyNote?: boolean };
}
