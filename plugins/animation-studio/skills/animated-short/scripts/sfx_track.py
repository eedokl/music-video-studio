# /// script
# requires-python = ">=3.12"
# dependencies = ["numpy==2.5.4"]
# ///
"""Sound effects for a short scene, each with its loudest moment exactly on an action frame (earshot sound bank).

Usage:
  uv run sfx_track.py cues.json [--video scene.mp4] [--out sfx.wav] [--fps 24]
cues.json:
  {"end": 150, "cues": [
     {"frame": 26, "sfx": "mallet/celesta", "args": ["--pitch", "G5"], "level": -14, "what": "Pip notices the leaf"},
     {"frame": 60, "sfx": "swish/soft", "args": ["--dur", "0.45", "--apex", "0.12"], "level": -16, "pan": -0.4},
     {"frame": 84, "sfx": "ui_pop/step", "args": ["--pitch", "D4"], "level": -11, "what": "landing"}]}
- The peak of each rendered sound is measured and placed on its frame (a landing "pop" lands on the contact frame).
- Soft by default: 6 kHz low-pass and 10 ms fades (hard unfiltered clicks read as a broken speaker).
- Writes <out> (48 kHz stereo WAV), <out>.json (cue log with the measured peaks) and with --video
  <video>_sfx.mp4 (picture copied, sound added). Then apply the look once at the very end (film-finish apply_look.py).
Typical sounds: ui_pop/soft|step|blip (landings, pops), swish/soft|bright (jumps, fast moves), mallet/celesta|glock
(magic, discovery, "ting"), whoosh_big/thump_airy (big impacts), pluck/* (small comic accents);
all ids: `earshot sfx list`. Needs earshot (config key "earshot"); without it the script stops with a message.
The mixing itself is the shared studio-core sfx_mix.py (same as film-finish sounds.py and animated-powerpoint).
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _studio  # noqa: E402
_studio.use()
import config  # noqa: E402
from sfx_mix import SfxMix  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description="Frame-exact sound-effect track from the earshot bank.")
    ap.add_argument("cues")
    ap.add_argument("--video")
    ap.add_argument("--out")
    ap.add_argument("--fps", type=float, default=24)
    ap.add_argument("--hard", action="store_true", help="no low-pass / fades")
    a = ap.parse_args()
    cfg = json.loads(Path(a.cues).read_text(encoding="utf-8"))
    cues = cfg["cues"] if isinstance(cfg, dict) else cfg
    end = cfg.get("end") if isinstance(cfg, dict) else None
    end = end or max(c["frame"] for c in cues) + 2 * a.fps
    out = Path(a.out) if a.out else Path(a.cues).with_name("sfx.wav")
    mix = SfxMix(end / a.fps + 1.0, cache=Path(a.cues).parent / "sfx_bank", pan_law="linear")
    if not mix.ear:
        sys.exit("earshot not configured (check_tools.py --set earshot=...) - no sound effects")
    for c in cues:
        ok = mix.sfx(c["frame"] / a.fps, c["sfx"], c.get("args", []), db=c.get("level", -14), pan=float(c.get("pan", 0.0)),
                     align="peak", stereo=True, lowpass_each=None if a.hard else 6000, soft=not a.hard,
                     what=c.get("what", ""))
        if not ok:
            sys.exit(f"earshot could not render {c['sfx']}")
        mix.log[-1]["frame"] = c["frame"]
        print(f"  {c['frame']:4d}f {c['frame'] / a.fps:6.2f}s  {c['sfx']:22s} {c.get('what', '')}")
    mix.write(out, limit=0.89, seconds=end / a.fps + 0.5)
    out.with_suffix(".json").write_text(json.dumps(mix.log, indent=1, ensure_ascii=False), encoding="utf-8")
    print("->", out)
    if a.video:
        v = Path(a.video)
        dst = v.with_name(v.stem + "_sfx.mp4")
        subprocess.run([config.need("ffmpeg"), "-y", "-loglevel", "error", "-i", str(v), "-i", str(out), "-map", "0:v",
                        "-map", "1:a", "-c:v", "copy", "-af", "apad", "-c:a", "aac", "-b:a", "192k", "-shortest",
                        str(dst)], check=True)          # apad: silence pads the track, the picture sets the length
        print("->", dst)


if __name__ == "__main__":
    main()
