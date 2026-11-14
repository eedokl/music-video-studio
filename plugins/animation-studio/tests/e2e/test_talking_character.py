"""talking-character: two short lines with the Windows system voice -> make.py (speak, scene, subtitles, sounds, film,
sync check). Whisper's line check runs on the CPU (WHISPER_CPU=1, small model from the local cache)."""
import os

from common import FPS, Test, Skip, expect, expect_film, full, need, read_json, script, write_json

NEW = script("talking-character", "new_talk.py")
MAKE = script("talking-character", "make.py")

DIALOGUE = "Tim: (to computer) Hallo Computer!\nComputer: (screen \"HALLO\") Guten Abend, Tim.\n"


def run_talk(ctx):
    if os.name != "nt":
        raise Skip("the 'system' voice engine is Windows speech (System.Speech) - not available here")
    need("ffmpeg", "synfig", "rhubarb")
    d = ctx.dir / "talk"
    (ctx.dir / "dialogue.txt").write_text(DIALOGUE, encoding="utf-8")
    ctx.uv(NEW, d, "--script", ctx.dir / "dialogue.txt", "--set", "room", "--seed", "11")
    P = read_json(d / "project.json")
    P["look"] = "standard" if full() else "none"                         # the look is checked by other tests
    write_json(d / "project.json", P)
    ctx.uv(MAKE, "--project", d, "--engine", "system", "--jobs", "8", timeout=1500)
    P = read_json(d / "project.json")
    secs = P.get("sections") or []
    expect(secs, "speak.py wrote no section into project.json")
    n = sum(round(s["to"] * FPS) - round(s["from"] * FPS) for s in secs)
    expect_film(ctx, d / "film.mp4", n)
    dia = read_json(d / "analysis" / "dialogue.json")
    lines = dia.get("lines", dia) if isinstance(dia, dict) else dia
    expect(len(lines) == 2, f"analysis/dialogue.json has {len(lines)} lines, the script 2")
    sync = read_json(d / "analysis" / "sync_check.json")
    ctx.log(f"sync_check: {sync}")
    agree = [v.get("agreement") for v in (sync.get("figures") or sync).values() if isinstance(v, dict) and "agreement" in v]
    expect(agree and min(agree) >= 0.6, f"lip-sync agreement {agree} (< 0.6: mouths and voices do not match)")
    ctx.note(f"{n} frames ({secs[0]['to']:.2f} s), 2 lines (system voice), lip-sync agreement {', '.join(f'{a:.2f}' for a in agree)}")


TESTS = [Test("talking-character", run_talk, about="new_talk.py + make.py --engine system through film and check_sync")]
