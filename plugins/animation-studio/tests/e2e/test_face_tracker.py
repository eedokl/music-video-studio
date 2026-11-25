"""ai-video face_pass.py tracker switch, without models or GPU: a fake RetinaFace detection file (what
face_track_retina.py writes) drives the same face choice, follow and smoothing as MediaPipe - the lead face near the
middle / the --hint face, a missing frame bridged, someone else's face ignored; measure(tracker="retinaface") reads the
cached detections (no torch run), keeps its own cache next to the MediaPipe one, an unknown tracker is refused."""
import json

from common import Test, expect, script

FACE_PASS = script("ai-video", "face_pass.py")

DRIVER = r'''
import json, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
import cv2
import numpy as np
import face_pass as fp

d = Path(sys.argv[2])
W, H, N = 1024, 576, 30
clip = d / "c.mp4"
vw = cv2.VideoWriter(str(clip), cv2.VideoWriter_fourcc(*"mp4v"), 24, (W, H))
for _ in range(N):
    vw.write(np.zeros((H, W, 3), np.uint8))
vw.release()
frames = fp.read_frames(clip)
dets = []
for i in range(N):
    f = [] if i == 10 else [[500 + 2 * i, 200, 60 + i, 0.99]]        # the lead walks right and comes closer
    f.append([100, 300, 70, 0.95])                                    # someone at the left edge, a bit larger
    if i == 20:
        f = [[900, 450, 65, 0.9], [100, 300, 70, 0.95]]               # the lead hidden, a far-off face instead
    dets.append(f)
(d / "c.retina.json").write_text(json.dumps({"W": W, "H": H, "frames": dets}))
out = {}
t = fp.track(frames, dets=fp.retina_faces(clip))
out["lead"] = dict(hits=t["hits"], first=t["faces_first"], face=t["face"], low=t["low"], x0=t["rows"][0]["x0"],
                   n=len(t["rows"]))
t = fp.track(frames, hint=(0.1, 0.5), dets=fp.retina_faces(clip))
out["hint"] = dict(hits=t["hits"], face=t["face"], x0=t["rows"][0]["x0"])
r = fp.measure(clip, tracker="retinaface")
out["measure"] = r
out["caches"] = sorted(p.name for p in d.glob("c.face*.json"))
try:
    fp.measure(clip, tracker="bogus")
    out["bogus"] = "accepted"
except SystemExit as e:
    out["bogus"] = str(e)
print("RESULT " + json.dumps(out))
'''


def run_face_tracker(ctx):
    r = ctx.py(DRIVER, deps_from=[FACE_PASS], name="face_tracker.py", args=[str(FACE_PASS.parent), str(ctx.dir)])
    line = [l for l in r.stdout.splitlines() if l.startswith("RESULT ")]
    expect(line, f"driver printed no result:\n{r.stdout[-800:]}")
    o = json.loads(line[-1][7:])
    lead, hint, m = o["lead"], o["hint"], o["measure"]
    # lead: found in 28 of 30 frames (frame 10 missing, frame 20 only other faces), two faces in the first frame
    expect(lead["n"] == 30 and lead["hits"] == 28 and lead["first"] == 2, f"lead track: {lead}")
    expect(70 <= lead["face"] <= 78 and 60 <= lead["low"] <= 66, f"lead face widths (60-89 px growing): {lead}")
    expect(lead["x0"] > 300, f"the crop follows the lead near the middle, not the left face: {lead}")
    expect(hint["hits"] == 30 and hint["face"] == 70 and hint["x0"] < 100, f"--hint 0.1 0.5 takes the left face: {hint}")
    expect(m["tracker"] == "retinaface" and m["hits"] == 28 and m["frames"] == 30 and m["far"],
           f"measure with retinaface: {m}")
    expect(o["caches"] == ["c.face.retinaface.json"], f"retinaface keeps its own cache: {o['caches']}")
    expect("unknown face tracker" in o["bogus"], f"unknown tracker: {o['bogus']}")
    ctx.note(f"retinaface dets: lead {lead['hits']}/30 frames, face {lead['low']:.0f}-{lead['face']:.0f} px, hint -> "
            f"left face; own cache; unknown tracker refused")


TESTS = [
    Test("face-tracker", run_face_tracker, about="ai-video face_pass.py: RetinaFace detections (fake file) drive the "
         "same face choice / follow / smoothing, own measure cache, unknown tracker refused"),
]
