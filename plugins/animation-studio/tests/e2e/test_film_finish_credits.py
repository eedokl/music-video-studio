"""film-finish credits.py: a short credits sequence on a synthetic song project - rolling text in two parts, one gag
between them (bundled set with curtains, own PNG figure with moves and mouths, silhouette, screen, bubble, bang,
caption, prop card, counting chips, a rendered clip), scene windows with a film excerpt and an outtake still, music
bed from a file, sound effects, a post-credits scene with an audio-driven figure and lights out
-> credits.mp4 + credits_sheet.png + cache/credits/timeline.json, --append -> film_with_credits.mp4."""
from common import (FPS, Test, audio_samples, expect, expect_film, full, need, read_json, script, tone, video_frames,
                    write_json)

CREDITS = script("film-finish", "credits.py")
GAG_S, POST_S, BLACK_BEFORE, BLACK_AFTER = 1.5, 2.0, 0.5, 0.5


def credits_spec():
    gag = {"name": "e2e_gag", "duration": GAG_S, "set": {"name": "stage", "dim": 0.3}, "items": [
        {"type": "screen", "box": [760, 170, 1180, 470], "steps": [
            {"at": 0, "title": "ULTRA", "line": "0 left", "red": True},
            {"at": 0.6, "title": "ULTRA PLUS", "line": "99 %", "bar": [0.9, 0.99], "shake": 0.3}]},
        {"figure": "hero.png", "mouth_at": [100, 80], "x": 380, "feet": 700, "height": 420,
         "mouth": [[0, "flat"], [0.5, "open"], [1.0, "o"]],
         "moves": [{"do": "bob", "from": 0, "to": 0.5}, {"do": "jump", "at": 0.5, "dur": 0.4},
                   {"do": "tilt", "from": 1.0, "to": 1.5, "angle": -6}]},
        {"type": "desk"},
        {"type": "bubble", "text": "Hello? Anybody?", "x": 640, "y": 160, "tail": [420, 300], "at": 0.2, "to": 1.2},
        {"type": "bang", "text": "BANG!", "at": 0.9, "to": 1.4, "x": 150, "y": 380},
        {"type": "prop", "card": {"title": "BILL", "rows": [["Tokens", "3"]], "total": ["TOTAL:", "all"]},
         "x": 900, "y": 300, "path": "drop", "dur": 0.8, "at": 0.3},
        {"type": "clip", "frames": "clip/f.%04d.png", "x": 1000, "y": 520, "at": 0.4},
        {"type": "caption", "text": "to be continued", "at": 1.0}],
        "sounds": [{"at": 0.5, "sfx": "click.wav", "level": 0.8}],
        "zoom": {"at": 1.1, "dur": 0.3, "to": 1.5, "center": [380, 330]}}
    post = {"name": "e2e_post", "duration": POST_S, "set": {"color": "#16121c"}, "items": [
        {"type": "spot", "x": 640, "top": 80, "bottom": 260, "alpha": 40},
        {"figure": "silhouette", "height": 420, "x": 640, "feet": 560, "mouth": [[0, "grin"], [0.4, "grin", 1.4]],
         "audio": {"file": "laugh.wav", "at": 0.5, "level": 0.8, "shake": 7}},
        {"type": "desk", "box": [300, 540, 980, 580], "color": "#2b1d14"},
        {"type": "count", "source": [430, 530], "target": [850, 530], "n": 4, "moves": 3, "every": 0.3,
         "sfx": "click.wav", "level": 0.5},
        {"type": "zzz", "x": 420, "y": 400, "at": 0.2, "to": 1.0}],
        "lights_out": {"at": 1.5, "fade": 0.125, "keep_mouths": True}}
    return {"text": [["head", "E2E!"], ["sub", "A test"], ["gap"], ["role", "Tim", "the tester"],
                     ["head2", "Made with"], ["role", "Animation"], ["name", "Python"]],
            "speed": 300, "layout": "text_left", "gag_order": "as_listed",
            "windows": {"film": "film.mp4", "times": [1.0, 2.5], "every": 0.5, "outtakes": ["outtakes/still.png"]},
            "music": {"file": "music.wav", "from": 0.0, "text": 0.22, "gag": 0.6},
            "gags": [gag], "black_before": BLACK_BEFORE, "post": post, "black_after": BLACK_AFTER, "append": True}


