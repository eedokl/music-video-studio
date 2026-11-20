# /// script
# requires-python = ">=3.12"
# dependencies = []
# [tool.uv]
# exclude-newer = "2026-11-14T00:00:00Z"
# ///
"""Preflight of the AI workflows: does the running ComfyUI have every node class, model file and option value the
planned jobs need? Asks ComfyUI's GET /object_info once (read-only, seconds) and compares it with assets/models.json
(+ the machine override, config `comfy_models` - see comfy_models.py). night_run.py runs it before the first job.

    uv run preflight.py jobs.json                  # the workflows the jobs of a night-run file need
    uv run preflight.py --kinds flux,ltx,s2v       # job kinds, night-run phases or workflow names of models.json
    uv run preflight.py --all                      # every workflow of models.json
    uv run preflight.py --list                     # workflows, their model files and folders (no ComfyUI needed)
    options: --url http://host:8188 (default config comfy_url), --object-info saved.json (check a saved dump instead)
Prints exactly what is missing - node class (+ which node pack provides it), model file (+ loader and models/ folder),
option value - and exits 1; 0 when everything is present; 2 when ComfyUI does not answer or the arguments are wrong.
From Python: preflight.check(names, preflight.fetch_object_info()) -> [problem dicts], preflight.lines(problems).
"""
import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

import _studio  # noqa: E402
_studio.use()
import comfy_models  # noqa: E402
import config  # noqa: E402

KIND_DEFAULT = {"qwen_edit": "qwen_edit", "ltx_lipsync": "ltx23", "ltx_moving": "ltx23", "ltx": "ltx23",
                "s2v": "s2v", "infinitetalk": "infinitetalk", "humo": "humo1.7B", "minimax_h3": "minimax_h3",
                "ltx25_multishot": "ltx25", "ltx25": "ltx25", "wan": "wan", "flux": "flux", "depth": None}       # job kinds and night-run phases -> workflow
FLUX_MODEL = {"flux": "flux", "sdxl": "sdxl", "qwen": "qwen_image"}


def workflows_for_job(job):
    """Workflow names (models.json) one night-run job needs ([] for jobs without ComfyUI, e.g. depth)."""
    k, a = job["kind"], job.get("args") or {}
    if k == "flux":
        return [FLUX_MODEL.get(a.get("model", "flux"), "flux")]
    if k == "s2v" and a.get("light"):
        return ["s2v_light"]
    if k == "humo":
        return [f"humo{a.get('size', '1.7B')}"]
    if k not in KIND_DEFAULT:
        raise ValueError(f"unknown job kind {k}")
    return [KIND_DEFAULT[k]] if KIND_DEFAULT[k] else []


def workflows_for_jobs(jobs):
    out = []
    for j in jobs:
        out += [w for w in workflows_for_job(j) if w not in out]
    return out


def resolve(names):
    """Job kinds / phases / workflow names -> workflow names (ValueError on unknown names)."""
    wfs = comfy_models.load()["workflows"]
    out = []
    for n in names:
        w = n if n in wfs else KIND_DEFAULT.get(n, "?")
        if w == "?":
            raise ValueError(f"unknown kind / workflow '{n}' - known: {', '.join(sorted(set(wfs) | set(KIND_DEFAULT)))}")
        if w and w not in out:
            out.append(w)
    return out


def url():
    return config.comfy_url().rstrip("/")


def fetch_object_info(base=None, timeout=60):
    """GET /object_info of the running ComfyUI (read-only). ConnectionError when it does not answer."""
    base = (base or url()).rstrip("/")
    try:
        with urllib.request.urlopen(base + "/object_info", timeout=timeout) as r:
            return json.loads(r.read())
    except (urllib.error.URLError, OSError, ValueError) as ex:
        raise ConnectionError(f"ComfyUI does not answer at {base} ({ex})") from None


def options(info, cls, inp):
    """Allowed values of a combo input (old format [[...], {...}] and new ["COMBO", {"options": [...]}]) or None."""
    spec = info.get(cls, {}).get("input", {})
    s = (spec.get("required") or {}).get(inp) or (spec.get("optional") or {}).get(inp)
    if not s:
        return None
    if isinstance(s[0], list):
        return s[0]
    if s[0] == "COMBO" and len(s) > 1 and isinstance(s[1], dict):
        return s[1].get("options") or []
    return None


def _norm(name):
    return str(name).replace("\\", "/")


def node_hint(cls):
    d = comfy_models.load()
    mod = d.get("nodes", {}).get(cls)
    tested = d.get("tested_with", "the reference ComfyUI")
    if mod is None:
        return "node pack unknown - search the class name in ComfyUI-Manager"
    if mod == "nodes" or mod.startswith("comfy_extras."):
        return f"core ComfyUI node ({mod}) - update ComfyUI (models.json was checked with {tested})"
    if mod.startswith("custom_nodes."):
        return f"custom node pack '{mod.split('.', 1)[1]}' - install it (ComfyUI-Manager) and restart ComfyUI"
    return f"provided by {mod}"


