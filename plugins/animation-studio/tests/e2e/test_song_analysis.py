"""song-analysis analyze.py: `lyric{sung}` overrides in the lyrics (step 1), the sung-word check at line starts
(warning with a ready Hi{Hey} fix, project.json "sung_words": "line_start" takes Whisper's stable word), the "heard"
word of track_read.align_lyrics, and `--quick --no-words` (CPU overview -> analysis/quick.json, no song_sheet.json).
No Whisper, no GPU: the word passes are crafted."""
import json

from common import Test, expect, need, read_json, script, tone, tool

NEW = script("song-analysis", "new_project.py")
ANALYZE = script("song-analysis", "analyze.py")

LYRICS = "[Intro]\nHi{Hey}. Ich bin hier die Künstliche.\n(she smiles)\nDer{} Test{Probe}, läuft\nOut of the dark\n"

DRIVER = r"""
import json, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
import analyze, track_read
from song_project import Project
P = Project(sys.argv[2])
# what track_read.align_lyrics keeps of a 1:1 swap
words, _ = track_read.align_lyrics([{"word": "Hey,", "start": 0.0, "end": 0.9, "prob": 0.96},
                                    {"word": "ich", "start": 1.1, "end": 1.3, "prob": 0.99},
                                    {"word": "bin", "start": 1.3, "end": 1.4, "prob": 0.99}], "Hi. Ich bin", 24)
def W(word, t, line, source="recognized", heard=None, prob=None):
    w = {"word": word, "t": t, "end": t + 0.2, "line": line, "source": source}
    if heard:
        w.update(heard=heard, heard_prob=prob)
    return w
sheet = {"duration": 20.0, "words": [
    W("Hi.", 0.0, 0, "aligned", "Hey,", 0.96), W("Ich", 1.12, 0), W("bin", 1.32, 0), W("hier", 1.4, 0),
    W("Out", 5.0, 1, "aligned", "Hey", 0.9), W("of", 5.3, 1, "aligned", "hey", 0.9), W("the", 5.5, 1), W("dark", 5.7, 1),
    W("Wir", 8.0, 2, "aligned", "Bier", 0.3), W("gehen", 8.3, 2), W("jetzt", 8.6, 2)],
    "lines": [{"line": 0, "text": "Hi. Ich bin hier", "t": 0.0, "end": 1.6},
              {"line": 1, "text": "Out of the dark", "t": 5.0, "end": 5.9},
              {"line": 2, "text": "Wir gehen jetzt", "t": 8.0, "end": 8.8}]}
(P.analysis / "lyrics_clean.txt").write_text("Hi. Ich bin hier\nOut of the dark\nWir gehen jetzt\n", encoding="utf-8")
(P.analysis / "song_sheet.json").write_text(json.dumps(sheet), encoding="utf-8")
swaps = [(w["line"], c) for w, c in analyze.line_start_swaps(sheet)]
warn = analyze.sheet_warnings(sheet)
done = analyze.apply_line_start(P, sheet)
again = analyze.line_start_swaps(json.loads((P.analysis / "song_sheet.json").read_text(encoding="utf-8")))
json.dump({"align0": words[0], "swaps": swaps, "warn": warn, "done": done, "again": len(again),
           "sheet": json.loads((P.analysis / "song_sheet.json").read_text(encoding="utf-8")),
           "lyrics": (P.analysis / "lyrics_clean.txt").read_text(encoding="utf-8"),
           "sung": json.loads((P.analysis / "sung_words.json").read_text(encoding="utf-8"))},
          open(Path(sys.argv[2]) / "r.json", "w", encoding="utf-8"), ensure_ascii=False)
"""


