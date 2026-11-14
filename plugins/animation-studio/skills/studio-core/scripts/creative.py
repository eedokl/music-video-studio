"""Creative seed: variation that is reproducible, plus a log of the ideas a film is built on.

Every project.json carries
  "seed": 4711                                   same seed -> same film; a new seed -> a different take
  "ideas": [{"by": "user"|"ai", "idea": "coins rain on the screen at 'Tokens'", "where": "chorus", "status": "planned|done|dropped"}]
Scripts never use `random` directly: they ask `rng(P, "what-for")`, a generator derived from the seed and a salt,
so changing one decision (e.g. the dance style of one figure) does not reshuffle all the others.
Skills must not hard-code one look or one routine: offer several variants and pick with the seed unless the user
or an idea fixes the choice.

    import creative
    seed = creative.seed(P)                          # reads project.json, creates and stores a seed if missing
    r = creative.rng(P, "dance:tim:chorus")          # random.Random
    style = creative.pick(P, "dance:tim", ["bounce", "step", "twist"])
    creative.add_idea(P, "ai", "Tim hides behind the desk at 'Limit'", "verse1")
"""
import hashlib
import json
import random
import time


def _data(P):
    return P.p if hasattr(P, "p") else P


def _save(P):
    if hasattr(P, "file"):
        P.file.write_text(json.dumps(P.p, ensure_ascii=False, indent=1), encoding="utf-8")


def seed(P):
    d = _data(P)
    if "seed" not in d:
        d["seed"] = int(time.time()) % 100000
        _save(P)
    return int(d["seed"])


def rng(P, salt=""):
    h = hashlib.sha256(f"{seed(P)}:{salt}".encode()).hexdigest()
    return random.Random(int(h[:16], 16))


def pick(P, salt, options):
    return rng(P, salt).choice(list(options))


def add_idea(P, by, idea, where="", status="planned"):
    d = _data(P)
    d.setdefault("ideas", []).append({"by": by, "idea": idea, "where": where, "status": status})
    _save(P)


def ideas(P, where=None):
    return [i for i in _data(P).get("ideas", []) if where is None or i.get("where") in (where, "", "all")]
