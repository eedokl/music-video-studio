# /// script
# requires-python = ">=3.12"
# dependencies = ["numpy==2.5.4", "opentimelineio==0.18.1", "pillow==13.0.0"]
# ///
"""Film cut for films WITHOUT a song timeline (shorts, slide clips, dialogue scenes, explainers): a shot list ->
film.mp4 / film_small.mp4 / film_mail.mp4 (+ film.otio for Kdenlive, contact sheet, level report).

  uv run cut.py cut.json [--version v2]
        [--out-dir DIR] [--no-otio] [--no-versions]
PREVIEW=1 in front = fast NVENC encodes for work-in-progress files.

cut.json (paths relative to the JSON file):
{
  "name": "Pip und das Blatt", "fps": 24, "size": [1280, 720], "out": "film",
  "crossfade": 12,                 default length (frames) of a dissolve
  "handles": "auto",               how a dissolve / whip gets its frames (see below)
  "shots": [
    {"card": "Pip und das Blatt", "sub": "ein kleiner Testfilm", "frames": 72},    paper title card (rendered)
    {"src": "titel.png", "frames": 72, "zoom": [1.0, 1.06]},                       still (optional slow push)
    {"src": "../lichtung/multiplane.mp4", "name": "Lichtung", "transition": "dissolve"},
    {"src": "talk.mp4", "in": 12, "out": 180, "transition": {"kind": "dissolve", "frames": 16},
     "subtitles": "../talk/analysis/dialogue.json", "mood": "calm"},                 clip keeps its own sound
    {"src": "s03.mp4", "audio": "s03_ton.wav", "gain_db": -2, "transition": "whip"}, separate sound file
    {"src": "s05.mp4", "audio": "none", "transition": {"kind": "iris", "center": [0.5, 0.4]}}
  ],
  "music": "music.wav"  |  {"file": "music.wav", "from": 0, "at": 0, "level_db": -4, "duck_db": 12,
                            "duck": true, "fade_in": 0, "fade_out": 1.5}
                        |  {"score": {"seed": 3, "style": "light", "cues": [{"shot": 0, "mood": "intro"}, ...]}},
  "title": {"text": "Pip!", "from": 0.5, "to": 3.0, "color": "#ffd23f"},
  "look": "standard", "look_strength": 1.0, "loudness": -16,
  "grade": false, "letterbox": 2.39,
  "versions": {"v1": {}, "v2": {"music": "music_lively.wav"}, "v3": {"grade": true, "letterbox": 2.39}}
}
Shots: a still needs "frames" (or "seconds"); a clip plays from "in" (frame) for "frames" or up to "out", default
the whole clip. A clip's own sound is used ("audio": "own" default; "none"; or a sound file aligned to the clip's
frame 0, "audio_offset" seconds). Pictures of another size are fitted ("fit": "contain" default | "cover").
Transitions ("transition" on the INCOMING shot, or plan-wide "transition"):
  cut (default) | dissolve (crossfade) | dip (through black) | whip (whip pan with motion blur) - two pictures
      blended; the sound crossfades with equal power over the same frames.
  zoom_through | glow | screen_zoom | iris | white | black - the frame-computed kinds of transitions.py, applied to
      the finished cut on the cut point (no handles needed, the timeline does not move).
  Aliases of the reference projects: blende=dissolve, wisch=whip, zoom=zoom_through, blitz=white, schnitt=cut.
How a two-picture transition gets its frames ("handles", per plan or per shot):
  auto     (default) real handles when both clips have spare frames (outgoing beyond its "out", incoming before its
           "in" - stills always have them): the dissolve is centred on the cut, the timeline does not move.
           Otherwise like "overlap".
  overlap  the incoming shot starts L frames early and overlaps the end of the outgoing one (like Kdenlive/MLT mix):
           every overlap makes the film L frames shorter.
  hold     the outgoing LAST frame is held under the first L frames of the incoming shot (the ai_efficiency cut): the
           timeline does not move, the outgoing sound is not extended.
Music bed: the level is set relative to the dialogue (all shot sound = "dialogue"): "level_db" where nobody speaks
  (default -4 dB under the dialogue level), "duck_db" under speech (default 12 dB under, calibrated on the real local music
  level -> dialogue measures ~12 dB
  over the ducked music), 150 ms pre-roll, 80 ms attack, 400 ms release. "duck": false + "gain_db" = the music file
  as it is (already ducked). {"score": {...}} generates the music with score.py on the finished timeline (cues may
  name shots: their real start after overlaps). The mix is brought to "loudness" LUFS (-16; measured, one linear gain + a -2 dBFS peak limiter).
Versions: "versions" names the variants; any value in the plan that is a dict keyed only by version names (plus
  "default") is resolved, e.g. "transition": {"v1": "dissolve", "v2": "whip"}; the version's own dict overrides top-
  level keys. Outputs get the suffix: film_v2.mp4 ...
Order: picture (two-picture transitions, title, grade/letterbox) -> frame-computed transitions on the untouched cut ->
sound (shot sound + music bed, ducking, loudness) -> look once -> film.mp4 -> small (< 30 MB) / mail (~12 MB) ->
decode check of every file -> <out>_sheet.png, <out>_report.json (durations, levels), <out>_shots.json (timeline;
subtitles.py --cut), <out>.otio (Kdenlive 25.04+ import: shots on V1 with dissolves, shot sound on A1/A2, the ducked
music bed on A3 as <out>_music_bed.wav), and <out>.srt/.vtt when shots carry "subtitles".
"""
import argparse
import json
import math
import os
import shutil
import subprocess
import sys
import wave
from pathlib import Path

