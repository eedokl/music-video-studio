"""Imported video engines ("legacy world"): play a video built with an earlier hand-made engine
(comfort-zone, roles-video, azure-version, …) with its ORIGINAL scenes inside the studio.

  uv run python -m studio.legacy import <project-id> <old-project-dir>
  uv run python -m studio.legacy build  <project-id>

The studio project must exist and be analysed (song + lyrics as performed). The importer
  1. copies the old src/ (+ public assets) to projects/<id>/legacy/src and patches its data modules:
     lyrics.ts → shim reading the studio project (original kept as lyrics_orig.ts), vocal.ts → held
     notes from the project, lyric.ts → lead from the project; adds studio_main.ts + index.html,
  2. maps the old lyric line indices to studio line ids (by text, in order) → project.legacy.lineMap,
  3. re-measures the old held notes (same names) on the studio's vocal track,
  4. builds the bundle, reads the original SCENES from the running page (headless) and creates one
     studio scene per original scene (start: auto, word anchor or time) → editable timeline.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

from . import store
from .config import RENDERER, ROOT
from .pipeline import UV_LIGHT, PIPELINE

ADAPTER = ROOT / "legacy" / "adapter"


def norm(s: str) -> str:
    return re.sub(r"[^\w]", "", s.lower())


def parse_raw(lyrics_ts: str) -> list[tuple[str, str]]:
    """RAW entries of an old lyrics.ts: ["verse1", "text"] or ['verse1', 'text'] (one per line)."""
    import ast

    body = lyrics_ts.split("const RAW", 1)[-1]
    rows = []
    for ln in body.splitlines():
        m = re.match(r"""^\s*(\[\s*(['"])\w+\2\s*,\s*(['"]).*\3\s*\])\s*,?\s*(//.*)?$""", ln)
        if m:
            try:
                sec, text = ast.literal_eval(m.group(1))
            except (ValueError, SyntaxError):
                continue
            rows.append((sec, text))
        elif rows and ln.strip().startswith("];"):
            break
    return rows


def word_map(orig_texts: list[str], lines: list[dict]) -> list:
    """Original engine line index → where its words are now in the studio lyrics.

    Word-level, so merged or split lines still work: the original line "and time doesn't wait." can be
    words 5–8 of the studio line "Twenty thirty one is coming, and time doesn't wait.". Entries:
    "l12" (whole line), {"id": "l12", "from": 5, "to": 8} (part of a line) or None (no longer sung)."""
    import difflib

    a = [(i, k, norm(w)) for i, t in enumerate(orig_texts) for k, w in enumerate(t.split(" ")) if norm(w)]
    b = [(ln["id"], k, norm(w["w"])) for ln in lines for k, w in enumerate(ln.get("words", [])) if norm(w["w"])]
    sm = difflib.SequenceMatcher(a=[x[2] for x in a], b=[x[2] for x in b], autojunk=False)
    hits: dict[int, list[tuple[str, int]]] = {}
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == "equal":
            for q in range(i2 - i1):
                hits.setdefault(a[i1 + q][0], []).append((b[j1 + q][0], b[j1 + q][1]))
        elif op == "replace":
            # replaced words ("Dann" → "Danach", "Europa" → "Europe") belong to the original line of the
            # word they replace (pair them in order)
            na, nb = i2 - i1, j2 - j1
            for q in range(nb):
                src = a[i1 + min(na - 1, q * na // nb)]
                hits.setdefault(src[0], []).append((b[j1 + q][0], b[j1 + q][1]))
    nwords = {ln["id"]: len(ln.get("words", [])) for ln in lines}
    ranges: dict[int, list] = {}
    for i in range(len(orig_texts)):
        hs = hits.get(i)
        if not hs:
            continue
        counts: dict[str, int] = {}
        for lid, _ in hs:
            counts[lid] = counts.get(lid, 0) + 1
        lid = max(counts, key=lambda x: counts[x])
        ks = [k for x, k in hs if x == lid]
        ranges[i] = [lid, min(ks), max(ks)]
    # changed words at the edges ("Europa" → "Europe", "Dann" → "Danach") belong to the neighbouring
    # original line: extend each range over studio words no other original line claims
    owner: dict[tuple[str, int], int] = {}
    for i, (lid, lo, hi) in ranges.items():
        for k in range(lo, hi + 1):
            owner[(lid, k)] = i
    for i in sorted(ranges):
        lid, lo, hi = ranges[i]
        while lo > 0 and (lid, lo - 1) not in owner:
            lo -= 1
            owner[(lid, lo)] = i
        while hi < nwords[lid] - 1 and (lid, hi + 1) not in owner:
            hi += 1
            owner[(lid, hi)] = i
        ranges[i] = [lid, lo, hi]
    out: list = []
    for i in range(len(orig_texts)):
        if i not in ranges:
            out.append(None)
            continue
        lid, lo, hi = ranges[i]
        out.append(lid if lo == 0 and hi == nwords[lid] - 1 else {"id": lid, "from": lo, "to": hi})
    return out


def map_entry_id(e) -> str | None:
    return e if isinstance(e, str) else (e or {}).get("id")


def build(pid: str) -> str:
    d = store.project_dir(pid)
    r = subprocess.run(["node", str(ROOT / "tools" / "legacy-build.mjs"), str(d)], capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise RuntimeError(f"legacy build failed:\n{r.stdout}\n{r.stderr}")
    p = store.load(pid)
    p.setdefault("legacy", {})["built"] = time.time()
    store.save(pid, p, keep_history=False)
    return (r.stdout + r.stderr).strip()


def src_changed_since_build(pid: str) -> bool:
    d = store.project_dir(pid) / "legacy"
    app = d / "app.js"
    if not app.exists():
        return True
    t = app.stat().st_mtime
    return any(f.stat().st_mtime > t for f in (d / "src").rglob("*") if f.is_file())


def _read_scenes(pid: str) -> list[dict]:
    """Open the built legacy page headless and ask the original code for its scene list."""
    script = r"""
import puppeteer from 'puppeteer-core';
import { existsSync, readdirSync } from 'node:fs';
import { resolve } from 'node:path';
const base = resolve(process.env.TEMP ?? '/tmp', 'mvchrome/chrome-headless-shell');
const exe = existsSync(base) ? readdirSync(base).map((v) => resolve(base, v, 'chrome-headless-shell-win64/chrome-headless-shell.exe')).find(existsSync) : undefined;
const b = await puppeteer.launch({ executablePath: exe, headless: 'shell', args: ['--use-angle=d3d11', '--enable-gpu'] });
const pg = await b.newPage();
await pg.setViewport({ width: 1280, height: 720 });
const errs = [];
pg.on('pageerror', (e) => errs.push(e.message));
await pg.goto(process.argv[2], { waitUntil: 'networkidle0', timeout: 60000 });
await pg.waitForFunction('window.__ready === true', { timeout: 60000 }).catch(() => {});
const scenes = await pg.evaluate(() => (window.__scenes ? window.__scenes() : null));
console.log(JSON.stringify({ scenes, errs }));
await b.close();
"""
    f = RENDERER / "_legacy_scenes.mjs"
    f.write_text(script, encoding="utf-8")
    from .config import RENDER_BASE

    url = f"{RENDER_BASE}/api/projects/{pid}/files/legacy/index.html?project={pid}"
    r = subprocess.run(["node", str(f), url], cwd=RENDERER, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180)
    f.unlink(missing_ok=True)
    out = json.loads(r.stdout.strip().splitlines()[-1])
    if not out.get("scenes"):
        raise RuntimeError(f"could not read scenes from the legacy page: {out.get('errs')} {r.stderr[-800:]}")
    if out["errs"]:
        print("page errors:", out["errs"])
    return out["scenes"]


def import_legacy(pid: str, old: Path):
    d = store.project_dir(pid)
    p = store.load(pid)
    lead = p.get("lyrics", {}).get("lead", 0.08)
    L = d / "legacy"
    if L.exists():
        shutil.rmtree(L)
    shutil.copytree(old / "src", L / "src")
    # public assets (images etc.), not the song
    if (old / "public").exists():
        for f in (old / "public").rglob("*"):
            if f.is_file() and f.suffix.lower() not in (".wav", ".mp3"):
                dst = L / f.relative_to(old / "public")
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(f, dst)
    s = L / "src"
    # ---- patch the data modules
    (s / "lyrics.ts").rename(s / "lyrics_orig.ts")
    shutil.copy(ADAPTER / "lyrics_shim.ts", s / "lyrics.ts")
    shutil.copy(ADAPTER / "studio_data.ts", s / "studio_data.ts")
    if (s / "vocal.ts").exists():  # engines without held notes have no vocal.ts
        v = (s / "vocal.ts").read_text(encoding="utf-8")
        v = re.sub(r"import held from '\./held\.json';", "import { studio } from './studio_data';\nconst held = studio.held;", v)
        v = re.sub(r"export type TrackName = [^;]+;", "export type TrackName = string;", v)
        (s / "vocal.ts").write_text(v, encoding="utf-8")
    ly = (s / "lyric.ts").read_text(encoding="utf-8")
    if "export const LEAD" in ly:
        ly = re.sub(r"export const LEAD = [\d.]+;", "export let LEAD = 0.08;\nexport function __setLead(v: number) {\n  LEAD = v;\n}", ly)
    else:  # engine without a lyric lead: no-op setter
        ly += "\nexport function __setLead(_v: number) {}\n"
    (s / "lyric.ts").write_text(ly, encoding="utf-8")
    main_orig = (s / "main.ts").read_text(encoding="utf-8")
    (s / "main.ts").rename(s / "main_orig.ts")
    fonts = "\n  ".join(re.findall(r"await document\.fonts\.load\([^)]*\);", main_orig))
    sm = (ADAPTER / "studio_main.ts").read_text(encoding="utf-8").replace("/*FONTS*/", fonts)
    sm = sm.replace("import { World3D } from './world3d';", "import { World3D } from './world3d';\nimport { __setLead } from './lyric';")
    sm = sm.replace("w.__update = (p: any) => {\n  studio.update(p);", "w.__update = (p: any) => {\n  studio.update(p);\n  __setLead(studio.lead);")
    sm = sm.replace("rebuildSchedule();\n\nwindow", "rebuildSchedule();\n__setLead(studio.lead);\n\nwindow")
    (s / "studio_main.ts").write_text(sm, encoding="utf-8")
    html = (ADAPTER / "index.html").read_text(encoding="utf-8")
    old_html = (old / "index.html").read_text(encoding="utf-8") if (old / "index.html").exists() else ""
    links = "\n    ".join(re.findall(r"<link[^>]+fonts\.(?:googleapis|gstatic)[^>]*>", old_html))
    (L / "index.html").write_text(html.replace("<!--FONTS-->", links), encoding="utf-8")

    # ---- old line index → studio words (word level: merged / split lines keep working)
    rows = parse_raw((s / "lyrics_orig.ts").read_text(encoding="utf-8"))
    orig_texts = [t for _, t in rows]
    line_map = word_map(orig_texts, p["lyrics"]["lines"])
    missing = [rows[i][1] for i, x in enumerate(line_map) if x is None]
    if missing:
        print("WARNING: old lines without a studio line:", missing)

    # ---- held notes: same names as the old engine, re-measured on the studio vocals
    held_old = json.loads((s / "held.json").read_text()) if (s / "held.json").exists() else {}
    timing_old = json.loads((s / "timing.json").read_text()) if (s / "timing.json").exists() else []
    byid = {ln["id"]: ln for ln in p["lyrics"]["lines"]}
    specs, held_lines = [], {}
    for name, tr in held_old.items():
        # the old word (any word, not only the last – e.g. "FIF-teen roles") that starts closest to the
        # old track start; its counterpart in the studio line gets re-measured for the old duration
        cands = [(abs(ws - tr["t0"]), i, k) for i, x in enumerate(timing_old) for k, ws in enumerate(x.get("words", []))]
        if not cands:
            continue
        _, best, wk = min(cands)
        if best >= len(line_map) or not line_map[best]:
            continue
        ent = line_map[best]
        ln = byid[map_entry_id(ent)]
        if isinstance(ent, dict):
            wk = min(ent["from"] + wk, ent["to"])
        wk = min(wk, len(ln["words"]) - 1)
        w = ln["words"][wk]
        old_dur = len(tr.get("env", [])) / tr.get("fps", 30) if tr.get("env") else 0
        specs.append(f"{name}:{w['t'] - 0.05:.2f}:{max(w['e'] + 0.1, w['t'] + old_dur):.2f}")
        held_lines[name] = (ln["id"], wk)
    held = []
    if specs:
        out = d / "analysis" / "held_legacy.json"
        out.parent.mkdir(exist_ok=True)
        subprocess.run(["uv", "run", "--no-project", *UV_LIGHT, "python", str(PIPELINE / "held.py"), str(d / "audio" / "vocals.wav"), str(out), *specs], check=True)
        hm = json.loads(out.read_text())
        held = [{"name": n, "line": held_lines[n][0], "word": held_lines[n][1], **hm[n]} for n in hm]

    p["world"] = "legacy"
    p["legacy"] = {"engine": old.name, "lineMap": line_map, "origLines": orig_texts, "scenes": []}
    p["held"] = held
    p["events"], p["looks"] = [], {}
    p["scenes"] = [{"id": "s0", "name": "temp", "start": {"kind": "time", "t": 0}, "lines": [], "legacy": ""}]
    store.save(pid, p)
    print(build(pid))

    # ---- original scenes → studio scenes
    src_scenes = (s / "scenes.ts").read_text(encoding="utf-8")
    word_starts = {}
    for m in re.finditer(r"id: '([^']+)'[^}]*?start: L\[(\d+)\]\.e \+ ([\d.]+)", src_scenes, re.S):
        word_starts[m.group(1)] = (int(m.group(2)), float(m.group(3)))
    first_sung = min((ln["words"][0]["t"] for ln in p["lyrics"]["lines"] if ln["words"] and not ln.get("unsung")), default=0)
    scenes = []
    for k, sc in enumerate(_read_scenes(pid)):
        lines = list(dict.fromkeys(map_entry_id(line_map[i]) for i in sc["lines"] if i < len(line_map) and line_map[i]))
        start = {"kind": "auto"}
        if sc["id"] in word_starts and line_map[word_starts[sc["id"]][0]]:
            li, off = word_starts[sc["id"]]
            ent = line_map[li]
            lid = map_entry_id(ent)
            wlast = ent["to"] if isinstance(ent, dict) else len(byid[lid]["words"]) - 1
            start = {"kind": "word", "line": lid, "word": wlast, "edge": "end", "offset": round(off + lead, 3)}
        elif sc["start"] is not None:
            t = float(sc["start"])
            start = {"kind": "time", "t": round(t, 3)} if t < first_sung or not lines else {"kind": "auto"}
        elif not lines:
            start = {"kind": "time", "t": 0}
        scenes.append({"id": f"s{k + 1}", "name": sc["id"], "legacy": sc["id"], "start": start, "lines": lines, "theme": sc.get("theme"), "three": sc.get("three")})
    p = store.load(pid)
    p["scenes"] = scenes
    p["legacy"]["scenes"] = [{"id": sc["name"], "three": sc.get("three"), "theme": sc.get("theme")} for sc in scenes]
    store.save(pid, p)
    print(f"imported {old.name} into {pid}: {len(scenes)} original scenes, {sum(1 for x in line_map if x)}/{len(line_map)} lines mapped, held: {[h['name'] for h in held]}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["import", "build"])
    ap.add_argument("pid")
    ap.add_argument("old", nargs="?")
    a = ap.parse_args()
    if a.cmd == "build":
        print(build(a.pid))
    else:
        import_legacy(a.pid, Path(a.old))


if __name__ == "__main__":
    sys.exit(main())
