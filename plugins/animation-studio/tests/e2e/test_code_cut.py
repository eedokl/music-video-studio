"""film-finish code_cut.py: a work folder with two stills and one take (numbered frames) -> check, render in the
headless browser, film on the song; a cut off the beat grid and a missing `why` are refused with exit code 2."""
from common import FPS, Test, expect, expect_film, need, script, tone, write_json

CODE_CUT = script("film-finish", "code_cut.py")


def edit(parts):
    return {"fps": FPS, "frames": 72, "size": [1280, 720], "worlds": {"a": {"accent": "#FFD23F", "tracker": "TAKE"}},
            "accents": {"0": "beat"}, "chrome": {"label": "E2E", "meter": {"title": "METER", "k0": 0, "k1": 72}},
            "overlays": [{"type": "shout", "k0": 24, "k1": 36, "text": "HEY!"}],
            "shots": [{"id": "s01", "k0": 0, "k1": 72, "world": "a", "scene": "E2E", "parts": parts}]}


PARTS = [{"k0": 0, "k1": 24, "kind": "still", "src": "stills/a.png", "cam": {"z": [1.0, 1.1]}, "why": "opening still"},
         {"k0": 24, "k1": 48, "kind": "take", "src": "t1", "cam": {"z": [1.0, 1.05]}, "why": "the take on the second bar"},
         {"k0": 48, "k1": 72, "kind": "still", "src": "stills/b.png", "tag": {"text": "TAG", "at": [0.6, 0.4]},
          "why": "closing still"}]


def run_code_cut(ctx):
    need("ffmpeg", "node", "browser")
    d = ctx.dir
    (d / "stills").mkdir()
    (d / "frames" / "t1").mkdir(parents=True)
    ctx.ff("-f", "lavfi", "-i", "smptebars=s=1280x704", "-frames:v", "1", d / "stills" / "a.png")
    ctx.ff("-f", "lavfi", "-i", "testsrc=s=1280x704", "-frames:v", "1", d / "stills" / "b.png")
    ctx.ff("-f", "lavfi", "-i", "testsrc2=s=1280x704:r=24", "-frames:v", "30", "-q:v", "3", d / "frames" / "t1" / "%04d.jpg")
    tone(ctx, d / "song.wav", 3.0)
    write_json(d / "song.json", {"t0": 0.0, "fps": FPS, "frames": 72, "beats_k": [0, 12, 24, 36, 48, 60],
                                 "kick": [1, 0, 1, 0, 1, 0],
                                 "lines": [{"i": 0, "text": "on the beat", "k0": 26, "k1": 46,
                                            "words": [{"w": "on", "k0": 26, "k1": 30}, {"w": "the", "k0": 30, "k1": 34},
                                                      {"w": "beat", "k0": 34, "k1": 46}]}]})
    write_json(d / "clips.json", {"t1": {"fps": 24, "frames": 30, "song_start": 0.9, "delay_frames": 0,
                                         "faces": [[0.4, 0.2, 0.2, 0.4]] * 30}})
    write_json(d / "edit.json", edit(PARTS))
    ctx.uv(CODE_CUT, "check", d)
    ctx.uv(CODE_CUT, "render", d, "--song", d / "song.wav", "--out", d / "film.mp4", timeout=600)
    expect_film(ctx, d / "film.mp4", 72)
    r = ctx.uv(CODE_CUT, "render", d, "--song", d / "song.wav", "--out", d / "film.mp4", check=False)
    expect(r.returncode != 0, "a second render onto the same file must be refused")
    ctx.uv(CODE_CUT, "sheet", d, d / "sheet.jpg", "10", "30", "60")
    expect((d / "sheet.jpg").exists(), "sheet.jpg missing")
    bad = [dict(p) for p in PARTS]
    bad[0]["k1"] = bad[1]["k0"] = 25                       # neither a beat nor a word onset
    bad[2].pop("why")
    write_json(d / "edit.json", edit(bad))
    r = ctx.uv(CODE_CUT, "check", d, check=False)
    out = (r.stdout or "") + (r.stderr or "")
    expect(r.returncode == 2 and "neither a beat nor a word onset" in out and "has no why" in out,
           f"broken edit: exit {r.returncode}, output {out[-300:]}")
    ctx.note("check ok, 72 frames rendered and joined with the song, overwrite refused, broken edit refused with exit 2")


TESTS = [Test("code-cut", run_code_cut, about="code_cut.py: stills + take + code layer in the headless browser -> film; rules enforced")]
