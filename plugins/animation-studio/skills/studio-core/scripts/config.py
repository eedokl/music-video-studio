"""Machine configuration: where the external programs, caches and the GPU lock live.

The skill ships without any machine paths. Lookup order for every entry:
  1. environment variable (e.g. SYNFIG=/path/to/synfig)
  2. the machine config file ~/.animation-studio/config.json (or the file named by ANIMATION_STUDIO_CONFIG),
     written by `check_tools.py --setup`; it lives outside the plugin so it survives plugin updates
  3. the program name on PATH
If a required program is missing, `need()` stops with a clear message pointing to check_tools.py.

Entries (env var = JSON key in lower case):
  FFMPEG      ffmpeg with libx264 and PNG decoding         FFPROBE   ffprobe (optional, falls back to ffmpeg -i)
  SYNFIG      synfig command-line renderer (1.4+)           INKSCAPE  inkscape 1.x (SVG -> paths)
  RHUBARB     rhubarb lip sync                              EARSHOT   earshot launcher (optional: who sings, sounds)
  GPU_PYTHON  python of a CUDA venv with torch, demucs, faster-whisper (optional, faster)
  GPU_LOCK_DIR  folder of the shared GPU lock file (share it with other GPU pipelines on the machine)
  HF_HOME / TORCH_HOME  model caches (optional; library defaults otherwise)
  LDRAW_DIR   LDraw parts library (bricks)              BLENDER   blender (bricks, 3D gags)
  More keys (face_landmarker, comfy_start, tts_python, piper, realesrgan, ...): see check_tools.py.
  COMFY_URL   ComfyUI server to flush on a model change (optional, default http://127.0.0.1:8188)
"""
import json
import os
import shutil
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
SKILL = SCRIPTS.parent
ASSETS = SKILL / "assets"
LOCAL = Path(os.environ.get("ANIMATION_STUDIO_CONFIG", Path.home() / ".animation-studio" / "config.json"))

PROGRAMS = {  # key: (names on PATH, required?, what for)
    "ffmpeg": (["ffmpeg"], True, "sound, cutting, encoding"),
    "ffprobe": (["ffprobe"], False, "reading durations (falls back to ffmpeg)"),
    "synfig": (["synfig"], True, "rendering scenes"),
    "inkscape": (["inkscape"], True, "turning SVG characters into paths"),
    "rhubarb": (["rhubarb"], True, "mouth shapes from the vocals"),
    "earshot": (["earshot"], False, "hearing male/female voices, sound-effect bank"),
    "gpu_python": ([], False, "Whisper large-v3 and Demucs on the GPU"),
    "blender": (["blender"], False, "brick films, 3D gags, Grease Pencil"),
    "krita": (["kritarunner"], False, "painting new sets"),
    "node": (["node"], False, "three.js renders (lyric videos, multiplane, comic flight)"),
    "browser": (["chrome", "msedge", "chromium"], False, "headless browser for three.js renders"),
    "realesrgan": (["realesrgan-ncnn-vulkan"], False, "upscaling painted panels and slide figures"),
}


def _local():
    try:
        return json.loads(LOCAL.read_text(encoding="utf-8"))
    except Exception:
        return {}


def get(key):
    """Value of a config entry or None."""
    v = os.environ.get(key.upper()) or _local().get(key)
    if v:
        return str(v)
    names = PROGRAMS.get(key, ([],))[0]
    for n in names:
        w = shutil.which(n)
        if w:
            return w
    return None


def need(key):
    """Path of a required program; stops with a helpful message if it is missing."""
    v = get(key)
    if not v or (not Path(v).exists() and not shutil.which(v)):
        what = PROGRAMS.get(key, ([], True, ""))[2]
        raise SystemExit(f"'{key}' not found ({what}). Run `python {SCRIPTS / 'check_tools.py'} --setup`, "
                         f"or set the environment variable {key.upper()}.")
    return v


def setup_env():
    """Set model caches from the config (call before importing torch / faster-whisper)."""
    for k in ("hf_home", "torch_home"):
        v = get(k)
        if v:
            os.environ.setdefault(k.upper(), v)
    ff = get("ffmpeg")
    if ff and Path(ff).exists():                       # libraries that call plain "ffmpeg" find ours
        os.environ["PATH"] = str(Path(ff).parent) + os.pathsep + os.environ.get("PATH", "")


def lock_dir():
    return Path(get("gpu_lock_dir") or (Path.home() / ".cache" / "gpu-lock"))


def comfy_url():
    return get("comfy_url") or "http://127.0.0.1:8188"


def gpu_runner(packages):
    """Command prefix for a GPU script: the configured CUDA venv python, else `uv run` with CPU packages."""
    py = get("gpu_python")
    if py and Path(py).exists():
        return [py]
    return ["uv", "run", "--no-project"] + [x for p in packages for x in ("--with", p)] + ["python"]
