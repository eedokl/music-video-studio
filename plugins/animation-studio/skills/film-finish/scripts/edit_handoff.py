# /// script
# requires-python = ">=3.12"
# dependencies = ["numpy==2.5.4", "opentimelineio==0.18.1", "pillow==13.0.0"]
# [tool.uv]
# exclude-newer = "2026-11-14T00:00:00Z"
# ///
"""Hand the cut over for manual editing: film.otio (Kdenlive, DaVinci Resolve, ...) and film.mlt (MLT / melt).

  uv run edit_handoff.py [--project .] [--crossfade 0]

Built from the same pieces as build.py film: one video clip per section (clips/<section>.mp4, silent, with overlays),
the song (+ sound effects) as one continuous audio track - so the editor gets exactly the film's timeline and can
re-cut, add transitions or credits by hand. Gaps between sections stay gaps.
- film.otio: Kdenlive 25.04+ imports it natively (File > Import > OpenTimelineIO). Media paths are written as plain
  absolute paths with "/" - Kdenlive does not understand file:/// URLs (it prepends the project folder).
  Default: hard cuts, so every section stays on its exact song frame (music videos). --crossfade N adds dissolves,
  but the section clips have no handles: each dissolve shortens the picture by N frames and pulls every later section
  N frames earlier against the song - fine for dialogue shorts, wrong for lip-synced music videos.
- film.mlt: written by melt (config key "melt", ships with Kdenlive/Shotcut) when available; `melt film.mlt` plays
  it, and Kdenlive/Shotcut open it as well.
The look is NOT baked into the hand-off clips: apply it once at the end of manual editing (apply_look.py).
"""
import argparse
import subprocess
from fractions import Fraction
from pathlib import Path

import _studio  # noqa: E402
_studio.use("song-analysis")
import config  # noqa: E402
from build import clip, frame_count, sound_track  # noqa: E402
from song_project import Project  # noqa: E402

MELT_PROFILES = {Fraction(24000, 1001): "atsc_720p_2398", 24: "atsc_720p_24", 25: "atsc_720p_25",
                 Fraction(30000, 1001): "atsc_720p_2997", 30: "atsc_720p_30", 50: "atsc_720p_50",
                 Fraction(60000, 1001): "atsc_720p_5994", 60: "atsc_720p_60"}


def media_path(p):
    return str(Path(p).resolve()).replace("\\", "/")


def melt_profile(fps, folder, size=(1280, 720)):
    """MLT profile matching the project fps and frame size (P.size): a stock 720p profile, else a profile file written
    to `folder` (e.g. 48 fps) - a wrong profile would play the frame-counted timeline at the wrong speed."""
    W, H = size
    da = Fraction(W, H)
    f = next((k for k in MELT_PROFILES if abs(float(k) - float(fps)) < 0.002), Fraction(fps).limit_denominator(1001))
    if f in MELT_PROFILES and (W, H) == (1280, 720):
        return MELT_PROFILES[f]
    p = Path(folder) / f"melt_profile_{W}x{H}_{f.numerator}_{f.denominator}.txt"
    p.write_text(f"description={W}x{H} {float(f):g} fps\nframe_rate_num={f.numerator}\nframe_rate_den={f.denominator}\n"
                 f"width={W}\nheight={H}\nprogressive=1\nsample_aspect_num=1\nsample_aspect_den=1\n"
                 f"display_aspect_num={da.numerator}\ndisplay_aspect_den={da.denominator}\ncolorspace=709\n",
                 encoding="utf-8")
    return str(p)


