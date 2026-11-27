# /// script
# requires-python = ">=3.12"
# dependencies = []
# [tool.uv]
# exclude-newer = "2026-11-14T00:00:00Z"
# ///
"""Check a project's settings up front - before any long step - so a typo stops the build in seconds, not after a
render: wrong types of shared keys, impossible sections (from >= to, negative, duplicate names), a TTS voice that is not in the cast, a talking slide figure
without mouth stages, sections whose frames were rendered for other times, unknown keys (did-you-mean).

  uv run project_check.py <project folder | project.json | clip.json | scene.json | short.json> [--skill <skill>]
  exit code 2 = errors (stop, nothing was built), 0 = fine (warnings are printed)

In a build script (every user skill calls it FIRST, before the first long step):
    import project_check; project_check.require(P, skill="animated-music-video")
    # P = song_project.Project, a folder, a json file or a dict (+ base= folder); prints the warnings and stops with
    # exit code 2 on errors. A child script started by an already checked build skips the repeated report.
    problems = project_check.check(P, skill=...)      # [Problem(level "error"|"warning", key, message)]
Frame size of the films: project_check.frame_size(p) -> (w, h) from project.json "size" (default 1280x720);
song_project.Project.size is the same; frame_scale(p) = h / 720 for pixel values designed at 1280x720.

The schema is plain Python data (SCHEMAS below, one dict per project family). A new project.json key MUST be added
there (CONVENTIONS.md) - otherwise every build warns about it as unknown.
"""
import argparse
import difflib
import json
import os
import struct
import sys
from collections import namedtuple
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILLS = HERE.parents[1]
DEFAULT_SIZE = (1280, 720)
REF_H = 720
Problem = namedtuple("Problem", "level key msg")

# ------------------------------------------------------------------ schema (plain data)
# A key spec: "type" = allowed JSON types ("str", "int", "number", "bool", "list", "dict", "null");
# "items" = type of every list entry; "need" = keys every dict entry must have; "fields" = specs of keys inside each
# dict entry (checked when present); "each" = spec of every value of a dict (figures, voices); "values" = allowed
# strings; "one_of" = each dict entry needs at least one of these keys; "doc" = what is expected (for the message).
NUM, INT, STR, BOOL, LIST, DICT, NULL = "number", "int", "str", "bool", "list", "dict", "null"
TRANSITION_KINDS = ("zoom_through", "glow", "screen_zoom", "iris", "white", "black")
VOICE_ROLES = ("male", "female", "announcer")         # song projects: who sings (song-analysis voices.py)
WORD_RULE = {"type": (LIST,), "items": DICT, "need": ("word",), "fields": {"word": {"type": (STR,)}},
             "doc": 'a list of rules [{"word": "token", ...}]'}
SOUND_RULE_FIELDS = {"sfx": {"type": (STR,)}, "word": {"type": (STR,)}, "at": {"type": (NUM,)},
                     "every": {"type": (NUM,)}, "marker": {"type": (STR,)}, "level": {"type": (NUM,)},
                     "pan": {"type": (NUM,)}, "offset": {"type": (NUM,)}, "dur": {"type": (NUM,)}}
SECTION_FIELDS = {"name": {"type": (STR,)}, "from": {"type": (NUM,)}, "to": {"type": (NUM,)},
                  "figures": {"type": (LIST,), "items": STR}, "set": {"type": (STR,)}, "lyrics": {"type": (BOOL,)},
                  "dance": {"type": (STR,), "values": ("chorus", "always", "never")}, "kind": {"type": (STR,)},
                  "acting": {"type": (BOOL, DICT)},
                  "face_fix": {"type": (BOOL,)}, "face_hint": {"type": (LIST,)},   # claudia face_fix.py
                  "take": {"type": (STR,), "values": ("short", "long")},   # claudia "takes": "mixed"
                  "relight": {"type": (DICT,), "doc": 'claudia relight.py: {"src", "light", "seeds", "size"} or {"keep": true}'}}

