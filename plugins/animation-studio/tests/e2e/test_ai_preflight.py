"""ai-video preflight against a fake ComfyUI (a tiny local http.server answering /object_info, /system_stats, /queue -
no real ComfyUI, no GPU, no POST is ever answered with success):
  - models.json matches the workflow builders (node classes + model files of every variant), the comfy_models override
    renames a file in the built workflow
  - preflight.py passes with everything present, lists a missing checkpoint (loader + models/ folder) and a missing
    node class (+ node pack hint) and exits 1, selects workflows from a jobs.json, follows the override, exits 2 when
    ComfyUI does not answer
  - night_run.py with a missing model stops before any job: exit 1, the message in milestones.log, no .part / output
    files, no POST to ComfyUI."""
import json
import os
import socket
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from common import SKILLS, Test, expect, read_json, script, write_json

AI = SKILLS / "ai-video"
PREFLIGHT = script("ai-video", "preflight.py")
NIGHT = script("ai-video", "night_run.py")
MODELS = AI / "assets" / "models.json"
LTX_FILE = "ltx-2.3-22b-distilled-fp8.safetensors"


# ------------------------------------------------------------------ fake ComfyUI
def object_info(models, drop_nodes=(), drop_files=(), rename=None):
    """/object_info as a ComfyUI with exactly the classes / files / values of models.json would answer.
    drop_files: (loader "Class.input", file) pairs left out; rename: {file: listed name}. Every other class uses the
    new combo format ["COMBO", {"options": [...]}], the rest the old [[...], {}] - preflight must read both."""
    combos = {}
    for f in models["files"].values():
        for li in f["loaders"]:
            if (li, f["file"]) not in drop_files:
                combos.setdefault(li, []).append((rename or {}).get(f["file"], f["file"]))
    for w in models["workflows"].values():
        for li, v in (w.get("values") or {}).items():
            for x in v if isinstance(v, list) else [v]:
                if x not in combos.setdefault(li, []):
                    combos[li].append(x)
    info = {}
    for k, cls in enumerate(sorted(models["nodes"])):
        if cls in drop_nodes:
            continue
        req = {}
        for li, opts in combos.items():
            c, inp = li.split(".", 1)
            if c == cls:
                req[inp] = ["COMBO", {"options": opts}] if k % 2 else [opts, {}]
        info[cls] = {"input": {"required": req}, "python_module": models["nodes"][cls], "name": cls}
    return info


class Fake:
    def __init__(self, info):
        self.info, self.requests = info, []
        fake = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _send(self, code, data):
                b = json.dumps(data).encode()
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(b)))
                self.end_headers()
                self.wfile.write(b)

            def do_GET(self):
                fake.requests.append(("GET", self.path))
                if self.path == "/object_info":
                    self._send(200, fake.info)
                elif self.path == "/system_stats":
                    self._send(200, {"system": {"comfyui_version": "fake"}, "devices": []})
                elif self.path == "/queue":
                    self._send(200, {"queue_running": [], "queue_pending": []})
                else:
                    self._send(404, {"error": "fake ComfyUI"})

            def do_POST(self):
                fake.requests.append(("POST", self.path))
                self._send(500, {"error": "fake ComfyUI runs no jobs"})

        self.srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.url = f"http://127.0.0.1:{self.srv.server_address[1]}"
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()

    def close(self):
        self.srv.shutdown()
        self.srv.server_close()


def env_for(ctx, url, override=None):
    """Machine config copy without comfy_start (a dead fake must never start the real ComfyUI) + the fake's URL."""
    try:
        cfg = json.loads(Path(os.environ["ANIMATION_STUDIO_CONFIG"]).read_text(encoding="utf-8"))
    except Exception:
        cfg = {}
    for k in ("comfy_start", "comfy_models", "comfy_dir", "comfy_url"):
        cfg.pop(k, None)
    p = ctx.dir / "config.json"
    write_json(p, cfg)
    env = {"ANIMATION_STUDIO_CONFIG": str(p), "ANIMATION_STUDIO_COMFY_URL": url, "ANIMATION_STUDIO_COMFY_START": "",
           "ANIMATION_STUDIO_COMFY_MODELS": str(override) if override else ""}
    return env


def missing_lines(out):
    return [l for l in out.splitlines() if "MISSING" in l]


