# /// script
# requires-python = ">=3.12"
# dependencies = ["numpy==2.5.4"]
# [tool.uv]
# exclude-newer = "2026-11-14T00:00:00Z"
# ///
"""ComfyUI client shared by every ai-video script: start/check the server, upload files, run a workflow, fetch results.

    import _studio; _studio.use("ai-video")
    import comfy
    comfy.ensure()                                    # server answers (starts it with config `comfy_start` if needed)
    comfy.lock("night_run_ltx", "comfy:ltx23")        # GPU lock; flushes ComfyUI when the model changes
    name = comfy.upload("start.png")                  # images AND audio go to ComfyUI's input folder this way
    h = comfy.run(workflow, timeout=3600)             # submit + wait -> history entry (RuntimeError on node errors)
    comfy.fetch_frames(comfy.outputs(h, "70"), folder) # SaveImage node 70 -> folder/f.0000.png ...

Config (studio-core config.py): comfy_url (default http://127.0.0.1:8188), comfy_start (optional: script that starts
the server, e.g. a .cmd/.sh file; without it the user is asked to start ComfyUI), comfy_dir (optional: ComfyUI's base
folder holding input/ and output/ - only needed for `clean_produced()` and the free-space check of the night run).
No machine paths here: the input folder of ComfyUI is reached through its /upload API, never through the file system.
Files this process creates in ComfyUI (uploads that did not exist before, SaveImage results) are recorded in
`PRODUCED`; `clean_produced()` deletes exactly those (needs comfy_dir) - never anything else.
"""
import json
import mimetypes
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

import _studio  # noqa: E402
_studio.use()
import config  # noqa: E402
import gpu_lock  # noqa: E402

PRODUCED = []       # (kind "input"/"output", subfolder, file name) created in ComfyUI by this process


def url():
    return config.comfy_url().rstrip("/")


def call(path, data=None, timeout=60, raw=None, ctype="application/json"):
    body = raw if raw is not None else (json.dumps(data).encode() if data is not None else None)
    req = urllib.request.Request(url() + path, data=body, headers={"Content-Type": ctype})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read()
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"ComfyUI HTTP {e.code} on {path}: {e.read().decode(errors='replace')[:3000]}")


def running():
    try:
        call("/system_stats", timeout=5)
        return True
    except Exception:
        return False


