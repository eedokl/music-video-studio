"""FastAPI server of the music-video studio.

uv run studio            → http://localhost:8000 (serves the built frontend + API)
"""

from __future__ import annotations

import json
import re
import shutil
import time
from contextlib import asynccontextmanager
from pathlib import Path

import numpy as np
import uvicorn
from fastapi import Body, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import chat, export, legacy, pipeline, store, storyboard
from .config import FRONTEND_DIST, HOST, PORT


@asynccontextmanager
async def _lifespan(_app: FastAPI):
    # startup: remove leftovers of exports interrupted by a previous shutdown
    for d in store.PROJECTS.iterdir():
        if (d / "out").is_dir():
            export.cleanup(d / "out")
    yield


app = FastAPI(title="Music Video Studio", lifespan=_lifespan)


def _404(pid: str):
    if not (store.project_dir(pid) / "project.json").exists():
        raise HTTPException(404, "project not found")


# ---------------------------------------------------------------- projects
@app.get("/api/projects")
def projects():
    return store.list_projects()


@app.post("/api/projects")
async def create(
    title: str = Form(...),
    lyrics: str = Form(...),
    storyline: str = Form(""),
    stylePrompt: str = Form(""),
    song: UploadFile = File(...),
    stems: list[UploadFile] = File(default=[]),
):
    pid = store.new_id(title)
    d = store.project_dir(pid)
    inp = d / "inputs"
    (inp / "stems").mkdir(parents=True)
    song_name = "song" + Path(song.filename or "song.wav").suffix.lower()
    (inp / song_name).write_bytes(await song.read())
    stem_names = []
    for s in stems:
        if not s.filename:
            continue
        name = Path(s.filename).name
        data = await s.read()
        if name.lower().endswith(".zip"):
            # e.g. Suno "Auto Split" download: take the audio files from the archive (flat, safe names)
            import io
            import zipfile

            with zipfile.ZipFile(io.BytesIO(data)) as z:
                for info in z.infolist():
                    member = Path(info.filename).name
                    if info.is_dir() or not member.lower().endswith((".wav", ".mp3", ".flac")):
                        continue
                    (inp / "stems" / member).write_bytes(z.read(info))
                    stem_names.append(member)
            continue
        (inp / "stems" / name).write_bytes(data)
        stem_names.append(name)
    meta = {"title": title, "lyrics": lyrics, "storyline": storyline, "stylePrompt": stylePrompt, "song": song_name, "stems": stem_names}
    (inp / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    store.save(
        pid,
        {
            "format": 1,
            "id": pid,
            "title": title,
            "storyline": storyline,
            "status": "analyzing",
            "audio": {"duration": 0},
            "lyrics": {"lines": []},
            "scenes": [],
        },
        keep_history=False,
    )
    pipeline.start(pid)
    return {"id": pid}


@app.get("/api/projects/{pid}")
def get_project(pid: str):
    _404(pid)
    data = store.load(pid)
    return JSONResponse(data, headers={"X-Version": str(store.version(pid))})


@app.put("/api/projects/{pid}")
def put_project(pid: str, data: dict = Body(...), base: float | None = None):
    _404(pid)
    if chat.state(pid).get("status") == "running":
        raise HTTPException(409, "the chat assistant is editing this project")
    if base is not None and abs(store.version(pid) - base) > 1e-6:
        raise HTTPException(409, "project changed on the server – reload")
    if data.get("world") == "legacy" and data.get("legacy", {}).get("origLines"):
        # lyrics may have been edited (words changed / added / removed): keep the original engine's
        # line mapping in step with the studio words
        from .legacy import word_map

        data["legacy"]["lineMap"] = word_map(data["legacy"]["origLines"], data["lyrics"]["lines"])
        return {"version": store.save(pid, data), "lineMap": data["legacy"]["lineMap"]}
    return {"version": store.save(pid, data)}


@app.get("/api/projects/{pid}/status")
def status(pid: str):
    _404(pid)
    return {"version": store.version(pid), "job": pipeline.job(pid), "chat": chat.state(pid), "export": export.state(pid)}


@app.post("/api/projects/{pid}/analyze")
def reanalyze(pid: str, step: str = "prepare", keep: bool = False):
    """Re-run the analysis from `step`. keep=true: re-measure the timing but keep scenes, events, looks
    and the held-note names the storyboard uses (anchors then follow the new word times)."""
    _404(pid)
    if step not in pipeline.STEPS:
        raise HTTPException(400, f"step must be one of {pipeline.STEPS}")
    mf = store.project_dir(pid) / "inputs" / "meta.json"
    if not mf.exists():
        raise HTTPException(400, "no inputs for this project")
    meta = json.loads(mf.read_text(encoding="utf-8"))
    meta["keepScenes"] = keep
    ids = meta.get("idMap") or []
    row = lambda lid: ids.index(lid) if lid in ids else int(lid[1:])  # noqa: E731
    meta["keepHeld"] = [{"name": h["name"], "row": row(h["line"])} for h in store.load(pid).get("held", [])] if keep else []
    meta.pop("newAudio", None)
    meta.pop("updatePlan", None)
    mf.write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    if not pipeline.start(pid, step):
        raise HTTPException(409, "analysis already running")
    return {"ok": True}


HEADERS = {
    "intro": "[Intro]",
    "verse1": "[Verse 1]",
    "chorus": "[Chorus]",
    "verse2": "[Verse 2]",
    "bridge": "[Bridge]",
    "final": "[Final Chorus]",
    "outro": "[Outro]",
}


def _current_lyrics(pid: str) -> str:
    mf = store.project_dir(pid) / "inputs" / "meta.json"
    if mf.exists():
        return json.loads(mf.read_text(encoding="utf-8")).get("lyrics", "")
    out, last = [], None
    for ln in store.load(pid).get("lyrics", {}).get("lines", []):
        if ln["section"] != last:
            out.append(HEADERS.get(ln["section"], f"[{ln['section']}]"))
            last = ln["section"]
        out.append(ln["text"])
    return "\n".join(out)


@app.get("/api/projects/{pid}/lyrics-text")
def lyrics_text_get(pid: str):
    _404(pid)
    return {"lyrics": _current_lyrics(pid)}


@app.post("/api/projects/{pid}/update-audio")
async def update_audio(pid: str, song: UploadFile = File(...), lyrics: str = Form(""), stems: list[UploadFile] = File(default=[])):
    """New version of the song (e.g. re-rendered in Suno with small lyric/timing changes): re-analyse it
    and carry the existing storyboard over (lines matched by text, time anchors shifted)."""
    _404(pid)
    if pipeline.job(pid) and pipeline.job(pid).get("status") == "running":
        raise HTTPException(409, "analysis already running")
    from . import lyrics_text, update

    old = store.load(pid)
    d = store.project_dir(pid)
    inp = d / "inputs"
    inp.mkdir(exist_ok=True)
    mf = inp / "meta.json"
    meta = (
        json.loads(mf.read_text(encoding="utf-8"))
        if mf.exists()
        else {"title": old.get("title", pid), "storyline": old.get("storyline", ""), "stylePrompt": old.get("stylePrompt", "")}
    )
    text = lyrics.strip() or _current_lyrics(pid)
    for f in inp.glob("song.*"):
        f.unlink()
    song_name = "song" + Path(song.filename or "song.wav").suffix.lower()
    (inp / song_name).write_bytes(await song.read())
    sd = inp / "stems"
    if sd.exists():
        shutil.rmtree(sd)
    sd.mkdir()
    stem_names = []
    for st in stems:
        if not st.filename:
            continue
        name = Path(st.filename).name
        data = await st.read()
        if name.lower().endswith(".zip"):
            import io
            import zipfile

            with zipfile.ZipFile(io.BytesIO(data)) as z:
                for info in z.infolist():
                    member = Path(info.filename).name
                    if not info.is_dir() and member.lower().endswith((".wav", ".mp3", ".flac")):
                        (sd / member).write_bytes(z.read(info))
                        stem_names.append(member)
            continue
        (sd / name).write_bytes(data)
        stem_names.append(name)
    # old stems no longer belong to the new render
    for f in (d / "audio" / "stems").glob("*.wav") if (d / "audio" / "stems").exists() else []:
        f.unlink()
    rows = lyrics_text.parse(text)
    plan = update.plan(old, rows)
    ids = plan["ids"]
    meta.update(
        song=song_name,
        stems=stem_names,
        lyrics=text,
        keepScenes=True,
        newAudio=True,
        idMap=ids,
        updatePlan=plan,
        keepHeld=[{"name": h["name"], "row": ids.index(h["line"])} for h in old.get("held", []) if h["line"] in ids],
    )
    meta.pop("stemMap", None)
    meta.pop("stemCheck", None)
    mf.write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    store.save(pid, old)  # keep the pre-update version in the history
    pipeline.start(pid, "prepare")
    return {
        "ok": True,
        "matched": sum(1 for s in plan["status"] if s != "new"),
        "new": plan["status"].count("new"),
        "changed": plan["status"].count("changed"),
        "removed": len(plan["removed"]),
    }


@app.post("/api/projects/{pid}/duplicate")
def duplicate(pid: str, title: str = Body(..., embed=True)):
    """Copy a project (audio, analysis, scenes, imported engine) under a new name – e.g. to start the
    next version of a video and then update its audio."""
    _404(pid)
    new = store.new_id(title)
    src, dst = store.project_dir(pid), store.project_dir(new)
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns(".history", "chat", "out", "*.tmp"))
    p = store.load(new)
    p["id"], p["title"] = new, title
    p.pop("lastUpdate", None)
    store.save(new, p, keep_history=False)
    mf = dst / "inputs" / "meta.json"
    if mf.exists():
        m = json.loads(mf.read_text(encoding="utf-8"))
        m["title"] = title
        mf.write_text(json.dumps(m, ensure_ascii=False, indent=1), encoding="utf-8")
    return {"id": new}


