"""Render a Synfig scene: .sif -> PNG frames -> MP4 (+ GIF, + contact sheet).

Usage:
  uv run --no-project python render.py scene.sif [--gif] [--contact 0,12,36|auto|none] [--width 1280 --height 720]
         [--single 40] [--audio voice.wav] [--jobs 8]

Output next to the .sif:  frames/<name>.NNNN.png, <name>.mp4, <name>.gif, contact.png (or --contact-out)
--single N renders only frame N to <name>_fN.png (quick pose check; renders the range N..N, not "--time",
which picked the wrong frame in tests).
--jobs N > 1 splits the frame range over N Synfig processes (synfig_parallel.py) - worth it from ~100 frames.
The contact sheet labels every tile with its frame number, so two sheets can be compared side by side.

As a module:  from render import render_sif, contact_sheet, encode
"""
import argparse
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _studio  # noqa: E402
_studio.use()
import config  # noqa: E402
from encoding import h264  # noqa: E402  (PREVIEW=1 -> NVENC)

HERE = Path(__file__).resolve().parent


def run(cmd):
    r = subprocess.run([str(c) for c in cmd], capture_output=True, text=True, errors="replace")
    errs = [l for l in (r.stdout + r.stderr).splitlines()
            if ("error" in l.lower() or "fehler" in l.lower()) and "GLib" not in l]   # Synfig speaks the system language
    if r.returncode != 0 or errs:
        print("\n".join(errs[-15:]) or (r.stdout + r.stderr)[-2000:], file=sys.stderr)
        if r.returncode != 0:
            sys.exit(f"failed: {Path(str(cmd[0])).name} (exit {r.returncode})")
    return r


def render_sif(sif, frames_dir=None, width=None, height=None, jobs=1):
    """Render all frames of a .sif to <frames_dir>/<name>.NNNN.png; returns (pattern, count)."""
    sif = Path(sif).resolve()
    name = sif.stem
    frames = Path(frames_dir) if frames_dir else sif.parent / "frames"
    frames.mkdir(parents=True, exist_ok=True)
    for p in frames.glob(f"{name}.*.png"):          # old frames of a longer version would end up in the video
        if re.fullmatch(rf"{re.escape(name)}\.\d{{4}}\.png", p.name):
            p.unlink()
    size = (["-w", str(width)] if width else []) + (["-h", str(height)] if height else [])
    if jobs and jobs > 1:
        run([sys.executable, HERE / "synfig_parallel.py", sif, frames, "--pattern", f"{name}.png", "--jobs", str(jobs)]
            + (["--width", str(width)] if width else []) + (["--height", str(height)] if height else []))
    else:
        run([config.need("synfig"), sif, "-t", "png", "-o", frames / f"{name}.png"] + size)
    n = len([p for p in frames.glob(f"{name}.*.png") if re.fullmatch(rf"{re.escape(name)}\.\d{{4}}\.png", p.name)])
    if n == 0:
        sys.exit("no frames rendered")
    return str(frames / f"{name}.%04d.png"), n


def encode(pattern, mp4, fps=24, audio=None):
    ff = config.need("ffmpeg")
    run([ff, "-y", "-loglevel", "error", "-framerate", str(fps), "-i", pattern, *h264(), "-pix_fmt", "yuv420p", mp4])
    if audio:
        tmp = Path(mp4).with_name(Path(mp4).stem + "_tmp.mp4")
        run([ff, "-y", "-loglevel", "error", "-i", mp4, "-i", Path(audio).resolve(),
             "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-shortest", tmp])
        tmp.replace(mp4)
    return mp4


def gif(pattern, out, fps=24, width=640):
    run([config.need("ffmpeg"), "-y", "-loglevel", "error", "-framerate", str(fps), "-i", pattern, "-vf",
         f"scale={width}:-1:flags=lanczos,split[a][b];[a]palettegen[p];[b][p]paletteuse", out])
    return out


def pick_frames(spec, n):
    if spec in (None, "", "auto"):
        return sorted({round(i * (n - 1) / 8) for i in range(9)})
    return [int(x) for x in str(spec).split(",") if x.strip()]


def _label_font():
    """A TrueType file for ffmpeg drawtext (Windows ffmpeg builds often lack fontconfig), escaped for filters."""
    import os
    cands = [config.get("font")]
    if os.environ.get("WINDIR"):
        cands += [str(Path(os.environ["WINDIR"]) / "Fonts" / n) for n in ("arialbd.ttf", "arial.ttf", "segoeui.ttf")]
    cands += ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "/Library/Fonts/Arial.ttf",
              "/System/Library/Fonts/Supplemental/Arial.ttf"]
    for c in cands:
        if c and Path(c).exists():
            return c.replace("\\", "/").replace(":", "\\:")
    return None


