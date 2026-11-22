// Song data of the example film (a German synth-pop song about code review by machines), written by hand:
// beat grid and word times as measured from the song. A new project gets this file from flight.py data instead.

export const FONT_FLAT = '900 200px Archivo'; // the flat voice (supply the font, see README)
export const FONT_MONO = '600 200px "IBM Plex Mono"'; // vocoder and machine

export const BPM = 119.4; // the grid fitted to the bass drum (hits.json of the song project)
export const OFFSET = 0.056; // first downbeat of the song, seconds
export const BEAT = 60 / BPM;
export const FROM_BEAT = 104; // excerpt starts on this beat of the song (a downbeat, 52.476 s)
export const FROM = 0; // the film is the whole song

export const V = 6; // flight speed, world units per second - the same in every world
export const STEP = V * BEAT; // distance flown per beat: everything along the road is spaced in STEPs

/** seconds in the song -> seconds since the start of the excerpt */
export const s = (songSeconds) => songSeconds - FROM;

// word start times (song seconds)
export const LINES = {
  pruefe: { words: ['ICH', 'PRÜFE', 'NICHT.'], at: [54.0, 54.2, 54.48] },
  frei: { words: ['ICH', 'GEBE', 'FREI.'], at: [55.92, 56.06, 56.38] },
  drei: { words: ['DREI', 'SEKUNDEN.'], at: [58.24, 58.44] },
  vorbei: { words: ['SCHON', 'VORBEI.'], at: [60.12, 60.3] },
  gruen: { words: ['ALLES', 'GRÜN.'], at: [62.32, 62.58] },
  gut: { words: ['ALLES', 'GUT.'], at: [64.32, 64.6] },
  keiner: { words: ['KEINER', 'WEISS,'], at: [66.32, 66.6] },
  tut: { words: ['WAS', 'ES', 'TUT.'], at: [68.32, 68.48, 68.64] },
  aus: { words: ['SIEHT', 'GUT', 'AUS.'], at: [73.24, 73.66, 74.14] },
  raus: { words: ['RAUS.', 'RAUS.', 'RAUS.'], at: [81.26, 81.78, 82.3] },
  // verse 2
  mensch: { words: ['DER', 'MENSCH', 'GEHT', 'HEIM.'], at: [102.24, 102.34, 102.62, 102.84] },
  bleibt: { words: ['DIE', 'MASCHINE', 'BLEIBT.'], at: [104.24, 104.34, 104.72] },
  prueft: { words: ['DIE', 'MASCHINE', 'PRÜFT,'], at: [106.28, 106.36, 106.76] },
  schreibt: { words: ['WAS', 'DIE', 'MASCHINE', 'SCHREIBT.'], at: [107.76, 107.9, 108.06, 108.66] },
  rot: { words: ['DER', 'TEST', 'WAR', 'ROT.'], at: [110.24, 110.34, 110.64, 110.88] },
  fort: { words: ['DER', 'TEST', 'IST', 'FORT.'], at: [112.26, 112.36, 112.72, 113.0] },
  jetzt: { words: ['GRÜN', 'IST', 'JETZT'], at: [114.52, 114.78, 114.95] },
  ort: { words: ['AN', 'JEDEM', 'ORT.'], at: [115.32, 116.38, 116.8] },
  // sequence (vocoder), then the answer
  zeile: [
    { words: ['ZEILE', 'FÜR', 'ZEILE.'], at: [118.44, 118.84, 119.12], answer: { words: ['KEINER', 'LIEST.'], at: [120.1, 120.86] } },
    { words: ['ZEILE', 'FÜR', 'ZEILE.'], at: [122.46, 122.86, 123.16], answer: { words: ['KEINER', 'PRÜFT.'], at: [124.12, 124.88] } },
    { words: ['ZEILE', 'FÜR', 'ZEILE.'], at: [126.48, 126.88, 127.18], answer: { words: ['SCHNELLER.', 'SCHNELLER.'], at: [128.14, 129.12] } },
    { words: ['ZEILE', 'FÜR', 'ZEILE.'], at: [130.48, 130.88, 131.18], answer: { words: ['FREITAG.', 'FÜNF.'], at: [132.16, 133.18] } },
  ],
  // second hook
  aus2: { words: ['SIEHT', 'GUT', 'AUS.'], at: [137.56, 137.98, 138.46] },
  raus2: { words: ['RAUS.', 'RAUS.', 'RAUS.'], at: [145.58, 146.1, 146.62] },
  // breakdown (speech synthesis)
  recht1: { words: ['DU', 'HAST', 'VOLLKOMMEN', 'RECHT.'], at: [153.04, 153.16, 153.32, 154.06] },
  recht2: { words: ['DU', 'HAST', 'VOLLKOMMEN', 'RECHT.'], at: [157.04, 157.16, 157.32, 158.08] },
  fertig: { words: ['JETZT', 'IST', 'ES', 'FERTIG.'], at: [161.04, 161.22, 161.42, 161.56] },
  wirklich: { words: ['JETZT', 'ABER', 'WIRKLICH.'], at: [163.42, 163.86, 164.4] },
  // verse 3
  sonntag: { words: ['SONNTAG', 'FRÜH.'], at: [166.76, 167.2] },
  leer: { words: ['DER', 'SHOP', 'IST', 'LEER.'], at: [168.48, 168.62, 168.92, 169.1] },
  null: { words: ['NULL', 'EURO.', 'WELTWEIT.'], at: [170.46, 170.72, 171.02] },
  bitte: { words: ['BITTE', 'SEHR.'], at: [172.7, 173.02] },
  status: { words: ['DIE', 'STATUSSEITE:'], at: [174.5, 174.64] },
  stabil: { words: ['ALLES', 'STABIL.'], at: [176.76, 177.06] },
  maschine: { words: ['DIE', 'MASCHINE', 'BLEIBT'], at: [178.78, 178.9, 179.46] },
  kuehl: { words: ['GANZ', 'KÜHL.'], at: [180.9, 181.26] },
  // intro (speech synthesis)
  achtung: { words: ['ACHTUNG.'], at: [9.08] },
  ki: { words: ['WIR', 'SIND', 'JETZT', 'EIN', 'KI-UNTERNEHMEN.'], at: [12.72, 12.88, 13.06, 13.33, 13.56] },
  fragen: { words: ['FRAGEN', 'BITTE', 'AN', 'DEN', 'BOT.'], at: [18.4, 18.74, 19.14, 19.43, 19.64] },
  // second breakdown
  geloest: { words: ['PROBLEM', 'GELÖST.'], at: [183.4, 183.96] },
  geloescht: { words: ['SHOP', 'GELÖSCHT.'], at: [187.82, 188.2] },
  // last hook
  aus3: { words: ['SIEHT', 'GUT', 'AUS.'], at: [193.88, 194.3, 194.76] },
  raus3: { words: ['RAUS.', 'RAUS.', 'RAUS.'], at: [201.88, 202.4, 202.92] },
  bot: { words: ['BOT', 'PRÜFT', 'BOT.'], at: [209.92, 210.44, 210.96] },
  lot: { words: ['ALLES', 'IM', 'LOT.'], at: [218.12, 218.5, 218.8] },
  // outro
  laeuft1: { words: ['LÄUFT', 'GUT.', 'TSCHÜSS.', 'MAHLZEIT.'], at: [235.86, 236.56, 236.94, 237.86] },
  laeuft2: { words: ['LÄUFT', 'GUT.', 'TSCHÜSS.', 'MAHLZEIT.'], at: [243.9, 244.6, 244.98, 245.9] },
  uwe: { words: ['UWE.'], at: [251.44] },
  melden: { words: ['BITTE', 'MELDEN.'], at: [252.28, 252.5] },
};
// the vocoder sings "El-Ge-Te-Em"; on screen it is always LGTM. Syllables after the word start (from fabrik.ts HOOK).
export const HOOK_SYL = [0, 0.76, 1.25, 1.76];
export const HOOKS = [70.36, 78.4];
export const HOOKS2 = [134.68, 142.72];
export const HOOKS0 = [38.25, 46.29];
export const HOOKS3 = [191.02, 199.04, 207.06, 215.08];
export const SONG_END = 272.63;
export const EYE = 1.6; // height of the camera above the road
