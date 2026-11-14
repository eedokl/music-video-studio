"""Brick sets as data: where figures can stand, where the props and the camera targets are (pure Python, no bpy).

The shot planner (outside Blender) and sets.py (inside Blender) both read these anchors, so a camera aimed at
"window" looks where sets.py builds the window. All points are LDraw coordinates: floor y = 0, up = -y,
front (towards the default camera) = -z, 1 LDU = 0.4 mm. A minifig is 72 LDU to the neck, its face at y ~ -84.

Variants (picked with the creative seed unless the plan fixes them):
  flip     mirror the set left/right (anchors and figure places follow)
  palette  wall/floor colours, mood = light colours (night_blue, warm_lamp, neon)
Sets: room (desk, monitor that can talk, window with a night city, server rack, coins), stage (curtain, bulb arch,
coloured spot cones, keyboard riser, glowing graphics card), rooftop (parapet, skyline, string lights, antenna,
stair hut with a door for cameos), house (night exterior: facade with a lit window, garden, fence, trees, moon and
stars - Tim's room is built behind the window; shots are one camera flight through the garden into the window),
arena (winners' podium of three heights, stadium lights, dark stands, a mountain of chips with the cameo on top),
cloud (auction above the clouds: white round-brick clouds, lectern, rows of seats, a sea of gold coins, moon).
"spot_floor": y of the feet per spot (podium tops); "flight": camera path of the house set (cam/aim points).
"""
SETS = {
    "room": {
        "spots": [(0, 0), (190, 10), (-90, 30), (110, 60)],          # where cast members stand, in order
        "yaw": [17.0, 20.0, 10.0, -10.0],
        "anchors": {
            "window": (-200, -150, 150), "outside": (-195, -150, 215), "outside_hidden": (-380, -150, 215),
            "monitor": (88, -80, 18), "desk": (80, -40, 0), "coins": (130, -60, 20), "gpu": (110, -56, -28),
            "rack": (240, -90, 100), "wall": (0, -120, 150), "keyboard": (55, -48, -17),
        },
        "cameo_floor": -58,                  # cameo figures float outside the window: y of their feet (neck at -130)
        "wide": ((60, -160, -600), (60, -70, 20)),
        "palettes": [
            {"wall": [72, 379], "floor": 72, "mood": "night_blue"},
            {"wall": [19, 28], "floor": 70, "mood": "warm_lamp"},
            {"wall": [71, 72], "floor": 0, "mood": "neon"},
            {"wall": [379, 15], "floor": 72, "mood": "night_blue"},
        ],
    },
    "stage": {
        "spots": [(-60, -10), (90, 0), (220, 20), (-200, 20)],
        "yaw": [8.0, -8.0, -15.0, 15.0],
        "anchors": {
            "curtain": (0, -150, 150), "keyboard": (-90, -40, -66), "gpu": (230, -64, -40), "arch": (0, -200, 128),
            "outside": (0, -150, 140), "outside_hidden": (0, -150, 260), "wall": (0, -150, 150),
        },
        "cameo_floor": 0,
        "wide": ((0, -170, -640), (0, -80, 30)),
        "palettes": [
            {"curtain": 320, "floor": 0, "mood": "warm_lamp", "spots": [[1.0, 0.3, 0.6], [0.3, 0.7, 1.0], [1.0, 0.8, 0.3]]},
            {"curtain": 22, "floor": 0, "mood": "neon", "spots": [[0.2, 1.0, 0.6], [1.0, 0.2, 0.8], [0.3, 0.5, 1.0]]},
            {"curtain": 1, "floor": 72, "mood": "night_blue", "spots": [[1.0, 0.9, 0.6], [0.6, 0.8, 1.0], [1.0, 0.5, 0.2]]},
        ],
    },
    "rooftop": {
        "spots": [(0, 0), (150, 20), (-140, 30), (260, 60)],
        "yaw": [10.0, -12.0, 15.0, -20.0],
        "anchors": {
            "skyline": (0, -200, 420), "door": (-260, -60, 140), "antenna": (300, -200, 160), "parapet": (0, -16, -140),
            "outside": (-260, 0, 80), "outside_hidden": (-260, 0, 240), "wall": (0, -150, 300),
        },
        "cameo_floor": 0,
        "wide": ((40, -200, -620), (40, -80, 60)),
        "palettes": [
            {"floor": 72, "parapet": 71, "mood": "night_blue", "bulbs": [1.0, 0.75, 0.35]},
            {"floor": 0, "parapet": 72, "mood": "neon", "bulbs": [1.0, 0.3, 0.7]},
            {"floor": 19, "parapet": 28, "mood": "warm_lamp", "bulbs": [1.0, 0.85, 0.5]},
        ],
    },
    "house": {
        "spots": [(0, 0), (190, 10), (-90, 30), (110, 60)],          # inside the room behind the facade
        "yaw": [-65.0, 20.0, 10.0, -10.0],
        "anchors": {
            "window": (40, -156, -160), "monitor": (88, -80, 18), "desk": (80, -40, 0), "keyboard": (55, -48, -17),
            "coins": (130, -60, 20), "gpu": (110, -56, -28), "outside": (-195, -150, 215),
            "outside_hidden": (-380, -150, 215), "wall": (40, -200, -160), "letters": (40, -420, -200),
        },
        "cameo_floor": -58,
        "flight": {"cam": [(80, -230, -1700), (80, -215, -1380), (40, -165, -560), (30, -140, -260), (15, -112, -120)],
                   "aim": [(60, -150, -160), (60, -150, -160), (40, -150, -160), (35, -120, -60), (30, -86, 0)]},
        "palettes": [
            {"wall": [72, 379], "floor": 72, "facade": [19, 28], "roof": 320, "mood": "night_blue"},
            {"wall": [19, 28], "floor": 70, "facade": [15, 71], "roof": 72, "mood": "night_blue"},
            {"wall": [71, 72], "floor": 0, "facade": [28, 70], "roof": 0, "mood": "warm_lamp"},
        ],
    },
    "arena": {
        "spots": [(-210, -70), (0, 40), (-80, 40), (80, 40)],        # front floor, then podium 1st / 2nd / 3rd
        "spot_floor": [0, -72, -48, -24],
        "yaw": [30.0, 0.0, 8.0, -8.0],
        "anchors": {
            "podium": (0, -96, 40), "chips": (250, -60, 190), "stands": (0, -60, 400), "lights": (0, -260, 420),
            "outside": (250, -150, 190), "outside_hidden": (250, -150, 330), "wall": (0, -150, 400),
            "letters": (0, -330, 120), "keyboard": (-80, -100, 40), "gpu": (0, -100, 40), "coins": (-150, -20, -40),
        },
        "cameo_floor": -56,                  # feet on top of the chip mountain
        "palettes": [
            {"floor": 72, "podium": 15, "stands": 0, "lights": [1.0, 0.95, 0.8], "mood": "night_blue"},
            {"floor": 0, "podium": 14, "stands": 72, "lights": [0.6, 0.9, 1.0], "mood": "neon"},
            {"floor": 71, "podium": 15, "stands": 1, "lights": [1.0, 0.85, 0.6], "mood": "warm_lamp"},
        ],
    },
    "cloud": {
        "spots": [(0, 30), (-150, 0), (150, 10), (-260, 60)],        # lectern, then the bidders
        "yaw": [0.0, 20.0, -20.0, 25.0],
        "anchors": {
            "lectern": (0, -70, 60), "coins": (-120, -10, -120), "seats": (0, -60, 230), "moon": (420, -520, 900),
            "outside": (120, -150, 300), "outside_hidden": (120, -150, 420), "wall": (0, -150, 300),
            "letters": (0, -340, 200), "keyboard": (0, -70, 60), "gpu": (0, -70, 60),
        },
        "cameo_floor": -72,                  # the last (highest) row of seats
        "palettes": [
            {"floor": 15, "cloud": [15, 151], "seats": 72, "lectern": 70, "sky": [0.012, 0.02, 0.06], "mood": "night_blue"},
            {"floor": 15, "cloud": [15, 503], "seats": 1, "lectern": 0, "sky": [0.05, 0.1, 0.22], "mood": "warm_lamp"},
            {"floor": 151, "cloud": [15, 9], "seats": 0, "lectern": 70, "sky": [0.03, 0.01, 0.06], "mood": "neon"},
        ],
    },
}

