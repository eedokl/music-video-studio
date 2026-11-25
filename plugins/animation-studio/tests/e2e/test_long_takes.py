"""claudia-music-video "takes": "long" (0.25.0): plan.py --takes long joins sung lines to takes of 6-9 s, jobs.py
renders them as LTX clips at 1024x576 with up to 217 frames, a shot "speed" slows the vocals and lengthens the clip,
clips.stretch_audio / frame_index place such a clip, pick.py's motion rule, ai-video film_motion.py. No GPU."""
from common import Test, expect, need, read_json, script, song_sheet, tone, write_json

NEW = script("song-analysis", "new_project.py")
PLAN = script("claudia-music-video", "plan.py")
JOBS = script("claudia-music-video", "jobs.py")
PICK = script("claudia-music-video", "pick.py")
MOTION = script("ai-video", "film_motion.py")
CLIPS = script("ai-video", "clips.py")

SONG = 24.0
LINES = ["Monday in the city", "another meeting waits", "paper falls like rain", "nobody looks up",
         "out into the storm", "wake up now"]


def words():
    out = []
    for li, text in enumerate(LINES):
        t0 = 0.4 + li * 3.9
        ws = text.split()
        for k, w in enumerate(ws):
            a = t0 + k * 3.0 / len(ws)
            out.append((w, round(a, 2), round(a + 2.6 / len(ws), 2), li))
    return out


