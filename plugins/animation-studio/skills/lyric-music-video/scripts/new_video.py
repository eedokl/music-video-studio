"""Create a lyric-music-video project: song project (project.json, song.wav, lyrics.txt) + the three.js engine in video/.

  uv run --no-project --with numpy python new_video.py PROJECT --song song.mp3 --lyrics lyrics.txt [--language auto|de|en]
         [--lead vocals.wav --backing backing.wav] [--from 38.3 --to 58.3 --lyrics-from "first" --lyrics-to "last"]
         [--name "Title"] [--seed 4711] [--no-install]

Stems are checked against the mix first (length + envelope cross-correlation): a stem of another song version
stops the script - Suno "(Edit)" versions were seconds off and drifting.
lyrics.txt: the lyrics AS PERFORMED - one sung line per row (repeat repeated lines), [Section] headers such as
[Verse 1] [Pre-Chorus] [Chorus] [Bridge] [Final Chorus] [Outro]; "(stage directions)" rows are dropped here (kept in
lyrics_source.txt) so that every remaining row is a sung line for the alignment.
The project folder: project.json, song.wav, lyrics.txt, stems/, analysis/ (song-analysis), video/ (Vite + three.js
engine copied from assets/engine-template, `npm install` run unless --no-install), out/ (finished videos).
Keep the project path short on Windows (node_modules + MAX_PATH).
"""
import argparse
import json
import re
import shutil
import subprocess
from pathlib import Path

import _studio  # noqa: E402
_studio.use("song-analysis")
import creative  # noqa: E402
from media import decode, duration  # noqa: E402
from new_project import cut, trim_lyrics  # noqa: E402
from song_project import Project  # noqa: E402

SKILL = Path(__file__).resolve().parents[1]
TEMPLATE = SKILL / "assets" / "engine-template"


def copy_engine(dst):
    if (dst / "package.json").exists():
        print(f"{dst} exists - engine not copied again")
        return
    shutil.copytree(TEMPLATE, dst, ignore=shutil.ignore_patterns("node_modules", "dist", "out"))


def npm_install(video):
    npm = shutil.which("npm") or shutil.which("npm.cmd")
    if not npm:
        raise SystemExit("npm not found - install Node.js 20+ (https://nodejs.org), then run `npm install` in video/")
    subprocess.run([npm, "install", "--no-audit", "--no-fund"], cwd=video, check=True)


def stem_check(song, stem, max_lag=10.0):
    """Is the stem from the same version as the mix? -> (duration difference s, best lag s, correlation).
    Suno stems of another version (e.g. an "(Edit)") are seconds off and drift - then the timing is useless."""
    import numpy as np
    sr = 1000
    env = []
    for f in (song, stem):
        y = decode(f, 8000)
        k = len(y) // 8
        env.append(np.sqrt((y[:k * 8].reshape(k, 8) ** 2).mean(axis=1)))     # 1 kHz loudness envelope
    a, b = env
    n = min(len(a), len(b))
    a, b = a[:n] - a[:n].mean(), b[:n] - b[:n].mean()
    m = int(max_lag * sr)
    spec = np.fft.rfft(a, 2 * n) * np.conj(np.fft.rfft(b, 2 * n))
    cc = np.fft.irfft(spec)
    cc = np.concatenate([cc[-m:], cc[:m + 1]])
    k = int(np.argmax(cc))
    corr = float(cc[k] / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-9))
    return abs(duration(song) - duration(stem)), (k - m) / sr, corr


def main():
    ap = argparse.ArgumentParser(description="New lyric-music-video project.")
    ap.add_argument("folder")
    ap.add_argument("--song", required=True)
    ap.add_argument("--lyrics", required=True)
    ap.add_argument("--language", default="auto", help="Whisper language: de, en, ... or auto (mixed songs)")
    ap.add_argument("--lead", help="lead-vocal stem (Suno 'Vocals') - must come from the same version as the mix")
    ap.add_argument("--backing", help="backing-vocal stem")
    ap.add_argument("--from", dest="start", type=float)
    ap.add_argument("--to", dest="end", type=float)
    ap.add_argument("--lyrics-from")
    ap.add_argument("--lyrics-to")
    ap.add_argument("--name")
    ap.add_argument("--seed", type=int)
    ap.add_argument("--no-install", action="store_true")
    a = ap.parse_args()
    d = Path(a.folder).resolve()
    for k in ("lead", "backing"):
        if getattr(a, k):
            dd, lag, corr = stem_check(a.song, getattr(a, k))
            print(f"{k} stem vs mix: length differs by {dd:.2f} s, best offset {lag * 1000:+.0f} ms, correlation {corr:.2f}")
            if dd > 0.5 or abs(lag) > 0.05:
                raise SystemExit(f"the {k} stem does not belong to this mix (other song version?) - use the mix that the "
                                 f"stems were split from, or leave the stems out (Demucs separates the vocals)")
    d.mkdir(parents=True, exist_ok=True)
    cut(a.song, d / "song.wav", a.start, a.end)
    stems = {}
    for k in ("lead", "backing"):
        if getattr(a, k):
            (d / "stems").mkdir(exist_ok=True)
            cut(getattr(a, k), d / "stems" / f"{k}.wav", a.start, a.end)
            stems[k] = f"stems/{k}.wav"
    text = Path(a.lyrics).read_text(encoding="utf-8-sig")
    (d / "lyrics_source.txt").write_text(text, encoding="utf-8")
    if a.lyrics_from or a.lyrics_to:
        text = trim_lyrics(text, a.lyrics_from, a.lyrics_to)
    rows = [r.rstrip() for r in text.splitlines() if r.strip() and not re.match(r"^\s*\(", r)]
    (d / "lyrics.txt").write_text("\n".join(rows) + "\n", encoding="utf-8")
    pj = d / "project.json"
    p = json.loads(pj.read_text(encoding="utf-8")) if pj.exists() else {}
    p.update({
        "name": a.name or p.get("name") or d.name,
        "kind": "lyric-music-video",
        "fps": 30,
        "source": {"song": Path(a.song).name, "from": a.start or 0.0},
        "lyrics": "lyrics.txt",
        "stems": stems or p.get("stems", {}),
        "language": a.language,
        "video": "video",
    })
    p.setdefault("identity", "")
    p.setdefault("ideas", [])
    if a.seed is not None:
        p["seed"] = a.seed
    pj.write_text(json.dumps(p, ensure_ascii=False, indent=1), encoding="utf-8")
    creative.seed(Project(d))                                    # creates and stores a seed if missing
    copy_engine(d / "video")
    if not a.no_install:
        npm_install(d / "video")
    sung = sum(1 for r in rows if not r.lstrip().startswith("["))
    print(f"-> {d}: song {duration(d / 'song.wav'):.1f} s, {sung} sung lines, stems: {', '.join(stems) or 'none (Demucs)'}, "
          f"language {a.language}, seed {json.loads(pj.read_text(encoding='utf-8'))['seed']}")
    if a.start or a.end:
        print("   excerpt: times in the project start at 0 = --from")


if __name__ == "__main__":
    main()
