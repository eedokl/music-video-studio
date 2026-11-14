# /// script
# requires-python = ">=3.12"
# dependencies = ["numpy==2.5.4"]
# [tool.uv]
# exclude-newer = "2026-11-14T00:00:00Z"
# ///
"""Compare the takes of every shot by eye and ear, pick by hand -> selection.json "manual" (pick.py: manual wins).

pick.py chooses the takes by the measured lip score. The Europe 2031 night run showed that the eye often prefers
another take (natural movement over the widest mouth: V3 took the V1 take in 11 of 17 singing shots). This page shows
all takes of a shot side by side, each placed on the song exactly as render_shots.py would place it (clip start,
tempo, LTX delay, lag) with the song's sound, the measured score / warnings from picks.log, the automatic pick marked.
No GPU: the takes exist already (2-4 LTX seeds per singing shot, the moving clips of B-roll / claudia_moving shots).

  uv run takes.py [<project>] [--only s02,s05] [--rebuild]   previews -> takes/<shot>/<take>.mp4 + takes/takes.json
  uv run takes.py [<project>] --serve [--port 0]           the page (URL printed); a click saves the choice at once
After choosing: uv run render_shots.py <project> --only <the changed shots>, then make_film.py.
"""
import argparse
import json
import re
import subprocess
import sys
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import _studio  # noqa: E402
_studio.use("song-analysis", "ai-video")
import clips  # noqa: E402
from media import ffmpeg  # noqa: E402
from song_project import Project  # noqa: E402

HERE = Path(__file__).resolve().parent
PAGE = HERE.parent / "assets" / "takes.html"
LIP_DIRS = ("lipsync", "s2v", "infinitetalk", "humo", "minimax_h3")
VOCALISE = {"oh", "ooh", "oooh", "ah", "aah", "la", "na", "mm", "mmm", "hm", "uh", "whoa", "wo", "yeah", "ha", "hey"}


def vocalise(line):
    """A line without real words ("Ooh, ah", "(la la)"): the lip score says little there - judge by eye (the live film's
    S2V vocalises 49 / 64 measured weak but were kept for their expression)."""
    ws = re.findall(r"[A-Za-zÄÖÜäöüß]+", line or "")
    return bool(line) and all(w.lower() in VOCALISE for w in ws)


def done(files):
    return [f for f in files if ".part." not in f.name and ".encoding." not in f.name]


def candidates(P, s):
    """All finished takes of a shot: lip-sync renders (with their .json) or moving clips."""
    name, ai = s["name"], P.dir / "ai"
    if s.get("technique") == "lipsync":
        out = [f for d in LIP_DIRS for f in sorted((ai / d).glob(f"{name}_*.mp4"))]
        return [f for f in done(out) if clips.meta_path(f).exists()]
    return done(sorted((ai / "moving").glob(f"{name}_*.mp4")))


def log_info(P):
    """picks.log -> {relative file: {"score", "lag", "warn"}} (the last entry of a file wins)."""
    info, f = {}, P.dir / "picks.log"
    if not f.exists():
        return info
    for ln in f.read_text(encoding="utf-8", errors="replace").splitlines():
        m = re.match(r"\s+(\S+\.mp4)\s+r0 (-?[\d.]+)\s+r@(-?\d+)\s.*?score (-?[\d.]+)(.*)", ln)
        if m:
            info["ai/" + m.group(1)] = {"score": float(m.group(4)), "lag": int(m.group(3)),
                                        "warn": m.group(5).strip()}
            continue
        m = re.match(r"clip (\S+): (\S+\.mp4)\s+motion ([\d.]+).*?(->.*)?$", ln)
        if m:
            info["ai/moving/" + Path(m.group(2)).name] = {"motion": float(m.group(3)),
                                                          "warn": (m.group(4) or "").lstrip("-> ").split(":")[0]}
    return info


