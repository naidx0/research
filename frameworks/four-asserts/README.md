# four-asserts

Four things to assert about a run before its record counts.

No dependencies. Python 3.10+.

## The measured absence

Twenty-five agent and evaluation frameworks were read in their own docs,
READMEs and published API source on 2026-09-05, and tested for four properties.

**Adding a tool is nearly free in all of them.** Eight of the twenty-five take
four lines and a decorator; one takes a single Markdown file; most of the rest
take a typed function in a list. That part of the problem is solved.

**Asserting anything about the run is no part of any of them.**

| property | present |
|---|---|
| **(a) a counting gate** — the runner asserts `ran == discovered`, denominator printed | **1 of 25** |
| **(b) a lock** — who holds the resource, and is that holder alive | **0 of 25** |
| **(c) a witness** — identity that survives the data being gone | **0 of 25** (1 hashes, for deduplication) |
| **(d) a judge reason that is checked** — the stored reason re-derived from the artifact | **0 of 25** (7 store one) |
| **all four** | **0 of 25** |
| **any two** | **0 of 25** |

The one counting gate and the one content hash are in different projects.

The sharpest datum is (b): of the twenty-five, the project whose entire surface
is GPU scheduling says *GPU* fifty-three times in its README and *lock* zero
times. The nearest misses to a lock are concurrency limiters — a cap on how
many things run at once, with no holder and no lease, which answers a different
question.

For (c), one project is content-addressed by sha256 and uses it for deduplication;
none keeps an identity once the bytes are gone, and none reports *what was read*
with a denominator. For (d), seven store a reason field — `explanation`,
`reason`, `rationale`, `comment` — and one of them explicitly ignores it during
evaluation. A stored reason that nobody re-derives is a decoration on a verdict,
and it reads as evidence.

## What each one would have caught

These are from one harness's own record, with the commits.

**`assert_ran` — a suite that discovered 3,822 cases, ran 3,315, and printed OK.**
No failure, no error, no skip line: a green tick over 87% of the suite, one
command from being pushed on. Two runs were sharing one machine. Nothing in the
runner's output distinguished that from a complete run, because a runner reports
what it ran and never what it was supposed to run (`d9c1ac4`).

And the case a count alone cannot see: a module that fails to import is replaced
by one placeholder that is discovered and runs like anything else, so the totals
agree over a smaller tree. Measured on one clean clone, 35 real cases became 2
placeholders while `ran == discovered` held throughout (`d6fe7e6`).

**`hold` — two full suites running concurrently under two interpreters while
nobody held the lock.** The lock existed. It protected only the runs that
remembered to take it, which is not a guard. So a green run now also names the
neighbours it can see (`d15b756`).

And: a lock's liveness check answered *alive* for pid 8932, and 8932 was the
desktop shell. Every operating system reuses process ids, so a lock left by a
run whose number was later handed to a long-lived program reads as held for as
long as that program runs. The holder's process start time is recorded beside
its number (`ceede9d`).

**`witness` — a path is a location, not a version.** A size-and-modification-time
stamp is free and it is not identity: on one ordinary filesystem, two *different*
files of the same length written back to back produced an identical stamp in
**157 of 200 trials**. Not an exotic filesystem with a coarse clock — the common
case for a fast rewrite.

**`void_unless` — a model asked to grade 72 rewrites that are not degradations
kept 19, and every one of the 19 justified itself with a clause the rewrite
still contains word for word.** One cited *"the rewrite drops the 'over 25.00'
condition"* where the only difference between the two texts was a removed full
stop (`4c915ac`). The day before, the same instrument attributed a quotation —
`'We open 11am to 4pm on bank holidays, except Christmas Day'` — to a rewrite
that contained no such text. The prose was decoupled from the text in both
directions: it fabricated quotes from nothing and fabricated deletions from
something.

Deciding the same question by rule instead refused 106 non-degradations at zero
model calls (`7b28bf6`).

## Install

```
python -m venv venv
venv/Scripts/python -m pip install "four-asserts @ git+https://github.com/naidx0/research.git#subdirectory=frameworks/four-asserts"
```

No dependencies, so nothing else is pulled in. **The tests are not part of the
installed package** — `pip install` gives you `four_asserts` and not `tests/`.
To run the 38 yourself, take the source and run them from it:

```
python -m unittest discover -s tests -t tests
```

## Four lines

