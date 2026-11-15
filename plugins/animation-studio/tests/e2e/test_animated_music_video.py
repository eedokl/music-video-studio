"""animated-music-video: synthetic song + song sheet + assignment -> scene.py --render -> overlays.py -> sounds.py ->
build.py film; and a two-section build with fractional boundaries (no drift of picture against sound)."""
from common import (FPS, Test, full, audio_samples, audio_seconds, expect, expect_film, first_loud, frame_colours, need,
                    read_json, script, song_sheet, assignment, tone, write_json, check_video)

SCENE = script("animated-music-video", "scene.py")
OVERLAYS = script("film-finish", "overlays.py")
SOUNDS = script("film-finish", "sounds.py")
BUILD = script("film-finish", "build.py")
NEW = script("song-analysis", "new_project.py")

WORDS = [("Hello", 0.30, 0.70, 0), ("tokens", 0.75, 1.20, 0), ("over", 1.25, 1.55, 0), ("the", 1.55, 1.70, 0),
         ("limit", 1.75, 2.30, 0), ("now", 2.35, 2.80, 0)]


def new_project(ctx, name, seconds, loud_from=None):
    song = tone(ctx, ctx.dir / f"{name}_song.wav", seconds, loud_from=loud_from)
    lyr = ctx.dir / f"{name}_lyrics.txt"
    lyr.write_text("[Chorus]\n" + " ".join(w for w, *_ in WORDS) + "\n", encoding="utf-8")
    proj = ctx.dir / name
    ctx.uv(NEW, proj, "--song", song, "--lyrics", lyr, "--language", "en")
    write_json(proj / "analysis" / "song_sheet.json", song_sheet(seconds, WORDS))
    write_json(proj / "analysis" / "assignment.json",
               assignment(["tim", "lia", "computer"], {"tim": [(0.3, 1.2)], "lia": [(1.25, 2.8)]}))
    return proj


def rms(y, t0, t1, sr=48000):
    seg = y[int(t0 * sr):int(t1 * sr)]
    return (sum(v * v for v in seg) / max(len(seg), 1)) ** 0.5


def frames_of(sec_from, sec_to):
    return round(sec_to * FPS) - round(sec_from * FPS)


def run_single(ctx):
    need("ffmpeg", "synfig", "earshot")
    proj = new_project(ctx, "amv", 3.5)
    P = read_json(proj / "project.json")
    S, E = 0.0, (2.98 if full() else 1.98)     # fast: 48 instead of 72 Synfig frames, same checks
    P["sections"] = [{"name": "chorus", "from": S, "to": E, "set": "stage", "figures": ["tim", "lia", "computer"],
                      "dance": "always", "lyrics": True}]
    P.update({"seed": 4711, "gags": [{"word": "tokens", "text": "TOKENS!", "color": "#ffd23f"}],
              "gestures": [{"word": "limit", "figure": "tim", "gesture": "scare"}],
              "title": {"text": "E2E", "from": 0.2, "to": 1.6}, "sounds": True})
    write_json(proj / "project.json", P)
    ctx.uv(SCENE, "chorus", "--project", proj, "--render", "--jobs", "8", timeout=1200)
    n_scene = len(list((proj / "scenes" / "chorus").glob("f.*.png")))
    expect(n_scene >= frames_of(S, E) - 1, f"scene rendered {n_scene} frames, section needs {frames_of(S, E)}")
    ctx.uv(OVERLAYS, "chorus", "--project", proj)
    expect((proj / "overlays" / "chorus.mov").exists(), "overlays/chorus.mov missing")
    expect(read_json(proj / "analysis" / "gags.json").get("chorus"), "the TOKENS! gag was not placed (gags.json)")

    # sounds.py: "sounds": true (default sources only), false (no track), a list (extra rules)
    ctx.uv(SOUNDS, proj)
    wav = proj / "analysis" / "sounds.wav"
    expect(wav.exists(), '"sounds": true wrote no analysis/sounds.wav')
    expect(abs(audio_seconds(wav) - 3.5) < 0.05, f"sounds.wav is {audio_seconds(wav):.2f} s, song 3.5 s")
    y_true = audio_samples(wav)
    P["sounds"] = False
    write_json(proj / "project.json", P)
    ctx.uv(SOUNDS, proj)
    expect(not wav.exists(), '"sounds": false kept analysis/sounds.wav')
    P["sounds"] = [{"word": "=now", "sfx": "ui_pop/blip", "level": -8}, {"at": 1.0, "sfx": "swish/soft", "level": -8}]
    write_json(proj / "project.json", P)
    ctx.uv(SOUNDS, proj)
    expect(wav.exists(), '"sounds": [list] wrote no analysis/sounds.wav')
    y_list = audio_samples(wav)
    gain = rms(y_list, 1.0, 1.25) / max(rms(y_true, 1.0, 1.25), 1.0)
    expect(gain > 3, f'the "at": 1.0 sound of the list is not in sounds.wav (level x{gain:.1f} against "sounds": true)')

    ctx.uv(BUILD, "film", "--project", proj, timeout=900)
    n = frames_of(S, E)
    expect_film(ctx, proj / "film.mp4", n)
    for v in ("film_small.mp4", "film_mail.mp4"):
        err = check_video(proj / v)
        expect((proj / v).exists() and not err, f"{v}: missing or decode errors {err[:200]}")
    ctx.note(f"{n} frames = round({E}*24)-round({S}*24), audio = picture length, 0 decode errors, sounds true/false/list ok")


