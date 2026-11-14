"""film-finish cut.py: title card + still + two clips (one with a dissolve on real handles) + music bed + title ->
film.mp4 / film_small / film_mail, report, shot list, OTIO."""
from common import FPS, Test, expect, expect_film, need, read_json, script, tone, write_json

CUT = script("film-finish", "cut.py")


def run_cut(ctx):
    need("ffmpeg")
    d = ctx.dir
    for name, f in (("a.mp4", 440), ("b.mp4", 550)):
        ctx.ff("-f", "lavfi", "-i", "testsrc2=s=1280x720:r=24", "-f", "lavfi", "-i", f"sine=f={f}:r=48000",
               "-frames:v", "48", "-shortest", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", d / name)
    ctx.ff("-f", "lavfi", "-i", "smptebars=s=1280x720", "-frames:v", "1", d / "still.png")
    tone(ctx, d / "music.wav", 6.0, freq=196)
    plan = {"name": "E2E cut", "fps": FPS, "size": [1280, 720], "out": "film",
            "shots": [{"card": "E2E", "sub": "end-to-end test", "frames": 36},
                      {"src": "a.mp4", "frames": 24},
                      {"src": "still.png", "frames": 30, "zoom": [1.0, 1.05]},
                      {"src": "b.mp4", "in": 12, "frames": 24, "transition": {"kind": "dissolve", "frames": 8}}],
            "music": {"file": "music.wav", "level_db": -6, "fade_out": 0.5},
            "title": {"text": "E2E", "from": 0.2, "to": 1.2}, "look": "standard"}
    write_json(d / "cut.json", plan)
    ctx.uv(CUT, d / "cut.json", timeout=900)
    total = 36 + 24 + 30 + 24                       # dissolve on real handles: the timeline does not move
    expect_film(ctx, d / "film.mp4", total)
    rep = read_json(d / "film_report.json")
    expect(rep.get("frames") == total and abs(rep.get("seconds", 0) - total / FPS) < 1e-3,
           f"report frames/seconds {rep.get('frames')}/{rep.get('seconds')}, expected {total}")
    files = rep.get("files", {})
    for f in ("film.mp4", "film_small.mp4", "film_mail.mp4"):
        expect(f in files and files[f].get("decode_errors") == 0, f"report: {f} {files.get(f)}")
    for f, mb in (("film_small.mp4", 29.0), ("film_mail.mp4", 12.0)):
        expect(files[f].get("target_mb") == mb and files[f].get("over_target") is False,
               f"report size target of {f}: {files[f]}")
    expect(rep.get("music", {}).get("mode"), f"report has no music mode: {rep.get('music')}")
    shots = read_json(d / "film_shots.json")
    starts = [s["start"] for s in shots["shots"]]
    expect(starts == [0, 36, 60, 90], f"shot starts {starts}, expected [0, 36, 60, 90]")
    for f in ("film_sheet.png", "film.otio"):
        expect((d / f).exists(), f"{f} missing")
    ctx.note(f"{total} frames, report frames/seconds/size targets ok, shot starts {starts}, OTIO written")


TESTS = [Test("film-finish-cut", run_cut, about="cut.py: card + still + clips + dissolve + music + title -> film + report")]