SHARED = {                                            # every project.json read by song_project.Project
    "name": {"type": (STR,)},
    "fps": {"type": (NUM,), "min": 1, "doc": "frames per second, a number such as 24"},
    "size": {"type": (LIST,), "doc": "[width, height] in pixels, even numbers, e.g. [1280, 720]"},
    "seed": {"type": (INT,)},
    "ideas": {"type": (LIST,), "items": DICT},
    "look": {"type": (STR, NULL), "doc": '"standard", "none" or a look folder'},
    "language": {"type": (STR,)},
    "figures": {"type": (DICT,), "each": {"type": (DICT,), "fields": {"voice": {"type": (STR,)}, "svg": {"type": (STR,)},
                                                                       "kind": {"type": (STR,)}, "size": {"type": (NUM,)}}},
                "doc": '{"tim": {"svg": ..., "voice": ...}, ...}'},
    "voices": {"type": (DICT,), "each": {"type": (DICT,)}, "doc": '{"<who>": {"engine": ..., "design": ...}}'},
    "sections": {"type": (LIST,), "items": DICT, "need": ("name", "from", "to"), "fields": SECTION_FIELDS,
                 "doc": 'a list [{"name": "chorus", "from": 0.0, "to": 12.5}, ...]'},
    "sounds": {"type": (BOOL, DICT, LIST, NULL), "items": DICT, "need": ("sfx",), "one_of": ("word", "at", "every", "marker"),
               "fields": SOUND_RULE_FIELDS,
               "doc": 'true / false, one rule {"sfx": ..., "word"|"at"|"every"|"marker": ...} or a list of such rules'},
    "gags": WORD_RULE, "screen": WORD_RULE, "steam": WORD_RULE, "gestures": WORD_RULE,
    "transitions": {"type": (LIST,), "items": DICT, "need": ("at",),
                    "fields": {"at": {"type": (NUM,)}, "kind": {"type": (STR,), "values": TRANSITION_KINDS}},
                    "doc": 'a list [{"at": 11.6, "kind": "glow"}, ...]'},
    "title": {"type": (DICT, NULL), "need": ("text", "from", "to"),
              "fields": {"text": {"type": (STR,)}, "from": {"type": (NUM,)}, "to": {"type": (NUM,)}},
              "doc": '{"text": "Title", "from": 0.5, "to": 3.5}'},
    "credits": {"type": (DICT, NULL)},
    "popups": {"type": (LIST,), "items": DICT}, "popup_credits": {"type": (LIST,), "items": DICT},
    "subtitles": {"type": (BOOL,)},
    "source": {"type": (DICT, STR, NULL)}, "lyrics": {"type": (STR, NULL)}, "stems": {"type": (DICT,)},
    "kind": {"type": (STR,)},
}
SONG = {**SHARED,                                     # music-video projects (song-analysis new_project.py and friends)
        "narrator": {"type": (STR, NULL)}, "announcements": {"type": (LIST,), "items": STR},
        "actions": {"type": (LIST,), "items": DICT}, "props": {"type": (LIST,), "items": DICT},
        "screen_badges": {"type": (LIST,), "items": DICT}, "screen_meter": {"type": (DICT, NULL)},
        "silhouettes": {"type": (LIST,), "items": DICT},
        "expressions": {"type": (LIST,), "items": DICT, "need": ("figure", "expression"),
                        "fields": {"figure": {"type": (STR,)},     # names: animated-music-video scene_acting.EXPRESSIONS
                                   "expression": {"type": (STR,), "values": ("grin", "skeptical", "shock", "angry", "sad")},
                                   "word": {"type": (STR,)}, "line": {"type": (STR,)}, "from": {"type": (NUM,)},
                                   "to": {"type": (NUM,)}, "duration": {"type": (NUM,), "min": 0.1}}},
        "acting": {"type": (BOOL, DICT), "doc": 'true / false or {"strength": 1.0, "glances": true, "nods": true, "brows": true}'},
        "lyrics_style": {"type": (STR, DICT)}, "lyrics_lines": {"type": (LIST,), "items": DICT},
        "lyrics_skip": {"type": (LIST,)}, "gag_size": {"type": (NUM,)},
        "sung_words": {"type": (STR, BOOL, NULL), "values": ("line_start",),          # song-analysis analyze.py
                       "doc": '"line_start" = Whisper\'s stable first word of a line replaces the lyric word; false = only warn'},
        "music_by": {"type": (STR, LIST, NULL)}, "song_title": {"type": (STR, NULL)},
        "bricks": {"type": (DICT,)},                                              # bricks-music-video
        "video": {"type": (STR,)}, "version": {"type": (STR,)}, "brief": {"type": (DICT,)},   # claudia / lyric
        "character_refs": {"type": (LIST, DICT)}, "characters": {"type": (DICT,)}, "character_library": {"type": (STR, LIST)}, "lead": {"type": (STR,)}, "variants": {"type": (INT, DICT)}, "finish": {"type": (DICT, STR)},
        "ai_label": {"type": (STR, BOOL, NULL)}, "lip_curve": {"type": (DICT, LIST, STR)},
        "mic": {"type": (STR,), "values": ("painted", "added"),       # claudia: headset painted with the start image, or
                "doc": '"added" = start image without a headset, the headset added by a second edit'},   # added after it
        "mic_tries": {"type": (INT,)}, "mic_repair": {"type": (BOOL,)},
        "face_fix": {"type": (BOOL, DICT), "doc": 'claudia face_fix.py: false = never, {"max_face": 85, "tracker": "auto"|"mediapipe"|"retinaface"}'},
        "pace": {"type": (STR,), "values": ("calm", "medium", "fast")}, "code_layer": {"type": (DICT,)},   # claudia code_film.py
        "takes": {"type": (STR,), "values": ("short", "long", "mixed"),         # claudia: sung takes of 6-9 s at 1024x576
                  "doc": '"long" = one take per two to four sung lines (plan.py --takes long); "mixed" = verses long, '
                         'chorus / hook short (shot "take": "long"|"short")'},
        "short_markers": {"type": (LIST,), "items": STR,              # claudia "takes": "mixed": parts cut short
                          "doc": 'marker words cut as short shots in "mixed" (default chorus, refrain, hook, drop)'},
        "pick_by": {"type": (STR,), "values": ("lips", "motion")},
        "delivery": {"type": (STR,), "values": ("song", "speech"),       # claudia: a spoken film -> "says the words"
                     "doc": '"speech" = the lip-sync prompts speak instead of sing (a sketch / dialogue film)'},     # claudia pick.py: the automatic take
        "dialogue": {"type": (DICT,), "doc": 'claudia dialogue_clips.py: {"image", "set", "who": {name: identifiers}, "off": [[from, to]], '
                                             '"clips": [{"name", "shots": [..], "cut": framing, "how": {shot: text}}]}'},
        "master": {"type": (DICT,), "doc": 'ai-video master_crops.py: {"image", "size": [w, h], "crops": {name: "w:h:x:y"}, '
                                           '"edits": {name: {"crop", "change"}}, "keep", "negative"}'},
        "relit_from": {"type": (DICT,), "doc": 'claudia relight.py: {"project", "light", "shots": {shot: {...}}}'},
        "identity": {"type": (STR,)}, "tempo": {"type": (DICT,)}, "word_passes": {"type": (LIST,)},   # lyric-music-video
        "flight": {"type": (STR,), "doc": "folder of the portal flight inside the project (new_flight.py)"},   # portal-music-video
        "held_max": {"type": (NUM,)}, "held_stretch": {"type": (BOOL, NUM, DICT)}, "held_style": {"type": (STR, DICT)},
        }
