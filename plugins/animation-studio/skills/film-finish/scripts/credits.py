# /// script
# requires-python = ">=3.12"
# dependencies = ["numpy==2.5.4", "pillow==13.0.0", "svgelements==1.9.6"]
# [tool.uv]
# exclude-newer = "2026-11-14T00:00:00Z"
# ///
"""End credits like in the cinema: slowly rolling text in blocks, short gag scenes between the blocks, "scene windows"
beside the text with excerpts of the finished film (and outtakes), a music bed (instrumental, quiet under the text,
louder in the gags), soft sound effects, an optional post-credits scene after black, then black.
-> credits.mp4 (with the look); --append -> film_with_credits.mp4 (film.mp4 stays untouched).

  python credits.py [--project .] --draft [--gags N] [--force]   first credits from the project -> project.json "credits"
  python credits.py [--project .] [--append] [--to s]              build (--to: only the first s seconds, quick test)
Run with: uv run credits.py ...   (PREVIEW=1 = NVENC)
The credits show film excerpts -> rebuild them after every new film (build.py film does it when "credits" is set).

project.json "credits" (all optional except "text"):
  "text":   [["head", "PROMPTS!"], ["sub", "A music video"], ["gap"], ["role", "Tim", "the user on the free plan"],
             ["head2", "Drawn & moved with"], ["role", "Animation"], ["name", "Synfig"], ...]
            kinds: head (big title), head2 (block heading), sub, role (small), name (big), gap; ["role", r, n] = both.
            The text is ONE roll, cut into len(gags)+1 equal parts; a gag plays between two parts.
  "speed": 57.6        roll speed in px/s (the reference: 2.4 px per frame)
  "layout": "text_left" | "text_right" | "text_center"   (default: picked by the seed)
  "gags": [gag, ...]   see GAG below;  "gag_order": "seed" (default) | "as_listed"
  "windows": {"film": "film.mp4", "times": [4.2, 61.5] | "auto", "seconds": 6.25, "every": 10, "outtakes": [...] | "auto"}
            one window per ~"every" s of text (one after another); auto = seeded picks spread over the film (dark
            frames skipped); "seconds" = excerpt length (looped), default = the window's time on screen;
            outtakes = rejected takes the project kept: a video, a frame folder or a still
            ({"path": "outtakes/take2.mp4", "label": "Take 2", "from": 0.0, "sounds": [{"at": 0.55, "sfx": ...}]});
            "auto" looks into <project>/outtakes/. 3D films: "out/<clip>/film" = the rendered frames of a clip (the
            quality falls back to preview / draft); "label": "" = no label (a film excerpt from raw frames).
  "music": {"stems": ["stems/*.wav"] | "file": "x.wav", "from": 46.0, "text": 0.22, "gag": 0.6, "post": 0.0}
            default: instrumental project stems, else Demucs no_vocals (cache/sep), else song minus the vocal stems
            (if they cancel), else Demucs is run (song-analysis separate_vocals.py, GPU lock; "demucs": false = no),
            else the song quietly. "from" = song second where the bed starts; looped (1 s crossfade) if too short.
  "sfx_gain": 0.35     sound effects ~9 dB down, 6 kHz low-pass, 12 ms fades (hard clicks sounded "like a broken box")
  "post": GAG          optional post-credits scene, after "black_before" s of black (default 2), then 1 s black
  "append": true       build.py film appends the credits automatically when "credits" is set

GAG = {"name": "quota", "duration": 7, "set": "room" | {"name": "stage", "dim": 0.35} | {"image": "x.png"} |
       {"color": "#16121c"}, "items": [...], "sounds": [{"at": 1.0, "sfx": "fit/key/medium" | "file.wav", "level": 0.5}],
       "zoom": {"at": 3.2, "dur": 0.8, "to": 2.3, "center": [380, 330]}, "lights_out": {"at": 7.1, "keep_mouths": true},
       "fade": true}
  Bundled sets (toon-2d): back layers under the items, front layers (curtains) over them ("front": false = none). Coordinates: 1280x720 px
  (the credits are composed at 1280x720 and scaled to project.json "size" when it differs).
  Every item may have "at" / "to" (seconds) and "fade_in" / "fade_out" (seconds). Items are drawn in list order.
  figure  {"figure": "tim" | "lia" | "fips" | "pip" | "silhouette" | "figure.svg" | "figure.png", "x": 380, "feet": 800,
           "height": 600, "mouth": "smile" | [[0, "flat"], [2.7, "open"], [4, "o"]] (shapes: smile o open flat grin none;
           [t, "grin", 1.6] = wider), "mouth_at": [x, y] (PNG px, for own PNGs), "silhouette": true,
           "moves": [{"do": "bob"|"jump"|"fall"|"rise"|"tilt"|"drift"|"sink"|"startle"|"wave", ...}],
           "audio": {"file": "laugh.wav", "at": 4.9, "level": 0.8, "shake": 7}}   mouth + shoulders follow its loudness
           Bundled figures are exported from their rig SVG WITHOUT mouth (Inkscape) - the mouths are drawn here.
  screen  {"box": [700, 170, 1180, 500], "steps": [{"at": 0, "title": "ULTRA", "line": "0 prompts left", "red": true,
           "bar": [0.99, 0.999], "glow": 1.6, "shake": 0.75}]}             monitor with text (eyes when no bar)
  banner  {"steps": [{"at": 0, "text": "Session expires in 3 ..."}], "y": 90}                       box at the top
  bubble  {"text": "Hello?", "x": 600, "y": 200, "tail": [420, 330]}                                speech bubble
  caption {"text": "...", "at": 5.5}                                                               line at the bottom
  bang    {"text": "BANG!", "at": 4.9, "to": 5.6, "x": 150, "y": 420, "size": 1.0, "grow": 0.4}  comic lettering
  prop    {"image": "x.png" | "card": {"title", "rows": [[a, b]], "total": [a, b]}, "x": 670, "y": 420,
           "path": "static" | "drop" (swings in from the top) | "fall" (hangs, then falls), "dur": 1.7, "drop": 360}
  desk    {"y": 548, "keyboard": [240, 520]}  or  {"box": [300, 520, 980, 560], "color": "#2b1d14"}
  spot    {"x": 640, "top": 80, "bottom": 260, "alpha": 40}                                         light cone
  zzz     {"x": 420, "y": 420}
  count   {"source": [430, 510], "target": [850, 510], "n": 10, "moves": 9, "every": 0.5, "sfx": "knock/plastic"}  chips/coins
  clip    {"frames": "folder" | "f.%04d.png" | "clip.mp4", "x": 0, "y": 0, "scale": 1.0}  any rendered clip
           (e.g. toon-2d figure_3d.py frames: a 2D figure turning into 3D) - transparent PNGs are composited
"""
# Code map: credits.py = CLI, planning (layout, gag order, timeline, scene-window picks), the picture pass, the
# finish (mux, look, checks, sheet, --append) and --draft;  credits_parts.py = the renderers of the parts (text roll
# with scene windows, gag / post-credits scenes);  credits_media.py = frame size, colours, fonts, sources (sets,
# figures, clips, sounds) and the sound track (music bed + sound effects).
import argparse
import json
import subprocess
import sys

