# Music Video Studio

Lyric-synced three.js music videos with a live preview instead of waiting for MP4 renders.

1. **New project**: song (WAV/MP3), lyrics, storyline, optional Suno stems (ZIP or WAVs).
2. **Analysis** (5–15 min, runs in the background): lead vocal (Suno stem or Demucs), Whisper word
   timestamps, alignment with the lyrics, word starts snapped to the voice, beat grid (fixed tempo or
   following tempo changes) with downbeats, riff hits, held notes, lines nobody sings → a first
   storyboard without AI.
3. **Editor**: live 3D preview (concert world), timeline (scenes, lines, words, vocal + mix waveform,
   effects), inspector, undo/redo, autosave. Fix timing by dragging words, tap-sync (T), nudging
   (, / .), move scene cuts (snap to bars), mark lines as not sung.
4. **Assistant**: chat with Claude Code about the selected scene ("replace this scene with …").
   It edits `project.json` / custom wall modules, the preview reloads.
5. **Export**: "Szene als MP4" (quick check of one scene) or the full video (+ `_small` <30 MB and
   `_mail` ≈12 MB). Preview and export run the same code.

## Worlds: concert or the original look of an existing video

Each project has a **world** – how the preview and the export look:

- `concert` – the stadium concert (LED wall story, band, crowd, lights) – default for new projects.
- `legacy` – an **imported video engine**: a video built earlier with its own code (Comfort Zone v3.2,
  Roles, Azure, …) keeps its ORIGINAL scenes and look. Timing, unsung lines, scene order/cuts and text
  come from the studio, so the timeline, scene list, inspector, assistant and export work the same.
  The assistant can change what a scene shows by editing the original code (`legacy/src/scenes.ts`);
  the bundle is rebuilt automatically.

Import an existing video (the studio project must exist and be analysed first – song + lyrics as sung):

```bash
uv run python -m studio.legacy import <project-id> <path-to-old-video-project>
```

## Start

Requirements: Python with [uv](https://docs.astral.sh/uv/), Node 20+, Claude Code (`claude`, logged in
once with `/login`), and for the export the Chrome headless shell:

```bash
npx @puppeteer/browsers install chrome-headless-shell@stable --path %TEMP%/mvchrome
```

```bash
start-studio.cmd
```

opens http://localhost:8000 (builds the frontend if needed, then runs the backend).

Development: `uv run studio` (API on :8000) and `npm --prefix frontend run dev`
(UI with hot reload on :5180).

## Docker

Everything runs in one container (the backend serves the built UI, so one pod with one container is
enough in Kubernetes too):

```bash
docker compose up --build
```

→ http://localhost:8000. Your `projects/` folder is mounted into the container. The folder above this one
is mounted read-only at `/videos`, for "Import existing": enter `/videos/<folder>` there. Change it with
`VIDEOS_DIR`. The assistant needs a one-time login inside the container:

```bash
docker compose exec studio claude
```

then `/login`. The login and the downloaded Whisper/Demucs models are kept in the `studio-data`
volume. Without a GPU in the container, the 3D preview renders in software (SwiftShader), so MP4
exports are slower than on the desktop. Don't run the container and `start-studio.cmd` at the same
time on the same `projects/` folder.

## Checks

```bash
uv run ruff check src tests
```

```bash
uv run ruff format src tests
```

```bash
uv run pytest
```

## Layout

- `pyproject.toml` – the Python package `studio` (src layout), ruff and pytest settings
- `src/studio/` – FastAPI app: projects, pipeline jobs, chat (Claude Code CLI), export
- `src/studio/scripts/` – analysis scripts run by the pipeline with uv (transcribe, align, refine, beats, hits, held, separate)
- `tests/` – unit tests (pytest), run against a temporary projects folder
- `frontend/src/engine/` – preview: timing model, concert world, LED wall visuals, lyrics
- `frontend/src/editor/` – editor UI: timeline, inspector, chat
- `renderer/` – headless MP4 renderer (puppeteer + ffmpeg)
- `projects/<id>/` – one folder per video: `project.json`, audio, analysis, `walls/*.js`, `out/*.mp4`
- `docs/` – project format, engine and LED wall reference (also read by the assistant)
