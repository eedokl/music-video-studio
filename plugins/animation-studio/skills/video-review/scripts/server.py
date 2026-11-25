"""Comparison page for review.py: N versions side by side, synced, pick per shot, cut. Standard library only.

Start:  python review.py serve review.json [--port 0]     (prints the URL; port 0 = any free port)
  GET  /                  the page (assets/index.html)
  GET  /api/review        title, versions, shots (start, end, label, note, diff, same), default, audio
  GET  /api/choice        {"choice": {shot: version id}}
  POST /api/choice        save the choice (choice.json next to review.json)
  GET  /film/<id>         a version (its light preview if there is one), with HTTP Range so seeking works
  GET  /film/cut          the last cut (small version if there is one)
  POST /api/cut           save the choice and start pick_cut.py;  GET /api/cut -> status
POSTs must come from the page itself: Content-Type application/json (a cross-site form cannot send it without a CORS
preflight, which this server never allows) and Host / Origin naming this server - other web pages cannot change the
choice or start a cut. Every GET also needs a Host header naming this server (127.0.0.1, localhost, [::1] or the
--host value): a DNS-rebinding page under a foreign name cannot read the films or the review data.
"""
import json
import re
import socket
import subprocess
import sys
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
PAGE = HERE.parent / "assets" / "index.html"


class OwnPortServer(ThreadingHTTPServer):
    """A port of its own: Python's server sets SO_REUSEADDR, which on Windows lets a second server bind a port that an
    old one still holds - the browser then got the OLD project's page (Du bist die Maschine, 2026-11-25: a takes page
    of another project answered). Exclusive use makes the second start fail with "port in use" instead."""
    allow_reuse_address = sys.platform != "win32"

    def server_bind(self):
        if sys.platform == "win32":
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


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

        def host_ok(self):
            port = self.server.server_address[1]
            return self.headers.get("Host", "") in {f"{h}:{port}" for h in ("127.0.0.1", "localhost", "[::1]", host)}

        def do_GET(self):
            if not self.host_ok():                            # DNS rebinding: a foreign name pointing at 127.0.0.1
                return self.reply(403, {"error": "open the review at 127.0.0.1 / localhost / the --host address"})
            p = self.path.split("?")[0]
            R = review()
            if p == "/favicon.ico":
                self.send_response(204)
                self.end_headers()
                return
            if p in ("/", "/index.html"):
                return self.file(PAGE, "text/html; charset=utf-8")
            if p.startswith("/film/"):
                f = films(R).get(urllib.parse.unquote(p[6:]))      # the page sends encodeURIComponent(id)
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

        def same_origin(self):
            port = self.server.server_address[1]
            allowed = {f"{h}:{port}" for h in ("127.0.0.1", "localhost", "[::1]", host)}
            if not self.host_ok():
                return False
            origin = self.headers.get("Origin")
            return origin is None or urllib.parse.urlsplit(origin).netloc in allowed

        def do_POST(self):
            ctype = self.headers.get("Content-Type", "").split(";")[0].strip().lower()
            if ctype != "application/json" or not self.same_origin():
                return self.reply(403, {"error": "only the review page itself may post (application/json, same origin)"})
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

    httpd = OwnPortServer((host, port), Handler)
    print(f"video review: http://{host}:{httpd.server_address[1]}/", flush=True)
    httpd.serve_forever()
