"""portal-music-video: a song project with synthetic analysis (timing.json, hits.json, lyrics_clean.txt, markers.json
instead of Whisper) -> new_flight.py --no-install (engine + starter worlds, song.js, the song cut into parts) ->
flight.py check --cpu (every portal crossing measured in a headless browser, one picture per world) ->
flight.py clip + final --cpu (frame-exact render by the software renderer, x264, the delivery copies).

The flight needs three and puppeteer-core (npm install = a download), so this test only runs when an existing
node_modules is named in ANIMATION_STUDIO_E2E_NODE_MODULES (the one of a lyric-video project has both); its packages
are linked into the temp project and unlinked afterwards - otherwise SKIP. Nothing touches the graphics card."""
import json
import os
import shutil
from pathlib import Path

from common import (Skip, Test, audio_seconds, check_video, expect, has_audio, link_tree, need, script, tone,
                    unlink_links, video_frames, write_json)

NEW = script("portal-music-video", "new_flight.py")
FLIGHT = script("portal-music-video", "flight.py")
SONG, FPS, BPM = 16.0, 6, 120.0


def run_portal(ctx):
    nm = os.environ.get("ANIMATION_STUDIO_E2E_NODE_MODULES")
    if not nm or not (Path(nm) / "three").is_dir() or not (Path(nm) / "puppeteer-core").is_dir():
        raise Skip("needs node_modules with three and puppeteer-core (npm install = download): set "
                   "ANIMATION_STUDIO_E2E_NODE_MODULES=<an existing lyric-video or portal project>/.../node_modules")
    need("ffmpeg")
    if not shutil.which("node"):
        raise Skip("node not on PATH")
    cfg = json.loads(Path(os.environ["ANIMATION_STUDIO_CONFIG"]).read_text(encoding="utf-8"))
    if not any(cfg.get(k) and Path(cfg[k]).exists() for k in ("chrome", "browser")) and not os.environ.get("ANIMATION_STUDIO_CHROME"):
        raise Skip("no Chrome/Edge configured (check_tools.py --set chrome=PATH)")
    d = ctx.dir / "pf"
    d.mkdir()
    tone(ctx, d / "song.wav", SONG)
    (d / "lyrics.txt").write_text("[Verse]\nLights on the stage\nwe sing tonight\n[Chorus]\nfly through the gate\n", encoding="utf-8")
    write_json(d / "project.json", {"name": "e2e flight", "kind": "lyric-music-video", "fps": 30, "lyrics": "lyrics.txt",
                                    "language": "en", "seed": 3, "ideas": []})
    (d / "analysis").mkdir()
    (d / "analysis" / "lyrics_clean.txt").write_text("Lights on the stage\nwe sing tonight\nfly through the gate\n", encoding="utf-8")
    write_json(d / "analysis" / "markers.json", [{"line": 0, "marker": "Verse"}, {"line": 2, "marker": "Chorus"}])
    write_json(d / "analysis" / "timing.json", [
        {"t": 0.9, "e": 2.4, "words": [0.9, 1.3, 1.6, 1.9], "ends": [1.3, 1.6, 1.9, 2.4]},
        {"t": 4.0, "e": 5.6, "words": [4.0, 4.5, 5.0], "ends": [4.5, 5.0, 5.6]},
        {"t": 7.9, "e": 10.0, "words": [7.9, 8.4, 8.9, 9.3], "ends": [8.4, 8.9, 9.3, 10.0]}])
    write_json(d / "analysis" / "hits.json", {"hits": [2.0, 4.0, 6.0, 8.0], "big": [8.0], "bpm": BPM, "offset": 0.0})
    r = ctx.uv(NEW, d, "--no-install")
    song_js = (d / "flight" / "src" / "song.js").read_text(encoding="utf-8")
    expect("export const BPM = 120;" in song_js and '"LIGHTS"' in song_js, "song.js lacks the beat grid or the words")
    # the chorus starts with its first word at 7.9 s -> the bar line at 8.0 s = beat 16: two parts of 16 beats
    parts = [json.loads(ln.strip().rstrip(",")) for ln in song_js.split("export const SECTIONS = [")[1].split("];")[0].splitlines() if ln.strip()]
    expect([p["beats"] for p in parts] == [16, 16] and parts[0]["lines"] == [0, 1] and parts[1]["lines"] == [2],
           f"the song was cut into {parts}, expected two parts of 16 beats (lines 0-1 and 2)")
    expect(json.loads((d / "project.json").read_text(encoding="utf-8")).get("flight") == "flight", "project.json has no \"flight\"")
    # a second run keeps the worlds and what was added below the marker line of song.js
    (d / "flight" / "src" / "song.js").write_text(song_js + "export const FONT_FLAT = '900 200px Arial';\n", encoding="utf-8")
    ctx.uv(NEW, d, "--no-install")
    expect("FONT_FLAT" in (d / "flight" / "src" / "song.js").read_text(encoding="utf-8"), "new_flight.py dropped what stood below the marker line")
    link = d / "flight" / "node_modules"
    link_tree(link, nm)
    try:
        r = ctx.uv(FLIGHT, d, "check", "--cpu", timeout=900)
        expect("SEAM" not in r.stdout and "PAGE ERROR" not in r.stdout, f"check found a seam or a page error:\n{r.stdout[-800:]}")
        expect((d / "out" / "flight_check.jpg").exists(), "check wrote no out/flight_check.jpg")
        rep = json.loads((d / "flight" / "out" / "check" / "check.json").read_text(encoding="utf-8"))
        expect(len(rep["worlds"]) == 2 and abs(rep["total"] - SONG) < 0.01, f"check saw {len(rep['worlds'])} worlds, {rep['total']} s")
        ctx.uv(FLIGHT, d, "clip", "--from", "7", "--to", "9", "--cpu", "--fps", str(FPS), "--size", "640x360", "--workers", "1", timeout=900)
        clip = d / "out" / "clip_7-9.mp4"
        expect(clip.exists() and not check_video(clip) and has_audio(clip), "clip_7-9.mp4 missing, broken or silent")
        ctx.uv(FLIGHT, d, "final", "--title", "e2e", "--cpu", "--fps", str(FPS), "--size", "640x360", "--workers", "2", timeout=1500)
        # a page that fails to load stops at once, with exit code 3 and the error named
        world = d / "flight" / "src" / "worlds" / "gate_wire.js"
        good = world.read_text(encoding="utf-8")
        world.write_text(good + "\nthrow new Error('e2e: broken on purpose');\n", encoding="utf-8")
        bad = ctx.uv(FLIGHT, d, "check", "--cpu", timeout=300, check=False)
        world.write_text(good, encoding="utf-8")
        expect(bad.returncode == 3 and "broken on purpose" in (bad.stderr + bad.stdout), f"a broken world gave exit {bad.returncode}, not 3 with the error")
    finally:
        unlink_links(link)                                  # the links only - never the linked node_modules
    out = d / "out"
    for name in ("e2e.mp4", "e2e_small.mp4", "e2e_mail.mp4"):
        f = out / name
        expect(f.exists(), f"out/{name} missing")
        err = check_video(f)
        expect(not err and has_audio(f), f"out/{name}: decode errors {err[:200]} / audio {has_audio(f)}")
    n = video_frames(out / "e2e.mp4")
    want = round(SONG * FPS)
    expect(abs(n - want) <= 1, f"e2e.mp4: {n} frames at {FPS} fps, the song needs {want}")
    a = audio_seconds(out / "e2e.mp4")
    expect(abs(a - SONG) < 0.15, f"e2e.mp4 audio {a:.2f} s, song {SONG} s")
    ctx.note(f"song cut into 2 parts on the bar line, crossing seamless, clip + {n} frames at {FPS} fps on the software "
             f"renderer, 3 files decode, audio {a:.2f} s, a broken world stops with exit 3")


TESTS = [Test("portal-music-video", run_portal, slow=True,
              about="synthetic analysis -> new_flight -> flight.py check / clip / final --cpu (needs linked node_modules + a browser)")]
