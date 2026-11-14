"""Shared base of the end credits (credits.py): frame size and colours, fonts, small helpers, the sources (gag sets,
figures, clips, film frames, sounds) and the sound track (music bed + sound effects). Imported only - no CLI."""
import glob
import re
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

import _studio  # noqa: E402
_studio.use("song-analysis", "characters")
import config  # noqa: E402
from media import decode, ffmpeg  # noqa: E402

W, H, SR = 1280, 720, 48000          # credits are composed at 1280x720 and scaled to project "size" at the end
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

    def _stack(self, files):
        """Opaque black frame with the given full-frame layers composited on it."""
        back = Image.new("RGBA", (W, H), (0, 0, 0, 255))
        for fn in files:
            back = Image.alpha_composite(back, self.image(fn, (W, H)))
        return back

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
            back = self._stack(info["dir"] / fn for fn in info.get("back", []))
            front = [self.image(info["dir"] / fn, (W, H)) for fn in info.get("front", [])] if spec.get("front", True) else []
        elif spec.get("image"):
            back = self._stack(spec["image"] if isinstance(spec["image"], list) else [spec["image"]])
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
        if key not in self._fig:
            self._fig[key] = self._silhouette(height) if name == "silhouette" else self._figure(name, height, spec)
        return self._fig[key]

    @staticmethod
    def _silhouette(height):
        img, mouth = silhouette_figure(), (160, 52)
        s = height / 600
        img = img.resize((max(1, int(img.width * s)), max(1, int(img.height * s))), Image.LANCZOS)
        return img, (mouth[0] * s, mouth[1] * s), s

    def _figure_source(self, name):
        """-> (full-size RGBA, mouth position in it or None): a bundled rig / own SVG (exported without mouth) or a PNG."""
        from figures import FIGURES, svg_path
        if name.lower() in FIGURES or name.lower().endswith(".svg"):
            svg = svg_path(name if name.lower() in FIGURES else self.path(name))
            png, mouth_svg, (vw, vh) = export_figure(svg, self.dir)
            src = Image.open(png).convert("RGBA")
            return src, ((mouth_svg[0] / vw * src.width, mouth_svg[1] / vh * src.height) if mouth_svg else None)
        return self.image(name), None

    def _figure(self, name, height, spec):
        src, mouth = self._figure_source(name)
        if spec.get("mouth_at"):
            mouth = tuple(spec["mouth_at"])
        s = height / src.height
        img = src.resize((max(1, int(src.width * s)), height), Image.LANCZOS)
        mouth = (mouth[0] * s, mouth[1] * s) if mouth else (img.width / 2, img.height * 0.43)
        if spec.get("silhouette"):
            a = img.getchannel("A")
            img = Image.new("RGBA", img.size, (5, 7, 13, 255))
            img.putalpha(a)
        return img, mouth, height / 600

    def clip(self, rel, size=None, n=None, start=0.0):
        """Frames of a clip: a folder / pattern of PNGs (alpha kept) or a video. -> list of RGBA images."""
        key = (str(rel), size, n, start)
        if key not in self._clip:
            self._clip[key] = self._load_clip(rel, size, n, start)
        return self._clip[key]

    def _load_clip(self, rel, size, n, start):
        p = self.P.path(rel)
        files = []
        if p.is_dir():
            files = sorted(f for f in p.iterdir() if f.suffix.lower() in (".png", ".jpg", ".webp"))
        elif "%" in str(p) or "*" in str(p):
            files = sorted(Path(f) for f in glob.glob(re.sub(r"%0?\d*d", "*", str(p))))
        if files:
            return [_open_rgba(f, size) for f in files[: n or None]]
        if p.exists() and p.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp"):
            return [_open_rgba(p, size)]
        if p.exists():
            return video_frames(p, start, n or 10 ** 6, size)
        raise SystemExit(f"credits: clip not found: {rel}")

    def sound(self, sid, cutoff=6000):
        """Mono float32 at SR, low-passed (6 kHz for effects, 9 kHz for voices/laughs). sid = earshot id or a file."""
        key = (sid, cutoff)
        if key in self._snd:
            return self._snd[key]
        p = self.P.path(sid)
        if not (p and p.exists()):
            p = earshot_sound(self.P, sid)
        self._snd[key] = None if p is None else load_sound(p, cutoff)
        return self._snd[key]


def _open_rgba(f, size):
    im = Image.open(f).convert("RGBA")
    return im.resize(size, Image.LANCZOS) if size else im