# ------------------------------------------------------------------ builders vs models.json
BUILD = r'''
import json, sys
from pathlib import Path
scripts, out = sys.argv[1], sys.argv[2]
sys.path.insert(0, scripts)
import numpy as np
import comfy, comfy_image, comfy_video, ltx, s2v, infinitetalk, humo, minimax, qwen_edit, mic_repair
R = {
 "flux": [comfy_image.workflow("p", 1280, 720, 5)],
 "flux_repaint": [comfy_image.workflow("p", 1280, 720, 5, init="in.png", denoise=0.4)],
 "sdxl": [comfy_image.workflow("p", 1024, 1024, 6, model="sdxl")],
 "sdxl_lora_repaint": [comfy_image.workflow("p", 1024, 1024, 6, model="sdxl", lora="USER_LORA", init="i.png", denoise=0.5)],
 "qwen_image": [comfy_image.workflow("p", 1328, 1328, 7, model="qwen")],
 "qwen_edit": [qwen_edit.workflow(["a.png"], "p", 1280, 720, 1)],
 "qwen_edit_angles": [qwen_edit.workflow(["a.png", "b.png"], "p", 1280, 720, 1, lora=0.6)],
 "ltx23": [ltx.workflow("i.png", "a.wav", "p", ltx.NEG_LIPSYNC, 97, 31)],
 "ltxv": [comfy_video.wf_ltx("i.png", "p", "n", 1216, 704, 97, 3, 8)],
 "wan": [comfy_video.wf_wan("i.png", "p", "n", 1280, 704, 97, 3, 20)],
 "s2v": [s2v.workflow("i.png", "a.wav", "p", s2v.NEG, 61, 20, 6.0, 31, "x")],
 "s2v_light": [s2v.workflow("i.png", "a.wav", "p", s2v.NEG, 61, 4, 1.0, 31, "x", light=True)],
 "infinitetalk": [infinitetalk.workflow("i.png", "a.wav", "p", 61, 31, "x"), infinitetalk.workflow("i.png", "a.wav", "p", 320, 31, "x")],
 "humo1.7B": [humo.workflow("i.png", "a.wav", "p", 97, 31, "x")],
 "humo17B": [humo.workflow("i.png", "a.wav", "p", 97, 31, "x", "17B")],
 "minimax_h3": [minimax.workflow("i.png", "a.wav", "p", 124, 31, "x")],
}
posted = []                                   # mic_repair builds its graph inside _refine: capture what it would POST
comfy.ensure = comfy.lock = lambda *a, **k: None
comfy.upload = lambda p, name=None: name or Path(p).name
comfy.run = lambda wf, timeout=0: (posted.append(json.loads(json.dumps(wf))), {"outputs": {}})[1]
comfy.outputs = lambda h, *a, **k: [{}]
def fetch(item, dest):
    import cv2
    cv2.imwrite(str(dest), np.full((64, 64, 3), 128, np.uint8))
comfy.fetch = fetch
mask = np.zeros((200, 200), np.uint8)
mask[80:120, 90:130] = 1
mic_repair._refine(np.full((200, 200, 3), 100, np.uint8), mask, 11, n_seeds=1)
R["mic_repair"] = posted
Path(out).write_text(json.dumps(R), encoding="utf-8")
'''
EXT = (".safetensors", ".pt", ".pth", ".ckpt", ".gguf", ".bin")


def build(ctx, out, env=None):
    ctx.py(BUILD, deps_from=[script("ai-video", "mic_repair.py")], name="preflight_build.py",
           args=[AI / "scripts", out], env=env)
    return read_json(out)


def files_of(wfs):
    """{file name: {"Class.input", ...}} of every model-file input of the graphs."""
    out = {}
    for wf in wfs:
        for n in wf.values():
            for k, v in n["inputs"].items():
                if isinstance(v, str) and v.endswith(EXT):
                    out.setdefault(v, set()).add(f"{n['class_type']}.{k}")
    return out


