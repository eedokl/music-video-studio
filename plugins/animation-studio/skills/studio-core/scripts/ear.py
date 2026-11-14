# /// script
# requires-python = ">=3.12"
# dependencies = []
# [tool.uv]
# exclude-newer = "2026-11-14T00:00:00Z"
# ///
"""Run earshot (the "ears" for an agent that cannot hear) with the configured launcher - no path to look up, and
on Windows through `cmd /d` so a broken cmd AutoRun registry entry does not print a warning on every call;
the configured ffmpeg goes on PATH (without it `sheet` draws no frames and `timeline` finds no picture cuts).

  python ear.py timeline film.mp4              listen through a film: events, sections, loudness, silences, cuts
  python ear.py sheet film.mp4 -o film_ear.png frames + spectrogram + events in one PNG (open it with Read)
  python ear.py ab a.mp4 b.mp4                 A/B the sound of two files
  python ear.py --help                         all earshot commands

earshot is optional (check_tools.py --setup finds it); without it this script says so and exits with 2.
"""
import subprocess
import sys

import config


def main():
    e = config.get("earshot")
    if not e:
        print("earshot is not configured (optional). Run check_tools.py --setup or set ANIMATION_STUDIO_EARSHOT.")
        sys.exit(2)
    config.setup_env()                                 # our ffmpeg on PATH: earshot reads the video frames with it
    r = subprocess.run(config.cmdline([e, *sys.argv[1:]]), capture_output=True, text=True, errors="replace")
    noise = ("AutoRun",)                               # cmd's AutoRun registry message, harmless
    for stream, text in ((sys.stdout, r.stdout), (sys.stderr, r.stderr)):
        stream.write("".join(l for l in text.splitlines(True) if not any(n in l for n in noise)))
    sys.exit(r.returncode)


if __name__ == "__main__":
    main()