def run_two_sections(ctx):
    need("ffmpeg", "synfig")
    cut = 1.37
    proj = new_project(ctx, "drift", 3.5, loud_from=cut)
    P = read_json(proj / "project.json")
    P["sections"] = [{"name": "a", "from": 0.0, "to": cut, "set": "color:#c02020", "figures": ["tim"], "dance": "never"},
                     {"name": "b", "from": cut, "to": 3.02, "set": "color:#2020c0", "figures": ["tim"], "dance": "never"}]
    P.update({"seed": 7, "sounds": False, "gags": [], "gestures": [], "look": "standard" if full() else "none"})   # look: tested in the one-section test
    write_json(proj / "project.json", P)
    for s in ("a", "b"):
        ctx.uv(SCENE, s, "--project", proj, "--render", "--jobs", "8", timeout=1200)
    ctx.uv(BUILD, "film", "--project", proj, timeout=900)
    total = round(3.02 * FPS)
    expect_film(ctx, proj / "film.mp4", total)
    cols = frame_colours(proj / "film.mp4")
    blue = next((i for i, (r, g, b) in enumerate(cols) if b > r), None)
    want = round(cut * FPS)
    expect(blue == want, f"section b starts on film frame {blue}, expected {want} = round({cut}*24) (drift)")
    expect(all(b > r for r, g, b in cols[want:]) and all(r > b for r, g, b in cols[:want]),
           "section colours are mixed up after the cut")
    y = audio_samples(proj / "film.mp4")
    quiet = max(abs(v) for v in y[int(0.5 * 48000):int(1.2 * 48000)])     # the song is 12 dB louder from the mark on
    loud = first_loud(y, 48000, 2.5 * quiet, start=0.5)
    expect(loud is not None and abs(loud - want / FPS) <= 1 / FPS,
           f"the song's sound mark at {cut} s is at {loud} s in the film, the picture cut at {want / FPS:.3f} s")
    ctx.note(f"{total} frames = round(3.02*24) (33 + 39), cut on frame {blue}, sound mark at {loud:.3f} s")


def run_park_word_action(ctx):
    # two former crashes: a bundled set without "scale"/"screen" (park) and an action keyed on a "word"
    need("synfig")
    proj = new_project(ctx, "park", 3.0)
    P = read_json(proj / "project.json")
    P["sections"] = [{"name": "p", "from": 0.0, "to": 2.0, "set": "park"}]
    P.update({"seed": 3, "sounds": False, "actions": [{"figure": "tim", "action": "typing", "word": "limit"}]})
    write_json(proj / "project.json", P)
    r = ctx.uv(SCENE, "p", "--project", proj, timeout=600)
    out = r.stdout if hasattr(r, "stdout") else str(r)
    expect((proj / "scenes" / "p.sif").exists(), "scene.py wrote no .sif for the park section")
    expect("set park" in out and "tim typing" in out, f"park set / word action missing in the output:\n{out[-600:]}")
    ctx.note("set park (no scale/screen in set.json) and an action keyed on the word 'limit' build")


