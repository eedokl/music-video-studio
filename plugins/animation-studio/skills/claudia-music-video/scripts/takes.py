# /// script
# requires-python = ">=3.12"
# dependencies = ["numpy==2.5.4"]
# [tool.uv]
# exclude-newer = "2026-11-14T00:00:00Z"
# ///
"""Compare the takes of every shot by eye and ear, pick by hand -> selection.json "manual" (pick.py: manual wins),
then build the cut from the page.

pick.py chooses the takes by the measured lip score. The Europe 2031 night run showed that the eye often prefers
another take (natural movement over the widest mouth: V3 took the V1 take in 11 of 17 singing shots; claudia3: the user
took LTX in 3 of 4 shots where S2V measured better). The page is built like the user's own V1/V2 compare tool: the shot
list on the left, the takes of one shot side by side on the stage, each placed on the song exactly as render_shots.py
would place it (clip start, tempo, LTX delay, lag) with the song's sound, the measured score / warnings from picks.log,
the automatic pick marked; keys 1-9 choose, up/down change the shot, space plays; "Build cut" runs
render_shots.py --only <changed shots> + make_film.py and shows the new film.
Every shot can also take its still (start image / B-roll picture with the depth camera move) instead of a clip.
A take made on a start image that is no longer the chosen one (re-made because of two mics, a wrong streak ...) is
marked: it still shows the old image's faults.
No GPU: the takes exist already (2-4 LTX seeds per singing shot, S2V, the moving clips of B-roll / claudia_moving).

  uv run takes.py [<project>] [--only s02,s05] [--rebuild]   previews -> takes/<shot>/<take>.mp4 + takes/takes.json
  uv run takes.py [<project>] --serve [--port 0]           the page (URL printed); a click saves the choice at once
"""
import argparse
import json
import re
import subprocess
import sys
import threading
import time
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
LIP_DIRS = ("lipsync", "s2v", "infinitetalk", "humo", "minimax_h3", "ltx25")
VOCALISE = {"oh", "ooh", "oooh", "ah", "aah", "la", "na", "mm", "mmm", "hm", "uh", "whoa", "wo", "yeah", "ha", "hey"}
STILL = "still"                                            # the pseudo take "the picked still instead of a clip"


def vocalise(line):
    """A line without real words ("Ooh, ah", "(la la)"): the lip score says little there - judge by eye (the live film's
    S2V vocalises 49 / 64 measured weak but were kept for their expression)."""
    ws = re.findall(r"[A-Za-zÄÖÜäöüß]+", line or "")
    return bool(line) and all(w.lower() in VOCALISE for w in ws)


def shouts(line):
    """Calls like "Hey! Hey!": the lip score says little there (test: all LTX takes -0.25..0.12, the best frozen)."""
    ws = [w.lower() for w in re.findall(r"[A-Za-zÄÖÜäöüß]+", line or "")]
    return (line or "").count("!") >= 2 or sum(w in VOCALISE for w in ws) >= 2


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
        m = re.match(r"\s*(?:clip \S+: |moving )(\S+\.mp4)\s+motion ([\d.]+).*?(->.*)?$", ln)
        if m:
            info["ai/moving/" + Path(m.group(1)).name] = {"motion": float(m.group(2)),
                                                          "warn": (m.group(3) or "").lstrip("-> ").split(":")[0]}
    return info


def still_of(P, s, sel):
    """The picked still of a shot (start image or B-roll picture) or None."""
    grp = "broll" if s.get("technique") == "broll" else "start"
    img = (sel.get(grp) or {}).get(s["name"])
    return img if img and P.path(img).exists() else None


def image_tag(P, clip):
    """The start image a take was made on: 'v2' / 'v2m' (from its meta "image", else from the file name)."""
    meta = clips.read_meta(clip) if clips.meta_path(clip).exists() else {}
    if meta.get("image"):
        return Path(str(meta["image"]).replace("\\", "/")).stem.split("_")[-1]
    parts = clip.stem.split("_")
    return parts[1] if len(parts) > 1 else None


