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
import os
import random
import time


def _data(P):
    return P.p if hasattr(P, "p") else P


def _update_file(P, change):
    """Apply change(dict) to project.json as it is on disk NOW (not the whole in-memory copy: another step may
    have changed other keys since P was loaded) and write it atomically. Returns the disk dict (None: no file)."""
    f = getattr(P, "file", None)
    if f is None:
        return None
    try:
        disk = json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
    except ValueError:
        raise SystemExit(f"{f} is not valid JSON - fix it before the seed / ideas can be stored")
    change(disk)
    tmp = f.with_name(f.name + ".tmp")
    tmp.write_text(json.dumps(disk, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, f)
    return disk


def seed(P):
    d = _data(P)
    if "seed" not in d:
        if hasattr(P, "file"):
            new = int(time.time()) % 100000
            disk = _update_file(P, lambda j: j.setdefault("seed", new))
            d["seed"] = disk.get("seed", new)          # another step may have stored one meanwhile
        else:
            # plain dict: nothing to store it in - a time-based seed would give a new take on every run, so derive
            # a stable one from the name; put "seed" into the JSON yourself for another take
            d["seed"] = int(hashlib.sha256(str(d.get("name", "")).encode()).hexdigest()[:8], 16) % 100000
            print(f"   creative: no \"seed\" in this config - using {d['seed']} (add \"seed\" to its JSON for another take)")
    return int(d["seed"])


def rng(P, salt=""):
    h = hashlib.sha256(f"{seed(P)}:{salt}".encode()).hexdigest()
    return random.Random(int(h[:16], 16))


def pick(P, salt, options):
    return rng(P, salt).choice(list(options))


def add_idea(P, by, idea, where="", status="planned"):
    d = _data(P)
    entry = {"by": by, "idea": idea, "where": where, "status": status}
    d.setdefault("ideas", []).append(entry)
    _update_file(P, lambda j: j.setdefault("ideas", []).append(entry))


def ideas(P, where=None):
    return [i for i in _data(P).get("ideas", []) if where is None or i.get("where") in (where, "", "all")]
