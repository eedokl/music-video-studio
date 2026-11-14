"""What the plan step writes besides the .sif files: the 2.5D stage config (stage.json, read by toon-2d
render_multiplane.py with assets/stage25d.html) and plan.json (events, narration, landing places - read by the
sound step and by scenes)."""


def tag_cfg(C, g, figs):
    f = next(x for x in figs if x["name"] == g["name"])
    if not f.get("tag"):
        return None
    q, side, (LX, F, LZ) = g["q"], g["side"], g["land"]
    movers = [x for x in figs if x.get("action", "step_out") == "step_out"]
    narrow = min(1.0, C.size[0] / C.size[1] / (16 / 9))                     # 4:3: closer
    if len(movers) > 1:          # a line-up: small tags, always on the same side (+x), so they never cover a neighbour
        d = f.get("tag_offset", 1.75)
        return {"src": f"tex/tag_{g['name']}.png", "w": 2.1 * narrow, "aspect": 380 / 900,
                "pos": [LX + d * q * narrow, F, LZ + 0.5 * q]}
    d = f.get("tag_offset", 3.0)
    return {"src": f"tex/tag_{g['name']}.png", "w": 2.8 * q, "aspect": 380 / 900,
            "pos": [LX - d * side * q * narrow, F, LZ + 0.6 * q]}


def stage_config(C, P, G, figs, names, order, states, n_sparkles, end, frames):
    """stage.json: output size, camera fov, slide states, room textures, one plane per figure, per-frame values."""
    return {
        "width": C.size[0], "height": C.size[1], "fps": C.fps, "end": end, "fov": C.fov, "out": "frames_3d",
        "floor_y": C.floor, "boil": P.get("boil", 0.0012),
        "slide": {"w": C.Ws, "h": C.Hs, "states": [f"tex/slide_{m:02x}.png" for m in states]},
        "tex": {"floor": "tex/floor.png", "wall": "tex/wall.png", "shadow": "tex/shadow.png",
                "sparkle": "tex/sparkle.png"},
        "sparkles": n_sparkles,
        "figures": [{"name": n, "src": f"frames/{n}/{n}.%04d.png", "light": f"light/{n}/s.%04d.png",
                     "plane_w": G[n]["plane_w"], "center_above_feet": G[n]["center_above_feet"],
                     "center_dx": G[n]["center_dx"], "foot_blobs": G[n]["blobs"],
                     "tag": tag_cfg(C, G[n], figs) if n in order else None} for n in names],
        "frames": frames}


def plan_meta(G, T, movers, names, order, states, events, end):
    """plan.json: clip length, events per figure, narration lines, slide states, geometry, landing places, variants."""
    lines = {lid: {"at": T.line_at(lid), "audio": T.cfg[lid]["audio"], "level": T.cfg[lid].get("level", 0),
                   "seconds": T.words(lid)["duration"]} for lid in T.cfg}
    return {"end": end, "events": events, "narration": lines, "states": {f"{m:02x}": i for m, i in states.items()},
            "figures": {n: {k: G[n][k] for k in ("feet_world", "height", "plane_w", "px", "su_world")} for n in names},
            "land": {n: [round(v, 3) for v in G[n]["land"]] for n in order},
            "variants": {f["name"]: {k: f.get(k) for k in ("style", "gesture", "spin")} for f in movers}}
