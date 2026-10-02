# fast-verification-kit

Make a slow check return the same answer in seconds, and make "is the new version
better?" a mechanical ACCEPT / REJECT / UNSURE verdict. Standard library only.

- `fastgate.py`: drop-in for a unittest or pytest suite. Per-test-file hash cache,
  parallel workers, a compile check first, and an `equal` mode that proves the fast
  gate gives the same verdict as the serial run on every test.
- `fastcheck_template.py`: the same ideas for any other scorer (eval, benchmark,
  backtest). Fill in six small adapter functions.
- `skills/fast-verification/SKILL.md`: the procedure, written for coding agents.

## At a glance

### How it works

```mermaid
flowchart LR
    A[Hash every file the tests read<br/>+ Python version, env vars] --> B[One key per test file]
    B --> C{Key in cache?}
    C -- yes --> D[Serve the stored verdict<br/>0.02 s]
    C -- no --> E[Compile changed files<br/>syntax error: rejected in ms]
    E --> F[Run files in parallel<br/>longest first, Docker files alone]
    F --> G[Store the verdict<br/>failures too]
```

Edit a source file and every test file reruns. Edit one test file and only that file
reruns. Change nothing and the gate costs one hash.

### What it saves

One suite, seconds per full run, each change measured on its own:

```mermaid
xychart-beta
    title "Seconds per full run (lower is better)"
    x-axis ["Before", "Parallel only", "Waste removed", "Both", "1 file edited", "Nothing changed"]
    y-axis "seconds" 0 --> 40
    bar [39.1, 19.6, 4.1, 1.65, 1.46, 0.02]
```

![Where the speed came from](docs/speed-breakdown.png)

### Before and after, four suites

```mermaid
flowchart LR
    subgraph before [Before: every run reruns everything]
        direction TB
        b1[Harness build tests, 304: 39.1 s]
        b2[Harness build tests, Windows, 323: 257 s]
        b3[Containerized eval tests, 275: 136 s]
        b4[Sandbox pipeline tests, 354: 2317 s]
    end
    subgraph after [After fastgate: same verdict on every test]
        direction TB
        a1[1.65 s fresh, 0.02 s unchanged]
        a2[136 s fresh, under 0.5 s unchanged]
        a3[121 s fresh, 1.2 to 1.7 s unchanged]
        a4[1569 s fresh]
    end
    b1 --> a1
    b2 --> a2
    b3 --> a3
    b4 --> a4
```

![Before and after on four suites](docs/four-suites.png)

### How it keeps agents honest

An agent loop reruns the same check hundreds of times. fastgate makes each rerun cheap,
and two gates stop the loop from trusting a shortcut or a lucky number.

```mermaid
flowchart TD
    S[Adopting fastgate in a repo] --> Q{fastgate equal:<br/>same verdict as the serial run<br/>on every test?}
    Q -- no --> X[Do not adopt.<br/>Fix the missing input:<br/>--env, --exclude, --serial]
    X --> Q
    Q -- yes, EXACT --> L[Agent loop]
    L --> E[Agent edits code]
    E --> R[fastgate run]
    R -- FAIL --> F[Cached failure:<br/>same input, same failure,<br/>no wasted reruns] --> E
    R -- PASS --> AB{Changes a score?<br/>fastgate ab vs baseline}
    AB -- ACCEPT --> K[Keep]
    AB -- REJECT --> V[Revert]
    AB -- UNSURE --> M[More items or revert]
    K --> L
    V --> L
    M --> L
```

- **equal** is the proof: the fast gate is adopted only at zero changed verdicts.
- **run** is the gate: exit code 0 means PASS, and a syntax error is rejected before
  any test runs.
- **ab** is the keep rule: paired by item, grouped by what is correlated,
  bootstrapped, ACCEPT only when the lower 90% bound is above zero. Nobody argues
  about noise.

## Numbers

| Suite | Tests | Before | After | Verdicts changed |
|---|---|---|---|---|
| Harness build tests, 4-core Linux | 304 | 39.1 s serial | 1.65 s fresh, 0.02 s unchanged | 0 |
| Harness build tests, Windows | 323 | 212 to 270 s | 120 to 148 s fresh | 0 |
| Sandbox pipeline tests, Windows, Docker | 354 | 2317 s | 1569 s fresh | 0 |
| Containerized eval tests, Windows, Docker | 275 | 135.6 s median | 120.9 s fresh, 1.2 to 1.7 s unchanged | 0 |

The biggest win on the first suite was not parallelism. Profiling showed half the time
was test servers idling (a 0.5 s shutdown poll, a 2 ms sleep per streamed chunk).
Removing that took it from 39.1 s to 4.1 s serial; running files in parallel alone
reached 19.6 s. Profile before you speed anything up.

## fastgate

```bash
python fastgate.py equal            # serial run vs fastgate, every test's verdict diffed
python fastgate.py run              # the gate: JSON summary, exit 0 on PASS
python fastgate.py run --fresh      # ignore the cache
python fastgate.py ab BASE.json CAND.json --group-by KEY
```

Options: `--runner pytest`, `--tests DIR`, `--jobs N`, `--env VAR` (an env var that
changes results), `--exclude PATH` (files the tests never read), `--serial GLOB` (files
that share Docker or a fixed port, run one at a time after the pool), `--retry-failed`
(rerun cached failures the machine caused).

How the cache key works: every non-test file in the tree, the Python version, the
named env vars and fastgate itself form one shared hash; each test file adds its own
bytes. Change nothing and the gate costs one tree hash. Edit one test file and only
that file reruns. Edit anything else and every file reruns. Failures are cached too.

The key assumes a test file does not read another `test_*.py` file. Helpers such as
`conftest.py`, fixtures and data are in every key.

## The gate

`ab` and `compare` pair candidate and baseline on the same items, average the deltas
within each group of correlated items, bootstrap over groups, and return ACCEPT only
when the lower bound of the 90% interval is above zero. Different item sets are
refused.

## Tests

```bash
python -m unittest discover -s tests
```

22 tests; one needs pytest and skips without it. Passing on Windows 11 with Python
3.11, 3.13 and 3.14.

## Install as a skill

Copy `skills/fast-verification/` to `~/.claude/skills/` (every project) or a repo's
`.claude/skills/`. Other agent harnesses can read `SKILL.md` as a plain instruction
file. Also at https://maxnaid.com/skills/.

## Licence

MIT. See `LICENSE`.
