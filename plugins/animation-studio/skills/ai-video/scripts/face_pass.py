# /// script
# requires-python = "==3.12.*"
# dependencies = ["mediapipe==1.2.3", "numpy==2.5.4", "opencv-python-headless==5.0.0.93"]
# [tool.uv]
# exclude-newer = "2026-11-14T00:00:00Z"
# ///
"""Far-face pass: rebuild a small face in a finished clip with LTX-2.3 and the Lightricks pixel upscaler IC-LoRA.

LTX-2.3 (and 2.5, same encoder) works on a 32x smaller latent grid. A face under ~90 px at 1024x576 lies on 1-3 grid
cells and is invented anew in every frame: smeared, half-closed, crooked eyes, while the start image was clean. This
pass (test "D2" of "Du bist die Maschine", 2026-11-25; five ways compared, see claudia-music-video lessons.md):
  1. track the face (MediaPipe, also in cut-outs around the last position - its detector misses faces under ~1/10 of
     the picture width; optional tracker="retinaface": face_track_retina.py, CPU PyTorch in its own uv environment,
     for faces under ~40 px, profiles, crowds, fast pans), smooth it, a square crop that follows the face size (face ~ 1/FACTOR of the crop) -> 512 px
  2. LTX-2.3 generates the crop anew at 1024 px from full noise, guided by the crop itself (IC-LoRA "pixel spatial
     upscaler x2", 8 distilled steps), with the clean face of the START IMAGE pinned on frame 0 (identity anchor) and
     the shot's vocals riding along (the lips stay in time: r 0.68 against 0.65 on the test shot)
  3. the result is colour-matched to the original crop (LAB mean/std in the face ellipse) and blended back with a
     feathered ellipse - hair, body and background stay the original pixels; where the take comes close (face over
     SMALL px) the pass fades out to the original by FADE_TO px: a near face is fine in the clip, the pass only added
     freckles and make-up there
Costs ~1.6 s GPU per frame (a 7-s clip 4-6 min) + ~30 s CPU. Side effects seen: the face looks a little more
made-up (eyeliner, fuller lips), a hair streak near the face can widen, more skin texture - compare with the clip.

Needs: ComfyUI with the LTX-2.3 checkpoint (role ltx23) and the LoRA file of role ltx23_upscale_x2 (assets/models.json,
models/loras), the clip's json (image = start image, audio = vocals, prompt), config face_landmarker, ffmpeg.

  uv run face_pass.py measure <clip.mp4> [...] [--tracker auto|retinaface]   face width (px, scaled to 1024 wide)
  uv run face_pass.py fix <clip.mp4> [-o out.mp4] [--hint x y] [--seed 7] [--redo] [--tracker retinaface]
        -> <clip>_g.mp4 + json (the clip's json plus "face_fix") + <clip>_g.sheet.jpg (top original, bottom fixed);
           the generated crop is kept in <clip dir>/face_pass/<clip stem>/pass_<seed>.mp4 - a second call only
           blends it in again (no GPU) unless --redo
  from face_pass import measure, fix
"""
import argparse
import json
import re
import shutil
import subprocess
import time
from pathlib import Path

import numpy as np

import _studio  # noqa: E402
_studio.use()
import clips  # noqa: E402
from cvio import imread, video_capture  # noqa: E402
from mouth import landmarker_model  # noqa: E402

SIZE = 512             # crop side fed to LTX (the result comes back at 2 x SIZE)
FACTOR = 3.4           # crop side = face width x FACTOR: the head needs context (2.6 squeezed the face in one test)
SMALL = 85             # face width (px at 1024 wide, 10th percentile of the take) below which a face counts as "far"
FADE_TO = 130          # face width from which the original clip is shown again (soft blend between SMALL and this)
SEED = 7
TRACKERS = ("mediapipe", "retinaface")
AUTO_HITS = 0.9        # "auto": MediaPipe found the face in fewer frames than this share ...
AUTO_NEAR = 110        # ... and the face's small part is under this (px) - near the "far" line: ask RetinaFace
MEASURE_V = 2          # bump when the tracking changes: cached <clip>.face.json files are measured again
CKPT, GEMMA, UPSCALER = "ltx23", "gemma3_te", "ltx23_upscale_x2"
SIGMAS = "1.0, 0.99375, 0.9875, 0.98125, 0.975, 0.909375, 0.725, 0.421875, 0.0"
EYES = ("Sharp, detailed, symmetric eyes with clear irises and natural eyelids, steady gaze, natural skin texture, "
        "natural light make-up.")