TALK = {**SHARED,                                     # talking-character (new_talk.py)
        "script": {"type": (STR,)}, "recording": {"type": (STR, NULL)}, "set": {"type": (STR,)},
        "direction": {"type": (DICT,)}, "camera": {"type": (STR, DICT, LIST)}, "close_zoom": {"type": (NUM,)},
        "view": {"type": (STR, LIST)}, "floor": {"type": (NUM,)}, "scale": {"type": (NUM,)},
        "push_in": {"type": (NUM,)}, "pronounce": {"type": (DICT,)}, "pause": {"type": (NUM, DICT)},
        }
SHORT = {                                             # animated-short short.json
    "title": {"type": (STR,)}, "seed": {"type": (INT,)}, "ideas": {"type": (LIST,), "items": DICT},
    "principles": {"type": (LIST,), "items": STR}, "beats": {"type": (LIST,), "items": LIST},
    "figure": {"type": (STR,)}, "final": {"type": (STR,)}, "look": {"type": (STR, NULL)},
}
DECK = {                                              # animated-powerpoint clip.json / scene.json
    "deck": {"type": (STR,)}, "slide": {"type": (INT,)}, "figures_dir": {"type": (STR,)},
    "size": {"type": (LIST,), "doc": "[width, height] in pixels, even numbers, e.g. [1920, 1080]"},
    "fps": {"type": (NUM,), "min": 1}, "seed": {"type": (INT,)}, "look": {"type": (STR, NULL)},
    "ending": {"type": (STR,), "values": ("stay", "return")}, "boil": {"type": (NUM,)}, "hold": {"type": (INT,)},
    "figures": {"type": (LIST, DICT)}, "tail": {"type": (INT,)}, "camera": {"type": (LIST,)}, "end": {"type": (INT, NULL)},
    "narration": {"type": (LIST,), "items": DICT, "need": ("id", "audio")},
    "sound": {"type": (BOOL,)}, "sounds": {"type": (LIST,), "items": DICT, "need": ("sfx",)},
    "voice_pan": {"type": (DICT,)}, "tag_hold": {"type": (INT, NUM)}, "spread": {"type": (NUM,)},
    "group_frames": {"type": (INT, LIST, DICT)}, "finale": {"type": (DICT, BOOL)}, "ideas": {"type": (LIST,)},
    "layers": {"type": (LIST,), "items": DICT}, "overlays": {"type": (LIST,), "items": DICT},
    "sprites": {"type": (LIST,), "items": DICT}, "steam": {"type": (LIST,), "items": DICT},
    "background": {"type": (STR,)}, "name": {"type": (STR,)},
    "lang": {"type": (STR,), "doc": "language of the narration for the word times, e.g. \"de\" (default: detected)"},
}
FILM3D = {                                            # animated-3d-film project.json (stage-3d stage_project.py)
    "title": {"type": (STR,)}, "kind": {"type": (STR,)}, "name": {"type": (STR,)},
    "fps": {"type": (NUM,), "min": 24, "max": 24, "doc": "24 (the 3D stage animates at 24 frames per second)"},
    "size": {"type": (LIST,), "doc": "[width, height] in pixels, even numbers, e.g. [1920, 1080]"},
    "seed": {"type": (INT,)}, "ideas": {"type": (LIST,), "items": DICT},
    "clips": {"type": (LIST,), "items": DICT, "need": ("name", "frames"),
              "fields": {"name": {"type": (STR,)}, "frames": {"type": (INT,), "min": 1},
                         "xfade": {"type": (INT,), "min": 0}, "about": {"type": (STR,)}},
              "doc": 'the edit in order: [{"name": "c01_intro", "frames": 240, "xfade": 0}, ...]'},
    "audio": {"type": (STR, NULL), "doc": "the finished sound track of the film, e.g. \"sound/film.wav\""},
    "lines": {"type": (LIST,), "items": DICT, "need": ("id", "who", "text"),
              "fields": {"id": {"type": (STR,)}, "who": {"type": (STR,)}, "text": {"type": (STR,)},
                         "audio": {"type": (STR,)}, "words": {"type": (LIST,), "items": DICT, "need": ("word", "t")},
                         "at": {"type": (STR,), "doc": "voice-over: <clip>:<frame>"},
                         "spoken": {"type": (BOOL,)}, "redo": {"type": (BOOL,)}},
              "doc": 'spoken lines [{"id": "l01", "who": "mo", "text": "Hello!", "audio": "speech/l01.wav"}]'},
    "sound": {"type": (DICT,), "doc": 'the music of the sound mix {"music": "...", "music_level": -18} (film3d.py sound)'},
    "voices": {"type": (DICT,), "each": {"type": (DICT,)}, "doc": '{"<who>": {"engine": ..., "design": ...}}'},
    "language": {"type": (STR,)}, "pronounce": {"type": (DICT,)},
    "look": {"type": (STR, NULL), "values": ("cinema", "ad", "standard", "none"),
             "doc": '"cinema" (default), "ad", "standard" or "none"'},
    "palette": {"type": (STR, DICT),
                "doc": '"ivory" (default), "petrol", "forest" or {"base": "ivory", "accent": "#C24F2D"}'},
    "lips": {"type": (STR,), "values": ("soft", "strong")},
    "figures": {"type": (STR,), "values": ("toy", "ragdoll", "puppet", "stopmotion", "clay", "paper", "marionette",
                                           "rigify"),
                "doc": 'the make of the figures: "toy" (default), "ragdoll" (sewn cloth), "puppet" (hand puppets), '
                       '"stopmotion" (gothic stop-motion puppets), "clay" (plasticine), "paper" (papercraft), '
                       '"marionette" (wooden string puppets) or "rigify" (realistic actors, stage-3d stage_rig.py)'},
    "actors": {"type": (DICT,), "each": {"type": (STR,)},
               "doc": '{"mo": "tim"} - which realistic actor (<actors>/<name>/figur.blend) plays which part '
                      '("figures": "rigify")'},
    "cast": {"type": (DICT,), "doc": '{"mo": "bear", "kit": {"look": "cat", "glasses": true}} - the bundled toy figures'},
    "final": {"type": (STR,)},
}
SCHEMAS = {"song": SONG, "talk": TALK, "short": SHORT, "deck": DECK, "film3d": FILM3D}
FAMILY = {"animated-music-video": "song", "bricks-music-video": "song", "claudia-music-video": "song",
          "lyric-music-video": "song", "portal-music-video": "song", "song-analysis": "song", "talking-character": "talk",
          "animated-short": "short", "animated-powerpoint": "deck", "animated-3d-film": "film3d"}      # film-finish / video-review: detected


