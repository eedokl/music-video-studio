"""lyric-music-video: new_video.py (--no-install) + synthetic analysis (timing.json, hits.json instead of Whisper) ->
install_data.py -> render.py final (tsc, three.js engine in headless Chrome, frame-exact) + the delivery versions.

The engine needs node_modules (npm install = a download), so this test only runs when an existing node_modules of
the engine template is named in the environment variable ANIMATION_STUDIO_E2E_NODE_MODULES; its packages are linked
into the temp project (junctions / symlinks, removed before cleanup) - otherwise SKIP."""
import os
import shutil
from pathlib import Path

from common import (Skip, Test, audio_seconds, check_video, expect, has_audio, link_tree, need, script, tone,
                    unlink_links, video_frames, write_json)

NEW = script("lyric-music-video", "new_video.py")
INSTALL = script("lyric-music-video", "install_data.py")
RENDER = script("lyric-music-video", "render.py")
SONG, FPS = 3.0, 12


def run_lyric(ctx):
    nm = os.environ.get("ANIMATION_STUDIO_E2E_NODE_MODULES")
    if not nm or not (Path(nm) / "vite").is_dir() or not (Path(nm) / "three").is_dir():
        raise Skip("needs node_modules of the engine template (npm install = download): set "
                   "ANIMATION_STUDIO_E2E_NODE_MODULES=<an existing lyric-video project>/video/node_modules")
    need("ffmpeg")
    if not shutil.which("node") or not (shutil.which("npx") or shutil.which("npx.cmd")):
        raise Skip("node / npx not on PATH (render.py runs them by name)")
    song = tone(ctx, ctx.dir / "song.wav", SONG)
    lyr = ctx.dir / "lyrics.txt"
    lyr.write_text("[Chorus]\nLights on the stage\nwe sing tonight\n", encoding="utf-8")
    d = ctx.dir / "lv"
    ctx.uv(NEW, d, "--song", song, "--lyrics", lyr, "--language", "en", "--seed", "3", "--no-install")
    write_json(d / "analysis" / "timing.json", [
        {"t": 0.3, "e": 1.4, "words": [0.3, 0.6, 0.8, 1.0], "ends": [0.6, 0.8, 1.0, 1.4]},
        {"t": 1.6, "e": 2.8, "words": [1.6, 1.9, 2.2], "ends": [1.9, 2.2, 2.8]}])
    write_json(d / "analysis" / "hits.json", {"hits": [0.5, 1.0, 1.5, 2.0, 2.5], "big": [1.0, 2.0], "bpm": 120.0,
                                              "offset": 0.0})
    ctx.uv(INSTALL, d)
    # node_modules as a real folder of links (vite writes its .vite cache there, never into the linked one)
    link = d / "video" / "node_modules"
    link_tree(link, nm)
    extra = ""
    try:
        ctx.uv(RENDER, d, "final", "--fps", str(FPS), "--title", "e2e", timeout=900)
        # 0.11.0: sheet without --times (was a crash), clip --sheet (every frame), a page that fails to load stops
        # the render at once instead of after the 180 s timeout
        ctx.uv(RENDER, d, "sheet", "out/e2e.mp4", timeout=300)
        expect((d / "out" / "e2e.jpg").exists(), "sheet without --times wrote no out/e2e.jpg")
        ctx.uv(RENDER, d, "clip", "--from", "0.5", "--to", "1.5", "--fps", "6", "--sheet", timeout=600)
        expect((d / "out" / "clip_0.5-1.5_frames_1.jpg").exists(), "clip --sheet wrote no frame sheet")
        main_ts = d / "video" / "src" / "main.ts"
        good = main_ts.read_text(encoding="utf-8")
        main_ts.write_text(good + "\nthrow new Error('e2e: broken on purpose');\n", encoding="utf-8")
        import time
        t0 = time.time()
        r = ctx.uv(RENDER, d, "clip", "--from", "0", "--to", "1", "--fps", "2", timeout=170, check=False)
        dt = time.time() - t0
        main_ts.write_text(good, encoding="utf-8")
        expect(r.returncode != 0, "a page error at load did not fail the render")
        expect(dt < 120, f"a page error at load took {dt:.0f} s to fail (should stop at once, not wait for the timeout)")
        extra = f", sheet + clip --sheet ok, page error stops after {dt:.0f} s"
    finally:
        unlink_links(link)                                  # the links only - never the linked node_modules
    out = d / "out"
    for name in ("e2e.mp4", "e2e_compressed.mp4", "e2e_small.mp4", "e2e_mail.mp4"):
        f = out / name
        expect(f.exists(), f"out/{name} missing")
        err = check_video(f)
        expect(not err and has_audio(f), f"out/{name}: decode errors {err[:200]} / audio {has_audio(f)}")
    n = video_frames(out / "e2e.mp4")
    want = round(SONG * FPS)
    expect(abs(n - want) <= 1, f"e2e.mp4: {n} frames at {FPS} fps, the song needs {want}")
    a = audio_seconds(out / "e2e.mp4")
    expect(abs(a - SONG) < 0.15, f"e2e.mp4 audio {a:.2f} s, song {SONG} s")
    ctx.note(f"tsc ok, {n} frames at {FPS} fps for {SONG} s, 4 files decode, audio {a:.2f} s{extra}")


TESTS = [Test("lyric-music-video", run_lyric, slow=True,
              about="new_video + synthetic timing/hits -> install_data -> render.py final (needs linked node_modules)")]
