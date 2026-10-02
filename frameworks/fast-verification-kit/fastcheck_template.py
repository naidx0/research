"""Portable fast checker: cached, tiered, parallel, with a paired keep/reject gate.

Copy this file into your repo, then edit only the ADAPTER section. Everything
below it is generic. Standard library only.

  python fastcheck_template.py check                      # every subject, default candidate
  python fastcheck_template.py check A B --cand DIR       # some subjects, a candidate
  python fastcheck_template.py compare A --cand DIR --base DIR
      paired comparison: per-group delta, bootstrap 90% interval,
      ACCEPT only when the lower bound is above 0
  python fastcheck_template.py selftest                   # runs on the toy adapter
  add --fresh to ignore the cache, --jobs N for parallelism

Tiers run in order and each runs only if the one before passed:
  0 static   cheap structural checks (imports, signatures, files present)
  1 guard    prove an exact shortcut holds on a few probes; fall back if not
  2 score    the real metric, plus per-unit scores and group ids for pairing
  3 extra    slow checks (long runs, stability); skipped if score failed

Every result is cached under CACHE keyed by a hash of everything it read:
the candidate's files, the data, the scorer, and this file. An unchanged
candidate costs one hash. Edit any input and the key changes by itself.
"""
import argparse
import hashlib
import json
import random
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent

# ============================ ADAPTER: edit this section ============================
# The toy below scores a "model" (a JSON file with a slope) against synthetic data,
# so selftest runs anywhere. Replace each function with your project's real code.

CACHE = HERE / ".fastcheck"
# Files whose change must invalidate every cached result: scorer, data, configs.
# This file is added automatically.
GLOBAL_INPUTS = []


def subjects():
    """Independent units to check (systems, tasks, datasets, packages)."""
    return ["toy_a", "toy_b"]


def default_candidate(subject):
    return HERE / ".toy" / subject / "current"


def candidate_files(subject, cand):
    """Every file the result depends on for this candidate. Hashed into the cache key."""
    return sorted(p for p in Path(cand).rglob("*") if p.is_file() and "__pycache__" not in p.parts)


def static_check(subject, cand):
    """Tier 0. Milliseconds. Return {"ok": bool, ...details}."""
    ok = (Path(cand) / "model.json").exists()
    return {"ok": ok, "why": None if ok else "model.json missing"}


def guard(subject, cand):
    """Tier 1. Prove the fast path gives the same answer as the slow one on a few
    probes. Return True to use the fast path, False to fall back. If you have no
    shortcut, return False."""
    return True


def score(subject, cand, fast):
    """Tier 2. Return {"metric": float (higher is better), "per_unit": [float],
    "groups": [hashable]}. per_unit and groups line up; units in the same group
    are correlated (same schedule, same user, same file) and are averaged before
    the bootstrap so they are not counted as independent evidence."""
    slope = json.loads((Path(cand) / "model.json").read_text())["slope"]
    rng = random.Random(subject)
    per_unit, groups = [], []
    for i in range(24):
        x = rng.uniform(0, 10)
        y = 2.0 * x + rng.gauss(0, 1)
        per_unit.append(1 / (1 + abs(slope * x - y)))
        groups.append(i // 3)
    return {"metric": sum(per_unit) / len(per_unit), "per_unit": per_unit, "groups": groups}


def extra(subject, cand):
    """Tier 3. Slow checks. Return {"ok": bool, ...}."""
    slope = json.loads((Path(cand) / "model.json").read_text())["slope"]
    return {"ok": abs(slope) < 100}

# ========================== end of ADAPTER ==========================================


def digest(subject, cand):
    h = hashlib.sha256()
    for p in candidate_files(subject, cand):
        h.update(str(p.relative_to(cand)).replace("\\", "/").encode())
        h.update(p.read_bytes())
    for p in [Path(__file__), *map(Path, GLOBAL_INPUTS)]:
        h.update(p.read_bytes())
    h.update(subject.encode())
    return h.hexdigest()[:20]


def evaluate(subject, cand, fresh=False):
    cand = Path(cand)
    key = digest(subject, cand)
    path = CACHE / f"{subject}-{key}.json"
    if path.exists() and not fresh:
        r = json.loads(path.read_text())
        r["cached"] = True
        return r
    t0 = time.time()
    r = {"subject": subject, "key": key, "static": static_check(subject, cand)}
    if r["static"]["ok"]:
        r["fast"] = bool(guard(subject, cand))
        r.update(score(subject, cand, r["fast"]))
        r["extra"] = extra(subject, cand)
        r["ok"] = bool(r["extra"]["ok"])
    else:
        r["ok"] = False
    r["sec"] = round(time.time() - t0, 3)
    CACHE.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(r))  # failures are cached too: same input, same failure
    r["cached"] = False
    return r