MOODS = {   # key light, fill, rim, world colour (linear)
    "night_blue": {"key": (1.0, 0.82, 0.62), "fill": (0.5, 0.6, 1.0), "rim": (0.55, 0.65, 1.0), "world": (0.012, 0.02, 0.045)},
    "warm_lamp": {"key": (1.0, 0.75, 0.5), "fill": (0.9, 0.7, 0.55), "rim": (1.0, 0.6, 0.35), "world": (0.03, 0.022, 0.016)},
    "neon": {"key": (0.95, 0.85, 1.0), "fill": (0.3, 0.9, 1.0), "rim": (1.0, 0.25, 0.75), "world": (0.02, 0.008, 0.035)},
}


def flip_x(p, flip):
    return (-p[0], *p[1:]) if flip else tuple(p)


def anchor(kind, name, flip=False):
    a = SETS[kind]["anchors"].get(name)
    return None if a is None else flip_x(a, flip)


def spot(kind, i, flip=False):
    s = SETS[kind]["spots"][i % len(SETS[kind]["spots"])]
    yaw = SETS[kind]["yaw"][i % len(SETS[kind]["yaw"])]
    return ((-s[0], s[1]) if flip else tuple(s)), (-yaw if flip else yaw)


def spot_floor(kind, i):
    """y of the feet on spot i (0 = floor; podiums are higher, i.e. negative)"""
    fl = SETS[kind].get("spot_floor")
    return float(fl[i % len(fl)]) if fl else 0.0