def check(names, info):
    """Problems of the given workflows against an object_info dict: [{"type": "node"|"file"|"value", ...}], deduplicated;
    each problem lists the workflows that need it in "for"."""
    d = comfy_models.load()
    probs = {}

    def add(key, p, wf):
        probs.setdefault(key, dict(p, **{"for": []}))["for"].append(wf)

    for wf in names:
        w = d["workflows"][wf]
        missing_nodes = set()
        for cls in w.get("nodes", []):
            if cls not in info:
                missing_nodes.add(cls)
                add(("node", cls), {"type": "node", "class": cls, "hint": node_hint(cls)}, wf)
        for role in w.get("files", []):
            f = d["files"][role]
            for li in f.get("loaders", []):
                cls, inp = li.split(".", 1)
                if cls not in w.get("nodes", []) or cls in missing_nodes:
                    continue                     # loader not used here / already reported as missing
                opts = options(info, cls, inp)
                have = {_norm(o) for o in opts or []}
                if _norm(f["file"]) in have:
                    continue
                base = _norm(f["file"]).rsplit("/", 1)[-1]
                near = sorted(o for o in have if o.rsplit("/", 1)[-1] == base)
                add(("file", role, li), {"type": "file", "role": role, "file": f["file"], "folder": f.get("folder", "?"),
                                         "loader": li, "what": f.get("what", ""), "found_as": near,
                                         "input_unknown": opts is None}, wf)
        for li, vals in (w.get("values") or {}).items():
            cls, inp = li.split(".", 1)
            if cls in missing_nodes:
                continue
            opts = options(info, cls, inp)
            for v in vals if isinstance(vals, list) else [vals]:
                if opts is not None and v not in opts:
                    add(("value", li, v), {"type": "value", "input": li, "value": v}, wf)
    return list(probs.values())


def lines(probs):
    """One readable line per problem."""
    out = []
    for p in probs:
        for_ = ", ".join(p["for"])
        if p["type"] == "node":
            out.append(f"MISSING node class  {p['class']}  (needed by {for_}) - {p['hint']}")
        elif p["type"] == "file":
            fix = (f"ComfyUI lists it as {' / '.join(p['found_as'])} - set that name for role '{p['role']}' in the "
                   f"comfy_models override" if p["found_as"] else
                   f"put it into ComfyUI's models/{p['folder']}/ folder, or name your own file for role '{p['role']}' "
                   f"in the comfy_models override")
            if p["input_unknown"]:
                fix = f"this ComfyUI's {p['loader']} has no such input - update ComfyUI"
            out.append(f"MISSING model file  {p['file']}  ({p['what']}; role {p['role']}, loader {p['loader']}, "
                       f"needed by {for_}) - {fix}")
        else:
            out.append(f"MISSING option  {p['input']} = {p['value']!r}  (needed by {for_}) - this ComfyUI does not offer "
                       f"it; update ComfyUI")
    return out


def summary(names, info, probs):
    d = comfy_models.load()
    nodes = {c for n in names for c in d["workflows"][n].get("nodes", [])}
    files = {r for n in names for r in d["workflows"][n].get("files", [])}
    if probs:
        return (f"preflight FAILED: {len(probs)} problem(s) for {', '.join(names)} "
                f"({len(nodes)} node classes, {len(files)} model files checked)")
    return f"preflight OK: {', '.join(names)} - {len(nodes)} node classes, {len(files)} model files present"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("jobs", nargs="?", help="night-run jobs.json")
    ap.add_argument("--kinds", default="", help="comma list: job kinds, phases or workflow names")
    ap.add_argument("--all", action="store_true", help="every workflow in models.json")
    ap.add_argument("--list", action="store_true", help="print the workflows and model files, no check")
    ap.add_argument("--url", default=None, help="ComfyUI URL (default: config comfy_url)")
    ap.add_argument("--object-info", default=None, help="check a saved /object_info JSON instead of asking ComfyUI")
    a = ap.parse_args()
    d = comfy_models.load()
    if a.list:
        print(f"models.json{' + override ' + d['override'] if d.get('override') else ''}")
        for n, w in d["workflows"].items():
            print(f"\n{n}  ({w.get('used_by', '')})")
            for r in w.get("files", []):
                f = d["files"][r]
                print(f"  {r:24s} models/{f.get('folder', '?')}/{f['file']}")
        return 0
    try:
        if a.all:
            names = list(d["workflows"])
        elif a.jobs:
            names = workflows_for_jobs(json.loads(Path(a.jobs).read_text(encoding="utf-8")).get("jobs", []))
        else:
            names = resolve([k.strip() for k in a.kinds.split(",") if k.strip()])
    except (ValueError, OSError, KeyError) as ex:
        print(f"preflight: {ex}")
        return 2
    if not names:
        print("preflight: no ComfyUI workflow to check (give jobs.json, --kinds or --all)")
        return 0 if (a.jobs or a.kinds) else 2
    try:
        info = (json.loads(Path(a.object_info).read_text(encoding="utf-8")) if a.object_info
                else fetch_object_info(a.url))
    except ConnectionError as ex:
        print(f"preflight: {ex} - start ComfyUI first")
        return 2
    probs = check(names, info)
    for line in lines(probs):
        print(line)
    print(summary(names, info, probs) + ("" if a.object_info else f" (ComfyUI {(a.url or url()).rstrip('/')})"))
    return 1 if probs else 0


if __name__ == "__main__":
    sys.exit(main())