@app.post("/api/projects/import-video")
def import_video(path: str = Body(..., embed=True), title: str = Body("", embed=True)):
    """New project from an existing hand-built video folder (src/scenes.ts, src/lyrics.ts,
    public/song.wav): song and lyrics come from the folder, the analysis runs, then the original
    scenes are imported (pipeline step "engine")."""
    from . import legacy

    old = Path(path.strip().strip('"'))
    missing = [x for x in ("src/scenes.ts", "src/lyrics.ts", "src/main.ts") if not (old / x).exists()]
    song = next((old / "public" / n for n in ("song.wav", "song.mp3") if (old / "public" / n).exists()), None)
    if not old.is_dir():
        raise HTTPException(400, f"Ordner nicht gefunden: {old}")
    if missing or song is None:
        raise HTTPException(
            400,
            f"Kein unterstütztes Video-Projekt (fehlt: {', '.join(missing + ([] if song else ['public/song.wav']))}). Ältere Engines wie Pop-up "
            "oder Rock werden noch nicht unterstützt.",
        )
    src_scenes = (old / "src" / "scenes.ts").read_text(encoding="utf-8")
    if "export const SCENES" not in src_scenes:
        raise HTTPException(400, "Dieses Projekt nutzt eine ältere Engine ohne SCENES-Liste (z. B. Pop-up oder Rock) – noch nicht unterstützt.")
    rows = legacy.parse_raw((old / "src" / "lyrics.ts").read_text(encoding="utf-8"))
    if not rows:
        raise HTTPException(400, "Konnte den Liedtext (RAW in src/lyrics.ts) nicht lesen.")
    if not title:
        html = (old / "index.html").read_text(encoding="utf-8") if (old / "index.html").exists() else ""
        m = re.search(r"<title>(.*?)</title>", html)
        title = m.group(1).strip() if m else old.name
    out, last = [], None
    for sec, text in rows:
        if sec != last:
            out.append(HEADERS.get(sec, f"[{sec}]"))
            last = sec
        out.append(text)
    pid = store.new_id(title)
    d = store.project_dir(pid)
    (d / "inputs" / "stems").mkdir(parents=True)
    shutil.copy(song, d / "inputs" / ("song" + song.suffix))
    meta = {
        "title": title,
        "lyrics": "\n".join(out),
        "storyline": f"Imported from {old}",
        "stylePrompt": "",
        "song": "song" + song.suffix,
        "stems": [],
        "legacySource": str(old),
    }
    (d / "inputs" / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    store.save(
        pid,
        {
            "format": 1,
            "id": pid,
            "title": title,
            "storyline": meta["storyline"],
            "status": "analyzing",
            "audio": {"duration": 0},
            "lyrics": {"lines": []},
            "scenes": [],
        },
        keep_history=False,
    )
    pipeline.start(pid)
    return {"id": pid}


@app.post("/api/projects/{pid}/storyboard")
def restoryboard(pid: str):
    """Replace scenes/events/looks with a fresh automatic storyboard (keeps lyrics and timing)."""
    _404(pid)
    p = store.load(pid)
    p["scenes"], p["events"], p["looks"] = storyboard.build(p)
    return {"version": store.save(pid, p)}


@app.post("/api/projects/{pid}/grid")
def set_grid_mode(pid: str, mode: str = Body(..., embed=True)):
    _404(pid)
    p = store.load(pid)
    g = p["grid"]
    g["mode"] = mode
    g["beats"] = g["fixed"] if mode == "fixed" else g["detected"]
    return {"version": store.save(pid, p)}


@app.post("/api/projects/{pid}/legacy/build")
def legacy_build(pid: str):
    """Re-bundle an imported engine (after its original code in legacy/src was changed)."""
    _404(pid)
    try:
        return {"log": legacy.build(pid)}
    except RuntimeError as e:
        raise HTTPException(400, str(e)) from e


@app.get("/api/projects/{pid}/history")
def hist(pid: str):
    _404(pid)
    return store.history(pid)


@app.post("/api/projects/{pid}/history/{name}")
def restore(pid: str, name: str):
    _404(pid)
    return {"version": store.restore(pid, name)}


# ---------------------------------------------------------------- media
@app.get("/api/projects/{pid}/files/{rel:path}")
def files(pid: str, rel: str):
    p = store.safe_file(pid, rel)
    if not p.is_file():
        raise HTTPException(404)
    # code, styles, pages and data change (rebuilds, edits) – never let the browser keep an old copy
    headers = {"Cache-Control": "no-store"} if p.suffix in (".js", ".json", ".css", ".html", ".mjs") else {}
    if rel.replace("\\", "/") == "legacy/index.html":
        # stamp the bundle URLs with their build time: a browser that cached an older app.js/app.css
        # (before no-store was sent) must fetch the new build because the address is new
        from fastapi.responses import HTMLResponse

        html = p.read_text(encoding="utf-8")
        for name in ("app.js", "app.css"):
            f = p.parent / name
            if f.exists():
                html = html.replace(f'"{name}"', f'"{name}?v={int(f.stat().st_mtime)}"')
        return HTMLResponse(html, headers=headers)
    return FileResponse(p, headers=headers)


@app.get("/api/projects/{pid}/peaks")
def peaks(pid: str, src: str = "mix", fps: int = 100):
    """min/max envelope (fps values per second) for the timeline waveform, cached."""
    p = store.load(pid)
    rel = p["audio"].get(src) or p["audio"].get("stems", {}).get(src)
    if not rel:
        raise HTTPException(404, "no such audio")
    wav = store.safe_file(pid, rel)
    cache = wav.with_suffix(f".peaks{fps}.json")
    if cache.exists() and cache.stat().st_mtime > wav.stat().st_mtime:
        return FileResponse(cache)
    x, sr = pipeline._read(wav)
    m = x.mean(axis=1)
    h = sr // fps
    n = len(m) // h
    blk = m[: n * h].reshape(n, h)
    data = {"fps": fps, "max": np.round(blk.max(axis=1), 3).tolist(), "min": np.round(blk.min(axis=1), 3).tolist()}
    cache.write_text(json.dumps(data))
    return data


# ---------------------------------------------------------------- chat + export
@app.get("/api/projects/{pid}/chat")
def chat_history(pid: str):
    _404(pid)
    return {"messages": chat.history(pid), "state": chat.state(pid)}


@app.post("/api/projects/{pid}/chat")
def chat_send(pid: str, text: str = Body(..., embed=True), context: str = Body("", embed=True)):
    _404(pid)
    if not chat.send(pid, text, context):
        raise HTTPException(409, "the assistant is still working on the last message")
    return {"ok": True}


@app.delete("/api/projects/{pid}/chat")
def chat_reset(pid: str):
    chat.reset(pid)
    return {"ok": True}


@app.post("/api/projects/{pid}/export")
def export_start(
    pid: str,
    variants: list[str] = Body(["full", "small", "mail"], embed=True),
    start: float | None = Body(None, embed=True),
    end: float | None = Body(None, embed=True),
):
    """variants: any of full, compressed, small, mail, preview; start/end: only that range (seconds)."""
    _404(pid)
    if not (FRONTEND_DIST / "index.html").exists():
        raise HTTPException(400, "frontend not built – run `npm run build` in frontend/")
    if not export.start(pid, variants, start, end):
        raise HTTPException(409, "export already running")
    return {"ok": True}


@app.get("/api/projects/{pid}/exports")
def exports_list(pid: str):
    """finished MP4s of a project (newest first)"""
    _404(pid)
    out = store.project_dir(pid) / "out"
    files = []
    for f in sorted(out.glob("*.mp4"), key=lambda x: -x.stat().st_mtime) if out.exists() else []:
        if f.name.startswith("."):
            continue
        st = f.stat()
        kind = next((k for k, suf in (("compressed", "_compressed"), ("small", "_small"), ("mail", "_mail"), ("preview", "_preview")) if suf in f.stem), "full")
        files.append({"name": f.name, "size": st.st_size, "mtime": st.st_mtime, "kind": kind})
    return {"files": files, "folder": str(out)}


@app.delete("/api/projects/{pid}/exports/{name}")
def exports_delete(pid: str, name: str):
    f = store.safe_file(pid, f"out/{name}")
    if f.suffix.lower() != ".mp4" or not f.is_file():
        raise HTTPException(404)
    f.unlink()
    return {"ok": True}


@app.post("/api/projects/{pid}/exports/open-folder")
def exports_open(pid: str):
    """open the export folder in Windows Explorer (the server runs on this PC)"""
    import os

    out = store.project_dir(pid) / "out"
    out.mkdir(exist_ok=True)
    if os.name == "nt":
        os.startfile(out)
    return {"folder": str(out)}


@app.delete("/api/projects/{pid}/export")
def export_cancel(pid: str):
    if not export.cancel(pid):
        raise HTTPException(409, "no export running")
    return {"ok": True}


@app.get("/api/health")
def health():
    return {"ok": True, "time": time.time()}


# ---------------------------------------------------------------- frontend
if FRONTEND_DIST.exists():
    app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")


def run():
    uvicorn.run("studio.main:app", host=HOST, port=PORT, reload=False)


if __name__ == "__main__":
    run()