# eyeshadow / glitter: under coloured club light the pass invented make-up (maschine_dance s06 glitter eyeshadow,
# s08 strong eye make-up - 2 of 9 fixes dropped; natural light: 3 of 3 fine)
NEG_EYES = ("blurry eyes, smeared eyes, asymmetric eyes, crossed eyes, half-closed eyes, heavy eyeliner, heavy make-up, "
            "eyeshadow, coloured eyeshadow, glitter, glitter make-up, smoky eyes, deformed face")
_state = {}


# ---------------------------------------------------------------- tracking

def read_frames(path):
    cap = video_capture(path)
    out = []
    while True:
        ok, f = cap.read()
        if not ok:
            break
        out.append(f)
    cap.release()
    return out


def _landmarker():
    if "lm" not in _state:
        from mediapipe.tasks.python import BaseOptions, vision
        _state["lm"] = vision.FaceLandmarker.create_from_options(vision.FaceLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=landmarker_model()), num_faces=4,
            min_face_detection_confidence=0.4, min_face_presence_confidence=0.4))
    return _state["lm"]


def _faces(bgr, x=0, y=0, side=None, to=SIZE):
    """Faces in a square window (x, y, side) of the picture, scaled up to `to` px first: [(cx, cy, width)] in picture
    pixels. width = horizontal extent of the face mesh (cheek to cheek)."""
    import cv2
    import mediapipe as mp
    H, W = bgr.shape[:2]
    if side is None:
        win, k = bgr, 1.0
    else:
        win = bgr[y:y + side, x:x + side]
        k = to / side
        win = cv2.resize(win, (to, to), interpolation=cv2.INTER_CUBIC if k > 1 else cv2.INTER_AREA)
    h, w = win.shape[:2]
    r = _landmarker().detect(mp.Image(image_format=mp.ImageFormat.SRGB,
                                      data=np.ascontiguousarray(cv2.cvtColor(win, cv2.COLOR_BGR2RGB))))
    out = []
    for f in r.face_landmarks or []:
        p = np.array([[q.x * w, q.y * h] for q in f], np.float32)
        lo, hi = p.min(0), p.max(0)
        out.append((x + (lo[0] + hi[0]) / 2 / k, y + (lo[1] + hi[1]) / 2 / k, (hi[0] - lo[0]) / k))
    return out


def _window(cx, cy, side, W, H):
    side = int(min(side, W, H))
    return (int(min(max(cx - side / 2, 0), W - side)), int(min(max(cy - side / 2, 0), H - side)), side)


def _first(bgr, hint=None):
    """All faces of the first frame: whole picture + overlapping square cut-outs (small faces), doubles dropped."""
    H, W = bgr.shape[:2]
    found = _faces(bgr)
    side = int(min(H, W) * 0.5)
    for y in np.linspace(0, H - side, 3).astype(int):
        for x in np.linspace(0, W - side, max(2, int(np.ceil(2 * W / side)) - 1)).astype(int):
            for c in _faces(bgr, int(x), int(y), side):
                if all(abs(c[0] - o[0]) + abs(c[1] - o[1]) > 0.5 * max(c[2], o[2]) for o in found):
                    found.append(c)
    return _choose(found, hint, W, H)


def _choose(found, hint, W, H):
    """(the lead face, number of faces) among the faces of the first frame."""
    if not found:
        return None, 0
    if hint is None:                     # several faces: the lead is framed near the middle (two-shots, people around)
        big = max(c[2] for c in found)
        found = [c for c in found if c[2] >= 0.5 * big]
        hint = (0.5, 0.35)
    hx, hy = hint[0] * W, hint[1] * H
    return min(found, key=lambda c: abs(c[0] - hx) + abs(c[1] - hy)), len(found)


def retina_faces(clip):
    """All faces of every frame from RetinaFace (face_track_retina.py in its own uv environment, CPU):
    [[(cx, cy, width), ...] per frame]. Cached next to the clip (<clip>.retina.json)."""
    import config
    clip = Path(clip)
    cf = clip.with_suffix(".retina.json")
    if not (cf.exists() and cf.stat().st_mtime >= clip.stat().st_mtime):
        script = Path(__file__).resolve().parent / "face_track_retina.py"
        subprocess.run(config.script_cmd(script) + [str(clip), "-o", str(cf)], check=True)
    return [[tuple(d[:3]) for d in f] for f in json.loads(cf.read_text(encoding="utf-8"))["frames"]]


