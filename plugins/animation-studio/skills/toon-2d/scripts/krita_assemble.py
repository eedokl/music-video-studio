"""Assemble painted layers (PNG) into a layered Krita file (.kra) and export PNG combinations - headless, no dialogs.

Usage (normal Python - starts Krita's kritarunner itself, config key "krita"):
  uv run --no-project python krita_assemble.py <folder>/krita_set.json [--export-only]

krita_set.json (paths relative to the JSON file):
  {"width": 1280, "height": 720, "kra": "room.kra",
   "layers": [{"file": "set/01_sky.png", "name": "Sky"},
              {"file": "set/02_wall.png", "name": "Wall"},
              {"file": "set/03_light.png", "name": "Light", "blend": "screen", "opacity": 230}],
   "exports": {"room_back.png": ["Wall", "Light"], "room_sky.png": ["Sky"]}}
- Exports: per PNG only the named layers are visible (the rest hidden), with alpha.
- Afterwards the artist can paint over the .kra in Krita; re-export with --export-only.

How it works: kritarunner finds scripts by module name, so the launcher copies this file into the config folder
(as _krita_assemble_run.py), runs `kritarunner -s _krita_assemble_run -f main|export_only` there and removes the
copy again. Inside Krita the script must call setBatchmode(True) on Krita and the document and pass all PNG options
in the InfoObject - otherwise Krita opens the PNG options dialog and waits for a click. Log: krita_log.txt.
"""
import json
import os
import traceback

try:
    from krita import InfoObject, Krita     # only inside Krita
    IN_KRITA = True
except ImportError:
    IN_KRITA = False

if IN_KRITA:
    HERE = os.getcwd().replace("\\", "/")
    CFG = json.load(open(os.path.join(HERE, "krita_set.json"), encoding="utf-8"))
    log = open(os.path.join(HERE, "krita_log.txt"), "w", encoding="utf-8")

    def p(*a):
        log.write(" ".join(map(str, a)) + "\n")
        log.flush()

    def export(doc):
        nodes = doc.topLevelNodes()
        for out, visible in CFG.get("exports", {}).items():
            for n in nodes:
                n.setVisible(n.name() in visible)
            doc.refreshProjection()
            doc.waitForDone()
            doc.setBatchmode(True)                       # no PNG dialogs
            cfg = InfoObject()
            for k, v in (("alpha", True), ("compression", 6), ("forceSRGB", False), ("indexed", False),
                         ("interlaced", False), ("saveSRGBProfile", False), ("transparencyFillcolor", [255, 255, 255])):
                cfg.setProperty(k, v)
            doc.exportImage(f"{HERE}/{out}", cfg)
            p("exported", out, visible)
        for n in nodes:
            n.setVisible(True)

    def main(args=None):
        try:
            k = Krita.instance()
            k.setBatchmode(True)
            w, h = CFG.get("width", 1280), CFG.get("height", 720)
            doc = k.createDocument(w, h, CFG.get("name", "Set"), "RGBA", "U8", "", 72.0)
            root = doc.rootNode()
            for old in list(root.childNodes()):
                old.remove()
            for L in CFG["layers"]:
                src = k.openDocument(f"{HERE}/{L['file']}")
                data = src.topLevelNodes()[0].pixelData(0, 0, w, h)
                src.close()
                node = doc.createNode(L["name"], "paintlayer")
                root.addChildNode(node, None)
                node.setPixelData(data, 0, 0, w, h)
                node.setOpacity(L.get("opacity", 255))
                node.setBlendingMode(L.get("blend", "normal"))
                p("layer", L["name"])
            doc.saveAs(f"{HERE}/{CFG['kra']}")
            p("saved", CFG["kra"])
            export(doc)
            doc.close()
            p("done")
        except Exception:
            p(traceback.format_exc())

    def export_only(args=None):
        try:
            k = Krita.instance()
            k.setBatchmode(True)
            doc = k.openDocument(f"{HERE}/{CFG['kra']}")
            export(doc)
            doc.close()
            p("done")
        except Exception:
            p(traceback.format_exc())

    def __main__(args):
        main(args)


def launch():
    import argparse
    import shutil
    import subprocess
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import _studio
    _studio.use()
    import config
    ap = argparse.ArgumentParser(description="Painted PNG layers -> layered .kra + PNG exports (Krita, headless).")
    ap.add_argument("config", help="krita_set.json")
    ap.add_argument("--export-only", action="store_true", help="only re-export from the existing .kra")
    ap.add_argument("--timeout", type=int, default=600)
    a = ap.parse_args()
    cfg_path = Path(a.config).resolve()
    folder = cfg_path.parent
    if cfg_path.name != "krita_set.json":
        shutil.copy(cfg_path, folder / "krita_set.json")
    runner = config.need("krita")              # kritarunner (Krita's command-line script runner)
    if Path(runner).name.lower().startswith("krita.") and (Path(runner).parent / "kritarunner.exe").exists():
        runner = str(Path(runner).parent / "kritarunner.exe")
    tmp = folder / "_krita_assemble_run.py"
    shutil.copy(Path(__file__), tmp)
    try:
        subprocess.run([runner, "-s", "_krita_assemble_run", "-f", "export_only" if a.export_only else "main"],
                       cwd=folder, timeout=a.timeout, capture_output=True)
    finally:
        tmp.unlink(missing_ok=True)
    logf = folder / "krita_log.txt"
    text = logf.read_text(encoding="utf-8") if logf.exists() else ""
    print(text.strip())
    if "done" not in text.splitlines()[-1:] and not text.rstrip().endswith("done"):
        sys.exit("Krita did not finish - see krita_log.txt")


if __name__ == "__main__" and not IN_KRITA:
    launch()
