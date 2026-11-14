"""Only one AI job at a time on the graphics card and in RAM (16 GB RAM is not enough for two big models).

Every GPU script calls, right after parsing its arguments:
    from gpu_lock import acquire;  acquire("comfy_image", model="comfy:flux")
The call waits until no other job holds the lock and keeps it until the process ends.
The operating system also releases the lock if a job crashes or is killed - nothing stays stuck.

If the model differs from the previous job's (e.g. FLUX -> Wan video -> depth map), ComfyUI is first asked to
drop its models from GPU and RAM (POST /free). So two big models are never in memory at the same time;
the same model several times in a row (e.g. 6 FLUX images) stays loaded and fast.

Lock folder: config.lock_dir() (GPU_LOCK_DIR) - share it with the other GPU pipelines on this machine.
Show the status:  uv run --no-project python gpu_lock.py
"""
import atexit
import json
import os
import sys
import time
import urllib.request

import config

try:
    import msvcrt
except ImportError:          # not Windows
    msvcrt = None
    import fcntl

# Shared on-disk format: other pipelines on this machine use the same lock folder and read/write these
# files with exactly these names and JSON fields - do not rename them.
LOCK_FILE_NAME = "gpu.lock"
INFO_FILE_NAME = "gpu_sperre_info.json"        # who holds the lock right now (display only)
LAST_MODEL_FILE_NAME = "gpu_letztes_modell.txt"  # model of the last job -> flush ComfyUI on a change
INFO_NAME, INFO_MODEL, INFO_PID, INFO_SINCE = "name", "modell", "pid", "seit"   # JSON fields of the info file

FOLDER = config.lock_dir()
LOCK = FOLDER / LOCK_FILE_NAME
INFO = FOLDER / INFO_FILE_NAME
LAST = FOLDER / LAST_MODEL_FILE_NAME
_handle = None


def _try_lock(f):
    """Non-blocking lock of byte 0 of the lock file; raises OSError if it is taken."""
    f.seek(0)
    if msvcrt:
        msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
    else:
        fcntl.lockf(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB, 1, 0)


def _unlock(f):
    f.seek(0)
    if msvcrt:
        msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
    else:
        fcntl.lockf(f.fileno(), fcntl.LOCK_UN, 1, 0)


def _read_info():
    try:
        return json.loads(INFO.read_text(encoding="utf-8"))
    except Exception:
        return {}


def flush_comfy():
    """Unload the ComfyUI models (if the server is running)."""
    try:
        req = urllib.request.Request(config.comfy_url() + "/free",
                                     data=json.dumps({"unload_models": True, "free_memory": True}).encode(),
                                     headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=10).read()
        time.sleep(2)
        return True
    except Exception:
        return False


def acquire(name, model=None, max_wait=6 * 3600):
    """Get the lock (waits while it is taken), then flush ComfyUI if the model changed."""
    global _handle
    if _handle is not None:
        return
    FOLDER.mkdir(parents=True, exist_ok=True)
    f = open(LOCK, "a+b")
    t0, reported = time.time(), False
    while True:
        try:
            _try_lock(f)
            break
        except OSError:
            if not reported:
                i = _read_info()
                print(f"[GPU lock] waiting - held by {i.get(INFO_NAME, '?')} ({i.get(INFO_MODEL, '?')}, "
                      f"since {i.get(INFO_SINCE, '?')}, PID {i.get(INFO_PID, '?')})", file=sys.stderr, flush=True)
                reported = True
            if time.time() - t0 > max_wait:
                raise SystemExit("[GPU lock] waited too long - is a job stuck? Status: python gpu_lock.py")
            time.sleep(2)
    _handle = f
    if reported:
        print(f"[GPU lock] free after {time.time() - t0:.0f} s", file=sys.stderr, flush=True)
    INFO.write_text(json.dumps({INFO_NAME: name, INFO_MODEL: model, INFO_PID: os.getpid(),
                                INFO_SINCE: time.strftime("%H:%M:%S")}), encoding="utf-8")
    model = model or name
    try:
        before = LAST.read_text(encoding="utf-8").strip()
    except Exception:
        before = ""
    if before and before != model and flush_comfy():
        print(f"[GPU lock] model change {before} -> {model}: ComfyUI memory flushed", file=sys.stderr, flush=True)
    LAST.write_text(model, encoding="utf-8")
    atexit.register(release)


def release():
    global _handle
    if _handle is None:
        return
    try:
        INFO.write_text("{}", encoding="utf-8")
        _unlock(_handle)
    except OSError:
        pass
    _handle.close()
    _handle = None


if __name__ == "__main__":
    print("Lock folder:", FOLDER)
    if not FOLDER.exists():
        print("GPU free (lock folder does not exist yet)")
        sys.exit(0)
    f = open(LOCK, "a+b")
    try:
        _try_lock(f)
        _unlock(f)
        print("GPU free")
    except OSError:
        print("GPU busy:", _read_info())
    try:
        print("last model:", LAST.read_text(encoding="utf-8").strip())
    except Exception:
        pass
