"""Unicode-safe OpenCV file access. cv2.imread / cv2.imwrite / cv2.VideoCapture take narrow (ANSI) paths on Windows and
fail SILENTLY on names like "Frühling" (imread returns None, VideoCapture opens nothing). Use these instead:

    import _studio; _studio.use("ai-video")
    from cvio import imread, imwrite, video_capture
    bgr = imread(path)                          # None when the file is missing or unreadable (like cv2.imread)
    imwrite(path, img)                          # raises OSError when it cannot write
    cap = video_capture(path)                   # cv2.VideoCapture; non-ASCII paths via the Windows short name or a temp copy

Images go through numpy (np.fromfile + cv2.imdecode, cv2.imencode + tofile), which takes any path.
Videos: OpenCV has no in-memory video decoder. A non-ASCII path that cv2.VideoCapture cannot open (older builds /
other backends; the current opencv-python FFmpeg backend opens it) is opened through its Windows 8.3 short name
(GetShortPathNameW) and, when the volume has no short names, through a temporary ASCII-named copy (deleted at exit).
"""
import atexit
import os
import shutil
import tempfile
from pathlib import Path

import numpy as np

_tmp_dir = None


def imread(path, flags=None):
    import cv2
    try:
        data = np.fromfile(str(path), dtype=np.uint8)
    except OSError:
        return None
    if data.size == 0:
        return None
    return cv2.imdecode(data, cv2.IMREAD_COLOR if flags is None else flags)


def imwrite(path, img, params=None):
    import cv2
    path = Path(path)
    ok, buf = cv2.imencode(path.suffix or ".png", img, params or [])
    if not ok:
        raise OSError(f"cannot encode {path.name}")
    buf.tofile(str(path))
    return True


def _ascii(s):
    try:
        s.encode("ascii")
        return True
    except UnicodeEncodeError:
        return False


def ascii_path(path):
    """A path OpenCV's video backends can open: the path itself, the Windows short name, or a temporary copy."""
    p = str(path)
    if os.name != "nt" or _ascii(p) or not Path(p).exists():
        return p
    try:
        import ctypes
        buf = ctypes.create_unicode_buffer(32768)
        if ctypes.windll.kernel32.GetShortPathNameW(p, buf, len(buf)) and _ascii(buf.value):
            return buf.value
    except Exception:
        pass
    global _tmp_dir
    if _tmp_dir is None:
        _tmp_dir = tempfile.mkdtemp(prefix="cvio_")
        atexit.register(shutil.rmtree, _tmp_dir, True)
    q = Path(_tmp_dir) / f"v{len(os.listdir(_tmp_dir)):04d}{Path(p).suffix}"
    shutil.copyfile(p, q)
    if not _ascii(str(q)):
        print(f"[cvio] warning: no ASCII path for {Path(p).name} (temp folder {_tmp_dir} is not ASCII either)")
    return str(q)


def video_capture(path):
    """cv2.VideoCapture that also opens non-ASCII paths (recent OpenCV FFmpeg builds can; older ones fail silently)."""
    import cv2
    cap = cv2.VideoCapture(str(path))
    if cap.isOpened() or _ascii(str(path)):
        return cap
    return cv2.VideoCapture(ascii_path(path))
