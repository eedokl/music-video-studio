"""A dialogue of two people (0.36.0): ai-video cut_check.py tells a hard cut from a dissolve and repairs it,
claudia-music-video dialogue_clips.py plans the clips of a "dialogue" block, silences a voice from off in the lip-sync
audio, checks takes and writes one take into selection.json for both of its shots; ai-video master_crops.py cuts the
singles out of a master picture; voice.py reports a line whose pitch falls out and builds the ElevenLabs dialogue
request. No GPU, no network: the takes are synthetic clips."""
import json
import struct

from common import FPS, Test, audio_samples, expect, need, read_json, script, tone, video_frames, write_json

NEW = script("song-analysis", "new_project.py")
CUT = script("ai-video", "cut_check.py")
MASTER = script("ai-video", "master_crops.py")
DIALOGUE = script("claudia-music-video", "dialogue_clips.py")
VOICE = script("voice", "voice.py")


def two_shots(ctx, out, at, dissolve=0.0, seconds=6.0):
    """A light shot, then a dark one from `at` s - a hard cut, or a cross-fade of `dissolve` s around it."""
    a, b = ["-f", "lavfi", "-i", f"color=c=0xB0B0B0:s=320x180:r={FPS}:d={seconds}"], \
           ["-f", "lavfi", "-i", f"color=c=0x202020:s=320x180:r={FPS}:d={seconds}"]
    if dissolve:
        f = f"[0:v][1:v]xfade=transition=fade:duration={dissolve}:offset={at - dissolve / 2},trim=duration={seconds}[v]"
    else:
        f = f"[0:v]trim=duration={at}[a];[1:v]trim=duration={seconds - at},setpts=PTS-STARTPTS[b];[a][b]concat=n=2:v=1[v]"
    ctx.ff(*a, *b, "-filter_complex", f, "-map", "[v]", "-r", FPS, "-c:v", "libx264", "-crf", "14", "-pix_fmt", "yuv420p", out)
    write_json(out.with_suffix(".json"), {"fps": FPS, "frames": video_frames(out), "song_start": 0.4, "delay_frames": 0})
    return out


def png_size(path):
    with open(path, "rb") as f:
        head = f.read(24)
    return struct.unpack(">II", head[16:24])


