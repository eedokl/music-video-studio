"""Check (and set up) the external programs the animation-studio plugin needs.

  python check_tools.py                 report: found / missing / optional, with the path used and an install hint
  python check_tools.py --setup         search PATH and the usual install folders on every drive, store what was
                                        found in the machine config (~/.animation-studio/config.json), plus the
                                        plugin folder (animation_studio_root, read by toon-2d scene shims)
  python check_tools.py --set key=value [key=value ...]   store paths by hand (e.g. gpu_lock_dir=D:/tools)
Exit code 1 when a REQUIRED program is missing. Never installs anything: show the missing lines to the user and ask.
Known keys: the programs in TOOLS below plus config.SETTINGS (gpu_lock_dir, hf_home, torch_home, comfy_url,
comfy_dir, comfy_start, sfx_cache, font, rife_model, minimax_api_base, claudia_refs, animation_studio_root);
--set refuses any other key (typo protection). ffmpeg is only stored when it has the libx264 encoder.
Environment overrides: ANIMATION_STUDIO_<KEY>, plain names only for the unambiguous keys (see config.py).
"""
import difflib
import json
import os
import shutil
import string
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import _studio  # noqa: E402
_studio.use()
import config  # noqa: E402

PLUGIN_ROOT = Path(__file__).resolve().parents[3]       # <plugin>/skills/studio-core/scripts -> <plugin>

# key: (required, what for, install hint, glob patterns relative to a drive root / Program Files)
TOOLS = {
    "ffmpeg": (True, "sound, cutting, encoding (needs libx264)", "https://ffmpeg.org or Kdenlive (ships ffmpeg)",
               ["*Kdenlive*/bin/ffmpeg.exe", "*ffmpeg*/bin/ffmpeg.exe", "*ffmpeg*/ffmpeg.exe"]),
    "synfig": (True, "rendering 2D scenes", "https://www.synfig.org/download-stable/", ["*Synfig*/bin/synfig.exe"]),
    "inkscape": (True, "SVG characters -> paths", "https://inkscape.org", ["*Inkscape*/bin/inkscape.exe"]),
    "rhubarb": (True, "mouth shapes from voices", "https://github.com/DanielSWolf/rhubarb-lip-sync/releases",
                ["*Rhubarb*/rhubarb.exe", "*rhubarb*/*/rhubarb.exe"]),
    "earshot": (False, "hearing male/female voices, sound-effect bank",
                "without it: voices follow lyric markers/corrections, no sound effects", []),
    "gpu_python": (False, "Whisper large-v3 and Demucs on the GPU (python.exe of a CUDA venv)",
                   "without it: Whisper small and Demucs on the CPU (slower, less exact)", []),
    "blender": (False, "brick films, 3D gags, Grease Pencil", "https://www.blender.org (needed for bricks-music-video)",
                ["*Blender Foundation*/Blender*/blender.exe", "Blender*/blender.exe"]),
    "ldraw_dir": (False, "LDraw parts library folder (brick films)",
                  "ask first: complete.zip from library.ldraw.org, unpack, then --set ldraw_dir=<folder>",
                  ["*/ldraw/LDConfig.ldr", "*/*/ldraw/LDConfig.ldr", "ldraw/LDConfig.ldr"]),
    "melt": (False, "MLT renderer: writes/plays film.mlt for the hand-off to Kdenlive/Shotcut",
             "ships with Kdenlive (bin/melt.exe) or Shotcut", ["*Kdenlive*/bin/melt.exe", "*Shotcut*/melt.exe"]),
    "shaders": (False, "folder with node_modules/shaders (npm shaders 4.0.6, WebGPU) - new looks and iris masks",
                "ask first: film-finish shaders_render.py --install (~40 MB npm)", ["*/node_modules/shaders/package.json"]),
    "krita": (False, "painting new sets", "https://krita.org (only for new sets)", ["*Krita*/bin/kritarunner.exe"]),
    "node": (False, "three.js renders (lyric videos, multiplane camera, comic flight)", "https://nodejs.org",
             ["nodejs/node.exe"]),
    "chrome": (False, "headless chrome-headless-shell for the lyric-video render (Edge/Chrome via 'browser' also work)",
               "ask the user; lyric-music-video can download it with INSTALL_BROWSER=1", []),
    "browser": (False, "headless Chrome/Edge for three.js renders", "Chrome, Edge or chrome-headless-shell",
                ["Microsoft/Edge/Application/msedge.exe", "Google/Chrome/Application/chrome.exe"]),
    "face_landmarker": (False, "MediaPipe face_landmarker.task model for measuring mouths (claudia-music-video)",
                        "download face_landmarker.task from Google's MediaPipe model page (ask first)", ["*/mediapipe/face_landmarker.task"]),
    "comfy_start": (False, "script that starts ComfyUI when it is not running", "the ComfyUI start script of this machine", []),
    "claudia_refs": (False, "reference images of Claudia (folder, or a.png;b.png)", "the user's Claudia reference sheet", []),
    "realesrgan": (False, "Real-ESRGAN ncnn-vulkan upscaler (painted panels, slide figures)",
                   "https://github.com/xinntao/Real-ESRGAN/releases (ncnn-vulkan build; ask first)",
                   ["*/realesrgan-ncnn-vulkan*/realesrgan-ncnn-vulkan.exe", "*/*/realesrgan-ncnn-vulkan*/realesrgan-ncnn-vulkan.exe"]),
    "rife": (False, "RIFE ncnn-vulkan frame interpolation (film-finish fps48.py: 48 fps only in camera moves)",
             "https://github.com/nihui/rife-ncnn-vulkan/releases (Windows build, unpack; ask first)",
             ["*/rife-ncnn-vulkan*/rife-ncnn-vulkan.exe", "*/*/rife-ncnn-vulkan*/rife-ncnn-vulkan.exe",
              "*/*/*/rife-ncnn-vulkan*/rife-ncnn-vulkan.exe"]),
    "tts_python": (False, "Qwen3-TTS voices (python.exe of a venv with qwen-tts + CUDA torch)",
                   "ask first: uv venv; uv pip install qwen-tts torch --index-url https://download.pytorch.org/whl/cu128 "
                   "(models ~4 GB each go to hf_home); without it: Piper or the Windows voices", []),
    "piper": (False, "Piper TTS (fast CPU voices, fallback)", "pip install piper-tts (ask first)", []),
    "piper_voices": (False, "folder with Piper <model>.onnx + .onnx.json voices", "e.g. de_DE-thorsten-high", []),
}


