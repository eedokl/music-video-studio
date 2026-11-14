# /// script
# requires-python = ">=3.12"
# dependencies = ["numpy==2.5.4", "pillow==13.0.0"]
# ///
"""Build the film: a preview of one section, or the whole film on the song timeline.

  preview <section>   scene frames + overlays + sound (song + sound effects) + look -> preview/<section>.mp4
  film                all sections frame-exact one after another (gaps black), ONE continuous sound track (no audio
                      seams), transitions, title, look once over everything ->
                      film.mp4 (full), film_small.mp4 (< 30 MB), film_mail.mp4 (~12 MB, 960x540; mail adds ~33 %) -
                      a version is a plain copy of film.mp4 when that is already under its size
Fixed order: cut -> title/transitions -> look -> smaller versions -> check (0 decode errors).
Only ONE session builds the film. Everything is written to *_tmp files first and then renamed; if a player has the
old file open (Windows lock), the new film is kept under a new name and the script says so.
Inputs per section: scenes/<section>/f.%04d.png (any renderer: Synfig, Blender, three.js ...), optional
overlays/<section>.mov (overlays.py - rebuilt automatically when older than project.json / the song sheet).
project.json:
  "transitions": [{"at": 21.9, "kind": "white"}]   zoom_through / glow / screen_zoom / iris / white / black -
                      computed frame by frame on the untouched cut (transitions.py), no handles needed
  "title": {"text": "Prompts!", "from": 0.5, "to": 3.5, "color": "#ffd23f"}   (default: static, fades in/out, 120 px
                      at 32 % height) - options: "size": 150, "y": 170 (px of the title's centre) or "place": "top" |
                      "center" | "lower", "animation": "pop" (scales in with an overshoot wobble, then stands) |
                      "fade", "shadow": true (soft dark drop shadow), "fade_out": 0.75 (s)
  "look": "standard" | "none"
  "credits": {...}    optional: after the film, credits.py rebuilds credits.mp4 (+ film_with_credits.mp4) from it
Usage: uv run build.py preview <section> [--project .]
       uv run build.py film [--project .]   (numpy: transitions)
PREVIEW=1 in front = fast NVENC encoding for work-in-progress files.
"""
import argparse
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import _studio  # noqa: E402
_studio.use("song-analysis")
import config  # noqa: E402
from encoding import h264  # noqa: E402
from media import check_video, ffmpeg  # noqa: E402
from encode import over_note, encode_target, place  # noqa: E402
from song_project import Project  # noqa: E402

W, H = 1280, 720
HERE = Path(__file__).resolve().parent


def frame_count(t_from, t_to, fps):
    """Frames of a piece from song second t_from to t_to: absolute rounding, so pieces laid end to end never drift
    against the continuous sound (per-piece round((to - from) * fps) accumulates errors)."""
    return round(t_to * fps) - round(t_from * fps)


def look(P, raw, out):
    if P.get("look", "standard") in (None, "none"):
        shutil.copyfile(raw, out)          # copy, not move: popup.py and others reuse cache/film_raw.mp4
        return
    subprocess.run([sys.executable, str(HERE / "apply_look.py"), str(raw), "-o", str(out), "--look", P.get("look", "standard")],
                   check=True)


def sound_track(P):
    """Song + sound effects (if any) as one file on the song timeline."""
    g = P.analysis / "sounds.wav"
    if not g.exists():
        return P.song
    out = P.cache / "song_with_sounds.wav"
    if not out.exists() or out.stat().st_mtime < max(g.stat().st_mtime, P.song.stat().st_mtime):
        subprocess.run([ffmpeg(), "-y", "-v", "error", "-i", str(P.song), "-i", str(g), "-filter_complex",
                        "[0:a][1:a]amix=inputs=2:duration=first:normalize=0[a]", "-map", "[a]", str(out)], check=True)
    return out


