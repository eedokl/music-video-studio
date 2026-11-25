"""claudia-music-video relight.py ("Nachtschicht"): a finished film (fake start images, B-roll picture, takes with
their json, selection.json with a hand choice) -> a new project in another light. Checks the copied song / analysis /
refs, the shot "relight" blocks (source picture, light, seeds, size), the light in set and look, the kept shot with
its original take as manual choice, the original takes as kept takes, the map relit_from; then jobs.py (Qwen relight
jobs with the original as the only reference, no jobs for the kept shot, LTX on the picked relit image), pick.py
pick_start (relit images: no canon check, first variant, a hand choice wins), takes.py (original take marked) and the
refusals (a non-empty target, an unknown light, a short sentence without a light word)."""
import json

from common import Test, expect, need, read_json, script, tone, write_json

RELIGHT = script("claudia-music-video", "relight.py")
JOBS = script("claudia-music-video", "jobs.py")
PICK = script("claudia-music-video", "pick.py")
TAKES = script("claudia-music-video", "takes.py")
SONG = 6.0


def png(ctx, out, w=1024, h=576, colour="steelblue"):
    out.parent.mkdir(parents=True, exist_ok=True)
    ctx.ff("-f", "lavfi", "-i", f"color=c={colour}:s={w}x{h}", "-frames:v", "1", out)


