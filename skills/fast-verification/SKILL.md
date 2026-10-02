---
name: fast-verification
description: Make a slow check (scorer, eval, benchmark, test suite, backtest) fast without changing its answer, and turn "is the candidate better?" into a mechanical ACCEPT / REJECT / UNSURE verdict. Use when an agent loop re-runs the same expensive check many times, when a check takes minutes and most inputs did not change, or when keep/reject decisions are being argued round after round. Ships two stdlib-only files (fastgate.py for unittest or pytest suites, fastcheck_template.py for any other scorer), both with a content-hash cache, parallel workers and a paired grouped-bootstrap gate.
---

# Fast verification

Goal: the same numbers as the slow check, in seconds, and a keep/reject rule no one
has to argue about. In the project this came from, a full check went from 77 to 170 s
to 9 s cold and 0.9 s cached, with every output field identical.

Files: https://github.com/naidx0/fast-verification-kit (MIT).

## If the slow check is a test suite: fastgate.py

Copy `fastgate.py` to the repo root. Nothing to fill in.

1. `python fastgate.py equal` (add `--runner pytest` for pytest, `--tests DIR` if the
   tests are not in `tests/`). It runs the serial suite and fastgate on the same tree
   and diffs every test's verdict. Adopt only on `"verdict": "EXACT"`.
2. `python fastgate.py run` as the gate from then on. Exit code 0 means PASS.
   Unchanged tree: verdicts come from the cache. One test file edited: only that file
   reruns. Any other file edited: everything reruns.
3. Name inputs the tree hash cannot see: `--env VAR` for env vars that change results,
   `--exclude runs/` for outputs the tests never read, `--serial "tests/test_docker*"`
   for files that share a Docker daemon or a fixed port.
4. `python fastgate.py ab BASE.json CAND.json --group-by KEY` for keep/reject calls on
   per-item scores (`{item: {"score": x, KEY: group}}`).

Measured on four repos, every kept setup gave the same verdict on every test as the
serial run (304 to 354 tests each). A rerun with nothing changed took 0.02 to 1.7 s
instead of minutes; fresh runs were 1.1x to 1.8x faster on a loaded Windows machine.
Profile first: in one suite half the time was test servers idling, and removing that
beat parallelism.

For anything else (a scorer, eval, benchmark or backtest), use the procedure below.

## Procedure

1. **Measure where the time goes before changing anything.** Profile one slow run.
   Look for work that is computed and then thrown away. The original case padded every
   rollout to 4000 steps and scored only the first 32 to 128: 97 to 99% of the time was
   waste. Write the number down; it is the baseline you must match.

2. **Freeze the reference.** Save the slow checker's full output for every subject.
   Every speedup below must reproduce it field for field. "Close" is not good enough:
   a fast check that disagrees is a different check.

3. **Copy `fastcheck_template.py` into the repo** (next to the existing scorer) and fill
   in only the ADAPTER section:
   - `subjects()`: independent units (systems, datasets, tasks).
   - `candidate_files()` and `GLOBAL_INPUTS`: **everything** the result reads. The cache
     key is a hash of these plus the checker file itself. Forget one and the cache serves
     stale results.
   - `static_check()`: millisecond checks that can only reject (imports, signatures,
     required files).
   - `guard()`: prove an exact shortcut on a few probes, return False to fall back.
   - `score()`: call the existing scorer. Return the metric plus `per_unit` scores and
     `groups` (units that share a cause: same schedule, user, file, seed).
   - `extra()`: slow checks that only matter once the score passed.
   Run `python fastcheck_template.py selftest` in a scratch copy first to see it work.

4. **Prove equality.** Run the old and new checkers on every subject and diff every
   field. Only then point the loop at the new one.

5. **Use `compare` as the gate.** `compare --cand NEW --base OLD` averages per-unit deltas
   within each group, bootstraps over groups, and returns ACCEPT only when the lower 90%
   bound is above zero. The baseline is cached by hash, so each comparison runs only the
   candidate.

## Rules that carry over

- **Exact shortcuts need a proof, not an assumption.** Check the shortcut against the
  slow path on probes every run (the hash changes when the code does) and fall back when
  it fails. Never ship an approximation as the default path.
- **Cheap tiers may only reject.** A fast approximate screen (jackknife, subsample, lint)
  is for throwing out candidates far behind. In the source project a one-step jackknife
  was 130x cheaper but ranked eight variants with a correlation of only 0.28. It never
  accepts anything.
- **Decide on held-out data, never in-sample.** In-sample tail score ranked candidates
  backwards (rank correlation −0.33 with held-out). If `score()` can only see in-sample
  predictions, the gate is not a gate yet: feed it held-out predictions first.
- **Pair and group.** Compare candidate and baseline on the same units, and treat
  correlated units as one group. Otherwise one lucky schedule carries a "win".
- **Cache failures too.** Same input, same failure. It stops a loop re-running a broken
  candidate.
- **Parallelise independent units** with processes, one per subject or fold. Set
  `OMP_NUM_THREADS=1` per worker if the scorer uses numpy/BLAS, or workers fight for cores.
- **Seal a holdout when the loop runs for long.** Hundreds of tries against the same 10
  to 30 groups fit the held-out set too. Keep two or three groups unread until a
  checkpoint (a release, an upload).
- **Save the real judge for the end.** Whatever the true ground truth is (a leaderboard,
  production, a user) comes last and only for batches that passed every rung.

## Optional: ledger, fingerprints, receipts

When many candidates behave identically (refactors, comment edits, no-op tweaks):
- **Behaviour fingerprint:** run the candidate on a fixed set of probe inputs, round the
  outputs to a fraction of the noise level, hash them. Same fingerprint means the same
  behaviour on the probes, so reuse the earlier result. Nearest fingerprint distance
  flags a change that did almost nothing. In the source project 47 of 70 historical
  versions reused an earlier result. Probes are not all inputs: a fingerprint match is
  good for screening, rerun the full check on the exact code before shipping.
- **Receipts:** store each result with the hashes of what it read. A reviewer recomputes
  the hashes and re-runs one randomly chosen node instead of the whole check. An edited
  receipt or an edited input is refused.

## Pitfalls

- A cache key that misses an input (a config, an env var, a random seed, the scorer's
  own helper module) silently serves stale results. Hash the checker files too.
- Hashing file paths as absolute strings breaks the cache across worktrees. Hash
  relative paths (the template does).
- A fast check "passing" only proves what it reads. Name what it reads before saying
  what it proves.
- Process pools on Windows need the `if __name__ == "__main__":` guard and picklable
  top-level functions (the template has both).
- Wall-clock numbers taken while another job runs are noisy; accuracy comparisons are not.
