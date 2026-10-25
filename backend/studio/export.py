"""MP4 export: the renderer opens the very same preview page in headless Chrome (render mode),
renders every frame and pipes it into FFmpeg; then the selected smaller versions are encoded.

Versions (any combination):
  full        1920×1080, CRF 22 – the master (highest quality, large)
  compressed  1920×1080, CRF 28 – looks the same, about 4× smaller
  small       1280×720, two-pass to < 30 MB for the whole song
  mail        960×540, two-pass to ≈ 12 MB for the whole song (mail attachments grow ~33 %)
  preview     1280×720, CRF 26 – quick check (used by "Szene als MP4")
"""
from __future__ import annotations

import subprocess
import threading
import time
from pathlib import Path

from . import store
from .config import RENDER_BASE, RENDERER, ffmpeg

_jobs: dict[str, dict] = {}
_lock = threading.Lock()

VARIANTS = ("full", "compressed", "small", "mail", "preview")
SUFFIX = {"full": "", "compressed": "_compressed", "small": "_small", "mail": "_mail", "preview": "_preview"}


def state(pid: str) -> dict:
    with _lock:
        j = _jobs.get(pid)
        return {k: v for k, v in dict(j, log=j["log"][-200:]).items() if k != "proc"} if j else {"status": "idle"}


def _log(pid, msg):
    with _lock:
        _jobs[pid]["log"].append(f"{time.strftime('%H:%M:%S')} {msg.rstrip()}")


def start(pid: str, variants: list[str], t_from: float | None = None, t_to: float | None = None) -> bool:
    variants = [v for v in variants if v in VARIANTS] or ["full"]
    with _lock:
        if _jobs.get(pid, {}).get("status") == "running":
            return False
        _jobs[pid] = {"status": "running", "progress": 0, "phase": "render", "log": [], "files": [], "started": time.time(), "variants": variants}
    threading.Thread(target=_work, args=(pid, variants, t_from, t_to), daemon=True).start()
    return True


def _free(path: Path) -> Path:
    """never overwrite a file the user may have open in a player: add a counter"""
    n, p = 2, path
    while p.exists():
        p = path.with_name(f"{path.stem} ({n}){path.suffix}")
        n += 1
    return p


def _tmp(final: Path) -> Path:
    """work file next to the final one; renamed when complete (an interrupted export never looks finished)"""
    return final.with_name(f".{final.stem}.partial.mp4")


def cleanup(out_dir: Path):
    """remove leftovers of interrupted exports (called at startup)"""
    for f in list(out_dir.glob(".*.partial.mp4")) + list(out_dir.glob(".pass_*")) + list(out_dir.glob(".*-master.mp4")):
        f.unlink(missing_ok=True)


def cancel(pid: str) -> bool:
    with _lock:
        j = _jobs.get(pid)
        if not j or j.get("status") != "running":
            return False
        j["cancel"] = True
        proc = j.get("proc")
    if proc is not None:
        # stop the whole process tree (node renderer + headless Chrome + ffmpeg)
        import os

        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True)
        else:
            proc.terminate()
    return True


def _two_pass(src: Path, dst: Path, w: int, h: int, kb: int, ab: int, logbase: str):
    common = ["-vf", f"scale={w}:{h}", "-c:v", "libx264", "-preset", "slow", "-b:v", f"{kb}k"]
    subprocess.run([ffmpeg(), "-v", "error", "-y", "-i", str(src), *common, "-pass", "1", "-passlogfile", logbase, "-an", "-f", "mp4", "NUL"], check=True)
    tmp = _tmp(dst)
    subprocess.run([ffmpeg(), "-v", "error", "-y", "-i", str(src), *common, "-pass", "2", "-passlogfile", logbase, "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", f"{ab}k", "-movflags", "+faststart", "-f", "mp4", str(tmp)], check=True)
    tmp.replace(dst)
    for f in Path(logbase).parent.glob(Path(logbase).name + "*"):
        f.unlink(missing_ok=True)


