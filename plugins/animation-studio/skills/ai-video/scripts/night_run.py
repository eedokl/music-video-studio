# /// script
# requires-python = ">=3.12"
# dependencies = ["numpy==2.5.4"]
# ///
"""Night run: compute a whole list of AI jobs unattended - one model at a time, resumable, with milestones.

jobs.json (written by a user skill, e.g. claudia-music-video jobs.py; paths relative to the jobs file):
  {"phases": ["flux", "qwen_edit", "depth", "ltx", "s2v", "infinitetalk", "humo", "minimax_h3", "wan"],          # order: each phase = ONE model
   "selection": "selection.json",                                          # picks between phases (see "pick")
   "hooks": {"after:qwen_edit": ["uv", "run", "${CLAUDE_PLUGIN_ROOT}/skills/<skill>/scripts/pick.py", "start", "."]},
                                     # commands run after a phase (cwd = jobs dir; ${CLAUDE_PLUGIN_ROOT} = this plugin)
   "jobs": [{"id": "s02/start_v1", "kind": "qwen_edit", "out": "ai/start/s02_v1.png",
             "args": {"refs": ["ref1.png", "ref2.png"], "prompt": "...", "neg": "...", "seed": 1}},
            {"id": "s02/ltx_s1", "kind": "ltx_lipsync", "out": "ai/lipsync/s02_{img}_s1.mp4",
             "args": {"image": {"pick": "start", "key": "s02", "candidates": ["ai/start/s02_v1.png"]},
                      "audio": {"src": "analysis/vocals_lead.wav", "from": 9.48, "dur": 4.3},
                      "prompt": "...", "frames": 97, "seed": 41, "strength": 1.0,
                      "meta": {"song_start": 9.48, "lead_in": 0.25, "shot": "s02"}}}]}
Kinds: flux (comfy_image), qwen_edit, depth (estimate_depth, one subprocess for the phase), ltx_lipsync, ltx_moving,
s2v, infinitetalk, humo, minimax_h3 (local MiniMax H3), wan (comfy_video).  An image argument may be {"pick": group, "key": shot, "candidates": [...]}: the chosen file
from selection.json["manual"][group][key] (hand choice), else selection.json[group][key], else the first existing
candidate. "{img}" in "out" becomes the chosen image's
variant tag (last "_" part of its name), so a new choice makes new clips instead of overwriting the old ones.
Rules:
  - resumable: existing outputs are skipped - after a crash or a stop just start again. Every output is written under
    a temporary name (<name>.part.<ext> + its .json) and renamed when complete, so a killed job is redone, not skipped
  - per phase: wait for the shared GPU lock, flush ComfyUI, compute all jobs, release the lock (a lock that stays
    taken too long skips the phase with a message; the run goes on with the next phase)
  - hooks run after their phase also when the phase had nothing to do (a hand pick may have changed)
  - disk: before the run and before every phase at least --min-free-gb (default 20) must be free on the project's
    drive (and on ComfyUI's, config comfy_dir); otherwise the run stops with a message. --clean-comfy deletes the
    files THIS run created in ComfyUI's input/output folders after each job (needs config comfy_dir)
  - a failing job is logged (milestones.log + traceback) and retried ONCE after flushing ComfyUI; then the run goes on
  - ComfyUI is started with config comfy_start if it is not running; if it does not answer for 15 min the phase is skipped
Audio args: "quiet_start": true moves the window start back into a silence (<= 0.5 s, lead-in grows),
"prepare": true levels the vocal (clips.prepare_vocal). LTX args: "compression" (img_compression, crowds 42).
Usage:
  uv run night_run.py jobs.json [--phases ltx,s2v] [--only s02,s05] [--dry-run] [--status]
         [--min-free-gb 20] [--clean-comfy]
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import traceback
from pathlib import Path

import _studio  # noqa: E402
_studio.use()
import clips  # noqa: E402
import comfy  # noqa: E402

PLUGIN_ROOT = Path(__file__).resolve().parents[3]       # <plugin>/skills/ai-video/scripts/night_run.py (at run time)
MODEL = {"flux": "comfy:flux", "qwen_edit": "comfy:qwen_edit", "depth": "depth:small", "ltx": "comfy:ltx23",
         "s2v": "comfy:wan_s2v", "infinitetalk": "comfy:infinitetalk", "humo": "comfy:humo1.7B", "minimax_h3": "comfy:minimax_h3",
         "wan": "comfy:wan"}
PHASE_OF = {"flux": "flux", "qwen_edit": "qwen_edit", "depth": "depth", "ltx_lipsync": "ltx", "ltx_moving": "ltx",
            "s2v": "s2v", "infinitetalk": "infinitetalk", "humo": "humo", "minimax_h3": "minimax_h3", "wan": "wan"}
LOAD = {"flux": 150, "qwen_edit": 540, "depth": 60, "ltx": 420, "s2v": 360, "infinitetalk": 300, "humo": 300, "minimax_h3": 600,
        "wan": 600}   # s cold model load (measured)


def estimate(job):
    a, k = job.get("args", {}), job["kind"]
    if k.startswith("ltx"):
        return 150 * a.get("frames", 97) / 97
    if k == "s2v":
        return 846 * a.get("frames", 61) / 61
    if k == "infinitetalk":
        return 80 * a.get("frames", 97) / 25
    if k == "humo":
        return 130 * a.get("frames", 97) / 25
    if k == "minimax_h3":
        return 42 * a.get("frames", 124) / 24
    if k == "wan":
        return 100 * a.get("seconds", 4)
    return {"flux": 9, "qwen_edit": 30, "depth": 2}.get(k, 60)


class Run:
    def __init__(self, jobs_file):
        self.file = Path(jobs_file).resolve()
        self.dir = self.file.parent
        self.d = json.loads(self.file.read_text(encoding="utf-8"))
        self.log_file = self.dir / "milestones.log"
        self._warned = set()
        self.min_free_gb = 20.0
        self.clean_comfy = False

    def disk_ok(self, what):
        """Enough free space on the project drive (and ComfyUI's, if comfy_dir is configured)? Logs when not."""
        for label, folder in (("project", self.dir), ("ComfyUI", comfy.comfy_dir())):
            if folder is None or not self.min_free_gb:
                continue
            free = shutil.disk_usage(folder).free / 1e9
            if free < self.min_free_gb:
                self.log(f"ERROR {what}: only {free:.1f} GB free on the {label} drive ({Path(folder).anchor or folder}), "
                         f"need {self.min_free_gb:g} GB - free some space (ComfyUI output/input folders, old renders) "
                         f"or lower --min-free-gb; run stopped")
                return False
        return True

    def p(self, rel):
        q = Path(rel)
        return q if q.is_absolute() else self.dir / q

    def selection(self):
        f = self.p(self.d.get("selection", "selection.json"))
        try:
            return json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def resolve_image(self, spec):
        """-> (path or None, tag)"""
        if isinstance(spec, str):
            q = self.p(spec)
            return q, q.stem.split("_")[-1]
        sel = self.selection()
        man = ((sel.get("manual") or {}).get(spec["pick"]) or {}).get(spec["key"])
        if isinstance(man, dict):
            man = man.get("file")
        if man and not self.p(man).exists() and (spec["pick"], spec["key"]) not in self._warned:
            self._warned.add((spec["pick"], spec["key"]))
            self.log(f"WARNING manual {spec['pick']} {spec['key']}: {man} does not exist - using the automatic pick")
        auto = (sel.get(spec["pick"]) or {}).get(spec["key"])
        cands = [c for c in (man, auto) if c] + list(spec.get("candidates", []))
        for c in cands:
            q = self.p(c)
            if q.exists():
                return q, q.stem.split("_")[-1]
        return None, "?"

    def out_of(self, job):
        out = job["out"]
        img = (job.get("args") or {}).get("image")
        if "{img}" in out:
            _, tag = self.resolve_image(img) if img else (None, "x")
            out = out.replace("{img}", tag)
        return self.p(out)

    def log(self, msg):
        line = f"{time.strftime('%Y-%m-%d %H:%M:%S')}  {msg}"
        print(line, flush=True)
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(line + "\n")

    # ------------------------------------------------------------- one job
    def execute(self, job, out, final=None):
        """Render job into `out` (a temporary name); `final` = the real output (names the cut audio)."""
        final = final or out
        a = dict(job.get("args") or {})
        k = job["kind"]
        img = None
        if "image" in a:
            img, _ = self.resolve_image(a["image"])
            if img is None:
                raise FileNotFoundError(f"start image missing for {job['id']}")
        if k == "flux":
            from comfy_image import generate
            generate(a["prompt"], out, a.get("w", 1280), a.get("h", 720), a.get("seed", 1), a.get("steps"),
                     a.get("model", "flux"), a.get("neg"))
        elif k == "qwen_edit":
            import qwen_edit
            qwen_edit.edit([self.p(r) for r in a["refs"]], a["prompt"], out, a.get("w", 1280), a.get("h", 720),
                           a.get("seed", 1), a.get("neg", qwen_edit.NEG))
        elif k in ("ltx_lipsync", "ltx_moving", "s2v", "infinitetalk", "humo", "minimax_h3"):
            au = dict(a["audio"])
            meta = dict(a.get("meta") or {})
            if au.get("quiet_start"):            # begin the vocal window in a silence (move back <= 0.5 s)
                q = clips.quiet_start(self.p(au["src"]), au["from"])
                if k.startswith("ltx"):          # LTX: never beyond LTX_MAX_FRAMES (RAM)
                    room = (clips.LTX_MAX_FRAMES - a.get("frames", 97)) // 8 * 8 / 24
                    q = max(q, au["from"] - room)
                if q < au["from"] - 0.01:
                    shift = au["from"] - q
                    au["from"], au["dur"] = q, au["dur"] + shift
                    meta["song_start"] = q
                    meta["lead_in"] = round(meta.get("lead_in", 0) + shift, 3)
                    step = 4 if k in ("infinitetalk", "humo", "minimax_h3") else 8   # frames still cover the window
                    fps = 25 if k in ("infinitetalk", "humo") else 24
                    a["frames"] = a.get("frames", 97) + int(-(-shift * fps // step)) * step
            wav = clips.cut_audio(self.p(au["src"]), au["from"], au["dur"], final.parent / "audio" / f"{final.stem}.wav")
            if au.get("prepare"):                # -16 dBFS sung RMS, peaks <= -1 dBFS, 15 ms ramps
                meta["vocal_rms_before_db"] = clips.prepare_vocal(wav)
            meta.setdefault("song_start", au["from"])
            meta["audio"] = str(wav)
            if k == "infinitetalk":
                import infinitetalk
                infinitetalk.render(img, wav, a["prompt"], out, a.get("frames", 97), a.get("seed", 31), meta)
            elif k == "humo":
                import humo
                humo.render(img, wav, a["prompt"], out, a.get("frames", 97), a.get("seed", 31), a.get("size", "1.7B"),
                            a.get("steps"), a.get("neg", humo.NEG), meta)
            elif k == "minimax_h3":
                import minimax
                minimax.render(img, wav, a["prompt"], out, a.get("frames", minimax.MIN_FRAMES), a.get("seed", 31), meta=meta)
            elif k == "s2v":
                import s2v
                s2v.render(img, wav, a["prompt"], out, a.get("frames", 61), a.get("steps", 20), a.get("seed", 31),
                           a.get("light", False), a.get("neg", s2v.NEG), meta)
            else:
                import ltx
                ltx.render("lipsync" if k == "ltx_lipsync" else "moving", img, wav, a["prompt"], out,
                           a.get("frames", 97), a.get("seed", 31), a.get("strength", 1.0), a.get("neg"), meta,
                           compression=a.get("compression", 18))
        elif k == "wan":
            import comfy_video
            comfy_video.image_to_video("wan", img, a["prompt"], out, a.get("seconds", 4), seed=a.get("seed", 1),
                                       neg=a.get("neg", comfy_video.NEG))
            if a.get("meta"):
                clips.write_meta(out, kind="wan", fps=24, delay_frames=0, image=str(img), **a["meta"])
        else:
            raise ValueError(f"unknown job kind {k}")

    # ------------------------------------------------------------- phases
    def depth_phase(self, todo):
        import estimate_depth
        tmp = self.dir / "ai" / "_depth_tmp"
        pairs = []
        for job, out in todo:
            img, _ = self.resolve_image(job["args"]["image"])
            if img is not None:
                pairs.append((img, out))
        if not pairs:
            return
        t0 = time.time()
        try:
            estimate_depth.run([i for i, _ in pairs], out_dir=tmp)
        except subprocess.CalledProcessError as ex:
            self.log(f"depth ERROR {ex}")
        ok = 0
        for img, out in pairs:
            src = tmp / f"{img.stem}_depth.png"
            if src.exists():
                out.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(src), str(out))
                ok += 1
        shutil.rmtree(tmp, ignore_errors=True)
        self.log(f"depth OK {ok}/{len(pairs)} maps in {time.time() - t0:.0f} s")

    def phase(self, ph, jobs, dry):
        todo = [(j, self.out_of(j)) for j in jobs]
        open_ = [(j, o) for j, o in todo if not o.exists()]
        est = (LOAD.get(ph, 120) if open_ else 0) + sum(estimate(j) for j, _ in open_)
        if dry:
            print(f"\n=== {ph}: {len(todo)} jobs, {len(todo) - len(open_)} done, {len(open_)} open, ~{fmt(est)}")
            for j, o in todo:
                st = "done" if o.exists() else "open"
                print(f"  {j['id']:28s} ~{estimate(j):5.0f}s  {st:5s} {o.relative_to(self.dir) if o.is_relative_to(self.dir) else o}")
            return est
        if not open_:
            self.log(f"phase {ph}: nothing to do ({len(todo)} done)")
            self.hook(ph)
            return 0
        if not self.disk_ok(f"phase {ph}"):
            raise DiskFull
        self.log(f"phase {ph}: {len(open_)} jobs, estimate {fmt(est)}")
        t_ph = time.time()
        if ph == "depth":
            self.depth_phase(open_)
        else:
            try:
                comfy.ensure(900)
            except SystemExit as ex:
                self.log(f"phase {ph}: ERROR ComfyUI not available ({ex}) - phase skipped")
                return 0
            try:
                comfy.lock(f"night_run_{ph}", MODEL[ph])
            except (SystemExit, Exception) as ex:     # lock timeout (SystemExit or an exception class): skip the phase
                self.log(f"phase {ph}: ERROR GPU lock not free ({type(ex).__name__}: {ex}) - phase skipped")
                return 0
            comfy.free()                     # always fresh: ComfyUI keeps leftovers of earlier jobs otherwise
            for j, out in open_:
                out = self.out_of(j)         # a pick may have changed meanwhile
                if out.exists():
                    continue
                out.parent.mkdir(parents=True, exist_ok=True)
                part = out.with_name(out.stem + ".part" + out.suffix)
                for attempt in (1, 2):
                    t0 = time.time()
                    try:
                        for f in (part, clips.meta_path(part)):
                            f.unlink(missing_ok=True)
                        self.execute(j, part, out)
                        if clips.meta_path(part).exists():                 # meta first, the clip last:
                            os.replace(clips.meta_path(part), clips.meta_path(out))
                        os.replace(part, out)                              # "out exists" = complete
                        self.log(f"{ph} OK     {j['id']}  {time.time() - t0:6.1f}s -> {out.relative_to(self.dir)}")
                        break
                    except BaseException as ex:          # SystemExit from tools as well
                        if isinstance(ex, KeyboardInterrupt):
                            raise
                        self.log(f"{ph} ERROR  {j['id']} (attempt {attempt}) {type(ex).__name__}: {comfy.short_error(ex)}")
                        with open(self.log_file, "a", encoding="utf-8") as f:
                            f.write(traceback.format_exc()[-1500:] + "\n")
                        if attempt == 2 or isinstance(ex, (FileNotFoundError, ValueError)):
                            break
                        try:
                            comfy.ensure(600)
                        except SystemExit:
                            self.log(f"{ph}: ComfyUI stopped answering - phase aborted")
                            self.clean()
                            comfy.unlock()
                            return 0
                        comfy.free()
                self.clean()
            comfy.unlock()
        self.log(f"phase {ph} finished in {fmt(time.time() - t_ph)}")
        self.hook(ph)
        return 0

    def clean(self):
        """--clean-comfy: delete the ComfyUI input/output files this run created (never anything else)."""
        if self.clean_comfy:
            n, b = comfy.clean_produced()
            if n:
                print(f"[night_run] ComfyUI: {n} files of this run deleted ({b / 1e6:.0f} MB)", flush=True)

    def hook(self, ph):
        hook = (self.d.get("hooks") or {}).get(f"after:{ph}")
        if hook:
            hook = [str(x).replace("${CLAUDE_PLUGIN_ROOT}", PLUGIN_ROOT.as_posix()) for x in hook]
            self.log(f"hook after {ph}: {' '.join(map(str, hook))[-160:]}")
            r = subprocess.run(hook, cwd=self.dir)
            if r.returncode:
                self.log(f"hook after {ph} returned {r.returncode}")


class DiskFull(Exception):
    pass


def fmt(s):
    return f"{int(s // 3600)}:{int(s % 3600 // 60):02d}:{int(s % 60):02d}"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("jobs")
    ap.add_argument("--phases", default="", help="e.g. ltx,s2v (default: all in the file's order)")
    ap.add_argument("--only", default="", help="job ids starting with these prefixes, e.g. s02,s05")
    ap.add_argument("--dry-run", action="store_true", help="list the jobs and a time estimate")
    ap.add_argument("--status", action="store_true", help="done/open per phase")
    ap.add_argument("--min-free-gb", type=float, default=20.0,
                    help="stop before a phase when less is free on the project / ComfyUI drive (0 = no check)")
    ap.add_argument("--clean-comfy", action="store_true",
                    help="delete the files this run created in ComfyUI's input/output folders (config comfy_dir)")
    a = ap.parse_args()
    R = Run(a.jobs)
    R.min_free_gb, R.clean_comfy = a.min_free_gb, a.clean_comfy
    if a.clean_comfy and comfy.comfy_dir() is None and not (a.dry_run or a.status):
        print("[night_run] --clean-comfy needs ComfyUI's base folder (holding input/ and output/): "
              "check_tools.py --set comfy_dir=<folder> or environment variable COMFY_DIR - nothing will be deleted",
              flush=True)
    order = R.d.get("phases") or list(MODEL)
    want = [p for p in a.phases.split(",") if p] or order
    only = [x for x in a.only.split(",") if x]
    jobs = [j for j in R.d["jobs"] if not only or any(j["id"].startswith(o) for o in only)]
    by = {}
    for j in jobs:
        by.setdefault(PHASE_OF[j["kind"]], []).append(j)
    if a.status:
        for ph in order:
            js = by.get(ph, [])
            done = sum(R.out_of(j).exists() for j in js)
            print(f"{ph:10s} {done}/{len(js)} done")
        return
    if not a.dry_run:
        R.log(f"===== night run start: phases {','.join(p for p in order if p in want)}" + (f", only {only}" if only else ""))
    t0, total = time.time(), 0
    if not a.dry_run and not R.disk_ok("night run start"):
        return 1
    for ph in order:
        if ph in want and by.get(ph):
            try:
                total += R.phase(ph, by[ph], a.dry_run) or 0
            except DiskFull:
                break
    if a.dry_run:
        print(f"\nTotal estimate {fmt(total)} (phases one after another, plus waiting for other GPU jobs)")
    else:
        R.log(f"===== night run end after {fmt(time.time() - t0)}")


if __name__ == "__main__":
    sys.exit(main())
