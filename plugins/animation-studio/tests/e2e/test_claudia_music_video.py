"""claudia-music-video: synthetic AI clips (ffmpeg test pictures with sound) + their <clip>.json meta as night_run /
ltx.py write them + selection.json -> render_shots.py -> make_film.py (lyrics, film, sheets, review.json)."""
from common import (FPS, Test, full, expect, expect_film, need, read_json, script, song_sheet, tone, video_frames,
                    write_json)

NEW = script("song-analysis", "new_project.py")
RENDER = script("claudia-music-video", "render_shots.py")
FILM = script("claudia-music-video", "make_film.py")
TAKES = script("claudia-music-video", "takes.py")

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
    ctx.note(f"{total} frames = round({SONG}*24) (song length), both clips placed, lyrics overlay, review.json")


TESTS = [Test("claudia-music-video", run_claudia, about="fake LTX clips + meta -> takes.py (compare/choose) -> render_shots.py -> make_film.py")]
