// The plan of the example film: fifteen worlds, a journey through the history of computer graphics and back.
// Every world module carries its own length (beats) and reads its lines from song.js by name.
import * as oszi from './worlds/oszi.js';
import * as urdraht from './worlds/urdraht.js';
import * as pruefstand from './worlds/pruefstand.js';
import * as alles_gruen from './worlds/alles_gruen.js';
import * as produktion from './worlds/produktion.js';
import * as raster from './worlds/raster.js';
import * as polygon from './worlds/polygon.js';
import * as textur from './worlds/textur.js';
import * as shader from './worlds/shader.js';
import * as spiegel from './worlds/spiegel.js';
import * as ki from './worlds/ki.js';
import * as leere from './worlds/leere.js';
import * as botstadt from './worlds/botstadt.js';
import * as rueckfall from './worlds/rueckfall.js';
import * as schluss from './worlds/schluss.js';

export const COMPANION = true; // the cube ("the change") that flies along and grows up with the machines
export const END_YEAR = 1962; // the last world's year runs back to where the first one starts
export const ORDER = [oszi, urdraht, pruefstand, alles_gruen, produktion, raster, polygon, textur, shader, spiegel, ki, leere, botstadt, rueckfall, schluss];
