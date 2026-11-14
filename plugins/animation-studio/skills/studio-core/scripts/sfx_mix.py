"""Shared sound-effect mixer on top of the earshot sound bank - used by film-finish sounds.py (song films),
animated-short sfx_track.py (frame cues) and animated-powerpoint sound.py (clips with narration).

    from sfx_mix import SfxMix
    mix = SfxMix(seconds=12.5, cache="cache/sfx_bank")          # earshot from config.py (key "earshot")
    mix.sfx(2.0, "ui_pop/step", args=["--pitch", "D4"], db=-11, pan=-0.3, align="peak")
    mix.voice("line01.wav", 3.2, db=-14)                        # a narration line, starting at 3.2 s
    mix.write("sounds.wav", lowpass=6000)                       # or loudnorm=-18 for speech

- Each sound is rendered once per id + args into the cache (earshot `sfx render`), normalised to peak 1, given 10 ms
  fades ("soft": hard unfiltered clicks over music read as a broken speaker) and placed with its START (align="start")
  or its LOUDEST MOMENT (align="peak": a landing pop sits on the contact frame) on the given second, at `db` peak level.
- pan -1..1; pan_law "linear" (each side min(1, 1 -/+ pan)) or "equal" (sqrt, +3 dB centre - the song films).
- Cache: config key "sfx_cache" (check_tools.py --set sfx_cache=<dir>) = one shared bank for every project and clip;
  otherwise the caller's folder.
- Without earshot every sfx() call is skipped (`mix.ear` is None, `mix.missing` lists what could not be rendered),
  voices are still mixed.
- write(): peak-limits to `limit` (0.89), optional low-pass and loudness normalisation, 48 kHz stereo 16-bit WAV.
"""
import subprocess
import tempfile
from pathlib import Path

import numpy as np

import config
from media import decode

SR = 48000


def earshot_launch():
    """Command prefix for earshot, or None if it is not configured."""
    e = config.get("earshot")
    if not e:
        return None
    return [e]                                         # run through config.cmdline (.cmd launchers)


