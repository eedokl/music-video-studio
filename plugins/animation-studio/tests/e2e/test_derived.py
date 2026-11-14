"""studio-core derived.py (records of what a cache was built from) and its call sites.

derived-unit        fresh / stale on input CONTENT and spec changes, never on mtime changes or a moved folder; an
                    interrupted build (exception, or a kill between replacing the target and writing its record)
                    never looks fresh; an input edited during the build makes the result stale; folder targets; the
                    Ledger of written files (interrupted pass keeps its log).
derived-call-sites  the caches that use it, with their expensive step replaced by a counter (no Synfig, TTS or
                    earshot): toon-2d breakout cached_still (sif text / svg content / killed render), talking-character
                    speak line cache (text, voice entry, engine, moved project, adoption of an old lines.json without
                    speaking again), studio-core sfx_mix bank (reuse, killed render, adoption of old bank files).
"""
import json
import os
import shutil
import sys
import time

from common import SKILLS, Test, expect, script

CORE = SKILLS / "studio-core" / "scripts"


def _derived():
    if str(CORE) not in sys.path:
        sys.path.insert(0, str(CORE))
    import derived
    return derived


def run_unit(ctx):
    D = _derived()
    w = ctx.dir / "proj"
    (w / "in").mkdir(parents=True)
    src, tgt = w / "in" / "a.txt", w / "out" / "a.bin"
    src.write_text("one", encoding="utf-8")
    spec = {"size": 3}

    def build(text="built", inputs=None, sp=None):
        with D.build(tgt, inputs or [src], sp or spec) as b:
            b.path.write_text(text + ":" + src.read_text(encoding="utf-8"), encoding="utf-8")

    expect(not D.fresh(tgt, [src], spec), "fresh before any build")
    build()
    expect(D.fresh(tgt, [src], spec), "not fresh right after the build")
    expect(not list(tgt.parent.glob(".tmp.*")), "temp left after a successful build")
    old = time.time() - 86400 * 3
    os.utime(src, (old, old))                                        # mtime change only (zip / git restore)
    os.utime(tgt, (old, old))
    expect(D.fresh(tgt, [src], spec), "an mtime change made the target stale")
    moved = ctx.dir / "moved"                                        # copy with NEW mtimes to another folder
    for f in w.rglob("*"):
        if f.is_file():
            (moved / f.relative_to(w)).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(f, moved / f.relative_to(w))
    expect(D.fresh(moved / "out" / "a.bin", [moved / "in" / "a.txt"], spec), "a copied project is not fresh (paths?)")
    rec = (tgt.parent / ".derived" / "a.bin.json").read_text(encoding="utf-8")
    expect(str(ctx.dir.resolve()) not in rec and str(ctx.dir) not in rec, "the record holds an absolute path")
    expect(not D.fresh(tgt, [src], {"size": 4}), "a spec change did not make the target stale")
    src.write_text("two", encoding="utf-8")
    expect(not D.fresh(tgt, [src], spec), "an input content change did not make the target stale")
    missing = w / "in" / "later.txt"
    build(inputs=[src, missing])
    expect(D.fresh(tgt, [src, missing], spec), "missing input: not fresh after the build")
    missing.write_text("x", encoding="utf-8")
    expect(not D.fresh(tgt, [src, missing], spec), "creating a missing input did not make the target stale")
    build()

    # interrupted build: exception inside the block -> old target kept, not fresh for the new inputs, temp removed
    src.write_text("three", encoding="utf-8")
    before = tgt.read_text(encoding="utf-8")
    try:
        with D.build(tgt, [src], spec) as b:
            b.path.write_text("half", encoding="utf-8")
            raise KeyboardInterrupt
    except KeyboardInterrupt:
        pass
    expect(tgt.read_text(encoding="utf-8") == before, "an interrupted build replaced the target")
    expect(not D.fresh(tgt, [src], spec), "an interrupted build looks fresh")
    expect(not list(tgt.parent.glob(".tmp.*")), "an interrupted build left its temp")

    # killed between replacing the target and writing the record (commit's last step)
    orig = D.record

    def killed(*a, **k):
        raise KeyboardInterrupt
    D.record = killed
    try:
        build("new")
    except KeyboardInterrupt:
        pass
    finally:
        D.record = orig
    expect(tgt.read_text(encoding="utf-8").startswith("new"), "test not effective: the target was not replaced")
    expect(not D.fresh(tgt, [src], spec), "new content without its record looks fresh")
    src.write_text("two", encoding="utf-8")
    expect(not D.fresh(tgt, [src], spec), "new content under the OLD record looks fresh for the old inputs")
    src.write_text("three", encoding="utf-8")

    # an input edited while the build runs: the result is stale at once
    with D.build(tgt, [src], spec) as b:
        b.path.write_text("x", encoding="utf-8")
        src.write_text("edited meanwhile", encoding="utf-8")
    expect(not D.fresh(tgt, [src], spec), "an input edited during the build: the result looks fresh")

    # folder target + folder input
    fin, fout = w / "frames_in", w / "frames_out"
    fin.mkdir()
    for i in range(3):
        (fin / f"f.{i}.txt").write_text(str(i), encoding="utf-8")
    with D.build(fout, [fin], {"k": 1}, folder=True) as b:
        for f in fin.iterdir():
            shutil.copyfile(f, b.path / f.name)
    expect(D.fresh(fout, [fin], {"k": 1}) and len(list(fout.iterdir())) == 3, "folder build not fresh / incomplete")
    with D.build(fout, [fin], {"k": 2}, folder=True) as b:
        (b.path / "only.txt").write_text("x", encoding="utf-8")
    expect([p.name for p in fout.iterdir()] == ["only.txt"], "a rebuilt folder kept files of the old build")
    (fin / "f.1.txt").write_text("changed", encoding="utf-8")
    expect(not D.fresh(fout, [fin], {"k": 2}), "a changed file inside an input folder did not make it stale")

    # Ledger: own files known, foreign file detected, interrupted pass keeps its log
    out, store = w / "led", w / "led_store"
    out.mkdir()
    L = D.Ledger(store, "written")
    expect(L.foreign([]) is None, "a ledger without a record claims files")
    with L.session() as s:
        for i in range(3):
            s.save(out / f"f.{i}.txt", lambda tmp, i=i: tmp.write_text(f"ours {i}", encoding="utf-8"))
    expect(L.foreign(sorted(out.glob("f.*.txt"))) == [], "own files counted as foreign")
    try:
        with L.session() as s:
            s.save(out / "f.0.txt", lambda tmp: tmp.write_text("ours again", encoding="utf-8"))
            raise KeyboardInterrupt
    except KeyboardInterrupt:
        pass
    expect(L.partial.exists(), "an interrupted pass dropped its log")
    expect(L.foreign(sorted(out.glob("f.*.txt"))) == [], "a file of the interrupted pass counted as foreign")
    (out / "f.2.txt").write_text("someone else", encoding="utf-8")
    expect(L.foreign(sorted(out.glob("f.*.txt"))) == [out / "f.2.txt"], "a foreign file was not detected")
    ctx.note("content not mtime, portable records, interrupted / killed builds never fresh, folders, ledger")