def load_sound(p, cutoff):
    """An audio file as mono float32 at SR, twice low-passed at cutoff, 12 ms fades."""
    raw = subprocess.run([ffmpeg(), "-v", "error", "-i", str(p), "-af", f"lowpass=f={cutoff},lowpass=f={cutoff}",
                          "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"], capture_output=True, check=True).stdout
    y = np.frombuffer(raw, np.float32).copy()
    k = min(len(y) // 4, int(0.012 * SR))
    if k > 1:
        y[:k] *= np.linspace(0, 1, k)
        y[-k:] *= np.linspace(1, 0, k)
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
    w, h = size or (W, H)
    vf = ["-vf", f"scale={w}:{h}"]                  # film excerpts of a project with another "size" fit the layout
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


# ============================================================ sound track: music bed + sound effects
NO_VOCALS = ("sep", "htdemucs", "song", "no_vocals.wav")     # Demucs instrumental under the project cache


def bed_sources(P, m):
    """-> (files to sum, vocal stems to subtract) for the music bed (see credits.py docstring "music")."""
    files, minus = [], []
    if m.get("file"):
        return [P.path(m["file"])], minus
    if m.get("stems"):
        for g in m["stems"]:
            files += sorted(Path(x) for x in glob.glob(str(P.path(g))))
        return files, minus
    st = P.get("stems") or {}
    files = [P.path(v) for k, v in st.items() if k not in ("lead", "backing") and "vocal" not in k.lower()]
    if not files and (P.dir / "stems").is_dir():
        files = [f for f in sorted((P.dir / "stems").glob("*.wav")) if "vocal" not in f.name.lower()
                 and f.stem not in ("lead", "backing")]
    nv = P.cache.joinpath(*NO_VOCALS)
    if not files and nv.exists():
        files = [nv]
    if not files:
        files = [P.song]
        minus = [P.path(v) for k, v in st.items() if k in ("lead", "backing")]
    return files, minus


def remove_vocals(P, m, mix, minus, load):
    """Song minus the vocal stems (works when the stems sum to the song), else Demucs, else the song quieter.
    -> (mix, description)."""
    voc = sum(load(f)[:len(mix)] for f in minus)
    rest = mix[:len(voc)] - voc
    ratio = np.sqrt(np.mean(rest ** 2) / (np.mean(mix ** 2) + 1e-12))
    if ratio < 0.8 and np.sqrt(np.mean(voc ** 2)) > 1e-4:
        return rest, "song minus vocal stems"
    if m.get("demucs", True) and demucs_no_vocals(P):
        return load(P.cache.joinpath(*NO_VOCALS)), "Demucs no_vocals"
    return mix * 0.6, "song (vocals still in - give music.stems or allow Demucs)"


def loop_to(mix, n_s):
    """Loop a bed with a 1 s crossfade until it is n_s samples long."""
    out = mix
    while len(out) < n_s:
        k = SR
        fade = np.linspace(0, 1, k, dtype=np.float32)
        out = np.concatenate([out[:-k], out[-k:] * (1 - fade) + mix[:k] * fade, mix[k:]])
    return out[:n_s].astype(np.float32)


def music_bed(P, C, A, n_s):
    m = C.get("music", {})
    start = float(m.get("from", min((s["from"] for s in P.sections()), default=0.0)))
    files, minus = bed_sources(P, m)
    if not files or not all(f.exists() for f in files):
        print("  music: no source found - credits without music")
        return np.zeros(n_s, np.float32), "none"
    load = lambda f: decode(f, SR)
    mix = None
    for f in files:
        y = load(f)
        mix = y if mix is None else mix[:len(y)] + y[:len(mix)]
    what = f"{len(files)} stem(s)" if len(files) > 1 or files[0] != P.song else "song"
    if minus:
        mix, what = remove_vocals(P, m, mix, minus, load)
    mix = mix[int(start * SR):]
    if len(mix) < SR:
        mix = load(files[0])
    return loop_to(mix, n_s), what


def demucs_no_vocals(P):
    """Instrumental of song.wav with Demucs (song-analysis separate_vocals.py, takes the shared GPU lock)."""
    nv = P.cache.joinpath(*NO_VOCALS)
    if nv.exists():
        return True
    script = _studio.skill_dir("song-analysis") / "scripts" / "separate_vocals.py"
    print("  music: separating the instrumental with Demucs (GPU lock) ...")
    r = subprocess.run(config.gpu_runner(["demucs", "soundfile"]) + [str(script), str(P.song), "-o", str(P.cache / "sep")])
    return r.returncode == 0 and nv.exists()


def bed_levels(C, segments, n_s, fps):
    """Music level per sample from the timeline segments (text / gag / black / post), smoothed over 0.5 s."""
    m = C.get("music", {})
    level = {"text": float(m.get("text", 0.22)), "gag": float(m.get("gag", 0.6)), "black": 0.0,
             "post": float(m.get("post", 0.0))}
    env = np.zeros(n_s, np.float32)
    for kind, a, b in segments:
        env[int(a / fps * SR):int(b / fps * SR)] = level[kind]
    k = int(0.5 * SR)
    return np.convolve(env, np.ones(k, np.float32) / k, mode="same")


def mix_events(mix, A, events, gain, fps):
    """Add the sound events (frame, source, level, low-pass, voice) into mix in place. -> number placed."""
    n_s, n_ev = len(mix), 0
    for at, src, vol, cutoff, voice in events:     # voice = the audio of an audio-driven figure (laugh): not softened
        s = A.sound(src, cutoff)
        if s is None:
            continue
        i0 = int(at / fps * SR)
        if i0 >= n_s:
            continue
        mix[i0:i0 + len(s)] += s[:n_s - i0] * vol * (1.0 if voice else gain)
        n_ev += 1
    return n_ev


def write_wav(mix, wav):
    """Mono float mix -> 16-bit stereo WAV."""
    p = subprocess.Popen([ffmpeg(), "-y", "-v", "error", "-f", "f32le", "-ar", str(SR), "-ac", "1", "-i", "-",
                          "-af", "pan=stereo|c0=c0|c1=c0", "-c:a", "pcm_s16le", str(wav)], stdin=subprocess.PIPE)
    p.communicate(mix.astype(np.float32).tobytes())
    return wav


def sound_track(P, C, A, segments, events, total_f, fps):
    n_s = int(total_f / fps * SR) + SR
    music, what = music_bed(P, C, A, n_s)
    mix = music * bed_levels(C, segments, n_s, fps)
    n_ev = mix_events(mix, A, events, float(C.get("sfx_gain", 0.35)), fps)
    mix = mix / max(1.0, np.max(np.abs(mix)) / 0.9)
    wav = write_wav(mix, A.dir / "sound.wav")
    print(f"  sound: music = {what}, {n_ev} sound events")
    return wav