def _work(pid: str, variants: list[str], t_from: float | None, t_to: float | None):
    d = store.project_dir(pid)
    p = store.load(pid)
    out_dir = d / "out"
    out_dir.mkdir(exist_ok=True)
    clip = f" {int(t_from // 60)}m{t_from % 60:04.1f}s" if t_from is not None else ""
    name = f"{p.get('title', pid)}{clip}".replace("/", "-").replace("\\", "-").replace(":", " -")
    only_preview = variants == ["preview"]
    # the master: 1080p (or 720p when only a quick preview is wanted)
    w, h, crf = (1280, 720, 26) if only_preview else (1920, 1080, 22)
    keep_master = "full" in variants or only_preview
    final_master = _free(out_dir / f"{name}{SUFFIX['preview'] if only_preview else ''}.mp4") if keep_master else None
    master = _tmp(final_master) if final_master else out_dir / f".{pid}-master.mp4"
    files: list[str] = []
    try:
        args = ["node", str(RENDERER / "render.mjs"), "--url", f"{RENDER_BASE}/?render=1&project={pid}", "--audio", str(d / p["audio"]["mix"]), "--out", str(master), "--width", str(w), "--height", str(h), "--crf", str(crf)]
        if t_from is not None:
            args += ["--from", f"{max(0.0, t_from):.3f}", "--to", f"{t_to if t_to is not None else t_from + 10:.3f}"]
        proc = subprocess.Popen(args, cwd=RENDERER, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
        with _lock:
            _jobs[pid]["proc"] = proc
        assert proc.stdout
        for line in proc.stdout:
            line = line.strip()
            if line.startswith("frame "):
                try:
                    a, b = line.split()[1].split("/")
                    with _lock:
                        _jobs[pid]["progress"] = int(a) / int(b)
                except ValueError:
                    pass
                continue
            _log(pid, line)
        rc = proc.wait()
        with _lock:
            _jobs[pid]["proc"] = None
            cancelled = _jobs[pid].get("cancel")
        if cancelled:
            raise RuntimeError("abgebrochen")
        if rc != 0 or not master.exists():
            raise RuntimeError("render failed – see log")
        if final_master:
            master.replace(final_master)
            master = final_master
            files.append(master.name)
        dur = p["audio"]["duration"]  # bitrates for the whole song, so a clip looks like the full export
        for v in [x for x in variants if x in ("compressed", "small", "mail")]:
            with _lock:
                _jobs[pid]["phase"] = v
            dst = _free(out_dir / f"{name}{SUFFIX[v]}.mp4")
            _log(pid, f"encoding {dst.name}")
            with _lock:
                if _jobs[pid].get("cancel"):
                    raise RuntimeError("abgebrochen")
            if v == "compressed":
                tmp = _tmp(dst)
                subprocess.run([ffmpeg(), "-v", "error", "-y", "-i", str(master), "-c:v", "libx264", "-preset", "slow", "-crf", "28", "-pix_fmt", "yuv420p", "-c:a", "copy", "-movflags", "+faststart", "-f", "mp4", str(tmp)], check=True)
                tmp.replace(dst)
            elif v == "small":
                _two_pass(master, dst, 1280, 720, int(29 * 8 * 1024 / dur) - 96, 96, str(out_dir / ".pass_small"))
            else:
                _two_pass(master, dst, 960, 540, int(12 * 8 * 1024 / dur) - 64, 64, str(out_dir / ".pass_mail"))
            files.append(dst.name)
        if not keep_master:
            master.unlink(missing_ok=True)
        with _lock:
            _jobs[pid].update(status="done", progress=1, files=files, phase="done")
        _log(pid, "done: " + ", ".join(files))
    except Exception as e:  # noqa: BLE001
        _log(pid, f"error: {e}")
        cleanup(out_dir)
        with _lock:
            _jobs[pid].update(status="cancelled" if str(e) == "abgebrochen" else "error", error=str(e), files=files, proc=None)
