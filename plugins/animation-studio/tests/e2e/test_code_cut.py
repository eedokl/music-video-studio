"""film-finish code_cut.py: a work folder with two stills and one take (numbered frames) -> check, render in the
headless browser, film on the song; a cut off the beat grid and a missing `why` are refused with exit code 2.
The small pieces (stamp, check, sight, rings, cards behind a mask, flip, quote, struck list, dust, iris) are drawn in
the same render; a stamp that stands too short gives a note, an unknown overlay type is refused."""
from common import FPS, Test, expect, expect_film, need, script, tone, write_json

CODE_CUT = script("film-finish", "code_cut.py")


def edit(parts):
    return {"fps": FPS, "frames": 72, "size": [1280, 720],
            "worlds": {"a": {"accent": "#FFD23F", "tracker": "TAKE", "dust": True}},
            "accents": {"0": "beat"}, "chrome": {"label": "E2E", "meter": {"title": "METER", "k0": 0, "k1": 72}},
            "iris": {"k0": 60, "k1": 72, "c": [0.5, 0.4], "r": 150},
            "overlays": [{"type": "shout", "k0": 24, "k1": 36, "text": "HEY!"},
                         {"type": "stamp", "k0": 2, "k1": 14, "text": "TOO SHORT AND MUCH TOO LONG FOR ITS PLACE", "x": 1100, "y": 200},
                         {"type": "counter", "k0": 0, "k1": 24, "x": 60, "y": 400, "from": 1234567, "to": 1234567,
                          "locale": "de-DE"},
                         {"type": "list", "k0": 0, "k1": 24, "x": 60, "y": 120, "title": "LIST", "numbers": False,
                          "items": [{"text": "one", "k": 2, "strike": 10}, {"text": "two", "k": 6}]},
                         {"type": "cards", "k0": 24, "k1": 48, "from": [200, 400], "n": 8, "behind": True},
                         {"type": "sight", "k0": 26, "k1": 46, "from": [640, 250], "to": [200, 230]},
                         {"type": "rings", "k0": 30, "k1": 46, "point": [900, 500]},
                         {"type": "check", "k0": 32, "k1": 48, "x": 820, "y": 200,
                          "words": [{"text": "ALL", "k": 34}, {"text": "FINE.", "k": 38, "accent": True}], "sub": "1 STEP"},
                         {"type": "flip", "k0": 48, "k1": 60, "k": 54, "from": {"label": "TODAY", "text": "2026"},
                          "to": {"label": "NEXT YEAR", "text": "2027"}},
                         {"type": "quote", "k0": 48, "k1": 60, "lines": ["a line to be read,", "and a second one"],
                          "mark": "to be read", "source": "- E2E"}],
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
    (d / "masks" / "t1").mkdir(parents=True)                # what near_masks.py writes: alpha = near (here: the right half)
    ctx.ff("-f", "lavfi", "-i", "color=white:s=640x352:r=24,format=rgba,geq=r=255:g=255:b=255:a='if(gt(X,320),255,0)'",
           "-frames:v", "30", d / "masks" / "t1" / "%04d.png")
    write_json(d / "clips.json", {"t1": {"fps": 24, "frames": 30, "song_start": 0.9, "delay_frames": 0, "masks": True,
                                         "faces": [[0.4, 0.2, 0.2, 0.4]] * 30}})
    write_json(d / "edit.json", edit(PARTS))
    r = ctx.uv(CODE_CUT, "check", d)
    out = (r.stdout or "") + (r.stderr or "")
    expect("NOTE: stamp at 2 stands" in out, f"a stamp of half a second must give a note: {out[-300:]}")
    ctx.uv(CODE_CUT, "render", d, "--song", d / "song.wav", "--out", d / "film.mp4", timeout=600)
    expect_film(ctx, d / "film.mp4", 72)
    r = ctx.uv(CODE_CUT, "render", d, "--song", d / "song.wav", "--out", d / "film.mp4", check=False)
    expect(r.returncode != 0, "a second render onto the same file must be refused")
    ctx.uv(CODE_CUT, "sheet", d, d / "sheet.jpg", "10", "30", "40", "52", "56", "66", "--grid")
    expect((d / "sheet.jpg").exists(), "sheet.jpg missing")
    expect((d / "last_render.json").exists(), "last_render.json (the current film) missing")
    edge = ctx.py("""
import sys
from PIL import Image
im = Image.open(sys.argv[1]).convert("RGB").crop((1272, 100, 1280, 360))       # the last 8 px at the right edge
b = im.tobytes()
print('RED', sum(1 for i in range(0, len(b), 3) if b[i] > 200 and b[i + 1] < 110 and b[i + 2] < 80))
""", deps_from=[CODE_CUT], name="edge.py", args=[d / "png" / "f_00008.png"])
    expect("RED 0" in (edge.stdout or ""),
           f"a stamp that is too long for its place must stay inside the frame: {edge.stdout!r}")
    cut = ctx.py("""
import sys
from PIL import Image
im = Image.open(sys.argv[1]).convert("RGB")
print(sum(im.getpixel((x, y)) == (0, 0, 0) for x in (5, 1275) for y in (60, 660)))
""", deps_from=[CODE_CUT], args=[d / "png" / "f_00070.png"])
    expect((cut.stdout or "").strip().endswith("4"), f"iris: the corners of frame 70 must be black: {cut.stdout!r}")
    bad = [dict(p) for p in PARTS]
    bad[0]["k1"] = bad[1]["k0"] = 25                       # neither a beat nor a word onset
    bad[2].pop("why")
    e = edit(bad)
    e["overlays"].append({"type": "sparkle", "k0": 0, "k1": 10})
    write_json(d / "edit.json", e)
    r = ctx.uv(CODE_CUT, "check", d, check=False)
    out = (r.stdout or "") + (r.stderr or "")
    expect(r.returncode == 2 and "neither a beat nor a word onset" in out and "has no why" in out
           and "unknown type 'sparkle'" in out,
           f"broken edit: exit {r.returncode}, output {out[-300:]}")
    ctx.note("check ok (note on a too short stamp), 72 frames with all small pieces, dust and cards behind a mask and an "
             "iris out, joined with the song, overwrite refused, broken edit and unknown overlay refused with exit 2")


TESTS = [Test("code-cut", run_code_cut, about="code_cut.py: stills + take + code layer in the headless browser -> film; rules enforced")]
