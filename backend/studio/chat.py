"""Chat with Claude Code about a project (no API key: uses the local `claude` CLI in print mode).

Each project keeps one Claude Code conversation (session id in chat/session.json), so follow-ups
like "make it darker" know what was discussed. The agent works inside the project folder and may
only read/edit files there (project.json, walls/*.js). After every reply the project file is
validated; if the agent broke it, the previous version is restored and the error is reported.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import threading
import time
import uuid

from . import store
from .config import CLAUDE_BIN, CLAUDE_MODEL, DOCS

_running: dict[str, dict] = {}
_lock = threading.Lock()

AGENT_GUIDE = """You are the scene assistant of a music-video studio. The user edits a lyric-synced three.js
concert video in a web app and talks to you in a chat (German or English – answer in the user's language,
short and concrete).

Your working directory is ONE project. The single source of truth is `project.json` (format: see
AGENT.md in this folder). The web app reloads it after your reply, so edit it directly with Edit/Write.

Rules:
- Change only what the user asks for. Keep ids of untouched scenes/lines/events stable.
- Keep valid JSON. Keep `scenes` in time order. Prefer anchors ({"kind":"auto"}, beat/bar, word) over
  absolute times so scenes follow the music and the voice.
- Measured data (`grid.detected`, word times, `hits`, `held`) only change when the user asks for timing
  fixes. To hide a line nobody sings, set "unsung": true instead of deleting it.
- New LED-wall visuals: prefer the built-in wall types with params. If none fits, write a JavaScript
  module in walls/<name>.js exporting a function (see AGENT.md "Custom walls") and reference it with
  {"type":"custom","module":"walls/<name>.js","fn":"<export>","params":{}}.
- The user's message may start with a context block (selected scene/line, playhead time). Use it.
- NEVER change anything outside this project folder: not the studio code (../../frontend, ../../backend,
  ../../legacy, ../../tools, ../../renderer), not other projects, not the original video folders. Those
  are central themes shared by everything. Every project has its OWN copy of its engine (legacy/src) –
  change that copy. If a wish can only be done centrally, say so instead of doing it.
- Imported engines (project.world == "legacy"): the look is code. Colours live in THREE places –
  legacy/src/style.css (CSS variables AND hard-coded values), legacy/src/scenes.ts (inline styles, SVG
  fills, rgb()/rgba()/hex in strings) and legacy/src/world3d.ts (THREE.Color / hex constants at the top and
  inside builders). A restyle must cover all three: grep for the old colours (e.g. "#e3001b", "#ffcc00",
  "227, 0, 27", "255, 204, 0") until none are left that should change.
- CHECK YOUR WORK before you answer (imported engines): build with
    node ../../tools/legacy-build.mjs .
  then render a few frames of the times you changed (seconds) with
    node ../../renderer/frames.mjs <project-id> frames/f 52 80 120
  and OPEN frames/f00.png, f01.png … with the Read tool and look at them. Describe colours/elements only
  from what you see in those images, not from what the code should do. Fix what does not look right.
  The user sees these frames next to your reply. Report only changes you actually made and saw.