def run_preflight(ctx):
    models = read_json(MODELS)

    # 1 builders vs models.json
    built = build(ctx, ctx.dir / "built.json")
    expect(set(built) == set(models["workflows"]), f"workflows: built {sorted(built)} vs models.json {sorted(models['workflows'])}")
    for name, wfs in built.items():
        w = models["workflows"][name]
        cls = sorted({n["class_type"] for wf in wfs for n in wf.values()})
        expect(cls == sorted(w["nodes"]), f"{name}: node classes differ from models.json:\n built  {cls}\n models {sorted(w['nodes'])}")
        want = {models["files"][r]["file"] for r in w["files"]}
        got = files_of(wfs)
        expect(set(got) == want, f"{name}: model files {sorted(got)} vs models.json {sorted(want)}")
        for r in w["files"]:
            f = models["files"][r]
            expect(got[f["file"]] <= set(f["loaders"]), f"{name}: {f['file']} loaded by {got[f['file']]}, models.json "
                                                        f"says {f['loaders']}")
    # override renames a file in the built graph, nothing else changes
    over = ctx.dir / "override.json"
    write_json(over, {"files": {"ltx23": "video/ltx23-renamed.safetensors"}})
    built2 = build(ctx, ctx.dir / "built_override.json", env={"ANIMATION_STUDIO_COMFY_MODELS": str(over)})
    f2 = files_of(built2["ltx23"])
    expect(set(f2) == {"video/ltx23-renamed.safetensors", models["files"]["gemma3_te"]["file"]} and
           len(f2["video/ltx23-renamed.safetensors"]) == 3, f"override not applied to all three LTX loaders: {f2}")
    expect({k: v for k, v in built2.items() if k != "ltx23"} == {k: v for k, v in built.items() if k != "ltx23"},
           "the ltx23 override changed other workflows")

    # 2 preflight against a fake ComfyUI
    fake = Fake(object_info(models))
    try:
        env = env_for(ctx, fake.url)
        r = ctx.uv(PREFLIGHT, "--all", env=env, check=False)
        expect(r.returncode == 0 and "preflight OK" in r.stdout and not missing_lines(r.stdout),
               f"all present: exit {r.returncode}\n{r.stdout[-800:]}")

        fake.info = object_info(models, drop_nodes={"WanSoundImageToVideo"},
                                drop_files={("CheckpointLoaderSimple.ckpt_name", LTX_FILE)})
        r = ctx.uv(PREFLIGHT, "--kinds", "flux,ltx,s2v,depth", env=env, check=False)
        miss = missing_lines(r.stdout)
        expect(r.returncode == 1, f"missing checkpoint + node: exit {r.returncode}, expected 1\n{r.stdout[-800:]}")
        expect(len(miss) == 2, f"expected exactly 2 MISSING lines, got:\n" + "\n".join(miss))
        ck = next((l for l in miss if LTX_FILE in l), "")
        expect("CheckpointLoaderSimple.ckpt_name" in ck and "models/checkpoints/" in ck and "ltx23" in ck,
               f"missing checkpoint line lacks loader / folder / workflow: {ck!r}")
        nd = next((l for l in miss if "WanSoundImageToVideo" in l), "")
        expect("node class" in nd and "needed by s2v" in nd and "core ComfyUI node" in nd,
               f"missing node line lacks the class / workflow / pack hint: {nd!r}")
        expect("preflight FAILED: 2 problem(s)" in r.stdout, f"no FAILED summary:\n{r.stdout[-500:]}")

        jobs = ctx.dir / "jobs.json"                     # workflows taken from a jobs file: flux + humo are complete
        write_json(jobs, {"jobs": [{"id": "a", "kind": "flux", "out": "a.png", "args": {"prompt": "x"}},
                                   {"id": "b", "kind": "humo", "out": "b.mp4", "args": {}},
                                   {"id": "c", "kind": "depth", "out": "c.png", "args": {}}]})
        r = ctx.uv(PREFLIGHT, jobs, env=env, check=False)
        expect(r.returncode == 0 and "flux, humo1.7B" in r.stdout, f"jobs.json (flux, humo): exit {r.returncode}\n{r.stdout[-500:]}")
        write_json(jobs, {"jobs": [{"id": "d", "kind": "s2v", "out": "d.mp4", "args": {"light": True}}]})
        r = ctx.uv(PREFLIGHT, jobs, env=env, check=False)
        expect(r.returncode == 1 and "needed by s2v_light" in r.stdout, f"jobs.json (s2v light): exit {r.returncode}\n{r.stdout[-500:]}")

        # the checkpoint sits in a sub-folder: the message names the listed name; the override makes it pass
        fake.info = object_info(models, rename={LTX_FILE: "video\\" + LTX_FILE})
        r = ctx.uv(PREFLIGHT, "--kinds", "ltx", env=env, check=False)
        expect(r.returncode == 1 and f"lists it as video/{LTX_FILE}" in r.stdout,
               f"sub-folder hint missing: exit {r.returncode}\n{r.stdout[-600:]}")
        write_json(over, {"files": {"ltx23": "video/" + LTX_FILE}})
        r = ctx.uv(PREFLIGHT, "--kinds", "ltx", env=env_for(ctx, fake.url, over), check=False)
        expect(r.returncode == 0 and "preflight OK" in r.stdout, f"override did not satisfy preflight:\n{r.stdout[-600:]}")
        expect(not any(m == "POST" for m, _ in fake.requests), f"preflight POSTed to ComfyUI: {fake.requests}")
    finally:
        fake.close()
    with socket.socket() as s:                           # a port nobody listens on
        s.bind(("127.0.0.1", 0))
        dead = f"http://127.0.0.1:{s.getsockname()[1]}"
    r = ctx.uv(PREFLIGHT, "--kinds", "flux", env=env_for(ctx, dead), check=False)
    expect(r.returncode == 2 and "does not answer" in r.stdout, f"dead ComfyUI: exit {r.returncode}\n{r.stdout[-400:]}")
    ctx.note(f"models.json = builders ({len(built)} workflows); all present OK; missing checkpoint + node class -> exit 1 "
             f"with loader/folder and pack hint; jobs.json selection; sub-folder hint + override; dead ComfyUI exit 2")


