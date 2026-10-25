"""Import several old hand-built videos into the studio: create the project (song + lyrics as sung,
taken from the old lyrics.ts), wait for the analysis, then import the original scenes.

  uv run --directory backend python ../tools/import_old_videos.py <old-dir>=<project-id>=<title> ...

Needs the studio backend running on :8000.
"""
import json
import sys
import time
import urllib.request
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from studio import legacy  # noqa: E402

API = "http://127.0.0.1:8000/api"
HEADERS = {"intro": "[Intro]", "verse1": "[Verse 1]", "chorus": "[Chorus]", "verse2": "[Verse 2]", "bridge": "[Bridge]", "final": "[Final Chorus]", "outro": "[Outro]"}


def post_multipart(url: str, fields: dict, files: dict) -> dict:
    b = uuid.uuid4().hex
    body = b""
    for k, v in fields.items():
        body += f'--{b}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode()
    for k, p in files.items():
        body += f'--{b}\r\nContent-Disposition: form-data; name="{k}"; filename="{Path(p).name}"\r\nContent-Type: application/octet-stream\r\n\r\n'.encode() + Path(p).read_bytes() + b"\r\n"
    body += f"--{b}--\r\n".encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": f"multipart/form-data; boundary={b}"}, method="POST")
    return json.loads(urllib.request.urlopen(req, timeout=600).read())


def status(pid: str) -> dict:
    return json.loads(urllib.request.urlopen(f"{API}/projects/{pid}/status", timeout=30).read())


def run(old: Path, pid_hint: str, title: str):
    rows = legacy.parse_raw((old / "src" / "lyrics.ts").read_text(encoding="utf-8"))
    out, last = [], None
    for sec, text in rows:
        if sec != last:
            out.append(HEADERS.get(sec, f"[{sec}]"))
            last = sec
        out.append(text)
    print(f"== {title}: {len(rows)} lines", flush=True)
    r = post_multipart(f"{API}/projects", {"title": title, "lyrics": "\n".join(out), "storyline": f"Original video '{title}' (imported engine)."}, {"song": old / "public" / "song.wav"})
    pid = r["id"]
    print("project", pid, flush=True)
    while True:
        j = status(pid)["job"] or {}
        if j.get("status") in ("done", "error"):
            break
        time.sleep(5)
    if j["status"] == "error":
        print("analysis failed:", j.get("error"), "\n".join(j.get("log", [])[-15:]), flush=True)
        return
    print("\n".join(line for line in j["log"] if any(k in line for k in ("not sung", "not heard", "beats,", "peak loudness", "project ready", "WARNING"))), flush=True)
    legacy.import_legacy(pid, old)


if __name__ == "__main__":
    for arg in sys.argv[1:]:
        d, pid, title = arg.split("=", 2)
        try:
            run(Path(d), pid, title)
        except Exception as e:  # noqa: BLE001
            print("FAILED", title, e, flush=True)