# ------------------------------------------------------------------ helpers
def frame_size(p):
    """(width, height) of the film frames: project.json "size": [w, h], default 1280x720. p = dict or Project."""
    p = getattr(p, "p", p) or {}
    s = p.get("size") if isinstance(p, dict) else None
    if isinstance(s, (list, tuple)) and len(s) == 2 and all(_is(v, INT) and v > 0 for v in s):
        return int(s[0]), int(s[1])
    return DEFAULT_SIZE


def frame_scale(p):
    """Pixel values designed for 1280x720 (fonts, title y, card places) times this = the same look at "size"."""
    return frame_size(p)[1] / REF_H


def _is(v, t):
    if t == NUM:
        return isinstance(v, (int, float)) and not isinstance(v, bool)
    if t == INT:
        return isinstance(v, int) and not isinstance(v, bool)
    return isinstance(v, {STR: str, BOOL: bool, LIST: list, DICT: dict, NULL: type(None)}[t])


def _kind(v):
    if v is None:
        return "null"
    if isinstance(v, bool):
        return f"{'true' if v else 'false'}"
    if isinstance(v, str):
        return f'a string ("{v[:30]}")'
    if isinstance(v, (int, float)):
        return f"a number ({v})"
    return {list: "a list", dict: "an object"}.get(type(v), type(v).__name__)