def placement(clip, s, lag):
    """(clip time where the shot starts, tempo, pad seconds before the clip starts) - as clips.frame_index places it."""
    meta = clips.read_meta(clip) if clips.meta_path(clip).exists() else {}
    if "song_start" not in meta:                           # a moving clip without placement: from its first frame
        return 0.0, 1.0, 0.0
    fps, tempo = float(meta["fps"]), float(meta.get("tempo", 1.0))
    i0 = clips.frame_index(s["from"], meta, lag)           # unclamped: may be < 0 when the clip starts later
    t0 = i0 / fps
    return (max(t0, 0.0), tempo, max(-t0, 0.0) / tempo)


def preview(P, clip, s, lag, out):
    dur = s["to"] - s["from"]
    t0, tempo, pad = placement(clip, s, lag)
    vf = (f"setpts=(PTS-STARTPTS)/{tempo},fps=24,scale=640:-2,"
          + (f"tpad=start_duration={pad:.3f}:start_mode=clone," if pad > 0 else "")
          + f"tpad=stop_duration={dur:.3f}:stop_mode=clone")
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_name(out.stem + ".part.mp4")
    subprocess.run([ffmpeg(), "-y", "-v", "error", "-ss", f"{t0:.4f}", "-i", str(clip), "-ss", f"{s['from']:.4f}",
                    "-t", f"{dur:.4f}", "-i", str(P.song), "-filter_complex", f"[0:v]{vf}[v]", "-map", "[v]",
                    "-map", "1:a", "-t", f"{dur:.4f}", "-c:v", "libx264", "-crf", "26", "-preset", "veryfast",
                    "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "96k", "-movflags", "+faststart", str(tmp)],
                   check=True)
    tmp.replace(out)


def build(P, only=None, rebuild=False):
    sel = json.loads((P.dir / "selection.json").read_text(encoding="utf-8")) if (P.dir / "selection.json").exists() else {}
    auto = sel.get("clip") or {}
    manual = (sel.get("manual") or {}).get("clip") or {}
    info = log_info(P)
    tj = P.dir / "takes" / "takes.json"
    prev = {x["name"]: x for x in json.loads(tj.read_text(encoding="utf-8"))["shots"]} if tj.exists() else {}
    shots = []
    for s in P.sections():
        if only and s["name"] not in only:
            continue
        cands = candidates(P, s)
        if not cands:
            continue
        a_ent = auto.get(s["name"]) or {}
        if a_ent.get("manual"):                            # "clip" holds a hand choice: keep the automatic one known
            a_ent = (prev.get(s["name"]) or {}).get("auto_entry") or {}
        rows = []
        for c in cands:
            rel = c.resolve().relative_to(P.dir).as_posix()
            li = info.get(rel, {})
            lag = a_ent.get("lag", li.get("lag", 0)) if a_ent.get("file") == rel else li.get("lag", 0)
            pv = P.dir / "takes" / s["name"] / (c.stem + ".mp4")
            if rebuild or not pv.exists() or pv.stat().st_mtime < c.stat().st_mtime:
                preview(P, c, s, lag, pv)
            rows.append(dict(file=rel, preview=pv.relative_to(P.dir).as_posix(), lag=lag, score=li.get("score"),
                             motion=li.get("motion"), warn=li.get("warn", ""), kind=c.parent.name))
        shots.append(dict(name=s["name"], start=s["from"], end=s["to"], technique=s.get("technique"),
                          line=s.get("line") or "", auto=a_ent.get("file"), auto_entry=a_ent,
                          vocalise=s.get("technique") == "lipsync" and vocalise(s.get("line")), engine=s.get("engine"),
                          manual=(manual.get(s["name"]) or {}).get("file"), takes=rows))
        print(f"  {s['name']}: {len(rows)} takes" + (f", auto {Path(shots[-1]['auto']).name}" if shots[-1]["auto"] else ""))
    data = dict(title=P.get("title") or P.dir.name, shots=shots)
    (P.dir / "takes").mkdir(exist_ok=True)
    (P.dir / "takes" / "takes.json").write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"-> takes/takes.json ({len(shots)} shots); look at them: uv run takes.py {P.dir} --serve")
    return data


