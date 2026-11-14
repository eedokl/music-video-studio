"""Set dressing of scene.py: own prop images placed on the set and silhouettes between set layers / as a shadow in the
spotlight (c = scene_context.SceneContext).
"""
import creative  # noqa: E402
from song_project import word_matches
from sif import V, anim, group, image
import scene_fx as fx


def props(c):
    """project.json "props": [{"image": "props/gpu.png", "x": -4.6, "height": 2.4, "y": null (= on the floor),
    "sections": ["chorus1"], "show_on": "gpu", "hide_on": "context", "front": false, "bounce": true}]
    -> (layers behind the figures, layers in front of them)"""
    from PIL import Image as PILImage
    P, S, E, F, keys = c.P, c.S, c.E, c.F, c.keys
    back_l, front_l = [], []
    for i, pr in enumerate(P.get("props", [])):
        if pr.get("sections") and c.section not in pr["sections"]:
            continue
        path = P.path(pr["image"])
        w_px, h_px = PILImage.open(path).size
        h = float(pr.get("height", 2.0)) * c.K
        w = h * w_px / h_px
        x = float(pr.get("x", 0.0))
        y0 = c.FLOOR if pr.get("y") is None else float(pr["y"])
        amt = [(0, 1.0, "constant")]
        for key, val in (("show_on", 1.0), ("hide_on", 0.0)):
            if pr.get(key):
                t = next((w_["t"] for w_ in c.words if word_matches(w_["word"], pr[key]) and S <= w_["t"] < E), None)
                if t is not None:
                    if key == "show_on":
                        amt[0] = (0, 0.0, "constant")
                    amt.append((F(t), val, "constant"))
        img = image(f"Prop {i}", path.as_posix(), (x - w / 2, y0 + h), (x + w / 2, y0))
        bounce = [(0, (1.0, 1.0))]
        if pr.get("bounce"):
            for b in c.beats:
                if c.in_dance(b["t"]):
                    f = F(b["t"])
                    bounce += [(f, (1.04, 0.95), "linear"), (f + 5, (1.0, 1.0))]
        layer = group(f"Prop {i}", [img], origin=(x, y0), offset=V(x, y0), scale=anim("vector", keys(bounce)),
                      amount=anim("real", keys(amt)))
        (front_l if pr.get("front") else back_l).append(layer)
    return back_l, front_l


def silhouettes(c, n_back):
    """project.json "silhouettes": [{"word": "lederjacke" | "line": "In der letzten" | "from": s, "to": s,
    "image": null (built-in faceless figure) | "props/man.png", "layer": index into the set's back layers
    (default: the set's "window" layer, else on top of the back layers), "x", "y", "height", "motion": rise|slide|fade,
    "hold": 1.0 (s after the line), "sections": [...]}] -> {layer index: [groups]}."""
    P, S, E, F, keys, lines, words = c.P, c.S, c.E, c.F, c.keys, c.lines, c.words
    out = {}
    win = c.SET.get("window") or {}
    for i, sp in enumerate(P.get("silhouettes", [])):
        if sp.get("sections") and c.section not in sp["sections"]:
            continue
        spans = []
        hold = float(sp.get("hold", 1.0))
        if sp.get("from") is not None:
            spans = [(float(sp["from"]), float(sp.get("to", sp["from"] + 3.0)))]
        else:
            for li, l in enumerate(lines):
                hit = (sp.get("line") and l["text"].lower().startswith(sp["line"].lower())) or \
                      (sp.get("word") and any(w.get("line") == li and word_matches(w["word"], sp["word"]) for w in words))
                if hit:
                    t0 = l["t"] if sp.get("line") else min(l["t"], c.word_time(sp["word"], after=l["t"] - 0.05) or l["t"])
                    spans.append((t0, l["end"] + hold))
        spans = [(max(t0, S), min(t1, E)) for t0, t1 in spans if t1 > S and t0 < E and min(t1, E) - max(t0, S) > 0.3]
        if not spans:
            continue
        shadow = not win and c.spot is not None and sp.get("layer") is None
        layer = sp.get("layer", win.get("layer", n_back) if not shadow else "shadow")
        scale = float(sp.get("height", 3.3 if shadow else 2.2)) / 2.2
        side = creative.rng(P, f"silhouette:{i}").choice((-1, 1))
        x = float(sp.get("x", win.get("x", 3.2 * side if shadow else 3.8 * side)))   # no window: peeks in at the back
        y = float(sp.get("y", win.get("y", 0.9 if shadow else 1.6)))
        motion = sp.get("motion") or creative.pick(P, f"silhouette_motion:{i}", ("rise", "slide", "fade"))
        amt, off = [(0, 0.0, "constant")], [(0, (0.0, -1.4 * scale if motion == "rise" else 0.0))]
        for t0, t1 in spans:
            f0, f1 = F(t0), F(t1)
            if motion == "rise":
                amt += [(f0, 1.0, "constant"), (f1, 0.0, "constant")]
                off += [(f0, (0.0, -1.4 * scale), "halt"), (f0 + 12, (0.0, 0.0), "halt"), (f1 - 10, (0.0, 0.0), "halt"),
                        (f1, (0.0, -1.4 * scale), "halt")]
            elif motion == "slide":
                amt += [(f0, 1.0, "constant"), (f1, 0.0, "constant")]
                off += [(f0, (-2.0 * scale, 0.0), "halt"), (f0 + 14, (0.0, 0.0), "halt"), (f1 - 12, (0.0, 0.0), "halt"),
                        (f1, (2.0 * scale, 0.0), "halt")]
            else:
                amt += [(f0, 0.0, "linear"), (f0 + 8, 1.0, "linear"), (f1 - 8, 1.0, "linear"), (f1, 0.0, "linear")]
        alpha = float(sp.get("alpha", 0.75 if shadow else 1.0))
        if sp.get("image"):
            from PIL import Image as PILImage
            path = P.path(sp["image"])
            w_px, h_px = PILImage.open(path).size
            h = 2.2
            w = h * w_px / h_px
            body = [image(f"Silhouette {i}", path.as_posix(), (-w / 2, h / 2), (w / 2, -h / 2))]
        else:
            body = fx.silhouette(alpha=alpha)
        g = group(f"Silhouette {i}", [group("Silhouette move", body, offset=anim("vector", keys(off)))],
                  origin=(0, 0), offset=V(x, y), scale=V(scale, scale), amount=anim("real", keys(amt)))
        out.setdefault(layer, []).append(g)
    return out