def _names(types):
    m = {STR: "a string", INT: "a whole number", NUM: "a number", BOOL: "true/false", LIST: "a list", DICT: "an object",
         NULL: "null"}
    return " or ".join(m[t] for t in types)


def _mean(word, options):
    near = difflib.get_close_matches(word, list(options), n=1, cutoff=0.6)
    return f' - did you mean "{near[0]}"?' if near else ""


class Report:
    def __init__(self, src):
        self.src, self.items = src, []

    def err(self, key, msg):
        self.items.append(Problem("error", key, msg))

    def warn(self, key, msg):
        self.items.append(Problem("warning", key, msg))


def _value(R, key, v, spec):
    """Type, items, fields of one value against its spec."""
    types = spec.get("type", ())
    if types and not any(_is(v, t) for t in types):
        R.err(key, f"expected {spec.get('doc') or _names(types)}, got {_kind(v)}")
        return
    if "min" in spec and _is(v, NUM) and v < spec["min"]:
        R.err(key, f"must be >= {spec['min']}, got {v}")
    if "max" in spec and _is(v, NUM) and v > spec["max"]:
        R.err(key, f"must be <= {spec['max']}, got {v}")
    if "values" in spec and isinstance(v, str) and v not in spec["values"]:
        R.err(key, f'"{v}" is not one of {", ".join(spec["values"])}{_mean(v, spec["values"])}')
    entries = []
    if isinstance(v, list):
        entries = [(f"{key}[{i}]", x) for i, x in enumerate(v)]
    elif isinstance(v, dict) and "each" in spec:
        for k, x in v.items():
            _value(R, f"{key}.{k}", x, spec["each"])
        return
    elif isinstance(v, dict) and ("need" in spec or "fields" in spec):
        entries = [(key, v)]
    for k, x in entries:
        it = spec.get("items")
        if isinstance(v, list) and it and not _is(x, it):
            R.err(k, f"every entry must be {_names((it,))} - expected {spec.get('doc') or _names(types)}, "
                     f"got {_kind(x)}")
            continue
        if not isinstance(x, dict):
            continue
        miss = [n for n in spec.get("need", ()) if n not in x]
        if miss:
            R.err(k, f"needs {', '.join(repr(m).replace(chr(39), chr(34)) for m in miss)} - expected "
                     f"{spec.get('doc') or 'an object with ' + ', '.join(spec['need'])}")
        if spec.get("one_of") and not any(n in x for n in spec["one_of"]):
            R.err(k, f"needs one of {', '.join(spec['one_of'])} (when the sound plays)")
        for f, fs in spec.get("fields", {}).items():
            if f in x and x[f] is not None:
                _value(R, f"{k}.{f}", x[f], fs)


def _size(R, p, key="size"):
    s = p.get(key)
    if s is None:
        return
    ok = isinstance(s, (list, tuple)) and len(s) == 2 and all(_is(v, INT) for v in s)
    if not ok:
        R.err(key, f"expected [width, height] in pixels (two whole numbers), got {json.dumps(s)[:40]}")
        return
    w, h = s
    if not (16 <= w <= 7680 and 16 <= h <= 4320):
        R.err(key, f"[{w}, {h}] is outside 16..7680 x 16..4320 pixels")
    elif w % 2 or h % 2:
        R.err(key, f"[{w}, {h}]: width and height must be even (H.264 / yuv420p)")
    elif abs(w / h - 16 / 9) > 0.01 and R.family in ("song", "talk"):
        R.warn(key, f"[{w}, {h}] is not 16:9 - the Synfig scenes and painted sets are drawn for 16:9 and are stretched")