def clip(ctx, out, meta, frames=48):
    out.parent.mkdir(parents=True, exist_ok=True)
    ctx.ff("-f", "lavfi", "-i", "testsrc2=s=1024x576:r=24", "-f", "lavfi", "-i", "sine=f=330:r=48000",
           "-frames:v", str(frames), "-shortest", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", out)
    write_json(out.with_suffix(".json"), dict(meta, fps=24, frames=frames, seed=1, prompt="day", seconds=2.0))


def run_relight(ctx):
    need("ffmpeg")
    src = ctx.dir / "day"
    for d in ("analysis", "cache/sep/htdemucs/song"):
        (src / d).mkdir(parents=True, exist_ok=True)
    tone(ctx, src / "song.wav", SONG)
    (src / "lyrics.txt").write_text("one\ntwo\nthree\n", encoding="utf-8")
    tone(ctx, src / "analysis" / "vocals_lead.wav", SONG)
    write_json(src / "analysis" / "song_sheet.json", {"duration": SONG, "words": []})
    tone(ctx, src / "cache" / "sep" / "htdemucs" / "song" / "no_vocals.wav", SONG, freq=110)
    png(ctx, src / "refs" / "claudia.png", 512, 512, "white")
    for k, c in ((1, "red"), (2, "orange")):
        png(ctx, src / "ai" / "start" / f"s01_v{k}.png", colour=c)
    png(ctx, src / "ai" / "broll" / "s02_v1.png", colour="green")
    png(ctx, src / "ai" / "start" / "s03_v1.png", colour="purple")
    clip(ctx, src / "ai" / "lipsync" / "s01_v2_s1.mp4", {"kind": "ltx_lipsync", "song_start": 0.0, "lead_in": 0.0,
                                                          "shot": "s01", "image": str(src / "ai/start/s01_v2.png")})
    write_json(src / "ai" / "lipsync" / "s01_v2_s1.mouth.json", {"m": []})
    clip(ctx, src / "ai" / "moving" / "s02_v1.mp4", {"kind": "ltx_moving", "song_start": 2.0, "lead_in": 0.0, "shot": "s02"})
    clip(ctx, src / "ai" / "lipsync" / "s03_v1_s2.mp4", {"kind": "ltx_lipsync", "song_start": 4.0, "lead_in": 0.0,
                                                          "shot": "s03"})
    write_json(src / "project.json", {
        "name": "Day film", "seed": 3, "version": "studio", "character_refs": ["refs/claudia.png"],
        "brief": {"look": "office", "wardrobe": "a petrol-blue coat",
                  "looks": {"office": ["Photographic 35mm film still, cool office daylight.", "cool office daylight"]}},
        "sections": [
            {"name": "s01", "from": 0.0, "to": 2.0, "technique": "lipsync", "line": "one", "look": "office",
             "framing": "medium shot from the waist up", "action": "she walks between the desks",
             "set": "in an open-plan office", "set_short": "in an office", "manner": "clearly"},
            {"name": "s02", "from": 2.0, "to": 4.0, "technique": "broll", "line": "two", "look": "office",
             "subject": "empty desks in rows", "motion": "the screens flicker"},
            {"name": "s03", "from": 4.0, "to": 5.0, "technique": "lipsync", "line": "three", "look": "black",
             "framing": "close-up", "set": "against pure black", "set_short": "black"},
            {"name": "s04", "from": 5.0, "to": SONG, "technique": "typo", "typo": {"kind": "title", "text": "END"}}]})
    write_json(src / "selection.json", {
        "start": {"s01": "ai/start/s01_v1.png", "s03": "ai/start/s03_v1.png"}, "broll": {"s02": "ai/broll/s02_v1.png"},
        "manual": {"start": {"s01": "ai/start/s01_v2.png"}},
        "clip": {"s01": {"file": "ai/lipsync/s01_v2_s1.mp4", "lag": 1}, "s02": {"file": "ai/moving/s02_v1.mp4", "lag": 0},
                 "s03": {"file": "ai/lipsync/s03_v1_s2.mp4", "lag": 2}}})

    new = ctx.dir / "night"
    out = ctx.uv(RELIGHT, src, new, "--light", "night", "--keep", "s03").stdout
    expect("2 shot(s) to relight" in out and "1 kept" in out and "No canon check" in out, f"relight.py summary:\n{out}")
    for f in ("song.wav", "lyrics.txt", "analysis/vocals_lead.wav", "analysis/song_sheet.json", "refs/claudia.png",
              "cache/sep/htdemucs/song/no_vocals.wav", "ai/relight_src/s01.png", "ai/relight_src/s02.png",
              "ai/relight_src/s03.png", "ai/lipsync/s01_orig_v2_s1.mp4", "ai/lipsync/s01_orig_v2_s1.mouth.json",
              "ai/moving/s02_orig_v1.mp4", "ai/lipsync/s03_orig_v1_s2.mp4"):
        expect((new / f).exists(), f"relight.py: {f} missing in the new project")
    expect((new / "ai/relight_src/s01.png").read_bytes() == (src / "ai/start/s01_v2.png").read_bytes(),
           "the source of s01 must be the HAND-chosen start image v2, not the automatic v1")
    P = read_json(new / "project.json")
    sh = {s["name"]: s for s in P["sections"]}
    r1 = sh["s01"]["relight"]
    expect(r1["src"] == "ai/relight_src/s01.png" and r1["seeds"] == [11, 23] and r1["size"] == [1024, 576]
           and "night" in r1["light"] and r1["from_shot"] == "s01", f"s01 relight block: {r1}")
    expect(sh["s01"]["set"].startswith("in an open-plan office, night") and sh["s01"]["look"] == "office_night"
           and "light" in P["brief"]["looks"]["office_night"][1] and P["brief"]["look"] == "office_night",
           f"light in set / look: {sh['s01']} / {P['brief']}")
    expect("night" in sh["s02"]["subject"] and sh["s02"]["relight"]["src"] == "ai/relight_src/s02.png",
           f"B-roll relight: {sh['s02']}")
    expect(sh["s03"]["relight"] == {"keep": True, "from_shot": "s03", "src": "ai/relight_src/s03.png"}
           and sh["s03"]["look"] == "black" and "typo" in sh["s04"] and "relight" not in sh["s04"],
           f"kept shot / typo untouched: {sh['s03']} / {sh['s04']}")
    rf = P["relit_from"]
    expect(rf["light"] == "night" and rf["shots"]["s01"] == {"shot": "s01", "start": "ai/start/s01_v2.png",
                                                             "clip": "ai/lipsync/s01_v2_s1.mp4", "lag": 1}
           and set(rf["shots"]) == {"s01", "s02", "s03"} and P["name"] == "Day film - night", f"relit_from: {rf}")
    om = read_json(new / "ai/lipsync/s01_orig_v2_s1.json")
    expect(om["kept"] == "orig" and om["original"]["lag"] == 1 and "relight to night" in om["original"]["note"]
           and om["image"].replace("\\", "/").endswith("ai/relight_src/s01.png"), f"original take meta: {om}")
    sel = read_json(new / "selection.json")
    expect(sel["manual"]["clip"] == {"s03": {"file": "ai/lipsync/s03_orig_v1_s2.mp4", "lag": 2}}
           and sel["manual"]["start"] == {"s03": "ai/relight_src/s03.png"} and "s01" not in sel.get("start", {}),
           f"new selection.json: {sel}")

    out = ctx.uv(JOBS, new).stdout
    J = read_json(new / "jobs.json")["jobs"]
    rj = [j for j in J if "/relight_v" in j["id"]]
    expect(sorted(j["out"] for j in rj) == ["ai/broll/s02_v1.png", "ai/broll/s02_v2.png", "ai/start/s01_v1.png",
                                            "ai/start/s01_v2.png"], f"relight jobs: {[j['out'] for j in rj]}")
    j1 = next(j for j in rj if j["out"] == "ai/start/s01_v1.png")
    expect(j1["kind"] == "qwen_edit" and j1["args"]["refs"] == ["ai/relight_src/s01.png"] and j1["args"]["seed"] == 11
           and j1["args"]["w"] == 1024 and j1["args"]["h"] == 576
           and j1["args"]["prompt"].startswith("Change only the light and the time of day of this photo: night")
           and "one clay-orange streak" in j1["args"]["prompt"], f"s01 relight job: {j1}")
    expect("Change only" in next(j for j in rj if j["out"] == "ai/broll/s02_v1.png")["args"]["prompt"]
           and "streak" not in next(j for j in rj if j["out"] == "ai/broll/s02_v1.png")["args"]["prompt"],
           "B-roll relight prompt names no people")
    expect(not [j for j in J if j["id"].startswith("s03/")], f"kept s03 must have no jobs: {[j['id'] for j in J]}")
    expect(not [j for j in J if j["id"].startswith("s01/start_v")], "s01 must not get identity start images")
    lj = [j for j in J if j["kind"] == "ltx_lipsync" and j["id"].startswith("s01/")]
    expect(lj and lj[0]["args"]["image"]["candidates"] == ["ai/start/s01_v1.png", "ai/start/s01_v2.png"]
           and "night" in lj[0]["args"]["prompt"], f"s01 LTX jobs on the relit picture: {lj[:1]}")
    pr = read_json(new / "prompts.json")
    expect("relight" in pr["s01"] and "start_image" not in pr["s01"] and "kept" in pr["s03"], f"prompts.json: {pr}")

    # the image phase is faked: pick_start takes the first relit variant without the canon check, a hand choice wins
    for k, c in ((1, "navy"), (2, "midnightblue")):
        png(ctx, new / "ai" / "start" / f"s01_v{k}.png", colour=c)
    drv = "\n".join([
        f"import sys, json; sys.path.insert(0, r'{PICK.parent}'); import pick, claudia; from song_project import Project",
        f"P = Project(r'{new}'); claudia.setup(P)",
        "sel = json.load(open(P.dir / 'selection.json')); log, rows = [], []",
        "pick.pick_start(P, sel, log, rows)",
        "s = json.load(open(P.dir / 'selection.json'))",
        "assert s['start']['s01'] == 'ai/start/s01_v1.png' and s['start']['s03'] == 'ai/relight_src/s03.png', s",
        "assert any('s01' in l and 'no canon check' in l for l in log), log",
        "assert all('no canon check' in r[1] for r in rows) and len(rows) == 2, rows",
        "s['manual']['start']['s01'] = 'ai/start/s01_v2.png'; json.dump(s, open(P.dir / 'selection.json', 'w'))",
        "log, rows = [], []; pick.pick_start(P, s, log, rows)",
        "s = json.load(open(P.dir / 'selection.json')); assert s['start']['s01'] == 'ai/start/s01_v2.png', s",
        "print('relight pick ok')", ""])
    out = ctx.py(drv, deps_from=[PICK], name="relight_pick.py")
    expect("relight pick ok" in out.stdout, f"pick_start relight branch:\n{out.stdout}")
    ctx.uv(TAKES, new, "--only", "s01")
    tj = read_json(new / "takes" / "takes.json")
    t1 = next(s for s in tj["shots"] if s["name"] == "s01")["takes"]
    orig = [t for t in t1 if t["file"] == "ai/lipsync/s01_orig_v2_s1.mp4"]
    expect(orig and "original take (before the relight to night)" in orig[0]["warn"], f"takes page original take: {t1}")

    for args, want in (((src, new, "--light", "night"), "not empty"), ((src, ctx.dir / "x1", "--light", "moon"), "not a preset"),
                       ((src, ctx.dir / "x2", "--light", "moon", "--text", "moonlit", "--short", "silver and calm"),
                        "names no light")):
        r = ctx.uv(RELIGHT, *args, check=False)
        expect(r.returncode != 0 and want in r.stdout and "Traceback" not in r.stdout,
               f"relight.py {args[2:]} must be refused with '{want}': exit {r.returncode}\n{r.stdout[-300:]}")
    ctx.note("2 shots relit (hand-chosen source), 1 kept with its take, 4 Qwen relight jobs at 1024x576, no canon check, "
             "original takes on the takes page, 3 refusals")


TESTS = [Test("claudia-relight", run_relight,
              about="relight.py: finished fake film -> new project in night light -> jobs.py / pick_start / takes.py")]
