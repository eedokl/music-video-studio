# /// script
# requires-python = ">=3.12"
# dependencies = ["numpy==2.5.4"]
# [tool.uv]
# exclude-newer = "2026-11-14T00:00:00Z"
# ///
"""Turn the shot plan + creative brief into prompts and the night-run job list (ai-video night_run.py).

Per shot (project.json "sections"):
  lipsync         Qwen-Image-Edit start images (variants) -> canon pick -> LTX-2.3 lip-sync, several seeds
                  (strength 1.0 / 0.85 / 1.0 / 0.7); engine "s2v" = one Wan2.2-S2V clip + 1 LTX seed,
                  engine "infinitetalk" = one InfiniteTalk clip + 1 LTX seed (the measurement picks)
                  engine "humo" / "minimax" = one HuMo 1.7B / local MiniMax H3 clip + 1 LTX seed (rescue for
                  plosive-heavy lines where LTX measures weak; both rejected as default - static face / robotic body)
  broll           FLUX stills (variants) -> pick -> LTX-2.3 "moving still" on the instrumental (no singing)
  claudia_moving  Qwen start images -> canon pick -> LTX-2.3 moving on the instrumental (she acts, does not sing)
  typo            no AI job: NEWSFLASH / stamps / departure board / title drawn by render_shots (typo.py)
  placed          an existing clip with a singing mouth (e.g. an old Wan clip) re-placed by its mouth curve (pick.py)
  + a depth map of each picked still (fallback: still with depth parallax if a clip fails)
Vocal inputs (LTX, InfiniteTalk) start in a silence and are levelled (-16 dBFS, peaks <= -1 dBFS, ramps).
B-roll with "recipe": "crowd" uses the crowd recipe (img_compression 42, "A cinematic scene of ...").
Writes prompts.json (all prompts, for review) and jobs.json; stops if a prompt breaks a canon/LTX rule (claudia.check).
A shot may name its own "start_image" (no Qwen jobs; e.g. re-shooting an earlier film's shot) and
"s2v_seed"/"s2v_steps"/"s2v_seeds" (S2V takes, default 1) and "seed" (moving clip). A seed other than the default
goes into the file name (<shot>_<img>_sd<seed>.mp4), so a re-render with a new seed is a new take next to the old one
(takes.py shows both) instead of "done". --only replaces the jobs of those shots and keeps the others. Seeds come from the creative seed; "variants" in project.json: {"start": 2, "seeds": 2, "broll": 2} (CLI overrides).
Reference images of Claudia: project.json "character_refs": [face, close-up] or config `claudia_refs`
(paths separated by ";" or a folder). Instrumental for moving clips: stems.instrumental (e.g. a mix of the Suno
non-vocal stems), else Demucs no_vocals (song-analysis separate_vocals.py, cache/sep/), else the song (warning).
Usage: uv run jobs.py [<project>] [--start 2] [--seeds 2] [--broll 2] [--no-depth] [--only s02,s05]
Then:  uv run <ai-video>/scripts/night_run.py <project>/jobs.json [--dry-run]
"""
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

import _studio  # noqa: E402
_studio.use("song-analysis", "ai-video")
import claudia  # noqa: E402
import clips  # noqa: E402
import config  # noqa: E402
import creative  # noqa: E402
from song_project import Project  # noqa: E402

STRENGTHS = [1.0, 0.85, 1.0, 0.7]
MEDIAPIPE = ["uv", "run"]          # pick.py pins Python 3.12 + mediapipe in its own PEP 723 header


def character_refs(P):
    refs = P.get("character_refs") or []
    if not refs:
        v = config.get("claudia_refs") or ""
        if v and Path(v).is_dir():
            refs = sorted(str(p) for p in Path(v).glob("*.png"))
        else:
            refs = [x for x in v.replace(os.pathsep, ";").split(";") if x]
    refs = [str(P.path(r)) for r in refs]
    if not refs or not all(Path(r).exists() for r in refs):
        raise SystemExit("Claudia reference images missing: set project.json \"character_refs\": [face.png, closeup.png] "
                         "or config claudia_refs (check_tools.py --set claudia_refs=<folder or a.png;b.png>). The plugin "
                         "ships none: ask the user - two images (her face with mic and clip; a close-up with the one "
                         "streak and the clip) from claudia.gallery (download only with the user's OK) or stills of an "
                         "earlier Claudia film.")
    return refs