def _sections(R, p, fps):
    secs = p.get("sections")
    if not isinstance(secs, list):
        return []
    good, names = [], {}
    for i, s in enumerate(secs):
        if not isinstance(s, dict):
            continue
        k = f"sections[{i}]" + (f" ({s['name']})" if isinstance(s.get("name"), str) else "")
        if isinstance(s.get("name"), str):
            if s["name"] in names:
                R.err(k, f'section name "{s["name"]}" is used twice (also sections[{names[s["name"]]}]) - names must be unique')
            names.setdefault(s["name"], i)
        a, b = s.get("from"), s.get("to")
        if not (_is(a, NUM) and _is(b, NUM)):
            continue
        if a < 0:
            R.err(k, f'"from" {a} is negative - times are song seconds from 0')
        if a >= b:
            R.err(k, f'"from" {a} must be smaller than "to" {b}')
            continue
        good.append((a, b, k, s))
    # order and overlaps are only warnings: film-finish build.py sorts the sections by "from" and cuts each one at the
    # next one's start (end = min(to, next from)) - the result is defined, maybe even intended (two takes of a span)
    if [g[0] for g in good] != sorted(g[0] for g in good):
        R.warn("sections", "listed out of time order - build.py sorts them by \"from\"")
    order = sorted(good, key=lambda g: g[0])
    for (a, b, k, _), (na, nb, nk, _) in zip(order, order[1:]):
        if na < b - 1e-6:
            kept = max(0.0, na - a)
            R.warn(k, f"overlaps {nk} ({na}-{nb} s): build.py cuts it at {na} s" +
                   (f" - it keeps {a}-{na} s" if kept > 0 else " - it is dropped (0 frames)"))
    return good


def png_size(path):
    """(width, height) of a PNG from its header (no decoding), None when it is not a PNG."""
    try:
        with open(path, "rb") as f:
            head = f.read(24)
        if head[:8] == b"\x89PNG\r\n\x1a\n":
            return struct.unpack(">II", head[16:24])
    except OSError:
        pass
    return None


def _frames(R, base, secs, fps, size, p_has_size=True):
    """Rendered frames (scenes/<section>/f.*.png) against the section's from/to and the frame size - warnings."""
    if base is None:
        return
    for a, b, k, s in secs:
        d = base / "scenes" / str(s.get("name"))
        if not d.is_dir():
            continue
        frames = sorted(d.glob("f.*.png"))
        if not frames:
            continue
        need = round(b * fps) - round(a * fps)
        if not need - 1 <= len(frames) <= need + 2:     # Synfig renders 0..N inclusive: up to 2 extra are normal
            R.warn(k, f"scenes/{s['name']}/ has {len(frames)} frames, but {a}-{b} s needs {need} at {fps} fps "
                      f"(from/to changed after the render?) - re-render the section"
                      + (" (build.py stops on too few)" if len(frames) < need else ""))
        got = png_size(frames[0])
        if got and tuple(got) != tuple(size) and p_has_size:
            R.warn(k, f"scenes/{s['name']}/ frames are {got[0]}x{got[1]}, the project size is {size[0]}x{size[1]} - "
                      f"re-render the section (build.py scales them)")


def _cast(base, p):
    """Voice cast keys: voice skill assets/cast.json + project.json "voices"."""
    keys = set()
    try:
        keys |= set(json.loads((SKILLS / "voice" / "assets" / "cast.json").read_text(encoding="utf-8"))["voices"])
    except (OSError, ValueError, KeyError):
        pass
    if isinstance(p.get("voices"), dict):
        keys |= set(p["voices"])
    return keys


def _voices(R, p, base):
    figs = p.get("figures")
    if not isinstance(figs, dict):
        return
    if R.family == "talk" and not p.get("recording"):  # TTS: every speaker is spoken by a cast voice (voice skill);
        #                                                 with "recording" speak.py uses the recording, no cast voice
        cast = _cast(base, p)
        for n, f in figs.items():
            if not isinstance(f, dict):
                continue
            v = f.get("voice", n)
            if isinstance(v, str) and v not in cast:
                R.err(f"figures.{n}.voice",
                      f'"{v}" is not a voice of the cast - use one of {", ".join(sorted(cast))}{_mean(v, cast)} '
                      f'(voice skill assets/cast.json) or add "{v}" to project.json "voices" with "design" + '
                      f'"sample_text"')
    elif R.family == "song":                          # songs: the figure's role decides who sings (voices.py)
        seen = {}
        for n, f in figs.items():
            if not isinstance(f, dict) or not isinstance(f.get("voice"), str):
                continue
            v = f["voice"]
            if v not in VOICE_ROLES:
                R.warn(f"figures.{n}.voice", f'"{v}" is not a singing role ({", ".join(VOICE_ROLES)}){_mean(v, VOICE_ROLES)} - '
                                             f"voices.py never gives this figure the voice (only corrections.json can)")
            elif v in seen:
                R.warn(f"figures.{n}.voice", f'"{v}" is also the voice of {seen[v]} - voices.py gives the "{v}" lines '
                                             f"only to {seen[v]}")
            seen.setdefault(v, n)
        narr = p.get("narrator")
        if isinstance(narr, str) and narr not in figs:
            R.warn("narrator", f'"{narr}" is not a figure ({", ".join(figs)}){_mean(narr, figs)} - narrated parts go to the '
                               f"announcer instead")
    for i, s in enumerate(p.get("sections") or []):     # figures named in a section must exist
        if isinstance(s, dict) and isinstance(s.get("figures"), list):
            for n in s["figures"]:
                if isinstance(n, str) and n not in figs:
                    R.warn(f"sections[{i}].figures", f'"{n}" is not in "figures" ({", ".join(figs)}){_mean(n, figs)} - '
                                                     f"it is left out")


