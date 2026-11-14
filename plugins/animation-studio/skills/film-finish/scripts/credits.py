# /// script
# requires-python = ">=3.12"
# dependencies = ["numpy==2.5.4", "pillow==13.0.0", "svgelements==1.9.6"]
# ///
"""End credits like in the cinema: slowly rolling text in blocks, short gag scenes between the blocks, "scene windows"
beside the text with excerpts of the finished film (and outtakes), a music bed (instrumental, quiet under the text,
louder in the gags), soft sound effects, an optional post-credits scene after black, then black.
-> credits.mp4 (with the look); --append -> film_with_credits.mp4 (film.mp4 stays untouched).

  python credits.py [--project .] --draft [--gags N] [--force]   first credits from the project -> project.json "credits"
  python credits.py [--project .] [--append] [--to s]              build (--to: only the first s seconds, quick test)
Run with: uv run credits.py ...   (PREVIEW=1 = NVENC)
The credits show film excerpts -> rebuild them after every new film (build.py film does it when "credits" is set).

project.json "credits" (all optional except "text"):
  "text":   [["head", "PROMPTS!"], ["sub", "A music video"], ["gap"], ["role", "Tim", "the user on the free plan"],
             ["head2", "Drawn & moved with"], ["role", "Animation"], ["name", "Synfig"], ...]
            kinds: head (big title), head2 (block heading), sub, role (small), name (big), gap; ["role", r, n] = both.
            The text is ONE roll, cut into len(gags)+1 equal parts; a gag plays between two parts.
  "speed": 57.6        roll speed in px/s (the reference: 2.4 px per frame)
  "layout": "text_left" | "text_right" | "text_center"   (default: picked by the seed)
  "gags": [gag, ...]   see GAG below;  "gag_order": "seed" (default) | "as_listed"
  "windows": {"film": "film.mp4", "times": [4.2, 61.5] | "auto", "seconds": 6.25, "every": 10, "outtakes": [...] | "auto"}
            one window per ~"every" s of text (one after another); auto = seeded picks spread over the film (dark
            frames skipped); "seconds" = excerpt length (looped), default = the window's time on screen;
            outtakes = rejected takes the project kept: a video, a frame folder or a still
            ({"path": "outtakes/take2.mp4", "label": "Take 2"}); "auto" looks into <project>/outtakes/.
  "music": {"stems": ["stems/*.wav"] | "file": "x.wav", "from": 46.0, "text": 0.22, "gag": 0.6, "post": 0.0}
            default: instrumental project stems, else Demucs no_vocals (cache/sep), else song minus the vocal stems
            (if they cancel), else Demucs is run (song-analysis separate_vocals.py, GPU lock; "demucs": false = no),
            else the song quietly. "from" = song second where the bed starts; looped (1 s crossfade) if too short.
  "sfx_gain": 0.35     sound effects ~9 dB down, 6 kHz low-pass, 12 ms fades (hard clicks sounded "like a broken box")
  "post": GAG          optional post-credits scene, after "black_before" s of black (default 2), then 1 s black
  "append": true       build.py film appends the credits automatically when "credits" is set

GAG = {"name": "quota", "duration": 7, "set": "room" | {"name": "stage", "dim": 0.35} | {"image": "x.png"} |
       {"color": "#16121c"}, "items": [...], "sounds": [{"at": 1.0, "sfx": "fit/key/medium" | "file.wav", "level": 0.5}],
       "zoom": {"at": 3.2, "dur": 0.8, "to": 2.3, "center": [380, 330]}, "lights_out": {"at": 7.1, "keep_mouths": true},
       "fade": true}
  Bundled sets (toon-2d): back layers under the items, front layers (curtains) over them ("front": false = none). Coordinates: 1280x720 px.
  Every item may have "at" / "to" (seconds) and "fade_in" / "fade_out" (seconds). Items are drawn in list order.
  figure  {"figure": "tim" | "lia" | "fips" | "pip" | "silhouette" | "figure.svg" | "figure.png", "x": 380, "feet": 800,
           "height": 600, "mouth": "smile" | [[0, "flat"], [2.7, "open"], [4, "o"]] (shapes: smile o open flat grin none;
           [t, "grin", 1.6] = wider), "mouth_at": [x, y] (PNG px, for own PNGs), "silhouette": true,
           "moves": [{"do": "bob"|"jump"|"fall"|"rise"|"tilt"|"drift"|"sink"|"startle"|"wave", ...}],
           "audio": {"file": "laugh.wav", "at": 4.9, "level": 0.8, "shake": 7}}   mouth + shoulders follow its loudness
           Bundled figures are exported from their rig SVG WITHOUT mouth (Inkscape) - the mouths are drawn here.
  screen  {"box": [700, 170, 1180, 500], "steps": [{"at": 0, "title": "ULTRA", "line": "0 prompts left", "red": true,
           "bar": [0.99, 0.999], "glow": 1.6, "shake": 0.75}]}             monitor with text (eyes when no bar)
  banner  {"steps": [{"at": 0, "text": "Session expires in 3 ..."}], "y": 90}                       box at the top
  bubble  {"text": "Hello?", "x": 600, "y": 200, "tail": [420, 330]}                                speech bubble
  caption {"text": "...", "at": 5.5}                                                               line at the bottom
  bang    {"text": "BANG!", "at": 4.9, "to": 5.6, "x": 150, "y": 420, "size": 1.0, "grow": 0.4}  comic lettering
  prop    {"image": "x.png" | "card": {"title", "rows": [[a, b]], "total": [a, b]}, "x": 670, "y": 420,
           "path": "static" | "drop" (swings in from the top) | "fall" (hangs, then falls), "dur": 1.7, "drop": 360}
  desk    {"y": 548, "keyboard": [240, 520]}  or  {"box": [300, 520, 980, 560], "color": "#2b1d14"}
  spot    {"x": 640, "top": 80, "bottom": 260, "alpha": 40}                                         light cone
  zzz     {"x": 420, "y": 420}
  count   {"source": [430, 510], "target": [850, 510], "n": 10, "moves": 9, "every": 0.5, "sfx": "knock/plastic"}  chips/coins
  clip    {"frames": "folder" | "f.%04d.png" | "clip.mp4", "x": 0, "y": 0, "scale": 1.0}  any rendered clip
           (e.g. toon-2d figure_3d.py frames: a 2D figure turning into 3D) - transparent PNGs are composited
"""
import argparse
import glob
import json
import math
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

import _studio  # noqa: E402
_studio.use("song-analysis", "characters")
import config  # noqa: E402
import creative  # noqa: E402
from encoding import h264  # noqa: E402
from media import check_video, contact_sheet, decode, duration, ffmpeg  # noqa: E402
from encode import place  # noqa: E402
from song_project import Project  # noqa: E402

W, H, SR = 1280, 720, 48000
HERE = Path(__file__).resolve().parent
CREAM, GOLD, INK, GREY = (246, 240, 226), (255, 210, 63), (43, 29, 20), (200, 190, 170)
BG_COL = (18, 14, 22)
FONT_DIRS = ["C:/Windows/Fonts/", "/usr/share/fonts/truetype/dejavu/", "/System/Library/Fonts/Supplemental/"]
FONT_FILES = {"script": ["segoepr.ttf", "comic.ttf", "DejaVuSans.ttf", "Arial.ttf"],
              "script_b": ["segoeprb.ttf", "comicbd.ttf", "DejaVuSans-Bold.ttf", "Arial Bold.ttf"],
              "impact": ["impact.ttf", "Impact.ttf", "DejaVuSans-Bold.ttf"]}
_fonts = {}


def font(kind, size):
    key = (kind, int(size))
    if key not in _fonts:
        f = None
        for name in FONT_FILES[kind]:
            for d in FONT_DIRS:
                if Path(d + name).exists():
                    f = ImageFont.truetype(d + name, int(size))
                    break
            if f:
                break
        _fonts[key] = f or ImageFont.load_default()
    return _fonts[key]


ease = lambda u: u * u * (3 - 2 * u)
clamp = lambda u: max(0.0, min(1.0, u))


def rgb(c, default=CREAM):
    if c is None:
        return default
    if isinstance(c, (list, tuple)):
        return tuple(int(v) for v in c[:3])
    h = str(c).lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def nframes(sec, fps):
    return int(sec * fps + 1e-6)


