---
name: film-tools
description: "Quick finishing jobs on any existing video, no project needed: the standard film look (paper, grain, vignette), smaller versions for upload or e-mail (< 30 MB, ~12 MB), a contact sheet, a decode check, listening through a film / comparing two versions, cutting several clips/stills into one film with titles, transitions and music, or a title sting (black, one shot, a title card such as 'X will return') cut to a piece of music. Use for 'apply the look', 'make it smaller', 'check this video'."
---

# Film tools

Small finishing jobs on videos that already exist – from any source, not only from this plugin. For whole films
(music videos, shorts, slides …) use the matching user skill; it calls the same tools at its end.

How the commands run:
- `uv run` for scripts that need Python packages: each declares exact versions in its header (`dependencies = [...]`).
  `apply_look.py` needs none; `encode.py` needs numpy, `cut.py` / `sting.py` / `shaders_render.py` numpy + pillow (+ opentimelineio).
  On the very first run uv downloads missing packages once into its cache – ask the user before that first run if
  the cache may be empty; after that it works offline (`uv run --offline ...`).
- plain `python` for `media.py` and `check_tools.py`: they need no packages beyond the standard library.
- Setup: run `python "${CLAUDE_PLUGIN_ROOT}/skills/studio-core/scripts/check_tools.py" --setup` only when
  `~/.animation-studio/config.json` does not exist yet, or a script stops with "'ffmpeg' not found" – otherwise the
  setup has already run. `check_tools.py` without `--setup` only reports what is found.

## Recipes