def fresh_overlay(P, name, A, ov):
    """overlays/<section>.mov older than project.json / the song sheet (a gag or lyric style added, times re-heard)
    or missing while the section has lyrics / the project has gags -> rebuilt with overlays.py first. Before, a new
    gag in project.json silently never reached the film."""
    deps = [P.dir / "project.json", P.analysis / "song_sheet.json"]
    newest = max((d.stat().st_mtime for d in deps if d.exists()), default=0)
    if ov.exists() and ov.stat().st_mtime >= newest:
        return
    if not ov.exists() and not (A.get("lyrics") or P.get("gags")):
        return
    print(f"   overlays/{name}.mov {'is older than project.json / song sheet' if ov.exists() else 'missing'} - rebuilding")
    subprocess.run([sys.executable, str(Path(__file__).resolve().parent / "overlays.py"), name, "--project", str(P.dir)],
                   check=True)


def clip(P, name):
    """Scene + overlays, silent -> clips/<name>.mp4 with exactly the section's frame count."""
    A = P.section(name)
    frames = P.dir / "scenes" / name
    nums = sorted(int(f.name[2:-4]) for f in frames.glob("f.*.png") if f.name[2:-4].isdigit())
    if not nums:
        raise SystemExit(f"scenes/{name}/ has no frames - render the scene first")
    n = frame_count(A["from"], A["to"], P.fps)
    have = next((k for k, v in enumerate(nums) if v != nums[0] + k), len(nums))   # ffmpeg stops at the first gap
    # one frame short is tolerated (renderers that counted round((to - from) * fps)): the last frame is held once
    if have < n - 1:
        raise SystemExit(f"scenes/{name}/ has {have} usable frames (f.{nums[0]:04d} on"
                         f"{', gap after f.%04d' % (nums[0] + have - 1) if have < len(nums) else ''}), the section "
                         f"{A['from']}-{A['to']} s needs {n} at {P.fps} fps - re-render the scene (every later section "
                         f"would slide against the sound)")
    if have > n + 1:
        print(f"   note: scenes/{name}/ has {have} frames, the section uses the first {n} (from/to changed?)")
    out = P.dir / "clips" / f"{name}.mp4"
    out.parent.mkdir(exist_ok=True)
    ov = P.dir / "overlays" / f"{name}.mov"
    fresh_overlay(P, name, A, ov)
    cmd = [ffmpeg(), "-y", "-v", "error", "-framerate", str(P.fps), "-start_number", str(nums[0]),
           "-i", str(frames / "f.%04d.png")]
    hold = "tpad=stop_mode=clone:stop=1"
    if ov.exists():
        cmd += ["-i", str(ov), "-filter_complex",
                f"[0:v]{hold}[s];[s][1:v]overlay=0:0:eof_action=pass,format=yuv420p[v]", "-map", "[v]"]
    else:
        cmd += ["-vf", f"{hold},format=yuv420p"]
    subprocess.run(cmd + ["-frames:v", str(n), "-an", *h264(), str(out)], check=True)
    return out, n


