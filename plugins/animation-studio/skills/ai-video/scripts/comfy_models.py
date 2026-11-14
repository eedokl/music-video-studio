"""Model files and node classes of the ai-video ComfyUI workflows: ONE data file, `assets/models.json`, plus an optional
per-machine override.

    import comfy_models
    comfy_models.file("ltx23")            # -> "ltx-2.3-22b-distilled-fp8.safetensors" (or the machine's own name)
    comfy_models.workflow("ltx23")        # -> {"nodes": [...], "files": ["ltx23", "gemma3_te"], "values": {...}}

models.json:
  files      role -> {"file": name as ComfyUI lists it, "folder": models/ sub-folder, "loaders": ["Class.input", ...],
             "what": description}
  workflows  builder variant -> {"used_by", "nodes": [class_type ...], "files": [role ...], "values": {"Class.input": v}}
  nodes      class_type -> python module on the reference ComfyUI ("nodes" / "comfy_extras.*" = core ComfyUI)
The workflow builders (comfy_image, comfy_video, ltx, s2v, infinitetalk, humo, minimax, qwen_edit, mic_repair) take
every model file name from here; preflight.py checks a running ComfyUI against the same entries.

Another machine with other file names (or files in sub-folders): leave models.json alone and point the machine config
key `comfy_models` (studio-core config.py; env ANIMATION_STUDIO_COMFY_MODELS) at a JSON file of the same layout with
only the entries that differ - merged key by key; a plain string for a file role is its file name:
    {"files": {"ltx23": "video/ltx-2.3-22b-distilled-fp8.safetensors", "umt5_xxl": {"file": "umt5-xxl-enc-fp8.safetensors"}}}
Standard library only.
"""
import json
from pathlib import Path

import _studio  # noqa: E402
_studio.use()
import config  # noqa: E402

ASSET = Path(__file__).resolve().parents[1] / "assets" / "models.json"
CONFIG_KEY = "comfy_models"
_cache = None


def override_path():
    """The machine's override file (config key comfy_models) or None."""
    v = config.get(CONFIG_KEY)
    return Path(v).expanduser() if v else None


def _merge(base, over, where):
    for sec in ("files", "workflows", "nodes"):
        add = over.get(sec)
        if add is None:
            continue
        if not isinstance(add, dict):
            raise SystemExit(f"{where}: '{sec}' must be an object")
        for k, v in add.items():
            if sec == "files" and isinstance(v, str):
                v = {"file": v}
            if isinstance(v, dict) and isinstance(base[sec].get(k), dict):
                base[sec][k] = {**base[sec][k], **v}
            else:
                base[sec][k] = v
    return base


def load(refresh=False):
    """models.json merged with the machine override (cached per process)."""
    global _cache
    if _cache is not None and not refresh:
        return _cache
    d = json.loads(ASSET.read_text(encoding="utf-8"))
    p = override_path()
    if p is not None:
        try:
            over = json.loads(p.read_text(encoding="utf-8"))
        except FileNotFoundError:
            raise SystemExit(f"config {CONFIG_KEY} points to {p}, which does not exist - fix it with "
                             f"`check_tools.py --set {CONFIG_KEY}=<file>` or remove the key") from None
        except json.JSONDecodeError as ex:
            raise SystemExit(f"config {CONFIG_KEY}: {p} is not valid JSON ({ex})") from None
        _merge(d, over, str(p))
        d["override"] = str(p)
    _cache = d
    return d


def file(role):
    """File name of a model role, as the loader node expects it."""
    f = load()["files"].get(role)
    if not f or not f.get("file"):
        raise KeyError(f"model role '{role}' is not in {ASSET.name} (nor in the {CONFIG_KEY} override)")
    return f["file"]


def workflow(name):
    w = load()["workflows"].get(name)
    if w is None:
        raise KeyError(f"workflow '{name}' is not in {ASSET.name}")
    return w
