# Music Video Studio in one container: the FastAPI backend serves the built UI, runs the analysis
# pipeline (uv), the MP4 renderer (node + headless Chrome) and the assistant (Claude Code CLI).
#
#   docker compose up --build        → http://localhost:8000
#   docker compose exec studio claude   (once: /login, so the assistant works)

# ---------------------------------------------------------------- stage 1: build the UI
FROM node:22-bookworm-slim AS frontend
WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ---------------------------------------------------------------- stage 2: the studio
FROM node:22-bookworm-slim

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates git unzip fonts-liberation fonts-noto-color-emoji \
 && rm -rf /var/lib/apt/lists/*

# uv + the Python versions the studio uses (3.12 for the app, 3.11 for the Demucs step)
COPY --from=ghcr.io/astral-sh/uv:0.11.7 /uv /uvx /usr/local/bin/
ENV UV_PYTHON_INSTALL_DIR=/opt/uv-python \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1
RUN uv python install 3.12 3.11

# Claude Code CLI for the assistant chat
RUN npm install -g @anthropic-ai/claude-code

WORKDIR /app
RUN mkdir -p /data && chown node:node /app /data

# JS runtime dependencies only: renderer (puppeteer, ffmpeg) and, for rebuilding imported video
# engines, esbuild + three from the frontend (no vite/TypeScript here – the UI comes from stage 1)
COPY --chown=node:node frontend/package.json frontend/package-lock.json frontend/
COPY --chown=node:node renderer/package.json renderer/package-lock.json renderer/
USER node
RUN npm ci --omit=dev --prefix frontend && npm ci --omit=dev --prefix renderer

# Chrome headless shell for export/frames + its system libraries (needs root for apt)
USER root
RUN cd renderer && npx browsers install chrome-headless-shell@stable --path /opt/chrome --install-deps \
 && ln -s "$(find /opt/chrome -type f -name chrome-headless-shell)" /usr/local/bin/chrome-headless-shell \
 && rm -rf /var/lib/apt/lists/*
USER node

# Python dependencies first (cached layer), then the code and the built UI
COPY --chown=node:node pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project --python 3.12
COPY --chown=node:node . .
COPY --chown=node:node --from=frontend /build/frontend/dist frontend/dist
RUN uv sync --frozen --no-dev --python 3.12

ENV STUDIO_ROOT=/app \
    STUDIO_HOST=0.0.0.0 \
    STUDIO_PORT=8000 \
    STUDIO_CHROME=/usr/local/bin/chrome-headless-shell \
    STUDIO_TORCH_INDEX=https://download.pytorch.org/whl/cpu \
    CLAUDE_CONFIG_DIR=/data/claude \
    UV_CACHE_DIR=/data/uv-cache \
    HF_HOME=/data/huggingface \
    TORCH_HOME=/data/torch \
    PATH=/app/.venv/bin:$PATH

EXPOSE 8000
CMD ["studio"]
