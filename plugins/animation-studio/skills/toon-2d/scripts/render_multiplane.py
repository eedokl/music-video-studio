"""Render a multiplane camera move or a 2.5D comic flight (three.js in headless Edge/Chrome) -> PNG frames -> MP4.

Usage:
  uv run --no-project python render_multiplane.py <scene>/multiplane.json [--gif] [--contact auto|0,40,80|none]
  uv run --no-project python render_multiplane.py <scene>/comic.json --page comic25d [--gif]

The config lives in the scene folder; every path inside it is relative to that folder.
  --page multiplane (default)  layers as glass planes at real depths, camera keys x/y/z/pan/tilt
  --page comic25d              comic page with panel windows, a diorama behind each window, camera keys per panel
Output: <out>/mp_NNNN.png (config key "out", default frames_mp), <config>.mp4, <config>.gif, contact_mp.png

Needs node (config key "node" or on PATH) and Edge or Chrome (config key "browser", PATH, or the usual install
folders). Renders on the GPU by default (ANGLE/D3D11, ~3x faster than software); --software uses SwiftShader.
A watchdog aborts after --startup seconds without a (new) frame or as soon as the page reports an ERROR, and prints
the page URL to open in a normal browser for debugging.
"""
import argparse
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _studio  # noqa: E402
_studio.use()
import config  # noqa: E402
from encoding import h264  # noqa: E402

HERE = Path(__file__).resolve().parent
PAGES = {"multiplane": "/_mp/multiplane.html", "comic25d": "/_mp/comic25d.html", "comic": "/_mp/comic25d.html"}


def find_browser():
    b = config.get("browser")
    if b and Path(b).exists():
        return b
    for n in ("msedge", "chrome", "google-chrome", "chromium", "chromium-browser"):
        w = shutil.which(n)
        if w:
            return w
    for env in ("ProgramFiles(x86)", "ProgramFiles", "LOCALAPPDATA"):
        root = os.environ.get(env)
        if not root:
            continue
        for rel in ("Microsoft/Edge/Application/msedge.exe", "Google/Chrome/Application/chrome.exe"):
            p = Path(root) / rel
            if p.exists():
                return str(p)
    mac = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
    if mac.exists():
        return str(mac)
    sys.exit("No Edge/Chrome found - set the config key 'browser' (check_tools.py --set browser=...)")


def kill_tree(proc, marker=None):
    """Stop the browser and its children. On Windows proc.kill() only hits the launcher - Edge hands off to child
    processes that keep running headless and slow down later renders. So also stop every browser process whose
    command line contains our own temporary profile folder (marker) - never other browser windows."""
    if proc.poll() is None:
        if os.name == "nt":
            subprocess.run(["taskkill", "/T", "/F", "/PID", str(proc.pid)], capture_output=True)
        else:
            proc.kill()
    if marker and os.name == "nt":
        ps = ("Get-CimInstance Win32_Process -Filter \"Name='msedge.exe' or Name='chrome.exe'\" | "
              f"Where-Object {{ $_.CommandLine -like '*{Path(marker).name}*' }} | "
              "ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }")
        subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True)
    elif marker:
        subprocess.run(["pkill", "-f", Path(marker).name], capture_output=True)


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def ffmpeg(args):
    r = subprocess.run([config.need("ffmpeg"), "-y", "-loglevel", "error"] + [str(a) for a in args],
                       capture_output=True, text=True, errors="replace")
    if r.returncode != 0:
        sys.exit("ffmpeg: " + r.stderr[-1500:])