def instrumental(P):
    """Music without vocals for the moving clips (LTX would otherwise make people sing)."""
    st = P.get("stems") or {}
    if st.get("instrumental") and P.path(st["instrumental"]).exists():
        return P.path(st["instrumental"])
    dm = P.cache / "sep" / "htdemucs" / "song" / "no_vocals.wav"
    if not dm.exists():
        # mastered songs are not the plain sum of their stems (song - vocals keeps ~40 % residue): use Demucs
        sep = _studio.skill_dir("song-analysis") / "scripts" / "separate_vocals.py"
        py = config.get("gpu_python")
        run = [py] if py and Path(py).exists() else ["uv", "run", "--no-project", "--with", "demucs", "--with",
                                                     "soundfile", "python"]
        print("instrumental: Demucs no_vocals (GPU lock) ...", flush=True)
        r = subprocess.run(run + [str(sep), str(P.song), "-o", str(P.cache / "sep")])
        if r.returncode or not dm.exists():
            print("WARNING: no instrumental (Demucs failed) - moving clips get the full song", file=sys.stderr)
            return P.song
    return dm


def seed_tag(seed, default, P=None, folder=None, shot=None):
    """'' for the default seed (old file names stay), else '_sd<seed>' - a new seed must not overwrite / count as done.
    A clip of that seed rendered before 0.4.28 under the plain name (<shot>_<img>.mp4, meta "seed" the same) keeps its
    name: night_run finds it done instead of rendering the same seed again as a duplicate take."""
    if seed == default:
        return ""
    if P is not None:
        for f in sorted((P.dir / "ai" / folder).glob(f"{shot}_*.mp4")):
            if "_sd" in f.stem or ".part." in f.name or ".encoding." in f.name or not clips.meta_path(f).exists():
                continue
            if clips.read_meta(f).get("seed") == seed:
                return ""
    return f"_sd{seed}"


def merged(path, new, shots, key):
    """--only: the entries of the other shots stay (claudia3: jobs.py --only s01 left a jobs.json with s01 alone)."""
    if not shots or not path.exists():
        return new
    old = json.loads(path.read_text(encoding="utf-8"))
    if key is None:                                   # prompts.json: {shot: {...}}
        return dict(old, **new)
    keep = [j for j in old.get(key, []) if j.get("id", "").split("/")[0] not in shots]
    return dict(new, **{key: keep + new[key]})


