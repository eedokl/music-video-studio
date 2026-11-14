"""The song project folder shared by all music-video skills of the plugin.

Layout: <project>/project.json, song.wav, lyrics.txt, stems/, analysis/ (song-analysis output), cache/.
project.json common keys (each user skill adds its own, e.g. "sections"):
  name, fps, source, lyrics, stems {lead, backing}, language, figures {name: {voice: male|female|announcer, ...}},
  narrator, announcements
"""
import json
import re
from pathlib import Path

import _studio  # noqa: E402
_studio.use("song-analysis")
import config  # noqa: E402

FPS = 24
CLEAN = "„“\"'().,!?…—-:;"


def word_matches(word, prefix):
    """Does a sung word match a trigger? Case-insensitive, punctuation at the word's edges stripped.

    "token"           prefix (default): matches "Tokens!", "token"
    "=pro"            exact word: matches "Pro." but not "Prompts" or "Pro-Limit"
    "re:^verkauf(t)?$"  regular expression (re.search) on the stripped word
    A trigger starting with "(" (also "=(" ) only matches calls in brackets: "(prompts" matches "(Prompts!)".
    """
    w, p = word.lower(), prefix.lower()
    if p.startswith("re:"):
        return re.search(prefix[3:], w.strip(CLEAN), re.I) is not None
    exact = p.startswith("=")
    if exact:
        p = p[1:]
    if p.startswith("(") and not w.startswith("("):
        return False
    return w.strip(CLEAN) == p.strip(CLEAN) if exact else w.strip(CLEAN).startswith(p.strip(CLEAN))


def allowed(spec, section):
    """Per-section filter of a rule (gag, sound, screen event ...): "sections": [names] = only there,
    "not_sections": [names] = never there. section = name of the section the event falls into (or None)."""
    only, never = spec.get("sections"), spec.get("not_sections")
    if only and section not in only:
        return False
    return not (never and section in never)


class Project:
    """project.json of one song project."""

    def __init__(self, folder="."):
        self.dir = Path(folder).resolve()
        self.file = self.dir / "project.json"
        if not self.file.exists():
            raise SystemExit(f"{self.file} missing - create the project first (song-analysis new_project.py)")
        self.p = json.loads(self.file.read_text(encoding="utf-8"))
        self.fps = self.p.get("fps", FPS)
        self.analysis = self.dir / "analysis"
        self.analysis.mkdir(exist_ok=True)
        self.cache = self.dir / "cache"
        self.cache.mkdir(exist_ok=True)

    def __getitem__(self, k):
        return self.p[k]

    def get(self, k, d=None):
        return self.p.get(k, d)

    def path(self, rel):
        """Path from project.json: relative to the project; 'skill:<skill>/<path>' = inside a skill of the plugin."""
        if rel is None:
            return None
        if str(rel).startswith("skill:"):
            name, _, sub = str(rel)[6:].partition("/")
            return _studio.skill_dir(name) / sub
        p = Path(rel)
        return p if p.is_absolute() else self.dir / p

    @property
    def song(self):
        return self.dir / "song.wav"

    def sheet(self):
        f = self.analysis / "song_sheet.json"
        if not f.exists():
            raise SystemExit("analysis/song_sheet.json missing - run song-analysis analyze.py first")
        return json.loads(f.read_text(encoding="utf-8"))

    def assignment(self):
        f = self.analysis / "assignment.json"
        if not f.exists():
            raise SystemExit("analysis/assignment.json missing - run song-analysis voices.py first")
        return json.loads(f.read_text(encoding="utf-8"))

    def markers(self):
        f = self.analysis / "markers.json"
        return json.loads(f.read_text(encoding="utf-8")) if f.exists() else []

    def sections(self):
        return self.p.get("sections", [])

    def section_at(self, t):
        """Name of the section that contains song second t (None in a gap)."""
        return next((s["name"] for s in self.sections() if float(s["from"]) <= t < float(s["to"])), None)

    def section(self, name):
        for s in self.sections():
            if s["name"] == name:
                return s
        raise SystemExit(f"section '{name}' not in project.json")