def _deck_mouths(R, p, base):
    """animated-powerpoint: a narration "speaker" (or a figure "talk") needs mouth stages from parts.json "mouth"."""
    if base is None:
        return
    root = (base / p.get("figures_dir", "../../figures")).resolve()
    figs = p.get("figures")
    talkers = {ln.get("speaker") for ln in p.get("narration") or [] if isinstance(ln, dict) and ln.get("speaker")}
    if isinstance(figs, list):
        talkers |= {f.get("name") for f in figs if isinstance(f, dict) and f.get("talk")}
    elif isinstance(figs, dict):
        talkers |= {n for n, f in figs.items() if isinstance(f, dict) and f.get("talk")}
    for n in sorted(t for t in talkers if isinstance(t, str)):
        d = root / n
        pj = d / "parts.json"
        if not pj.exists():
            R.warn(f"narration speaker {n}", f"{pj} not found - cut the figure first (parts.py)")
            continue
        try:
            parts = json.loads(pj.read_text(encoding="utf-8"))
        except ValueError as e:
            R.err(f"narration speaker {n}", f"{pj} is not valid JSON: {e}")
            continue
        if "mouth" not in parts and not (d / "mouth.json").exists():
            R.err(f"narration speaker {n}", f'figure "{n}" talks but {pj.name} has no "mouth" block - add one '
                                            f'(kinds open | line | beak, see mouth.py) or drop its "speaker"/"talk"')


def _look(R, p, base):
    lk = p.get("look")
    if lk in ("ad", "cinema") and R.family != "film3d":
        R.err("look", f'"{lk}" is a look of the 3D film cut (film-finish clip_film.py) - here "standard", "none" '
                      "or a look folder")
        return
    if not isinstance(lk, str) or lk in ("none", "standard", "ad", "cinema"):     # ad / cinema: clip_film.py
        return
    cands = [SKILLS / "film-finish" / "assets" / "look" / lk, Path(lk)] + ([base / lk] if base else [])
    if not any(c.is_dir() for c in cands):
        R.warn("look", f'"{lk}" is neither a look of film-finish (standard, none) nor a look folder')


def _film3d(R, p, base):
    """clips: unique names, a scene module each; lines: unique ids; the sound track exists."""
    clips = [c for c in p.get("clips") or [] if isinstance(c, dict) and _is(c.get("name"), STR)]
    seen = set()
    for c in clips:
        if c["name"] in seen:
            R.err("clips", f'the clip name "{c["name"]}" is used twice')
        seen.add(c["name"])
        if not c["name"].isidentifier():
            R.err("clips", f'"{c["name"]}" is not a valid clip name (letters, digits, _ - it is a Python module name)')
        elif base and not (base / "scenes" / f'{c["name"]}.py').exists():
            R.warn("clips", f'scenes/{c["name"]}.py does not exist yet')
    ids = [ln.get("id") for ln in p.get("lines") or [] if isinstance(ln, dict)]
    for i in sorted({i for i in ids if ids.count(i) > 1}):
        R.err("lines", f'the line id "{i}" is used twice')
    s = p.get("size")
    if isinstance(s, (list, tuple)) and len(s) == 2 and all(_is(v, INT) for v in s) and (s[0] % 4 or s[1] % 4):
        R.err("size", f"[{s[0]}, {s[1]}]: a 3D film needs multiples of 4 (the draft renders half of it, H.264 needs "
                      "even sizes)")
    names = {c["name"] for c in clips}
    for ln in p.get("lines") or []:
        at = ln.get("at") if isinstance(ln, dict) else None
        if _is(at, STR):
            c, sep, fr = at.partition(":")
            if not sep or not fr.isdigit() or c not in names:
                R.err("lines", f'line {ln.get("id")}: "at" {at!r} - expected <clip>:<frame> with a clip of "clips"')
    au = p.get("audio")
    if base and _is(au, STR) and not (base / au).exists():
        R.warn("audio", f"{au} does not exist (the film is built without sound)")


def detect(p, src=None):
    if src is not None and Path(src).name == "short.json":
        return "short"
    if "clips" in p or p.get("kind") == "film3d":
        return "film3d"
    if "script" in p or "recording" in p:
        return "talk"
    if ("deck" in p or "slide" in p or "narration" in p or "layers" in p) and "sections" not in p:
        return "deck"
    return "song"


