"""animated-short: a new short from the blank template -> make_scene.py -> short.py finish (render, sound cues, look,
GIF, contact sheet)."""
import re

from common import (Test, audio_samples, expect, expect_film, loudest, need, read_json, script, write_json)

SHORT = script("animated-short", "short.py")


def run_short(ctx):
    need("ffmpeg", "synfig", "earshot")
    d = ctx.dir / "hop"
    ctx.uv(SHORT, "new", d, "--title", "E2E hop", "--template", "blank", "--seed", "4711",
           "--principles", "anticipation,squash")
    ctx.uv(SHORT, "idea", d, "Pip hops once and lands with a squash")
    ctx.uv(SHORT, "variant", d, "landing", "soft", "hard")
    S = read_json(d / "short.json")
    expect(S.get("seed") == 4711 and len(S.get("ideas", [])) == 2, f"short.json seed/ideas wrong: {S}")
    ms = d / "make_scene.py"
    expect(ms.exists() and (d / "_toon.py").exists(), "short.py new wrote no make_scene.py / _toon.py")
    src = ms.read_text(encoding="utf-8")
    m = re.search(r"FPS, END = 24, (\d+)", src)
    expect(m, "blank template: 'FPS, END = 24, <frames>' not found")
    end = 96                                              # 4 s instead of the template's 5 s
    ms.write_text(src.replace(m.group(0), f"FPS, END = 24, {end}"), encoding="utf-8")
    ctx.run(["uv", "run", "--offline", ms], cwd=d)
    sif = d / "scene.sif"
    expect(sif.exists(), "make_scene.py wrote no scene.sif")
    land = 58                                             # the template's hop lands on frame 58
    write_json(d / "sfx_cues.json", {"end": end, "cues": [{"frame": land, "sfx": "ui_pop/soft", "level": -8,
                                                           "what": "landing"}]})
    ctx.uv(SHORT, "finish", d, "--sif", sif, "--contact", f"0,40,49,{land}", "--jobs", "6", timeout=900)
    final = d / "final" / "scene.mp4"
    frames = end + 1                                      # Synfig renders frames 0..END
    expect_film(ctx, final, frames, tol_audio=0.6)
    for f in ("scene.gif", "contact.png"):
        expect((d / "final" / f).exists(), f"final/{f} missing")
    t, peak = loudest(audio_samples(final), 48000, (land - 12) / 24, (land + 12) / 24)
    expect(abs(t - land / 24) <= 1.5 / 24, f"landing sound peaks at {t:.3f} s, its frame {land} is {land / 24:.3f} s")
    fin = str(read_json(d / "short.json").get("final", "")).replace("\\", "/")     # short.py stores an OS path
    expect(fin == "final/scene.mp4", f"short.json final = {fin!r}, expected final/scene.mp4")
    ctx.note(f"{frames} frames (0..{end}), landing sound peak {t:.3f} s on frame {land}, gif + contact sheet")


TESTS = [Test("animated-short", run_short, about="short.py new (blank) -> make_scene.py -> short.py finish")]
