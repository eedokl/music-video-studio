"""Section "kind": "panels" of scene.py: a comic page on a desk, one panel per lyric line (images, parallax layers or
figures), hard camera cuts with push-in and roll per panel (c = scene_context.SceneContext).
"""
import numpy as np

import creative  # noqa: E402
from sif import V, anim, group, circle, hexc, image, clipped, outline
from scene_context import TL, BR, box
from scene_figures import figure
from scene_screen import screen_face

PANEL_BG = ["#5fb3a3", "#8a7ad6", "#e0703e", "#4f86c2", "#d96b6b", "#e09f3e", "#6bbf6b", "#c46bd6", "#3fa7c9", "#f0b84a"]


def panels_scene(c):
    """-> (camera group, cut times, figures shown per panel)"""
    import comic_page as cp
    P, A, S, E, N, F, lines = c.P, c.A, c.S, c.E, c.N, c.F, c.lines
    cut_lines = [l for l in lines if S - 0.05 <= l["t"] < E - 0.8]   # a line starting in the last 0.8 s belongs to the next section (no empty panel)
    cuts, cut_line = [S], [None]
    for l in cut_lines:                               # one panel per line; lines closer than 0.3 s share a panel
        if l["t"] > cuts[-1] + 0.3:
            cuts.append(l["t"])
            cut_line.append(l)
    if cut_lines and cut_lines[0]["t"] <= S + 0.3:
        cut_line[0] = cut_lines[0]
    line_specs = [x for x in A.get("panels", []) if x.get("line")]
    idx_specs = [x for x in A.get("panels", []) if not x.get("line")]
    n = len(cuts)
    cols = int(A.get("columns") or (creative.pick(P, f"panel_cols:{c.section}", (3, 3, 2)) if n > 4 else 2))
    rows_pp = 3
    per_page = cols * rows_pp
    pw_px = 370 if cols == 3 else 560
    ph_px = 300 if cols == 3 else 360
    aspect = A.get("panel_aspect")                    # e.g. "16:9": panels shaped like the screen, camera covers them
    if aspect:
        aspect = (lambda a_, b_: float(a_) / float(b_))(*str(aspect).split(":")) if ":" in str(aspect) else float(aspect)
        pw_px = 480 if cols == 3 else 640
        ph_px = round(pw_px / aspect)
    PW = 100 + cols * pw_px + (cols - 1) * 15
    n_rows = min(rows_pp, -(-n // cols))
    PH = 140 + n_rows * (ph_px + 30) + 40
    ppu = 100.0                                       # page pixels per unit
    pal = list(PANEL_BG)
    creative.rng(P, f"panel_bg:{c.section}").shuffle(pal)
    layers, cam_c, figs_in = [], [], []
    page_layers = []
    n_pages = -(-n // per_page)
    for pg in range(n_pages):
        px0 = pg * (PW / ppu + 2.0)                    # pages side by side on the desk
        rects = {}
        for j in range(per_page):
            i = pg * per_page + j
            if i >= n:
                break
            col, r = j % cols, j // cols
            rects[f"p{i}"] = (50 + col * (pw_px + 15), 140 + r * (ph_px + 30), pw_px, ph_px)
        title = A.get("title") if pg == 0 else ""
        if title is None:
            title = (cut_lines[0]["text"] if cut_lines else P.get("name", "")).strip()[:28]
        page_png = P.cache / f"page_{c.section}_{pg}.png"
        cp.page((PW, PH), rects, title=title or "", footer_right=f"{pg + 1}/{n_pages}" if n_pages > 1 else "",
                seed=creative.seed(P) + pg).save(page_png)
        to_u = lambda x, y, px0=px0: (px0 + (x - PW / 2) / ppu, (PH / 2 - y) / ppu)
        for key, (x, y, w, h) in rects.items():
            i = int(key[1:])
            (ux0, uy0), (ux1, uy1) = to_u(x, y), to_u(x + w, y + h)
            cx, cy, wu, hu = (ux0 + ux1) / 2, (uy0 + uy1) / 2, ux1 - ux0, uy0 - uy1
            t0 = cuts[i]
            t1 = cuts[i + 1] if i + 1 < n else E
            ln = (cut_line[i] or {}).get("text", "").lower()
            spec = next((x for x in line_specs if ln.startswith(x["line"].lower())), None)
            if spec is None:
                spec = idx_specs[i] if i < len(idx_specs) else (idx_specs[i % len(idx_specs)] if idx_specs and A.get("cycle_panels") else {})
            content = panel_content(c, i, spec, t0, t1, wu, hu, pal[i % len(pal)])
            figs_in.append(content[1])
            mask = box("Panel mask", -wu / 2, hu / 2, wu / 2, -hu / 2, hexc("#000000"))
            layers.append(group(f"Panel {i}", [clipped(f"Panel {i} clip", mask, content[0])], origin=(0, 0), offset=V(cx, cy)))
            cam_c.append((cx, cy, hu))
        tl, br = to_u(0, 0), to_u(PW, PH)
        page_layers += [box("Page shadow", tl[0] + 0.12, tl[1] - 0.12, br[0] + 0.12, br[1] - 0.12, hexc("#000000", 0.45)),
                        image(f"Page {pg}", page_png.as_posix(), tl, br)]
    desk = [box("Desk", -60, 40, 60, -40, hexc(A.get("desk_color", "#4a3524")))]
    # camera: hard cut on every line start, slow push-in + small roll and drift inside each panel
    rr = creative.rng(P, f"panel_cam:{c.section}")
    roll = rr.uniform(0.6, 1.6)
    fill0, fill1 = rr.uniform(0.95, 1.05), rr.uniform(1.12, 1.22)   # panel height vs picture height
    off, sc, ang = [], [], []
    vh = TL[1] - BR[1]
    vw = BR[0] - TL[0]
    if aspect:                                        # cover the view: no page edge or neighbour panel in the picture
        fill0, fill1, roll = 1.08 + (fill0 - 0.95) * 0.5, 1.16 + (fill1 - 1.12) * 0.5, roll * 0.5
    for i, (cx, cy, hu) in enumerate(cam_c):
        f0 = F(cuts[i])
        f1 = (F(cuts[i + 1]) if i + 1 < n else N + 1) - 1
        fit = max(vh / hu, vw / (hu * aspect)) if aspect else vh / hu
        s0, s1 = fill0 * fit, fill1 * fit
        d = (0.1 if aspect else 0.15) * (1 if i % 2 else -1)
        rl = roll * (1 if i % 2 else -1)
        off += [(f0, (-cx - d, -cy), ("constant", "linear")), (max(f1, f0), (-cx + d, -cy), ("linear", "constant"))]
        sc += [(f0, (s0, s0), ("constant", "linear")), (max(f1, f0), (s1, s1), ("linear", "constant"))]
        ang += [(f0, rl, ("constant", "linear")), (max(f1, f0), rl * 0.4, ("linear", "constant"))]
    world = group("Comic page", desk + layers + page_layers, origin=(0, 0), offset=anim("vector", off))
    cam = group("Camera", [world], origin=(0, 0), offset=V(0, (TL[1] + BR[1]) / 2), scale=anim("vector", sc),
                angle=anim("angle", ang))
    return cam, cuts, figs_in


def panel_content(c, i, spec, t0, t1, wu, hu, bg):
    """Layers of one panel in panel coordinates (centre 0, 0) and the figures it shows.
    spec: {"layers": [png ...]} | {"image": png} | {"figures": [...], "shot": close|medium|wide, "bg": "#..."} | {}
    (= auto: whoever sings this line, in close-up)."""
    from PIL import Image as PILImage
    P, F, names, figs_cfg = c.P, c.F, c.names, c.figs_cfg
    out, shown = [], []
    rp = creative.rng(P, f"panel:{c.section}:{i}")
    imgs = spec.get("layers") or ([spec["image"]] if spec.get("image") else [])
    if imgs:
        for j, src in enumerate(imgs):
            im = PILImage.open(P.path(src)).convert("RGBA")
            import comic_page as cp
            crop = cp.crop_aspect(im, wu / hu)
            p = P.cache / f"panel_{c.section}_{i}_{j}.png"
            crop.save(p)
            f0, f1 = F(t0), F(t1)
            z = 1.0 + 0.05 * (j + 1)                  # slow parallax push per layer
            out.append(group(f"Layer {j}", [image(f"Layer {j}", p.as_posix(), (-wu / 2, hu / 2), (wu / 2, -hu / 2))],
                             origin=(0, 0), scale=anim("vector", [(f0, (1.0, 1.0), "linear"), (f1, (z, z), "linear")])))
        return out, shown
    col = spec.get("bg", bg)
    out.append(box("Panel bg", -wu, hu, wu, -hu, hexc(col)))
    out.append(circle("Panel glow", hexc("#fff6d8", 0.45), 0.55 * wu, (0, 0.1 * hu), feather=0.45 * wu))
    if rp.random() < 0.7:                             # speed lines
        nl = rp.randint(18, 30)
        for j in range(nl):
            ang_ = 2 * np.pi * j / nl + rp.uniform(-0.05, 0.05)
            r0, r1 = 0.35 * hu, 1.2 * wu
            out.append(outline("Speed line", hexc("#ffffff", 0.22), [(np.cos(ang_) * r0, np.sin(ang_) * r0, 0, 0),
                                                                     (np.cos(ang_) * r1, np.sin(ang_) * r1, 0, 0)], 0.03, loop=False))
    who = spec.get("figures")
    if who is None:
        ts = np.arange(t0, max(t1, t0 + 0.1), 0.1)
        cnt = {k: sum(c.act(k, t) for t in ts) for k in names}
        singers = [k for k in sorted(names, key=lambda k: -cnt[k]) if cnt[k] > 0]
        who = [k for k in singers if figs_cfg[k].get("svg")][:2] or [k for k in singers if figs_cfg[k].get("kind") == "screen"][:1] \
            or c.svg_figs[:1]
    scr = [k for k in who if figs_cfg[k].get("kind") == "screen"]
    svgs = [k for k in who if figs_cfg[k].get("svg")]
    if scr and not svgs:
        out += screen_face(c, scr[0], rect=(-0.44 * wu, 0.42 * hu, 0.44 * wu, -0.42 * hu))
        shown += scr
    elif svgs:
        shot_ = spec.get("shot") or rp.choice(("close", "medium") if len(svgs) == 1 else ("medium", "wide"))
        cy_, vh_ = {"close": (5.0, 4.0), "medium": (4.3, 5.8), "wide": (3.8, 8.6)}[shot_]
        xs = [0.0] if len(svgs) == 1 else [-1.6, 1.6]
        figs_ = [figure(c, k, j, x=xs[j], scale=1.0, floor=0.0, actions=False) for j, k in enumerate(svgs)]
        s = hu / vh_
        out.append(group("Panel figures", figs_, origin=(0, cy_), offset=V(0, 0), scale=V(s, s)))
        shown += svgs
    return out, shown


def panels_section(c):
    """-> (camera group, frame -> set of figures in the current panel, info line)"""
    scene, cuts, figs_in = panels_scene(c)
    cut_frames = [c.F(t) for t in cuts]

    def hidden_at(f):
        i = max(j for j, cf in enumerate(cut_frames) if cf <= f) if f >= cut_frames[0] else 0
        return set(figs_in[i])
    info = f"panels {len(cuts)}, cuts at {[round(t, 2) for t in cuts]}"
    return scene, hidden_at, info