def run_acting(ctx):
    """project.json "acting": listeners turn to the singer (scene_acting.py). Off = no acting layer in the scene."""
    need("ffmpeg", "synfig")
    import re
    words = [("Hello", 0.30, 0.70, 0), ("tokens", 0.75, 1.40, 0), ("over", 1.75, 2.05, 1), ("the", 2.05, 2.20, 1),
             ("limit", 2.25, 2.70, 1), ("now", 2.75, 3.30, 1)]
    proj = new_project(ctx, "act", 4.0)
    write_json(proj / "analysis" / "song_sheet.json", song_sheet(4.0, words))
    write_json(proj / "analysis" / "assignment.json",
               assignment(["tim", "lia", "computer"], {"tim": [(0.3, 1.4)], "lia": [(1.75, 3.3)]}))
    P = read_json(proj / "project.json")
    P["sections"] = [{"name": "verse", "from": 0.0, "to": 3.98, "set": "stage", "figures": ["tim", "lia", "computer"],
                      "dance": "never"}]
    P.update({"seed": 11, "gags": [{"word": "limit", "text": "LIMIT!"}], "gestures": [], "look": "none"})
    sif = proj / "scenes" / "verse.sif"

    def build(acting, section=None):
        P["acting"] = acting
        P["sections"][0].pop("acting", None)
        if section is not None:
            P["sections"][0]["acting"] = section
        write_json(proj / "project.json", P)
        out = ctx.uv(SCENE, "verse", "--project", proj).stdout
        return out, sif.read_text(encoding="utf-8")

    out, off = build(False)
    expect("acting {" not in out and "acting gaze" not in off, 'without "acting" the scene has an acting layer')
    out, on = build(True)
    expect("acting gaze" in on and "acting brow" in on, 'with "acting": true the scene has no gaze / brow layer')
    m = re.search(r"acting (\{.*\})", out)
    expect(m, f"scene.py does not report the acting layer:\n{out[-500:]}")
    n = eval(m.group(1))                              # the dict printed by scene.py (own output)
    expect(n["tim"]["turns"] >= 1 and n["lia"]["turns"] >= 1 and n["computer"]["turns"] >= 2,
           f"tim and lia sing one after the other - each must turn to the other, the screen to both: {n}")
    expect(n["tim"]["brows"] >= 1 and n["lia"]["brows"] == 0,
           f"the gag word 'limit' is sung by lia: tim's brows react, her own do not: {n}")
    expect(len({n[k]["delay"] for k in n}) >= 1 and all(3 <= n[k]["delay"] <= 7 for k in n), f"reaction delays: {n}")
    out2, on2 = build(True)
    expect(on2 == on, "the same seed gives a different acting take")
    out, sec_off = build(True, section=False)
    expect(sec_off == off, 'a section with "acting": false differs from the scene without acting')
    # expressions: tim is shocked while lia sings - own mouth, brows tipped one by one, the face turns to her
    P["sections"][0].pop("acting", None)
    P["expressions"] = [{"figure": "tim", "expression": "shock", "from": 1.9, "to": 3.0},
                        {"figure": "lia", "expression": "grin", "word": "tokens"}]
    write_json(proj / "project.json", P)
    out = ctx.uv(SCENE, "verse", "--project", proj).stdout
    ex = sif.read_text(encoding="utf-8")
    for mark in ("Mouth o", "Mouth grin", "expression brow 0", "expression brow 1", "expression auge_l",
                 "acting turn nose", "acting turn cheeks", "acting turn mouth", "Mouth sync"):
        expect(mark in ex, f'expressions: no "{mark}" layer in the scene')
    expect("'expressions': [(1.9, 'shock')]" in out and "'grin')" in out,
           f"scene.py does not report the expressions:\n{out[-500:]}")
    P["expressions"] = [{"expression": "shock", "from": 1.9}]
    write_json(proj / "project.json", P)
    r = ctx.uv(SCENE, "verse", "--project", proj, check=False)
    expect(r.returncode == 2 and "expressions" in r.stdout, 'an expression without "figure" was not rejected')
    P.pop("expressions")
    bad = dict(P, acting="yes")
    write_json(proj / "project.json", bad)
    r = ctx.uv(SCENE, "verse", "--project", proj, check=False)
    expect(r.returncode == 2 and "acting" in r.stdout, '"acting": "yes" (a string) was not rejected by the project check')
    ctx.note(f"off = no acting layer; on: turns tim {n['tim']['turns']} lia {n['lia']['turns']} screen "
             f"{n['computer']['turns']}, tim's brows on lia's gag word, same seed same take, section switch works; expressions: own mouths, brows, eyes, face turn")


