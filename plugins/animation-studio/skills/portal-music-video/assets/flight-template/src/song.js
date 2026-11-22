// The song's data. WRITTEN BY flight.py data (from the song project's analysis) - do not edit by hand; a film's own
// additions (fonts, hand-picked times) belong in a file of their own, or below the marker line at the end.
// This copy is a placeholder so that the template runs before a song is installed.

export const BPM = 120;
export const OFFSET = 0; // first downbeat of the song, seconds
export const BEAT = 60 / BPM;
export const FROM = 0; // the film is the whole song
export const SONG_END = 16;

export const V = 6; // flight speed, world units per second - the same in every world
export const STEP = V * BEAT; // distance flown per beat: everything along the road is spaced in STEPs
export const EYE = 1.6; // height of the camera above the road

// every sung line: the words as shown (upper case) and when each word starts (song seconds)
export const LINES = [
  { text: 'Lights on the stage', section: 0, words: ['LIGHTS', 'ON', 'THE', 'STAGE'], at: [1.0, 1.4, 1.7, 2.0] },
  { text: 'we sing tonight', section: 1, words: ['WE', 'SING', 'TONIGHT'], at: [9.0, 9.5, 10.0] },
];
// the song cut into worlds: every part starts on a bar line; beats may be fractional in the first and last part
export const SECTIONS = [
  { name: 'Verse', beats: 16, lines: [0] },
  { name: 'Chorus', beats: 16, lines: [1] },
];

// ---- below this line flight.py data keeps what you add ----