DRIVER = r'''
import json, os, shutil, sys, types
from pathlib import Path
skills, work = Path(sys.argv[1]), Path(sys.argv[2])
res = {}

# ---------------------------------------------------------------- toon-2d breakout cached_still
sys.path.insert(0, str(skills / "toon-2d" / "scripts"))
import breakout as B
calls = []


def fake_render(text, path, sif=None):
    calls.append(text)
    Path(sif or path.with_suffix(".sif")).write_text(text, encoding="utf-8")
    path.write_bytes(b"PNG:" + text.encode())
    return path
B.render_still = fake_render
bw = work / "breakout_work"
bw.mkdir(parents=True)
svg = work / "fig.svg"
svg.write_text("<svg>1</svg>", encoding="utf-8")
png = bw / "rest.png"
legacy_sif = png.with_suffix(".sif")                       # a cache of the old format: rest.png + same .sif text
png.write_bytes(b"old"); legacy_sif.write_text("SIF A", encoding="utf-8")
B.cached_still("SIF A", png, svg); n_legacy = len(calls)
B.cached_still("SIF A", png, svg); n_same = len(calls)
B.cached_still("SIF B", png, svg); n_text = len(calls)
svg.write_text("<svg>2</svg>", encoding="utf-8")
B.cached_still("SIF B", png, svg); n_svg = len(calls)


def boom(text, path, sif=None):
    path.write_bytes(b"half")
    raise KeyboardInterrupt
B.render_still = boom
try:
    B.cached_still("SIF C", png, svg)
except KeyboardInterrupt:
    pass
B.render_still = fake_render
B.cached_still("SIF C", png, svg); n_kill = len(calls)
res["breakout"] = {"legacy_rerendered_once": n_legacy == 1, "same_text_cached": n_same == 1,
                   "text_change": n_text == 2, "svg_change": n_svg == 3, "after_kill_rerendered": n_kill == 4,
                   "png_ok": png.read_bytes() == b"PNG:SIF C",
                   "no_temp": not list(bw.glob(".tmp.*"))}

# ---------------------------------------------------------------- talking-character speak line cache
sys.path.insert(0, str(skills / "talking-character" / "scripts"))
import speak as S
import voice as V
from song_project import Project
from dialogue import parse
spoken = []
engine = {"name": "system"}


def fake_speak(items, project_dir=None, seed=0, language="de", engine=None, pronounce=None, **k):
    out = []
    for it in items:
        spoken.append(it["text"])
        Path(it["out"]).write_bytes(b"RIFF" + it["text"].encode())
        out.append({"who": it["who"], "text": it["text"], "out": it["out"], "engine": engine_now(),
                    "score": 1.0, "heard": it["text"], "words": [{"word": "x", "t": 0.0, "end": 0.2}],
                    "duration": 0.5, "take": 0})
    return out


def engine_now():
    return engine["name"]
V.speak = fake_speak
V.choose = lambda entry, force=None: {**entry, "engine": force or engine_now()}
proj = work / "talk"
proj.mkdir()
(proj / "project.json").write_text(json.dumps({"name": "t", "seed": 5, "figures": {"tim": {}, "lia": {}},
    "voices": {"tim": {"engine": "system", "voice": "A"}, "lia": {"engine": "system", "voice": "B"}}}), encoding="utf-8")
script_text = "Tim: Hallo Lia!\nLia: Hallo Tim.\n"
args = types.SimpleNamespace(redo=False, engine=None)


def run(project, text):
    P = Project(project)
    before = len(spoken)
    r = S.spoken_lines(P, parse(text, list(P["figures"])), args)
    return len(spoken) - before, r
n1, r1 = run(proj, script_text)
n2, r2 = run(proj, script_text)
n3, _ = run(proj, "Tim: Hallo Lia!\nLia: Servus Tim.\n")
pj = json.loads((proj / "project.json").read_text(encoding="utf-8"))
pj["voices"]["tim"]["voice"] = "C"
(proj / "project.json").write_text(json.dumps(pj), encoding="utf-8")
n4, _ = run(proj, "Tim: Hallo Lia!\nLia: Servus Tim.\n")
engine["name"] = "piper"
n5, _ = run(proj, "Tim: Hallo Lia!\nLia: Servus Tim.\n")
moved = work / "talk_moved"
shutil.copytree(proj, moved)
n6, r6 = run(moved, "Tim: Hallo Lia!\nLia: Servus Tim.\n")
recs = "".join(p.read_text(encoding="utf-8") for p in (moved / "lines" / ".derived").glob("*.json"))
# an old project: lines.json in the format before derived.py (sig per line), no records -> adopted, nothing spoken
old = work / "talk_old"
shutil.copytree(proj, old)
shutil.rmtree(old / "lines" / ".derived")
P = Project(old)
voices = V.cast(old)
legacy = {}
for k, text in (("0:0", "Hallo Lia!"), ("1:0", "Servus Tim.")):
    who = "tim" if k == "0:0" else "lia"
    legacy[k] = {"who": who, "text": text, "out": f"lines/{k[0].zfill(2)}_0_{who}.wav", "engine": "piper",
                 "score": 1.0, "heard": text, "words": [{"word": "x", "t": 0.0, "end": 0.2}], "duration": 0.5,
                 "take": 0, "sig": S._legacy_sig(who, text, voices, P, args)}
(old / "lines" / "lines.json").write_text(json.dumps(legacy), encoding="utf-8")
n7, r7 = run(old, "Tim: Hallo Lia!\nLia: Servus Tim.\n")
n8, _ = run(old, "Tim: Hallo Lia!\nLia: Servus Tim.\n")
res["speak"] = {"first": n1 == 2, "cached": n2 == 0, "text_change": n3 == 1, "voice_change": n4 == 1,
                "engine_change": n5 == 2, "moved_project_cached": n6 == 0,
                "moved_paths_local": all(str(moved.resolve()) in v["out"] for v in r6.values()),
                "records_without_abs_paths": not any(s in recs for w in (work, work.resolve())
                                                     for s in (str(w), str(w).replace("\\", "/"),
                                                               str(w).replace("\\", "\\\\"))),
                "legacy_adopted": n7 == 0 and n8 == 0, "legacy_words_kept": r7[(0, 0)]["words"][0]["word"] == "x",
                "no_temp": not list((proj / "lines").glob(".tmp.*"))}

# ---------------------------------------------------------------- studio-core sfx_mix bank
import subprocess
import sfx_mix as M
bank = work / "bank"
bank.mkdir()
runs = []
mode = {"m": "ok"}


class R:
    def __init__(self, rc):
        self.returncode, self.stdout, self.stderr = rc, "", ""


def fake_run(cmd, **k):
    if isinstance(cmd, list) and "sfx" in cmd and "render" in cmd:
        out = Path(cmd[cmd.index("-o") + 1])
        runs.append(cmd[cmd.index("render") + 1])
        if mode["m"] == "unknown":
            return R(2)
        out.write_bytes(b"RIFFdata")
        return R(1 if mode["m"] == "crash" else 0)
    return real_run(cmd, **k)
real_run = subprocess.run
M.subprocess.run = fake_run
mix = M.SfxMix(1.0, cache=bank)
mix.cache = bank
mix.ear = ["earshot"]
wav = bank / "ui_pop__blip_d0.3.wav"
a = mix._bank(wav, "ui_pop/blip", ["--dur", "0.3"]); r_a = len(runs)
b = mix._bank(wav, "ui_pop/blip", ["--dur", "0.3"]); r_b = len(runs)
mode["m"] = "crash"
wav2 = bank / "swish__soft.wav"
c = mix._bank(wav2, "swish/soft", []); c_left = wav2.exists() or bool(list(bank.glob(".tmp.*")))
mode["m"] = "ok"
d = mix._bank(wav2, "swish/soft", []); r_d = len(runs)
mode["m"] = "unknown"
e = mix._bank(bank / "nope.wav", "nope", [])
import io, wave as _wave
buf = io.BytesIO()
with _wave.open(buf, "wb") as w_:                         # a complete bank file from before derived.py
    w_.setnchannels(1); w_.setsampwidth(2); w_.setframerate(48000); w_.writeframes(bytes([0, 1]) * 480)
good_wav = buf.getvalue()
legacy = bank / "drip__plink.wav"
legacy.write_bytes(good_wav)
f = mix._bank(legacy, "drip/plink", []); r_f = len(runs)
mode["m"] = "ok"
trunc = bank / "drip__bubble.wav"                         # one a killed render left half-written (no record)
trunc.write_bytes(good_wav[:len(good_wav) // 2])
g = mix._bank(trunc, "drip/bubble", []); r_g = len(runs)
res["sfx_bank"] = {"rendered": a and r_a == 1, "reused": b and r_b == 1,
                   "crash_not_kept": (not c) and not c_left, "rerendered_after_crash": d and r_d == 3,
                   "unknown_id": (not e) and not (bank / "nope.wav").exists(),
                   "legacy_adopted": f and r_f == 4 and legacy.read_bytes() == good_wav,
                   "truncated_legacy_rerendered": g and r_g == 5 and trunc.read_bytes() == b"RIFFdata",
                   "no_temp": not list(bank.glob(".tmp.*"))}
print("RESULT " + json.dumps(res))
'''


def run_call_sites(ctx):
    r = ctx.py(DRIVER, deps_from=[script("toon-2d", "breakout.py"), script("talking-character", "speak.py")],
               name="derived_sites.py", args=[SKILLS, ctx.dir])
    line = next((l for l in r.stdout.splitlines() if l.startswith("RESULT ")), None)
    expect(line, "driver printed no result")
    res = json.loads(line[7:])
    bad = [f"{site}.{k}" for site, v in res.items() for k, ok in v.items() if not ok]
    expect(not bad, f"failed checks: {', '.join(bad)}  ({json.dumps(res)})")
    ctx.note("breakout stills, speak line cache (incl. old lines.json adopted), sfx bank (killed render, old files)")


TESTS = [Test("derived-unit", run_unit, about="studio-core derived.py: fresh/stale by content, interrupted builds, ledger"),
         Test("derived-call-sites", run_call_sites, about="breakout stills, speak line cache, sfx bank on derived.py")]
