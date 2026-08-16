# Mutation testing

Mutation testing for `spork.core`'s decision-critical modules — a
different kind of test than correctness (docs/DESIGN.md §16.2), so
this lives outside `tests/` (pytest's `testpaths`) and never runs as
part of `uv run pytest` or either CI gate, same reasoning
`benchmarks/` already established for performance tests. It runs
manually and on a weekly schedule
(`.github/workflows/mutation-testing.yml`).

```bash
uv run mutmut run       # full run against the scoped modules (~1-2 minutes)
uv run mutmut results   # list survived/killed mutants from the last run
uv run mutmut show <id> # view one mutant's diff
```

Uses [mutmut](https://mutmut.readthedocs.io/) 3.x, configured in
`pyproject.toml`'s `[tool.mutmut]`:

- `source_paths = ["src/spork"]` — the whole package is copied into a
  working `mutants/` directory so the four in-scope files still have
  the rest of `spork.core` (models, classify, state, ...) importable
  alongside them.
- `only_mutate` narrows which files actually get mutated to the four
  in scope (docs/DESIGN.md §16.1's list): `rules/engine.py`,
  `actions/executor.py`, `dispatch/combine.py`, `pipeline/default.py`.
- `pytest_add_cli_args_test_selection` scopes the test run per mutant
  to `tests/core/{rules,actions,dispatch,pipeline}` — fast enough for
  mutmut's per-mutant re-run loop; the full suite still runs in CI.

## Baseline (this run)

174 mutants generated across the four in-scope files: **171 killed**,
**3 survived** — all three confirmed equivalent below, so the real
kill rate against distinguishable mutants is 171/171. `uv run mutmut
results` after a fresh `uv run mutmut run` should reproduce this same
3-survivor baseline; a new survivor beyond these three means either a
real gap (add a targeted test, same as any other coverage gap) or a
new equivalent mutant (add it to the list below with the same
reasoning this file already uses).

## Recorded equivalent mutants

Mutants that survive because the mutated code is behaviorally
identical to the original for every input — not a test gap, and no
test could kill them without asserting on something that doesn't
actually matter.

- **`spork.core.pipeline.default.x_process_message__mutmut_16`** and
  **`..._mutmut_20`** — both mutate the literal `text=""` passed to
  the initial `Payload` in `process_message()` (to `None` and `"XXXX"`
  respectively). None of the eight concrete pipeline modules
  (`spork.core.pipeline.modules`) ever read `payload.text` — this
  pipeline's real content lives in `meta.message.body_text`, and
  `Payload.text` is part of the generic `Filter`/`Augment` framework
  meant for a future prompt-building chain (docs/DESIGN.md §9.4's
  "different concrete pipeline" note). Asserting on this value would
  test an implementation detail nothing downstream depends on.

- **`spork.core.rules.engine.x__condition_matches__mutmut_1`** —
  mutates `checked_any = False` to `checked_any = None` at the top of
  `_condition_matches()`. `checked_any`'s only use is as this
  function's return value, and every caller (`evaluate()`) uses it in
  a boolean `if` context (`if _condition_matches(...)`) — Python
  treats `None` and `False` identically there. No input can make this
  observable without inspecting `_condition_matches()`'s raw return
  value directly, which nothing in `spork` does.

## Scope rationale

Scoped to `spork.core.rules.engine`, `spork.core.actions.executor`,
`spork.core.dispatch.combine`, and `spork.core.pipeline.default` —
not every module already at 100% line coverage. These four are both
*decision* logic (a bug here silently misfiles or misfires on real
mail — the exact failure mode docs/DESIGN.md §11 exists to bound) and
already fully covered by example-based tests, the two preconditions
that make a surviving mutant worth a human's time to look at. See
docs/DESIGN.md §16.1/§16.2 for the full reasoning, including why
property-based (Hypothesis) tests for the same four modules run in the
ordinary `uv run pytest` gate while this doesn't.