def run_night_stop(ctx):
    models = read_json(MODELS)
    d = ctx.dir / "proj"
    d.mkdir()
    write_json(d / "jobs.json", {"phases": ["flux", "ltx"], "jobs": [
        {"id": "s01/still", "kind": "flux", "out": "ai/start/s01_v1.png", "args": {"prompt": "a stage", "seed": 1}},
        {"id": "s01/ltx_s1", "kind": "ltx_lipsync", "out": "ai/lipsync/s01_s1.mp4",
         "args": {"image": "ai/start/s01_v1.png", "audio": {"src": "song.wav", "from": 0.0, "dur": 1.0},
                  "prompt": "she sings", "frames": 25, "seed": 41}}]})
    fake = Fake(object_info(models, drop_files={("CheckpointLoaderSimple.ckpt_name", LTX_FILE)}))
    try:
        r = ctx.uv(NIGHT, d / "jobs.json", "--min-free-gb", "0", env=env_for(ctx, fake.url), check=False, timeout=300)
        reqs = list(fake.requests)
    finally:
        fake.close()
    expect(r.returncode == 1, f"night_run with a missing model: exit {r.returncode}, expected 1\n{r.stdout[-800:]}")
    log = (d / "milestones.log").read_text(encoding="utf-8") if (d / "milestones.log").exists() else ""
    expect(f"MISSING model file  {LTX_FILE}" in log and "run stopped before any job" in log,
           f"milestones.log lacks the preflight message:\n{log[-800:]}")
    expect(" OK " not in log and "ERROR " not in log and "phase " not in log, f"a phase / job ran:\n{log[-800:]}")
    made = sorted(str(p.relative_to(d)) for p in d.rglob("*") if p.is_file() and p.name not in ("jobs.json", "milestones.log"))
    expect(not made, f"files were created although the run stopped before any job: {made}")
    expect(not any(m == "POST" for m, _ in reqs), f"night_run POSTed to ComfyUI: {reqs}")
    expect(("GET", "/object_info") in reqs, f"night_run never asked /object_info: {reqs}")
    ctx.note("night_run stopped before any job (exit 1, MISSING line + stop message in milestones.log, no files, no POST)")


TESTS = [
    Test("ai-preflight", run_preflight, about="ai-video models.json vs builders, override, preflight.py against a fake "
         "ComfyUI (all present / missing checkpoint + node class / jobs.json / dead server)"),
    Test("ai-preflight-night-run", run_night_stop, about="ai-video night_run.py stops before any job when preflight "
         "finds a missing model (fake ComfyUI)"),
]