def fade(y, ms=10, fade_in=True, fade_out=True):
    k = min(max(1, int(ms / 1000 * SR)), len(y) // 2)
    if k:
        r = np.linspace(0, 1, k, dtype=np.float32)[:, None] if y.ndim == 2 else np.linspace(0, 1, k, dtype=np.float32)
        if fade_in:
            y[:k] *= r
        if fade_out:
            y[-k:] *= r[::-1]
    return y


class SfxMix:
    def __init__(self, seconds, cache=None, pan_law="linear", tail=2.0, names="short"):
        self.n = int(round(seconds * SR))
        self.buf = np.zeros((self.n + int(tail * SR), 2), np.float32)
        shared = config.get("sfx_cache")                # one bank for all projects/clips (earshot renders are fixed
        self.cache = Path(shared) if shared else Path(cache) if cache else Path(tempfile.mkdtemp(prefix="sfx_bank_"))
        self.names = names                              # per id + args); else the caller's folder / a temp folder
        self.pan_law = pan_law
        self.ear = earshot_launch()
        self.count, self.missing, self.log = 0, [], []
        self._mem = {}

    # ---------- sounds ----------
    def render(self, sid, args=(), stereo=False, lowpass_each=None, soft=True):
        """Rendered sound (n, 2) float32 normalised to peak 1 with soft fades, or None (no earshot / unknown id).
        args = extra earshot arguments ("--dur", "0.32", "--pitch", "G5", ...). stereo=True keeps earshot's stereo
        image; lowpass_each filters this one sound (animated-short), otherwise filter the whole mix in write()."""
        key = (sid, tuple(args), stereo, lowpass_each, soft)
        if key in self._mem:
            return self._mem[key]
        if not self.ear:
            self.missing.append(sid)
            return None
        self.cache.mkdir(parents=True, exist_ok=True)
        args = [str(x) for x in args]
        if self.names == "short" and len(args) == 2 and args[0] == "--dur":
            tag = f"_d{args[1]}"                       # same file names as before the shared mixer (cache reuse)
        else:
            tag = "".join("_" + x.replace(".", "").replace("-", "") for x in args)
        wav = self.cache / (sid.replace("/", "__") + tag + ".wav")
        if not wav.exists():
            subprocess.run(config.cmdline(self.ear + ["sfx", "render", sid, "-o", str(wav), "--sr", str(SR)] + args),
                           capture_output=True, text=True, errors="replace")
        if not wav.exists():
            print(f"  sound '{sid}' not found - skipped (earshot sfx list)")
            self.missing.append(sid)
            self._mem[key] = None
            return None
        if stereo or lowpass_each:
            af = (f"lowpass=f={lowpass_each}," if lowpass_each else "") + "anull"
            raw = subprocess.run([config.need("ffmpeg"), "-v", "error", "-i", str(wav), "-af", af, "-ac", "2", "-ar",
                                  str(SR), "-f", "f32le", "-"], capture_output=True, check=True).stdout
            y = np.frombuffer(raw, np.float32).reshape(-1, 2).copy()
        else:
            y = np.repeat(decode(wav, SR)[:, None], 2, axis=1)
        if soft:
            y = fade(y)
        y /= (np.abs(y).max() + 1e-9)
        self._mem[key] = y
        return y

    def place(self, y, t, db=-14.0, pan=0.0, align="start"):
        """Add a (n, 2) signal at second t with its peak at db; align 'start' or 'peak'. Returns the start sample."""
        peak = int(np.argmax(np.abs(y).max(axis=1))) if align == "peak" else 0
        start = int(t * SR) - peak
        g = 10 ** (db / 20) / (np.abs(y).max() + 1e-9)
        if self.pan_law == "equal":
            lr = np.array([np.sqrt((1 - pan) / 2), np.sqrt((1 + pan) / 2)], np.float32) * 1.41
        else:
            lr = np.array([min(1, 1 - pan), min(1, 1 + pan)], np.float32)
        s0 = max(start, 0)
        seg = (y * g * lr)[s0 - start:][: len(self.buf) - s0]
        if len(seg) > 0:
            self.buf[s0:s0 + len(seg)] += seg
        return start

    def sfx(self, t, sid, args=(), db=-20.0, pan=0.0, align="peak", stereo=False, lowpass_each=None, soft=True, what=""):
        y = self.render(sid, args, stereo=stereo, lowpass_each=lowpass_each, soft=soft)
        if y is None:
            return False
        if not -len(y) / SR < t < len(self.buf) / SR:
            return False
        start = self.place(y, t, db, pan, align)
        self.count += 1
        self.log.append({"t": round(t, 3), "sfx": sid, "db": db, "pan": pan,
                         "peak_ms": round((int(t * SR) - start) / SR * 1000, 1), "what": what})
        return True

    def voice(self, path, t, db=-14.0, pan=0.0):
        y = fade(np.repeat(decode(path, SR)[:, None], 2, axis=1))
        self.place(y, t, db, pan, "start")

    # ---------- output ----------
    def write(self, wav, lowpass=None, loudnorm=None, limit=0.89, seconds=None):
        n = self.n if seconds is None else int(round(seconds * SR))
        mix = self.buf[:n].copy()
        if len(mix) < n:
            mix = np.concatenate([mix, np.zeros((n - len(mix), 2), np.float32)])
        peak = float(np.abs(mix).max()) if len(mix) else 0.0
        if peak > limit:
            mix *= limit / peak
        af = []
        if lowpass:
            af.append(f"lowpass=f={lowpass}")
        if loudnorm is not None:
            af.append(f"loudnorm=I={loudnorm}:TP=-1.5:LRA=14")
        cmd = [config.need("ffmpeg"), "-y", "-v", "error", "-f", "f32le", "-ar", str(SR), "-ac", "2", "-i", "-"]
        cmd += (["-af", ",".join(af)] if af else []) + ["-ar", str(SR), "-c:a", "pcm_s16le", str(wav)]
        p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
        p.communicate(mix.astype(np.float32).tobytes())
        return Path(wav)