def run_credits(ctx):
    need("ffmpeg")
    d = ctx.dir
    tone(ctx, d / "song.wav", 4.0)
    tone(ctx, d / "music.wav", 3.0, freq=196)
    tone(ctx, d / "laugh.wav", 1.0, freq=330)
    ctx.ff("-f", "lavfi", "-i", "sine=f=1500:d=0.08", d / "click.wav")
    ctx.ff("-f", "lavfi", "-i", "testsrc2=s=1280x720:r=24", "-f", "lavfi", "-i", "sine=f=440:r=48000",
           "-frames:v", "96", "-shortest", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", d / "film.mp4")
    (d / "outtakes").mkdir()
    ctx.ff("-f", "lavfi", "-i", "smptebars=s=640x360", "-frames:v", "1", d / "outtakes" / "still.png")
    ctx.ff("-f", "lavfi", "-i", "color=c=0x3080c0@0.8:s=200x420,format=rgba", "-frames:v", "1", d / "hero.png")
    (d / "clip").mkdir()
    ctx.ff("-f", "lavfi", "-i", "testsrc=s=160x90:r=24", "-frames:v", "12", d / "clip" / "f.%04d.png")
    write_json(d / "project.json", {"name": "E2E credits", "fps": FPS, "seed": 7, "look": "standard" if full() else "none",
                                    "sections": [{"name": "a", "from": 0.0, "to": 4.0}], "credits": credits_spec()})
    log = ctx.uv(CREDITS, "--project", d, "--append", timeout=900).stdout

    tl = read_json(d / "cache" / "credits" / "timeline.json")
    segs = tl["segments"]
    kinds = [s[0] for s in segs]
    expect(kinds == ["text", "gag", "text", "black", "post", "black"], f"timeline segments {kinds}")
    expect(all(segs[i][2] == segs[i + 1][1] for i in range(len(segs) - 1)) and segs[0][1] == 0,
           f"segments not contiguous: {segs}")
    length = {k: b - a for k, a, b in segs}
    expect(segs[0][2] - segs[0][1] == segs[2][2] - segs[2][1] > 12, f"text parts differ / too short: {segs}")
    for kind, sec in (("gag", GAG_S), ("post", POST_S)):
        expect(length[kind] == int(sec * FPS + 1e-6), f"{kind}: {length[kind]} frames, expected {sec * FPS:.0f}")
    expect([b - a for k, a, b in segs if k == "black"] == [int(BLACK_BEFORE * FPS), int(BLACK_AFTER * FPS)],
           f"black segments {segs}")
    total = tl["frames"]
    expect(total == segs[-1][2], f"timeline frames {total} vs segments end {segs[-1][2]}")
    expect_film(ctx, d / "credits.mp4", total)
    expect((d / "credits_sheet.png").exists(), "credits_sheet.png missing")
    for line in ("credits: layout text_left, 2 text parts", "window 1.1: ", "outtake outtakes/still.png",
                 "sound: music = 1 stem(s), ", "0 decode errors"):
        expect(line in log, f"credits.py output lacks '{line}'")
    n_ev = int(log.split("sound: music = 1 stem(s), ")[1].split(" sound events")[0])
    expect(n_ev == 1 + 1 + 3, f"{n_ev} sound events placed, expected 5 (gag click, laugh, 3 chip clicks)")
    # the laugh of the audio-driven figure is heard in the post scene, the black before it is silent-ish
    a = audio_samples(d / "credits.mp4")
    sr = 48000
    post_a = segs[4][1] / FPS
    laugh = max(abs(x) for x in a[int((post_a + 0.6) * sr):int((post_a + 1.2) * sr)])
    black = max(abs(x) for x in a[int((segs[3][1] / FPS + 0.3) * sr):int((post_a - 0.05) * sr)])
    expect(laugh > 4 * max(black, 30), f"post-scene laugh peak {laugh} vs black {black}")
    n_film, n_all = video_frames(d / "film.mp4"), video_frames(d / "film_with_credits.mp4")
    expect(n_all == n_film + total, f"film_with_credits: {n_all} frames, expected {n_film} + {total}")
    ctx.note(f"{total} frames ({', '.join(f'{k} {length[k]}' for k in ('gag', 'post'))}), {n_ev} sound events, "
             f"laugh peak {laugh} vs black {black}, film_with_credits {n_all} frames")


TESTS = [Test("film-finish-credits", run_credits,
              about="credits.py: text roll + gag + scene windows (excerpt, outtake) + post scene -> credits.mp4, --append")]