def run_long(ctx):
    need("ffmpeg")
    song = tone(ctx, ctx.dir / "song.wav", SONG)
    lyr = ctx.dir / "lyrics.txt"
    lyr.write_text("\n".join(LINES) + "\n", encoding="utf-8")
    d = ctx.dir / "long"
    ctx.uv(NEW, d, "--song", song, "--lyrics", lyr, "--language", "en")
    write_json(d / "analysis" / "song_sheet.json", song_sheet(SONG, words()))
    (d / "analysis" / "vocals_lead.wav").write_bytes(song.read_bytes())
    for n in ("a.png", "b.png"):
        ctx.ff("-f", "lavfi", "-i", "color=c=gray:s=64x64", "-frames:v", "1", d / n)
    P = read_json(d / "project.json")
    P.update({"seed": 7, "character_refs": ["a.png", "b.png"]})
    write_json(d / "project.json", P)

    # 1. the plan: every sung take 6-8.9 s, lip-sync with LTX, a framing and a move made for long takes
    out = ctx.uv(PLAN, d, "--takes", "long")
    P = read_json(d / "project.json")
    shots = P["sections"]
    sung = [s for s in shots if s["lyrics"]]
    expect(P.get("takes") == "long", "plan.py --takes long did not write project.json \"takes\"")
    expect(len(sung) == 3, f"6 lines of 3.9 s should give 3 takes of two lines, got {len(sung)}:\n{out.stdout}")
    for s in sung:
        dur = s["to"] - s["from"]
        expect(6.0 <= dur <= 8.9, f"{s['name']}: {dur:.2f} s is not a long take")
        expect(s["technique"] == "lipsync" and s["engine"] == "ltx", f"{s['name']}: {s['technique']} / {s['engine']}")
        expect("frontal" in s["framing"] and "small head movements" not in s["action"], f"{s['name']}: {s['framing']} / {s['action']}")
    expect(sung[0]["line"] == "Monday in the city another meeting waits", f"joined line text: {sung[0]['line']!r}")
    expect(abs(shots[-1]["to"] - SONG) < 0.01 and all(abs(a["to"] - b["from"]) < 1e-6 for a, b in zip(shots, shots[1:])),
           "the takes do not tile the song")

    # 2. the jobs: long clips at 1024x576; a shot "speed" = slowed vocals, a longer clip, the same song window
    P["brief"] = dict(P.get("brief") or {}, wardrobe="a grey blazer over a white top")
    P["sections"][1 if not shots[0]["lyrics"] else 0]["set"] = "in a glass corridor"
    fast = sung[1]["name"]
    for s in P["sections"]:
        if s["lyrics"]:
            s.update(idea="test", set="in a glass corridor", set_short="in a glass corridor")
        else:
            s.update(subject="an empty glass corridor", motion="light moves over the floor")
        if s["name"] == fast:
            s["speed"] = 1.1
    write_json(d / "project.json", P)
    out = ctx.uv(JOBS, d, "--seeds", "1", "--start", "1", "--no-depth")
    jobs = {j["id"]: j for j in read_json(d / "jobs.json")["jobs"]}
    for s in sung:
        a = jobs[f"{s['name']}/ltx_s1"]["args"]
        dur = s["to"] - s["from"]
        speed = 1.1 if s["name"] == fast else 1.0
        expect((a.get("w"), a.get("h"), a.get("max_frames")) == (1024, 576, 217), f"{s['name']}: size {a.get('w')}x{a.get('h')}")
        expect(121 < a["frames"] <= 217 and (a["frames"] - 1) % 8 == 0, f"{s['name']}: {a['frames']} frames")
        expect(a["frames"] >= (dur + 0.05) * speed * 24, f"{s['name']}: {a['frames']} frames do not cover {dur:.2f} s at speed {speed}")
        expect(a["audio"].get("speed", 1.0) == speed, f"{s['name']}: audio speed {a['audio'].get('speed')}")
        expect(abs(a["audio"]["dur"] - (a["frames"] / 24 / speed + 0.2)) < 0.002, f"{s['name']}: audio window {a['audio']['dur']}")
    expect("longer than one LTX clip" not in out.stdout, f"a take that fits was reported as too long:\n{out.stdout}")
    # the same project without "takes": the clips stop at 121 frames and jobs.py says what to do
    P2 = dict(P)
    P2.pop("takes")
    write_json(d / "project.json", P2)
    out = ctx.uv(JOBS, d, "--seeds", "1", "--start", "1", "--no-depth")
    a = read_json(d / "jobs.json")["jobs"]
    a = next(j for j in a if j["id"] == f"{sung[0]['name']}/ltx_s1")["args"]
    expect(a["frames"] == 121 and "w" not in a, f"short takes: {a['frames']} frames, w {a.get('w')}")
    expect('"takes": "long"' in out.stdout, f"no hint for a 7 s shot in a short-take project:\n{out.stdout}")
    write_json(d / "project.json", P)
    bad = dict(P, sections=[dict(s, speed=2.5) if s["name"] == fast else s for s in P["sections"]])
    write_json(d / "project.json", bad)
    r = ctx.uv(JOBS, d, "--seeds", "1", "--start", "1", "--no-depth", check=False)
    expect(r.returncode != 0 and '"speed"' in (r.stdout + r.stderr), "speed 2.5 was not refused")
    write_json(d / "project.json", P)

    # 2b. "takes": "mixed": the verse (lines 0-3) as long takes, the chorus (lines 4-5) one shot per line; jobs.py
    # renders only the long ones at 1024x576; plan.py names the face pass for long takes
    m = ctx.dir / "mixed"
    ctx.uv(NEW, m, "--song", song, "--lyrics", lyr, "--language", "en")
    write_json(m / "analysis" / "song_sheet.json", song_sheet(SONG, words()))
    write_json(m / "analysis" / "markers.json", [{"line": 0, "marker": "Verse 1"}, {"line": 4, "marker": "Chorus"}])
    (m / "analysis" / "vocals_lead.wav").write_bytes(song.read_bytes())
    for n in ("a.png", "b.png"):
        (m / n).write_bytes((d / n).read_bytes())
    PM = read_json(m / "project.json")
    PM.update({"seed": 7, "character_refs": ["a.png", "b.png"]})
    write_json(m / "project.json", PM)
    out = ctx.uv(PLAN, m, "--takes", "mixed", "--no-s2v", "--lipsync", "1")
    PM = read_json(m / "project.json")
    ms = [s for s in PM["sections"] if s["lyrics"]]
    verse = [s for s in ms if s["marker"].startswith("Verse")]
    chorus = [s for s in ms if s["marker"] == "Chorus"]
    expect(PM.get("takes") == "mixed" and len(verse) == 2 and all(s["take"] == "long" and 6.0 <= s["to"] - s["from"] <= 8.9
                                                                   and s["technique"] == "lipsync" for s in verse),
           f"mixed: verse not as long takes: {[(s['name'], s['marker'], s.get('take'), round(s['to'] - s['from'], 1)) for s in ms]}")
    expect(len(chorus) == 2 and all(s["take"] == "short" and s["to"] - s["from"] <= 5.0 for s in chorus),
           f"mixed: chorus not one short shot per line: {[(s['name'], s.get('take'), round(s['to'] - s['from'], 1)) for s in chorus]}")
    expect(abs(PM["sections"][-1]["to"] - SONG) < 0.01 and
           all(abs(a["to"] - b["from"]) < 1e-6 for a, b in zip(PM["sections"], PM["sections"][1:])), "mixed shots do not tile the song")
    expect("face pass" in out.stdout, f"plan.py names no face pass for long takes:\n{out.stdout[-500:]}")
    for s in PM["sections"]:
        s.update(idea="test", set="in a glass corridor", set_short="in a glass corridor",
                 subject="an empty glass corridor", motion="light moves over the floor")
    PM["brief"] = dict(PM.get("brief") or {}, wardrobe="a grey blazer over a white top")
    write_json(m / "project.json", PM)
    ctx.uv(JOBS, m, "--seeds", "1", "--start", "1", "--no-depth")
    mj = {j["id"]: j["args"] for j in read_json(m / "jobs.json")["jobs"]}
    for s in verse + [c for c in chorus if c["technique"] == "lipsync"]:
        a = mj[f"{s['name']}/ltx_s1"]
        want = (1024, 576) if s["take"] == "long" else (None, None)
        expect((a.get("w"), a.get("h")) == want, f"mixed jobs {s['name']} ({s['take']}): size {a.get('w')}x{a.get('h')}")

    # 3. clips: frames for a speed, the slowed sound, the placement of a clip with "tempo"; pick.py's motion rule
    drv = "\n".join([
        f"import sys, wave; sys.path.insert(0, r'{CLIPS.parent}'); sys.path.insert(0, r'{PICK.parent}')",
        "import clips",
        "assert clips.ltx_frames(7.0) == 177 and clips.ltx_frames(7.0, 0.25, 1.18) == 209, (clips.ltx_frames(7.0), clips.ltx_frames(7.0, 0.25, 1.18))",
        "assert clips.ltx_fit(8.9, max_frames=217)[0] == 217 and clips.ltx_fit(8.9)[0] == 121",
        "f, li = clips.ltx_fit(7.5, max_frames=217, speed=1.18); assert f == 217 and li < 0.25, (f, li)",
        "assert 8.8 < clips.ltx_seconds(217) < 9.0 and 7.5 < clips.ltx_seconds(217, 1.18) < 7.6, clips.ltx_seconds(217, 1.18)",
        f"w = clips.cut_audio(r'{song}', 2.0, 4.0, r'{d / 'stretch.wav'}')",
        "clips.stretch_audio(w, 1.25)",
        "with wave.open(str(w)) as x: sec = x.getnframes() / x.getframerate()",
        "assert abs(sec - 5.0) < 0.05, sec",
        "m = {'song_start': 10.0, 'fps': 24, 'delay_frames': 1, 'tempo': 1.25}",
        "assert clips.frame_index(10.0, m) == -1 and clips.frame_index(12.0, m) == 59 and clips.frame_index(12.0, dict(m, tempo=1.0)) == 47",
        "import pick; assert pick.MOTION_SLACK == 0.12",
        "print('clips ok')", ""])
    out = ctx.py(drv, deps_from=[PICK], name="long_clips.py")
    expect("clips ok" in out.stdout, f"clips speed / tempo:\n{out.stdout}\n{out.stderr}")

    # 4. film_motion.py: two takes of 3 s, a slow zoom and a still
    film = ctx.dir / "two.mp4"
    ctx.ff("-f", "lavfi", "-t", "3", "-i", "mandelbrot=s=320x180:r=24", "-f", "lavfi", "-i", "color=c=navy:s=320x180:r=24:d=3",
           "-filter_complex", "[0:v][1:v]concat=n=2:v=1[v]", "-map", "[v]", "-c:v", "libx264", "-pix_fmt", "yuv420p", film)
    out = ctx.uv(MOTION, film, "--json", ctx.dir / "motion.json", "--shots", d / "project.json")
    m = read_json(ctx.dir / "motion.json")[0]
    expect(m["takes"] == 2 and abs(m["take_max_s"] - 3.0) <= 0.4, f"film_motion takes: {m}")
    expect(m["still_share"] >= 0.4 and "shots" in m, f"film_motion still share / shots: {m}")
    ctx.note(f"3 takes of two lines ({', '.join(str(round(s['to'] - s['from'], 1)) for s in sung)} s), LTX jobs at "
             f"1024x576 up to 217 frames, speed 1.1 lengthens the clip, short-take hint, speed 2.5 refused, "
             f"stretch_audio + frame_index tempo, film_motion 2 takes; mixed: verse {len(verse)} long, chorus "
             f"{len(chorus)} short")


TESTS = [Test("claudia-long-takes", run_long, about="plan.py --takes long -> jobs.py (1024x576, 217 frames, shot speed) -> clips tempo -> film_motion.py")]