import numpy as np

import _studio  # noqa: E402
_studio.use()
from encoding import h264  # noqa: E402
from media import check_video, contact_sheet, ffmpeg  # noqa: E402
from encode import over_note, encode_target, place  # noqa: E402

HERE = Path(__file__).resolve().parent
SR = 48000
STILLS = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp"}
TWO = {"dissolve", "dip", "whip"}
FRAME_KINDS = {"zoom_through", "glow", "screen_zoom", "iris", "white", "black"}
ALIASES = {"blende": "dissolve", "crossfade": "dissolve", "mix": "dissolve", "wisch": "whip", "zoom": "zoom_through",
           "blitz": "white", "flash": "white", "schnitt": "cut", "hard": "cut", "none": "cut"}
DEFAULT_LEN = {"dissolve": 12, "dip": 12, "whip": 10}
FONTS = ["C:/Windows/Fonts/segoeprb.ttf", "C:/Windows/Fonts/arialbd.ttf",
         "/System/Library/Fonts/Supplemental/Arial Bold.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]
FONTS_TITLE = ["C:/Windows/Fonts/impact.ttf", "/System/Library/Fonts/Supplemental/Impact.ttf",
               "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]


# ------------------------------------------------------------------ plan

def resolve(v, version, names):
    if isinstance(v, dict):
        if names and v and set(v) <= set(names) | {"default"}:
            return resolve(v.get(version, v.get("default")), version, names)
        return {k: resolve(x, version, names) for k, x in v.items()}
    if isinstance(v, list):
        return [resolve(x, version, names) for x in v]
    return v


def load_plan(path, version=None):
    path = Path(path).resolve()
    raw = json.loads(path.read_text(encoding="utf-8"))
    versions = raw.pop("versions", {}) or {}
    names = list(versions)
    if names and version is None:
        version = names[0]
    if version and version not in versions:
        raise SystemExit(f"version '{version}' is not in \"versions\" ({', '.join(names) or 'none'})")
    plan = resolve(raw, version, names)
    plan.update(resolve(versions.get(version, {}) if version else {}, version, names))
    plan["_base"] = path.parent
    plan["_version"] = version
    return plan


def rel(plan, p):
    return (Path(plan["_base"]) / p).resolve()


_PROBE = {}


def probe(path, fps):
    """(frames at the film frame rate, has audio) - decoded once (exact frame count)."""
    key = (str(path), Path(path).stat().st_mtime, fps)
    if key not in _PROBE:
        r = subprocess.run([ffmpeg(), "-hide_banner", "-i", str(path), "-map", "0:v:0", "-vf", f"fps={fps}",
                            "-f", "null", "-"], capture_output=True, text=True, errors="replace").stderr
        import re
        fr = re.findall(r"frame=\s*(\d+)", r)
        _PROBE[key] = (int(fr[-1]) if fr else 0, "Audio:" in r.split("Output")[0])
    return _PROBE[key]


def transition_of(s, plan):
    t = s.get("transition", plan.get("transition", "cut"))
    t = dict(t) if isinstance(t, dict) else {"kind": t}
    k = ALIASES.get(str(t.get("kind", "cut")).lower(), str(t.get("kind", "cut")).lower())
    if k not in TWO | FRAME_KINDS | {"cut"}:
        raise SystemExit(f"unknown transition '{k}'")
    t["kind"] = k
    if k in TWO:
        t["frames"] = int(t.get("frames", plan.get("crossfade", DEFAULT_LEN[k]) if k == "dissolve" else DEFAULT_LEN[k]))
        if t["frames"] <= 0:
            t["kind"] = "cut"
    return t


def timeline(plan):
    """Shots with their place on the film timeline (frames). Every shot: start, dur, vis_start, vis_end, hold."""
    fps = int(plan.get("fps", 24))
    shots, specs = [], []
    for i, s in enumerate(plan["shots"]):
        sh = {"i": i, "name": s.get("name") or (s.get("card") or Path(s.get("src", f"shot{i}")).stem), "spec": s,
              "in": int(s.get("in", 0)), "hold": False, "trans": None, "mood": s.get("mood")}
        if "card" in s:
            sh.update(kind="card", path=None, src_frames=math.inf, audio=None)
        elif "color" in s and "src" not in s:
            sh.update(kind="color", path=None, src_frames=math.inf, audio=None)
        else:
            p = rel(plan, s["src"])
            if not p.exists():
                raise SystemExit(f"shot {i}: missing {p}")
            if p.suffix.lower() in STILLS:
                sh.update(kind="still", path=p, src_frames=math.inf, audio=None)
            else:
                n, has_a = probe(p, fps)
                a = s.get("audio", "own")
                audio = p if (a == "own" and has_a) else (None if a in ("own", "none", None) else rel(plan, a))
                sh.update(kind="video", path=p, src_frames=n, audio=audio)
        if "frames" in s:
            dur = int(s["frames"])
        elif "seconds" in s:
            dur = round(float(s["seconds"]) * fps)
        elif "out" in s:
            dur = int(s["out"]) - sh["in"]
        elif sh["kind"] == "video":
            dur = sh["src_frames"] - sh["in"]
        else:
            raise SystemExit(f"shot {i} ({sh['name']}): a still/card needs \"frames\" or \"seconds\"")
        if dur <= 0:
            raise SystemExit(f"shot {i} ({sh['name']}): no frames to show")
        sh["dur"] = dur
        if not shots:
            sh["start"] = 0
        else:
            prev = shots[-1]
            prev_end = prev["start"] + prev["dur"]
            t = transition_of(s, plan)
            if t["kind"] in TWO:
                L = t["frames"]
                h1, h2 = L // 2, L - L // 2
                mode = s.get("handles", plan.get("handles", "auto"))
                if mode == "auto":
                    tail_ok = prev["src_frames"] - (prev["in"] + prev["dur"]) >= h2
                    head_ok = sh["kind"] != "video" or sh["in"] >= h1
                    mode = "handles" if tail_ok and head_ok else "overlap"
                if mode == "handles":
                    sh["start"] = prev_end
                    sh["vis_start"] = prev_end - h1
                    prev["vis_end"] = prev_end + h2
                elif mode == "overlap":
                    sh["start"] = prev_end - L
                    sh["vis_start"] = sh["start"]
                elif mode == "hold":
                    sh["start"] = prev_end
                    sh["vis_start"] = prev_end
                    prev["vis_end"] = prev_end + L
                    prev["hold"] = True
                else:
                    raise SystemExit(f"unknown handles mode '{mode}' (auto | overlap | hold)")
                sh["trans"] = {**t, "mode": mode, "L": L}
            else:
                sh["start"] = prev_end
                if t["kind"] in FRAME_KINDS:
                    specs.append({**{k: v for k, v in t.items() if k != "frames"}, "at": prev_end / fps, "shot": i})
                    sh["trans"] = {**t, "mode": "computed"}
        sh.setdefault("vis_start", sh["start"])
        shots.append(sh)
    for sh in shots:
        sh.setdefault("vis_end", sh["start"] + sh["dur"])
    total = max(sh["start"] + sh["dur"] for sh in shots)
    return {"fps": fps, "frames": total, "shots": shots, "specs": specs}


def src_index(sh, n):
    """Source frame of shot sh at film frame n (clamped; a held shot freezes on its last frame)."""
    k = sh["in"] + n - sh["start"]
    hi = sh["in"] + sh["dur"] - 1 if sh["hold"] else (sh["src_frames"] - 1 if sh["src_frames"] != math.inf else k)
    return int(max(0, min(k, hi)))


# ------------------------------------------------------------------ pictures

def font(cands, size):
    from PIL import ImageFont
    for f in cands:
        if Path(f).exists():
            return ImageFont.truetype(f, size)
    return ImageFont.load_default()


def hexrgb(h, default=(0, 0, 0)):
    if not h:
        return default
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def render_card(s, W, H, out, seed=5):
    """Paper card with a title and an optional subtitle (the film_schnitt cards)."""
    from PIL import Image, ImageDraw
    rng = np.random.default_rng(seed)
    paper, ink = hexrgb(s.get("bg"), (246, 240, 226)), hexrgb(s.get("ink"), (43, 29, 20))
    base = np.ones((H, W, 3), np.float32) * np.array(paper) / 255 + rng.normal(0, 0.012, (H, W, 1))
    yy, xx = np.mgrid[0:H, 0:W]
    vign = 1 - 0.25 * (((xx - W / 2) / W) ** 2 + ((yy - H / 2) / H) ** 2) * 2.2
    img = Image.fromarray(((base * vign[..., None]).clip(0, 1) * 255).astype(np.uint8))
    d = ImageDraw.Draw(img)
    f = font(FONTS, int(96 * H / 720))
    b = d.textbbox((0, 0), s["card"], font=f)
    d.text(((W - b[2] + b[0]) / 2, H / 2 - 90 * H / 720 - b[1]), s["card"], font=f, fill=ink)
    if s.get("sub"):
        f2 = font(FONTS, int(38 * H / 720))
        b2 = d.textbbox((0, 0), s["sub"], font=f2)
        d.text(((W - b2[2] + b2[0]) / 2, H / 2 + 50 * H / 720), s["sub"], font=f2, fill=ink)
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out)
    return out


def fit_image(img, W, H, mode="contain"):
    from PIL import Image
    img = img.convert("RGB")
    sc = (max if mode == "cover" else min)(W / img.width, H / img.height)
    im = img.resize((max(1, round(img.width * sc)), max(1, round(img.height * sc))), Image.LANCZOS)
    canvas = Image.new("RGB", (W, H))
    canvas.paste(im, ((W - im.width) // 2, (H - im.height) // 2))
    return np.asarray(canvas)


def zoomed(arr, z):
    from PIL import Image
    if abs(z - 1) < 1e-4:
        return arr
    H, W = arr.shape[:2]
    cw, ch = W / z, H / z
    x0, y0 = (W - cw) / 2, (H - ch) / 2
    return np.asarray(Image.fromarray(arr).resize((W, H), Image.BICUBIC, box=(x0, y0, x0 + cw, y0 + ch)))


class Source:
    """Frames of one shot, read in increasing film-frame order."""

    def __init__(self, sh, W, H, fps, cache):
        self.sh, self.W, self.H = sh, W, H
        self.proc, self.last, self.pos = None, None, -1
        s = sh["spec"]
        if sh["kind"] == "card":
            sh["path"] = render_card(s, W, H, cache / "cards" / f"card_{sh['i']:02d}.png", seed=5 + sh["i"])
        if sh["kind"] in ("card", "still"):
            from PIL import Image
            self.still = fit_image(Image.open(sh["path"]), W, H, s.get("fit", "contain"))
        elif sh["kind"] == "color":
            self.still = np.zeros((H, W, 3), np.uint8) + np.array(hexrgb(s["color"]), np.uint8)
        else:
            first = src_index(sh, sh["vis_start"])
            scale = (f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H}" if s.get("fit") == "cover" else
                     f"scale={W}:{H}:force_original_aspect_ratio=decrease,pad={W}:{H}:(ow-iw)/2:(oh-ih)/2")
            vf = f"fps={fps},trim=start_frame={first},setpts=PTS-STARTPTS,{scale},setsar=1,format=rgb24"
            self.proc = subprocess.Popen([ffmpeg(), "-v", "error", "-i", str(sh["path"]), "-map", "0:v:0", "-vf", vf,
                                          "-f", "rawvideo", "-"], stdout=subprocess.PIPE,
                                         stderr=subprocess.DEVNULL)    # closed early on purpose: no broken-pipe noise
            self.pos = first - 1

    def frame(self, n):
        sh = self.sh
        if self.proc is None:
            z = sh["spec"].get("zoom")
            if z:
                u = min(max((n - sh["vis_start"]) / max(sh["vis_end"] - sh["vis_start"] - 1, 1), 0), 1)
                return zoomed(self.still, z[0] + (z[1] - z[0]) * u)
            return self.still
        want = src_index(sh, n)
        size = self.W * self.H * 3
        while self.pos < want:
            buf = self.proc.stdout.read(size)
            if len(buf) < size:
                if self.last is None:
                    raise SystemExit(f"shot {sh['name']}: no frames decoded from {sh['path']}")
                self.pos = want                    # clip shorter than expected: hold its last frame
                break
            self.last = np.frombuffer(buf, np.uint8).reshape(self.H, self.W, 3)
            self.pos += 1
        return self.last

    def close(self):
        if self.proc:
            self.proc.stdout.close()
            self.proc.wait()
            self.proc = None


def smooth(u):
    u = min(max(u, 0.0), 1.0)
    return u * u * (3 - 2 * u)


def blend(kind, a, b, u, color=(0, 0, 0)):
    a = a.astype(np.float32)
    b = b.astype(np.float32)
    if kind == "dissolve":
        out = a * (1 - u) + b * u
    elif kind == "dip":
        c = np.array(color, np.float32)
        out = a * (1 - 2 * u) + c * 2 * u if u < 0.5 else c * (2 - 2 * u) + b * (2 * u - 1)
    else:                                              # whip: both pictures slide left with horizontal motion blur
        H, W = a.shape[:2]
        sh = int(W * smooth(u))
        img = np.empty_like(b)
        img[:, :W - sh] = a[:, sh:]
        img[:, W - sh:] = b[:, :sh]
        r = int(60 * W / 1920 * math.sin(math.pi * u))
        if r > 0:
            c = np.cumsum(np.pad(img, ((0, 0), (r + 1, r), (0, 0)), mode="edge"), axis=1)
            img = (c[:, 2 * r + 1:] - c[:, :-2 * r - 1]) / (2 * r + 1)
        out = img
    return np.clip(out, 0, 255).astype(np.uint8)


def title_layer(t, W, H):
    from PIL import Image, ImageDraw
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    f = font(FONTS_TITLE, int(t.get("size", 120) * H / 720))
    tw = d.textlength(t["text"], font=f)
    d.text(((W - tw) / 2, H * t.get("y", 0.32)), t["text"], font=f, fill=hexrgb(t.get("color", "#ffd23f")) + (255,),
           stroke_width=max(2, int(8 * H / 720)), stroke_fill=(43, 29, 20, 255))
    a = np.asarray(img).astype(np.float32)
    return a[..., :3], a[..., 3:] / 255


def grade_filter(plan, W, H):
    vf = []
    if plan.get("grade"):
        vf.append("eq=contrast=1.08:saturation=1.12:gamma=0.98,"
                  "colorbalance=rs=0.04:bs=-0.04:rh=0.03:bh=-0.03:rm=0.02:bm=-0.02")
    if plan.get("letterbox"):
        bar = max(0, int((H - W / float(plan["letterbox"])) / 2))
        if bar:
            vf.append(f"drawbox=x=0:y=0:w=iw:h={bar}:color=black:t=fill,drawbox=x=0:y=ih-{bar}:w=iw:h={bar}:color=black:t=fill")
    return vf


def picture(plan, tl, out, cache):
    W, H = plan.get("size", [1280, 720])
    fps, total, shots = tl["fps"], tl["frames"], tl["shots"]
    vf = ["format=yuv420p"] + grade_filter(plan, W, H)
    enc = subprocess.Popen([ffmpeg(), "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                            "-r", str(fps), "-i", "-", "-vf", ",".join(vf), "-an", *h264(), "-pix_fmt", "yuv420p",
                            "-movflags", "+faststart", str(out)], stdin=subprocess.PIPE)
    title = plan.get("title")
    tl_rgb = tl_a = None
    if title:
        tl_rgb, tl_a = title_layer(title, W, H)
    srcs = {}
    blank = np.zeros((H, W, 3), np.uint8)
    for n in range(total):
        vis = [sh for sh in shots if sh["vis_start"] <= n < sh["vis_end"]]
        for sh in vis:
            if sh["i"] not in srcs:
                srcs[sh["i"]] = Source(sh, W, H, fps, cache)
        for i in [i for i in srcs if n >= shots[i]["vis_end"]]:
            srcs.pop(i).close()
        if not vis:
            img = blank
        elif len(vis) == 1:
            img = srcs[vis[0]["i"]].frame(n)
        else:
            a, b = vis[-2], vis[-1]
            tr = b["trans"] or {"kind": "dissolve", "L": max(1, a["vis_end"] - b["vis_start"])}
            L = max(1, a["vis_end"] - b["vis_start"])
            u = (n - b["vis_start"] + 1) / (L + 1)
            img = blend(tr["kind"], srcs[a["i"]].frame(n), srcs[b["i"]].frame(n), u, hexrgb(tr.get("color")))
        if title and title["from"] <= n / fps < title["to"]:
            t = n / fps - title["from"]
            d = title["to"] - title["from"]
            k = min(1.0, t / 0.3, max(0.0, (d - t) / 0.4))
            img = (img.astype(np.float32) * (1 - tl_a * k) + tl_rgb * tl_a * k).clip(0, 255).astype(np.uint8)
        enc.stdin.write(np.ascontiguousarray(img).tobytes())
    for s in srcs.values():
        s.close()
    enc.stdin.close()
    if enc.wait():
        raise SystemExit("encoding the picture failed")


# ------------------------------------------------------------------ sound

def load_audio(path):
    raw = subprocess.run([ffmpeg(), "-v", "error", "-i", str(path), "-map", "0:a:0", "-ac", "2", "-ar", str(SR),
                          "-f", "f32le", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32).reshape(-1, 2).astype(np.float32)


def write_wav(path, y, sr=SR):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    y = np.atleast_2d(y.T).T if y.ndim == 1 else y
    with wave.open(str(path), "wb") as w:
        w.setnchannels(y.shape[1])
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes((np.clip(y, -1, 1) * 32767).astype(np.int16).tobytes())


def ramp(n, up=True):
    x = np.sin(np.linspace(0, np.pi / 2, n)) if up else np.cos(np.linspace(0, np.pi / 2, n))
    return x.astype(np.float32)[:, None]


def shot_sound(tl, n_total):
    fps, shots = tl["fps"], tl["shots"]
    dia = np.zeros((n_total, 2), np.float32)
    S = lambda f: int(round(f / fps * SR))
    cache = {}
    for k, sh in enumerate(shots):
        if not sh.get("audio"):
            continue
        y = cache.setdefault(str(sh["audio"]), load_audio(sh["audio"]))
        a_start = sh["vis_start"]
        a_end = sh["start"] + sh["dur"] if sh["hold"] else sh["vis_end"]
        t0, t1 = S(a_start), min(S(a_end), n_total)
        off = int(round(float(sh["spec"].get("audio_offset", 0)) * SR))
        s0 = S(sh["in"] + a_start - sh["start"]) + off
        seg = np.zeros((t1 - t0, 2), np.float32)
        lo, hi = max(0, s0), min(len(y), s0 + (t1 - t0))
        if hi > lo:
            seg[lo - s0:hi - s0] = y[lo:hi]
        seg *= 10 ** (float(sh["spec"].get("gain_db", 0)) / 20)
        dc = min(int(0.01 * SR), len(seg) // 2)            # declick every edge
        if dc:
            seg[:dc] *= ramp(dc, True)
            seg[-dc:] *= ramp(dc, False)
        tr = sh["trans"]
        if tr and tr["kind"] in TWO and tr["mode"] != "hold":   # equal-power crossfade with the previous shot
            L = S(shots[k - 1]["vis_end"]) - t0
            if 0 < L <= len(seg):
                seg[:L] *= ramp(L, True)
        nxt = shots[k + 1] if k + 1 < len(shots) else None
        if nxt and nxt["trans"] and nxt["trans"]["kind"] in TWO and nxt["trans"]["mode"] != "hold":
            L = t1 - S(nxt["vis_start"])
            if 0 < L <= len(seg):
                seg[-L:] *= ramp(L, False)
        dia[t0:t1] += seg
    return dia


def activity(y, hop):
    """Speech/sound activity per hop (bool) + RMS dB per hop."""
    m = np.abs(y).mean(1) if y.ndim == 2 else np.abs(y)
    k = len(m) // hop
    rms = np.sqrt(np.mean((y[: k * hop] ** 2).reshape(k, hop, -1).mean(2), axis=1) + 1e-12)
    db = 20 * np.log10(rms)
    if not k or db.max() < -70:
        return np.zeros(k, bool), db
    act = db > max(db.max() - 35, -55)
    return act, db


def level_db(y, mask, hop):
    k = min(len(mask), len(y) // hop)
    if not k or not mask[:k].any():
        return None
    p = (y[: k * hop] ** 2).reshape(k, hop, -1).mean((1, 2))[mask[:k]]
    return float(10 * np.log10(p.mean() + 1e-12))


def music_bed(plan, tl, dia, n_total, cache):
    m = plan.get("music")
    if not m:
        return None, {}
    m = {"file": m} if isinstance(m, str) else dict(m)
    if m.get("score") is not None:
        import score
        opts = m["score"] if isinstance(m["score"], dict) else {}
        y = score.compose(score_cues(plan, tl, opts), n_total / SR, int(opts.get("seed", 0)),
                          opts.get("style", "light"), SR, opts.get("hits", ()))
        write_wav(cache / "score.wav", y)
        src = "score.py (seed %s, %s)" % (opts.get("seed", 0), opts.get("style", "light"))
    else:
        y = load_audio(rel(plan, m["file"]))
        src = m["file"]
    a = int(round(float(m.get("from", 0)) * SR))
    at = int(round(float(m.get("at", 0)) * SR))
    bed = np.zeros((n_total, 2), np.float32)
    piece = y[a:a + n_total - at]
    bed[at:at + len(piece)] = piece
    if m.get("fade_in"):
        f = min(int(float(m["fade_in"]) * SR), len(piece))
        bed[at:at + f] *= np.linspace(0, 1, f, dtype=np.float32)[:, None]
    if m.get("fade_out"):
        f = min(int(float(m["fade_out"]) * SR), n_total)
        bed[n_total - f:] *= np.linspace(1, 0, f, dtype=np.float32)[:, None]
    hop = SR // 100
    act, _ = activity(dia, hop)
    info = {"source": src}
    if m.get("duck", True) is False or not act.any():
        g = 10 ** (float(m.get("gain_db", 0)) / 20)
        info["mode"] = f"as is, gain {float(m.get('gain_db', 0)):+.1f} dB"
        return bed * g, info
    level, duck = float(m.get("level_db", -4)), float(m.get("duck_db", 12))
    ld = level_db(dia, act, hop)
    music_act, _ = activity(bed, hop)
    lm = level_db(bed, music_act, hop) or -20.0
    hi_db, lo_db = ld + level - lm, ld - duck - lm
    pre = int(0.15 * 100)                               # 150 ms pre-roll: duck before the first syllable
    tgt = act.astype(np.float32)
    tgt = np.maximum(tgt, np.concatenate([tgt[pre:], np.zeros(pre, np.float32)]))
    e = np.zeros_like(tgt)
    up, down = 1 - math.exp(-1 / 8), 1 - math.exp(-1 / 40)     # 80 ms attack, 400 ms release (10 ms hops)
    for i in range(len(tgt)):
        prev = e[i - 1] if i else tgt[0]
        e[i] = prev + (tgt[i] - prev) * (up if tgt[i] > prev else down)
    free = ~act & music_act[:len(act)] if len(music_act) >= len(act) else ~act

    def gain(hi, lo):
        g = np.repeat(10 ** ((hi * (1 - e) + lo * e) / 20), hop)
        return np.concatenate([g, np.full(n_total - len(g), g[-1] if len(g) else 1.0)])[:n_total].astype(np.float32)

    for _ in range(3):        # calibrate on the real (local) music level: the score is quieter in calm cues
        out = bed * gain(hi_db, lo_db)[:, None]
        under, over = level_db(out, act, hop), level_db(out, free, hop)
        if under is not None:
            lo_db += (ld - under) - duck
        if over is not None:
            hi_db += level - (over - ld)
    info["mode"] = f"ducked: {level:+.0f} dB to the dialogue level in the free parts, {-duck:+.0f} dB under speech"
    return bed * gain(hi_db, lo_db)[:, None], info


def loudnorm(src, dst, target):
    meas = subprocess.run([ffmpeg(), "-hide_banner", "-i", str(src), "-af",
                           f"loudnorm=I={target}:TP=-1.5:LRA=11:print_format=json", "-f", "null", "-"],
                          capture_output=True, text=True, errors="replace").stderr
    j = json.loads(meas[meas.rfind("{"):meas.rfind("}") + 1])
    measured = float(j["input_i"])             # "-inf" for (near) silent sound
    if not math.isfinite(measured) or measured < -70:
        print(f"   loudness: sound is (nearly) silent ({j['input_i']} LUFS) - left at its level, not normalised")
        gain = 0.0
    else:
        gain = target - measured               # one linear gain + a peak limiter: the dialogue/music balance stays
    af = f"volume={gain:.2f}dB,alimiter=limit=0.79:attack=5:release=60:level=disabled"     # limit -2 dBFS
    subprocess.run([ffmpeg(), "-y", "-v", "error", "-i", str(src), "-af", af, "-ar", str(SR), str(dst)], check=True)
    return measured if math.isfinite(measured) else None


def sound(plan, tl, out_wav, bed_wav, cache):
    n_total = int(round(tl["frames"] / tl["fps"] * SR))
    dia = shot_sound(tl, n_total)
    bed, info = music_bed(plan, tl, dia, n_total, cache)
    mix = dia + (bed if bed is not None else 0)
    hop = SR // 100
    act, _ = activity(dia, hop)
    rep = {"music": info}
    if bed is not None:
        write_wav(bed_wav, bed)
        d_db, m_db = level_db(dia, act, hop), level_db(bed, act, hop)
        if d_db is not None and m_db is not None:
            rep["dialogue_over_music_db"] = round(d_db - m_db, 1)
        free = ~act if act.any() else np.ones(len(act), bool)
        if d_db is not None:
            mf = level_db(bed, free, hop)
            rep["music_free_parts_vs_dialogue_db"] = round(mf - d_db, 1) if mf is not None else None
    rep["speech_seconds"] = round(float(act.sum()) / 100, 2)
    raw = cache / "sound_raw.wav"
    peak = float(np.abs(mix).max()) if len(mix) else 0
    write_wav(raw, mix / max(1.0, peak / 0.95))
    target = plan.get("loudness", -16)
    if target is None or peak == 0:
        shutil.copy(raw, out_wav)
    else:
        lufs = loudnorm(raw, out_wav, float(target))
        rep["loudness_in_lufs"] = round(lufs, 1) if lufs is not None else None
        rep["loudness_target_lufs"] = float(target)
    return rep


# ------------------------------------------------------------------ cues for score.py

def score_cues(plan, tl, opts):
    fps, shots = tl["fps"], tl["shots"]
    byname = {sh["name"]: sh for sh in shots}
    cues = []
    for c in opts.get("cues") or []:
        c = dict(c)
        if "shot" in c:
            sh = shots[c["shot"]] if isinstance(c["shot"], int) else byname.get(c["shot"])
            if sh is None:
                raise SystemExit(f"score cue: no shot '{c['shot']}'")
            c["at"] = sh["start"] / fps + float(c.get("offset", 0))
        cues.append(c)
    if not cues:
        last = None
        for sh in shots:
            if sh.get("mood") and sh["mood"] != last:
                cues.append({"at": sh["start"] / fps, "mood": sh["mood"]})
                last = sh["mood"]
    return cues or [{"at": 0, "mood": "playful"}]


# ------------------------------------------------------------------ hand-off

def media_path(p):
    return str(Path(p).resolve()).replace("\\", "/")


def write_otio(plan, tl, out, bed_wav):
    import opentimelineio as otio
    fps, shots = tl["fps"], tl["shots"]
    rt = lambda f: otio.opentime.RationalTime(f, fps)
    tr = lambda s, d: otio.opentime.TimeRange(rt(s), rt(d))
    cuts = []
    for sh in shots:
        t = sh["trans"]
        cuts.append(sh["vis_start"] + t["L"] // 2 if t and t["kind"] in TWO and t["mode"] != "hold" else sh["start"])
    tlx = otio.schema.Timeline(name=plan.get("name", "Film"))
    v1 = otio.schema.Track(name="V1 picture", kind=otio.schema.TrackKind.Video)
    for k, sh in enumerate(shots):
        c0 = cuts[k]
        c1 = cuts[k + 1] if k + 1 < len(shots) else sh["start"] + sh["dur"]
        t = sh["trans"]
        if k and t and t["kind"] in TWO and t["mode"] != "hold":
            v1.append(otio.schema.Transition(name="Dissolve", transition_type=otio.schema.TransitionTypes.SMPTE_Dissolve,
                                             in_offset=rt(t["L"] // 2), out_offset=rt(t["L"] - t["L"] // 2)))
        if sh["kind"] == "video":
            avail = tr(0, sh["src_frames"])
            src0 = sh["in"] + c0 - sh["start"]
        else:
            avail = tr(0, sh["vis_end"] - sh["vis_start"])
            src0 = c0 - sh["vis_start"]
        clip = otio.schema.Clip(name=sh["name"], source_range=tr(src0, c1 - c0),
                                media_reference=otio.schema.ExternalReference(target_url=media_path(sh["path"]),
                                                                              available_range=avail))
        if t and (t["kind"] in FRAME_KINDS or t["kind"] == "whip" or t["mode"] == "hold"):
            clip.markers.append(otio.schema.Marker(name=f"transition {t['kind']} ({t['mode']}) - only in the rendered film",
                                                   marked_range=tr(src0, 1)))
        v1.append(clip)
    tlx.tracks.append(v1)
    atr = [otio.schema.Track(name=f"A{i + 1} shot sound", kind=otio.schema.TrackKind.Audio) for i in range(2)]
    cursor = [0, 0]
    for k, sh in enumerate(shots):
        if not sh.get("audio"):
            continue
        a0 = sh["vis_start"]
        a1 = sh["start"] + sh["dur"] if sh["hold"] else sh["vis_end"]
        j = 0 if cursor[0] <= a0 else 1
        if cursor[j] > a0:
            j = int(np.argmin(cursor))
        if a0 > cursor[j]:
            atr[j].append(otio.schema.Gap(source_range=tr(0, a0 - cursor[j])))
        off = round(float(sh["spec"].get("audio_offset", 0)) * fps)
        atr[j].append(otio.schema.Clip(name=sh["name"] + " (sound)", source_range=tr(sh["in"] + a0 - sh["start"] + off, a1 - a0),
                                       media_reference=otio.schema.ExternalReference(target_url=media_path(sh["audio"]))))
        cursor[j] = a1
    for t in atr:
        if len(t):
            tlx.tracks.append(t)
    if bed_wav and Path(bed_wav).exists():
        a3 = otio.schema.Track(name="A3 music bed (ducked)", kind=otio.schema.TrackKind.Audio)
        a3.append(otio.schema.Clip(name="music bed", source_range=tr(0, tl["frames"]),
                                   media_reference=otio.schema.ExternalReference(target_url=media_path(bed_wav),
                                                                                 available_range=tr(0, tl["frames"]))))
        tlx.tracks.append(a3)
    otio.adapters.write_to_file(tlx, str(out))


# ------------------------------------------------------------------ main

def main():
    ap = argparse.ArgumentParser(description="Film cut from a shot list (films without a song timeline).")
    ap.add_argument("plan")
    ap.add_argument("--version")
    ap.add_argument("--out-dir")
    ap.add_argument("--no-otio", action="store_true")
    ap.add_argument("--no-versions", action="store_true", help="only film(.mp4), no small/mail versions")
    a = ap.parse_args()
    plan = load_plan(a.plan, a.version)
    out_dir = Path(a.out_dir).resolve() if a.out_dir else plan["_base"]
    out_dir.mkdir(parents=True, exist_ok=True)
    cache = out_dir / "cache"
    cache.mkdir(exist_ok=True)
    prefix = plan.get("out", "film") + (f"_{plan['_version']}" if plan["_version"] else "")
    tl = timeline(plan)
    fps, total = tl["fps"], tl["frames"]
    print(f"{len(tl['shots'])} shots, {total} frames = {total / fps:.2f} s" +
          (f", version {plan['_version']}" if plan["_version"] else ""))
    for sh in tl["shots"]:
        t = sh["trans"]
        print(f"  {sh['start']:6d}  {sh['dur']:5d} f  {sh['name'][:34]:34s} "
              f"{(t['kind'] + ' ' + t['mode'] + (' ' + str(t.get('L')) if t.get('L') else '')) if t else ''}")
    pic = cache / f"{prefix}_picture.mp4"
    picture(plan, tl, pic, cache)
    if tl["specs"]:
        import transitions
        try:
            from shaders_render import iris_masks as masks
        except Exception:
            masks = None
        pic2 = cache / f"{prefix}_picture_tr.mp4"
        _, changed = transitions.apply(pic, pic2, tl["specs"], 0.0, fps, iris_masks=masks)
        print(f"   frame-computed transitions: {len(tl['specs'])}, {changed} frames changed")
        pic = pic2
    wav = cache / f"{prefix}_sound.wav"
    bed_wav = out_dir / f"{prefix}_music_bed.wav"
    rep = sound(plan, tl, wav, bed_wav, cache)
    raw = cache / f"{prefix}_raw.mp4"
    subprocess.run([ffmpeg(), "-y", "-v", "error", "-i", str(pic), "-i", str(wav), "-map", "0:v", "-map", "1:a",
                    "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(raw)], check=True)
    tmp = cache / f"{prefix}_tmp.mp4"
    look = plan.get("look", "standard")
    if look in (None, "none"):
        shutil.copy(raw, tmp)
    else:
        subprocess.run([sys.executable, str(HERE / "apply_look.py"), str(raw), "-o", str(tmp), "--look", look,
                        "--strength", str(plan.get("look_strength", 1.0))], check=True)
    film = place(tmp, out_dir / f"{prefix}.mp4")
    results = [film]
    dur = total / fps
    targets = {}
    if not a.no_versions:
        W, H = plan.get("size", [1280, 720])
        for name, mb, side, ak in ((f"{prefix}_small", 29.0, 1280, 128), (f"{prefix}_mail", 12.0, 960, 64)):
            s = min(1.0, side / max(W, H))                     # long side <= 1280 / 960, never upscaled (portrait)
            w, h = int(round(W * s / 2) * 2), int(round(H * s / 2) * 2)
            target = cache / f"{name}_tmp.mp4"
            if film.stat().st_size < mb * 1e6:                  # already small enough (as build.py)
                shutil.copy(film, target)
            else:
                encode_target(film, target, mb, w, h, ak, dur)
            results.append(place(target, out_dir / f"{name}.mp4"))
            targets[results[-1]] = mb
    checks = {}
    for r in results:
        err = check_video(r)
        over = over_note(r, targets[r]) if r in targets else ""
        checks[r.name] = {"mb": round(r.stat().st_size / 1e6, 2), "decode_errors": err[:300] if err else 0}
        if r in targets:
            checks[r.name]["target_mb"], checks[r.name]["over_target"] = targets[r], bool(over)
        print(f"-> {r.name}: {r.stat().st_size / 1e6:.1f} MB{over}, {'0 decode errors' if not err else 'ERRORS: ' + err[:300]}")
    sheet = contact_sheet(film, out_dir / f"{prefix}_sheet.png", cols=4, rows=3, width=480, fps=fps)
    shots_json = out_dir / f"{prefix}_shots.json"
    shots_json.write_text(json.dumps({
        "fps": fps, "frames": total, "seconds": round(dur, 3), "version": plan["_version"],
        "shots": [{"name": sh["name"], "src": str(sh["path"]) if sh["path"] else None, "start": sh["start"],
                   "end": sh["start"] + sh["dur"], "vis_start": sh["vis_start"], "vis_end": sh["vis_end"],
                   "in": sh["in"], "transition": sh["trans"],
                   "subtitles": str(rel(plan, sh["spec"]["subtitles"])) if sh["spec"].get("subtitles") else None}
                  for sh in tl["shots"]]}, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    if any(sh["spec"].get("subtitles") for sh in tl["shots"]):
        import subtitles
        n = subtitles.write_from_cut(shots_json, out_dir / prefix)
        print(f"-> {prefix}.srt / {prefix}.vtt ({n} cues)")
    if not a.no_otio:
        try:
            write_otio(plan, tl, out_dir / f"{prefix}.otio", bed_wav)
            print(f"-> {prefix}.otio (Kdenlive: File > Import > OpenTimelineIO)")
        except ImportError:
            print("   opentimelineio missing - run with `uv run cut.py` (declares it) for the Kdenlive hand-off")
    rep.update({"frames": total, "seconds": round(dur, 3), "files": checks, "sheet": str(sheet)})
    (out_dir / f"{prefix}_report.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    lv = rep.get("dialogue_over_music_db")
    print(f"   {dur:.2f} s, look {look}, music: {rep['music'].get('mode', 'none')}"
          + (f", dialogue {lv:+.1f} dB over the music under speech" if lv is not None else ""))


if __name__ == "__main__":
    main()
