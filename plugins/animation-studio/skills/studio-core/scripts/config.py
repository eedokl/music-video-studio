"""Machine configuration: where the external programs, caches and the GPU lock live.

The skill ships without any machine paths. Lookup order for every entry:
  1. environment variable ANIMATION_STUDIO_<KEY> (e.g. ANIMATION_STUDIO_SYNFIG=/path/to/synfig); for the unambiguous
     keys in BARE_ENV also the plain name (FFMPEG, SYNFIG, HF_HOME, ...). Generic names such as BROWSER (often a
     URL-opener script), NODE, CHROME, BLENDER, MELT, PIPER, SHADERS or RIFE are NOT read - use the prefixed form.
  2. the machine config file ~/.animation-studio/config.json (or the file named by ANIMATION_STUDIO_CONFIG),
     written by `check_tools.py --setup`; it lives outside the plugin so it survives plugin updates
  3. the program name on PATH
If a required program is missing, `need()` stops with a clear message pointing to check_tools.py.

Programs (JSON key = lower case; env ANIMATION_STUDIO_<KEY>, plain name too where marked *):
  ffmpeg*     ffmpeg with libx264 and PNG decoding         ffprobe*  ffprobe (optional, falls back to ffmpeg -i)
  synfig*     synfig command-line renderer (1.4+)           inkscape* inkscape 1.x (SVG -> paths)
  rhubarb*    rhubarb lip sync                              earshot*  earshot launcher (optional: who sings, sounds)
  gpu_python* python of a CUDA venv with torch, demucs, faster-whisper (optional, faster)
  blender, krita, node, browser, chrome, melt, realesrgan, rife, piper, tts_python ...: see check_tools.py
Settings (not programs):
  gpu_lock_dir*  folder of the shared GPU lock file (share it with other GPU pipelines on the machine)
  hf_home* / torch_home*  model caches (optional; library defaults otherwise)
  ldraw_dir*  LDraw parts library (bricks)              comfy_url*  ComfyUI server (default http://127.0.0.1:8188)
  comfy_dir*  ComfyUI folder (optional: ai-video night_run.py --clean-comfy and the free-space check)
  animation_studio_root  the plugin folder (env ANIMATION_STUDIO_ROOT) - read by toon-2d scene shims; written by
              check_tools.py --setup and toon-2d new_scene.py
  sfx_cache, comfy_start, comfy_models, font, rife_model, minimax_api_base, claudia_refs, actors3d, awake: see SETTINGS below.
"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
SKILL = SCRIPTS.parent
ASSETS = SKILL / "assets"
LOCAL = Path(os.environ.get("ANIMATION_STUDIO_CONFIG", Path.home() / ".animation-studio" / "config.json"))
ENV_PREFIX = "ANIMATION_STUDIO_"

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

# settings that are not programs (folders, URLs, command lines, lists) - known keys for check_tools --set
SETTINGS = {
    "gpu_lock_dir": "folder of the shared GPU lock file",
    "hf_home": "Hugging Face model cache",
    "torch_home": "torch model cache",
    "comfy_url": "ComfyUI server URL (default http://127.0.0.1:8188)",
    "comfy_dir": "ComfyUI folder (input/output folders of the workflows)",
    "comfy_start": "command or script that starts ComfyUI when it is not running",
    "comfy_models": "JSON file overriding model file names of ai-video's assets/models.json (other ComfyUI file names)",
    "sfx_cache": "one earshot sound-effect bank folder shared by all projects",
    "font": "TTF font for labels and contact sheets",
    "rife_model": "RIFE model folder (default: rife-v4.6 next to the RIFE exe)",
    "minimax_api_base": "MiniMax API base URL",
    "claudia_refs": "reference images of Claudia (folder, or a.png;b.png)",
    "animation_studio_root": "the plugin folder, read by toon-2d scene shims (env ANIMATION_STUDIO_ROOT)",
    "actors3d": "folder(s) of realistic 3D actors (<name>/figur.blend, Rigify) for stage-3d \"figures\": \"rigify\"",
    "awake": "0 = let the computer sleep during long jobs (default: kept awake while a job holds the GPU lock)",
}

# documented, unambiguous keys whose plain upper-case environment name is read as well (after the prefixed one)
BARE_ENV = {"ffmpeg", "ffprobe", "synfig", "inkscape", "rhubarb", "earshot", "gpu_python", "gpu_lock_dir",
            "hf_home", "torch_home", "ldraw_dir", "comfy_url", "comfy_dir"}


def env_names(key):
    """Environment variables read for a key, in order."""
    k = key.upper()
    if k.startswith(ENV_PREFIX):                       # animation_studio_root -> ANIMATION_STUDIO_ROOT
        return [k]
    return [ENV_PREFIX + k] + ([k] if key in BARE_ENV else [])


def _local():
    try:
        return json.loads(LOCAL.read_text(encoding="utf-8"))
    except Exception:
        return {}


def get(key):
    """Value of a config entry or None."""
    v = next((os.environ[n] for n in env_names(key) if os.environ.get(n)), None) or _local().get(key)
    if v:
        return str(v)
    names = PROGRAMS.get(key, ([],))[0]
    for n in names:
        w = shutil.which(n)
        if w:
            return w
    if key == "ffprobe":                                  # ffprobe ships next to ffmpeg (e.g. Kdenlive's bin folder)
        ff = get("ffmpeg")
        if ff and Path(ff).exists():
            p = Path(ff).with_name(Path(ff).name.replace("ffmpeg", "ffprobe"))
            if p.exists():
                return str(p)
    return None


def need(key):
    """Path of a required program; stops with a helpful message if it is missing."""
    v = get(key)
    if not v or (not Path(v).exists() and not shutil.which(v)):
        what = PROGRAMS.get(key, ([], True, ""))[2]
        raise SystemExit(f"'{key}' not found ({what}). Run `python {SCRIPTS / 'check_tools.py'} --setup`, "
                         f"or set the environment variable {env_names(key)[0]}.")
    return v


def cmdline(cmd):
    """Argument list -> what subprocess.run needs. A Windows .cmd/.bat launcher (earshot) runs through
    `cmd /d /s /c "<line>"`: with a plain ["cmd", "/c", ...] cmd.exe strips the wrong quotes as soon as the launcher
    path contains a space and another argument is quoted."""
    cmd = [str(c) for c in cmd]
    if os.name == "nt" and cmd and cmd[0].lower().endswith((".cmd", ".bat")):
        return f'cmd /d /s /c "{" ".join(_bat_arg(c) for c in cmd)}"'
    return cmd


_BAT_SPECIAL = set(' \t&|<>^()%!"')


def _bat_arg(a):
    """One argument for a cmd.exe command line that ends in a batch file (which passes it on with %*):
    quoted whenever it contains whitespace or a cmd metacharacter (& | < > ^ ( ) % ! ") so cmd.exe never runs or
    redirects anything; an inner " is doubled; every % becomes %%cd:~,% (cmd expands %cd:~,% to nothing), so a
    %NAME% in an argument is passed on literally instead of being expanded. Line breaks cannot be passed safely."""
    if "\n" in a or "\r" in a:
        raise ValueError("a line break cannot be passed to a .cmd/.bat launcher")
    if a and not (set(a) & _BAT_SPECIAL):
        return a
    return '"' + a.replace('"', '""').replace("%", "%%cd:~,%") + '"'


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


def script_cmd(script):
    """Command that runs another plugin script with the packages of its own PEP 723 header (`uv run script.py`);
    plain python only when uv is missing."""
    uv = shutil.which("uv")
    return [uv, "run", str(script)] if uv else [sys.executable, str(script)]


def gpu_runner(packages):
    """Command prefix for a GPU script: the configured CUDA venv python, else `uv run` with CPU packages."""
    py = get("gpu_python")
    if py and Path(py).exists():
        return [py]
    return ["uv", "run", "--no-project"] + [x for p in packages for x in ("--with", p)] + ["python"]