import numpy as np
from PIL import Image

import _studio  # noqa: E402
_studio.use("song-analysis", "characters")
import creative  # noqa: E402
from encoding import h264  # noqa: E402
from media import check_video, contact_sheet, duration, ffmpeg  # noqa: E402
from encode import place  # noqa: E402
from song_project import Project  # noqa: E402
from credits_media import W, H, Assets, nframes, sound_track, video_frames  # noqa: E402
from credits_parts import LAYOUTS, Gag, Roll, window_loader  # noqa: E402


APPEND_TO = {}


# ============================================================ planning: layout, parts, timeline, scene windows
def plan_parts(P, C):
    """-> (layout, gags in playing order, number of text parts). Layout and gag order follow the seed."""
    layout = C.get("layout") or creative.pick(P, "credits:layout", list(LAYOUTS))
    gags = list(C.get("gags", []))
    if C.get("gag_order", "seed") == "seed" and len(gags) > 1:
        creative.rng(P, "credits:gag_order").shuffle(gags)
    return layout, gags, int(C.get("parts", len(gags) + 1))


def plan_timeline(C, gags, n_parts):
    """timeline: text | gag | text | ... | text | black | post | black  -> [(kind, text part / gag / seconds), ...]"""
    plan = []
    for k in range(n_parts):
        plan.append(("text", k))
        if k < len(gags) and k < n_parts - 1:
            plan.append(("gag", gags[k]))
    for g in gags[n_parts - 1:]:
        plan.append(("gag", g))
    if C.get("post"):
        plan.append(("black", float(C.get("black_before", 2.0))))
        plan.append(("post", C["post"]))
    plan.append(("black", float(C.get("black_after", 1.0))))
    return plan


