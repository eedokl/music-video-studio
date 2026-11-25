"""claudia-music-video: synthetic AI clips (ffmpeg test pictures with sound) + their <clip>.json meta as night_run /
ltx.py write them + selection.json -> render_shots.py -> make_film.py (lyrics, film, sheets, review.json)."""
import json

from common import (FPS, Test, full, expect, expect_film, need, read_json, script, song_sheet, tone, tool,
                    video_frames, write_json)

NEW = script("song-analysis", "new_project.py")
RENDER = script("claudia-music-video", "render_shots.py")
FILM = script("claudia-music-video", "make_film.py")
TAKES = script("claudia-music-video", "takes.py")
PICK = script("claudia-music-video", "pick.py")
JOBS = script("claudia-music-video", "jobs.py")
CODE = script("claudia-music-video", "code_film.py")

SONG = 3.30
WORDS = [("Light", 0.20, 0.60, 0), ("the", 0.60, 0.75, 0), ("city", 0.80, 1.40, 0),
         ("we", 1.70, 1.95, 1), ("run", 2.00, 2.50, 1), ("tonight", 2.55, 3.20, 1)]


def clip(ctx, out, frames, meta, seed):
    out.parent.mkdir(parents=True, exist_ok=True)
    ctx.ff("-f", "lavfi", "-i", f"testsrc2=s=1280x704:r=24", "-f", "lavfi", "-i", f"sine=f={300 + seed}:r=48000",
           "-frames:v", str(frames), "-shortest", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", out)
    write_json(out.with_suffix(".json"), dict(meta, fps=24, frames=frames, seed=seed, strength=1.0,
                                              image="ai/start/x_v1.png", prompt="test", negative="", seconds=1.0))


def run_claudia(ctx):
    need("ffmpeg")
    song = tone(ctx, ctx.dir / "song.wav", SONG)
    lyr = ctx.dir / "lyrics.txt"
    lyr.write_text("Light the city\nwe run tonight\n", encoding="utf-8")
    d = ctx.dir / "claudia"
    ctx.uv(NEW, d, "--song", song, "--lyrics", lyr, "--language", "en")
    write_json(d / "analysis" / "song_sheet.json", song_sheet(SONG, WORDS))
    P = read_json(d / "project.json")
    cut = 1.62
    P.update({"seed": 5, "version": "studio", "ai_label": "AI-generated test clips",
              "look": "standard" if full() else "none",                 # the look itself is checked by other tests
              "sections": [{"name": "s01", "from": 0.0, "to": cut, "technique": "lipsync", "line": "Light the city",
                            "lyrics": True},
                           {"name": "s02", "from": cut, "to": SONG, "technique": "broll", "line": "we run tonight",
                            "lyrics": True}]})
    write_json(d / "project.json", P)
    # LTX lip-sync clip: starts at the shot (no lead-in), picture 1 frame early (delay_frames 1)
    clip(ctx, d / "ai" / "lipsync" / "s01_v1_s1.mp4", 49,
         {"kind": "ltx_lipsync", "delay_frames": 1, "song_start": 0.0, "lead_in": 0.0, "shot": "s01"}, 1)
    # moving B-roll: 0.25 s lead-in before the shot (cut away by the placement rule)
    clip(ctx, d / "ai" / "broll" / "s02_v1.mp4", 49,
         {"kind": "ltx_moving", "delay_frames": 0, "song_start": cut - 0.25, "lead_in": 0.25, "shot": "s02"}, 2)
    write_json(d / "selection.json", {"clip": {"s01": {"file": "ai/lipsync/s01_v1_s1.mp4", "lag": 0},
                                               "s02": {"file": "ai/broll/s02_v1.mp4", "lag": 1}}})
    # takes.py: a second take of s01, scores from picks.log; previews on the song; choose by hand and back
    clip(ctx, d / "ai" / "lipsync" / "s01_v1_s2.mp4", 49,
         {"kind": "ltx_lipsync", "delay_frames": 1, "song_start": 0.0, "lead_in": 0.0, "shot": "s01"}, 3)
    (d / "picks.log").write_text("  lipsync/s01_v1_s1.mp4                r0 0.6  r@0 0.6  range 1.0  face 1.0  score 0.6\n"
                                 "  lipsync/s01_v1_s2.mp4                r0 0.3  r@1 0.4  range 0.9  face 1.0  score 0.4"
                                 "  mouth closed\n", encoding="utf-8")
    ctx.uv(TAKES, d)
    tj = read_json(d / "takes" / "takes.json")
    s01 = next(s for s in tj["shots"] if s["name"] == "s01")
    expect(len(s01["takes"]) == 2 and s01["auto"] == "ai/lipsync/s01_v1_s1.mp4"
           and {t["score"] for t in s01["takes"]} == {0.6, 0.4} and s01["takes"][1]["lag"] == 1
           and "mouth closed" in s01["takes"][1]["warn"], f"takes.json s01: {s01}")
    for t in s01["takes"]:
        pv = d / t["preview"]
        expect(pv.exists() and abs(video_frames(pv) - round(cut * FPS)) <= 1, f"preview {pv.name}: wrong length")
    drv = (f"import sys; sys.path.insert(0, r'{TAKES.parent}'); import takes; from song_project import Project; "
           f"P = Project(r'{d}'); takes.choose(P, 's01', 'ai/lipsync/s01_v1_s2.mp4'); "
           "import json; s = json.load(open(P.dir / 'selection.json')); "
           "assert s['manual']['clip']['s01'] == {'file': 'ai/lipsync/s01_v1_s2.mp4', 'lag': 1}, s; "
           "assert s['clip']['s01']['file'].endswith('s2.mp4'), s; "
           "takes.choose(P, 's01', None); s = json.load(open(P.dir / 'selection.json')); "
           "assert 's01' not in s['manual']['clip'] and s['clip']['s01']['file'].endswith('s1.mp4'), s; print('choose ok')")
    out = ctx.run(["python", "-c", drv])
    expect("choose ok" in out.stdout, f"takes.choose:\n{out.stdout}")
    ctx.uv(RENDER, d, timeout=900)
    log = (d / "render.log").read_text(encoding="utf-8")
    expect(log.count(" clip ") == 2 and "card" not in log, f"render_shots did not use both clips:\n{log}")
    # the still instead of the clip (takes page "still"), render --only keeps the other render.log lines, changed()
    (d / "ai" / "broll").mkdir(parents=True, exist_ok=True)
    ctx.ff("-f", "lavfi", "-i", "testsrc2=s=1280x704", "-frames:v", "1", d / "ai" / "broll" / "s02_v1.png")
    sel = read_json(d / "selection.json")
    sel["broll"] = {"s02": "ai/broll/s02_v1.png"}
    write_json(d / "selection.json", sel)
    ctx.uv(TAKES, d, "--only", "s02")
    tj = read_json(d / "takes" / "takes.json")
    expect([s["name"] for s in tj["shots"]] == ["s01", "s02"]
           and any(t["file"] == "still" for t in tj["shots"][1]["takes"]), f"takes --only s02 / still take: {tj['shots']}")
    drv = (f"import sys; sys.path.insert(0, r'{TAKES.parent}'); import takes; from song_project import Project; "
           f"P = Project(r'{d}'); assert takes.changed(P) == [], takes.changed(P); "
           "takes.choose(P, 's02', 'still'); assert takes.changed(P) == ['s02'], takes.changed(P); print('still ok')")
    out = ctx.run(["python", "-c", drv])
    expect("still ok" in out.stdout, f"takes still / changed:\n{out.stdout}")
    # pick.py saves minutes after loading (night-run hook): a choice made on the page meanwhile wins, the hand choice
    # keeps "manual": true and the automatic pick under "auto" ("back to automatic" restores that one, not the hand one)
    drv = "\n".join([
        f"import sys, json; sys.path.insert(0, r'{TAKES.parent}'); import pick, takes; from song_project import Project",
        f"P = Project(r'{d}'); sel = json.load(open(P.dir / 'selection.json'))",
        "sel['clip']['s02'] = {'file': 'ai/broll/s02_v1.mp4', 'lag': 0}",
        "takes.choose(P, 's01', 'ai/lipsync/s01_v1_s2.mp4')",
        "pick.save(P, sel)",
        "s = json.load(open(P.dir / 'selection.json'))",
        "c = s['clip']['s01']; assert c['manual'] and c['file'].endswith('s2.mp4') and c['auto']['file'].endswith('s1.mp4'), s",
        "assert s['clip']['s02'] == {'still': True, 'manual': True, 'auto': {'file': 'ai/broll/s02_v1.mp4', 'lag': 0}}, s",
        "tj = takes.build(P, {'s01'}); assert tj['shots'][0]['auto'].endswith('s1.mp4'), tj['shots'][0]",
        "takes.choose(P, 's01', None); s = json.load(open(P.dir / 'selection.json'))",
        "assert s['clip']['s01'] == {'file': 'ai/lipsync/s01_v1_s1.mp4', 'lag': 0}, s['clip']['s01']",
        "print('pick save ok')", ""])
    out = ctx.py(drv, deps_from=[PICK], name="pick_save.py")
    expect("pick save ok" in out.stdout, f"pick.save / hand choice:\n{out.stdout}")
    # a seed rendered before 0.4.28 under the plain name keeps it (no duplicate render of the same seed)
    write_json(d / "ai" / "s2v" / "s09_v1.json", {"kind": "s2v", "seed": 777})
    (d / "ai" / "s2v" / "s09_v1.mp4").write_bytes(b"")
    drv = "\n".join([
        f"import sys; sys.path.insert(0, r'{JOBS.parent}'); import jobs; from song_project import Project",
        f"P = Project(r'{d}')",
        "assert jobs.seed_tag(777, 5, P, 's2v', 's09') == '', 'old name not adopted'",
        "assert jobs.seed_tag(778, 5, P, 's2v', 's09') == '_sd778'",
        "print('seed tag ok')", ""])
    out = ctx.py(drv, deps_from=[JOBS], name="seed_tag.py")
    expect("seed tag ok" in out.stdout, f"jobs.seed_tag:\n{out.stdout}")
    for f in ("s09_v1.json", "s09_v1.mp4"):
        (d / "ai" / "s2v" / f).unlink()
    # --keep-old: a rewritten shot's finished takes stay on the takes page as <shot>_<tag>_... (sidecars, start image
    # copy, kept-flag, selection.json / picks.log follow); a second call keeps nothing twice; a wave is hinted
    lip, st = d / "ai" / "lipsync", d / "ai" / "start"
    st.mkdir(parents=True, exist_ok=True)
    (st / "s77_v2.png").write_bytes(b"png")
    for stem in ("s77_v2_s1", "s77_v2_s1_g"):
        write_json(lip / f"{stem}.json", {"kind": "ltx_lipsync", "seed": 5, "image": str(st / "s77_v2.png")})
        (lip / f"{stem}.mp4").write_bytes(b"")
    write_json(lip / "s77_v2_s1.mouth.json", {"m": []})
    sel = json.loads((d / "selection.json").read_text(encoding="utf-8"))
    sel_before = dict(sel)
    sel.setdefault("manual", {}).setdefault("clip", {})["s77"] = {"file": "ai/lipsync/s77_v2_s1_g.mp4", "lag": 0}
    write_json(d / "selection.json", sel)
    drv = "\n".join([
        f"import sys, json; sys.path.insert(0, r'{JOBS.parent}'); import jobs, claudia; from song_project import Project",
        "from pathlib import Path",
        f"P = Project(r'{d}'); lip = Path(r'{lip}')",
        "m = jobs.keep_old(P, ['s77'], 'wink')",
        "assert sorted(m.values()) == ['ai/lipsync/s77_wink_v2_s1.mp4', 'ai/lipsync/s77_wink_v2_s1_g.mp4'], m",
        "assert sorted(f.name for f in lip.glob('s77_*')) == ['s77_wink_v2_s1.json', 's77_wink_v2_s1.mouth.json', "
        "'s77_wink_v2_s1.mp4', 's77_wink_v2_s1_g.json', 's77_wink_v2_s1_g.mp4'], sorted(f.name for f in lip.glob('s77_*'))",
        "meta = json.loads((lip / 's77_wink_v2_s1.json').read_text(encoding='utf-8'))",
        "assert meta['kept'] == 'wink' and Path(meta['image']).name == 's77_v2wink.png' and Path(meta['image']).exists(), meta",
        "sel = json.loads((P.dir / 'selection.json').read_text(encoding='utf-8'))",
        "assert sel['manual']['clip']['s77']['file'] == 'ai/lipsync/s77_wink_v2_s1_g.mp4', sel['manual']['clip']",
        "assert jobs.keep_old(P, ['s77'], 'wink') == {} and jobs.keep_old(P, ['s77'], 'again') == {}, 'kept twice'",
        "assert jobs.seed_tag(6, 5, P, 'lipsync', 's77') == '_sd6'",
        "try:\n    jobs.keep_old(P, ['s77'], 'a b'); raise AssertionError('bad tag taken')\nexcept SystemExit: pass",
        "h = claudia.hints([dict(name='a', technique='lipsync', action='he gives a small polite wave'),",
        "                   dict(name='b', technique='lipsync', idea='she waves goodbye'),",
        "                   dict(name='c', technique='lipsync', action='she waves goodbye', wave=True),",
        "                   dict(name='d', technique='lipsync', action='her hair falls in soft waves'),",
        "                   dict(name='e', technique='broll', subject='waves crash at the shore')])",
        "assert sorted(x.split(':')[0] for x in h if 'a wave in the text' in x) == ['a', 'b'], h",
        "print('keep old ok')", ""])
    out = ctx.py(drv, deps_from=[JOBS], name="keep_old.py")
    expect("keep old ok" in out.stdout, f"jobs.keep_old / wave hint:\n{out.stdout}")
    for f in list(lip.glob("s77_*")) + [st / "s77_v2.png", d / "ai" / "start_alt" / "s77_v2wink.png"]:
        f.unlink()
    (d / "ai" / "start_alt").rmdir()
    write_json(d / "selection.json", sel_before)
    # other characters (project.json "characters" / "lead", shot "who"): their own identity, refs and negatives; none
    # of Claudia's canon (microphone, streak) in a prompt, a check or the mic repair; Claudia herself unchanged
    drv = "\n".join([
        f"import sys; sys.path.insert(0, r'{JOBS.parent}'); import claudia",
        "old = claudia.start_image_prompt({'framing': 'close-up', 'technique': 'lipsync'}, 'a coat', 'L.')",
        "P = {'lead': 'tom', 'characters': {'tom': {'pronoun': 'he', 'full': 'a tall man with grey hair', 'refs': ['a.png', 'b.png'],",
        "     'options': {'cap': 'a flat cap'}, 'negative': 'beard'}}}",
        "claudia.setup(P)",
        "s = {'name': 's01', 'technique': 'lipsync', 'framing': 'close-up', 'cap': True, 'action': 'he nods', 'set': 'in a field'}",
        "sp = claudia.start_image_prompt(s, 'a jacket', 'Warm light.')",
        "assert 'a tall man with grey hair, a flat cap' in sp and 'His lips' in sp and 'microphone' not in sp and 'streak' not in sp, sp",
        "lp = claudia.lipsync_prompt(s, 'a jacket', 'warm light', 'Hallo Welt')",
        "assert 'he sings into the camera, nods' in lp and 'He sings the words \"Hallo Welt\"' in lp and 'headset' not in lp, lp",
        "assert claudia.check(sp, 'image', s) == [] and claudia.check(lp, 'lipsync', s) == [], (claudia.check(sp, 'image', s), claudia.check(lp, 'lipsync', s))",
        "assert not claudia.has_canon(s) and 'beard' in claudia.neg_image(s) and 'microphone, headset' in claudia.neg_lipsync(s)",
        "assert claudia.shot_refs(s, lambda: 1 / 0) == ['a.png', 'b.png']",
        "duo = dict(s, who=['tom', 'claudia'], technique='claudia_moving')",
        "dp = claudia.start_image_prompt(duo, 'a jacket', 'Warm light.')",
        "assert dp.startswith('Two people in one picture: the man keeps') and 'Remove her headset microphone' in dp, dp",
        "assert claudia.shot_refs(duo, lambda: ['c1.png', 'c2.png']) == ['a.png', 'c1.png']",
        "h = claudia.hints([dict(s, action='he runs a hand through his hair'), dict(s, name='s02', action='he raises his eyebrows'),",
        "                   {'name': 's03', 'technique': 'broll', 'subject': 'a man with a laptop on a field path'}])",
        "assert len(h) == 4 and h[0].startswith('s01: a hand at the hair') and 'stranger' in h[3], h",
        "h2 = claudia.hints([dict(s, framing='medium wide shot'), dict(s, name='s02', technique='claudia_moving', motion='She hands him the apple'),",
        "                    dict(s, name='s03', wardrobe='a crumpled shirt'), dict(s, name='s04', action='he waits', framing='medium shot from the waist up', motion='he looks up')])",
        "assert len(h2) == 3 and 'stranger' in h2[0] and h2[1].startswith('s02: the motion asks') and 'holes' in h2[2], h2",
        "assert 'passers-by' in claudia.neg_moving({'technique': 'broll', 'subject': 'an old tractor, no people'})",
        "assert 'passers-by' not in claudia.neg_moving({'technique': 'broll', 'subject': 'five colleagues at a table'})",
        "claudia.setup({})",
        "assert claudia.has_canon({}) and claudia.start_image_prompt({'framing': 'close-up', 'technique': 'lipsync'}, 'a coat', 'L.') == old",
        "assert claudia.neg_image({}) == claudia.NEG_IMAGE and any('microphone' in e for e in claudia.check('a woman', 'image', {}))",
        "print('characters ok')", ""])
    out = ctx.py(drv, deps_from=[JOBS], name="characters.py")
    expect("characters ok" in out.stdout, f"claudia characters:\n{out.stdout}")
    # "mic": "added": a start image without a headset (no microphone word left but the "no microphone" sentence), the
    # add prompt names only the picture side; not from behind, not with a given start image, a shot may opt out
    drv = "\n".join([
        f"import sys; sys.path.insert(0, r'{JOBS.parent}'); import claudia",
        "s = {'name': 's01', 'technique': 'lipsync', 'framing': 'close-up', 'action': 'she nods', 'set': 'in a field'}",
        "claudia.setup({})",
        "assert not claudia.mic_added(s) and claudia.mic_added(dict(s, mic='added'))",
        "claudia.setup({'mic': 'added'})",
        "assert claudia.mic_added(s) and not claudia.mic_added(dict(s, framing='medium shot from behind'))",
        "assert not claudia.mic_added(dict(s, mic='painted')) and not claudia.mic_added(dict(s, start_image='x.png'))",
        "old = claudia.start_image_prompt(s, 'a coat', 'Warm light.')",
        "bp = claudia.start_image_prompt(s, 'a coat', 'Warm light.', bare=True)",
        "assert bp.count('microphone') == 1 and bp.count('headset') == 1 and claudia.MIC_NONE in bp, bp",
        "assert bp.endswith('Warm light.') and 'star clip of the woman in image 1' in bp and 'eyes open.' in bp, bp",
        "assert claudia.check(bp, 'image_bare', s) == [] and claudia.check(old, 'image', s) == [], claudia.check(bp, 'image_bare', s)",
        "assert any('no microphone' in e for e in claudia.check(old, 'image_bare', s))",
        "wide = claudia.start_image_prompt(dict(s, framing='wide shot', technique='claudia_moving'), 'a coat', 'Warm light.', bare=True)",
        "assert wide.count('microphone') == 1 and claudia.MIC_NONE in wide, wide",
        "assert 'LEFT side of the picture' in claudia.MIC_ADD and 'right cheek' not in claudia.MIC_ADD",
        "assert 'cable hanging down' in claudia.MIC_ADD_NEG and claudia.NEG_BARE.startswith('microphone, headset')",
        "try:",
        "    claudia.start_image_prompt(dict(s, set='next to a microphone stand'), 'a coat', 'L.', bare=True)",
        "    raise AssertionError('a microphone in the shot text was not refused')",
        "except SystemExit:",
        "    pass",
        "try:",
        "    claudia.setup({'mic': 'glued'})",
        "    raise AssertionError('a wrong mic value was not refused')",
        "except SystemExit:",
        "    pass",
        "claudia.setup({})",
        "assert not claudia.mic_added(s) and claudia.start_image_prompt(s, 'a coat', 'Warm light.') == old",
        "lp = claudia.lipsync_prompt(dict(s, manner='warmly', hold_last=True), 'a coat', 'warm light', 'Hallo Welt')",
        "assert 'She sings the words \"Hallo Welt\". She holds the last word as one long open note' in lp, lp",
        "assert 'holds the last word' not in claudia.lipsync_prompt(dict(s, manner='warmly'), 'a coat', 'warm light', 'Hallo Welt')",
        "h = claudia.hints([dict(s, manner='dryly, with a tired smile'), dict(s, name='s02', manner='warmly'),",
        "                   dict(s, name='s03', technique='claudia_moving', manner='quietly')])",
        "assert len(h) == 1 and h[0].startswith('s01: \"manner\" has the mood word \"dryly\"'), h",
        "print('mic added ok')", ""])
    out = ctx.py(drv, deps_from=[JOBS], name="mic_added.py")
    expect("mic added ok" in out.stdout, f"claudia mic added:\n{out.stdout}")
    ctx.uv(RENDER, d, "--only", "s02", timeout=900)
    log = (d / "render.log").read_text(encoding="utf-8").splitlines()
    expect(len(log) == 2 and " clip " in log[0] and "still ai/broll/s02_v1.png" in log[1], f"render.log after --only:\n{log}")
    for s in P["sections"]:
        n = len(list((d / "scenes" / s["name"]).glob("f.*.png")))
        want = round(s["to"] * FPS) - round(s["from"] * FPS)
        expect(n == want, f"scenes/{s['name']}: {n} frames, expected {want}")
    ctx.uv(FILM, d, timeout=900)
    total = round(SONG * FPS)
    expect_film(ctx, d / "film.mp4", total)
    for f in ("film_small.mp4", "film_mail.mp4", "film_sheet.png", "film_shots.jpg", "review.json"):
        expect((d / f).exists(), f"{f} missing")
    rv = read_json(d / "review.json")
    expect([s["name"] for s in rv["shots"]] == ["s01", "s02"], f"review.json shots {rv['shots']}")
    code = "code cut skipped (needs node, browser, face_landmarker)"
    if all(tool(k) for k in ("node", "browser", "face_landmarker")):       # the same project cut in code (code_film.py)
        ctx.uv(CODE, d, "--pace", "fast", timeout=900)
        expect_film(ctx, d / "film_code_v01.mp4", total)
        ed = read_json(d / "code_cut" / "edit.json")
        expect(ed["pace"] == "fast" and [s["id"] for s in ed["shots"]] == ["s01", "s02"]
               and all(p.get("why") for s in ed["shots"] for p in s["parts"]), f"code cut edit.json: {ed['shots']}")
        pj = read_json(d / "project.json")                     # small pieces written with anchors at their shot
        pj["sections"][0].setdefault("code", {})["overlays"] = [
            {"type": "stamp", "text": "A LONG STAMP TEXT E2E", "side": "right"},
            {"type": "board", "side": "right", "w": 440, "rows": [["09:00", "A", "OK"]], "len": 10},
            {"type": "check", "side": "left", "words": [{"text": "OK"}], "len": 12, "at": {"line": 0,
             "word": read_json(d / "code_cut" / "song.json")["lines"][0]["words"][0]["w"]}},
            {"type": "list", "title": "L", "items": [{"text": "a", "strike_at": {"shot": "s01", "end": True}}], "len": 20},
            {"type": "rings", "point": [640, 500], "at": {"shot": "s01"}, "len": 10}]   # "at" = when, "point" = where
        pj["code_layer"] = dict(pj.get("code_layer") or {}, iris={"c": [0.5, 0.4], "r": 150})
        write_json(d / "project.json", pj)
        ctx.uv(CODE, d, "--pace", "calm", "--plan-only", timeout=300)
        calm = read_json(d / "code_cut" / "edit.json")
        s1 = calm["shots"][0]
        st, ck, li = (next(o for o in calm["overlays"] if o["type"] == t) for t in ("stamp", "check", "list"))
        expect(st["k0"] == s1["k0"] and st["k1"] >= st["k0"] + 2 * FPS and st["x"] == 640,
               f"stamp at its shot, at least 2 s; a long text on the right starts at the middle at the earliest: {st}")
        bd = next(o for o in calm["overlays"] if o["type"] == "board")
        expect(bd["x"] == 1232 - 440, f"a piece on the right is right-aligned by its width: {bd}")
        expect(calm.get("locale") == {"de": "de-DE", "en": "en-US"}.get(pj.get("language") or "", calm.get("locale")),
               f"locale from the project's language: {calm.get('locale')} / {pj.get('language')}")
        w0 = read_json(d / "code_cut" / "song.json")["lines"][0]["words"][0]
        expect(ck["x"] == 96 and ck["k1"] == ck["k0"] + 12 and ck["words"][0]["k"] == ck["k0"] == w0["k0"], f"check: {ck}")
        expect(li["items"][0]["strike"] == s1["k1"], f"list strike anchor: {li}")
        expect(calm["iris"]["k1"] == calm["frames"] and calm["fade_out"] == 0, f"iris: {calm.get('iris')}")
        rg = next(o for o in calm["overlays"] if o["type"] == "rings")
        expect(rg["point"] == [640, 500] and "at" not in rg and rg["k1"] == rg["k0"] + 10, f"rings keep their place: {rg}")
        # found on the first real film: a word index past the line's words crashed, a gap in the shot plan was refused
        good = read_json(d / "project.json")
        bad = read_json(d / "project.json")
        bad["sections"][0]["code"]["overlays"].append({"type": "stamp", "text": "X", "at": {"line": 0, "word": 99}})
        write_json(d / "project.json", bad)
        r = ctx.uv(CODE, d, "--plan-only", check=False, timeout=300)
        out = (r.stdout or "") + (r.stderr or "")
        expect(r.returncode != 0 and "words:" in out and "Traceback" not in out,
               f"a word index past the line must be refused with the line's words: exit {r.returncode}, {out[-300:]}")
        bad["sections"][0]["code"]["overlays"][-1]["at"] = {"line": 0, "word": "zzz"}
        write_json(d / "project.json", bad)
        r = ctx.uv(CODE, d, "--plan-only", check=False, timeout=300)
        out = (r.stdout or "") + (r.stderr or "")
        expect(r.returncode != 0 and "no word starting with 'zzz'" in out, f"unknown word text: exit {r.returncode}, {out[-300:]}")
        gap = read_json(d / "project.json")
        gap["sections"][0]["code"]["overlays"].pop()
        gap["sections"][0]["to"] = round(gap["sections"][1]["from"] - 0.4, 3)     # 0.4 s between the two shots
        write_json(d / "project.json", gap)
        ctx.uv(CODE, d, "--pace", "calm", "--plan-only", timeout=300)
        g = read_json(d / "code_cut" / "edit.json")["shots"]
        expect(g[0]["k1"] == g[1]["k0"] and g[0]["parts"][-1].get("hold") is True,
               f"a gap in the shot plan: the take is held over it: {g[0]['parts'][-1]}")
        write_json(d / "project.json", good)
        expect(sum(len(s["parts"]) for s in calm["shots"]) <= sum(len(s["parts"]) for s in ed["shots"]),
               "pace calm has more parts than pace fast")
        code = ("code cut film_code_v01.mp4 (pace fast), calm plan has no more parts; pieces anchored at their shot "
                "(word as text, minimum standing time, side, rings point, iris), bad anchors refused, gap held")
    ctx.note(f"{total} frames = round({SONG}*24) (song length), both clips placed, lyrics overlay, review.json; {code}")


TESTS = [Test("claudia-music-video", run_claudia, about="fake LTX clips + meta -> takes.py (compare/choose) -> render_shots.py -> make_film.py -> code_film.py")]