def _smooth(boxes, win):
    n = len(boxes)
    idx = [i for i, b in enumerate(boxes) if b]
    arr = np.array([boxes[i] for i in idx], float)
    full = np.stack([np.interp(range(n), idx, arr[:, k]) for k in range(3)], 1)
    if n < 3:
        return full
    win = min(win, n - (1 - n % 2))
    k = np.ones(win) / win
    pad = np.pad(full, ((win // 2, win // 2), (0, 0)), mode="edge")
    return np.stack([np.convolve(pad[:, j], k, mode="valid") for j in range(3)], 1)


def track(frames, hint=None, factor=FACTOR, dets=None):
    """Per frame {x0, y0, side, face} of a square crop around the face; None when no face is found at all.
    MediaPipe: the search window follows the last position (6 face widths, at least 160 px), so a small face is found
    at 512 px. dets = all faces per frame from another tracker (retina_faces) instead - same choice and smoothing."""
    H, W = frames[0].shape[:2]
    first = (lambda i: _choose(dets[i], hint, W, H)) if dets else (lambda i: _first(frames[i], hint))
    prev, n_first = first(0)
    if prev is None:
        for i in range(1, min(12, len(frames))):                # face hidden at the very start: try a few frames
            prev, n_first = first(i)
            if prev:
                break
    if prev is None:
        return None
    boxes = []
    for i, f in enumerate(frames):
        if dets:
            found = dets[i] if i < len(dets) else []
        else:
            x, y, s = _window(prev[0], prev[1], max(6 * prev[2], 160), W, H)
            found = _faces(f, x, y, s)
        best = min(found, key=lambda c: abs(c[0] - prev[0]) + abs(c[1] - prev[1])) if found else None
        if best and abs(best[0] - prev[0]) + abs(best[1] - prev[1]) > max(60, 1.2 * prev[2]):
            best = None                                         # someone else's face
        if best:
            prev = best
        boxes.append(best)
    hits = sum(b is not None for b in boxes)
    if hits < max(3, len(frames) // 4):
        return None
    tr = _smooth(boxes, 9)
    fw = _smooth([tuple(t) for t in tr], 25)[:, 2]              # face size changes slowly: no zoom pumping
    rows = []
    for (cx, cy, _), w in zip(tr, fw):
        side = int(np.clip(round(w * factor), 64, min(W, H)))
        x0 = int(round(min(max(cx - side / 2, 0), W - side)))
        y0 = int(round(min(max(cy - side * 0.45, 0), H - side)))
        rows.append(dict(x0=x0, y0=y0, side=side, face=round(float(w), 1)))
    return dict(rows=rows, hits=hits, faces_first=n_first, W=W, H=H, frames=len(frames),
                face=round(float(np.median(fw)) * 1024 / W, 1), low=round(float(np.percentile(fw, 10)) * 1024 / W, 1))


def _track(clip, frames, hint, tracker):
    if tracker not in TRACKERS:
        raise SystemExit(f"unknown face tracker {tracker!r} - one of {', '.join(TRACKERS)}")
    return track(frames, hint, dets=retina_faces(clip) if tracker == "retinaface" else None)


def measure_auto(clip, hint=None, tracker="auto", log=print):
    """(measure, tracker used). tracker "auto": MediaPipe, and RetinaFace only where MediaPipe found no face or lost it
    (face in < AUTO_HITS of the frames) while the face is near the far line (small part < AUTO_NEAR px) - there a
    profile or a turned head can decide "far" or not. A near face MediaPipe loses for a moment stays with MediaPipe."""
    if tracker != "auto":
        return measure(clip, hint, tracker), tracker
    m = measure(clip, hint)
    lost = m["face"] is None or (m.get("frames") and m["hits"] < AUTO_HITS * m["frames"] and m["low"] < AUTO_NEAR)
    if not lost:
        return m, "mediapipe"
    why = "no face" if m["face"] is None else f"face in {m['hits']}/{m['frames']} frames, small part {m['low']:.0f} px"
    log(f"  {Path(clip).name}: MediaPipe {why} - measuring again with RetinaFace (CPU)")
    r = measure(clip, hint, "retinaface")
    return (r, "retinaface") if r["face"] is not None else (m, "mediapipe")


def measure(clip, hint=None, tracker="mediapipe"):
    """{"face": median face width, "low": 10th percentile (px scaled to a 1024-wide picture; None = no face found),
    "hits": frames with a face, "far": low < SMALL}. A face that grows during the take counts by its small part.
    Cached next to the clip (<clip>.face.json, other trackers <clip>.face.<tracker>.json)."""
    clip = Path(clip)
    cf = clip.with_suffix(".face.json" if tracker == "mediapipe" else f".face.{tracker}.json")
    if cf.exists() and cf.stat().st_mtime >= clip.stat().st_mtime:
        r = json.loads(cf.read_text(encoding="utf-8"))
        if r.get("v") == MEASURE_V and r.get("hint") == hint and r.get("tracker", "mediapipe") == tracker:
            return r
    frames = read_frames(clip)
    t = _track(clip, frames, hint, tracker)
    r = dict(v=MEASURE_V, face=t["face"] if t else None, low=t["low"] if t else None, hits=t["hits"] if t else 0,
             frames=len(frames), hint=hint, tracker=tracker)
    r["far"] = r["low"] is not None and r["low"] < SMALL
    cf.write_text(json.dumps(r), encoding="utf-8")
    return r


# ---------------------------------------------------------------- crop / paste

def _writer(out, w, h, fps, audio_from=None):
    from media import ffmpeg
    cmd = [ffmpeg(), "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{w}x{h}", "-r", str(fps),
           "-i", "-"]
    if audio_from:
        cmd += ["-i", str(audio_from), "-map", "0:v", "-map", "1:a?", "-c:a", "copy", "-shortest"]
    cmd += ["-c:v", "libx264", "-crf", "12", "-preset", "slow", "-pix_fmt", "yuv420p", str(out)]
    return subprocess.Popen(cmd, stdin=subprocess.PIPE)


def write_crop(frames, rows, out, fps):
    import cv2
    p = _writer(out, SIZE, SIZE, fps)
    for f, r in zip(frames, rows):
        s = r["side"]
        p.stdin.write(cv2.resize(f[r["y0"]:r["y0"] + s, r["x0"]:r["x0"] + s], (SIZE, SIZE),
                                 interpolation=cv2.INTER_LANCZOS4).tobytes())
    p.stdin.close()
    if p.wait():
        raise RuntimeError("ffmpeg failed writing the face crop")


def start_crop(image, rows, W, H, out):
    import cv2
    im = imread(image)
    if im is None:
        raise SystemExit(f"start image not readable: {image}")
    im = cv2.resize(im, (W, H), interpolation=cv2.INTER_LANCZOS4)
    r = rows[0]
    s = r["side"]
    cv2.imwrite(str(out), cv2.resize(im[r["y0"]:r["y0"] + s, r["x0"]:r["x0"] + s], (SIZE, SIZE),
                                     interpolation=cv2.INTER_LANCZOS4))


def _mask(side):
    import cv2
    m = np.zeros((side, side), np.float32)
    cv2.ellipse(m, (side // 2, int(side * 0.47)), (int(side * 0.30), int(side * 0.38)), 0, 0, 360, 1.0, -1)
    k = max(3, int(side * 0.12) | 1)
    return cv2.GaussianBlur(m, (k, k), 0)[..., None]


def _match(src, ref, m):
    import cv2
    a = cv2.cvtColor(src, cv2.COLOR_BGR2LAB).astype(np.float32)
    b = cv2.cvtColor(ref, cv2.COLOR_BGR2LAB).astype(np.float32)
    w = m[..., 0] > 0.5
    for c in range(3):
        sa, sb = a[..., c][w], b[..., c][w]
        a[..., c] = (a[..., c] - sa.mean()) / (sa.std() + 1e-5) * sb.std() + sb.mean()
    return cv2.cvtColor(np.clip(a, 0, 255).astype(np.uint8), cv2.COLOR_LAB2BGR)


def weight(face):
    """How much of the pass is shown at a face width (px at 1024 wide): all of it while the face is far, fading out
    to the original clip by FADE_TO - a near face is fine in the original, the pass only adds freckles and make-up
    there (a take zooming in from 78 to 225 px, 2026-11-25)."""
    return float(np.clip((FADE_TO - face) / (FADE_TO - SMALL), 0.0, 1.0))


def paste(clip, frames, rows, crops, out, fps):
    """Blend the processed crops back into the clip frames (colour-matched, feathered ellipse); the clip's own sound
    track (if any) is copied."""
    import cv2
    H, W = frames[0].shape[:2]
    tmp = Path(out).with_name(Path(out).stem + ".encoding.mp4")
    p = _writer(tmp, W, H, fps, audio_from=clip)
    n = min(len(frames), len(crops))
    for i, f in enumerate(frames):
        k = weight(rows[i]["face"] * 1024 / W) if i < n else 0.0
        if k > 0:
            r, f = rows[i], f.copy()
            s, x0, y0 = r["side"], r["x0"], r["y0"]
            m = _mask(s)
            orig = f[y0:y0 + s, x0:x0 + s]
            new = _match(cv2.resize(crops[i], (s, s), interpolation=cv2.INTER_AREA), orig, m)
            m = m * k                                           # fade only after the colour match (it reads m > 0.5)
            f[y0:y0 + s, x0:x0 + s] = (new * m + orig * (1 - m)).astype(np.uint8)
        p.stdin.write(f.tobytes())
    p.stdin.close()
    if p.wait():
        raise RuntimeError("ffmpeg failed writing the face-fixed clip")
    tmp.replace(out)
    return n


def sheet(before, after, rows, out, cols=7, cell=200):
    """Before/after sheet: tight face crops at `cols` frames, top row the clip, bottom row the pass."""
    import cv2
    n = min(len(before), len(after))
    idx = np.linspace(2, n - 3, cols).astype(int)
    lines = []
    for fr in (before, after):
        cells = []
        for i in idx:
            r = rows[i]
            t = int(r["side"] * 0.6)
            x, y = r["x0"] + (r["side"] - t) // 2, r["y0"] + int(r["side"] * 0.12)
            c = cv2.resize(fr[i][y:y + t, x:x + t], (cell, cell), interpolation=cv2.INTER_CUBIC)
            cv2.putText(c, f"f{i}", (5, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)
            cells.append(c)
        lines.append(np.hstack(cells))
    cv2.imwrite(str(out), np.vstack(lines), [cv2.IMWRITE_JPEG_QUALITY, 90])


# ---------------------------------------------------------------- LTX workflow

def crop_prompt(meta):
    """Prompt for the face crop from the clip's prompt: the person, the sung words, sharp eyes - no scene, no framing."""
    p = meta.get("prompt", "")
    m = re.search(r"\b(an? (?:woman|man|girl|boy)\b.*?)(?:, (?:she|he) |\. )", p)
    person = m.group(1).rstrip(" ,") if m else "the person"
    he = bool(re.match(r"an? (man|boy)\b", person))
    w = re.search(r'words "([^"]+)"', p)
    sing = (f' {"He" if he else "She"} sings the words "{w.group(1)}", {"his" if he else "her"} lips clearly form every '
            f'word.') if w else ""
    return f"Close-up portrait of {person}, the face fills the frame.{sing} {EYES} Cinematic photographic 35mm film look."


def workflow(video, img, wav, frames, prompt, neg, seed, prefix, lora_strength=1.0):
    """The crop video is the IC-LoRA reference (half size); the clip is generated at 2 x SIZE from full noise with
    the start-image face on frame 0 and the vocals fixed (audio latent noise mask 0)."""
    import comfy_models
    ckpt = comfy_models.file(CKPT)
    big = 2 * SIZE
    dur = frames / clips.LTX_FPS
    wf = {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": ckpt}},
        "2": {"class_type": "LTXAVTextEncoderLoader", "inputs": {"text_encoder": comfy_models.file(GEMMA),
                                                                "ckpt_name": ckpt, "device": "default"}},
        "3": {"class_type": "LTXVAudioVAELoader", "inputs": {"ckpt_name": ckpt}},
        "4": {"class_type": "LoraLoaderModelOnly", "inputs": {"model": ["1", 0], "lora_name": comfy_models.file(UPSCALER),
                                                             "strength_model": lora_strength}},
        "5": {"class_type": "LoadVideo", "inputs": {"file": video}},
        "6": {"class_type": "GetVideoComponents", "inputs": {"video": ["5", 0]}},
        "8": {"class_type": "GetICLoRAParameters", "inputs": {"iclora_model": ["4", 0]}},
        "10": {"class_type": "LoadImage", "inputs": {"image": img}},
        "11": {"class_type": "ImageScale", "inputs": {"image": ["10", 0], "upscale_method": "lanczos", "width": big,
                                                      "height": big, "crop": "center"}},
        "12": {"class_type": "LTXVPreprocess", "inputs": {"image": ["11", 0], "img_compression": 18}},
        "20": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["2", 0], "text": prompt}},
        "21": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["2", 0], "text": neg}},
        "22": {"class_type": "LTXVConditioning", "inputs": {"positive": ["20", 0], "negative": ["21", 0],
                                                           "frame_rate": float(clips.LTX_FPS)}},
        "30": {"class_type": "EmptyLTXVLatentVideo", "inputs": {"width": big, "height": big, "length": frames,
                                                               "batch_size": 1}},
        "31": {"class_type": "LTXVImgToVideoInplace", "inputs": {"vae": ["1", 2], "image": ["12", 0], "latent": ["30", 0],
                                                                "strength": 1.0, "bypass": False}},
        "32": {"class_type": "LTXVAddGuide", "inputs": {"positive": ["22", 0], "negative": ["22", 1], "vae": ["1", 2],
                                                        "latent": ["31", 0], "image": ["6", 0], "frame_idx": 0,
                                                        "strength": 1.0, "iclora_parameters": ["8", 0]}},
        "40": {"class_type": "LoadAudio", "inputs": {"audio": wav}},
        "41": {"class_type": "TrimAudioDuration", "inputs": {"audio": ["40", 0], "start_index": 0.0, "duration": dur}},
        "42": {"class_type": "LTXVAudioVAEEncode", "inputs": {"audio": ["41", 0], "audio_vae": ["3", 0]}},
        "43": {"class_type": "SolidMask", "inputs": {"value": 0.0, "width": big, "height": big}},
        "44": {"class_type": "SetLatentNoiseMask", "inputs": {"samples": ["42", 0], "mask": ["43", 0]}},
        "45": {"class_type": "LTXVConcatAVLatent", "inputs": {"video_latent": ["32", 2], "audio_latent": ["44", 0]}},
        "50": {"class_type": "CFGGuider", "inputs": {"model": ["4", 0], "positive": ["32", 0], "negative": ["32", 1],
                                                    "cfg": 1.0}},
        "51": {"class_type": "KSamplerSelect", "inputs": {"sampler_name": "euler"}},
        "52": {"class_type": "ManualSigmas", "inputs": {"sigmas": SIGMAS}},
        "53": {"class_type": "RandomNoise", "inputs": {"noise_seed": seed}},
        "54": {"class_type": "SamplerCustomAdvanced", "inputs": {"noise": ["53", 0], "guider": ["50", 0],
                                                                  "sampler": ["51", 0], "sigmas": ["52", 0],
                                                                  "latent_image": ["45", 0]}},
        "55": {"class_type": "LTXVSeparateAVLatent", "inputs": {"av_latent": ["54", 0]}},
        "56": {"class_type": "LTXVCropGuides", "inputs": {"positive": ["32", 0], "negative": ["32", 1],
                                                          "latent": ["55", 0]}},
        "60": {"class_type": "VAEDecodeTiled", "inputs": {"samples": ["56", 2], "vae": ["1", 2], "tile_size": 768,
                                                         "overlap": 64, "temporal_size": 4096, "temporal_overlap": 4}},
        "70": {"class_type": "SaveImage", "inputs": {"images": ["60", 0], "filename_prefix": prefix}},
    }
    return wf


def fix(clip, out=None, hint=None, seed=SEED, redo=False, prompt=None, log=print, tracker="mediapipe"):
    """Run the pass on one clip -> out (default <clip>_g.mp4) + json + sheet. The generated face crop is kept in
    <clip dir>/face_pass/<clip stem>/pass_<seed>.mp4: a second call only blends again (no GPU) unless redo=True."""
    import cv2
    clip = Path(clip)
    out = Path(out) if out else clip.with_name(clip.stem + "_g.mp4")
    meta = clips.read_meta(clip)
    for k in ("image", "audio"):
        if not meta.get(k) or not Path(meta[k]).exists():
            raise SystemExit(f"{clip.name}: the clip json has no usable '{k}' - the pass needs the start image and the "
                             f"shot's vocals")
    work = clip.parent / "face_pass" / clip.stem
    work.mkdir(parents=True, exist_ok=True)
    frames = read_frames(clip)
    fps = int(meta.get("fps", clips.LTX_FPS))
    t = _track(clip, frames, hint, tracker)
    if t is None:
        raise SystemExit(f"{clip.name}: no face found to track")
    if t["faces_first"] > 1 and hint is None:
        log(f"  {clip.name}: {t['faces_first']} faces in the first frame - took the large one nearest the middle; "
            f"give --hint x y (shot key face_hint) if that is the wrong one")
    (work / "track.json").write_text(json.dumps(t, indent=0), encoding="utf-8")
    done = work / f"pass_{seed}.mp4"
    gpu = 0
    if redo or not done.exists():
        import comfy
        write_crop(frames, t["rows"], work / "crop.mp4", fps)
        start_crop(meta["image"], t["rows"], t["W"], t["H"], work / "start_crop.png")
        comfy.ensure()
        comfy.lock("face_pass", "comfy:ltx23")
        tag = re.sub(r"[^A-Za-z0-9_.-]", "_", f"face_{clip.stem}_{seed}")
        t0 = time.time()
        wf = workflow(comfy.upload(work / "crop.mp4", f"{tag}.mp4"), comfy.upload(work / "start_crop.png", f"{tag}.png"),
                      comfy.upload(meta["audio"], f"{tag}.wav"), len(frames), prompt or crop_prompt(meta),
                      ", ".join(x for x in (meta.get("negative"), NEG_EYES) if x), seed,
                      f"animation-studio/face_pass/{tag}")
        hist = comfy.run(wf, timeout=3600)
        fdir = work / "frames"
        comfy.fetch_frames(comfy.outputs(hist, "70"), fdir)
        comfy.frames_to_mp4(fdir, done, fps, crf=10)
        shutil.rmtree(fdir, ignore_errors=True)
        gpu = round(time.time() - t0)
    n = paste(clip, frames, t["rows"], read_frames(done), out, fps)
    sheet(frames, read_frames(out), t["rows"], out.with_suffix(".sheet.jpg"))
    shown = sum(weight(r["face"] * 1024 / t["W"]) > 0 for r in t["rows"][:n])
    meta.update(face_fix=dict(method="ltx23 ic-lora upscale x2 + start-face anchor", seed=seed, tracker=tracker, face=t["face"],
                              low=t["low"], frames=n, frames_changed=shown, fade=[SMALL, FADE_TO], gpu_s=gpu),
                face_fix_from=clip.name)
    clips.meta_path(out).write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    log(f"  {clip.name} -> {out.name}: face {t['low']:.0f}-{t['face']:.0f} px, {shown} of {n} frames changed, "
        + (f"{gpu} s GPU" if gpu else "pass reused (no GPU)"))
    return meta


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    m = sub.add_parser("measure")
    m.add_argument("clips", nargs="+")
    m.add_argument("--tracker", choices=TRACKERS + ("auto",), default="mediapipe")
    f = sub.add_parser("fix")
    f.add_argument("clip")
    f.add_argument("-o", "--out")
    f.add_argument("--hint", type=float, nargs=2, help="face position in the first frame (x y as 0-1)")
    f.add_argument("--seed", type=int, default=SEED)
    f.add_argument("--redo", action="store_true", help="generate the face again (else a kept pass is only re-blended)")
    f.add_argument("--tracker", choices=TRACKERS, default="mediapipe",
                   help="retinaface: CPU PyTorch tracker for tiny faces / profiles / crowds (face_track_retina.py)")
    a = ap.parse_args()
    if a.cmd == "measure":
        for c in a.clips:
            r, used = measure_auto(c, tracker=a.tracker)
            v = "no face" if r["face"] is None else (f"median {r['face']:5.0f} px, small part {r['low']:5.0f} px, "
                                                      f"{r['hits']}/{r.get('frames', '?')} frames, {used} ")
            print(f"{v:38s}{'far' if r['far'] else '':5s}{c}")
    else:
        fix(a.clip, a.out, a.hint, a.seed, a.redo, tracker=a.tracker)


if __name__ == "__main__":
    main()
