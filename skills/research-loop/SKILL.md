---
name: research-loop
description: Run measured research on any goal with a number attached (accuracy, loss, latency, pass rate, answer quality). Each change is pre-registered with a win condition, tested against a sealed baseline with the same rows, seeds and budget, and then kept or reverted by a mechanical rule. The loop also generates ideas by running blind proposers against each other and having cheap models pitch ideas that a stronger writer codes. Use when someone says "improve X", "try ideas for X", "run experiments", "autoresearch", or wants a lane that keeps getting better without arguing about what counts as a win. Ships one stdlib-only helper, scripts/arloop.py.
---

# Autoresearch loop

Goal: every change is a measured experiment, and a result counts only if it beats a sealed baseline
by more than the noise. A discard is a result: log it so nobody retries it.

Helper: `scripts/arloop.py` (Python 3.8+, no dependencies). Run `python arloop.py selftest` once.
It must print PASS. Everything below writes to `research/` (log.md, handoff.md, ledger.jsonl).

## 0. Set up (once per project)

1. Ask for, or infer and state: the **goal**, the **metric**, its **direction** (higher or lower
   is better), and the **budget per run** (steps, tokens, seconds or dollars). Never spend money or
   post anything outside the project without the owner's yes.
2. `python arloop.py init`.
3. Split the data three ways: **train**, **select** (tune and screen on it freely) and **sealed**
   (opened only to decide a pre-registered hypothesis). Split by a hash of the item, so near copies
   never straddle splits. `python arloop.py seal --rows <sealed file>` and log the hash.
4. Write one scorer command that takes a candidate, seed and budget and prints the score as its
   last number: `score {cand} {seed} {steps}`. Give it a positive and a negative control: a planted
   good and a planted bad candidate must score as expected before you trust it.
5. **Measure the noise floor.** Run the baseline on 5 seeds, then run the same seeds again. If the
   same seed does not reproduce (GPUs often do not), compare means with the unpaired SE and never
   pair by seed. Log the floor. Any gap below it is noise, whatever a single run says.

## 1. The loop (repeat until the goal is met)

1. **Pick one hypothesis** and write the win before running anything:
   `python arloop.py prereg --id H7 --hypothesis "..." --win "new beats base by > 2 SE on sealed, seeds 0-4, same budget"`.
   Use `above2se` to claim better, and `within2se` for "as good, but cheaper or simpler".
2. **Build the smallest version** that tests it. Change one thing.
3. **Screen on select**, not sealed. Short runs kill bad ideas cheaply, but check that they
   predict the full budget: a learning-rate schedule compressed to a short run can rank ideas
   differently.
4. **Measure on sealed**: same rows, same seeds (5 or more), same budget, same device, and
   the baseline rerun in the same stage when the hardware drifts. Save per-seed scores as JSON
   (`{"0": 0.91, "1": 0.88}`).
5. **Decide**: `python arloop.py verdict --id H7 --base base.json --new new.json`. It logs baseline,
   new, delta, n, SE and t, and exits 0 only on KEEP. Keep only on KEEP. Otherwise revert the change
   completely.
6. **Log and hand off.** The verdict line is already in log.md. Add one line saying why it probably
   won or lost. Put what is kept, what is discarded, what is running (with the exact command) and
   what comes next at the top of handoff.md.
7. **Commit** code, results and log together, and name the hypothesis in the message. Then pick
   the next hypothesis.

A result that exists only in chat is lost. Put every number in log.md.

## 2. Generating ideas (when the obvious knobs are spent)

- **Blind competing proposers.** Give 2 or 3 strong agents the same task folder: the README with
  the rules and budget, the harness, the baseline, and nothing else. No logs, no earlier winners.
  Each works in its own folder, screens on select within a step budget recorded in a ledger, and
  submits one file with notes. The judge scores all submissions on sealed in one stage. Convergent
  inventions from independent proposers are strong evidence the idea is real.
- **Cheap pitches, strong writer.** Small local models write broken code, but their word-only
  pitches are usable. Ask each small model for 3 or 4 pitches of at most 6 sentences each, and show
  it its own earlier pitches so it does not repeat. Group the pitches into families. A stronger writer
  implements one pitch per family exactly as written, then screen those.
- **Context for proposers**: the verdict lines of log.md (kept and discarded, with numbers). To test
  whether the loop can rediscover something, hide it: drop every matching line, and keep its code
  out of the sandbox.
- **Mix components**: at each check-in, ask what would help this lane, whether a library, a small
  trained model, or a technique kept in another project. Test the mix like any other change.
- **Screen with successive halving**: `python arloop.py screen --cands cands/ --cmd "score {cand} {seed} {steps}" --rungs 600:0,1200:0-1,2400:0-1`.
  Only the survivor goes to sealed.
- **Novelty** (optional; its bonus is not A/B tested yet): `python arloop.py novelty --cand x.py --kept kept/`
  gives 1 when the candidate shares no code with any kept mechanism and 0 for a copy. Use it to
  flag tweaks, and to break ties between winners. It never turns a loss into a keep.

## 3. Rules learned the hard way

- Pre-register, then look. A win condition written after the numbers is not a test.
- The sealed split decides a hypothesis once. Tuning on sealed turns it into select.
- Rerun the baseline in the same harness, on the same device and at the same time as the
  candidate. Old numbers from another harness move, even with the same code and seeds (a kept 0.93
  reproduced as 0.62 here).
- Suspect the check first. A result that looks too good usually has a leak, a wall-clock
  artefact (a smaller model gets more steps inside the same seconds), or a stale cache.
- Budgets are in steps or tokens, not seconds, unless the job is speed.
- Take seeds that "take off" or "stall" seriously: a bimodal arm needs more seeds, not a better story.
- An idea that wins on a fixed-format toy may be using the format. Retest it on a harder or
  free-form version before calling it general.
- One GPU job at a time, under a lock. Release the lock between stages.
- Report every claim with its evidence: the command, the exit code and the file.
