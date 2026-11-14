# animation-studio – conventions for every skill in this plugin

Read this before adding or changing a skill. It keeps the plugin free of duplicates and portable.

## Layout

```
animation-studio/
  .claude-plugin/plugin.json
  README.md            what the plugin does, the skills, how to install
  TOOLS.md             external programs and AI models: used / recommended / optional
  CONVENTIONS.md       this file
  skills/<skill>/SKILL.md, scripts/, references/, assets/
```

Two kinds of skills:
- **User skills** (one per kind of video the user asks for): thin. Interview → creative brief → build →
  review checkpoints. Their SKILL.md is what the user sees; frontmatter `name` + a "pushy" `description`.
- **Building blocks** (studio-core, song-analysis, toon-2d, film-finish, characters, voice, ai-video, bricks-3d):
  scripts + knowledge used by several user skills, written once. Frontmatter `user-invocable: false`, description
  starts with "Building block of the animation-studio plugin: ...".
Anything two user skills need goes into a building block – never copy code between skills.

## Language and paths

- English everywhere: SKILL.md, references, script names, code, comments, CLI help, printed messages, JSON keys.
  Examples (lyrics, gag texts, German songs) may stay German.
- No absolute paths and nothing outside the plugin in any file. Scripts find sibling skills with the per-skill
  helper `scripts/_studio.py`:  `import _studio; _studio.use("song-analysis", "toon-2d")` (studio-core is always
  added) and `_studio.skill_dir("toon-2d")` for assets.
- External programs and machine paths only through `studio-core/scripts/config.py`: `config.need("synfig")`,
  `config.get("earshot")`. They come from environment variables or the machine config
  `~/.animation-studio/config.json` written by `check_tools.py --setup` / `--set key=value`.
- In SKILL.md, call scripts as `python "${CLAUDE_PLUGIN_ROOT}/skills/<skill>/scripts/x.py"` (substituted by Claude
  Code when the skill loads). Run them with `uv run --no-project --with <pkgs> python ...`.

## Shared machinery

- GPU: any AI model run takes the shared lock first: `from gpu_lock import acquire; acquire("job", model="...")`.
  It waits for other jobs and flushes ComfyUI on a model change. Never delete another job's lock.
- Song projects: `song-analysis/scripts/song_project.py` (`Project`): `project.json`, `song.wav`, `lyrics.txt`,
  `stems/`, `analysis/`, `cache/`. Times are always song seconds.
- Picture: each section renders to `scenes/<section>/f.%04d.png` (any renderer); `film-finish/scripts/build.py`
  assembles preview and film (film.mp4, film_small.mp4 < 30 MB, film_mail.mp4 ~12 MB), applies the look once and
  checks every file (0 decode errors).
- Media helpers: `studio-core/scripts/media.py` (decode, duration, voice activity, check_video, contact_sheet).

## Creative seed (keep films fresh)

Every project has `"seed"` and `"ideas"` (see `studio-core/scripts/creative.py`).
- Variation comes from `creative.rng(P, salt)` / `creative.pick(...)` – same seed, same film; new seed, new take.
- Every user skill has a **creative brief** step: before building, invent ideas that come from *this* song or
  topic (a concrete image per lyric idea, props, gags, an ending) and record them with `creative.add_idea`. User
  ideas are recorded with `by: "user"` and always win. Reference projects show techniques, never a template to copy.
- Defaults are a starting point, not the film: a skill that produces the same routine for every song is broken.

## Tests

- Each user skill has `references/reference-tests.md`: which earlier project is its reference, how to rebuild a
  part of it with the skill, what was compared (measurements + contact sheets) and the result.
- Run tests in a scratch folder outside the plugin; never modify the reference projects.