- Finish with one or two sentences saying what you changed (scene names / times), no JSON dump.
"""


def _agent_md() -> str:
    fmt = (DOCS / "project-format.md").read_text(encoding="utf-8")
    walls = (DOCS / "walls.md").read_text(encoding="utf-8") if (DOCS / "walls.md").exists() else ""
    engine = (DOCS / "engine.md").read_text(encoding="utf-8") if (DOCS / "engine.md").exists() else ""
    return f"# Agent reference\n\n{fmt}\n\n{engine}\n\n{walls}\n"


def state(pid: str) -> dict:
    with _lock:
        return dict(_running.get(pid, {"status": "idle"}))


def history(pid: str) -> list[dict]:
    f = store.project_dir(pid) / "chat" / "messages.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else []


def _append(pid: str, msg: dict):
    d = store.project_dir(pid) / "chat"
    d.mkdir(exist_ok=True)
    msgs = history(pid)
    msgs.append(msg)
    (d / "messages.json").write_text(json.dumps(msgs, ensure_ascii=False, indent=1), encoding="utf-8")


def send(pid: str, text: str, context: str = "") -> bool:
    with _lock:
        if _running.get(pid, {}).get("status") == "running":
            return False
        _running[pid] = {"status": "running", "started": time.time()}
    _append(pid, {"role": "user", "text": text, "context": context, "t": time.time()})
    threading.Thread(target=_work, args=(pid, text, context), daemon=True).start()
    return True


def _work(pid: str, text: str, context: str):
    d = store.project_dir(pid)
    (d / "AGENT.md").write_text(_agent_md(), encoding="utf-8")
    before = (d / "project.json").read_text(encoding="utf-8")
    started = time.time()
    sess_f = d / "chat" / "session.json"
    sess = json.loads(sess_f.read_text()) if sess_f.exists() else {}
    prompt = (f"<context>\n{context}\n</context>\n\n" if context else "") + text
    args = [CLAUDE_BIN, "-p", prompt, "--output-format", "json", "--permission-mode", "acceptEdits", "--allowedTools", "Read,Edit,Write,Glob,Grep,Bash(node ../../tools/legacy-build.mjs:*),Bash(node ../../renderer/frames.mjs:*)", "--append-system-prompt", AGENT_GUIDE]
    if CLAUDE_MODEL:
        args += ["--model", CLAUDE_MODEL]
    if sess.get("id"):
        args += ["--resume", sess["id"]]
    else:
        sid = str(uuid.uuid4())
        args += ["--session-id", sid]
        sess = {"id": sid}
    reply, ok = "", True
    try:
        exe = shutil.which(CLAUDE_BIN) or CLAUDE_BIN
        p = subprocess.run([exe, *args[1:]], cwd=d, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=900)
        try:
            out = json.loads(p.stdout)
            reply = out.get("result", "") or p.stderr
            if out.get("session_id"):
                sess["id"] = out["session_id"]
            ok = not out.get("is_error", False)
        except json.JSONDecodeError:
            reply, ok = (p.stdout or p.stderr or "no output")[-2000:], False
    except Exception as e:  # noqa: BLE001
        reply, ok = f"Claude Code could not be started: {e}", False
    if "Not logged in" in reply or "/login" in reply:
        reply = ("Claude Code ist auf diesem PC nicht angemeldet. Bitte einmal ein Terminal öffnen, `claude` starten "
                 "und dort `/login` ausführen (dein Claude-Abo). Danach funktioniert der Assistent hier.")
        ok = False
    sess_f.parent.mkdir(exist_ok=True)
    sess_f.write_text(json.dumps(sess))
    # validate the project after the agent's edits
    after = (d / "project.json").read_text(encoding="utf-8")
    if after != before:
        try:
            data = json.loads(after)
            assert isinstance(data.get("scenes"), list) and isinstance(data.get("lyrics", {}).get("lines"), list)
            (d / "project.json").write_text(before, encoding="utf-8")  # put back, then save via store (history)
            store.save(pid, data)
        except Exception as e:  # noqa: BLE001
            (d / "project.json").write_text(before, encoding="utf-8")
            reply += f"\n\n(Änderung verworfen – project.json war danach ungültig: {e})"
            ok = False
    # imported engine: the agent may have changed the original scene code → rebuild the bundle
    code_changed = False
    try:
        from . import legacy

        if store.load(pid).get("world") == "legacy" and legacy.src_changed_since_build(pid):
            code_changed = True
            legacy.build(pid)
            reply += "\n\n(Original-Code neu gebaut.)"
    except Exception as e:  # noqa: BLE001
        reply += f"\n\n(Neubau des Original-Codes fehlgeschlagen – bitte nochmal beschreiben, was sich ändern soll:\n{str(e)[-600:]})"
        ok = False
    # frames the assistant rendered to check its work – shown with its reply, so the user sees the truth
    shots = sorted(str(f.relative_to(d)).replace("\\", "/") for f in (d / "frames").glob("*.png") if f.stat().st_mtime >= started - 1) if (d / "frames").exists() else []
    _append(pid, {"role": "assistant", "text": reply.strip(), "ok": ok, "changed": after != before or code_changed, "images": shots[:8], "t": time.time()})
    with _lock:
        _running[pid] = {"status": "idle", "last": time.time()}


def reset(pid: str):
    d = store.project_dir(pid) / "chat"
    for f in ("session.json", "messages.json"):
        (d / f).unlink(missing_ok=True)