def paired(cand, base, n_boot=4000, seed=0):
    """Mean over groups of (candidate - baseline), bootstrap 90% interval over groups."""
    if cand["groups"] != base["groups"]:
        raise ValueError("candidate and baseline were scored on different units")
    by = {}
    for g, c, b in zip(cand["groups"], cand["per_unit"], base["per_unit"]):
        by.setdefault(g, []).append(c - b)
    dg = [sum(v) / len(v) for v in by.values()]
    rng = random.Random(seed)
    boot = sorted(sum(rng.choice(dg) for _ in dg) / len(dg) for _ in range(n_boot))
    lo, hi = boot[int(0.05 * n_boot)], boot[int(0.95 * n_boot) - 1]
    verdict = "ACCEPT" if lo > 0 and cand["ok"] else "REJECT" if hi < 0 or not cand["ok"] else "UNSURE"
    return {"delta": round(sum(dg) / len(dg), 5), "ci90": [round(lo, 5), round(hi, 5)],
            "wins": sum(d > 0 for d in dg), "losses": sum(d < 0 for d in dg),
            "groups": len(dg), "verdict": verdict}


def run(jobs, n, fresh):
    if n <= 1 or len(jobs) <= 1:
        return [evaluate(s, c, fresh) for s, c in jobs]
    with ProcessPoolExecutor(min(n, len(jobs))) as ex:
        return list(ex.map(evaluate, *zip(*jobs), [fresh] * len(jobs)))


def slim(r):
    return {k: v for k, v in r.items() if k not in ("per_unit", "groups")}


def selftest():
    import shutil
    root = HERE / ".toy"
    shutil.rmtree(root, ignore_errors=True)
    shutil.rmtree(CACHE, ignore_errors=True)
    for s in subjects():
        for name, slope in (("current", 1.8), ("better", 2.0), ("worse", 1.0)):
            (root / s / name).mkdir(parents=True)
            (root / s / name / "model.json").write_text(json.dumps({"slope": slope}))
    s = subjects()[0]
    cur, better, worse = (root / s / n for n in ("current", "better", "worse"))
    first = evaluate(s, cur)
    again = evaluate(s, cur)
    assert not first["cached"] and again["cached"] and again["metric"] == first["metric"], "cache"
    assert paired(evaluate(s, better), first)["verdict"] == "ACCEPT", "better must be accepted"
    assert paired(evaluate(s, worse), first)["verdict"] == "REJECT", "worse must be rejected"
    assert paired(first, first)["verdict"] == "UNSURE", "identical must be unsure"
    (cur / "model.json").write_text(json.dumps({"slope": 1.8, "note": "edit"}))
    assert not evaluate(s, cur)["cached"], "an edit must invalidate the cache"
    (worse / "model.json").unlink()
    assert evaluate(s, worse)["ok"] is False, "static tier must stop a broken candidate"
    print("selftest ok")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["check", "compare", "selftest"])
    ap.add_argument("subjects", nargs="*")
    ap.add_argument("--cand")
    ap.add_argument("--base")
    ap.add_argument("--jobs", type=int, default=8)
    ap.add_argument("--fresh", action="store_true")
    a = ap.parse_intermixed_args()
    if a.cmd == "selftest":
        return selftest()
    subs = a.subjects or subjects()
    jobs = [(s, a.cand or default_candidate(s)) for s in subs]
    if a.cmd == "compare":
        if not a.base:
            ap.error("compare needs --base")
        jobs += [(s, a.base) for s in subs]
    res = run(jobs, a.jobs, a.fresh)
    for i, r in enumerate(res[:len(subs)]):
        out = slim(r)
        if a.cmd == "compare":
            b = res[len(subs) + i]
            out["paired"] = paired(r, b) if r["ok"] and b.get("per_unit") else {"verdict": "REJECT"}
        print(json.dumps(out), flush=True)


if __name__ == "__main__":
    main()