VALUE_KEYS = {"claudia_refs", "comfy_start"}           # values, not single files: reported as "set", not checked
KNOWN = set(TOOLS) | set(config.PROGRAMS) | set(config.SETTINGS)
DRIVE_ROOT_DEPTH = 2                                     # on a bare drive root only patterns up to 2 folders deep


def has_x264(exe):
    try:
        r = subprocess.run([exe, "-hide_banner", "-encoders"], capture_output=True, text=True, errors="replace",
                           timeout=30)
    except (OSError, subprocess.SubprocessError):
        return False
    return "libx264" in r.stdout


VALIDATE = {"ffmpeg": has_x264}                         # a found program is only stored when it passes


def candidates(patterns):
    drives = [f"{d}:/" for d in string.ascii_uppercase if Path(f"{d}:/").exists()] or ["/"]
    for drive in drives:
        root = Path(drive)
        for base in (root / "Program Files", root / "Program Files (x86)", root / "Programs", root):
            if not base.is_dir():
                continue
            for pat in patterns:
                if base == root and pat.count("/") > DRIVE_ROOT_DEPTH:
                    continue                             # deep globs over a whole drive take minutes
                try:
                    for hit in base.glob(pat):
                        if hit.is_file():
                            yield str(hit)
                            break
                except OSError:
                    pass


def search(patterns, ok=None):
    return next((p for p in candidates(patterns) if not ok or ok(p)), None)


