"""Keep the computer awake while a long job runs (renders, video models): it must not fall asleep after the idle
time of the power plan and stop the job half way.

    from awake import awake
    with awake("rendering the film"):
        ...

or hold() / free(). gpu_lock.acquire() holds it by itself until the lock is released (so every GPU job - Blender,
ComfyUI, LTX - keeps the machine awake while it runs); stage_run.py film holds it for the whole film.
Windows: SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED) - the system stays on, the screen may still
turn off; ends with free() or when the process dies. macOS: `caffeinate -i -w <pid>`. Linux: `systemd-inhibit`
when it is there. Elsewhere nothing. The config key `awake` = 0 (env ANIMATION_STUDIO_AWAKE=0) turns it off.
Closing the lid or the power button still put the machine to sleep.
"""
import contextlib
import os
import shutil
import subprocess
import sys

ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001
_state = {"depth": 0, "held": False, "proc": None}


def _off():
    try:
        import config
        v = config.get("awake")
    except Exception:
        v = os.environ.get("ANIMATION_STUDIO_AWAKE")
    return str(v or "1").strip().lower() in ("0", "no", "false", "off")


def hold(why="a long job"):
    """the machine does not go to idle sleep until free() (calls nest: the last free() lets it sleep again)"""
    _state["depth"] += 1
    if _state["depth"] > 1 or _off():
        return
    try:
        if sys.platform == "win32":
            import ctypes
            _state["held"] = bool(ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED))
        elif sys.platform == "darwin" and shutil.which("caffeinate"):
            _state["proc"] = subprocess.Popen(["caffeinate", "-i", "-w", str(os.getpid())])
        elif shutil.which("systemd-inhibit"):
            _state["proc"] = subprocess.Popen(
                ["systemd-inhibit", "--what=idle:sleep", f"--why={why}", "--mode=block", "sleep", "infinity"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:                                  # never let this stop the job itself
        _state["held"], _state["proc"] = False, None
    if _state["held"] or _state["proc"]:
        print(f"AWAKE the computer stays awake while {why}", file=sys.stderr, flush=True)


def free():
    if _state["depth"] == 0:
        return
    _state["depth"] -= 1
    if _state["depth"]:
        return
    if _state["held"]:
        try:
            import ctypes
            ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS)
        except Exception:
            pass
    if _state["proc"]:
        _state["proc"].terminate()
    _state["held"], _state["proc"] = False, None


def holding():
    return bool(_state["held"] or _state["proc"])


@contextlib.contextmanager
def awake(why="a long job"):
    hold(why)
    try:
        yield
    finally:
        free()
