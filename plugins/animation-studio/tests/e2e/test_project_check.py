"""Project settings: a bad project.json is rejected up front (studio-core project_check.py, exit code 2, before any
render), and project.json "size" changes the frame size of an animated-music-video film."""
import re
import struct
import subprocess
import time

from common import (FPS, Test, expect, expect_film, ffmpeg, full, need, read_json, script, song_sheet, assignment,
                    tone, write_json)

CHECK = script("studio-core", "project_check.py")
SCENE = script("animated-music-video", "scene.py")
OVERLAYS = script("film-finish", "overlays.py")
BUILD = script("film-finish", "build.py")
MAKE = script("talking-character", "make.py")
NEW = script("song-analysis", "new_project.py")
WORDS = [("Hello", 0.30, 0.70, 0), ("tokens", 0.75, 1.20, 0), ("over", 1.25, 1.55, 0), ("the", 1.55, 1.70, 0),
         ("limit", 1.75, 2.30, 0), ("now", 2.35, 2.80, 0)]


def rejected(ctx, label, cmd, wants, limit=30):
    """cmd must stop with exit code 2 within `limit` s and print every regex of `wants`."""
    t0 = time.time()
    r = ctx.run(cmd, check=False, timeout=120)
    dt = time.time() - t0
    expect(r.returncode == 2, f"{label}: exit code {r.returncode}, expected 2 (rejected):\n{r.stdout[-600:]}")
    for w in wants:
        expect(re.search(w, r.stdout), f"{label}: message /{w}/ missing in:\n{r.stdout[-900:]}")
    expect(dt < limit, f"{label}: took {dt:.1f} s to reject (> {limit} s)")
    return dt


def run_bad_project(ctx):
    # a song project: "sounds" as a string, overlapping sections, a typo'd key, an unknown transition kind
    song = ctx.dir / "song"
    write_json(song / "project.json", {
        "name": "bad", "fps": 24, "seed": 1,
        "figures": {"tim": {"svg": "skill:characters/assets/figures/tim.svg", "voice": "male"}},
        "sections": [{"name": "a", "from": 0.0, "to": 2.0, "figures": ["tim"]},
                     {"name": "b", "from": 1.5, "to": 3.0, "figures": ["tim"]}],
        "sounds": "pop", "gags": [{"text": "NO WORD"}], "transitions": [{"at": 2.0, "kind": "glwo"}],
        "titel": {"text": "x", "from": 0, "to": 1}})
    want_song = [r'ERROR: sounds: expected true / false, one rule .* got a string \("pop"\)',
                 r"ERROR: sections\[1\] \(b\): overlaps sections\[0\] \(a\)",
                 r'ERROR: gags\[0\]: needs "word"', r'transitions\[0\]\.kind: "glwo" is not one of .*did you mean "glow"',
                 r'WARNING: titel: unknown key - did you mean "title"']
    times = [rejected(ctx, "project_check.py", ["uv", "run", "--offline", CHECK, song], want_song),
             rejected(ctx, "scene.py --render", ["uv", "run", "--offline", SCENE, "a", "--project", song, "--render"],
                      want_song[:2]),
             rejected(ctx, "build.py film", ["uv", "run", "--offline", BUILD, "film", "--project", song], want_song[:2])]
    expect(not (song / "scenes").exists() and not (song / "film.mp4").exists(), "something was rendered before the check")

    # a talking scene: a figure voiced "male" (a singing role) instead of a voice of the cast
    talk = ctx.dir / "talk"
    (talk).mkdir(parents=True, exist_ok=True)
    (talk / "dialogue.txt").write_text("Tim: Hallo!\n", encoding="utf-8")
    write_json(talk / "project.json", {
        "name": "talk", "fps": 24, "script": "dialogue.txt", "set": "room", "seed": 2,
        "figures": {"tim": {"svg": "skill:characters/assets/figures/tim.svg", "voice": "male"}}})
    times.append(rejected(ctx, "talking-character make.py", ["uv", "run", "--offline", MAKE, "--project", talk],
                          [r'ERROR: figures\.tim\.voice: "male" is not a voice of the cast - use one of .*tim',
                           r'add "male" to project\.json "voices"']))
    expect(not (talk / "lines").exists() and not (talk / "song.wav").exists(), "voices were made before the check")

    # a slide clip whose narration speaker has no mouth block in parts.json
    deck = ctx.dir / "deck"
    write_json(deck / "figures" / "fritz" / "parts.json", {"parts": []})
    write_json(deck / "clips" / "c1" / "clip.json", {
        "deck": "../../deck/deck.json", "slide": 5, "figures_dir": "../../figures",
        "figures": [{"name": "fritz", "action": "step_out"}],
        "narration": [{"id": "l1", "audio": "l1.wav", "speaker": "fritz"}]})
    times.append(rejected(ctx, "slide clip.json", ["uv", "run", "--offline", CHECK, deck / "clips" / "c1" / "clip.json"],
                          [r'ERROR: narration speaker fritz: figure "fritz" talks but parts\.json has no "mouth" block']))

    # the same projects fixed: no error (exit 0)
    P = read_json(song / "project.json")
    P.update({"sounds": False, "gags": [{"word": "token", "text": "T!"}], "transitions": [{"at": 2.0, "kind": "glow"}]})
    P["sections"][1]["from"] = 2.0
    P["title"] = P.pop("titel")
    write_json(song / "project.json", P)
    r = ctx.run(["uv", "run", "--offline", CHECK, song], check=False)
    expect(r.returncode == 0 and "0 error(s), 0 warning(s)" in r.stdout, f"fixed song project not clean:\n{r.stdout[-600:]}")
    ctx.note(f"rejected with exit 2 in {min(times):.1f}-{max(times):.1f} s (CLI, scene.py, build.py, make.py, clip.json), "
             f"nothing rendered; fixed project clean")