def write(values):
    cfg = {}
    if config.LOCAL.exists():
        try:
            cfg = json.loads(config.LOCAL.read_text(encoding="utf-8"))
            if not isinstance(cfg, dict):
                raise ValueError("not a JSON object")
        except ValueError as e:
            bad = config.LOCAL.with_name(config.LOCAL.name + f".bad-{time.strftime('%Y%m%d-%H%M%S')}")
            shutil.copy(config.LOCAL, bad)
            print(f"warning: {config.LOCAL} was not valid JSON ({e}) - kept as {bad.name}, starting a new one")
            cfg = {}
    new = {k: v for k, v in values.items() if v}
    cfg.update(new)
    config.LOCAL.parent.mkdir(parents=True, exist_ok=True)
    tmp = config.LOCAL.with_name(config.LOCAL.name + ".tmp")
    tmp.write_text(json.dumps(cfg, indent=1), encoding="utf-8")
    os.replace(tmp, config.LOCAL)                        # atomic: a crash never leaves half a config
    print(f"saved {len(new)} entries -> {config.LOCAL}")


def comfy():
    try:
        urllib.request.urlopen(config.comfy_url() + "/system_stats", timeout=2)
        return config.comfy_url()
    except Exception:
        return None


def report():
    missing = 0
    print(f"   {'tool':12}{'status':10}path / hint")
    for key, (req, what, hint, _) in TOOLS.items():
        p = config.get(key)
        ok = p and (key in VALUE_KEYS or Path(p).exists() or shutil.which(p))
        if ok:
            print(f"OK {key:12}{'set' if key in VALUE_KEYS else 'found':10}{p}")
        else:
            missing += req
            print(f"{'!!' if req else '--'} {key:12}{'MISSING' if req else 'optional':10}{what} -> {hint}")
    ff = config.get("ffmpeg")
    if ff and (Path(ff).exists() or shutil.which(ff)) and not has_x264(ff):
        missing += 1
        print(f"!! {'ffmpeg':12}{'no x264':10}{ff} has no libx264 encoder - every encode fails; use another build")
    npm = shutil.which("npm") or shutil.which("npm.cmd")
    print(f"   {'npm':12}{'found' if npm else 'missing':10}{npm or 'comes with Node.js (lyric-music-video)'}")
    print(f"   {'uv':12}{'found' if shutil.which('uv') else 'MISSING':10}{shutil.which('uv') or 'https://docs.astral.sh/uv/'}")
    missing += 0 if shutil.which("uv") else 1
    print(f"   {'gpu lock':12}{'':10}{config.lock_dir()}  (share it with other GPU pipelines: --set gpu_lock_dir=...)")
    print(f"   {'ComfyUI':12}{'running' if comfy() else 'off':10}{config.comfy_url()}  (only for ai-video / painted panels)")
    print(f"   {'plugin':12}{'':10}{config.get('animation_studio_root') or 'not stored (check_tools.py --setup)'}")
    print(f"   {'config':12}{'':10}{config.LOCAL}")
    print("\nAll required tools found." if not missing else
          f"\n{missing} required tool(s) missing - show these lines to the user and ask before installing anything.")
    return 1 if missing else 0


def parse_set(items):
    values, bad = {}, []
    for a in items:
        if "=" not in a:
            continue
        k, v = a.split("=", 1)
        k = k.strip().lower()
        if k in KNOWN:
            values[k] = v
        else:
            close = difflib.get_close_matches(k, sorted(KNOWN), n=1)
            bad.append(f"{k}" + (f" (did you mean {close[0]}?)" if close else ""))
    if bad:
        raise SystemExit("unknown config key(s): " + ", ".join(bad) + " - nothing saved.\nKnown keys: "
                         + ", ".join(sorted(KNOWN)))
    return values


def main():
    args = sys.argv[1:]
    if "--set" in args:
        write(parse_set(args[args.index("--set") + 1:]))
    elif "--setup" in args:
        found = {"animation_studio_root": str(PLUGIN_ROOT)}
        for key, (_, _, _, pats) in TOOLS.items():
            ok = VALIDATE.get(key)
            p = config.get(key)
            if p and ok and not ok(p):
                print(f"   {key}: {p} fails the check (ffmpeg without libx264?) - searching another one")
                p = None
            p = p or (search(pats, ok) if pats else None)
            if p and key.endswith("_dir") and Path(p).is_file():
                p = str(Path(p).parent)                    # a marker file was searched - store its folder
            if p and key == "shaders" and Path(p).is_file():
                p = str(Path(p).parents[2])                # .../<dir>/node_modules/shaders/package.json -> <dir>
            if p:
                found[key] = p
        write(found)
    sys.exit(report())


if __name__ == "__main__":
    main()
