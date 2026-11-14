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


TESTS = [
    Test("animated-music-video", run_single, about="one section: scene.py --render, overlays, sounds (true/false/list), build.py film"),
    Test("animated-music-video-park", run_park_word_action, about="set park + an action keyed on a word (two former crashes)"),
    Test("animated-music-video-drift", run_two_sections, about="two sections 0-1.37-3.02 s: frame count and cut frame vs sound"),
]
