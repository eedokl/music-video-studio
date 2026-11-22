// The plan of the flight: which world for which part of the song, in order. YOURS TO REWRITE.
//
// As delivered every part of the song (SECTIONS in song.js) gets one of the three starter worlds in turn, with the
// lines sung in it - enough to fly through the whole song at once and see where the portals fall. Then replace
// them, part by part, with worlds made for this song (references/world-contract.md of the skill).
//
// An entry is { mod, beats, lines } or a world module alone (then the module's own `beats` count and the world
// reads its lines from song.js itself). The beats of all entries together are the length of the song.
import { LINES, SECTIONS } from './song.js';
import * as gate_wire from './worlds/gate_wire.js';
import * as mirror_hall from './worlds/mirror_hall.js';
import * as pixel_hall from './worlds/pixel_hall.js';

const STARTERS = [gate_wire, pixel_hall, mirror_hall];

export const COMPANION = true; // a small body that flies along through every portal (false: nothing flies along)
export const END_YEAR = null; // worlds with a `year`: the number the last world's label runs to (null = it stands)
export const ORDER = SECTIONS.map((s, i) => ({ mod: STARTERS[i % STARTERS.length], beats: s.beats, lines: s.lines.map((k) => LINES[k]) }));
