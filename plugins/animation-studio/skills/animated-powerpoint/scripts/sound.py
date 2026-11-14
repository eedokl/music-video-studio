# /// script
# requires-python = ">=3.12"
# dependencies = ["numpy==2.5.4"]
# [tool.uv]
# exclude-newer = "2026-11-14T00:00:00Z"
# ///
"""Sound for a clip: narration lines + sound effects (earshot bank) with their loudest moment on the event frame.

Called by clip.py (step "sound") after "final": reads plan.json (events per figure, narration lines), writes
ton.wav and muxes it into <name>.mp4 (picture copied). The cue sheet per style reproduces the reference films:
  jump     eyes left/right (tink), suction before take-off, rubber stretch + pop, swish for the flip, landing pop + wood
  flutter  lip pop, a bamboo swish per wing beat, soft landing      hop   stick swish, pop, step landing
  stuck    waddle knocks, the shell jams (zip), tension riser into the silence, a ping for the glance, last zip, pop,
           falling whistle, deep thump + desk knock, swishes for the head shake
  gestures fist/wave swish per beat, look_up swish + celesta on the glasses flash, wag a flick every 10 frames
  tag      pop + glockenspiel
With narration the effects sit 3 dB lower and the mix is normalised to -18 LUFS (speech); without narration the
levels of the probe clip are kept. clip.json: "sound": false (off), "sounds": [{"at": <time spec>, "sfx": "id",
"args": [], "level": -20, "pan": 0, "align": "peak"|"start"}] (extra cues), narration lines {"level": dB, "pan"}
(default 0 = -14 dB, centre; "voice_pan": {"felix": 0.35} pans by speaker). Mixing: shared studio-core sfx_mix.py.
Needs earshot (config key "earshot"); without it only the narration is mixed.
Usage: uv run sound.py clips/<name>/clip.json
"""
import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np

import _studio
_studio.use()
import config  # noqa: E402
from sfx_mix import SR, SfxMix  # noqa: E402


class Mix(SfxMix):
    """Frame-based front end of the shared studio-core mixer (sfx_mix.py) - same API as before the merge:
    Mix(frames, fps, cache).voice(path, frame, db, pan) / .sfx(frame, sid, args, db, pan, align) / .write(wav, loudnorm)."""

    def __init__(self, frames, fps, cache):
        super().__init__(frames / fps, cache=cache, pan_law="linear", names="args")
        self.fps = fps

    def voice(self, path, frame, db=-14, pan=0.0):
        super().voice(path, frame / self.fps, db, pan)

    def sfx(self, frame, sid, args=(), db=-20, pan=0.0, align="peak"):
        """align "peak" (loudest moment on the frame, default) or "start" (the sound begins on the frame)."""
        return super().sfx(frame / self.fps, sid, list(args), db, pan, align)

    def peak_frames(self, sid, args=()):
        """Frames from the start of a sound to its loudest moment (0 without earshot)."""
        y = self.render(sid, list(args))
        return 0 if y is None else int(round(int(np.argmax(np.abs(y).max(axis=1))) / SR * self.fps))

    def write(self, wav, loudnorm):
        return super().write(wav, loudnorm=-18 if loudnorm else None, limit=0.89)


