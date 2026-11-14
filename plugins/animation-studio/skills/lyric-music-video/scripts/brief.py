# /// script
# requires-python = ">=3.12"
# dependencies = []
# [tool.uv]
# exclude-newer = "2026-11-14T00:00:00Z"
# ///
"""Creative brief of a lyric video: the seed's dice, the visual identity and the scene ideas (project.json).

  uv run brief.py PROJECT                        show seed, dice, identity, ideas, past identities
  ... brief.py PROJECT --identity "risograph print shop: ..."         set the visual identity (2-3 lines)
  ... brief.py PROJECT --idea "waveform squeezed into a chip" --where "verse1:3" [--by user]
  ... brief.py PROJECT --status 4 done|dropped|planned                 update idea number 4
  ... brief.py PROJECT --reroll                                        new seed -> new dice (a different take)

The dice are seeded suggestions that push every video somewhere new: a lyric entrance, a cut style, a palette
strategy, a type pairing, a camera/space idea and an ending archetype. They are prompts, not rules - the user's
wishes and ideas that come from the lyrics always win (record user ideas with --by user).
Past identities (references/scene-catalog.md section 1) are listed so the new one differs from all of them.
"""
import argparse
import json
import random
import re
from pathlib import Path

import _studio  # noqa: E402
_studio.use("song-analysis")
import creative  # noqa: E402
from song_project import Project  # noqa: E402

CATALOG = Path(__file__).resolve().parents[1] / "references" / "scene-catalog.md"

DICE = {
    "lyric entrance": ["letters stamped like a press", "typewriter with caret", "letters slide up out of a mask line",
                       "ink bleeds into paper letter by letter", "split-flap letters settle on the word's onset",
                       "letters assemble from scattered particles", "neon tubes flicker on per letter",
                       "handwritten stroke draws each word (stroke-dash)", "words drop in on strings like a mobile",
                       "letters cut out of paper and glued on with a tiny shadow jump", "LED matrix dots light per letter",
                       "chalk letters scratched onto a board", "words projected and focus-pulled sharp"],
    "cut style": ["black dip + hit flash", "diagonal colour wipe", "hard cut with 0.16 s scale-in", "page turn",
                  "iris / circle wipe on the downbeat", "film-strip slide", "shutter blinds", "zoom through a letter",
                  "glitch slice", "ink splash wipe", "match cut on a shape"],
    "palette strategy": ["two colours + paper", "brand colours of the source material", "night + one neon accent",
                         "duotone photo look", "pastel + black ink", "monochrome + one signal colour",
                         "colours per section that evolve", "warm analogue (sepia, cream, rust)", "cold steel + gold"],
    "type pairing": ["condensed grotesk + elegant italic serif", "rounded geometric sans only", "monospace + display serif",
                     "hand lettering + clean sans", "slab serif posters", "wide extended sans + thin mono captions",
                     "blackletter accents + modern sans", "stencil + typewriter"],
    "space": ["flat 2D poster layouts", "three.js depth: words in a 3D space", "multiplane parallax layers",
              "one continuous camera move through a world", "UI / screens as the stage", "paper cut-out stage",
              "data-viz canvas (charts, maps, diagrams)", "isometric miniature world"],
    "ending": ["switch-off / power-down", "something closes (shutter, book, curtain, lid)", "a chain or picture completes",
               "the camera pulls back to reveal the whole", "the last word stays alone and burns in",
               "everything falls / collapses, one thing remains", "a stamp / signature seals it", "fade into a sunrise"],
}


def dice(P):
    return {k: creative.pick(P, f"dice:{k}", v) for k, v in DICE.items()}


def past_identities():
    if not CATALOG.exists():
        return []
    rows = []
    for line in CATALOG.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^\|\s*`([^`]+)`\s*\|[^|]*\|\s*(.+?)\s*\|$", line)
        if m:
            rows.append((m.group(1), m.group(2)[:150]))
    return rows


def main():
    ap = argparse.ArgumentParser(description="Creative brief: seed dice, identity, ideas.")
    ap.add_argument("project", nargs="?", default=".")
    ap.add_argument("--identity")
    ap.add_argument("--idea")
    ap.add_argument("--where", default="")
    ap.add_argument("--by", default="ai", choices=["ai", "user"])
    ap.add_argument("--status", nargs=2, metavar=("NR", "STATUS"))
    ap.add_argument("--reroll", action="store_true")
    a = ap.parse_args()
    P = Project(a.project)
    save = lambda: P.file.write_text(json.dumps(P.p, ensure_ascii=False, indent=1), encoding="utf-8")
    if a.reroll:
        P.p["seed"] = random.SystemRandom().randrange(100000)
        save()
    if a.identity:
        P.p["identity"] = a.identity
        save()
    if a.idea:
        creative.add_idea(P, a.by, a.idea, a.where)
    if a.status:
        P.p["ideas"][int(a.status[0]) - 1]["status"] = a.status[1]
        save()
    print(f"seed {creative.seed(P)}")
    print("dice (seeded suggestions - take, bend or overrule them):")
    for k, v in dice(P).items():
        print(f"  {k:16} {v}")
    print(f"identity: {P.get('identity') or '(not set yet - write 2-3 lines with --identity)'}")
    ideas = creative.ideas(P)
    print(f"ideas ({len(ideas)}):")
    for i, x in enumerate(ideas, 1):
        print(f"  {i:2}. [{x.get('status', 'planned'):7}] {x.get('by', 'ai'):4} {x.get('where', ''):12} {x['idea']}")
    print("past identities (do not repeat them):")
    for name, ident in past_identities():
        print(f"  {name:18} {ident}")


if __name__ == "__main__":
    main()
