# CLAUDE.md – Music Video Studio

> **Scene assistant inside the studio** (your working directory is `projects/<id>/`): this file is NOT
> for you. Follow your system prompt and `AGENT.md` in the project folder. Change files only inside
> that project folder – never the studio code described below.

This file is for working on the studio itself: a web tool for lyric-synced three.js music videos.
It has a FastAPI backend, a React + three.js preview/editor, an analysis pipeline (Demucs, Whisper),
a headless MP4 renderer and a chat assistant via the local `claude` CLI. The user speaks German or
English; UI texts are mostly German.

## Commands

```bash
uv sync                                # Python env (always uv – never pip)
uv run studio                          # backend + built UI on http://localhost:8000
npm --prefix frontend run dev          # UI with hot reload on :5180 (proxies /api to :8000)
npm --prefix frontend run build        # tsc check + vite build → frontend/dist (served by the backend)
uv run ruff check src tests            # lint
uv run ruff format src tests           # format
uv run pytest                          # unit tests (temporary projects folder, never touches projects/)
node tools/legacy-build.mjs projects/<id>                       # rebuild an imported video engine
node renderer/frames.mjs <id> <outPrefix> 52 80 120             # render check frames (needs backend)
docker compose up --build              # everything in one container
```

On Windows, start the desktop version with `start-studio.cmd`.

## Layout

- `src/studio/` – Python package (src layout, `pyproject.toml` at the root)
  - `main.py` – FastAPI app: projects, files, analysis, update audio, duplicate, import, chat, export
  - `pipeline.py` – analysis steps (prepare → separate → transcribe → align → refine → beats → hits →
    voice → assemble → engine), each runs a script from `scripts/` with `uv run --with …` as a subprocess
  - `scripts/` – standalone analysis scripts (own dependencies via uv, not imported by the app)
  - `legacy.py` – imported video engines: build, scene read-out, `word_map` (original line → studio words)
  - `update.py` – "Audio aktualisieren": match lines of a changed song, carry the storyboard over
  - `export.py` – MP4 export variants, `.partial.mp4` temp files, cancel; `chat.py` – Claude Code assistant
  - `store.py` – `project.json` load/save with `.history/`; `config.py` – paths and `STUDIO_*` env vars
- `frontend/src/engine/` – preview (timing model, concert world, `legacyPlayer.ts` for imported engines)
- `frontend/src/editor/` – editor UI (timeline, inspector, scene list, chat, exports)
- `legacy/adapter/` – shims that plug an imported engine into the studio (lyrics, timing, `studio_main.ts`)
- `renderer/` – puppeteer + ffmpeg; `chrome.mjs` finds Chrome and sets GPU flags (Windows D3D, Linux SwiftShader)
- `tools/legacy-build.mjs` – esbuild bundle of `projects/<id>/legacy/src` → `legacy/app.js` + `app.css`
- `docs/` – project format, engine, LED walls. The scene assistant reads these too, so keep them current.
- `projects/<id>/` – one video each: `project.json`, audio, analysis, `legacy/src` (engine copy), `out/*.mp4`

## Core rules

- **`project.json` is the single source of truth.** The preview and the export read the same file with
  the same code. Timing uses anchors (`auto`, `beat`, `bar`, `word`, `time`); see `docs/project-format.md`.
- **Never change a central theme for one video.** The look of a single project lives in its own copy
  `projects/<id>/legacy/src`. A different look means a new project or a change in that copy –
  never `legacy/adapter`, `frontend/src/engine` or the original video folders outside this repo.
- **Measured data stays measured**: word times, `grid.detected`, `hits`, `held` only change for timing fixes.
- **Imported engines map lines at word level**: `legacy.lineMap` entries are `"l12"`, `{id, from, to}`
  or `null`, computed by `word_map` from `legacy.origLines`. The server recomputes them on every PUT
  and on audio updates.

## Working on a running studio

- **Before restarting the backend, check every project's `/api/projects/<id>/status`** (analysis job,
  export, chat). Restart only when all are idle. A restart kills running exports and analyses.
- Browsers cache old engine bundles: `files/legacy/index.html` is served with `app.js?v=<mtime>` and
  everything code-like with `no-store`. Keep that when touching the files endpoint.
- Check visual changes with real frames (`renderer/frames.mjs`) and look at them before claiming a change.

## Code conventions

- No `# noqa`, `# type: ignore` or `# pragma: no cover` without asking the user first.
- Ruff settings live in `pyproject.toml` (line length 160; `–`, `×`, `−` are allowed characters).
- New logic in `src/studio` gets a unit test in `tests/` (the `projects` fixture gives an empty
  projects folder; `make_line()` builds lyric lines with word times).
- esbuild and three are runtime dependencies of `frontend/` (used by `legacy-build.mjs`), not only build tools.
- The analysis scripts run on Windows and Linux: use `pathlib`, UTF-8, and no shell-specific commands.

## Docker

The Dockerfile is multistage: stage 1 builds the UI, and the final image has only runtime packages,
`chrome-headless-shell`, uv and the Claude Code CLI. `compose.yaml` mounts `./projects` and the old
video folders (read-only at `/videos`), and a `studio-data` volume holds the Claude login, the uv cache
and models. Don't run the container and the desktop studio on the same `projects/` at the same time.