def _load(P, base=None):
    """(dict, base folder, source label) from a Project, a folder, a json file or a dict."""
    if hasattr(P, "p") and hasattr(P, "dir"):
        return P.p, Path(P.dir), str(getattr(P, "file", Path(P.dir) / "project.json"))
    if isinstance(P, dict):
        return P, Path(base) if base else None, "project"
    f = Path(P)
    if f.is_dir():
        f = next((f / n for n in ("project.json", "short.json", "clip.json", "scene.json") if (f / n).exists()),
                 f / "project.json")
    if not f.exists():
        raise SystemExit(f"{f} missing")
    try:
        return json.loads(f.read_text(encoding="utf-8")), f.parent, str(f)
    except ValueError as e:
        raise SystemExit(f"{f} is not valid JSON: {e} - nothing was built") from None


def check(P, skill=None, base=None):
    """All problems of a project: [Problem(level, key, message)] (level "error" stops a build)."""
    p, base, src = _load(P, base)
    R = Report(src)
    R.family = FAMILY.get(skill) or detect(p, src)
    if not isinstance(p, dict):
        R.err("(top)", f"expected an object {{...}}, got {_kind(p)}")
        return R.items
    schema = SCHEMAS[R.family]
    for k, v in p.items():
        if k.startswith("_"):                         # "_about", "_note": comments
            continue
        if k not in schema:
            R.warn(k, f"unknown key{_mean(k, schema)} (not read by any {R.family} build script; new keys belong in "
                      f"studio-core project_check.py SCHEMAS)")
            continue
        _value(R, k, v, schema[k])
    _size(R, p)
    fps = p.get("fps", 24) if _is(p.get("fps", 24), NUM) and p.get("fps", 24) > 0 else 24
    if R.family in ("song", "talk"):
        secs = _sections(R, p, fps)
        _voices(R, p, base)
        _frames(R, base, secs, fps, frame_size(p), bool(p.get("size")))
        t = p.get("title")
        if isinstance(t, dict) and _is(t.get("from"), NUM) and _is(t.get("to"), NUM) and t["from"] >= t["to"]:
            R.err("title", f'"from" {t["from"]} must be smaller than "to" {t["to"]}')
    if R.family == "song" and isinstance(p.get("figures"), dict):
        for e in p.get("expressions") or []:          # an unknown figure was silently dropped by scene_acting
            if isinstance(e, dict) and _is(e.get("figure"), STR) and e["figure"] not in p["figures"]:
                R.err("expressions", f'figure "{e["figure"]}" is not in "figures"{_mean(e["figure"], list(p["figures"]))}')
    if R.family == "deck":
        _deck_mouths(R, p, base)
    if R.family == "film3d":
        _film3d(R, p, base)
    _look(R, p, base)
    return R.items


def report(items, src=""):
    for it in items:
        print(f"project check {it.level.upper()}: {it.key}: {it.msg}", file=sys.stderr if it.level == "error" else sys.stdout)


def require(P, skill=None, base=None):
    """Check and report; stop with exit code 2 on errors. A child process of a build that already checked the same
    file (unchanged) stays quiet. Returns the warnings."""
    p, b, src = _load(P, base)
    stamp = None
    try:
        f = Path(src)
        stamp = f"{f.resolve()}|{f.stat().st_mtime_ns}"
    except (OSError, ValueError):
        pass
    if stamp and os.environ.get("ANIMATION_STUDIO_PROJECT_CHECKED") == stamp:
        return []
    items = check(P, skill, base)
    report(items, src)
    errs = [i for i in items if i.level == "error"]
    if errs:
        print(f"project check: {len(errs)} error(s) in {src} - fix them first, nothing was built", file=sys.stderr)
        sys.exit(2)
    if stamp:
        os.environ["ANIMATION_STUDIO_PROJECT_CHECKED"] = stamp
    return [i for i in items if i.level == "warning"]


def main():
    ap = argparse.ArgumentParser(description="Check a project's settings (project.json, short.json, clip.json, "
                                             "scene.json) before building. Exit code 2 = errors.")
    ap.add_argument("project", nargs="?", default=".", help="project folder or json file (default: .)")
    ap.add_argument("--skill", choices=sorted(set(FAMILY) | {"film-finish", "video-review"}),
                    help="the skill that builds it (default: detected from the keys)")
    a = ap.parse_args()
    items = check(a.project, a.skill)
    report(items)
    n_err = sum(1 for i in items if i.level == "error")
    print(f"project check: {n_err} error(s), {len(items) - n_err} warning(s)")
    sys.exit(2 if n_err else 0)


if __name__ == "__main__":
    main()