```python
from four_asserts import assert_ran, Hold, witness, void_unless, Verdict, account

ran = assert_ran(discovered=3822, ran=3315)          # exit_code 2: it did not say
with Hold("gpu.hold", holder="lane-a", purpose="a suite"):
    pass                                             # waits while the holder lives
kept = witness("pyproject.toml")                     # sha256 + size, outlives the file
rulings = void_unless([Verdict("KEEP", "It drops a clause.", "a b c", "a b c")])

print(ran.verdict)                                   # DID NOT SAY: 507 case(s) never ran
print(kept.how)                                      # sha256 ... over all N bytes
print(account(rulings))                              # 1 of 1 verdicts are void
```

**That block is run verbatim on every push**, on both the oldest Python this
package supports and the newest, and a non-zero exit fails the build — because
two of the four usages here were wrong when they were only prose, and a person
on a fresh machine found them by typing them in. See `.github/workflows/`.

Which is why the examples make their own conditions: `Hold` creates its lock
where you point it and `witness` reads a real file. Both raise
`FileNotFoundError` rather than inventing a result, which is the same rule as
everything else here — and an example that cannot run on its own is an example a
reader cannot run either.

## What it costs to add — measured, not estimated

Adding a *tool* to a builder is about four lines. That is the number the survey
above starts from, so the fair question is what adding the asserts costs beside
it. Measured on the MCP Python SDK (2.1.1), on a server with three tools and a
runner, counting code lines only and excluding docstrings:

| builder | added to | before | after | net |
|---|---|---|---|---|
| MCP Python SDK 2.1.1 | three tools (`witness`, `hold`, `void_unless`, one import) | 16 | 19 | **+3** |
| MCP Python SDK 2.1.1 | its test runner (`assert_ran`, with the pending banner) | 4 | 9 | **+5** |
| LangGraph 1.2.11 | three nodes (the same three asserts, one import) | 29 | 37 | **+8** |
| LangGraph 1.2.11 | its test runner | 4 | 9 | **+5** |

**The node side costs more than the tool side, and the reason is the state
schema.** A LangGraph node returns a slice of a typed state, so every field an
assert adds — the witness sentence, the void flag — has to be declared in the
`TypedDict` before a node may return it, and the grader reads its inputs out of
that state rather than from arguments. Two lines of schema and two of state
access is most of the difference. The runner cost is identical in both, because
`assert_ran` wraps a runner and neither builder owns one.

Per assert on the MCP server: `witness` replaced two lines with two, `hold`
wrapped one line in a context manager, `void_unless` added one line and
extended the return, and `assert_ran` cost three lines plus two for the banner
that stops a killed run reading as a pass.

What those lines bought, on the same server, in the same run:

- `count_rows` answered `120 rows` before and
  `counted 120 rows; sha256 fd61574c… over all 1328 bytes of rows.jsonl` after.
- `grade` returned the verdict and its reason before; after, it returned
  `"void": true` on a reason claiming a dropped clause where the two texts
  differ by a full stop.
- `train_adapter` waited for a foreign holder instead of running, and left no
  lock file behind. Checked by planting one: the tool blocks while it is there
  and runs when it is gone, so the line is not decorative.

Two builders, not twenty-five. The survey is a reading of documentation; these
are runs. On the LangGraph side the same fabricated reason came back
`"void": true` through a compiled graph, and the count carried the same sha256
through the finished state.

## What this does not claim

- **It does not decide whether your work is good.** It decides whether the
  record of it says what it appears to say. A run where everything ran and
  everything failed is a valid record of a bad result.
- **`void_unless` does not decide whether a verdict was right.** A reason that
  survives its rule can still be a wrong call. It says only that the stated
  reason is about the text in front of it — and it distinguishes *no rule was
  registered for this reason* from *the rule ran and the reason failed it*,
  because collapsing those is how an unchecked field starts looking checked.
- **`hold` is not a distributed lock.** It is one file created with `O_EXCL`,
  atomic on Windows and POSIX alike. One machine, named holders.
- **`witness` costs a read.** Hashing a large artifact is not free, and a
  partial witness says it is partial and refuses to be compared as an identity.
- **`assert_ran` does not explain a mismatch.** It is red whenever discovery and
  execution disagree, whatever caused it. A guard that needs a diagnosis first
  is a guard that fails on the next cause nobody diagnosed.
- **The survey is a reading of documentation and published source, not of
  behaviour.** Two projects' docs were unreachable when it was taken; those are
  recorded as *not found*, not as *confirmed absent*.

## Licence

MIT.
