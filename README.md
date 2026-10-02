# research

Tools for running research that measures itself: every change is tested against a fixed
baseline and kept only if it wins by more than the noise. Everything here is plain Python
with no dependencies. MIT licensed.

## What is in each folder

**`skills/`** holds instructions written for coding agents (Claude Code, Codex and others).
Copy a folder into your agent's skills directory and it knows the procedure.

- `skills/research-loop/`: how to run an experiment loop. Write down what counts as a win,
  test against a sealed baseline, keep or revert by a fixed rule, and log every result,
  including the losses. Ships its own copy of `arloop.py`.
- `skills/fast-verification/`: how to make a slow test suite or eval give the same answer
  in seconds, and how to turn "is the new version better?" into ACCEPT, REJECT or UNSURE.

**`frameworks/`** holds the code those skills use, and pointers to larger projects.

- `frameworks/arloop/`: one file, `arloop.py`. It seals the test rows, records each
  hypothesis before it runs, compares the new score with the baseline, and writes the
  verdict to a log. Run `python arloop.py selftest` to check it works.
- `frameworks/fast-verification-kit/`: `fastgate.py` makes a unittest or pytest suite fast
  with a cache and parallel workers. `fastcheck_template.py` does the same for any other
  scorer. Both have tests.
- `frameworks/executed-pivots/`: the Pivot Inspector walkthrough. Executed Pivots rewards an
  agent's terminal step by what the command actually did, not by what it typed. Open the
  walkthrough at https://naidx0.github.io/research/ . The full project lives in its own repo.
- `frameworks/four-asserts/`: four checks to run before trusting a test or eval run: every
  case that was found actually ran, a shared resource has a live named holder, a record of
  what was read outlives the data, and a judge's stated reason holds up against the text.

**`tests/`** checks that the two copies of `arloop.py` match and that every tool passes its
own tests.

## Not in here

ML Harness and Sequence are products with their own repos:
[ml-harness-app](https://github.com/naidx0/ml-harness-app) and
[sequence-arch-tool](https://github.com/naidx0/sequence-arch-tool).

## Quick start

```bash
python frameworks/arloop/arloop.py selftest
python -m unittest discover -s tests
```
