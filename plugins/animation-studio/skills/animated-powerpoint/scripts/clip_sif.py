"""Synfig scene of one slide figure (clip.py step "plan", also used by scene.py): the figure's rig with its keys."""
import numpy as np
from PIL import Image

import _studio
_studio.use("toon-2d")
from sif import anim, canvas, group, image  # noqa: E402


def head_layer(d, keys, img, angle_group, su, tl, br, has_eyes):
    """Head group: the head drawing (or head_base + one mouth stage per frame when the figure speaks) and the eyes,
    which move and blink inside the head."""
    kids = [img("head")]
    if keys.get("mouth") and (d / "head_base.png").exists():        # lip sync: base + one stage per frame
        mk = keys["mouth"]
        kids = [image("head_base", (d / "head_base.png").as_posix(), tl=tl, br=br)]
        for i in range(8):
            vis = [(f, 1.0 if s == i else 0.0, "constant") for f, s in mk]
            kids.append(group(f"mouth_{i}", [image(f"mouth_{i}", (d / f"mouth_{i}.png").as_posix(), tl=tl, br=br)],
                              amount=anim("real", vis)))
    if has_eyes:
        a = np.asarray(Image.open(d / "eyes.png"))[..., 3] > 128
        ys, xs = np.nonzero(a)
        ec = su(xs.mean(), ys.mean())
        ek = keys.get("eyes", [(0, (0, 0))])
        bk = keys.get("blink", [(0, 1)])
        kids.append(group("eyes", [img("eyes")], origin=ec,
                          offset=anim("vector", [(k[0], (ec[0] + k[1][0], ec[1] + k[1][1])) + tuple(k[2:])
                                                 for k in ek]),
                          scale=anim("vector", [(k[0], (1, k[1]), k[2] if len(k) > 2 else "linear")
                                                for k in bk])))
    return angle_group("head", kids, "head", "idle_head")


def whole_figure(name, layers, keys, com):
    """Wrap the part layers: spin (centre) -> squash (feet) -> tilt -> breath -> idle weight -> position."""
    gr = group("spin", layers, origin=com, angle=anim("angle", keys.get("spin", [(0, 0)])))
    gr = group("squash", [gr], origin=(0, 0), scale=anim("vector", keys.get("sq", [(0, (1, 1))])))
    if "tilt" in keys:                                     # whole figure tips over its feet (hop, waddle)
        gr = group("tilt", [gr], origin=(0, 0), angle=anim("angle", keys["tilt"]))
    if "idle_breath" in keys:
        gr = group("breath", [gr], origin=(0, 0), scale=anim("vector", [(f, (1, v)) for f, v in keys["idle_breath"]]))
    if "idle_tilt" in keys:
        gr = group("weight", [gr], origin=(0, 0), angle=anim("angle", keys["idle_tilt"]))
    return group(name, [gr], origin=(0, 0), offset=anim("vector", keys["pos"]) if "pos" in keys else None)


def write_sif(C, g, keys, end, gesture_part=None):
    """Synfig rig from the original parts: position -> tilt -> idle weight -> breath -> squash (feet) -> spin (centre)
    -> parts; jointed parts in angle groups (+ inner idle groups), eyes move and blink inside the head."""
    rig, d = g["rig"], g["dir"]
    W, H = rig["size"]
    su = g["su"]
    tl, br = su(0, 0), su(W, H)
    piv = {k: su(*v) for k, v in rig["pivots"].items()}
    com = su(*rig["com"])
    parts = rig["parts"]
    joints = [p for p in parts if p in piv and p not in ("head", "body", "eyes")]
    gp = gesture_part or next((p for p in ("arm_r", "arm_l", "arm", "hand_r", "wing_r", "wing", "wing_l")
                               if p in joints), None)

    def img(p):
        return image(p, (d / f"{p}.png").as_posix(), tl=tl, br=br)

    def angle_group(p, kids, k, idle):
        if idle in keys:
            kids = [group(f"{p}_idle", kids, origin=piv[p], angle=anim("angle", keys[idle]))]
        if k and k in keys:
            return group(p, kids, origin=piv[p], angle=anim("angle", keys[k]))
        return group(p, kids, origin=piv[p])

    layers = []
    for p in parts:
        if p == "eyes":
            continue
        if p == "head" and "head" in piv:
            layers.append(head_layer(d, keys, img, angle_group, su, tl, br, "eyes" in parts))
        elif p in joints:
            ch = p if p in keys else ("gesture" if p == gp else "follow")        # keys by part name win (scenes)
            layers.append(angle_group(p, [img(p)], ch, "idle_part"))
        else:
            layers.append(img(p))
    if "eyes" in parts and "head" not in piv:
        layers.append(img("eyes"))
    gr = whole_figure(g["name"], layers, keys, com)
    l, t, r, b = rig["view"]
    sif = canvas([gr], w=g["px"], h=g["px"], fps=C.fps, end=end, name=g["name"], view=f"{l} {t} {r} {b}")
    (C.dir / f"{g['name']}.sif").write_text(sif, encoding="utf-8")