def find_outtakes(P):
    d = P.dir / "outtakes"
    if not d.is_dir():
        return []
    out = []
    for p in sorted(d.iterdir()):
        if p.is_dir() and any(p.glob("*.png")) or p.suffix.lower() in (".mp4", ".mov", ".webm", ".png", ".jpg"):
            out.append({"path": str(p.relative_to(P.dir)), "label": "Outtake"})
    return out


def pick_excerpt_times(film, n_win, n, fps, rng):
    """One seeded excerpt start per slot of the film; dark frames are skipped (up to 6 tries)."""
    dur = duration(film)
    times = []
    for k in range(n_win):
        lo, hi = dur * k / n_win, dur * (k + 1) / n_win - n / fps
        t = lo
        for _ in range(6):
            t = max(0.0, rng.uniform(lo + 0.5, max(lo + 0.5, hi)))
            fr = video_frames(film, t, 1, (64, 36))
            if fr and np.asarray(fr[0].convert("L")).mean() > 30:
                break
        times.append(round(t, 2))
    return times


def place_outtakes(specs, outt, n_win, rng):
    """Outtakes take seeded window slots (at most every other window); without film excerpts they are the windows."""
    if outt and specs:
        slots = rng.sample(range(min(len(specs), n_win)), max(1, min(len(outt), min(len(specs), n_win) // 2)))
        for s, o in zip(sorted(slots), outt):
            specs[s] = {"outtake": o}
    elif outt:
        specs = [{"outtake": o} for o in outt]
    return specs


def plan_windows(P, C, A, n_parts, part_n, rng, layout):
    """-> per text part a list of (loader -> frames, label): one window per ~"every" seconds of text (default 10)."""
    w = C.get("windows", {})
    film = P.path(w.get("film", C.get("film", "film.mp4")))
    size = LAYOUTS[layout]["win"]
    per = max(1, round(part_n / P.fps / float(w.get("every", 10.0))))
    n_win = per * n_parts
    n = nframes(float(w["seconds"]), P.fps) if w.get("seconds") else -(-part_n // per)
    specs = []
    times = w.get("times", "auto")
    if film and film.exists():
        if times == "auto":
            times = pick_excerpt_times(film, n_win, n, P.fps, rng)
        specs = [{"film": t} for t in times]
    elif times != "auto":
        print(f"  windows: film {film} missing - no scene windows")
    outt = w.get("outtakes", "auto")
    outt = find_outtakes(P) if outt == "auto" else [o if isinstance(o, dict) else {"path": o} for o in outt]
    specs = place_outtakes(specs, outt, n_win, rng)
    wins = []
    for k in range(n_parts):
        part = []
        for j in range(per if specs else 0):
            s = specs[(k * per + j) % len(specs)]
            snd = [] if "film" in s else [(float(x.get("at", 0)) - float(s["outtake"].get("from", 0)), x["sfx"],
                                           float(x.get("level", 1.0))) for x in s["outtake"].get("sounds", [])]
            part.append((window_loader(s, film, A, size, n),
                         None if "film" in s else s["outtake"].get("label", "Outtake"), snd))
            print(f"  window {k + 1}.{j + 1}: " + (f"film {s['film']:.2f} s" if "film" in s
                                                    else f"outtake {s['outtake']['path']}"))
        wins.append(part)
    return wins


# ============================================================ picture: every part, frame by frame, into one video
def part_frames(kind, x, roll, wins, A, fps):
    """-> (frame iterator, gag or None) of one timeline entry."""
    if kind == "text":
        return roll.frames(x, wins[x], fade_in=True, fade_out=True), None
    if kind == "black":
        blk = Image.new("RGB", (W, H))
        return (blk for _ in range(nframes(x, fps))), None
    g = Gag(x, A, fps, "post" if kind == "post" else "gag")
    return (g.render(f) for f in range(g.n)), g


def render_picture(plan, roll, wins, A, fps, pic, max_f=None):
    """Encode the timeline to pic (stops after max_f frames). -> (frames, segments [(kind, a, b)], sound events)."""
    enc = subprocess.Popen([ffmpeg(), "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                            "-r", str(fps), "-i", "-", *h264(), "-pix_fmt", "yuv420p", str(pic)], stdin=subprocess.PIPE)
    fno, segments, events = 0, [], []
    for kind, x in plan:
        a = fno
        frames, g = part_frames(kind, x, roll, wins, A, fps)
        if g is not None:
            events += [(a + e[0],) + tuple(e[1:]) for e in g.sounds()]
        if kind == "text" and wins[x]:                 # sounds of the outtakes in the scene windows
            slot = roll.part_n / len(wins[x])
            for j, w in enumerate(wins[x]):
                w0, w1 = int(round(j * slot)), int(round((j + 1) * slot))
                for at, sfx, lvl in (w[2] if len(w) > 2 else []):
                    f = w0 + nframes(at, fps) if at >= 0 else -1
                    if w0 <= f < w1:
                        events.append((a + f, sfx, lvl, 6000, False))
        for img in frames:
            if max_f is not None and fno >= max_f:
                break
            enc.stdin.write(img.tobytes())
            fno += 1
        segments.append((kind, a, fno))
        if max_f is not None and fno >= max_f:
            break
    enc.stdin.close()
    enc.wait()
    return fno, segments, events


# ============================================================ finish: mux, look, checks
def mux(P, pic, wav, total, fps, raw):
    """Picture + sound -> raw (scaled to project.json "size" when it is not 1280x720)."""
    vcodec = ["-c:v", "copy"] if P.size == (W, H) else [
        "-vf", f"scale={P.size[0]}:{P.size[1]}:flags=lanczos,setsar=1", *h264(), "-pix_fmt", "yuv420p"]
    subprocess.run([ffmpeg(), "-y", "-v", "error", "-i", str(pic), "-i", str(wav), "-map", "0:v", "-map", "1:a",
                    "-t", f"{total / fps:.3f}", *vcodec, "-c:a", "aac", "-b:a", "192k", str(raw)], check=True)
    return raw


def finish(P, C, A, raw, total, fps, layout, segments):
    """The film look on raw -> credits.mp4, timeline.json, decode check, contact sheet."""
    tmp = A.dir / "credits_tmp.mp4"
    if P.get("look", "cinema" if P.get("kind") == "film3d" else "standard") in ("cinema", "ad"):
        from clip_film import grade_video        # 3D films: the per-frame look of clip_film.py
        grade_video(raw, tmp, P.get("look", "cinema"))
    else:
        import build as film_build               # the same look step as the film
        film_build.look(P, raw, tmp)
    out = place(tmp, P.dir / C.get("out", "credits.mp4"))
    (A.dir / "timeline.json").write_text(json.dumps({"fps": fps, "frames": total, "layout": layout,
                                                     "segments": segments}, indent=1), encoding="utf-8")
    err = check_video(out)
    sheet = contact_sheet(out, P.dir / "credits_sheet.png", 4, 4, 480, fps)
    print(f"-> {out.name}: {total / fps:.1f} s, {out.stat().st_size / 1e6:.1f} MB, "
          f"{'0 decode errors' if not err else 'ERRORS: ' + err[:200]}; sheet {sheet.name}")
    return out


def build(P, quick_to=None, append=False):
    C = P.get("credits")
    if not C or not C.get("text"):
        raise SystemExit('project.json has no "credits" text - run credits.py --draft first')
    fps = P.fps
    A = Assets(P)
    rng = creative.rng(P, "credits")
    layout, gags, n_parts = plan_parts(P, C)
    roll = Roll(P, C, A, n_parts, layout, rng)
    print(f"credits: layout {layout}, {n_parts} text parts x {roll.part_n} frames, gags: "
          + (", ".join(g.get("name", "?") for g in gags) or "none") + (", post-credits scene" if C.get("post") else ""))
    wins = plan_windows(P, C, A, n_parts, roll.part_n, creative.rng(P, "credits:excerpts"), layout)
    plan = plan_timeline(C, gags, n_parts)
    total, segments, events = render_picture(plan, roll, wins, A, fps, A.dir / "picture.mp4",
                                             nframes(quick_to, fps) if quick_to else None)
    print(f"  {total} frames = {total / fps:.1f} s; " + ", ".join(f"{k}:{a}-{b}" for k, a, b in segments))
    wav = sound_track(P, C, A, segments, events, total, fps)
    raw = mux(P, A.dir / "picture.mp4", wav, total, fps, A.dir / "credits_raw.mp4")
    out = finish(P, C, A, raw, total, fps, layout, segments)
    if append:
        append_to_film(P, out)


def append_to_film(P, credits):
    C = P.get("credits")
    film = P.path(APPEND_TO.get("film") or C.get("append_to", "film.mp4"))
    if not film.exists():
        raise SystemExit(f"{film.name} missing - build the film first")
    tmp = P.cache / "credits" / "film_with_credits_tmp.mp4"
    from media import has_audio
    silent = [k for k, f in enumerate((film, credits)) if not has_audio(f)]     # a silent film: add silence
    au = "".join(f"[{k}:a]aresample=48000,aformat=channel_layouts=stereo[a{k}];" if k not in silent else
                 f"anullsrc=r=48000:cl=stereo,atrim=duration={duration(f):.3f}[a{k}];"
                 for k, f in enumerate((film, credits)))
    fc = (f"[0:v]fps={P.fps},format=yuv420p,setsar=1[f0];[1:v]fps={P.fps},format=yuv420p,setsar=1[c1];"
          "[c1][f0]scale2ref=flags=lanczos[v1][v0];"                  # the credits in the size of the film (previews)
          f"{au}[v0][a0][v1][a1]concat=n=2:v=1:a=1[v][a]")
    subprocess.run([ffmpeg(), "-y", "-v", "error", "-i", str(film), "-i", str(credits), "-filter_complex", fc,
                    "-map", "[v]", "-map", "[a]", *h264(), "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart",
                    str(tmp)], check=True)
    out = place(tmp, P.dir / "film_with_credits.mp4")
    err = check_video(out)
    print(f"-> {out.name}: {duration(out):.1f} s (film {duration(film):.1f} s + credits), "
          f"{out.stat().st_size / 1e6:.1f} MB, {'0 decode errors' if not err else 'ERRORS: ' + err[:200]}")


# ============================================================ draft
LABELS = {
    "de": {"video": "Ein Musikvideo", "cast": "Besetzung", "music": "Musik", "song": "Song", "made": "Gemacht mit",
           "heard": "Gehört & verstanden von", "assembled": "Zusammengesetzt mit", "section": "Abschnitt",
           "ai": "Enthält KI-generierte Inhalte", "assist": "Regie-Assistenz", "rest": "Alles dazwischen",
           "end": "Kein Modell wurde bei den Dreharbeiten verletzt.", "self": "als sich selbst", "fill": "(wer? bitte eintragen)",
           "roles": {"Vocals": "Gesang", "Vocals separated": "Gesang getrennt", "Every word heard": "Jedes Wort gehört",
                     "Beat & pitch": "Takt & Tonhöhe", "Lips": "Lippen", "Who sings": "Ohren (Mann? Frau?)",
                     "Figure rigs": "Figuren-Rigs", "Sound effects": "Geräusche", "Transitions": "Übergänge",
                     "Edit hand-off": "Schnitt-Übergabe", "Pop-up cards": "Pop-up-Karten", "stems": "Stems",
                     "earshot sound bank": "earshot-Geräuschbank"}},
    "en": {"video": "A music video", "cast": "Cast", "music": "Music", "song": "Song", "made": "Made with",
           "heard": "Heard & understood by", "assembled": "Put together with", "section": "Section",
           "ai": "Contains AI-generated content", "assist": "Directing assistant", "rest": "Everything in between",
           "end": "No model was harmed in the making of this film.", "self": "as themselves", "fill": "(who? fill in)",
           "roles": {}},
}


def detect_tools(P):
    """What was actually used, from the files the skills leave in the project. -> (per section, hearing, assembly, ai)"""
    a, c = P.analysis, P.cache
    per = {}
    for s in P.sections():
        t = []
        name = s["name"]
        sc = P.dir / "scenes"
        if (sc / f"{name}.sif").exists() or list(sc.glob(f"{name}*.sif")):
            t.append("Synfig")
        if list(sc.glob(f"{name}*.html")) or list(sc.glob(f"{name}/*.html")) or s.get("renderer") == "threejs":
            t.append("three.js")
        if s.get("set"):
            t.append(f"Krita ({s['set']})")
        if list((P.dir / "overlays").glob(f"{name}.mov")) if (P.dir / "overlays").is_dir() else False:
            t.append("Pillow")
        if s.get("renderer") in ("blender", "bricks") or list(sc.glob(f"{name}*.blend")):
            t.append("Blender")
        per[name] = t or ["?"]
    hear = []
    if P.get("stems"):
        hear.append(("Vocals", "stems"))
    if (c / "sep").is_dir():
        hear.append(("Vocals separated", "Demucs"))
    if (a / "song_sheet.json").exists():
        hear.append(("Every word heard", "Whisper"))
        hear.append(("Beat & pitch", "librosa"))
    if list(a.glob("*mouth*.json")):
        hear.append(("Lips", "Rhubarb Lip Sync"))
    if (a / "gender.json").exists() or (a / "assignment.json").exists():
        hear.append(("Who sings", "earshot"))
    asm = []
    if P.get("figures"):
        if any(str(f.get("svg", "")).endswith(".svg") for f in P.get("figures").values() if isinstance(f, dict)):
            asm.append(("Figure rigs", "Inkscape"))
    if (a / "sounds.wav").exists():
        asm.append(("Sound effects", "earshot sound bank"))
    if any(x.get("shaders") for x in P.get("transitions", []) or []):
        asm.append(("Transitions", "Shaders"))
    if (P.dir / "film.otio").exists() or (P.dir / "film.mlt").exists():
        asm.append(("Edit hand-off", "Kdenlive / melt"))
    if P.get("popups"):
        asm.append(("Pop-up cards", "Pillow"))
    blob = json.dumps(P.p).lower()
    ai = sorted({n for k, n in (("whisper", "Whisper"), ("demucs", "Demucs"), ("flux", "FLUX"), ("ltx", "LTX-Video"),
                                ("wan", "Wan"), ("depth", "Depth Anything"), ("qwen", "Qwen"), ("suno", "Suno"))
                 if k in blob} | {n for _, n in hear if n in ("Whisper", "Demucs")})
    return per, hear, asm, ai


def draft_text(P, lang):
    """First credits text from the project: title, cast, song, the tools found per section, AI label, end line."""
    L = LABELS[lang]
    per, hear, asm, ai = detect_tools(P)
    from figures import FIGURES
    text = [["head", str(P.get("title", {}) and P.get("title", {}).get("text") or P.get("name", "Untitled")).upper()],
            ["sub", L["video"]], ["gap"], ["head2", L["cast"]]]
    for name, f in (P.get("figures") or {}).items():
        about = (f or {}).get("role") or (FIGURES.get(name, {}).get("about", "").split(";")[0].split(",")[0]
                                          if lang == "en" else "") or L["self"]
        text.append(["role", name.capitalize(), about])
    text.append(["gap"])
    src = P.get("source") or {}
    song = src.get("title") or P.get("song_title") or P.get("name", "")
    tr = lambda x: L["roles"].get(x, x)
    text += [["role", L["song"], f"„{song}“" if lang == "de" else f"\"{song}\""],
             ["role", L["music"], str(P.get("music_by") or ("Suno (?)" if "Suno" in ai else L["fill"]))], ["gap"],
             ["head2", L["made"]]]
    for sec, tools in per.items():
        text.append(["role", f"{L['section']} „{sec}“" if lang == "de" else f"{L['section']} '{sec}'", " · ".join(tools)])
    text.append(["gap"])
    if hear:
        text.append(["head2", L["heard"]])
        text += [["role", tr(r), tr(n)] for r, n in hear]
        text.append(["gap"])
    text.append(["head2", L["assembled"]])
    text += [["role", tr(r), tr(n)] for r, n in asm] + [["role", L["rest"], "ffmpeg & Python"], ["role", L["assist"], "Claude"],
                                                ["gap"]]
    if "claudia" in json.dumps(P.p).lower():
        text.append(["sub", "Claudia by anabology"])
    text.append(["sub", f"{L['ai']}: " + ", ".join(ai + ["Claude"])])
    text.append(["sub", L["end"]])
    return text


def draft_gags(P, n_gags):
    """Gag skeletons from the song/project: screen texts, pop-up gag words, the figures (templates in seeded order)."""
    from figures import FIGURES
    figs = [n for n in (P.get("figures") or {}) if n.lower() in FIGURES or str((P.get("figures")[n] or {}).get("svg", "")).endswith(".svg")]
    words = [g.get("text", "") for g in P.get("gags", [])] + [s.get("text", "").split("\n")[0] for s in P.get("screen", [])]
    words = [w for w in words if w] or [str(P.get("name", "THE END")).upper()]
    r = creative.rng(P, "credits:draft")
    sets = [s.get("set") for s in P.sections() if s.get("set")]
    templates = ["screen", "bubble", "card"]
    r.shuffle(templates)
    gags = []
    for i in range(n_gags):
        kind = templates[i % len(templates)]
        hero = figs[i % len(figs)] if figs else "silhouette"
        w = words[i % len(words)]
        sset = {"name": "room" if kind == "screen" else (sets[0] if sets else "stage"), "dim": 0.4}
        gags.append(draft_gag(kind, hero, w, words, sset))
    return gags


def draft_gag(kind, hero, w, words, sset):
    """One gag skeleton: "screen" (a monitor upsell), "bubble" (the hero asks) or "card" (an invoice drops in)."""
    if kind == "screen":
        return {"name": f"screen_{w.lower().strip('!')}", "duration": 6, "set": sset, "items": [
            {"type": "screen", "steps": [{"at": 0, "title": w, "line": "0 left", "red": True},
                                         {"at": 2.8, "title": w + " PLUS", "line": "Welcome! (49.99 / hour)", "glow": 1.6,
                                          "shake": 0.7}]},
            {"figure": hero, "x": 380, "feet": 800, "mouth": [[0, "flat"], [2.8, "open"], [3.8, "o"]],
             "moves": [{"do": "bob", "from": 1.0, "to": 2.5}, {"do": "jump", "at": 2.9, "dur": 0.6}]},
            {"type": "desk"}, {"type": "bang", "text": w, "at": 3.0, "to": 3.7, "x": 120, "y": 400},
            {"type": "caption", "text": f"{hero.capitalize()} will be back ...", "at": 4.6}],
            "sounds": [{"at": 1.0 + 0.25 * k, "sfx": "fit/key/medium", "level": 0.5} for k in range(6)]
            + [{"at": 2.8, "sfx": "glitch/mid", "level": 0.6}, {"at": 3.0, "sfx": "cut_hit/punch", "level": 0.8}]}
    elif kind == "bubble":
        return {"name": f"bubble_{hero}", "duration": 5, "set": sset, "items": [
            {"figure": hero, "x": 640, "feet": 660, "mouth": [[0, "smile"], [0.8, "open"], [2.6, "smile"], [3.6, "o"]],
             "moves": [{"do": "wave", "from": 0, "to": 5}]},
            {"type": "bubble", "text": f"{w} ... {w}?", "x": 900, "y": 190, "tail": [700, 300], "at": 0.8, "to": 3.4},
            {"type": "caption", "text": "(to be continued)", "at": 3.6}],
            "sounds": [{"at": 0.8, "sfx": "ui_pop/blip", "level": 0.8}]}
    else:
        return {"name": "invoice", "duration": 5.5, "set": {"name": "room"}, "items": [
            {"type": "screen", "steps": [{"at": 0, "title": words[0], "line": "PLUS"}]},
            {"figure": hero, "x": 380, "feet": 800, "mouth": [[0, "flat"], [2.5, "o"]],
             "moves": [{"do": "rise", "at": 1.1, "dur": 0.75, "from": 450}]}, {"type": "desk"},
            {"type": "prop", "card": {"title": "INVOICE", "rows": [[x, "1"] for x in words[:3]], "total": ["TOTAL:", "all"]},
             "x": 670, "y": 300, "path": "drop", "dur": 1.7}],
            "zoom": {"at": 3.2, "dur": 0.8, "to": 2.0, "center": [380, 330]},
            "sounds": [{"at": 0.2, "sfx": "fit/whoosh.short/bamboo_swish", "level": 0.8}]}


def draft(P, n_gags=2, force=False):
    C = P.get("credits") or {}
    if C.get("text") and not force:
        raise SystemExit('project.json already has "credits" text - use --force to overwrite it')
    lang = "de" if str(P.get("language", "en")).startswith("de") else "en"
    text = draft_text(P, lang)
    gags = draft_gags(P, n_gags)
    C.update({"text": text, "gags": gags if (force or not C.get("gags")) else C["gags"],
              "windows": C.get("windows", {"times": "auto", "outtakes": "auto"}), "append": C.get("append", True)})
    P.p["credits"] = C
    P.file.write_text(json.dumps(P.p, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"draft: {len(text)} text lines, {len(gags)} gag(s) written to project.json 'credits'. Check every line "
          "(roles, who made the music, the AI label), rewrite the gags into jokes about THIS song, add a 'post' scene "
          "(audio-driven figure) if wanted, then run credits.py.")


def main():
    ap = argparse.ArgumentParser(description="End credits with gags, film excerpts and a post-credits scene.")
    ap.add_argument("--project", default=".")
    ap.add_argument("--draft", action="store_true", help="write a first credits text + gags into project.json")
    ap.add_argument("--gags", type=int, default=2, help="number of draft gags")
    ap.add_argument("--force", action="store_true", help="--draft overwrites existing credits text/gags")
    ap.add_argument("--append", action="store_true", help="also write film_with_credits.mp4 (film.mp4 untouched)")
    ap.add_argument("--to", type=float, help="only the first seconds (quick test)")
    ap.add_argument("--film", help="the film to append to (default: credits.append_to or film.mp4)")
    ap.add_argument("--clip-quality", help="3D films: take the clip frames out/<clip>/<q> in this quality first")
    a = ap.parse_args()
    if a.film:
        APPEND_TO["film"] = a.film
    if a.clip_quality:
        import credits_media
        credits_media.CLIP_QUALITY[0] = a.clip_quality
    sys.stdout.reconfigure(line_buffering=True)
    P = Project(a.project)
    P.check("film-finish")                 # project.json validated before any long step
    if a.draft:
        return draft(P, a.gags, a.force)
    build(P, a.to, a.append)


if __name__ == "__main__":
    main()