def main():
    import opentimelineio as otio
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", default=".")
    ap.add_argument("--crossfade", type=int, default=0, help="frames of dissolve between sections (0 = hard cuts)")
    a = ap.parse_args()
    P = Project(a.project)
    P.check("film-finish")                 # project.json validated before any long step
    fps, xf = P.fps, a.crossfade
    secs = sorted(P.sections(), key=lambda s: s["from"])
    if not secs:
        raise SystemExit("no sections in project.json")
    t0 = secs[0]["from"]
    if xf and len(secs) > 1:
        print(f"WARNING: --crossfade {xf} shortens the picture by {xf * (len(secs) - 1)} frames and moves later sections "
              "earlier against the song (no handles) - keep hard cuts for lip-synced music videos")
    shots = []
    for i, s in enumerate(secs):
        c, n = clip(P, s["name"])
        end = min(s["to"], secs[i + 1]["from"]) if i + 1 < len(secs) else s["to"]
        shots.append({"path": c, "name": s["name"], "start": frame_count(t0, s["from"], fps),
                      "dur": frame_count(s["from"], end, fps)})          # same frames as build.py film
    film_len = shots[-1]["start"] + shots[-1]["dur"]
    audio = sound_track(P)

    rt = lambda f: otio.opentime.RationalTime(f, fps)
    tr = lambda s, d: otio.opentime.TimeRange(rt(s), rt(d))
    tl = otio.schema.Timeline(name=P.get("name", "Film"))
    v1 = otio.schema.Track(name="V1 picture", kind=otio.schema.TrackKind.Video)
    h1, h2 = xf // 2, xf - xf // 2
    cursor = 0
    for i, sh in enumerate(shots):
        if sh["start"] > cursor:
            v1.append(otio.schema.Gap(source_range=tr(0, sh["start"] - cursor)))
        cut_in = h2 if (i > 0 and xf) else 0
        cut_out = h1 if (i < len(shots) - 1 and xf) else 0
        if i > 0 and xf:
            v1.append(otio.schema.Transition(name="Dissolve", transition_type=otio.schema.TransitionTypes.SMPTE_Dissolve,
                                             in_offset=rt(h1), out_offset=rt(h2)))
        ref = otio.schema.ExternalReference(target_url=media_path(sh["path"]), available_range=tr(0, sh["dur"]))
        v1.append(otio.schema.Clip(name=sh["name"], media_reference=ref, source_range=tr(cut_in, sh["dur"] - cut_in - cut_out)))
        cursor = sh["start"] + sh["dur"]
    tl.tracks.append(v1)
    a1 = otio.schema.Track(name="A1 song + sounds", kind=otio.schema.TrackKind.Audio)
    a1.append(otio.schema.Clip(name="song", media_reference=otio.schema.ExternalReference(
        target_url=media_path(audio), available_range=tr(0, round((t0 * fps)) + film_len)),
        source_range=tr(round(t0 * fps), film_len)))
    tl.tracks.append(a1)
    out = P.dir / "film.otio"
    otio.adapters.write_to_file(tl, str(out))
    msg = f"-> film.otio ({len(shots)} sections, {film_len} frames = {film_len / fps:.1f} s)"

    melt = config.get("melt")
    if melt and Path(melt).exists():
        cmd = [melt, "-profile", melt_profile(fps, P.cache, P.size)]
        cursor = 0
        for i, sh in enumerate(shots):
            if sh["start"] > cursor:
                cmd += ["-blank", str(sh["start"] - cursor - 1)]
            cmd += [str(sh["path"]), "in=0", f"out={sh['dur'] - 1}"]
            if i > 0 and xf:
                cmd += ["-mix", str(xf), "-mixer", "luma"]
            cursor = sh["start"] + sh["dur"]
        cmd += ["-track", str(audio), f"in={round(t0 * fps)}", f"out={round(t0 * fps) + film_len - 1}",
                "-transition", "mix", "a_track=0", "b_track=1", "always_active=1", "sum=1"]
        subprocess.run(cmd + ["-consumer", f"xml:{P.dir / 'film.mlt'}"], check=True, capture_output=True)
        msg += ", film.mlt"
    else:
        msg += " (no melt configured - film.mlt skipped; check_tools.py --set melt=...)"
    print(msg)


if __name__ == "__main__":
    main()