def placement(clip, s, lag):
    """(clip time where the shot starts, tempo, pad seconds before the clip starts) - as clips.frame_index places it."""
    meta = clips.read_meta(clip) if clips.meta_path(clip).exists() else {}
    if "song_start" not in meta:                           # a moving clip without placement: from its first frame
        return 0.0, 1.0, 0.0
    fps, tempo = float(meta["fps"]), float(meta.get("tempo", 1.0))
    i0 = clips.frame_index(s["from"], meta, lag)           # unclamped: may be < 0 when the clip starts later
    t0 = i0 / fps
    return (max(t0, 0.0), tempo, max(-t0, 0.0) / tempo)


def _encode(P, s, inputs, vf, out):
    dur = s["to"] - s["from"]
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_name(out.stem + ".part.mp4")
    subprocess.run([ffmpeg(), "-y", "-v", "error", *inputs, "-ss", f"{s['from']:.4f}", "-t", f"{dur:.4f}",
                    "-i", str(P.song), "-filter_complex", f"[0:v]{vf}[v]", "-map", "[v]", "-map", "1:a",
                    "-t", f"{dur:.4f}", "-c:v", "libx264", "-crf", "26", "-preset", "veryfast", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", "-b:a", "96k", "-movflags", "+faststart", str(tmp)], check=True)
    tmp.replace(out)


def preview(P, clip, s, lag, out):
    dur = s["to"] - s["from"]
    t0, tempo, pad = placement(clip, s, lag)
    vf = (f"setpts=(PTS-STARTPTS)/{tempo},fps=24,scale=640:-2,"
          + (f"tpad=start_duration={pad:.3f}:start_mode=clone," if pad > 0 else "")
          + f"tpad=stop_duration={dur:.3f}:stop_mode=clone")
    _encode(P, s, ["-ss", f"{t0:.4f}", "-i", str(clip)], vf, out)


def preview_still(P, img, s, out):
    """The still with a slow push-in (render_shots adds the depth parallax; close enough to judge)."""
    n = max(2, round((s["to"] - s["from"]) * 24))
    vf = f"scale=1280:-2,zoompan=z='1+0.06*on/{n}':x='iw/2-iw/zoom/2':y='ih/2-ih/zoom/2':d={n}:s=640x360:fps=24"
    _encode(P, s, ["-loop", "1", "-framerate", "24", "-i", str(P.path(img))], vf, out)


LOCK = threading.RLock()                                  # the page's threads: one read-modify-write at a time


def _read_json(f, default):
    for k in range(10):                                     # a writer replacing the file on Windows: try again
        try:
            return json.loads(f.read_text(encoding="utf-8")) if f.exists() else default
        except (PermissionError, json.JSONDecodeError):
            if k == 9:
                raise
            time.sleep(0.1)


def write_atomic(path, data):
    """Temp file + replace: pick.py / render_shots / the page never read a half-written file."""
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    for k in range(20):
        try:
            tmp.replace(path)
            return
        except PermissionError:
            if k == 19:
                raise
            time.sleep(0.1)


def read_sel(P):
    return _read_json(P.dir / "selection.json", {})


def auto_entry_of(e, prev=None):
    """The automatic pick of a "clip" entry: a hand choice carries it under "auto" (pick.py / choose); older files
    without it: the one remembered in the last takes.json."""
    if not e.get("manual"):
        return e
    return e.get("auto") or (prev or {}).get("auto_entry") or {}


def build(P, only=None, rebuild=False, quiet=False):
    sel = read_sel(P)
    auto = sel.get("clip") or {}
    manual = (sel.get("manual") or {}).get("clip") or {}
    info = log_info(P)
    tj = P.dir / "takes" / "takes.json"
    prev = {x["name"]: x for x in _read_json(tj, {}).get("shots", [])}
    shots = []
    for s in P.sections():
        if only and s["name"] not in only:
            if s["name"] in prev:
                shots.append(prev[s["name"]])
            continue
        cands = candidates(P, s)
        still = still_of(P, s, sel)
        if not cands and not still:
            continue
        a_ent = auto_entry_of(auto.get(s["name"]) or {}, prev.get(s["name"]))
        chosen_tag = Path(still).stem.split("_")[-1] if still else None
        old_keys = {t["file"]: t.get("key") for t in (prev.get(s["name"]) or {}).get("takes", [])}
        rows = []
        for c in cands:
            rel = c.resolve().relative_to(P.dir).as_posix()
            li = info.get(rel, {})
            lag = a_ent.get("lag", li.get("lag", 0)) if a_ent.get("file") == rel else li.get("lag", 0)
            # folder in the name: ai/s2v/s04_v1.mp4 and ai/infinitetalk/s04_v1.mp4 must not share one preview
            pv = P.dir / "takes" / s["name"] / f"{c.parent.name}_{c.stem}.mp4"
            # the placement is part of the key: a new lag or shot from/to makes the preview again (it is what
            # choose saves and render_shots places)
            key = f"{s['from']:.3f}-{s['to']:.3f} lag {lag} {c.stat().st_mtime:.0f}"
            if rebuild or not pv.exists() or old_keys.get(rel) != key:
                preview(P, c, s, lag, pv)
            tag = image_tag(P, c)
            warn = [w for w in [li.get("warn", "")] if w]
            if s.get("technique") != "broll" and tag and chosen_tag and tag != chosen_tag:
                # claudia3: a take on the discarded s08_v2 (two mics) was chosen and the second mic was in the film
                warn.append(f"made on start image {tag}, not the chosen {chosen_tag} - check mic / streak")
            if tag and tag.endswith("m"):
                warn.append("start image is a mic repair - check the cheek")
            style = (clips.read_meta(c) if clips.meta_path(c).exists() else {}).get("prompt_style")
            rows.append(dict(file=rel, preview=pv.relative_to(P.dir).as_posix(), lag=lag, key=key, score=li.get("score"),
                             motion=li.get("motion"), warn="; ".join(warn), kind=c.parent.name, image=tag,
                             style={"plain": "prompt A (plain)", "timeline": "prompt B (timeline)"}.get(style)))
        if still:
            pv = P.dir / "takes" / s["name"] / "_still.mp4"
            key = f"{s['from']:.3f}-{s['to']:.3f} {still} {P.path(still).stat().st_mtime:.0f}"
            if rebuild or not pv.exists() or old_keys.get(STILL) != key:
                preview_still(P, still, s, pv)
            rows.append(dict(file=STILL, preview=pv.relative_to(P.dir).as_posix(), lag=0, key=key, score=None, motion=None,
                             warn="", kind="still", image=chosen_tag, still=still))
        auto_file = STILL if a_ent.get("still") else a_ent.get("file")
        if auto_file and auto_file != STILL and not P.path(auto_file).exists():
            auto_file = STILL if still else None           # a clip that does not exist: render_shots takes the still
        if not auto_file and still and not cands:
            auto_file = STILL
        m_ent = manual.get(s["name"]) or {}
        mine = STILL if m_ent.get("still") else m_ent.get("file")
        note = ""
        if mine and mine != STILL and not P.path(mine).exists():
            # a deleted take (or the old trick "a hand clip that does not exist"): render_shots takes the still
            note = (f"Your hand choice {mine} no longer exists - the cut uses the still. Choose a take or go back to "
                    "the automatic pick.")
            mine = STILL
        shots.append(dict(name=s["name"], start=s["from"], end=s["to"], technique=s.get("technique"),
                          line=s.get("line") or "", auto=auto_file,
                          auto_entry=a_ent, vocalise=s.get("technique") == "lipsync" and vocalise(s.get("line")),
                          shouts=s.get("technique") == "lipsync" and not vocalise(s.get("line")) and shouts(s.get("line")),
                          engine=s.get("engine"), manual=mine, note=note, takes=rows))
        if not quiet:
            print(f"  {s['name']}: {len(rows)} takes" + (f", auto {Path(shots[-1]['auto']).name}" if shots[-1]["auto"] else ""))
    (P.dir / "takes").mkdir(exist_ok=True)
    with LOCK:
        data = dict(title=P.get("title") or P.dir.name, shots=shots, dirty=_read_json(tj, {}).get("dirty", []))
        write_atomic(tj, data)
    if not quiet:
        print(f"-> takes/takes.json ({len(shots)} shots); look at them: uv run takes.py {P.dir} --serve")
    return data


def choose(P, shot, file):
    """file = a take (relative path) or "still" -> selection.json manual.clip[shot]; None -> back to the automatic pick."""
    with LOCK:
        _choose(P, shot, file)


def _choose(P, shot, file):
    f = P.dir / "selection.json"
    sel = read_sel(P)
    man = sel.setdefault("manual", {}).setdefault("clip", {})
    data = _read_json(P.dir / "takes" / "takes.json", {"shots": []})
    s = next((x for x in data["shots"] if x["name"] == shot), None)
    take = next((t for t in (s or {}).get("takes", []) if t["file"] == file), None) if file else None
    if file and not take:
        raise ValueError(f"{file} is not a take of {shot}")
    sel["clip"] = dict(sel.get("clip") or {})
    auto = auto_entry_of(sel["clip"].get(shot) or {}, s) or (s or {}).get("auto_entry") or {}
    keep = {"auto": auto} if auto else {}                  # the automatic pick stays known (pick.py does the same)
    if take and file == STILL:                             # render_shots: "still" skips the clip -> still + depth move
        man[shot] = {"still": True}
        sel["clip"][shot] = {"still": True, "manual": True, **keep}
    elif take:                                             # render_shots reads "clip": the manual choice goes there too
        man[shot] = {"file": take["file"], "lag": take["lag"]}
        sel["clip"][shot] = {"file": take["file"], "lag": take["lag"], "manual": True, **keep}
    else:
        man.pop(shot, None)
        if auto:                                           # back to the automatic pick
            sel["clip"][shot] = auto
        else:
            sel["clip"].pop(shot, None)
    write_atomic(f, sel)
    if s:
        s["manual"] = take["file"] if take else None
        s["note"] = ""
        data["dirty"] = sorted(set(data.get("dirty", [])) | {shot})   # chosen since the last cut
        write_atomic(P.dir / "takes" / "takes.json", data)


def rendered(P):
    """render.log -> {shot: description} (what the scenes/ frames were last made from)."""
    f = P.dir / "render.log"
    out = {}
    if f.exists():
        for ln in f.read_text(encoding="utf-8", errors="replace").splitlines():
            m = re.match(r"(\S+)\s+[\d.]+-\s*[\d.]+\s+\S+\s+(.*)$", ln)
            if m:
                out[m.group(1)] = m.group(2).strip()
    return out


def changed(P, sel=None):
    """Shots whose scenes/ frames do not show the current choice (or were never rendered)."""
    sel, done_ = sel if sel is not None else read_sel(P), rendered(P)
    tj = P.dir / "takes" / "takes.json"
    dirty = set(_read_json(tj, {}).get("dirty", []))
    out = []
    for s in P.sections():
        name = s["name"]
        d = done_.get(name)
        c = (sel.get("clip") or {}).get(name) or {}
        if not (P.dir / "scenes" / name).exists():
            out.append(name)
        elif d is None:                                    # rendered, but render.log lost the line (old --only run)
            if name in dirty:
                out.append(name)
        elif c.get("still"):
            if not d.startswith("still"):
                out.append(name)
        elif c.get("file") and P.path(c["file"]).exists():
            first = P.dir / "scenes" / name / "f.0000.png"
            if d != f"clip {c['file']} lag {c.get('lag', 0):+d}":
                out.append(name)
            elif first.exists() and P.path(c["file"]).stat().st_mtime > first.stat().st_mtime + 1:
                out.append(name)                           # the clip was re-rendered under the same name (Das Warum:
                #                                            two re-shot shots were missing from "Build cut")
    return out


class Builder:
    """render_shots.py --only <changed> + make_film.py in a thread; the page polls the state."""

    def __init__(self, P):
        self.P, self.state, self.lock = P, dict(running=False, ok=None, step="", log="", shots=[]), threading.Lock()

    def start(self):
        with self.lock:
            if self.state["running"]:
                return False
            todo = changed(self.P)
            self.state.update(running=True, ok=None, step="", log="", shots=todo)
        threading.Thread(target=self._run, args=(todo,), daemon=True).start()
        return True

    def _run(self, todo):
        steps = ([("scenes " + ",".join(todo), ["uv", "run", str(HERE / "render_shots.py"), str(self.P.dir), "--only",
                                                 ",".join(todo)])] if todo else []) + \
                [("film", ["uv", "run", str(HERE / "make_film.py"), str(self.P.dir)])]
        for label, cmd in steps:
            self.state["step"] = label
            r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
            self.state["log"] = (self.state["log"] + (r.stdout or "")[-1500:] + (r.stderr or "")[-1500:])[-3000:]
            if r.returncode:
                self.state.update(running=False, ok=False)
                return
        tj = self.P.dir / "takes" / "takes.json"
        with LOCK:                                         # only the shots that were built: a choice made during the
            d = _read_json(tj, {"shots": []})              # build stays "changed"
            sel = read_sel(self.P)
            d["dirty"] = [n for n in d.get("dirty", []) if n not in self.state["shots"] or n in changed(self.P, sel)]
            write_atomic(tj, d)
        self.state.update(running=False, ok=True, step="done")


def film_file(P):
    for n in ("film_small.mp4", "film.mp4"):
        if (P.dir / n).exists():
            return P.dir / n
    return None


def serve(P, port=0, host="127.0.0.1"):
    allowed_hosts = ("127.0.0.1", "localhost", "[::1]", host)
    builder = Builder(P)

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
            if not path or not path.exists():
                return self.reply(404, {"error": "missing"})
            size = path.stat().st_size
            m = re.match(r"bytes=(\d*)-(\d*)", self.headers.get("Range", ""))
            a, b = 0, size - 1
            if m:
                if m.group(1):
                    a = int(m.group(1))
                    b = min(int(m.group(2)) if m.group(2) else size - 1, size - 1)
                else:
                    a = max(0, size - int(m.group(2) or 0))
                if a >= size or b < a:
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
                # built again on every load: pick.py / a night run may have changed the automatic picks, lags or
                # takes meanwhile (user test 0.5.3: the page kept the old "automatic pick", A restored another);
                # previews are only made again when their placement key changed
                with LOCK:
                    d = build(P, quiet=True)
                d["changed"] = changed(P)
                return self.reply(200, d)
            if p == "/api/build":
                f = film_file(P)
                return self.reply(200, dict(builder.state, changed=changed(P), film=f.name if f else None,
                                            film_time=f.stat().st_mtime if f else None))
            if p == "/film.mp4":
                return self.file(film_file(P), "video/mp4")
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
            try:
                d = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
                if not isinstance(d, dict):
                    raise ValueError("send a JSON object")
                if self.path == "/api/choose":
                    choose(P, str(d["shot"]), d.get("file"))
                    return self.reply(200, {"ok": True, "changed": changed(P)})
                if self.path == "/api/build":
                    if not builder.start():
                        return self.reply(409, {"error": "a cut is being built already"})
                    return self.reply(200, {"ok": True})
            except (ValueError, KeyError, TypeError) as e:
                return self.reply(400, {"error": str(e)})
            self.reply(404, {"error": "unknown"})

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
    sys.exit(main())
