"""song-analysis refine_timing.py: silence_fix (a word that starts in silence moves to the next vocal onset) and
repeat_fix (two sections with the same text that are the same recording get the same word times) on a synthetic
vocal track - tone bursts as words, the "chorus" copied 4.00 s later."""
import json

from common import Test, expect, script

REFINE = script("song-analysis", "refine_timing.py")

CODE = r"""
import json, sys, wave
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(sys.argv[1]).parent))
from refine_timing import Onsets, in_silence, repeat_fix, silence_fix
sr = 48000
x = np.zeros(sr * 10, dtype=np.float32)
def word(t, d=0.25, f=220.0):
    n = int(d * sr); k = int(t * sr)
    env = np.minimum(1, np.arange(n) / (0.01 * sr)) * np.minimum(1, (n - np.arange(n)) / (0.03 * sr))
    x[k:k + n] += 0.5 * env * np.sin(2 * np.pi * f * np.arange(n) / sr)
starts = [1.0, 1.4, 1.8, 2.6, 3.0, 3.4]                 # two lines of three words
for i, t in enumerate(starts):
    word(t, f=200 + 30 * i)
x[int(5.0 * sr):int(9.0 * sr)] = x[int(1.0 * sr):int(5.0 * sr)]   # the same recording 4.00 s later
out = Path(sys.argv[2]); wav = out / "v.wav"
with wave.open(str(wav), "wb") as w:
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr); w.writeframes((x * 32767).astype("<i2").tobytes())
def line(ws):
    return {"t": ws[0], "e": ws[-1] + 0.25, "words": list(ws), "ends": [t + 0.25 for t in ws]}
lines = [line([1.0, 1.4, 1.8]), line([2.15, 3.0, 3.4]),          # line 1: first word in the pause (really 2.6)
         line([5.0, 5.4, 5.8]), line([6.6, 7.0, 7.62])]          # line 3: last word 0.22 s late (really 7.4)
texts = ["one two three", "four five six", "one two three", "four five six"]
on = Onsets(wav)
before = in_silence(on, lines, texts)
moved = silence_fix(on, lines, texts, verbose=False)
rep = repeat_fix(on, lines, texts, verbose=False)
json.dump({"before": before, "after": in_silence(on, lines, texts), "moved": len(moved), "rep": rep,
           "lines": [l["words"] for l in lines]}, open(out / "r.json", "w"))
"""


def run_repair(ctx):
    code = ctx.dir / "t.py"
    code.write_text("# /// script\n# requires-python = \">=3.12\"\n# dependencies = [\"numpy==2.5.4\"]\n"
                    "# [tool.uv]\n# exclude-newer = \"2026-11-14T00:00:00Z\"\n# ///\n" + CODE, encoding="utf-8")
    ctx.uv(code, REFINE, ctx.dir)
    r = json.loads((ctx.dir / "r.json").read_text(encoding="utf-8"))
    L = r["lines"]
    expect(r["before"][0] >= 1 and r["after"][0] == 0, f"words in silence before/after: {r['before']} / {r['after']}")
    expect(abs(L[1][0] - 2.6) < 0.06, f"silence_fix: the word at 2.15 s should move to the onset at 2.60 s, got {L[1][0]}")
    expect(r["rep"] and abs(r["rep"][0][3] - 4.0) < 0.02 and r["rep"][0][4] > 0.9,
           f"repeat_fix: offset / match of the copied section: {r['rep']}")
    expect(abs(L[3][2] - L[1][2] - 4.0) < 0.03 and abs(L[3][2] - 7.4) < 0.08,
           f"repeat_fix: the late word should follow the first section (7.40 s), got {L[3][2]} vs {L[1][2]}")
    ctx.note(f"silence: {r['before'][0]} -> 0 words, the word moved to {L[1][0]:.2f} s; repeated section {r['rep'][0][3]:.2f} s "
             f"apart (match {r['rep'][0][4]:.2f}), late word -> {L[3][2]:.2f} s")


TESTS = [Test("timing-repair", run_repair, about="refine_timing silence_fix + repeat_fix on synthetic vocals")]