def rel(P, p):
    p = Path(p)
    try:
        return p.resolve().relative_to(P.dir).as_posix()
    except ValueError:
        return str(p)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("project", nargs="?", default=".")
    ap.add_argument("--start", type=int, help="start-image variants per Claudia shot")
    ap.add_argument("--seeds", type=int, help="LTX seeds per lip-sync shot (1-4)")
    ap.add_argument("--broll", type=int, help="FLUX variants per B-roll shot")
    ap.add_argument("--no-depth", action="store_true")
    ap.add_argument("--only", default="")
    ap.add_argument("--ignore-checks", action="store_true")
    a = ap.parse_args()
    P = Project(a.project)
    var = dict(dict(start=2, seeds=2, broll=2), **(P.get("variants") or {}))
    nst, nseed, nbr = a.start or var["start"], min(4, a.seeds or var["seeds"]), a.broll or var["broll"]
    version = P.get("version", "studio")
    brief = P.get("brief") or {}
    wardrobe = brief.get("wardrobe") or creative.pick(P, "wardrobe", claudia.WARDROBE[version])
    only = [x for x in a.only.split(",") if x]
    refs = None
    vocals = P.analysis / "vocals_lead.wav"
    if not vocals.exists():
        raise SystemExit("analysis/vocals_lead.wav missing - run song-analysis analyze.py first")
    inst = None
    jobs, prompts, problems = [], {}, []

    def add(kind, jid, out, **args):
        jobs.append({"id": jid, "kind": kind, "out": out, "args": args})

    for s in P.sections():
        name, tech = s["name"], s["technique"]
        if only and name not in only:
            continue
        rng = creative.rng(P, f"seeds:{name}")
        base = rng.randrange(1000, 900000)
        dur = s["to"] - s["from"]
        look_img, look_vid = claudia.look(brief, s.get("look"), version)
        pr = prompts[name] = {"technique": tech}
        if tech in ("typo", "placed"):
            continue                                  # typo: drawn by render_shots; placed: an existing clip (pick.py)
        if tech in ("lipsync", "claudia_moving"):
            refs = refs or ([] if s.get("start_image") else character_refs(P))
            sp = claudia.start_image_prompt(s, wardrobe, look_img, version)
            pr["start_image"] = sp
            problems += [f"{name} start image: {e}" for e in claudia.check(sp, "image")]
            use_refs = refs[:1] if claudia.is_wide(s.get("framing")) else refs[:2]
            cands = []
            if s.get("start_image"):                 # a given start image (re-shoot of an earlier film's shot)
                cands = [rel(P, P.path(s["start_image"]))]
            for k in range(1, (0 if cands else nst) + 1):
                out = f"ai/start/{name}_v{k}.png"
                cands.append(out)
                add("qwen_edit", f"{name}/start_v{k}", out, refs=use_refs, prompt=sp, neg=claudia.NEG_IMAGE, seed=base + k)
            img = {"pick": "start", "key": name, "candidates": cands}
            if not a.no_depth:
                add("depth", f"{name}/depth", f"ai/depth/{name}_start_depth.png", image=img)
            if tech == "lipsync":
                frames, lead = clips.ltx_fit(dur)
                line = s.get("sing") or s.get("line")
                if s.get("timeline") and lead:
                    # the spans count from the shot start; the LTX clip starts `lead` s earlier (the first span also
                    # covers the lead-in)
                    s = dict(s, timeline=[[0 if float(t0) <= 0 else round(float(t0) + lead, 2),
                                           round(float(t1) + lead, 2), act] for t0, t1, act in s["timeline"]])
                lp = claudia.lipsync_prompt(s, wardrobe, look_vid, line)
                pr["lipsync"] = lp
                problems += [f"{name} lipsync: {e}" for e in claudia.check(lp, "lipsync")]
                # a "timeline" shot is mixed by default: odd seeds the plain prompt (A), even seeds the timeline (B);
                # "prompt_style": "timeline" | "plain" forces one style for all seeds
                mode = s.get("prompt_style", "mixed") if s.get("timeline") else "plain"
                lp_a = claudia.lipsync_prompt(s, wardrobe, look_vid, line, style="plain") if mode == "mixed" else lp
                if mode == "plain" and s.get("timeline"):
                    lp = lp_a = claudia.lipsync_prompt(s, wardrobe, look_vid, line, style="plain")
                if mode == "mixed":
                    pr["lipsync_plain"] = lp_a
                    problems += [f"{name} lipsync (plain): {e}" for e in claudia.check(lp_a, "lipsync")]
                n_ltx = nseed if s.get("engine", "ltx") == "ltx" else 1      # s2v/infinitetalk: + 1 LTX seed
                if s.get("engine", "ltx") != "ltx" and dur > 4.7:
                    n_ltx = 0                                 # longer than LTX can do in one clip (121 frames)
                # mixed: odd seeds A, even seeds B; with a single LTX seed B (a timeline shot is one where B won)
                plain_k = (lambda k: mode == "plain" or (mode == "mixed" and k % 2 == 1 and n_ltx > 1))
                for k in range(1, n_ltx + 1):
                    add("ltx_lipsync", f"{name}/ltx_s{k}", f"ai/lipsync/{name}_{{img}}_s{k}.mp4", image=img,
                        audio={"src": rel(P, vocals), "from": round(s["from"] - lead, 3), "dur": round(frames / 24 + 0.2, 3),
                               "quiet_start": True, "prepare": True},
                        prompt=lp_a if plain_k(k) else lp, neg=claudia.NEG_LIPSYNC, frames=frames,
                        seed=base + 100 + k,
                        strength=STRENGTHS[(k - 1) % 4],
                        meta={"song_start": round(s["from"] - lead, 3), "lead_in": lead, "shot": name,
                              # takes.py shows it: the user compares A / B by eye
                              **({"prompt_style": "plain" if plain_k(k) else "timeline"}
                                 if s.get("timeline") else {})})
                if s.get("engine") == "infinitetalk":
                    import infinitetalk
                    n, li = infinitetalk.frames_for(dur), infinitetalk.LEAD_IN
                    ip = claudia.s2v_prompt(s, look_vid)
                    pr["infinitetalk"] = ip
                    add("infinitetalk", f"{name}/infinitetalk", f"ai/infinitetalk/{name}_{{img}}.mp4", image=img,
                        audio={"src": rel(P, vocals), "from": round(s["from"] - li, 3), "dur": round(n / 25 + 0.2, 3),
                               "quiet_start": True, "prepare": True},
                        prompt=ip, frames=n, seed=s.get("s2v_seed", base + 250),
                        meta={"song_start": round(s["from"] - li, 3), "lead_in": li, "shot": name})
                if s.get("engine") in ("humo", "minimax"):  # rescue engines for plosive lines (+ 1 LTX seed)
                    import humo
                    import minimax
                    mod, kind, fps = (humo, "humo", 25) if s["engine"] == "humo" else (minimax, "minimax_h3", 24)
                    n, li = mod.frames_for(dur), 0.25
                    rp = claudia.s2v_prompt(s, look_vid)
                    pr[kind] = rp
                    problems += [f"{name} {kind}: {e}" for e in claudia.check(rp, "s2v")]
                    add(kind, f"{name}/{kind}", f"ai/{kind}/{name}_{{img}}.mp4", image=img,
                        audio={"src": rel(P, vocals), "from": round(s["from"] - li, 3), "dur": round(n / fps + 0.2, 3),
                               "quiet_start": True, "prepare": True},
                        prompt=rp, frames=n, seed=s.get("s2v_seed", base + 270),
                        meta={"song_start": round(s["from"] - li, 3), "lead_in": li, "shot": name})
                if s.get("engine") == "s2v":
                    n = clips.s2v_frames(dur)
                    sp2 = claudia.s2v_prompt(s, look_vid)
                    pr["s2v"] = sp2
                    seed0 = s.get("s2v_seed", base + 200)
                    for k in range(max(1, int(s.get("s2v_seeds", 1)))):
                        sd = seed0 + 17 * k
                        tg = seed_tag(sd, base + 200, P, "s2v", name)
                        add("s2v", f"{name}/s2v" + (f"_sd{sd}" if sd != base + 200 else ""),
                            f"ai/s2v/{name}_{{img}}{tg}.mp4", image=img,
                            audio={"src": rel(P, vocals), "from": s["from"], "dur": round(n / 16 + 0.2, 3)},
                            prompt=sp2, frames=n, steps=s.get("s2v_steps", 20), seed=sd,
                            meta={"song_start": s["from"], "shot": name})
            else:
                inst = inst or instrumental(P)
                frames, lead = clips.ltx_fit(dur)
                mp = claudia.moving_prompt((claudia.timeline_text(s["timeline"]) if s.get("timeline") else None)
                                           or s.get("motion") or s.get("action") or "She moves slowly, her hair moves slightly",
                                           s.get("camera", "slow push-in"), look_vid)
                pr["moving"] = mp
                problems += [f"{name} moving: {e}" for e in claudia.check(mp, "moving")]
                sd = s.get("seed", base + 300)
                add("ltx_moving", f"{name}/moving" + seed_tag(sd, base + 300),
                    f"ai/moving/{name}_{{img}}{seed_tag(sd, base + 300, P, 'moving', name)}.mp4",
                    image=img,
                    audio={"src": rel(P, inst), "from": round(s["from"] - lead, 3), "dur": round(frames / 24 + 0.2, 3)},
                    prompt=mp, neg=claudia.NEG_MOVING, frames=frames, seed=sd,
                    meta={"song_start": round(s["from"] - lead, 3), "lead_in": lead, "shot": name})
        else:   # broll
            if not s.get("subject") and not s.get("start_image"):
                problems.append(f"{name} broll: no 'subject' - the creative brief must say what we see")
            bp = claudia.broll_still_prompt(s.get("subject") or s.get("idea") or "an empty city street at dawn", look_img)
            pr["still"] = bp
            cands = [rel(P, P.path(s["start_image"]))] if s.get("start_image") else []
            for k in range(1, (0 if cands else nbr) + 1):
                out = f"ai/broll/{name}_v{k}.png"
                cands.append(out)
                add("flux", f"{name}/still_v{k}", out, prompt=bp, seed=base + k)
            img = {"pick": "broll", "key": name, "candidates": cands}
            if not a.no_depth:
                add("depth", f"{name}/depth", f"ai/depth/{name}_broll_depth.png", image=img)
            inst = inst or instrumental(P)
            frames, lead = clips.ltx_fit(dur)
            mp = claudia.moving_prompt(s.get("motion") or "Light shifts slowly, dust floats in the air",
                                       s.get("camera", "slow push-in"), look_vid)
            crowd = s.get("recipe") == "crowd"
            if crowd:                                 # crowd recipe: binds the start image less, the crowd moves
                import ltx
                mp = ltx.crowd_prompt(mp)
            pr["moving"] = mp
            problems += [f"{name} moving: {e}" for e in claudia.check(mp, "moving")]
            sd = s.get("seed", base + 300)
            add("ltx_moving", f"{name}/moving" + seed_tag(sd, base + 300),
                f"ai/moving/{name}_{{img}}{seed_tag(sd, base + 300, P, 'moving', name)}.mp4",
                image=img,
                audio={"src": rel(P, inst), "from": round(s["from"] - lead, 3), "dur": round(frames / 24 + 0.2, 3)},
                prompt=mp, neg=claudia.NEG_MOVING, frames=frames, seed=sd,
                compression=s.get("compression", 42 if crowd else 18),
                meta={"song_start": round(s["from"] - lead, 3), "lead_in": lead, "shot": name})
    prompts = merged(P.dir / "prompts.json", prompts, only, None)
    (P.dir / "prompts.json").write_text(json.dumps(prompts, ensure_ascii=False, indent=1), encoding="utf-8")
    if problems:
        print("Prompt problems:\n  " + "\n  ".join(problems))
        if not a.ignore_checks:
            raise SystemExit("fix the brief (or --ignore-checks) - jobs.json not written")
    # no absolute paths in jobs.json: night_run expands ${CLAUDE_PLUGIN_ROOT} at run time and runs hooks in the
    # project folder (the jobs file's folder), so the hook survives plugin updates and moved projects
    hook = MEDIAPIPE + ["${CLAUDE_PLUGIN_ROOT}/skills/claudia-music-video/scripts/pick.py", "auto", "."]
    d = {"phases": ["flux", "qwen_edit", "depth", "ltx", "s2v", "infinitetalk", "humo", "minimax_h3", "wan"], "selection": "selection.json",
         "hooks": {"after:flux": hook, "after:qwen_edit": hook + ["--repair-mic"]}, "jobs": jobs}
    n_new = len(jobs)
    d = merged(P.dir / "jobs.json", d, only, "jobs")
    jobs = d["jobs"]
    (P.dir / "jobs.json").write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    if only:
        print(f"--only {','.join(only)}: {n_new} jobs replaced, the other shots' jobs kept (night_run skips finished files)")
    kinds = {}
    for j in jobs:
        kinds[j["kind"]] = kinds.get(j["kind"], 0) + 1
    print(f"-> jobs.json: {len(jobs)} jobs {kinds}; prompts.json; wardrobe: {wardrobe}")


if __name__ == "__main__":
    main()