def _pil_labels(out, frames, cols, rows):
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        print("(contact sheet without frame labels: run with --with pillow to get them)")
        return
    im = Image.open(out).convert("RGB")
    tw, th = im.width // cols, im.height // rows
    d = ImageDraw.Draw(im)
    try:
        font = ImageFont.truetype("arialbd.ttf", max(14, th // 12))
    except OSError:
        font = ImageFont.load_default()
    for k, f in enumerate(frames):
        x, y = (k % cols) * tw + 6, (k // cols) * th + 6
        box = d.textbbox((x, y), f"f{f}", font=font)
        d.rectangle((box[0] - 4, box[1] - 3, box[2] + 4, box[3] + 3), fill=(0, 0, 0))
        d.text((x, y), f"f{f}", font=font, fill=(255, 255, 255))
    im.save(out)


def contact_sheet(pattern, out, frames, tile_width=426, label=True):
    """Tiles of the given frame numbers (3 per row when more than 4), each labelled 'f<number>'."""
    cols = 3 if len(frames) > 4 else len(frames)
    rows = -(-len(frames) // cols)
    sel = "+".join(f"eq(n\\,{i})" for i in frames)
    vf = f"select='{sel}',scale={tile_width}:-2,tile={cols}x{rows}"
    font = _label_font() if label else None
    if label:   # label each frame with its source number before selecting
        ff = f"fontfile='{font}':" if font else ""
        vf = (f"drawtext={ff}text='f%{{n}}':x=8:y=8:fontsize=h/24:fontcolor=white:box=1:boxcolor=black@0.55:"
              "boxborderw=5," + vf)
    r = subprocess.run([config.need("ffmpeg"), "-y", "-loglevel", "error", "-i", pattern, "-vf", vf,
                        "-frames:v", "1", str(out)], capture_output=True, text=True, errors="replace")
    if r.returncode != 0 and label:          # ffmpeg without drawtext: plain sheet, labels with Pillow if present
        contact_sheet(pattern, out, frames, tile_width, label=False)
        _pil_labels(out, frames, cols, rows)
        return out
    if r.returncode != 0:
        sys.exit("contact sheet failed: " + r.stderr[-800:])
    return out


def main():
    ap = argparse.ArgumentParser(description="Render a Synfig scene to frames, MP4, GIF and a contact sheet.")
    ap.add_argument("sif")
    ap.add_argument("--gif", action="store_true", help="also a GIF (640 px wide)")
    ap.add_argument("--contact", default="auto", help="frames for the contact sheet: 0,15,36 | auto (9 evenly) | none")
    ap.add_argument("--contact-out", help="file name of the contact sheet (default contact.png next to the .sif)")
    ap.add_argument("--width", type=int)
    ap.add_argument("--height", type=int)
    ap.add_argument("--fps", type=int, default=24)
    ap.add_argument("--single", type=int, help="render only this frame")
    ap.add_argument("--audio", help="sound track (wav/ogg/mp3) for the MP4, e.g. dialogue for lip sync")
    ap.add_argument("--jobs", type=int, default=1, help="parallel Synfig processes (synfig_parallel.py)")
    a = ap.parse_args()

    sif = Path(a.sif).resolve()
    name = sif.stem
    size = (["-w", str(a.width)] if a.width else []) + (["-h", str(a.height)] if a.height else [])

    if a.single is not None:
        out = sif.with_name(f"{name}_f{a.single}.png")
        tmp = sif.parent / f"_single_{name}"
        tmp.mkdir(exist_ok=True)
        run([config.need("synfig"), sif, "-t", "png", "-o", tmp / "s.png", "--begin-time", str(a.single),
             "--end-time", str(a.single)] + size)
        got = sorted(tmp.glob("s*.png"))
        if not got:
            sys.exit("frame not rendered")
        got[0].replace(out)
        for p in tmp.glob("*"):
            p.unlink()
        tmp.rmdir()
        print("frame:", out)
        return

    pattern, n = render_sif(sif, width=a.width, height=a.height, jobs=a.jobs)
    mp4 = encode(pattern, sif.with_suffix(".mp4"), a.fps, a.audio)
    print(f"{n} frames -> {mp4}" + (" (with sound)" if a.audio else ""))
    if a.gif:
        print("GIF:", gif(pattern, sif.with_suffix(".gif"), a.fps))
    if a.contact and a.contact != "none":
        nums = [f for f in pick_frames(a.contact, n) if f < n]
        out = Path(a.contact_out) if a.contact_out else sif.parent / "contact.png"
        contact_sheet(pattern, out, nums)
        print(f"contact sheet ({', '.join(map(str, nums))}):", out)


if __name__ == "__main__":
    main()