def preview(P, name):
    A = P.section(name)
    c, n = clip(P, name)
    (P.dir / "preview").mkdir(exist_ok=True)
    raw = P.cache / f"preview_{name}_raw.mp4"
    subprocess.run([ffmpeg(), "-y", "-v", "error", "-i", str(c), "-ss", f"{A['from']:.3f}", "-t", f"{n / P.fps:.3f}",
                    "-i", str(sound_track(P)), "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                    str(raw)], check=True)
    tmp = P.cache / f"preview_{name}_tmp.mp4"
    look(P, raw, tmp)
    out = place(tmp, P.dir / "preview" / f"{name}.mp4")
    print(f"-> {out.relative_to(P.dir)} ({n / P.fps:.1f} s)")


TITLE_Y = {"top": 170, "center": 360, "lower": 520}


def title_sprite(t):
    """The title lettering as an RGBA image (Impact, ink outline, optional drop shadow)."""
    from PIL import Image, ImageDraw, ImageFont
    fp = next((f for f in ("C:/Windows/Fonts/impact.ttf", "/System/Library/Fonts/Supplemental/Impact.ttf",
                           "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf") if Path(f).exists()), None)
    size = int(t.get("size", 150))
    f = ImageFont.truetype(fp, size) if fp else ImageFont.load_default()
    tw, th = f.getbbox(t["text"])[2:]
    img = Image.new("RGBA", (tw + 80, th + 80), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    h = t.get("color", "#ffd23f").lstrip("#")
    if t.get("shadow", True):
        d.text((50, 52), t["text"], font=f, fill=(12, 10, 24, 200))
    d.text((40, 40), t["text"], font=f, fill=tuple(int(h[i:i + 2], 16) for i in (0, 2, 4)) + (255,),
           stroke_width=max(4, size // 16), stroke_fill=(23, 18, 13, 255))
    return img


def title_frames(P, t):
    """Animated title ("animation": "pop"): one transparent PNG per frame -> cache/title/t.%04d.png."""
    import math
    from PIL import Image
    fps = P.fps
    n = frame_count(t["from"], t["to"], fps)
    fade = max(1, round(float(t.get("fade_out", 0.75)) * fps))
    spr = title_sprite(t)
    y = t["y"] if isinstance(t.get("y"), (int, float)) else TITLE_Y.get(t.get("place", "top"), 170)
    d = P.cache / "title"
    d.mkdir(exist_ok=True)
    for old in d.glob("t.*.png"):
        old.unlink()
    for i in range(n):
        u = i / 10                                        # pop: 0.55 -> 1.15 in 10 frames, then a decaying wobble
        s = 0.55 + 0.6 * u if u < 1 else 1.0 + 0.1 * math.exp(-(u - 1) * 3) * math.cos((u - 1) * 7)
        a = min(1.0, i / 6) * (1 - max(0.0, (i - (n - fade)) / fade))
        img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        sp = spr.resize((max(1, int(spr.width * s)), max(1, int(spr.height * s))), Image.LANCZOS)
        if a < 1:
            sp.putalpha(sp.getchannel("A").point(lambda v: int(v * max(a, 0))))
        img.alpha_composite(sp, (W // 2 - sp.width // 2, int(y - sp.height / 2)))
        img.save(d / f"t.{i:04d}.png")
    return d / "t.%04d.png", n


def title_image(P, t):
    if any(k in t for k in ("size", "y", "place", "shadow")):     # positioned lettering, static
        from PIL import Image
        spr = title_sprite(t)
        img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        y = t["y"] if isinstance(t.get("y"), (int, float)) else TITLE_Y.get(t.get("place", "top"), 170)
        img.alpha_composite(spr, (W // 2 - spr.width // 2, int(y - spr.height / 2)))
        out = P.cache / "title.png"
        img.save(out)
        return out
    return title_image_plain(P, t)


def title_image_plain(P, t):
    from PIL import Image, ImageDraw, ImageFont
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    fp = next((f for f in ("C:/Windows/Fonts/impact.ttf", "/System/Library/Fonts/Supplemental/Impact.ttf",
                           "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf") if Path(f).exists()), None)
    f = ImageFont.truetype(fp, 120) if fp else ImageFont.load_default()
    h = t.get("color", "#ffd23f").lstrip("#")
    tw = d.textlength(t["text"], font=f)
    d.text(((W - tw) / 2, H * 0.32), t["text"], font=f, fill=tuple(int(h[i:i + 2], 16) for i in (0, 2, 4)) + (255,),
           stroke_width=8, stroke_fill=(43, 29, 20, 255))
    out = P.cache / "title.png"
    img.save(out)
    return out


def film(P):
    secs = sorted(P.sections(), key=lambda a: a["from"])
    fps = P.fps
    t_start = secs[0]["from"]
    inputs, parts, pos = [], [], t_start
    for i, a in enumerate(secs):
        gap = frame_count(pos, a["from"], fps)
        if gap > 0:                                         # gap -> black, exactly `gap` frames
            parts.append(f"color=c=black:s={W}x{H}:r={fps}:d={(gap + 1) / fps:.4f},trim=end_frame={gap},"
                         f"setpts=PTS-STARTPTS[g{len(parts)}]")
        c, n = clip(P, a["name"])
        k = inputs.count("-i")
        inputs += ["-i", str(c)]
        end = min(a["to"], secs[i + 1]["from"]) if i + 1 < len(secs) else a["to"]
        parts.append(f"[{k}:v]trim=end_frame={frame_count(a['from'], end, fps)},setpts=PTS-STARTPTS,fps={fps}"
                     f"[g{len(parts)}]")
        pos = end
    graph = ";".join(parts) + ";" + "".join(f"[g{i}]" for i in range(len(parts))) + f"concat=n={len(parts)}:v=1:a=0[v0]"
    last = "v0"
    t = P.get("title")
    if t and t.get("animation") == "pop":
        k = inputs.count("-i")
        pattern, _ = title_frames(P, t)
        inputs += ["-framerate", str(fps), "-i", str(pattern)]
        graph += (f";[{k}:v]format=rgba,setpts=PTS+{t['from'] - t_start:.3f}/TB[ti];"
                  f"[{last}][ti]overlay=0:0:eof_action=pass[vt]")
        last = "vt"
    elif t:
        k = inputs.count("-i")
        dur = t["to"] - t["from"]
        fo = float(t.get("fade_out", 0.4))
        inputs += ["-loop", "1", "-t", f"{dur:.3f}", "-i", str(title_image(P, t))]
        graph += (f";[{k}:v]format=rgba,fade=in:st=0:d=0.3:alpha=1,fade=out:st={dur - fo:.3f}:d={fo:.3f}:alpha=1,"
                  f"setpts=PTS+{t['from'] - t_start:.3f}/TB[ti];[{last}][ti]overlay=0:0:eof_action=pass[vt]")
        last = "vt"
    graph += f";[{last}]format=yuv420p[v]"
    dur = frame_count(t_start, pos, fps) / fps          # the picture's exact length; frame 0 = song frame round(t_start*fps)
    k = inputs.count("-i")
    inputs += ["-ss", f"{round(t_start * fps) / fps:.4f}", "-t", f"{dur:.4f}", "-i", str(sound_track(P))]
    raw = P.cache / "film_raw.mp4"
    cut = P.cache / "film_cut.mp4"                    # the untouched cut - transitions are always computed from it
    subprocess.run([ffmpeg(), "-y", "-v", "error", *inputs, "-filter_complex", graph, "-map", "[v]", "-map", f"{k}:a",
                    *h264(), "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(cut)], check=True)
    specs = P.get("transitions", [])
    if specs:
        import transitions
        masks = None
        try:                                              # optional Shaders iris masks (film-finish shaders_render.py)
            from shaders_render import iris_masks as masks
        except Exception:
            masks = None
        pic = P.cache / "film_transitions.mp4"
        n_all, n_changed = transitions.apply(cut, pic, specs, t_start, fps, iris_masks=masks)
        subprocess.run([ffmpeg(), "-y", "-v", "error", "-i", str(pic), "-i", str(cut), "-map", "0:v", "-map", "1:a",
                        "-c", "copy", "-movflags", "+faststart", str(raw)], check=True)
        print(f"   transitions: {len(specs)} ({', '.join(x.get('kind', 'white') for x in specs)}), {n_changed} frames changed")
    else:
        shutil.copy(cut, raw)
    tmp = P.cache / "film_tmp.mp4"
    look(P, raw, tmp)
    out = place(tmp, P.dir / "film.mp4")
    results, targets = [out], {}
    for name, mb, w, h, ak in (("film_small", 29.0, 1280, 720, 128), ("film_mail", 12.0, 960, 540, 64)):
        target = P.cache / f"{name}_tmp.mp4"
        if out.stat().st_size < mb * 1e6:
            shutil.copy(out, target)                        # already small enough
        else:
            encode_target(out, target, mb, w, h, ak, dur)
        results.append(place(target, P.dir / f"{name}.mp4"))
        targets[results[-1]] = mb
    for r in results:
        err = check_video(r)
        over = over_note(r, targets[r]) if r in targets else ""
        print(f"-> {r.name}: {r.stat().st_size / 1e6:.1f} MB{over}, {'0 decode errors' if not err else 'ERRORS: ' + err[:300]}")
    print(f"   {dur:.1f} s, look {P.get('look', 'standard')}")
    if P.get("credits"):                     # optional: credits show film excerpts -> rebuilt after every new film
        subprocess.run(config.script_cmd(HERE / "credits.py") + ["--project", str(P.dir)]
                       + (["--append"] if P.get("credits").get("append", True) else []), check=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("what", choices=["preview", "film"])
    ap.add_argument("section", nargs="?")
    ap.add_argument("--project", default=".")
    a = ap.parse_args()
    P = Project(a.project)
    if a.what == "preview":
        if not a.section:
            raise SystemExit("build.py preview <section>")
        preview(P, a.section)
    else:
        film(P)


if __name__ == "__main__":
    main()