def main():
    ap = argparse.ArgumentParser(description="Multiplane camera / 2.5D comic flight renderer (three.js, headless).")
    ap.add_argument("config")
    ap.add_argument("--page", default="multiplane", help="multiplane | comic25d | /_mp/<file>.html | skill:<skill>/<path>.html | a path to an .html file")
    ap.add_argument("--gif", action="store_true")
    ap.add_argument("--contact", default="auto")
    ap.add_argument("--timeout", type=int, default=1800, help="seconds")
    ap.add_argument("--software", action="store_true", help="software WebGL (SwiftShader) - only without a usable GPU")
    ap.add_argument("--startup", type=int, default=60, help="abort when no (new) frame arrives for this many seconds")
    a = ap.parse_args()
    page = PAGES.get(a.page, a.page)
    if "/_mp/" in page and not page.startswith("/_mp/"):    # Git Bash turns "/_mp/x.html" into a Windows path
        page = page[page.index("/_mp/"):]

    cfg_path = Path(a.config).resolve()
    root = cfg_path.parent
    src = None                                           # a page kept in another skill or anywhere on disk
    if page.startswith("skill:"):
        name, _, sub = page[6:].partition("/")
        src = _studio.skill_dir(name) / sub
    elif page.endswith(".html") and Path(page).is_file() and not page.startswith("/_mp/"):
        src = Path(page)
    if src is not None:                                  # served from the scene folder, like a page placed there
        dst = root / f"_page_{src.name}"
        dst.write_bytes(src.read_bytes())
        page = "/" + dst.name
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    out = root / cfg.get("out", "frames_mp")
    out.mkdir(exist_ok=True)
    for p in out.glob("mp_*.png"):
        if re.fullmatch(r"mp_\d{4}\.png", p.name):
            p.unlink()

    browser = find_browser()
    node = config.get("node") or shutil.which("node")
    if not node:
        sys.exit("node not found (needed for the small frame server) - install Node.js or set the config key 'node'")
    port = free_port()
    server = subprocess.Popen([node, str(HERE / "multiplane" / "server.mjs"), str(root), str(out), str(port)],
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace")
    time.sleep(0.8)
    gl = (["--use-angle=d3d11", "--enable-gpu-rasterization", "--ignore-gpu-blocklist"] if not a.software
          else ["--use-angle=swiftshader", "--enable-unsafe-swiftshader"])
    if not a.software and os.name != "nt":
        gl = ["--enable-gpu-rasterization", "--ignore-gpu-blocklist"]
    profile = tempfile.mkdtemp(prefix="mp_browser_")
    url = f"http://127.0.0.1:{port}{page}?config=/{cfg_path.name}&auto=1"
    edge = subprocess.Popen([browser, "--headless=new", f"--user-data-dir={profile}", "--no-first-run",
                             "--disable-extensions", "--mute-audio"] + gl + ["--window-size=1400,900", url],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    t0 = time.time()
    lines_seen = []
    threading.Thread(target=lambda: lines_seen.extend(server.stdout), daemon=True).start()
    end = cfg.get("end", 0) + 1
    last_n, last_change, problem = 0, time.time(), None
    print(f"rendering {end} frames: {url}", flush=True)
    try:
        while server.poll() is None:
            time.sleep(2)
            n_now = len(list(out.glob("mp_*.png")))
            if n_now != last_n:
                last_n, last_change = n_now, time.time()
                if n_now % 200 < 20:
                    print(f"  {n_now}/{end} frames ({time.time() - t0:.0f} s)", flush=True)
            if any("ERROR" in l for l in lines_seen):
                problem = "the page reports an error"
            elif n_now == 0 and time.time() - t0 > a.startup:
                problem = (f"no frame after {a.startup} s - the page does not load (check URL/config, "
                           f"open in a browser: {url.replace('&auto=1', '')})")
            elif n_now and time.time() - last_change > a.startup:
                problem = f"no new frame for {a.startup} s (stuck at {n_now}/{end})"
            elif time.time() - t0 > a.timeout:
                problem = "time limit reached"
            if problem:
                break
    finally:
        if server.poll() is None:
            server.kill()
        kill_tree(edge, profile)
        time.sleep(0.5)
        shutil.rmtree(profile, ignore_errors=True)
    msgs = [l.rstrip() for l in lines_seen if l.strip()]
    print("\n".join(msgs[-6:]))
    if problem:
        sys.exit("ABORTED: " + problem)
    if any("ERROR" in l for l in msgs):
        sys.exit("rendering failed")

    n = len(list(out.glob("mp_*.png")))
    if n == 0:
        sys.exit("no frames")
    fps = str(cfg.get("fps", 24))
    pattern = str(out / "mp_%04d.png")
    mp4 = cfg_path.with_suffix(".mp4")
    ffmpeg(["-framerate", fps, "-i", pattern, *h264(), "-pix_fmt", "yuv420p", mp4])
    print(f"{n} frames in {time.time() - t0:.0f} s -> {mp4}")
    if a.gif:
        gif = cfg_path.with_suffix(".gif")
        ffmpeg(["-framerate", fps, "-i", pattern, "-vf", "fps=12,scale=480:-1:flags=lanczos,split[a][b];"
                "[a]palettegen=max_colors=128[p];[b][p]paletteuse=dither=bayer:bayer_scale=4", gif])
        print("GIF:", gif)
    if a.contact != "none":
        from render import contact_sheet, pick_frames
        nums = [f for f in pick_frames(a.contact, n) if f < n]
        contact = root / "contact_mp.png"
        contact_sheet(pattern, contact, nums)
        print("contact sheet:", contact)


if __name__ == "__main__":
    main()
