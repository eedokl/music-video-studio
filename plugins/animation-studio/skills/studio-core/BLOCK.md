<!-- Building block of the animation-studio plugin - a reference document, NOT a skill (it is not loaded
     into every session). User skills point here. `<plugin>` = the plugin folder, the path that
     the variable CLAUDE_PLUGIN_ROOT stands for in the SKILL.md files. -->
# studio-core

*Machine setup and shared machinery for every video skill: finding external programs (check_tools.py, machine config), the shared GPU lock (one AI model at a time), video encoding presets, media helpers (decode, durations, voice activity, decode check, contact sheets) and the creative seed with the ideas log. Use it when setting up a machine for the plugin, when a tool is missing, or when another skill of the plugin refers to it.*

**Run a script of this block:** `uv run "<plugin>/skills/studio-core/scripts/<script>.py" ...` - the script names in the tables below live in `<plugin>/skills/studio-core/scripts/`; each script declares its own packages (PEP 723), so no `--with`. A script whose first line says it runs in another interpreter (Blender, gpu_python, tts_python) is started by the scripts that need it.

## Machine setup (once per machine)

`python "<plugin>/skills/studio-core/scripts/check_tools.py" --setup` searches PATH and the usual install
folders on every drive and stores what it finds in `~/.animation-studio/config.json` (outside the plugin, survives
updates; override the file with `ANIMATION_STUDIO_CONFIG`). Without arguments it reports found / missing / optional
with install hints; exit code 1 means something required is missing. Paths can be set by hand:
`check_tools.py --set gpu_lock_dir=D:/tools hf_home=D:/hf-cache earshot=D:/tools/earshot.cmd` (unknown keys are
refused). Environment overrides: `ANIMATION_STUDIO_<KEY>` (e.g. `ANIMATION_STUDIO_BROWSER`); the plain name only
for unambiguous keys (`FFMPEG`, `SYNFIG`, `HF_HOME`, ... - see `config.py`), never `BROWSER`, `NODE`, `BLENDER`.

**Never install anything without asking.** Show the user the missing lines, say what each tool is needed for, and
ask; when they agree, install to the drive they keep tools on and store the path with `--set`. A missing optional
tool is reported in one line ("without earshot there is no male/female detection and no sound effects") and the
work goes on. The full list of tools and models is in the plugin's `TOOLS.md`.

## Modules (import with `import _studio; _studio.use()` first)

| Module | Use |
|---|---|
| `config.py` | `config.need("synfig")` (stops with a clear message if missing), `config.get("earshot")`, `config.setup_env()` (model caches, ffmpeg on PATH), `config.lock_dir()`, `config.comfy_url()` |
| `gpu_lock.py` | `acquire("job", model="comfy:ltx23")` before any AI model run: waits while another job holds the lock, flushes ComfyUI when the model changes; `python gpu_lock.py` shows who holds it. Never delete another job's lock. |
| `encoding.py` | `h264()` ffmpeg options: x264 CRF 18 for anything shown or handed over; with `PREVIEW=1` NVENC for fast work-in-progress files (probed once; x264 veryfast where there is no NVENC) |
| `media.py` | `decode`, `duration`, `has_audio`, `voice_activity`, `check_video` ("" = 0 decode errors), `contact_sheet` (`python media.py sheet film.mp4 sheet.png`, prints frame/second per tile), `compare` (`python media.py compare a.mp4 b.mp4`: size, length, PSNR/SSIM, sound identical?), CLI `check <video>...` |
| `ear.py` | earshot with the configured launcher, no path lookup, no cmd AutoRun noise: `python ear.py timeline film.mp4`, `ear.py sheet film.mp4 -o x.png`, `ear.py ab a b` (exit 2 without earshot) |
| `frames.py` | contact sheet at given times, labelled side-by-side comparison of two videos, SSIM score – for reference tests and reviews |
| `sfx_mix.py` | `SfxMix(seconds, cache)` – the ONE sound-effect mixer (earshot bank): `sfx(t, id, args, db, pan, align="peak"|"start")`, `voice(path, t, db, pan)`, `write(wav, lowpass=, loudnorm=)`; soft 10 ms fades, pan law linear/equal, shared bank via config key `sfx_cache`. Used by film-finish `sounds.py`, animated-short `sfx_track.py`, animated-powerpoint `sound.py` |
| `derived.py` | every cache / derived file or folder: `derived.fresh(target, inputs=[files], spec={...})` and `with derived.build(target, inputs, spec) as b: write(b.path)` – content hashes (not mtimes), record in `<parent>/.derived/` without absolute paths, written only after the build succeeded (temp + rename, an interrupted build never looks fresh), `recorded(target)["extra"]` for build metadata, `commit()` for batch builders; `Ledger(store, name)` = hashes of the files a pass wrote (tells own outputs from a re-render) |
| `project_check.py` | `require(P, skill="...")` validates project.json / short.json / clip.json / scene.json before any long step (exit code 2 on errors, warnings printed; CLI: `project_check.py <project> [--skill ...]`); `frame_size(p)` = `"size"` or 1280x720, `frame_scale(p)` = h / 720. Schema = plain data `SCHEMAS`: add every new project key there |
| `creative.py` | `seed(P)`, `rng(P, salt)`, `pick(P, salt, options)`, `add_idea(P, by, idea, where)`, `ideas(P)` – reproducible variation and the ideas log every film is built on |

## Rules shared by all skills

- One AI model on the GPU at a time (on the reference machine 16 GB VRAM and 16 GB RAM do not hold two big models; see TOOLS.md "Tuned for the reference machine").
- Only one session builds a project's final film files; verify every output with `check_video`.
- Look at your own renders (contact sheets) before showing them to the user.