def video_size(path):
    r = subprocess.run([ffmpeg(), "-hide_banner", "-i", str(path)], capture_output=True, text=True, errors="replace")
    m = re.search(r"Video:.*?, (\d{2,5})x(\d{2,5})", r.stderr)
    return (int(m.group(1)), int(m.group(2))) if m else None


def run_size(ctx):
    need("ffmpeg", "synfig")
    song = tone(ctx, ctx.dir / "song.wav", 3.0)
    lyr = ctx.dir / "lyrics.txt"
    lyr.write_text("[Chorus]\n" + " ".join(w for w, *_ in WORDS) + "\n", encoding="utf-8")
    proj = ctx.dir / "small"
    ctx.uv(NEW, proj, "--song", song, "--lyrics", lyr, "--language", "en")
    write_json(proj / "analysis" / "song_sheet.json", song_sheet(3.0, WORDS))
    write_json(proj / "analysis" / "assignment.json", assignment(["tim", "lia"], {"tim": [(0.3, 1.2)], "lia": [(1.25, 2.8)]}))
    P = read_json(proj / "project.json")
    S, E = 0.0, (2.48 if full() else 1.48)
    P["sections"] = [{"name": "chorus", "from": S, "to": E, "set": "stage", "figures": ["tim", "lia"], "dance": "always",
                      "lyrics": True}]
    P.update({"size": [640, 360], "seed": 99, "sounds": False, "gags": [{"word": "tokens", "text": "TOKENS!"}],
              "title": {"text": "SIZE", "from": 0.1, "to": 1.2, "place": "top"},
              "look": "standard" if full() else "none"})
    write_json(proj / "project.json", P)
    ctx.uv(SCENE, "chorus", "--project", proj, "--render", "--jobs", "8", timeout=1200)
    frame0 = sorted((proj / "scenes" / "chorus").glob("f.*.png"))[0]
    head = frame0.read_bytes()[:24]
    got = struct.unpack(">II", head[16:24])
    expect(got == (640, 360), f"scene frames are {got[0]}x{got[1]}, expected 640x360 (Synfig canvas from project size)")
    ctx.uv(OVERLAYS, "chorus", "--project", proj)
    ctx.uv(BUILD, "film", "--project", proj, timeout=900)
    n = round(E * FPS) - round(S * FPS)
    expect_film(ctx, proj / "film.mp4", n)
    for v in ("film.mp4", "film_small.mp4", "film_mail.mp4"):
        sz = video_size(proj / v)
        expect(sz == (640, 360), f"{v} is {sz}, expected 640x360")
    # frames rendered for other times are reported (warning, exit 0)
    P["sections"][0]["to"] = E + 1.0
    write_json(proj / "project.json", P)
    r = ctx.run(["uv", "run", "--offline", CHECK, proj], check=False)
    expect(r.returncode == 0 and re.search(r"WARNING: sections\[0\] \(chorus\): scenes/chorus/ has \d+ frames, but", r.stdout),
           f"no frame-count warning after changing 'to':\n{r.stdout[-600:]}")
    ctx.note(f"640x360 frames, film/small/mail 640x360, {n} frames = round({E}*24)-round({S}*24); stale frames warned")


TESTS = [
    Test("project-check", run_bad_project, about="bad project.json (sounds string, overlapping sections, voice 'male' "
                                                 "in a talking scene) rejected with exit 2 before any render"),
    Test("project-size", run_size, about='animated-music-video with "size": [640, 360]: frames, film versions, frame count'),
]
