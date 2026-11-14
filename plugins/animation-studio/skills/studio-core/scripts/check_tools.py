"""Check (and set up) the external programs the animation-studio plugin needs.

  python check_tools.py                 report: found / missing / optional, with the path used and an install hint
  python check_tools.py --setup         search PATH and the usual install folders on every drive, store what was
                                        found in the machine config (~/.animation-studio/config.json)
  python check_tools.py --set key=value [key=value ...]   store paths by hand (e.g. gpu_lock_dir=D:/tools)
Exit code 1 when a REQUIRED program is missing. Never installs anything: show the missing lines to the user and ask.
Keys: ffmpeg, ffprobe, synfig, inkscape, rhubarb, earshot, blender, krita, gpu_python, gpu_lock_dir, hf_home,
torch_home, comfy_url, tts_python.
"""
import json
import shutil
import string
import sys
import urllib.request
from pathlib import Path

import _studio  # noqa: E402
_studio.use()
import config  # noqa: E402

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


def search(patterns):
    for drive in [f"{d}:/" for d in string.ascii_uppercase if Path(f"{d}:/").exists()] or ["/"]:
        for base in (Path(drive), Path(drive) / "Program Files", Path(drive) / "Program Files (x86)", Path(drive) / "Programs"):
            for pat in patterns:
                try:
                    hit = next(base.glob(pat), None)
                except OSError:
                    hit = None
                if hit and hit.is_file():
                    return str(hit)
    return None


def write(values):
    cfg = {}
    if config.LOCAL.exists():
        cfg = json.loads(config.LOCAL.read_text(encoding="utf-8"))
    cfg.update({k: v for k, v in values.items() if v})
    config.LOCAL.parent.mkdir(parents=True, exist_ok=True)
    config.LOCAL.write_text(json.dumps(cfg, indent=1), encoding="utf-8")
    print(f"saved {len(values)} entries -> {config.LOCAL}")


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
        ok = p and (Path(p).exists() or shutil.which(p))
        if ok:
            print(f"OK {key:12}{'found':10}{p}")
        else:
            missing += req
            print(f"{'!!' if req else '--'} {key:12}{'MISSING' if req else 'optional':10}{what} -> {hint}")
    npm = shutil.which("npm") or shutil.which("npm.cmd")
    print(f"   {'npm':12}{'found' if npm else 'missing':10}{npm or 'comes with Node.js (lyric-music-video)'}")
    print(f"   {'uv':12}{'found' if shutil.which('uv') else 'MISSING':10}{shutil.which('uv') or 'https://docs.astral.sh/uv/'}")
    missing += 0 if shutil.which("uv") else 1
    print(f"   {'gpu lock':12}{'':10}{config.lock_dir()}  (share it with other GPU pipelines: --set gpu_lock_dir=...)")
    print(f"   {'ComfyUI':12}{'running' if comfy() else 'off':10}{config.comfy_url()}  (only for ai-video / painted panels)")
    print(f"   {'config':12}{'':10}{config.LOCAL}")
    print("\nAll required tools found." if not missing else
          f"\n{missing} required tool(s) missing - show these lines to the user and ask before installing anything.")
    return 1 if missing else 0


def main():
    args = sys.argv[1:]
    if "--set" in args:
        write(dict(a.split("=", 1) for a in args[args.index("--set") + 1:] if "=" in a))
    elif "--setup" in args:
        found = {}
        for key, (_, _, _, pats) in TOOLS.items():
            p = config.get(key) or (search(pats) if pats else None)
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