def run_acting_draft(ctx):
    """acting_draft.py: a mood per line (guess + corrections that survive), expressions derived from it."""
    need("ffmpeg")
    draft = script("animated-music-video", "acting_draft.py")
    words = [("Hello", 0.30, 0.70, 0), ("tokens", 0.75, 1.40, 0), ("over", 1.75, 2.05, 1), ("the", 2.05, 2.20, 1),
             ("limit", 2.25, 2.70, 1), ("now", 2.75, 3.30, 1)]
    proj = new_project(ctx, "draft", 4.0)
    write_json(proj / "analysis" / "song_sheet.json", song_sheet(4.0, words))
    write_json(proj / "analysis" / "assignment.json",
               assignment(["tim", "lia", "computer"], {"tim": [(0.3, 1.4)], "lia": [(1.75, 3.3)]}))
    P = read_json(proj / "project.json")
    P["sections"] = [{"name": "verse", "from": 0.0, "to": 3.98, "set": "stage", "figures": ["tim", "lia", "computer"]}]
    P["expressions"] = [{"figure": "lia", "expression": "angry", "from": 0.2, "to": 1.0}]      # set by hand
    P.pop("seed", None)                                    # no seed yet: apply stores one and must keep it
    write_json(proj / "project.json", P)
    ctx.uv(draft, "draft", "--project", proj)
    rows = read_json(proj / "analysis" / "acting.json")["lines"]
    expect([r["singers"] for r in rows] == [["tim"], ["lia"]], f"who sings each line: {[r['singers'] for r in rows]}")
    expect(rows[1]["mood"] == "alarm" and rows[0]["mood"] == "neutral",
           f"guess: 'over the limit now' = alarm, 'Hello tokens' = neutral, got {[r['mood'] for r in rows]}")
    expect(all(isinstance(r["energy_db"], (int, float)) for r in rows), f"no voice level per line: {rows}")
    d = read_json(proj / "analysis" / "acting.json")
    d["lines"][0].update({"mood": "proud", "by": "ai"})                    # somebody read the line
    write_json(proj / "analysis" / "acting.json", d)
    ctx.uv(draft, "draft", "--project", proj)
    rows = read_json(proj / "analysis" / "acting.json")["lines"]
    expect(rows[0]["mood"] == "proud" and rows[0]["by"] == "ai", "a second draft overwrote a mood that was read by hand")
    ctx.uv(draft, "apply", "--project", proj)
    P1 = read_json(proj / "project.json")
    ex = P1["expressions"]
    hand = [e for e in ex if not e.get("auto")]
    auto = [e for e in ex if e.get("auto")]
    expect(hand == [{"figure": "lia", "expression": "angry", "from": 0.2, "to": 1.0}], f"the hand-set expression changed: {hand}")
    expect(P1.get("acting") is True, '"acting" was not switched on')
    expect(any(e["figure"] == "tim" and e["expression"] == "shock" and e["from"] >= 1.75 for e in auto),
           f"lia sings the alarm line - tim (the listener) must be shocked: {auto}")
    expect(not any(e["figure"] == "lia" and e["from"] < 2.0 for e in auto),
           f"an automatic expression of lia overlaps her hand-set one (0.2-1.0 s + 1 s gap): {auto}")
    ctx.uv(draft, "apply", "--project", proj)
    expect(read_json(proj / "project.json")["expressions"] == ex, "a second apply changed the expressions (same seed)")
    d["lines"][1]["mood"] = "furious"
    write_json(proj / "analysis" / "acting.json", d)
    bad = ctx.uv(draft, "apply", "--project", proj, check=False)
    expect(bad.returncode != 0 and "unknown mood" in bad.stdout, "an unknown mood was not rejected")
    ctx.note(f"guess alarm on 'limit', read mood kept, {len(auto)} automatic expression(s), hand-set one kept, repeatable")


TESTS = [
    Test("animated-music-video-acting-draft", run_acting_draft, about="acting_draft.py: mood per line, listeners' expressions derived, hand-set ones kept"),
    Test("animated-music-video-acting", run_acting, about='"acting": listeners look at the singer, brows on gag words, off = unchanged'),
    Test("animated-music-video", run_single, about="one section: scene.py --render, overlays, sounds (true/false/list), build.py film"),
    Test("animated-music-video-park", run_park_word_action, about="set park + an action keyed on a word (two former crashes)"),
    Test("animated-music-video-drift", run_two_sections, about="two sections 0-1.37-3.02 s: frame count and cut frame vs sound"),
]