| The user wants | Command | Result |
|---|---|---|
| the standard film look (paper + grain + vignette) | `uv run "${CLAUDE_PLUGIN_ROOT}/skills/film-finish/scripts/apply_look.py" in.mp4 -o in_look.mp4 [--strength 0.6] [--look <folder>]` | `in_look.mp4`, picture and sound otherwise unchanged |
| smaller versions (upload, e-mail) | `uv run "${CLAUDE_PLUGIN_ROOT}/skills/film-finish/scripts/encode.py" in.mp4 [--small] [--mail] [--mb 20 --suffix _web --side 1280]` | `in_small.mp4` (< 29 MB, long side ≤ 1280), `in_mail.mp4` (~12 MB, ≤ 960); aspect kept (phone clips stay upright), never upscaled, never bigger than the input (copied when already under both limits), "OVER the N MB target" if a very long video cannot fit |
| a contact sheet (3x3 frames) | `python "${CLAUDE_PLUGIN_ROOT}/skills/studio-core/scripts/media.py" sheet in.mp4 sheet.png` | open the PNG with the Read tool and describe what you see; the command prints which frame / second each tile is |
| one frame at full size | `python "${CLAUDE_PLUGIN_ROOT}/skills/studio-core/scripts/media.py" frame in.mp4 2.5 f.png` | the frame at 2.5 s (number printed); open it with Read |
| every frame of a short stretch (a gesture, a cut, lip sync) | `python "${CLAUDE_PLUGIN_ROOT}/skills/studio-core/scripts/media.py" sheet in.mp4 strip.png --from 2.4 --to 3.4 --cols 6 --rows 4 --width 320` | 24 consecutive frames at 24 fps; the printed list names each tile's frame and second |
| listen through a film (you cannot hear: earshot does) | `python "${CLAUDE_PLUGIN_ROOT}/skills/studio-core/scripts/ear.py" timeline in.mp4` (events, sections, loudness, silences, picture cuts) and `ear.py sheet in.mp4 -o in_ear.png` (frames + spectrogram + events in one PNG, open it) | say what it heard – a machine's ear, not a listener. `ear.py` finds earshot (optional program; exit 2 when it is not set up) and puts the configured ffmpeg on PATH. A sheet with "0 frames" from an earlier run without ffmpeg: ear.py notices it and refreshes earshot's cached result itself |
| what is said / sung, with times (you cannot hear) | `"<gpu_python>" "${CLAUDE_PLUGIN_ROOT}/skills/song-analysis/scripts/track_read.py" in.mp4 --lang de` – `<gpu_python>` = the CUDA python from `check_tools.py` (key `gpu_python`); without it see song-analysis BLOCK.md (`uv run --with faster-whisper ...`, downloads packages and the Whisper model on first use: ask first) | `in_sheet.json` / `.csv` / `.png` NEXT TO the input (to keep a folder untouched, run it on a copy elsewhere): every word with second and frame, beats, accents; compare with the script. Word times are rough (±0.3 s) - for exact timing use `ear.py timeline` / a frame strip |
| compare two versions (A/B) | `python "${CLAUDE_PLUGIN_ROOT}/skills/studio-core/scripts/media.py" compare a.mp4 b.mp4` (size, length, MB, PSNR / SSIM, sound identical?) + `media.py sheet` of both; a different sound: `ear.py ab a.mp4 b.mp4` | which one for what (upload, mail, archive) and why |
| a decode check | `python "${CLAUDE_PLUGIN_ROOT}/skills/studio-core/scripts/media.py" check in.mp4 [...]` | size (e.g. 1920x1080, as displayed), length and "0 decode errors" per file, exit code 1 otherwise – no ffprobe needed |
| several clips / stills / title cards into one film, with dissolves, music, title | write a `cut.json` (shot list) and run `uv run "${CLAUDE_PLUGIN_ROOT}/skills/film-finish/scripts/cut.py" cut.json` | `film.mp4` + small / mail versions, sheet, `.otio` for Kdenlive – the format is in film-finish BLOCK.md (`cut.py` row) |
| a title sting: black, one shot, a title card ("X WILL RETURN"), cut to a piece of music | first `uv run "${CLAUDE_PLUGIN_ROOT}/skills/film-finish/scripts/sting.py" analyse track.mp3` (hit, drop, tail, end + suggested times), then `uv run "${CLAUDE_PLUGIN_ROOT}/skills/film-finish/scripts/sting.py" build shot.mp4 --title "X WILL RETURN" --audio track.mp3 --shot-at 7.5 --black-at 16.0 --title-at 17.3 --end 24.3 [--clip-start 0.3] [--note "picture and video AI-generated"]` | `shot_sting.mp4`: the shot appears out of black (light sweeps in from the left), hard cut to black on the drop, title card over the tail; without `--audio` a silent film. Say that nobody listened; the track is the user's file (see the reference-video guide below) |
| a new look (other paper, softer grain …) | `uv run "${CLAUDE_PLUGIN_ROOT}/skills/film-finish/scripts/shaders_render.py" look --preset my_look.json --out <folder>`, then `apply_look.py in.mp4 --look <folder>` | needs node + a headless Chrome/Edge; see film-finish BLOCK.md and its `references/shaders.md` |

Working from a reference video ("same look and feel as this one"): read
`${CLAUDE_PLUGIN_ROOT}/skills/studio-core/references/reference-video.md` first - frames by seeking, the sound
track before the first render, what may be taken.

Always check the result: decode check, a contact sheet looked at, the file size. Say what was not checked (e.g.
nobody listened to the sound).

**Building blocks** (shared code + docs of this plugin, not skills - read the one you need):
`${CLAUDE_PLUGIN_ROOT}/skills/<block>/BLOCK.md` for `studio-core`, `song-analysis`, `toon-2d`, `characters`, `voice`, `ai-video`, `bricks-3d`, `stage-3d`, `film-finish`. In those files
`<plugin>` stands for `${CLAUDE_PLUGIN_ROOT}`. First use on a machine: `python "${CLAUDE_PLUGIN_ROOT}/skills/studio-core/scripts/check_tools.py" --setup` (finds the programs).

## Rules

- Never overwrite the input; write next to it with a suffix.
- An existing output IS overwritten without asking (`apply_look.py -o`, `encode.py`'s `_small` / `_mail` / own
  suffix; a file locked by a player gets a time-stamped name instead). If that name already exists and may matter,
  pick a new one (`-o in_look_v2.mp4`, `--suffix _web2`) or ask.
- Label AI-made content when the video contains any (see the user skill that made it).
- Nothing is installed or downloaded without asking the user.
