# arloop

The keep-or-revert engine behind `skills/research-loop`. One file, standard library only,
Python 3.8 or newer.

| command | what it does |
|---|---|
| `init` | creates `research/` with `log.md`, `handoff.md` and `ledger.jsonl` |
| `seal --rows FILE` | hashes the sealed test rows so nobody can quietly change them |
| `prereg --id H7 --hypothesis ... --win ...` | records the hypothesis and its win rule before the run |
| `verdict --id H7 --base base.json --new new.json` | compares the scores and logs KEPT or DISCARDED |
| `compare` | the same comparison without logging |
| `screen` | narrows many candidates down with successive halving |
| `novelty` | scores how different a candidate is from the ones already kept |
| `selftest` | checks the tool itself and prints PASS |

The skill folder carries an identical copy so it can be installed on its own;
`tests/test_layout.py` fails if the two drift apart.
