# video-review – reference tests

Reference: the user's own V3 of the music video "Europe 2031" (Claudia, 62 shots, 197 s, 1280×720, 24 fps), cut
from V1 and V2 with a hand-made comparison page and `v3_schneiden.py` (frames via OpenCV, audio copied from V2).
Inputs: `claudia_europe2031.mp4` (V1), `claudia_europe2031_v2.mp4` (V2), the user's picks `auswahl_v3.json`
(44 picks, legacy format `{"wahl": {"3": 2}}`), shot list `planung/shots.json`; reference output
`claudia_europe2031_v3.mp4`. All read only; the test ran in a scratch folder.

## Rebuild

```
review.py init V1.mp4 V2.mp4 --labels V1 V2 --previews V1_small.mp4 V2_small.mp4 --audio v2 --default v2 \
          --shots planung/shots.json --name europe2031_v3.mp4 --out review/review.json        # 37 s
review.py cut review/review.json --choice vergleich/auswahl_v3.json                          # 64 s
```

## Results (2026-11-13)

| Check | Result |
|---|---|
| Shots per version | V1 28, V2 34 – same as the user's log ("Shots aus V1: 28, aus V2: 34") |
| Frames | 4729 = reference; source of every frame (V1 or V2, nearest by mean abs difference): 4727/4729 agree, the 2 others are frames 1–2 of a fade from black where V1 and V2 are equal |
| Picture vs. reference V3 | per-frame mean abs difference (RGB, 0–255): mean 2.37, median 2.37, max 2.93, 99th percentile 2.83; no frame above 3 |
| Where that difference comes from | the reference V3 itself is 2.25 away from its source frames and ~1.5 levels darker (RGB mean −1.56/−1.48/−1.93: OpenCV's BGR round trip); the plugin cut is 1.59 away from the sources with no shift (+0.06/+0.04/+0.10) – i.e. pure encoder noise, closer to V1/V2 than the reference |
| Audio | stream-copied: packet MD5 and decoded-PCM MD5 identical to the reference V3 (9237 AAC frames, 197.034 s) |
| Cut from the page (`POST /api/cut`) | video stream MD5 identical to the CLI cut |
| "only differing shots" | 16 shots marked identical by pixels (diff < 1.5); the user's page marked 18 by material name – shots 32 and 60 have the same material name but differ by 2.5–2.9 (re-placed lip sync), so the plugin shows them. None of the 44 picked shots is hidden |
| `--detect` (V1+V2+V3) | all 61 listed shot boundaries found (±5 frames), 5 extra splits (flashes/strobes inside two shots): recall 1.0, precision 0.92. First run had a split at frame 1 and lost a real cut 0.24 s after a flash → now no shot < 0.5 s, and of two close cuts the stronger wins |
| Browser (headless Edge via Playwright) | page loads 62 shots, 2 synced players (drift ≤ 0.03 s), keys 1/2 pick + auto-advance, ↑ goes back, Space plays/pauses, S switches sound, filter hides 16 / shows all, picks saved to choice.json, cut player shown |
| HTTP | Range 206 with Content-Range, suffix ranges, 404 for unknown ids/paths, 409 while a cut runs |
| Generality | 3 versions with different frame sizes (1280×720 + 960×540 scaled up), shots from a song project's sections, legacy index picks mixed with ids, `--small` → 28.0 MB |

Test scripts and numbers: `experiments/plugin-tests/video-review/` (`compare_v3.py`, `compare_v3.json`,
`compare_v3_src.json`, `detect_vs_shotlist.json`, `ui_test.py`, `review/ui.png`).