def run_sung_words(ctx):
    need("ffmpeg")
    song = tone(ctx, ctx.dir / "song.wav", 12.0, loud_from=6.0)
    lyr = ctx.dir / "lyrics.txt"
    lyr.write_text(LYRICS, encoding="utf-8")
    d = ctx.dir / "proj"
    ctx.uv(NEW, d, "--song", song, "--lyrics", lyr, "--language", "de")
    pj = read_json(d / "project.json")
    pj["sung_words"] = "line_start"                       # must pass the project check of every analyze.py call
    (d / "project.json").write_text(json.dumps(pj, ensure_ascii=False, indent=1), encoding="utf-8")

    # step 1: overrides from the lyrics
    out = ctx.uv(ANALYZE, d, "--only", "1").stdout
    clean = (d / "analysis" / "lyrics_clean.txt").read_text(encoding="utf-8").splitlines()
    expect(clean == ["Hey. Ich bin hier die Künstliche.", "Probe, läuft", "Out of the dark"],
           f"lyrics_clean.txt with the sung words: {clean}")
    sung = read_json(d / "analysis" / "sung_words.json")
    expect([(s["line"], s["lyric"], s["sung"]) for s in sung] == [(0, "Hi", "Hey"), (1, "Der", ""), (1, "Test", "Probe")],
           f"sung_words.json: {sung}")
    expect("3 sung-word override(s)" in out, f"step 1 should report the overrides:\n{out[-400:]}")

    # line-start check on crafted Whisper words
    ctx.py(DRIVER, deps_from=[ANALYZE], args=[ANALYZE.parent, d])
    r = json.loads((d / "r.json").read_text(encoding="utf-8"))
    a0 = r["align0"]
    expect(a0["source"] == "aligned" and a0.get("heard") == "Hey," and a0.get("heard_prob") == 0.96,
           f"align_lyrics should keep the heard word of a 1:1 swap: {a0}")
    expect(r["swaps"] == [[0, "Hey"]], f"only line 0 is a stable swap (line 1 = unlisted call, line 2 unsure): {r['swaps']}")
    hint = [w for w in r["warn"] if "Hi{Hey}" in w]
    expect(hint and "sung 'Hey'" in hint[0], f"warning with the ready Hi{{Hey}} fix missing: {r['warn']}")
    expect(not any("lyric line 0:" in w and "far before" in w for w in r["warn"]),
           f"the stray warning should give way to the swap hint on line 0: {r['warn']}")
    expect(not any(w.startswith(("lyric line 1: sung", "lyric line 2: sung")) for w in r["warn"]),
           f"lines 1 and 2 must not get a swap hint: {r['warn']}")
    w0 = r["sheet"]["words"][0]
    expect(w0["word"] == "Hey." and w0.get("lyric") == "Hi.", f"applied: sheet word {w0}")
    expect(r["sheet"]["lines"][0]["text"] == "Hey. Ich bin hier" and r["lyrics"].startswith("Hey. Ich bin hier\nOut of"),
           f"line text / lyrics_clean.txt not updated: {r['sheet']['lines'][0]} / {r['lyrics'][:40]!r}")
    expect(r["sheet"]["words"][4]["word"] == "Out", "line 1 (unlisted call) must keep its lyric words")
    expect(r["again"] == 0 and [s["source"] for s in r["sung"]][-1:] == ["whisper"],
           f"second pass should find nothing, sung_words.json lists the swap: again={r['again']} {r['sung']}")

    # --quick --no-words: CPU overview in gpu_python (librosa), never a song_sheet.json
    if not tool("gpu_python"):
        ctx.note("sung words OK; --quick skipped (no gpu_python with librosa configured)")
        return
    (d / "analysis" / "song_sheet.json").unlink()
    q = ctx.uv(ANALYZE, d, "--quick", "--no-words").stdout
    expect("Q  quick overview" in q, f"--quick did not finish:\n{q[-500:]}")
    res = read_json(d / "analysis" / "quick.json")
    expect(res["quick"] and abs(res["duration"] - 12.0) < 0.1 and res["tempo_bpm"] > 0 and len(res["loudness_2s"]) == 6,
           f"quick.json: duration {res.get('duration')}, tempo {res.get('tempo_bpm')}, {len(res.get('loudness_2s', []))} blocks")
    expect(any(abs(j["t"] - 6.0) < 0.1 and j["to_db"] - j["from_db"] > 6 for j in res["jumps"]),
           f"the 12 dB jump at 6.0 s missing: {res['jumps']}")
    expect(not (d / "analysis" / "song_sheet.json").exists(), "--quick must not write song_sheet.json")
    ctx.note(f"overrides Hi->Hey, Der->-, Test->Probe; line-start swap only on the stable line; --quick: "
             f"{res['tempo_bpm']} BPM, jump at {res['jumps'][0]['t']} s, no song_sheet.json")


TESTS = [Test("song-analysis", run_sung_words,
              about="lyric{sung} overrides, sung-word check at line starts, analyze.py --quick (no Whisper, no GPU)")]