def run_dialogue(ctx):
    need("ffmpeg")
    song = tone(ctx, ctx.dir / "song.wav", 10.0)
    lyr = ctx.dir / "lyrics.txt"
    lyr.write_text("Zwölf Minuten.\nSeit zwanzig Minuten.\nSiehst du.\n", encoding="utf-8")
    d = ctx.dir / "talk"
    ctx.uv(NEW, d, "--song", song, "--lyrics", lyr, "--language", "de")
    (d / "analysis").mkdir(exist_ok=True)
    (d / "analysis" / "vocals_lead.wav").write_bytes(song.read_bytes())
    (d / "ai" / "master").mkdir(parents=True)
    ctx.ff("-f", "lavfi", "-i", "testsrc2=size=1920x1056", "-frames:v", "1", d / "ai" / "master" / "master.png")
    P = read_json(d / "project.json")
    P.update({"delivery": "speech", "sections": [
        {"name": "s01", "from": 0.5, "to": 3.0, "who": "max", "sing": "Zwölf Minuten.", "lyrics": False},
        {"name": "s02", "from": 3.0, "to": 6.0, "who": "ida", "sing": "Seit zwanzig Minuten.", "lyrics": False},
        {"name": "s03", "from": 6.0, "to": 9.5, "who": ["max", "ida"], "sing": "Siehst du.", "lyrics": False}],
        "master": {"image": "ai/master/master.png", "size": [1280, 704],
                   "crops": {"him": "1152:634:0:110", "two": "1920:1056:0:0"},
                   "edits": {"him_talk": {"crop": "him", "change": "his mouth is open in the middle of a word."}}},
        "dialogue": {"image": "ai/master/two_crop.png", "set": "Medium shot of two people at a table, nothing behind them moves.",
                     "who": {"max": "the man in the blue jacket, on the left", "ida": "the woman in the green sweater, on the right"},
                     "off": [[6.0, 7.5]],
                     "clips": [{"name": "A", "shots": ["s01", "s02"], "cut": "frontal medium close-up from the chest up"},
                               {"name": "B", "shots": ["s03"]}]}})
    write_json(d / "project.json", P)

    # 1. the master picture: crops at the video size, a crop of another shape is refused
    ctx.uv(MASTER, d, "crops")
    for n in ("him", "two"):
        f = d / "ai" / "master" / f"{n}_crop.png"
        expect(f.exists() and png_size(f) == (1280, 704), f"master_crops.py crops: {n}_crop.png missing or not 1280x704")
    out = ctx.uv(MASTER, d, "edits", "--dry-run").stdout
    expect("him_talk v1" in out and "him_talk v2" in out, f"master_crops.py edits --dry-run lists no variants:\n{out}")
    bad = dict(P, master=dict(P["master"], crops={"him": "1000:1000:0:0"}))
    write_json(d / "project.json", bad)
    r = ctx.uv(MASTER, d, "crops", check=False)
    expect(r.returncode != 0 and "squeezed" in r.stdout + r.stderr, "a crop of another shape than the video frame was accepted")
    write_json(d / "project.json", P)

    # 2. the plan: one clip with a cut for the exchange, one without for the answer to the off voice
    out = ctx.uv(DIALOGUE, d, "plan").stdout
    expect("== A  shots s01+s02" in out and "== B  shots s03" in out, f"dialogue_clips.py plan lists not both clips:\n{out}")
    expect("A hard cut transitions to a frontal medium close-up" in out and 'says the words "Zwoelf Minuten"' in out,
           f"the cut sentence or the spoken words are missing (umlauts written out, no full stop):\n{out}")
    expect("the woman in the green sweater, on the right, facing the camera" in out, "the second speaker's identifiers are not repeated after the cut")
    expect("listens to a voice that comes from off screen" in out and out.count("A hard cut") == 1,
           f"clip B does not open on the off voice, or it cuts:\n{out}")
    expect("PROBLEM" not in out, f"plan reports problems on a valid block:\n{out}")
    long = json.loads(json.dumps(P))
    long["sections"][1]["to"] = long["sections"][2]["from"] = 9.2
    long["sections"][2]["to"] = 9.9
    write_json(d / "project.json", long)
    r = ctx.uv(DIALOGUE, d, "plan", check=False)
    expect(r.returncode != 0 and "split it" in r.stdout, f"an exchange of 8.8 s was not refused:\n{r.stdout}")
    write_json(d / "project.json", P)

    # 3. the lip-sync audio: the off voice is silent in it, the rest is the voices track
    ctx.uv(DIALOGUE, d, "lips")
    lips = audio_samples(d / "analysis" / "vocals_lips.wav")
    peak = lambda t0, t1: max(abs(x) for x in lips[int(t0 * 48000):int(t1 * 48000)])   # noqa: E731
    expect(peak(6.3, 7.2) < 0.001, f"the off voice is still in the lip-sync audio (peak {peak(6.3, 7.2):.3f})")
    expect(peak(2.0, 3.0) > 0.05 and peak(8.0, 9.0) > 0.05, "the lip-sync audio lost the spoken parts")

    # 4. takes: a hard cut, a dissolve, a clip that must not cut
    takes = d / "ai" / "ltx25"
    takes.mkdir(parents=True)
    hard = two_shots(ctx, takes / "dlg_A_sd7.mp4", 2.5)
    soft = two_shots(ctx, takes / "dlg_A_sd8.mp4", 2.5, dissolve=0.5)
    two_shots(ctx, takes / "dlg_B_sd7.mp4", 2.0)
    res = json.loads(ctx.uv(CUT, hard, soft, "--json").stdout)
    h, s = res[str(hard)], res[str(soft)]
    expect(h["kind"] == "hard" and abs(h["frame"] - 60) <= 1, f"cut_check.py on a hard cut at frame 60: {h}")
    expect(s["kind"] == "dissolve" and s["first"] >= 52 and s["last"] <= 68 and s["last"] - s["first"] >= 8,
           f"cut_check.py on a 12-frame dissolve around frame 60: {s}")
    out = ctx.uv(DIALOGUE, d, "check").stdout
    expect("dlg_A_sd7.mp4" in out and "hard cut" in out and "the speaker changes at 3.00 s" in out, f"check: hard cut not reported\n{out}")
    expect("DISSOLVE" in out and "this clip should not cut" in out, f"check: the dissolve or the unwanted cut is not flagged\n{out}")
    expect((takes / "sheets" / "dlg_A_sd8.jpg").exists(), "check wrote no strip of the take")

    # 5. select: one take for both shots of the clip; --harden replaces the dissolve, length kept
    out = ctx.uv(DIALOGUE, d, "select", "A=8").stdout
    expect("DISSOLVES" in out, f"select took a dissolving take without a word:\n{out}")
    ctx.uv(DIALOGUE, d, "select", "A=8", "--harden")
    sel = read_json(d / "selection.json")
    want = "ai/ltx25/dlg_A_sd8_hc.mp4"
    expect(sel["clip"]["s01"]["file"] == want and sel["clip"]["s02"]["file"] == want and sel["manual"]["clip"]["s02"]["file"] == want,
           f"selection.json does not give both shots the hardened take: {sel}")
    hc = takes / "dlg_A_sd8_hc.mp4"
    r = json.loads(ctx.uv(CUT, hc, "--json").stdout)[str(hc)]
    expect(r["kind"] == "hard" and video_frames(hc) == video_frames(soft), f"the hardened take: {r}, {video_frames(hc)} frames")
    expect(read_json(hc.with_suffix(".json")).get("song_start") == 0.4, "the hardened take lost its song_start")

    # 6. voices: a line whose pitch falls out of its character's range; the dialogue request
    out = ctx.py("import sys, json\nsys.path.insert(0, sys.argv[1])\nimport voice\n"
                 "print(json.dumps(voice.pitch_outliers([('a', 180), ('a', 190), ('a', 154), ('a', 198), ('b', 110), ('b', 150)])))\n",
                 deps_from=(VOICE,), args=(str(VOICE.parent),)).stdout
    expect(json.loads(out.strip().splitlines()[-1]) == [2], f"pitch_outliers: {out}")
    P["voices"] = {"max": {"engine": "elevenlabs", "voice_id": "VOICE_M"}, "ida": {"engine": "elevenlabs", "voice_id": "VOICE_I"}}
    write_json(d / "project.json", P)
    write_json(d / "turns.json", [{"who": "max", "text": "[cheerful] Zwölf Minuten.", "name": "s01"},
                                  {"who": "ida", "text": "[deadpan] Seit zwanzig Minuten.", "name": "s02"}])
    body = json.loads(ctx.uv(VOICE, "dialogue", d / "turns.json", "-o", d / "take.mp3", "--project", d, "--dry-run").stdout)
    expect([i["voice_id"] for i in body["inputs"]] == ["VOICE_M", "VOICE_I"] and body["model_id"] == "eleven_v3",
           f"voice.py dialogue --dry-run: {body}")
    expect(not (d / "take.mp3").exists(), "voice.py dialogue --dry-run wrote a file")
    ctx.note(f"hard cut at frame {h['frame']}, dissolve frames {s['first']}-{s['last']} hardened, 2 clips planned, off voice "
             "silent in the lip-sync audio, selection for both shots, pitch outlier found")


TESTS = [Test("dialogue-clips", run_dialogue, about="two people: cut check + repair, dialogue clips plan / lips / check / select, master crops, directed voices")]
