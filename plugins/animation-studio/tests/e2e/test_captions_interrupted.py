"""animated-music-video captions.apply interrupted mid-save: a pass killed while a composite PNG is half written
(truncated temp file), one killed after the save but before its log line (complete, unlogged temp file), one killed
after the log line but before the rename (complete temp, hash in composited.partial), and the same in the very first
pass (no manifest yet, scenes/s/ holds only part of the composites). The next run must not mistake the frames for a
new render: raw originals kept, output identical to an uninterrupted run."""
import json

from common import Test, expect, script, SKILLS

SCENE = script("animated-music-video", "scene.py")       # its PEP 723 pins cover captions.py

DRIVER = r'''
import hashlib, json, os, shutil, sys, tempfile
from pathlib import Path
sys.path.insert(0, sys.argv[1])
import captions as C
from PIL import Image
from song_project import Project
work = Path(sys.argv[2])


def make_project(tag):
    d = work / tag
    (d / "analysis").mkdir(parents=True)
    (d / "project.json").write_text(json.dumps({"name": "t", "fps": 24, "sections": [
        {"name": "s", "from": 0.0, "to": 1.0, "kind": "external", "caption": {"group": "line"}}]}))
    words = [{"word": w, "t": 0.1 + 0.15 * i, "end": 0.2 + 0.15 * i, "line": 0}
             for i, w in enumerate("one two three four".split())]
    (d / "analysis" / "song_sheet.json").write_text(json.dumps({"fps": 24, "words": words,
        "lines": [{"line": 0, "text": "one two three four", "t": 0.1, "end": 0.8}], "beats": []}))
    fr = d / "scenes" / "s"
    fr.mkdir(parents=True)
    for i in range(24):
        Image.new("RGB", (1280, 720), (20 + i * 5, 40, 90)).save(fr / f"f.{i:04d}.png")
    return d


def digest(folder):
    return {p.name: hashlib.md5(p.read_bytes()).hexdigest() for p in sorted(folder.glob("f.*.png"))}


ref = make_project("clean")
raw_before = digest(ref / "scenes" / "s")
C.apply(Project(ref), "s")
want, raw_want = digest(ref / "scenes" / "s"), digest(ref / "scenes" / "s_raw")
assert raw_want == raw_before, "the clean run did not keep the originals in s_raw"
assert want != raw_before, "the clean run drew no caption"
orig_save = Image.Image.save
res = {}
orig_replace = os.replace
for case in ("truncated", "unlogged", "logged_unrenamed", "first_pass_killed"):
    d = make_project(case)
    P = Project(d)
    if case != "first_pass_killed":
        C.apply(P, "s")                               # a first full pass (composites + manifest exist)
    calls = {"n": 0}

    def boom_replace(src, dst, *a, **k):
        # complete composite, its hash already in composited.partial - killed before the rename
        if Path(src).name.startswith(".tmp.f."):
            calls["n"] += 1
            if calls["n"] == 10:
                raise KeyboardInterrupt
        return orig_replace(src, dst, *a, **k)

    def boom_save(self, fp, *a, **k):
        calls["n"] += 1
        if calls["n"] == 10:
            if case == "truncated":
                Path(fp).write_bytes(b"\x89PNG\r\n\x1a\n" + b"\0" * 100)   # half a file, then the kill
                raise KeyboardInterrupt
            orig_save(self, fp, *a, **k)
            raise KeyboardInterrupt                   # complete file, killed before the log line
        return orig_save(self, fp, *a, **k)
    if case in ("truncated", "unlogged"):
        Image.Image.save = boom_save
    else:
        os.replace = boom_replace
    try:
        C.apply(P, "s")                               # second pass (first_pass_killed: the first), killed at frame 10
    except KeyboardInterrupt:
        pass
    finally:
        Image.Image.save = orig_save
        os.replace = orig_replace
    part = d / "scenes" / "s_raw" / "composited.partial"
    logged = part.read_text().split() if part.exists() else []
    tmp_hashes = [hashlib.blake2b(t.read_bytes(), digest_size=16).hexdigest()
                  for t in (d / "scenes" / "s").glob(".tmp.*")]
    left = len(list((d / "scenes" / "s").glob(".tmp.*")))
    fresh = C._fresh_render(d / "scenes" / "s", d / "scenes" / "s_raw")
    C.apply(P, "s")                                   # next run
    res[case] = {"temp_left_after_kill": left, "fresh_render": bool(fresh),
                 "temp_logged": bool(tmp_hashes) and all(h in logged for h in tmp_hashes),
                 "raw_kept": digest(d / "scenes" / "s_raw") == raw_want,
                 "output_equals_clean": digest(d / "scenes" / "s") == want,
                 "temp_after_rerun": len(list((d / "scenes" / "s").glob(".tmp.*")))}
print("RESULT " + json.dumps(res))
'''


def run_captions(ctx):
    r = ctx.py(DRIVER, deps_from=[SCENE], args=[SKILLS / "animated-music-video" / "scripts", ctx.dir])
    line = next((l for l in r.stdout.splitlines() if l.startswith("RESULT ")), None)
    expect(line, "driver printed no result")
    res = json.loads(line[7:])
    for case, v in res.items():
        expect(v["temp_left_after_kill"] >= 1, f"{case}: the simulated kill left no temp file (test not effective)")
        expect(not v["fresh_render"], f"{case}: the next run treats the frames as a NEW render (would re-caption "
                                      f"captioned frames / drop the raw originals)")
        expect(v["raw_kept"], f"{case}: raw originals in scenes/s_raw changed")
        expect(v["output_equals_clean"], f"{case}: output differs from an uninterrupted run")
        expect(v["temp_after_rerun"] == 0, f"{case}: temp files left after the rerun")
        if case in ("logged_unrenamed", "first_pass_killed"):
            expect(v["temp_logged"], f"{case}: the temp's hash was not in composited.partial (test not effective)")
    ctx.note("truncated / unlogged / logged-but-not-renamed temp PNG, also in a first pass: not a new render, raw "
             "kept, output identical to a clean run")


TESTS = [Test("captions-interrupted", run_captions,
              about="captions.apply killed mid-save (truncated / unlogged / logged-not-renamed temp PNG, first pass)")]