def ensure(wait=900):
    """Make sure the server answers; start it with the configured script if it does not. Returns True when ready."""
    if running():
        return True
    start = config.get("comfy_start")
    if not start:
        raise SystemExit(f"ComfyUI does not answer at {url()}. Start it, or store its start script once with "
                         f"`check_tools.py --set comfy_start=<script>` (environment variable ANIMATION_STUDIO_COMFY_START).")
    print(f"[comfy] not running - starting {Path(start).name} (minimised)", file=sys.stderr, flush=True)
    if os.name == "nt":
        # start's first quoted argument is the window TITLE - without it the script name would be read as the title
        subprocess.Popen(f'cmd /c start "ComfyUI" /min "{start}"', cwd=str(Path(start).parent))
    else:
        subprocess.Popen([start], cwd=str(Path(start).parent), start_new_session=True,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    t0 = time.time()
    while time.time() - t0 < wait:
        if running():
            print(f"[comfy] ready after {time.time() - t0:.0f} s", file=sys.stderr, flush=True)
            return True
        time.sleep(5)
    raise SystemExit(f"ComfyUI did not come up within {wait} s ({url()})")


def free():
    """Ask ComfyUI to unload its models and free RAM/VRAM (never kills anything)."""
    return gpu_lock.flush_comfy()


def lock(name, model):
    """Take the shared GPU lock for `model` (waits for other jobs). If this process already holds it for another
    model, ComfyUI is flushed first - one big model in memory at a time."""
    if gpu_lock._handle is None:
        gpu_lock.acquire(name, model=model)
        return
    try:
        before = gpu_lock.LAST.read_text(encoding="utf-8").strip()
    except Exception:
        before = ""
    if before != model:
        gpu_lock.flush_comfy()
        gpu_lock.LAST.write_text(model, encoding="utf-8")


def unlock():
    gpu_lock.release()


def upload(path, name=None):
    """Copy a local file (image or audio) into ComfyUI's input folder -> the name for LoadImage/LoadAudio."""
    path = Path(path)
    name = name or path.name
    base = comfy_dir()
    existed = base is None or (base / "input" / name).exists()
    b = "----comfy" + uuid.uuid4().hex
    ctype = mimetypes.guess_type(name)[0] or "application/octet-stream"
    head = (f'--{b}\r\nContent-Disposition: form-data; name="image"; filename="{name}"\r\n'
            f'Content-Type: {ctype}\r\n\r\n').encode()
    tail = f'\r\n--{b}\r\nContent-Disposition: form-data; name="overwrite"\r\n\r\ntrue\r\n--{b}--\r\n'.encode()
    r = call("/upload/image", raw=head + path.read_bytes() + tail, ctype=f"multipart/form-data; boundary={b}", timeout=300)
    d = json.loads(r)
    if not existed:
        PRODUCED.append(("input", d.get("subfolder") or "", d["name"]))
    return (d.get("subfolder") + "/" if d.get("subfolder") else "") + d["name"]


def submit(wf):
    r = json.loads(call("/prompt", {"prompt": wf, "client_id": str(uuid.uuid4())}))
    if "prompt_id" not in r:
        raise RuntimeError(f"ComfyUI refused the workflow: {json.dumps(r)[:2000]}")
    return r["prompt_id"]


def wait(pid, timeout=3 * 3600, poll=2.0):
    t0 = time.time()
    while time.time() - t0 < timeout:
        hist = json.loads(call(f"/history/{pid}"))
        if pid in hist:
            h = hist[pid]
            st = h.get("status", {})
            if st.get("status_str") == "error":
                msgs = [m for m in st.get("messages", []) if m and m[0] == "execution_error"]
                raise RuntimeError(short_error(json.dumps(msgs)))
            if st.get("completed") or h.get("outputs"):
                return h
        time.sleep(poll)
    cancel(pid)
    raise TimeoutError(f"ComfyUI job {pid} not finished after {timeout} s - cancelled")


def cancel(pid):
    """Take a job out of ComfyUI's queue, or interrupt it when it is the one running (never touches other jobs)."""
    try:
        q = json.loads(call("/queue", timeout=30))
        if any(len(x) > 1 and x[1] == pid for x in q.get("queue_pending", [])):
            call("/queue", {"delete": [pid]}, timeout=30)
        if any(len(x) > 1 and x[1] == pid for x in q.get("queue_running", [])):
            call("/interrupt", {"prompt_id": pid}, timeout=30)   # older ComfyUI: interrupts the running job
        print(f"[comfy] job {pid} cancelled after its timeout", file=sys.stderr, flush=True)
    except Exception as ex:
        print(f"[comfy] could not cancel job {pid}: {ex}", file=sys.stderr, flush=True)


def run(wf, timeout=3 * 3600):
    h = wait(submit(wf), timeout)
    for o in h.get("outputs", {}).values():
        for items in o.values():
            for i in items if isinstance(items, list) else []:
                if isinstance(i, dict) and i.get("type") == "output" and i.get("filename"):
                    PRODUCED.append(("output", i.get("subfolder") or "", i["filename"]))
    return h


def comfy_dir():
    v = config.get("comfy_dir")
    return Path(v) if v and Path(v).is_dir() else None


def clean_produced():
    """Delete the input/output files this process created in ComfyUI (recorded in PRODUCED). -> (files, bytes)."""
    base = comfy_dir()
    if base is None:
        return 0, 0
    n = size = 0
    while PRODUCED:
        kind, sub, name = PRODUCED.pop()
        root = (base / kind).resolve()
        f = (root / sub / name).resolve()
        if f.is_relative_to(root) and f.is_file():
            try:
                size += f.stat().st_size
                f.unlink()
                n += 1
            except OSError:
                pass
    return n, size


def outputs(h, node=None, kind="images"):
    """Result items (images/audio) of one node, or of all nodes."""
    outs = h.get("outputs", {})
    nodes = [outs.get(str(node), {})] if node is not None else outs.values()
    return [i for o in nodes for i in o.get(kind, [])]


def fetch(item, dest):
    q = urllib.parse.urlencode({k: item[k] for k in ("filename", "subfolder", "type")})
    Path(dest).write_bytes(call(f"/view?{q}", timeout=300))
    return Path(dest)


def fetch_frames(items, folder):
    folder = Path(folder)
    shutil.rmtree(folder, ignore_errors=True)
    folder.mkdir(parents=True)
    for k, im in enumerate(items):
        fetch(im, folder / f"f.{k:04d}.png")
    return len(items)


def frames_to_mp4(folder, out, fps, crf=15):
    """Encode to a temp name, then rename: a kill during the encode never leaves a truncated `out`."""
    from media import ffmpeg
    out = Path(out)
    tmp = out.with_name(out.stem + ".encoding" + out.suffix)
    subprocess.run([ffmpeg(), "-y", "-v", "error", "-framerate", str(fps), "-i", str(Path(folder) / "f.%04d.png"),
                    "-c:v", "libx264", "-crf", str(crf), "-preset", "medium", "-pix_fmt", "yuv420p", str(tmp)], check=True)
    os.replace(tmp, out)
    return out


def short_error(text):
    """ComfyUI errors carry tensors and tracebacks - keep node type + message."""
    t = str(text)
    i = t.find('"exception_message"')
    if i >= 0:
        j = t.find('"node_type"')
        node = t[j + 14:t.find('"', j + 14)] if j >= 0 else ""
        return (node + ": " + t[i + 22:i + 330]).replace("\\n", " ")
    return t[:400].replace("\n", " ")


if __name__ == "__main__":
    print("ComfyUI", url(), "running" if running() else "NOT running")