# ============================================================ sources: figures, sets, clips, sounds
class Assets:
    def __init__(self, P):
        self.P = P
        self.dir = P.cache / "credits"
        self.dir.mkdir(parents=True, exist_ok=True)
        self._img, self._fig, self._clip, self._snd = {}, {}, {}, {}

    def path(self, rel):
        p = self.P.path(rel)
        if p is None or not p.exists():
            raise SystemExit(f"credits: file not found: {rel}")
        return p

    def image(self, rel, size=None):
        key = (str(rel), size)
        if key not in self._img:
            im = Image.open(self.path(rel)).convert("RGBA")
            self._img[key] = im.resize(size, Image.LANCZOS) if size and im.size != size else im
        return self._img[key]

    def set_layers(self, spec):
        """-> (back RGBA, [front RGBA]) for a gag set."""
        if isinstance(spec, str):
            spec = {"name": spec}
        spec = spec or {}
        front = []
        if spec.get("name"):
            _studio.use("toon-2d")
            from sets import load_set
            info = load_set(spec["name"])
            back = Image.new("RGBA", (W, H), (0, 0, 0, 255))
            for fn in info.get("back", []):
                back = Image.alpha_composite(back, self.image(info["dir"] / fn, (W, H)))
            front = [self.image(info["dir"] / fn, (W, H)) for fn in info.get("front", [])] if spec.get("front", True) else []
        elif spec.get("image"):
            imgs = spec["image"] if isinstance(spec["image"], list) else [spec["image"]]
            back = Image.new("RGBA", (W, H), (0, 0, 0, 255))
            for fn in imgs:
                back = Image.alpha_composite(back, self.image(fn, (W, H)))
            front = [self.image(fn, (W, H)) for fn in spec.get("front", [])]
        else:
            back = Image.new("RGBA", (W, H), rgb(spec.get("color"), (22, 18, 28)) + (255,))
        if spec.get("dim", 0.45 if spec.get("name") or spec.get("image") else 0):
            back = Image.blend(back, Image.new("RGBA", (W, H), rgb(spec.get("dim_color"), (5, 6, 14)) + (255,)),
                               float(spec.get("dim", 0.45)))
        return back, front

    def figure(self, spec):
        """-> (RGBA image at the wanted height, mouth position in that image, scale vs. a 600 px figure)."""
        name = str(spec.get("figure", "tim"))
        height = int(spec.get("height", 600))
        key = (name, height, bool(spec.get("silhouette")), str(spec.get("mouth_at")))
        if key in self._fig:
            return self._fig[key]
        if name == "silhouette":
            img, mouth = silhouette_figure(), (160, 52)
            s = height / 600
            img = img.resize((max(1, int(img.width * s)), max(1, int(img.height * s))), Image.LANCZOS)
            mouth = (mouth[0] * s, mouth[1] * s)
            out = (img, mouth, s)
            self._fig[key] = out
            return out
        from figures import FIGURES, svg_path
        if name.lower() in FIGURES or name.lower().endswith(".svg"):
            svg = svg_path(name if name.lower() in FIGURES else self.path(name))
            png, mouth_svg, (vw, vh) = export_figure(svg, self.dir)
            src = Image.open(png).convert("RGBA")
            mouth = (mouth_svg[0] / vw * src.width, mouth_svg[1] / vh * src.height) if mouth_svg else None
        else:
            src = self.image(name)
            mouth = None
        if spec.get("mouth_at"):
            mouth = tuple(spec["mouth_at"])
        s = height / src.height
        img = src.resize((max(1, int(src.width * s)), height), Image.LANCZOS)
        mouth = (mouth[0] * s, mouth[1] * s) if mouth else (img.width / 2, img.height * 0.43)
        if spec.get("silhouette"):
            a = img.getchannel("A")
            img = Image.new("RGBA", img.size, (5, 7, 13, 255))
            img.putalpha(a)
        out = (img, mouth, height / 600)
        self._fig[key] = out
        return out

    def clip(self, rel, size=None, n=None, start=0.0):
        """Frames of a clip: a folder / pattern of PNGs (alpha kept) or a video. -> list of RGBA images."""
        key = (str(rel), size, n, start)
        if key in self._clip:
            return self._clip[key]
        p = self.P.path(rel)
        files = []
        if p.is_dir():
            files = sorted(f for f in p.iterdir() if f.suffix.lower() in (".png", ".jpg", ".webp"))
        elif "%" in str(p) or "*" in str(p):
            files = sorted(Path(f) for f in glob.glob(re.sub(r"%0?\d*d", "*", str(p))))
        if files:
            frames = []
            for f in files[: n or None]:
                im = Image.open(f).convert("RGBA")
                frames.append(im.resize(size, Image.LANCZOS) if size else im)
        elif p.exists() and p.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp"):
            im = Image.open(p).convert("RGBA")
            frames = [im.resize(size, Image.LANCZOS) if size else im]
        elif p.exists():
            frames = video_frames(p, start, n or 10 ** 6, size)
        else:
            raise SystemExit(f"credits: clip not found: {rel}")
        self._clip[key] = frames
        return frames

    def sound(self, sid, cutoff=6000):
        """Mono float32 at SR, low-passed (6 kHz for effects, 9 kHz for voices/laughs). sid = earshot id or a file."""
        key = (sid, cutoff)
        if key in self._snd:
            return self._snd[key]
        p = self.P.path(sid)
        if not (p and p.exists()):
            p = earshot_sound(self.P, sid)
        if p is None:
            self._snd[key] = None
            return None
        raw = subprocess.run([ffmpeg(), "-v", "error", "-i", str(p), "-af", f"lowpass=f={cutoff},lowpass=f={cutoff}",
                              "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"], capture_output=True, check=True).stdout
        y = np.frombuffer(raw, np.float32).copy()
        k = min(len(y) // 4, int(0.012 * SR))
        if k > 1:
            y[:k] *= np.linspace(0, 1, k)
            y[-k:] *= np.linspace(1, 0, k)
        self._snd[key] = y
        return y


def earshot_sound(P, sid):
    ear = config.get("earshot")
    if not ear or "/" not in sid:
        print(f"  sound '{sid}' not found" + ("" if ear else " (earshot not installed)") + " - skipped")
        return None
    bank = P.cache / "sfx_bank"                       # same bank folder as sounds.py
    bank.mkdir(exist_ok=True)
    wav = bank / (sid.replace("/", "__") + ".wav")
    if not wav.exists():
        subprocess.run(config.cmdline([ear, "sfx", "render", sid, "-o", str(wav), "--sr", str(SR)]), capture_output=True)
        if not wav.exists():
            print(f"  sound '{sid}' not in the earshot bank - skipped (earshot sfx list)")
            return None
    return wav


def export_figure(svg, work):
    """Rig SVG -> PNG (2x) WITHOUT the mouth (lip sync draws it) and without the pivot markers.
    -> (png, mouth pivot in SVG units or None, (viewbox w, h))."""
    txt = Path(svg).read_text(encoding="utf-8")
    m = re.search(r'id="pivot_mund"[^>]*?cx="([\d.]+)"[^>]*?cy="([\d.]+)"', txt) or \
        re.search(r'cx="([\d.]+)"[^>]*?cy="([\d.]+)"[^>]*?id="pivot_mund"', txt)
    vb = re.search(r'viewBox="[\d.\-]+ [\d.\-]+ ([\d.]+) ([\d.]+)"', txt)
    vw, vh = (float(vb.group(1)), float(vb.group(2))) if vb else (400.0, 600.0)
    out = Path(work) / f"figure_{Path(svg).stem}.png"
    if not out.exists() or out.stat().st_mtime < Path(svg).stat().st_mtime:
        clean = re.sub(r'<circle[^>]*id="pivot_[^"]*"[^>]*/>', "", txt)
        tmp = Path(work) / f"figure_{Path(svg).stem}_nomouth.svg"
        tmp.write_text(clean, encoding="utf-8")
        subprocess.run([config.need("inkscape"), str(tmp), "--export-type=png", f"--export-filename={out}",
                        f"--export-width={int(vw * 2)}", f"--export-height={int(vh * 2)}", "--export-area-page"],
                       check=True, capture_output=True)
    return out, ((float(m.group(1)), float(m.group(2))) if m else None), (vw, vh)


def silhouette_figure():
    """Generic dark silhouette (head + shoulders, jacket shine) - nobody real. 320x332 px, mouth at (160, 52)."""
    k = 2
    img = Image.new("RGBA", (320 * k, 332 * k), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    cx, cy = 160 * k, 72 * k
    dark = (5, 7, 13, 255)
    d.polygon([(cx - 150 * k, cy + 260 * k), (cx - 120 * k, cy + 120 * k), (cx - 40 * k, cy + 80 * k),
               (cx + 40 * k, cy + 80 * k), (cx + 120 * k, cy + 120 * k), (cx + 150 * k, cy + 260 * k)], fill=dark)
    d.ellipse((cx - 62 * k, cy - 72 * k, cx + 62 * k, cy + 72 * k), fill=dark)
    d.line([(cx + 70 * k, cy + 130 * k), (cx + 95 * k, cy + 200 * k)], fill=(106, 111, 128, 255), width=7 * k)
    d.line([(cx - 60 * k, cy + 110 * k), (cx - 20 * k, cy + 160 * k)], fill=(58, 63, 78, 255), width=6 * k)
    return img.resize((320, 332), Image.LANCZOS)


def video_frames(path, start, n, size=None):
    vf = ["-vf", f"scale={size[0]}:{size[1]}"] if size else []
    w, h = size or (W, H)
    raw = subprocess.run([ffmpeg(), "-v", "error", "-ss", f"{start:.3f}", "-i", str(path), "-frames:v", str(int(n)), *vf,
                          "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True, check=True).stdout
    arr = np.frombuffer(raw, np.uint8)
    arr = arr[: len(arr) // (w * h * 3) * (w * h * 3)].reshape(-1, h, w, 3)
    return [Image.fromarray(a).convert("RGBA") for a in arr]


def envelope(path, fps):
    """Loudness per frame of an audio file, 0..1 (RMS, normalised to its loudest frame)."""
    y = decode(path, fps * 200)
    env = np.array([np.sqrt(np.mean(y[i:i + 200] ** 2)) for i in range(0, len(y), 200)])
    return env / (env.max() + 1e-9)


# ============================================================ gag scenes
def draw_mouth(img, shape, x, y, s=1.0, scale=1.0, open_=0.0):
    """Expression mouths: smile, o, open, flat, grin (white, for silhouettes), none. open_ 0..1 = audio-driven opening."""
    d = ImageDraw.Draw(img)
    r = lambda v: v * s
    if shape == "grin":
        gw = 36 * s * scale
        if open_ > 0.05:
            d.chord((x - gw, y - r(6), x + gw, y + gw * (0.9 + 0.8 * open_)), 0, 180, fill=(243, 243, 243))
            d.chord((x - gw * 0.6, y + gw * 0.5, x + gw * 0.6, y + gw * (0.9 + 0.7 * open_)), 0, 180, fill=(20, 10, 12))
        else:
            d.arc((x - gw, y, x + gw, y + gw * 0.9), 20, 160, fill=(243, 243, 243), width=max(2, int(r(8))))
        return
    if open_ > 0.05 and shape != "none":                     # talking/laughing: an open mouth sized by the loudness
        ry = r(6 + 26 * open_)
        d.ellipse((x - r(20), y - r(6), x + r(20), y - r(6) + ry + r(8)), fill=(122, 31, 43), outline=INK,
                  width=max(2, int(r(5))))
        return
    if shape == "smile":
        d.arc((x - r(26), y - r(22), x + r(26), y + r(12)), 20, 160, fill=INK, width=max(2, int(r(6))))
    elif shape == "o":
        d.ellipse((x - r(13), y - r(8), x + r(13), y + r(20)), fill=(122, 31, 43), outline=INK, width=max(2, int(r(5))))
    elif shape == "open":
        d.ellipse((x - r(24), y - r(6), x + r(24), y + r(36)), fill=(122, 31, 43), outline=INK, width=max(2, int(r(5))))
        d.ellipse((x - r(12), y + r(16), x + r(12), y + r(32)), fill=(232, 120, 120))
    elif shape == "flat":
        d.line((x - r(18), y + r(6), x + r(18), y + r(6)), fill=INK, width=max(2, int(r(6))))


def paste(img, fig, x, y_feet, ang=0.0, alpha=1.0):
    t = fig.rotate(ang, expand=True, resample=Image.BICUBIC) if ang else fig
    if alpha < 1:
        t = t.copy()
        t.putalpha(t.getchannel("A").point(lambda v: int(v * alpha)))
    img.alpha_composite(t, (int(x - t.width / 2), int(y_feet - t.height)))


def item_alpha(it, t):
    a0, a1 = it.get("at", -1e9), it.get("to", 1e9)
    if not a0 <= t < a1:
        return 0.0
    a = 1.0
    if it.get("fade_in"):
        a = min(a, clamp((t - a0) / it["fade_in"]))
    if it.get("fade_out"):
        a = min(a, clamp((a1 - t) / it["fade_out"]))
    return a


def step_at(steps, t):
    cur = None
    for s in sorted(steps, key=lambda s: s.get("at", 0)):
        if t >= s.get("at", 0):
            cur = s
    return cur


class Gag:
    """One gag scene (or the post-credits scene): a set, items in list order, sounds, zoom, lights out."""

    def __init__(self, spec, A, fps, kind="gag"):
        self.s, self.A, self.fps, self.kind = spec, A, fps, kind
        self.n = nframes(float(spec.get("duration", 6)), fps)
        self.back, self.front = A.set_layers(spec.get("set"))
        self.envs = {}
        self._glow = {}
        for it in spec.get("items", []):
            if it.get("type", "figure") == "figure" and it.get("audio"):
                self.envs[id(it)] = envelope(A.path(it["audio"]["file"]), fps)

    # ---- sound events (frame offset in the gag, source, level, low-pass)
    def sounds(self):
        ev = [(nframes(x.get("at", 0), self.fps), x["sfx"], float(x.get("level", 1.0)), 6000, False)
              for x in self.s.get("sounds", [])]
        for it in self.s.get("items", []):
            au = it.get("audio")
            if au:
                ev.append((nframes(au.get("at", 0), self.fps), au["file"], float(au.get("level", 0.8)), 9000, True))
            if it.get("type") == "count" and it.get("sfx"):
                every = nframes(it.get("every", 0.5), self.fps)
                at = nframes(it.get("at", 0), self.fps)
                for k in range(int(it.get("moves", it.get("n", 10) - 1))):
                    ev.append((at + every * k + every // 2, it["sfx"], float(it.get("level", 0.7)), 6000, False))
        return ev

    # ---- items
    def figure(self, img, it, t, f, mouths):
        a = item_alpha(it, t)
        if a <= 0:
            return
        fig, (mx, my), s = self.A.figure(it)
        x, y, ang = float(it.get("x", 640)), float(it.get("feet", 700)), 0.0
        for mv in it.get("moves", []):
            do = mv.get("do")
            at, dur = float(mv.get("at", mv.get("from", 0))), float(mv.get("dur", 0.5))
            if do == "bob" and mv.get("from", 0) <= t < mv.get("to", 1e9):
                half = max(1, round(float(mv.get("period", 0.25)) * self.fps / 2))
                y -= float(mv.get("amp", 6)) if (f // half) % 2 else 0
            elif do == "jump" and at <= t < at + dur:
                y -= float(mv.get("height", 40)) * math.sin(math.pi * clamp((t - at) / dur))
            elif do == "fall" and t >= at:
                u = ease(clamp((t - at) / dur))
                x += float(mv.get("dx", -120)) * u
                y += float(mv.get("dy", 650)) * u * u
                ang += float(mv.get("angle", 75)) * u
            elif do == "rise":
                if t < at:
                    return
                y += float(mv.get("from", 450)) * (1 - ease(clamp((t - at) / dur)))
            elif do == "tilt" and mv.get("from", 0) <= t < mv.get("to", 1e9):
                ang += float(mv.get("angle", -8))
            elif do == "drift" and t >= mv.get("from", 0):
                u = clamp((t - mv["from"]) / max(1e-6, mv.get("to", mv["from"] + 1) - mv["from"]))
                x += float(mv.get("dx", 0)) * u
                y += float(mv.get("dy", 0)) * u
            elif do == "sink" and t >= at:
                u = ease(clamp((t - at) / dur))
                y += float(mv.get("dy", 90)) * u
                if t < mv.get("until", 1e9):
                    ang += float(mv.get("angle", -14)) * u
            elif do == "startle" and t >= at:
                u = clamp((t - at) / dur)
                y -= float(mv.get("up", 150)) * u
                if t >= at + dur:
                    y += float(mv.get("settle", 40)) * (1 - math.exp(-(t - at - dur) * self.fps / 4))
            elif do == "wave" and mv.get("from", 0) <= t < mv.get("to", 1e9):
                ang += float(mv.get("angle", 1.8)) * math.sin(f * float(mv.get("speed", 1 / 3)))
        # mouth (drawn into a copy of the figure, so it turns with it)
        shape, scale = "smile", 1.0
        mspec = it.get("mouth", "smile")
        if isinstance(mspec, str):
            shape = mspec
        else:
            prev = 1.0
            for e in sorted(mspec, key=lambda e: e[0]):
                if t >= e[0]:
                    shape = e[1]
                    sc = float(e[2]) if len(e) > 2 else 1.0
                    scale = prev + (sc - prev) * ease(clamp((t - e[0]) / 0.42))
                    prev = sc
        open_, shake = 0.0, 0
        au = it.get("audio")
        if au:
            env = self.envs[id(it)]
            k = f - nframes(au.get("at", 0), self.fps)
            lv = float(env[k]) if 0 <= k < len(env) else 0.0
            if k >= 0:
                shake = int(float(au.get("shake", 7)) * lv * math.sin(f * 1.9))
                open_ = clamp(k / 4) * clamp(0.15 + 1.1 * lv)
        y += shake
        if shape == "grin":       # white grin on a dark silhouette: drawn on top, also after lights out
            def m(im, xx=x - fig.width / 2 + mx, yy=y - fig.height + my):
                draw_mouth(im, "grin", xx, yy, s, scale, open_)
            paste(img, fig, x, y, ang, a)
            m(img)
            if it.get("keep_mouth", True):
                mouths.append(m)
            return
        f2 = fig.copy()
        draw_mouth(f2, shape, mx, my, s, scale, open_)
        paste(img, f2, x, y, ang, a)

    def screen(self, img, it, t, f):
        st = step_at(it.get("steps", []), t) or {}
        x0, y0, x1, y1 = it.get("box", [700, 170, 1180, 500])
        sh = (0, 0)
        if st.get("shake") and t - st.get("at", 0) < st["shake"]:
            sh = (int(6 * math.sin(f * 2.1)), int(4 * math.cos(f * 1.7)))
        if st.get("shake_x"):
            sh = (int(5 * math.sin(f * 2)), 0)
        x0, x1, y0, y1 = x0 + sh[0], x1 + sh[0], y0 + sh[1], y1 + sh[1]
        glow = float(st.get("glow", 1.0)) if not st.get("shake") or t - st.get("at", 0) < st.get("shake", 0) else 1.0
        key = (x0, y0, x1, y1, glow)
        if key not in self._glow:
            g = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            ImageDraw.Draw(g).ellipse((x0 - 160, y0 - 120, x1 + 160, y1 + 120), fill=(95, 179, 255, int(min(255, 70 * glow))))
            self._glow[key] = g.filter(ImageFilter.GaussianBlur(60))
        img.alpha_composite(self._glow[key])
        d = ImageDraw.Draw(img)
        d.rectangle((x0, y0, x1, y1), fill=(28, 31, 38), outline=INK, width=6)
        d.rectangle((x0 + 22, y0 + 22, x1 - 22, y1 - 22), fill=(107, 26, 26) if st.get("red") else (29, 59, 92))
        if it.get("stand", True):
            d.rectangle((x0 + 210, y1, x0 + 270, it.get("stand_to", 552)), fill=(48, 52, 62))
        cx = (x0 + x1) / 2
        title, line = str(st.get("title", "")), str(st.get("line", ""))
        tf = font("impact", 46)
        while d.textlength(title, font=tf) > x1 - x0 - 60 and tf.size > 20:
            tf = font("impact", tf.size - 2)
        d.text((cx - d.textlength(title, font=tf) / 2, y0 + 60), title, font=tf, fill=(255, 243, 176))
        lf = font("script_b", 28)
        for i, row in enumerate(line.split("\n")):
            d.text((cx - d.textlength(row, font=lf) / 2, y0 + 150 + 40 * i), row, font=lf, fill=(232, 251, 255))
        bar = st.get("bar")
        if bar is not None:
            if isinstance(bar, (list, tuple)):
                nxt = [s["at"] for s in it["steps"] if s.get("at", 0) > st.get("at", 0)]
                span = (min(nxt) if nxt else st.get("at", 0) + 5) - st.get("at", 0)
                bar = bar[0] + (bar[1] - bar[0]) * clamp((t - st.get("at", 0)) / span)
            d.rectangle((x0 + 60, y0 + 210, x1 - 60, y0 + 240), outline=(232, 251, 255), width=3)
            d.rectangle((x0 + 64, y0 + 214, x0 + 64 + (x1 - x0 - 128) * bar, y0 + 236), fill=(95, 211, 138))
        elif st.get("eyes", True):
            for ex in (x0 + 170, x1 - 170):
                d.ellipse((ex - 22, y1 - 105, ex + 22, y1 - 61), fill=(232, 251, 255))
                d.ellipse((ex - 9, y1 - 92, ex + 9, y1 - 74), fill=(29, 59, 92))

    def banner(self, img, it, t):
        st = step_at(it.get("steps", [{"at": 0, "text": it.get("text", "")}]), t)
        if not st:
            return
        d = ImageDraw.Draw(img)
        f_ = font("script_b", 28)
        txt = st["text"]
        tw = d.textlength(txt, font=f_)
        y = it.get("y", 90)
        d.rounded_rectangle((W / 2 - tw / 2 - 24, y, W / 2 + tw / 2 + 24, y + 60), 10, fill=(29, 59, 92), outline=INK, width=4)
        d.text((W / 2 - tw / 2, y + 10), txt, font=f_, fill=(232, 251, 255))

    def bubble(self, img, it, t):
        a0 = it.get("at", 0)
        u = (t - a0) * self.fps
        sc = 0.2 + u / 5 if u < 4 else 1.0 + 0.1 * math.exp(-(u - 4) / 2) * math.cos((u - 4) * 1.5)
        f_ = font("script_b", int(it.get("size", 30)))
        rows, cur = [], ""
        for w in str(it["text"]).split():
            tt = (cur + " " + w).strip()
            if f_.getlength(tt) > it.get("width", 360):
                rows.append(cur)
                cur = w
            else:
                cur = tt
        rows.append(cur)
        bw = int(max(f_.getlength(r) for r in rows) + 60)
        bh = int(len(rows) * f_.size * 1.3 + 40)
        x, y = it.get("x", 640), it.get("y", 200)
        tx, ty = it.get("tail", [x - bw / 3, y + bh])
        layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        d.polygon([(x - bw * 0.15, y + bh * 0.3), (x + bw * 0.05, y + bh * 0.3), (tx, ty)], fill="white", outline=INK, width=4)
        d.ellipse((x - bw / 2, y - bh / 2, x + bw / 2, y + bh / 2), fill="white", outline=INK, width=4)
        d.polygon([(x - bw * 0.13, y + bh * 0.28), (x + bw * 0.03, y + bh * 0.28), (tx, ty)], fill="white")
        for i, r in enumerate(rows):
            d.text((x - f_.getlength(r) / 2, y - bh / 2 + 20 + i * f_.size * 1.3), r, font=f_, fill=INK)
        if abs(sc - 1) > 0.01:                  # pop with a small overshoot, scaled about the bubble centre
            big = layer.resize((max(1, int(W * sc)), max(1, int(H * sc))), Image.BICUBIC)
            layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            layer.paste(big, (int(x - x * sc), int(y - y * sc)))
        img.alpha_composite(layer)

    def caption(self, img, it, t):
        d = ImageDraw.Draw(img)
        f_ = font("script_b", 30)
        a = clamp((t - it.get("at", 0)) * self.fps / 8)
        tw = d.textlength(it["text"], font=f_)
        d.rectangle((W / 2 - tw / 2 - 26, 628, W / 2 + tw / 2 + 26, 690), fill=BG_COL)
        d.text((W / 2 - tw / 2, 640), it["text"], font=f_, fill=tuple(int(v * a) for v in CREAM))

    def bang(self, img, it, t):
        span = max(1e-6, it.get("to", it.get("at", 0) + 0.67) - it.get("at", 0))
        s = float(it.get("size", 1.0)) * (1 + float(it.get("grow", 0.4)) * (1 - (t - it.get("at", 0)) / span))
        ImageDraw.Draw(img).text((it.get("x", 150), it.get("y", 420)), it["text"], font=font("impact", 70 * s),
                                 fill=rgb(it.get("color"), GOLD), stroke_width=5, stroke_fill=(23, 18, 13))

    def prop(self, img, it, t, f):
        if "_img" not in it:
            it["_img"] = card_image(it["card"]) if it.get("card") else self.A.image(it["image"])
        p = it["_img"]
        at = it.get("at", 0)
        path = it.get("path", "static")
        x, y = float(it.get("x", 640)), float(it.get("y", 300))
        if path == "drop":                      # swings in from the top and settles (a sheet of paper)
            fl = (t - at) * self.fps
            u = clamp((t - at) / float(it.get("dur", 1.67)))
            rot = float(it.get("swing", 25)) * math.sin(fl / 4.0) * (1 - u) + float(it.get("angle", 4))
            q = p.rotate(rot, expand=True, resample=Image.BICUBIC)
            img.alpha_composite(q, (int(x + float(it.get("sway", 120)) * math.sin(fl / 5.0) * (1 - u) - q.width / 2),
                                    int(y - 800 + 800 * ease(u))))
        elif path == "fall":                    # hangs in the air for a moment, then falls and wobbles
            t0 = at + float(it.get("hold", 0.08))
            u = clamp((t - t0) / float(it.get("dur", 0.5)))
            yy = y + float(it.get("drop", 360)) * u * u
            ang = float(it.get("angle", -20)) * u if u < 1 else float(it.get("angle", -20)) + 6 * math.sin(f)
            q = p.rotate(ang, expand=True)
            img.alpha_composite(q, (int(x - q.width / 2), int(yy)))
        else:
            q = p.rotate(float(it.get("angle", 0)), expand=True, resample=Image.BICUBIC) if it.get("angle") else p
            img.alpha_composite(q, (int(x - q.width / 2), int(y)))

    def count(self, img, it, t, f):
        d = ImageDraw.Draw(img)
        cols = [rgb(c) for c in it.get("colors", ["#c0262d", "#2f6db3", "#1f1f1f"])]
        (ax, ay), (bx, by) = it.get("source", [430, 510]), it.get("target", [850, 510])
        n, every = int(it.get("n", 10)), nframes(it.get("every", 0.5), self.fps)
        fl = f - nframes(it.get("at", 0), self.fps)
        moves = int(it.get("moves", n - 1))
        moved = min(max(fl, 0) // every, moves)

        def chip(x, y, c):
            d.ellipse((x - 46, y - 14, x + 46, y + 14), fill=c, outline=(23, 18, 13), width=3)
            d.ellipse((x - 30, y - 9, x + 30, y + 9), outline=(240, 240, 240), width=2)
        for i in range(n - moved):
            chip(ax, ay - i * 12, cols[i % len(cols)])
        for i in range(moved):
            chip(bx, by - i * 12, cols[(i + 1) % len(cols)])
        if 0 <= fl < every * moves and fl % every < every // 2:
            u = (fl % every) / (every // 2)
            chip(ax + (bx - ax) * u, ay - 130 - 60 * math.sin(math.pi * u), cols[moved % len(cols)])

    def clip(self, img, it, t):
        fps_c = float(it.get("fps", self.fps))
        k = int((t - it.get("at", 0)) * fps_c + 1e-6)
        sc = float(it.get("scale", 1.0))
        frames = self.A.clip(it["frames"])
        if k >= len(frames):
            if not it.get("hold_last"):
                return
            k = len(frames) - 1
        fr = frames[k]
        if sc != 1.0:
            fr = fr.resize((int(fr.width * sc), int(fr.height * sc)), Image.LANCZOS)
        a = item_alpha(it, t)
        if a < 1:
            fr = fr.copy()
            fr.putalpha(fr.getchannel("A").point(lambda v: int(v * a)))
        img.alpha_composite(fr, (int(it.get("x", 0)), int(it.get("y", 0))))

    def render(self, f):
        t = f / self.fps
        img = self.back.copy()
        mouths = []
        for it in self.s.get("items", []):
            kind = it.get("type", "figure")
            if kind not in ("figure", "clip") and item_alpha(it, t) <= 0:
                continue
            if kind == "figure":
                self.figure(img, it, t, f, mouths)
            elif kind == "screen":
                self.screen(img, it, t, f)
            elif kind == "banner":
                self.banner(img, it, t)
            elif kind == "bubble":
                self.bubble(img, it, t)
            elif kind == "caption":
                pass                                       # captions go over the front layers (below)
            elif kind == "bang":
                self.bang(img, it, t)
            elif kind == "prop":
                self.prop(img, it, t, f)
            elif kind == "count":
                self.count(img, it, t, f)
            elif kind == "clip":
                if t >= it.get("at", 0):
                    self.clip(img, it, t)
            elif kind == "desk":
                d = ImageDraw.Draw(img)
                if it.get("box"):
                    d.rectangle(tuple(it["box"]), fill=rgb(it.get("color"), INK))
                else:
                    y = it.get("y", 548)
                    d.rectangle((0, y + 12, W, H), fill=rgb(it.get("color"), (138, 90, 60)), outline=INK, width=5)
                    d.rectangle((0, y, W, y + 18), fill=(176, 122, 82), outline=INK, width=4)
                    if it.get("keyboard", [240, 520]):
                        kx, ky = it.get("keyboard", [240, 520])
                        d.rectangle((kx, ky + 8, kx + 280, ky + 32), fill=(58, 63, 74), outline=INK, width=3)
            elif kind == "spot":
                if "_img" not in it:
                    sp = Image.new("RGBA", (W, H), (0, 0, 0, 0))
                    x, a, b = it.get("x", 640), it.get("top", 80), it.get("bottom", 260)
                    ImageDraw.Draw(sp).polygon([(x - a, 0), (x + a, 0), (x + b, H), (x - b, H)],
                                               fill=(255, 241, 201, int(it.get("alpha", 40))))
                    it["_img"] = sp.filter(ImageFilter.GaussianBlur(20))
                img.alpha_composite(it["_img"])
            elif kind == "zzz":
                d = ImageDraw.Draw(img)
                for k in range(3):
                    p = ((t - it.get("at", 0)) * self.fps / 14 + k / 3) % 1
                    d.text((it.get("x", 420) + 70 * p, it.get("y", 420) - 160 * p), "z", font=font("impact", 30 + 24 * p),
                           fill=(232, 251, 255))
        for fr in self.front:
            img.alpha_composite(fr)
        for it in self.s.get("items", []):
            if it.get("type") == "caption" and item_alpha(it, t) > 0:
                self.caption(img, it, t)
        z = self.s.get("zoom")
        if z and t >= z["at"]:
            zz = 1 + (float(z.get("to", 2.0)) - 1) * ease(clamp((t - z["at"]) / float(z.get("dur", 0.8))))
            cx, cy = z.get("center", [W / 2, H / 2])
            big = img.resize((int(W * zz), int(H * zz)), Image.BICUBIC)
            x0 = int(min(max(cx * zz - W / 2, 0), big.width - W))
            y0 = int(min(max(cy * zz - H / 2, 0), big.height - H))
            img = big.crop((x0, y0, x0 + W, y0 + H))
        lo = self.s.get("lights_out")
        if lo and t >= lo["at"]:
            img = Image.blend(img, Image.new("RGBA", (W, H), (0, 0, 0, 255)), clamp((t - lo["at"]) / lo.get("fade", 0.125)))
            if lo.get("keep_mouths", True) and f < self.n - 8:
                for m in mouths:
                    m(img)
        black = Image.new("RGBA", (W, H), (0, 0, 0, 255))
        if self.s.get("fade", True):
            if f < 8:
                img = Image.blend(black, img, f / 8)
            if self.kind == "gag" and f >= self.n - 8:
                img = Image.blend(black, img, (self.n - f) / 8)
        return img.convert("RGB")


def card_image(c):
    """A paper card prop: title, rows of (left, right), a red total line."""
    rows = c.get("rows", [])
    h = 200 + 46 * len(rows)
    img = Image.new("RGBA", (300, h), (0, 0, 0, 0))
    k = ImageDraw.Draw(img)
    fr, ft = font("script", 24), font("script_b", 30)
    k.rectangle((0, 0, 299, h - 1), fill=(251, 251, 245), outline=INK, width=4)
    k.text((26, 22), c.get("title", ""), font=font("impact", 46), fill=INK)
    k.line((26, 86, 274, 86), fill=INK, width=3)
    for i, (a, b) in enumerate(rows):
        k.text((26, 104 + i * 46), a, font=fr, fill=INK)
        k.text((274 - k.textlength(b, font=fr), 104 + i * 46), b, font=fr, fill=INK)
    if c.get("total"):
        y = 120 + 46 * len(rows)
        k.line((26, y, 274, y), fill=INK, width=3)
        a, b = c["total"]
        k.text((26, y + 12), a, font=ft, fill=(192, 38, 45))
        k.text((274 - k.textlength(b, font=ft), y + 12), b, font=ft, fill=(192, 38, 45))
    return img


# ============================================================ text roll + scene windows
STYLE = {"head": ("impact", 64, GOLD, 90), "head2": ("script_b", 30, GOLD, 64), "sub": ("script", 26, CREAM, 44),
         "role": ("script", 24, GREY, 32), "name": ("script_b", 30, CREAM, 48), "gap": ("script", 26, CREAM, 40)}
LAYOUTS = {   # text column centre, window size, window boxes (alternating), tilt sign
    "text_left": {"cx": 410, "win": (440, 248), "boxes": [(790, 220)]},
    "text_right": {"cx": 870, "win": (440, 248), "boxes": [(40, 220)]},
    "text_center": {"cx": 640, "win": (330, 186), "boxes": [(870, 160), (20, 330)]},
}


def roll_lines(text):
    lines, y = [], 0
    for e in text:
        e = [e] if isinstance(e, str) else list(e)
        kind = e[0]
        if kind == "role" and len(e) > 2:                       # ["role", "Tim", "the user"] = role + name
            seq = [("role", e[1]), ("name", e[2])]
        else:
            seq = [(kind, e[1] if len(e) > 1 else "")]
        for k, txt in seq:
            fk, size, col, dy = STYLE.get(k, STYLE["sub"])
            lines.append((y, txt, font(fk, size), col))
            y += dy
    return lines, y


class Roll:
    def __init__(self, P, C, A, n_parts, layout, rng):
        self.P, self.C, self.A, self.fps = P, C, A, P.fps
        self.lines, h = roll_lines(C.get("text", []))
        self.speed = float(C.get("speed", 57.6)) / self.fps
        total = h + H * float(C.get("end_at", 0.55))
        self.part_n = int(total / self.speed / n_parts)
        self.L = LAYOUTS[layout]
        self.tilt = float(C.get("windows", {}).get("tilt", rng.choice([2.5, 3, 3.5])))
        self.tilt_sign = 1 if "tilt" in C.get("windows", {}) else rng.choice([1, -1])
        self.dy = int(C.get("windows", {}).get("dy", 0 if C.get("layout") else rng.choice([-30, 0, 0, 30])))
        self.bg = Image.new("RGB", (W, H), rgb(C.get("background"), BG_COL))
        self.roll_f = 0
        self.win_k = 0

    def window_card(self, fr, k, label=None):
        cw, ch = self.L["win"]
        card = Image.new("RGB", (cw + 16, ch + 16), CREAM)
        if fr.mode == "RGBA":                     # transparent frames (e.g. a 3D figure render) on a dark backdrop
            fr = Image.alpha_composite(Image.new("RGBA", fr.size, (44, 38, 58, 255)), fr)
        card.paste(fr.convert("RGB"), (8, 8))
        if label:
            d = ImageDraw.Draw(card)
            f_ = font("script_b", 18)
            tw = d.textlength(label, font=f_) + 20
            d.rounded_rectangle((14, 12, 14 + tw, 40), 8, fill=(224, 71, 63))
            d.text((24, 13), label, font=f_, fill="white")
        ang = self.tilt * self.tilt_sign * (-1 if k % 2 else 1)
        return card.rotate(ang, expand=True, resample=Image.BICUBIC, fillcolor=self.bg.getpixel((0, 0)))

    def frames(self, part, wins, fade_in=True, fade_out=True):
        """Yield the frames of one text part; wins = [(loader -> window frames, label), ...] shown one after another."""
        n = self.part_n
        boxes = self.L["boxes"]
        wins = wins or []
        slot = n / max(1, len(wins))
        cur, frames = -1, None
        for i in range(n):
            img = self.bg.copy()
            d = ImageDraw.Draw(img)
            off = H - self.roll_f * self.speed
            cx = self.L["cx"]
            for yy, txt, f_, col in self.lines:
                yp = off + yy
                if -80 < yp < H + 20 and txt:
                    a = clamp(min(yp / 90, (H - yp) / 90))
                    d.text((cx - d.textlength(txt, font=f_) / 2, yp), txt, font=f_,
                           fill=tuple(int(v * a + self.bg.getpixel((0, 0))[j] * (1 - a)) for j, v in enumerate(col)))
            if wins:
                j = min(int(i / slot), len(wins) - 1)
                if j != cur:
                    cur, frames = j, wins[j][0]()
                    self.win_k += 1
                if frames:
                    il, ln = i - int(round(j * slot)), int(round((j + 1) * slot)) - int(round(j * slot))
                    fr = frames[il % len(frames)]
                    card = self.window_card(fr, self.win_k - 1, wins[j][1])
                    ca = clamp(min(il / 12, (ln - il) / 12))
                    bx, by = boxes[(self.win_k - 1) % len(boxes)]
                    box = (bx, by + self.dy, bx + card.width, by + self.dy + card.height)
                    img.paste(Image.blend(img.crop(box), card, ca), box[:2])
            if fade_in and i < 12:
                img = Image.blend(Image.new("RGB", (W, H)), img, i / 12)
            if fade_out and i >= n - 10:
                img = Image.blend(Image.new("RGB", (W, H)), img, (n - i) / 10)
            self.roll_f += 1
            yield img


def find_outtakes(P):
    d = P.dir / "outtakes"
    if not d.is_dir():
        return []
    out = []
    for p in sorted(d.iterdir()):
        if p.is_dir() and any(p.glob("*.png")) or p.suffix.lower() in (".mp4", ".mov", ".webm", ".png", ".jpg"):
            out.append({"path": str(p.relative_to(P.dir)), "label": "Outtake"})
    return out


def plan_windows(P, C, A, n_parts, part_n, rng):
    """-> per text part a list of (loader -> frames, label): one window per ~"every" seconds of text (default 10)."""
    w = C.get("windows", {})
    film = P.path(w.get("film", C.get("film", "film.mp4")))
    cw, ch = LAYOUTS[C["_layout"]]["win"]
    per = max(1, round(part_n / P.fps / float(w.get("every", 10.0))))
    n_win = per * n_parts
    n = nframes(float(w["seconds"]), P.fps) if w.get("seconds") else -(-part_n // per)
    specs = []
    times = w.get("times", "auto")
    if film and film.exists():
        dur = duration(film)
        if times == "auto":
            times = []
            for k in range(n_win):                            # one seeded pick per slot of the film, skip dark frames
                lo, hi = dur * k / n_win, dur * (k + 1) / n_win - n / P.fps
                t = lo
                for _ in range(6):
                    t = max(0.0, rng.uniform(lo + 0.5, max(lo + 0.5, hi)))
                    fr = video_frames(film, t, 1, (64, 36))
                    if fr and np.asarray(fr[0].convert("L")).mean() > 30:
                        break
                times.append(round(t, 2))
        specs = [{"film": t} for t in times]
    elif times != "auto":
        print(f"  windows: film {film} missing - no scene windows")
    outt = w.get("outtakes", "auto")
    outt = find_outtakes(P) if outt == "auto" else [o if isinstance(o, dict) else {"path": o} for o in outt]
    if outt and specs:                                      # outtakes take seeded slots (at most every other window)
        slots = rng.sample(range(min(len(specs), n_win)), max(1, min(len(outt), min(len(specs), n_win) // 2)))
        for s, o in zip(sorted(slots), outt):
            specs[s] = {"outtake": o}
    elif outt:
        specs = [{"outtake": o} for o in outt]

    def loader(s):
        if "film" in s:
            return lambda: [f.convert("RGB") for f in video_frames(film, s["film"], n, (cw, ch))]
        o = s["outtake"]

        def load():
            fr = A.clip(o["path"], (cw, ch), n, float(o.get("from", 0)))
            if len(fr) != 1:
                return fr
            base, out = fr[0], []                          # a still: slow push-in
            for i in range(n):
                z = 1 + 0.08 * i / max(1, n - 1)
                big = base.resize((int(cw * z), int(ch * z)), Image.BICUBIC)
                x0, y0 = (big.width - cw) // 2, (big.height - ch) // 2
                out.append(big.crop((x0, y0, x0 + cw, y0 + ch)))
            return out
        return load
    wins = []
    for k in range(n_parts):
        part = []
        for j in range(per if specs else 0):
            s = specs[(k * per + j) % len(specs)]
            part.append((loader(s), None if "film" in s else s["outtake"].get("label", "Outtake")))
            print(f"  window {k + 1}.{j + 1}: " + (f"film {s['film']:.2f} s" if "film" in s
                                                    else f"outtake {s['outtake']['path']}"))
        wins.append(part)
    return wins


# ============================================================ music bed + sound
def music_bed(P, C, A, n_s):
    m = C.get("music", {})
    start = float(m.get("from", min((s["from"] for s in P.sections()), default=0.0)))
    files, minus = [], []
    if m.get("file"):
        files = [P.path(m["file"])]
    elif m.get("stems"):
        for g in m["stems"]:
            files += sorted(Path(x) for x in glob.glob(str(P.path(g))))
    else:
        st = P.get("stems") or {}
        files = [P.path(v) for k, v in st.items() if k not in ("lead", "backing") and "vocal" not in k.lower()]
        if not files and (P.dir / "stems").is_dir():
            files = [f for f in sorted((P.dir / "stems").glob("*.wav")) if "vocal" not in f.name.lower()
                     and f.stem not in ("lead", "backing")]
        nv = P.cache / "sep" / "htdemucs" / "song" / "no_vocals.wav"
        if not files and nv.exists():
            files = [nv]
        if not files:
            files = [P.song]
            minus = [P.path(v) for k, v in st.items() if k in ("lead", "backing")]
    if not files or not all(f.exists() for f in files):
        print("  music: no source found - credits without music")
        return np.zeros(n_s, np.float32), "none"
    load = lambda f: decode(f, SR)
    mix = None
    for f in files:
        y = load(f)
        mix = y if mix is None else mix[:len(y)] + y[:len(mix)]
    what = f"{len(files)} stem(s)" if len(files) > 1 or files[0] != P.song else "song"
    if minus:                                    # song minus the vocal stems (works when stems sum to the song)
        voc = sum(load(f)[:len(mix)] for f in minus)
        rest = mix[:len(voc)] - voc
        ratio = np.sqrt(np.mean(rest ** 2) / (np.mean(mix ** 2) + 1e-12))
        if ratio < 0.8 and np.sqrt(np.mean(voc ** 2)) > 1e-4:
            mix, what = rest, "song minus vocal stems"
        elif m.get("demucs", True) and demucs_no_vocals(P):
            mix, what = load(P.cache / "sep" / "htdemucs" / "song" / "no_vocals.wav"), "Demucs no_vocals"
        else:
            mix, what = mix * 0.6, "song (vocals still in - give music.stems or allow Demucs)"
    mix = mix[int(start * SR):]
    if len(mix) < SR:
        mix = load(files[0])
    out = mix
    while len(out) < n_s:                        # loop with a 1 s crossfade
        k = SR
        fade = np.linspace(0, 1, k, dtype=np.float32)
        out = np.concatenate([out[:-k], out[-k:] * (1 - fade) + mix[:k] * fade, mix[k:]])
    return out[:n_s].astype(np.float32), what


def demucs_no_vocals(P):
    """Instrumental of song.wav with Demucs (song-analysis separate_vocals.py, takes the shared GPU lock)."""
    nv = P.cache / "sep" / "htdemucs" / "song" / "no_vocals.wav"
    if nv.exists():
        return True
    script = _studio.skill_dir("song-analysis") / "scripts" / "separate_vocals.py"
    print("  music: separating the instrumental with Demucs (GPU lock) ...")
    r = subprocess.run(config.gpu_runner(["demucs", "soundfile"]) + [str(script), str(P.song), "-o", str(P.cache / "sep")])
    return r.returncode == 0 and nv.exists()


def sound_track(P, C, A, segments, events, total_f, fps):
    n_s = int(total_f / fps * SR) + SR
    music, what = music_bed(P, C, A, n_s)
    m = C.get("music", {})
    level = {"text": float(m.get("text", 0.22)), "gag": float(m.get("gag", 0.6)), "black": 0.0,
             "post": float(m.get("post", 0.0))}
    env = np.zeros(n_s, np.float32)
    for kind, a, b in segments:
        env[int(a / fps * SR):int(b / fps * SR)] = level[kind]
    k = int(0.5 * SR)
    env = np.convolve(env, np.ones(k, np.float32) / k, mode="same")
    mix = music * env
    gain = float(C.get("sfx_gain", 0.35))
    n_ev = 0
    for at, src, vol, cutoff, voice in events:     # voice = the audio of an audio-driven figure (laugh): not softened
        s = A.sound(src, cutoff)
        if s is None:
            continue
        i0 = int(at / fps * SR)
        if i0 >= n_s:
            continue
        mix[i0:i0 + len(s)] += s[:n_s - i0] * vol * (1.0 if voice else gain)
        n_ev += 1
    mix = mix / max(1.0, np.max(np.abs(mix)) / 0.9)
    wav = A.dir / "sound.wav"
    p = subprocess.Popen([ffmpeg(), "-y", "-v", "error", "-f", "f32le", "-ar", str(SR), "-ac", "1", "-i", "-",
                          "-af", "pan=stereo|c0=c0|c1=c0", "-c:a", "pcm_s16le", str(wav)], stdin=subprocess.PIPE)
    p.communicate(mix.astype(np.float32).tobytes())
    print(f"  sound: music = {what}, {n_ev} sound events")
    return wav


# ============================================================ build
def build(P, quick_to=None, append=False):
    C = P.get("credits")
    if not C or not C.get("text"):
        raise SystemExit('project.json has no "credits" text - run credits.py --draft first')
    fps = P.fps
    A = Assets(P)
    rng = creative.rng(P, "credits")
    layout = C.get("layout") or creative.pick(P, "credits:layout", list(LAYOUTS))
    C["_layout"] = layout
    gags = list(C.get("gags", []))
    if C.get("gag_order", "seed") == "seed" and len(gags) > 1:
        creative.rng(P, "credits:gag_order").shuffle(gags)
    n_parts = int(C.get("parts", len(gags) + 1))
    roll = Roll(P, C, A, n_parts, layout, rng)
    print(f"credits: layout {layout}, {n_parts} text parts x {roll.part_n} frames, gags: "
          + (", ".join(g.get("name", "?") for g in gags) or "none") + (", post-credits scene" if C.get("post") else ""))
    wins = plan_windows(P, C, A, n_parts, roll.part_n, creative.rng(P, "credits:excerpts"))
    # timeline: text | gag | text | ... | text | black | post | black
    plan = []
    for k in range(n_parts):
        plan.append(("text", k))
        if k < len(gags) and k < n_parts - 1:
            plan.append(("gag", gags[k]))
    for g in gags[n_parts - 1:]:
        plan.append(("gag", g))
    if C.get("post"):
        plan.append(("black", float(C.get("black_before", 2.0))))
        plan.append(("post", C["post"]))
    plan.append(("black", float(C.get("black_after", 1.0))))
    max_f = nframes(quick_to, fps) if quick_to else None

    pic = A.dir / "picture.mp4"
    enc = subprocess.Popen([ffmpeg(), "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                            "-r", str(fps), "-i", "-", *h264(), "-pix_fmt", "yuv420p", str(pic)], stdin=subprocess.PIPE)
    fno, segments, events = 0, [], []

    def emit(img):
        nonlocal fno
        if max_f is not None and fno >= max_f:
            return False
        enc.stdin.write(img.tobytes())
        fno += 1
        return True

    for kind, x in plan:
        a = fno
        if kind == "text":
            for img in roll.frames(x, wins[x], fade_in=True, fade_out=True):
                if not emit(img):
                    break
        elif kind == "black":
            blk = Image.new("RGB", (W, H))
            for _ in range(nframes(x, fps)):
                if not emit(blk):
                    break
        else:
            g = Gag(x, A, fps, "post" if kind == "post" else "gag")
            events += [(a + e[0],) + tuple(e[1:]) for e in g.sounds()]
            for f in range(g.n):
                if not emit(g.render(f)):
                    break
        segments.append((kind, a, fno))
        if max_f is not None and fno >= max_f:
            break
    enc.stdin.close()
    enc.wait()
    total = fno
    print(f"  {total} frames = {total / fps:.1f} s; " + ", ".join(f"{k}:{a}-{b}" for k, a, b in segments))
    wav = sound_track(P, C, A, segments, events, total, fps)
    raw = A.dir / "credits_raw.mp4"
    subprocess.run([ffmpeg(), "-y", "-v", "error", "-i", str(pic), "-i", str(wav), "-map", "0:v", "-map", "1:a",
                    "-t", f"{total / fps:.3f}", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", str(raw)], check=True)
    import build as film_build                   # the same look step as the film
    tmp = A.dir / "credits_tmp.mp4"
    film_build.look(P, raw, tmp)
    out = place(tmp, P.dir / C.get("out", "credits.mp4"))
    (A.dir / "timeline.json").write_text(json.dumps({"fps": fps, "frames": total, "layout": layout,
                                                     "segments": segments}, indent=1), encoding="utf-8")
    err = check_video(out)
    sheet = contact_sheet(out, P.dir / "credits_sheet.png", 4, 4, 480, fps)
    print(f"-> {out.name}: {total / fps:.1f} s, {out.stat().st_size / 1e6:.1f} MB, "
          f"{'0 decode errors' if not err else 'ERRORS: ' + err[:200]}; sheet {sheet.name}")
    if append:
        append_to_film(P, out)


def append_to_film(P, credits):
    C = P.get("credits")
    film = P.path(C.get("append_to", "film.mp4"))
    if not film.exists():
        raise SystemExit(f"{film.name} missing - build the film first")
    tmp = P.cache / "credits" / "film_with_credits_tmp.mp4"
    fc = (f"[0:v]fps={P.fps},format=yuv420p,setsar=1[v0];[1:v]fps={P.fps},format=yuv420p,setsar=1[v1];"
          "[0:a]aresample=48000,aformat=channel_layouts=stereo[a0];[1:a]aresample=48000,aformat=channel_layouts=stereo[a1];"
          "[v0][a0][v1][a1]concat=n=2:v=1:a=1[v][a]")
    subprocess.run([ffmpeg(), "-y", "-v", "error", "-i", str(film), "-i", str(credits), "-filter_complex", fc,
                    "-map", "[v]", "-map", "[a]", *h264(), "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart",
                    str(tmp)], check=True)
    out = place(tmp, P.dir / "film_with_credits.mp4")
    err = check_video(out)
    print(f"-> {out.name}: {duration(out):.1f} s (film {duration(film):.1f} s + credits), "
          f"{out.stat().st_size / 1e6:.1f} MB, {'0 decode errors' if not err else 'ERRORS: ' + err[:200]}")


# ============================================================ draft
LABELS = {
    "de": {"video": "Ein Musikvideo", "cast": "Besetzung", "music": "Musik", "song": "Song", "made": "Gemacht mit",
           "heard": "Gehört & verstanden von", "assembled": "Zusammengesetzt mit", "section": "Abschnitt",
           "ai": "Enthält KI-generierte Inhalte", "assist": "Regie-Assistenz", "rest": "Alles dazwischen",
           "end": "Kein Modell wurde bei den Dreharbeiten verletzt.", "self": "als sich selbst", "fill": "(wer? bitte eintragen)",
           "roles": {"Vocals": "Gesang", "Vocals separated": "Gesang getrennt", "Every word heard": "Jedes Wort gehört",
                     "Beat & pitch": "Takt & Tonhöhe", "Lips": "Lippen", "Who sings": "Ohren (Mann? Frau?)",
                     "Figure rigs": "Figuren-Rigs", "Sound effects": "Geräusche", "Transitions": "Übergänge",
                     "Edit hand-off": "Schnitt-Übergabe", "Pop-up cards": "Pop-up-Karten", "stems": "Stems",
                     "earshot sound bank": "earshot-Geräuschbank"}},
    "en": {"video": "A music video", "cast": "Cast", "music": "Music", "song": "Song", "made": "Made with",
           "heard": "Heard & understood by", "assembled": "Put together with", "section": "Section",
           "ai": "Contains AI-generated content", "assist": "Directing assistant", "rest": "Everything in between",
           "end": "No model was harmed in the making of this film.", "self": "as themselves", "fill": "(who? fill in)",
           "roles": {}},
}


def detect_tools(P):
    """What was actually used, from the files the skills leave in the project. -> (per section, hearing, assembly, ai)"""
    a, c = P.analysis, P.cache
    per = {}
    for s in P.sections():
        t = []
        name = s["name"]
        sc = P.dir / "scenes"
        if (sc / f"{name}.sif").exists() or list(sc.glob(f"{name}*.sif")):
            t.append("Synfig")
        if list(sc.glob(f"{name}*.html")) or list(sc.glob(f"{name}/*.html")) or s.get("renderer") == "threejs":
            t.append("three.js")
        if s.get("set"):
            t.append(f"Krita ({s['set']})")
        if list((P.dir / "overlays").glob(f"{name}.mov")) if (P.dir / "overlays").is_dir() else False:
            t.append("Pillow")
        if s.get("renderer") in ("blender", "bricks") or list(sc.glob(f"{name}*.blend")):
            t.append("Blender")
        per[name] = t or ["?"]
    hear = []
    if P.get("stems"):
        hear.append(("Vocals", "stems"))
    if (c / "sep").is_dir():
        hear.append(("Vocals separated", "Demucs"))
    if (a / "song_sheet.json").exists():
        hear.append(("Every word heard", "Whisper"))
        hear.append(("Beat & pitch", "librosa"))
    if list(a.glob("*mouth*.json")):
        hear.append(("Lips", "Rhubarb Lip Sync"))
    if (a / "gender.json").exists() or (a / "assignment.json").exists():
        hear.append(("Who sings", "earshot"))
    asm = []
    if P.get("figures"):
        if any(str(f.get("svg", "")).endswith(".svg") for f in P.get("figures").values() if isinstance(f, dict)):
            asm.append(("Figure rigs", "Inkscape"))
    if (a / "sounds.wav").exists():
        asm.append(("Sound effects", "earshot sound bank"))
    if any(x.get("shaders") for x in P.get("transitions", []) or []):
        asm.append(("Transitions", "Shaders"))
    if (P.dir / "film.otio").exists() or (P.dir / "film.mlt").exists():
        asm.append(("Edit hand-off", "Kdenlive / melt"))
    if P.get("popups"):
        asm.append(("Pop-up cards", "Pillow"))
    blob = json.dumps(P.p).lower()
    ai = sorted({n for k, n in (("whisper", "Whisper"), ("demucs", "Demucs"), ("flux", "FLUX"), ("ltx", "LTX-Video"),
                                ("wan", "Wan"), ("depth", "Depth Anything"), ("qwen", "Qwen"), ("suno", "Suno"))
                 if k in blob} | {n for _, n in hear if n in ("Whisper", "Demucs")})
    return per, hear, asm, ai


def draft(P, n_gags=2, force=False):
    C = P.get("credits") or {}
    if C.get("text") and not force:
        raise SystemExit('project.json already has "credits" text - use --force to overwrite it')
    lang = "de" if str(P.get("language", "en")).startswith("de") else "en"
    L = LABELS[lang]
    per, hear, asm, ai = detect_tools(P)
    from figures import FIGURES
    text = [["head", str(P.get("title", {}) and P.get("title", {}).get("text") or P.get("name", "Untitled")).upper()],
            ["sub", L["video"]], ["gap"], ["head2", L["cast"]]]
    for name, f in (P.get("figures") or {}).items():
        about = (f or {}).get("role") or (FIGURES.get(name, {}).get("about", "").split(";")[0].split(",")[0]
                                          if lang == "en" else "") or L["self"]
        text.append(["role", name.capitalize(), about])
    text.append(["gap"])
    src = P.get("source") or {}
    song = src.get("title") or P.get("song_title") or P.get("name", "")
    tr = lambda x: L["roles"].get(x, x)
    text += [["role", L["song"], f"„{song}“" if lang == "de" else f"\"{song}\""],
             ["role", L["music"], str(P.get("music_by") or ("Suno (?)" if "Suno" in ai else L["fill"]))], ["gap"],
             ["head2", L["made"]]]
    for sec, tools in per.items():
        text.append(["role", f"{L['section']} „{sec}“" if lang == "de" else f"{L['section']} '{sec}'", " · ".join(tools)])
    text.append(["gap"])
    if hear:
        text.append(["head2", L["heard"]])
        text += [["role", tr(r), tr(n)] for r, n in hear]
        text.append(["gap"])
    text.append(["head2", L["assembled"]])
    text += [["role", tr(r), tr(n)] for r, n in asm] + [["role", L["rest"], "ffmpeg & Python"], ["role", L["assist"], "Claude"],
                                                ["gap"]]
    if "claudia" in json.dumps(P.p).lower():
        text.append(["sub", "Claudia by anabology"])
    text.append(["sub", f"{L['ai']}: " + ", ".join(ai + ["Claude"])])
    text.append(["sub", L["end"]])
    # gag ideas from the song/project: screen texts, pop-up gag words, the figures
    figs = [n for n in (P.get("figures") or {}) if n.lower() in FIGURES or str((P.get("figures")[n] or {}).get("svg", "")).endswith(".svg")]
    words = [g.get("text", "") for g in P.get("gags", [])] + [s.get("text", "").split("\n")[0] for s in P.get("screen", [])]
    words = [w for w in words if w] or [str(P.get("name", "THE END")).upper()]
    r = creative.rng(P, "credits:draft")
    sets = [s.get("set") for s in P.sections() if s.get("set")]
    templates = ["screen", "bubble", "card"]
    r.shuffle(templates)
    gags = []
    for i in range(n_gags):
        kind = templates[i % len(templates)]
        hero = figs[i % len(figs)] if figs else "silhouette"
        w = words[i % len(words)]
        sset = {"name": "room" if kind == "screen" else (sets[0] if sets else "stage"), "dim": 0.4}
        if kind == "screen":
            g = {"name": f"screen_{w.lower().strip('!')}", "duration": 6, "set": sset, "items": [
                {"type": "screen", "steps": [{"at": 0, "title": w, "line": "0 left", "red": True},
                                             {"at": 2.8, "title": w + " PLUS", "line": "Welcome! (49.99 / hour)", "glow": 1.6,
                                              "shake": 0.7}]},
                {"figure": hero, "x": 380, "feet": 800, "mouth": [[0, "flat"], [2.8, "open"], [3.8, "o"]],
                 "moves": [{"do": "bob", "from": 1.0, "to": 2.5}, {"do": "jump", "at": 2.9, "dur": 0.6}]},
                {"type": "desk"}, {"type": "bang", "text": w, "at": 3.0, "to": 3.7, "x": 120, "y": 400},
                {"type": "caption", "text": f"{hero.capitalize()} will be back ...", "at": 4.6}],
                "sounds": [{"at": 1.0 + 0.25 * k, "sfx": "fit/key/medium", "level": 0.5} for k in range(6)]
                + [{"at": 2.8, "sfx": "glitch/mid", "level": 0.6}, {"at": 3.0, "sfx": "cut_hit/punch", "level": 0.8}]}
        elif kind == "bubble":
            g = {"name": f"bubble_{hero}", "duration": 5, "set": sset, "items": [
                {"figure": hero, "x": 640, "feet": 660, "mouth": [[0, "smile"], [0.8, "open"], [2.6, "smile"], [3.6, "o"]],
                 "moves": [{"do": "wave", "from": 0, "to": 5}]},
                {"type": "bubble", "text": f"{w} ... {w}?", "x": 900, "y": 190, "tail": [700, 300], "at": 0.8, "to": 3.4},
                {"type": "caption", "text": "(to be continued)", "at": 3.6}],
                "sounds": [{"at": 0.8, "sfx": "ui_pop/blip", "level": 0.8}]}
        else:
            g = {"name": "invoice", "duration": 5.5, "set": {"name": "room"}, "items": [
                {"type": "screen", "steps": [{"at": 0, "title": words[0], "line": "PLUS"}]},
                {"figure": hero, "x": 380, "feet": 800, "mouth": [[0, "flat"], [2.5, "o"]],
                 "moves": [{"do": "rise", "at": 1.1, "dur": 0.75, "from": 450}]}, {"type": "desk"},
                {"type": "prop", "card": {"title": "INVOICE", "rows": [[x, "1"] for x in words[:3]], "total": ["TOTAL:", "all"]},
                 "x": 670, "y": 300, "path": "drop", "dur": 1.7}],
                "zoom": {"at": 3.2, "dur": 0.8, "to": 2.0, "center": [380, 330]},
                "sounds": [{"at": 0.2, "sfx": "fit/whoosh.short/bamboo_swish", "level": 0.8}]}
        gags.append(g)
    C.update({"text": text, "gags": gags if (force or not C.get("gags")) else C["gags"],
              "windows": C.get("windows", {"times": "auto", "outtakes": "auto"}), "append": C.get("append", True)})
    P.p["credits"] = C
    P.file.write_text(json.dumps(P.p, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"draft: {len(text)} text lines, {len(gags)} gag(s) written to project.json 'credits'. Check every line "
          "(roles, who made the music, the AI label), rewrite the gags into jokes about THIS song, add a 'post' scene "
          "(audio-driven figure) if wanted, then run credits.py.")


def main():
    ap = argparse.ArgumentParser(description="End credits with gags, film excerpts and a post-credits scene.")
    ap.add_argument("--project", default=".")
    ap.add_argument("--draft", action="store_true", help="write a first credits text + gags into project.json")
    ap.add_argument("--gags", type=int, default=2, help="number of draft gags")
    ap.add_argument("--force", action="store_true", help="--draft overwrites existing credits text/gags")
    ap.add_argument("--append", action="store_true", help="also write film_with_credits.mp4 (film.mp4 untouched)")
    ap.add_argument("--to", type=float, help="only the first seconds (quick test)")
    a = ap.parse_args()
    sys.stdout.reconfigure(line_buffering=True)
    P = Project(a.project)
    if a.draft:
        return draft(P, a.gags, a.force)
    build(P, a.to, a.append)


if __name__ == "__main__":
    main()
