# Runs in the configured gpu_python (CUDA venv); without it run() falls back to `uv run --with ...` on the CPU - no PEP 723 header.
"""Near masks for the code cut (film-finish code_cut.py): where is "near" in every frame of a take, so that dust and overlays with "behind": true
pass behind people (code_cut/draw.js cuts them out with the mask).

Usage (needs torch + transformers: the configured gpu_python; `--kind matte` needs onnxruntime instead):
  <gpu_python> near_masks.py <work> [--takes t1,t2] [--kind depth|matte] [--near 0.26 0.38] [--width 640]
  From Python (any interpreter):  _studio.use("ai-video"); import near_masks; near_masks.run(work, takes=[...])
Result: <work>/masks/<take>/0001.png ... (white, alpha = near; same numbering as frames/<take>) and
clips.json[take]["masks"] = true. Without --takes: every take that needs one (its world or the edit has "dust", or an
overlay with "behind": true lies on one of its parts).

--kind depth (default): Depth Anything V2 Small, every frame normalised by itself, alpha rises from --near A to B
  (0..1 of the frame's depth range). Fast (a film in about a minute on a GPU), soft edges: right for dust, haze, glow.
  Furniture in front of the person counts as near too. Takes the GPU lock.
--kind matte: a salient-object matting model as ONNX (config key `matte_model` or --matte-model, e.g. BRIA RMBG-1.4,
  check its licence) on the CPU, about 8 s per frame: clean edges for single shots where cards or notes fly behind
  a person. Keep it to the shots that need it.
"""
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

import _studio  # noqa: E402
_studio.use()
import config  # noqa: E402

HERE = Path(__file__).resolve()


def run(work, takes=None, kind="depth", near=(0.26, 0.38)):
    """Run this script in the configured GPU python (falls back to uv on the CPU)."""
    py = config.get("gpu_python")
    cmd = ([py] if py and Path(py).exists() else
           ["uv", "run", "--no-project", "--with", "transformers", "--with", "torch", "--with", "pillow", "--with", "numpy",
            "--with", "onnxruntime", "python"])
    cmd += [str(HERE), str(work), "--kind", kind, "--near", str(near[0]), str(near[1])]
    if takes:
        cmd += ["--takes", ",".join(takes)]
    subprocess.run(cmd, check=True)


def needed(edit):
    """Takes that carry dust or an overlay with "behind": true."""
    out = []
    behind = [o for o in edit.get("overlays", []) if o.get("behind")]
    for s in edit["shots"]:
        dust = (edit.get("worlds", {}).get(s.get("world"), {}) or {}).get("dust", edit.get("dust"))
        for p in s["parts"]:
            if p["kind"] == "take" and p["src"] not in out and (
                    dust or any(o["k0"] < p["k1"] and o["k1"] > p["k0"] for o in behind)):
                out.append(p["src"])
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("work")
    ap.add_argument("--takes", help="comma separated take names (default: every take with dust or a 'behind' overlay)")
    ap.add_argument("--kind", default="depth", choices=["depth", "matte"])
    ap.add_argument("--near", type=float, nargs=2, default=[0.26, 0.38], metavar=("A", "B"),
                    help="depth: alpha rises from A to B of the frame's depth range (default 0.26 0.38)")
    ap.add_argument("--width", type=int, default=640, help="mask width in pixels (default 640)")
    ap.add_argument("--matte-model", help="ONNX matting model for --kind matte (default: config key matte_model)")
    a = ap.parse_args()
    work = Path(a.work)
    edit = json.loads((work / "edit.json").read_text(encoding="utf-8"))
    clips_file = work / "clips.json"
    clips = json.loads(clips_file.read_text(encoding="utf-8"))
    takes = a.takes.split(",") if a.takes else needed(edit)
    if not takes:
        print('no take needs a mask (no "dust", no overlay with "behind": true)')
        return 0
    import numpy as np
    from PIL import Image

    if a.kind == "depth":
        config.setup_env()                              # hf_home -> HF_HOME before transformers is imported
        from gpu_lock import acquire
        acquire("near_masks", model="depth:small")
        import torch
        from transformers import pipeline
        dev = 0 if torch.cuda.is_available() else "cpu"
        pipe = pipeline("depth-estimation", model="depth-anything/Depth-Anything-V2-Small-hf", device=dev,
                        torch_dtype=torch.float16 if dev == 0 else None)

        def alpha(img):
            d = np.asarray(pipe(img)["predicted_depth"].squeeze().float().cpu().numpy(), dtype=np.float32)   # large = near
            d = (d - d.min()) / (d.max() - d.min() + 1e-6)
            return np.clip((d - a.near[0]) / max(a.near[1] - a.near[0], 1e-3), 0, 1)
    else:
        model = a.matte_model or config.get("matte_model")
        if not model or not Path(model).exists():
            raise SystemExit("--kind matte needs an ONNX matting model: --matte-model PATH or the config key matte_model")
        import onnxruntime as ort
        ort.set_default_logger_severity(3)
        sess = ort.InferenceSession(str(model), providers=["CPUExecutionProvider"])
        inp = sess.get_inputs()[0].name

        def alpha(img):
            x = (np.asarray(img.resize((1024, 1024), Image.BICUBIC), np.float32) / 255 - 0.5).transpose(2, 0, 1)[None]
            y = sess.run(None, {inp: x})[0][0, 0]
            return (y - y.min()) / max(float(y.max() - y.min()), 1e-6)

    for take in takes:
        src = work / "frames" / take
        files = sorted(src.glob("*.jpg"))
        if not files:
            raise SystemExit(f"frames/{take} has no frames")
        dst = work / "masks" / take
        dst.mkdir(parents=True, exist_ok=True)
        t0 = time.time()
        for f in files:
            img = Image.open(f).convert("RGB")
            h = round(a.width * img.height / img.width)
            al = Image.fromarray((alpha(img) * 255).astype(np.uint8)).resize((a.width, h), Image.BILINEAR)
            m = Image.new("RGBA", (a.width, h), (255, 255, 255, 0))
            m.putalpha(al)
            m.save(dst / (f.stem + ".png"))
        clips.setdefault(take, {})["masks"] = True
        clips_file.write_text(json.dumps(clips, ensure_ascii=False), encoding="utf-8")
        print(f"{take}: {len(files)} masks ({a.kind}) in {time.time() - t0:.1f} s", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
