"""Comparison page for review.py: N versions side by side, synced, pick per shot, cut. Standard library only.

Start:  python review.py serve review.json [--port 0]     (prints the URL; port 0 = any free port)
  GET  /                  the page (assets/index.html)
  GET  /api/review        title, versions, shots (start, end, label, note, diff, same), default, audio
  GET  /api/choice        {"choice": {shot: version id}}
  POST /api/choice        save the choice (choice.json next to review.json)
  GET  /film/<id>         a version (its light preview if there is one), with HTTP Range so seeking works
  GET  /film/cut          the last cut (small version if there is one)
  POST /api/cut           save the choice and start pick_cut.py;  GET /api/cut -> status
"""
import json
import re
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
PAGE = HERE.parent / "assets" / "index.html"


def serve(rp, port=0, host="127.0.0.1"):
    base = rp.parent
    state = {"running": False, "done": False, "error": "", "log": ""}

    def review():
        return json.loads(rp.read_text(encoding="utf-8"))

    def choice_path(R):
        return base / R.get("choice_file", "choice.json")

    def films(R):
        f = {v["id"]: base / (v.get("preview") or v["file"]) for v in R["versions"]}
        out = base / R.get("out", "cut.mp4")
        small = out.with_name(out.stem + "_small.mp4")
        f["cut"] = small if small.exists() else out
        return f

    def run_cut():
        state.update(running=True, done=False, error="", log="")
        r = subprocess.run([sys.executable, str(HERE / "pick_cut.py"), str(rp)], capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        state.update(running=False, done=r.returncode == 0, error="" if r.returncode == 0 else r.stderr[-1500:],
                     log=r.stdout[-800:])

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def reply(self, code, data, ctype="application/json; charset=utf-8"):
            body = data if isinstance(data, bytes) else json.dumps(data, ensure_ascii=False).encode()
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def file(self, path, ctype):
            if not path.exists():
                return self.reply(404, {"error": f"{path.name} missing"})
            size = path.stat().st_size
            m = re.match(r"bytes=(\d*)-(\d*)", self.headers.get("Range", ""))
            a, b = 0, size - 1
            if m:
                if m.group(1):
                    a = int(m.group(1))
                    b = min(int(m.group(2)) if m.group(2) else size - 1, size - 1)
                else:                                           # suffix range: last N bytes
                    a = max(0, size - int(m.group(2) or 0))
                if a >= size:
                    self.send_response(416)
                    self.send_header("Content-Range", f"bytes */{size}")
                    self.end_headers()
                    return
            self.send_response(206 if m else 200)
            self.send_header("Content-Type", ctype)
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Content-Length", str(b - a + 1))
            self.send_header("Cache-Control", "no-store")
            if m:
                self.send_header("Content-Range", f"bytes {a}-{b}/{size}")
            self.end_headers()
            with open(path, "rb") as f:
                f.seek(a)
                rest = b - a + 1
                try:
                    while rest > 0:
                        chunk = f.read(min(1 << 20, rest))
                        if not chunk:
                            break
                        self.wfile.write(chunk)
                        rest -= len(chunk)
                except (ConnectionResetError, BrokenPipeError, ConnectionAbortedError):
                    pass

        def do_GET(self):
            p = self.path.split("?")[0]
            R = review()
            if p == "/favicon.ico":
                self.send_response(204)
                self.end_headers()
                return
            if p in ("/", "/index.html"):
                return self.file(PAGE, "text/html; charset=utf-8")
            if p.startswith("/film/"):
                f = films(R).get(p[6:])
                return self.file(f, "video/mp4") if f else self.reply(404, {"error": "unknown version"})
            if p == "/api/review":
                keys = ("title", "fps", "size", "duration", "audio", "default", "shot_source", "out")
                return self.reply(200, dict({k: R.get(k) for k in keys},
                                            versions=[{"id": v["id"], "label": v["label"]} for v in R["versions"]],
                                            shots=R["shots"]))
            if p == "/api/choice":
                cp = choice_path(R)
                d = json.loads(cp.read_text(encoding="utf-8")) if cp.exists() else {}
                return self.reply(200, {"choice": d.get("choice", {})})
            if p == "/api/cut":
                return self.reply(200, dict(state, exists=films(R)["cut"].exists()))
            self.reply(404, {"error": "unknown"})

        def do_POST(self):
            n = int(self.headers.get("Content-Length", 0))
            try:
                data = json.loads(self.rfile.read(n) or b"{}")
            except json.JSONDecodeError:
                return self.reply(400, {"error": "bad json"})
            R = review()
            ids = {v["id"] for v in R["versions"]}
            choice = {str(k): v for k, v in (data.get("choice") or {}).items() if v in ids}
            if self.path == "/api/choice":
                choice_path(R).write_text(json.dumps({"choice": choice}, indent=1), encoding="utf-8")
                return self.reply(200, {"ok": True, "saved": len(choice)})
            if self.path == "/api/cut":
                if state["running"]:
                    return self.reply(409, {"error": "already running"})
                choice_path(R).write_text(json.dumps({"choice": choice}, indent=1), encoding="utf-8")
                threading.Thread(target=run_cut, daemon=True).start()
                return self.reply(200, {"ok": True})
            self.reply(404, {"error": "unknown"})

    httpd = ThreadingHTTPServer((host, port), Handler)
    print(f"video review: http://{host}:{httpd.server_address[1]}/", flush=True)
    httpd.serve_forever()
