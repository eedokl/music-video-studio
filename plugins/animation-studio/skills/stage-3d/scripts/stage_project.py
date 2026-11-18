"""The project file of a 3D film (project.json with "clips") - shared by stage_run.py, stage_speech.py, film-finish
clip_film.py and the animated-3d-film skill. Standard library only.

project.json:
  "title": "...", "kind": "film3d", "fps": 24 (fixed), "size": [1920, 1080], "seed": 4711, "ideas": [...],
  "clips": [{"name": "c01_intro", "frames": 240, "xfade": 0}, ...]   the edit, in order; scenes/<name>.py builds a
            clip; "xfade" = frames of the dissolve INTO the clip (0 = cut); "part": "credits" + "credits": "outtake" |
            "extra" = a clip of the end credits (rendered with the film, not cut into it; film-finish credits.py)
  "audio": "sound/film.wav" | null     the finished sound track (voices, music, effects) laid under the whole film
  "lines": [{"id": "l01", "who": "mo", "text": "Hello!", "audio": "speech/l01.wav"}]   spoken lines (lip sync)
  "voices": {...}, "language": "en"    for the voice block
  "look": "cinema" | "ad" | "standard" | "none"   finish of the film (film-finish clip_film.py)
  "palette": "ivory" | "petrol" | "forest" | {"base": ..., "accent": "#..."}   the colours of sets and props
  "lips": "soft" | "strong"            mouth opening while speaking
  "figures": "toy" | "ragdoll" | "puppet" | "stopmotion" | "clay" | "paper" | "marionette"   the make of the
                                       figures (stage_looks.py): as modelled, sewn rag dolls, hand puppets with flap
                                       mouths, gothic stop-motion puppets, plasticine, papercraft, string puppets
                                       | "rigify": realistic actors (stage_rig.py)
  "actors": {"mo": "tim"}              which actor (<actors>/<name>/figur.blend) plays which part ("rigify")
"""
import json
import os
from pathlib import Path

FPS = 24
QUALITIES = ("draft", "preview", "film", "final")
ENGINES = ("cycles", "eevee")
FOLDERS = QUALITIES + tuple(q + "_eevee" for q in QUALITIES)      # out/<clip>/<folder>: EEVEE renders are kept apart


def folder(q, engine="cycles"):
    return q if engine == "cycles" else f"{q}_{engine}"


class Film:
    def __init__(self, folder):
        self.dir = Path(folder).resolve()
        if self.dir.is_file():
            self.dir = self.dir.parent
        self.file = self.dir / "project.json"
        if not self.file.exists():
            raise SystemExit(f"{self.file} missing - not a 3D film project (animated-3d-film: film3d.py new)")
        try:
            self.p = json.loads(self.file.read_text(encoding="utf-8"))
        except ValueError as e:
            raise SystemExit(f"{self.file} is not valid JSON: {e}") from None

    def get(self, key, default=None):
        return self.p.get(key, default)

    def save(self):
        tmp = self.file.with_name(self.file.name + ".tmp")
        tmp.write_text(json.dumps(self.p, ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(tmp, self.file)

    def check(self):
        import project_check
        return project_check.require(self, skill="animated-3d-film")

    @property
    def clips(self):
        """[(name, frames, xfade)] in film order - all clips, also those of the end credits"""
        return [(c["name"], int(c["frames"]), int(c.get("xfade", 0))) for c in self.p.get("clips", [])]

    @property
    def film_clips(self):
        """the clips of the film itself (without "part": "credits": outtakes and extra scenes of the credits)"""
        return [(c["name"], int(c["frames"]), int(c.get("xfade", 0))) for c in self.p.get("clips", [])
                if c.get("part") != "credits"]

    @property
    def credit_clips(self):
        """[(name, frames, kind)] of the end credits: kind "outtake" or "extra" (project.json clips[].credits)"""
        return [(c["name"], int(c["frames"]), c.get("credits", "extra")) for c in self.p.get("clips", [])
                if c.get("part") == "credits"]

    def clip(self, name):
        for c in self.clips:
            if c[0] == name:
                return c
        raise SystemExit(f"clip '{name}' is not in project.json \"clips\" ({', '.join(c[0] for c in self.clips) or 'none'})")

    @property
    def size(self):
        s = self.p.get("size") or (1920, 1080)
        return int(s[0]), int(s[1])

    @property
    def frames(self):
        return sum(c[1] for c in self.clips)

    def out(self, clip, q=None):
        return self.dir / "out" / clip / q if q else self.dir / "out" / clip

    def frame(self, clip, q, f):
        return self.out(clip, q) / f"f_{f:04d}.png"

    def missing(self, clip, q):
        """frame numbers of a clip that are not rendered in quality q"""
        n = self.clip(clip)[1]
        have = {p.name for p in self.out(clip, q).glob("f_*.png")} if self.out(clip, q).is_dir() else set()
        return [f for f in range(1, n + 1) if f"f_{f:04d}.png" not in have]