def choose(P, shot, file):
    """file = a take (relative path) -> selection.json manual.clip[shot]; None -> back to the automatic pick."""
    f = P.dir / "selection.json"
    sel = json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
    man = sel.setdefault("manual", {}).setdefault("clip", {})
    data = json.loads((P.dir / "takes" / "takes.json").read_text(encoding="utf-8"))
    s = next((x for x in data["shots"] if x["name"] == shot), None)
    take = next((t for t in (s or {}).get("takes", []) if t["file"] == file), None) if file else None
    if file and not take:
        raise ValueError(f"{file} is not a take of {shot}")
    if take:
        man[shot] = {"file": take["file"], "lag": take["lag"]}
    else:
        man.pop(shot, None)
    sel["clip"] = dict(sel.get("clip") or {})
    if take:                                               # render_shots reads "clip": the manual choice goes there too
        sel["clip"][shot] = {"file": take["file"], "lag": take["lag"], "manual": True}
    elif s and s.get("auto_entry"):                        # back to the automatic pick
        sel["clip"][shot] = s["auto_entry"]
    f.write_text(json.dumps(sel, ensure_ascii=False, indent=1), encoding="utf-8")
    if s:
        s["manual"] = take["file"] if take else None
        (P.dir / "takes" / "takes.json").write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")


def serve(P, port=0, host="127.0.0.1"):
    allowed_hosts = ("127.0.0.1", "localhost", "[::1]", host)

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
                else:
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
            if m:
                self.send_header("Content-Range", f"bytes {a}-{b}/{size}")
            self.end_headers()
            with open(path, "rb") as fh:
                fh.seek(a)
                rest = b - a + 1
                try:
                    while rest > 0:
                        chunk = fh.read(min(1 << 20, rest))
                        if not chunk:
                            break
                        self.wfile.write(chunk)
                        rest -= len(chunk)
                except (ConnectionResetError, BrokenPipeError, ConnectionAbortedError):
                    pass

        def host_ok(self):
            port_ = self.server.server_address[1]
            return self.headers.get("Host", "") in {f"{h}:{port_}" for h in allowed_hosts}

        def do_GET(self):
            if not self.host_ok():                     # DNS rebinding: a foreign name pointing at 127.0.0.1
                return self.reply(403, {"error": "open the page at 127.0.0.1 / localhost"})
            p = urllib.parse.unquote(self.path.split("?")[0])
            if p in ("/", "/index.html"):
                return self.file(PAGE, "text/html; charset=utf-8")
            if p == "/api/takes":
                return self.file(P.dir / "takes" / "takes.json", "application/json; charset=utf-8")
            if p.startswith("/takes/") and p.endswith(".mp4"):
                f = (P.dir / p.lstrip("/")).resolve()
                if (P.dir / "takes").resolve() in f.parents:
                    return self.file(f, "video/mp4")
            self.reply(404, {"error": "unknown"})

        def do_POST(self):
            ctype = self.headers.get("Content-Type", "").split(";")[0].strip().lower()
            origin = self.headers.get("Origin")
            port_ = self.server.server_address[1]
            same = origin is None or urllib.parse.urlsplit(origin).netloc in {f"{h}:{port_}" for h in allowed_hosts}
            if ctype != "application/json" or not self.host_ok() or not same:
                return self.reply(403, {"error": "only the page itself may post (application/json, same origin)"})
            if self.path != "/api/choose":
                return self.reply(404, {"error": "unknown"})
            try:
                d = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
                choose(P, str(d["shot"]), d.get("file"))
            except (ValueError, KeyError) as e:
                return self.reply(400, {"error": str(e)})
            self.reply(200, {"ok": True})

    httpd = ThreadingHTTPServer((host, port), Handler)
    print(f"takes: http://{host}:{httpd.server_address[1]}/   (Ctrl+C to stop)", flush=True)
    httpd.serve_forever()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("project", nargs="?", default=".")
    ap.add_argument("--only", help="shots, e.g. s02,s05")
    ap.add_argument("--rebuild", action="store_true", help="make every preview again")
    ap.add_argument("--serve", action="store_true", help="start the page (builds missing previews first)")
    ap.add_argument("--port", type=int, default=0)
    a = ap.parse_args()
    P = Project(a.project)
    only = set(a.only.split(",")) if a.only else None
    build(P, only, a.rebuild)
    if a.serve:
        serve(P, a.port)


if __name__ == "__main__":
    main()