def cues(plan, extra_db):
    out = []

    def c(f, sid, db, pan, args=()):
        out.append((int(f), sid, list(args), db + extra_db, pan))
    for n, e in plan["events"].items():
        if n.startswith("_"):
            continue
        x = plan.get("land", {}).get(n, [0])[0]
        pan = max(-0.45, min(0.45, x / 8))
        st = e.get("style", "jump")
        if st == "jump":
            if "look_left" in e:
                c(e["look_left"], "click/tink", -27, -0.3)
                c(e["look_right"], "click/tink", -27, 0.3)
            c(e["take_off"] - 2, "whoosh_fast/reverse", -19, pan, ["--dur", "0.6", "--apex", "0.4"])
            c(e["pop"] - 1, "riser/snatch", -21, pan)
            c(e["pop"], "fit/pop/mouth_plop", -10, pan)
            if plan["variants"].get(n, {}).get("spin") == "flip":
                c(e["take_off"] + 18, "swish/soft", -15, 0.0, ["--dur", "0.7", "--apex", "0.33"])
            c(e["land"], "ui_pop/soft", -10, pan, ["--pitch", "D4"])
            c(e["land"] + 1, "knock/wood", -20, pan)
            for d, db, p in ((-6, -27, 0.4), (4, -29, -0.5), (9, -28, 0.2)):
                c(e["land"] + d, "fit/tick/domino", db, p)
        elif st == "flutter":
            c(e["pop"], "fit/pop/lip_pop", -12, pan)
            for f in e.get("wing_beats", []):
                c(f, "fit/whoosh.short/bamboo_swish", -22, pan)
            c(e["land"], "ui_pop/soft", -14, pan, ["--pitch", "A4"])
        elif st == "hop":
            c(e["take_off"] - 1, "swish/stick", -20, pan)
            c(e["pop"], "fit/pop/mouth_plop", -12, pan)
            c(e["land"], "ui_pop/step", -10, pan, ["--pitch", "C4"])
            c(e["land"] + 1, "knock/wood", -21, pan)
        elif st == "stuck":
            for f in e.get("waddle_steps", []):
                c(f, "knock/wood", -23, pan)
            b, p = e["beat"], e["pop"]
            c(e["stuck"] + 2, "pro_zip/up", -24, pan)
            c(b, "riser/tension", -20, pan, ["--dur", "1.4"])
            c(b + 3, "pro_hover_tick/ping", -24, pan)
            c(p - 3, "pro_zip/up", -21, pan)
            c(p, "fit/pop/mouth_plop", -7, pan, ["--pitch", "A4"])
            c(p + 1, "pro_pop/bloop", -15, pan)
            c(p + 6, "pro_zip/down_warm", -16, pan)
            c(p + 8, "whoosh_fast/whistle", -21, pan, ["--dur", "0.6", "--apex", "0.5"])
            c(e["land"], "whoosh_big/thump_deep", -8, pan, ["--dur", "1.0", "--apex", "0.15"])
            c(e["land"] + 1, "knock/desk", -17, pan)
            c(e["head_shake"], "swish/flick", -22, pan)
            c(e["head_shake"] + 8, "swish/flick", -24, pan)
        g = plan["variants"].get(n, {}).get("gesture")
        beats = []
        for at in e.get("gesture", []):
            if g in ("fist", "wave"):
                beats += [at, at + 11]
            elif g == "look_up":
                c(at + 12, "swish/soft", -21, pan, ["--dur", "0.4", "--apex", "0.15"])
            elif g == "wag":
                for k in range(5):
                    c(at + 10 * k, "swish/flick", -26, pan)
        for at in e.get("cheer", []):
            beats += [at, at + 16]
        if e.get("group_gesture") and e["group_gesture"][0] in ("fist", "wave"):
            beats.append(e["group_gesture"][1])
        for f in beats:
            c(f, "swish/flick", -18, pan)
        for f in e.get("sparkle", [])[:1]:
            c(f, "mallet/celesta", -17, pan, ["--pitch", "E7"])
        if "tag" in e and plan.get("tags", {}).get(n, True):
            c(e["tag"] + 1, "ui_pop/wide", -17, pan)
            c(e["tag"] + 3, "mallet/glock", -16, pan, ["--pitch", "A6"])
    return out


def make(clip_dir, P, times=None):
    clip_dir = Path(clip_dir)
    plan = json.loads((clip_dir / "plan.json").read_text(encoding="utf-8"))
    fps = P.get("fps", 24)
    m = Mix(plan["end"] + 1, fps, clip_dir.parent.parent / "cache" / "sfx")
    lines = plan.get("narration", {})
    vpan = P.get("voice_pan", {})                     # {"felix": 0.35, "helmut": -0.4} - dialogue placed like the figures
    for lid, ln in lines.items():
        who = ln.get("figure") or ln.get("who") or ln.get("speaker")
        m.voice(clip_dir / ln["audio"], ln["at"], -14 + ln.get("level", 0), float(ln.get("pan", vpan.get(who, 0.0))))
    cs = cues(plan, -3 if lines else 0)
    for x in P.get("sounds", []):
        f = times(x["at"]) if times else x["at"]
        cs.append((f, x["sfx"], x.get("args", []), x.get("level", -20), x.get("pan", 0.0), x.get("align", "peak")))
    for f, sid, args, db, pan, *al in cs:
        m.sfx(f, sid, args, db, pan, al[0] if al else "peak")
    wav = clip_dir / "ton.wav"
    m.write(wav, loudnorm=bool(lines))
    (clip_dir / "sound.json").write_text(json.dumps({"cues": [{"frame": c_[0], "sfx": c_[1], "args": c_[2], "db": c_[3], "pan": c_[4]}
                                                             for c_ in cs], "narration": lines,
                                                    "missing": sorted(set(m.missing))}, indent=1), encoding="utf-8")
    print(f"  sound: {m.count} effects + {len(lines)} narration lines -> {wav.name}"
          + (f" (missing: {sorted(set(m.missing))})" if m.missing else ""))
    return wav


def mux(video, wav):
    tmp = Path(video).with_name(Path(video).stem + "_mux.mp4")
    subprocess.run([config.need("ffmpeg"), "-y", "-v", "error", "-i", str(video), "-i", str(wav), "-map", "0:v:0",
                    "-map", "1:a:0", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", str(tmp)], check=True)
    os.replace(tmp, video)


if __name__ == "__main__":
    f = Path(sys.argv[1]).resolve()
    P = json.loads(f.read_text(encoding="utf-8"))
    w = make(f.parent, P)
    v = f.parent / f"{f.parent.name}.mp4"
    if v.exists():
        mux(v, w)
