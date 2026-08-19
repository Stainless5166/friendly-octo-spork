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
  working `mutants/` directory so the eight in-scope files still have
  the rest of `spork.core` (models, classify, state, ...) importable
  alongside them.
- `only_mutate` narrows which files actually get mutated to the eight
  in scope (docs/DESIGN.md §16.1's list): `rules/engine.py`,
  `actions/executor.py`, `dispatch/combine.py`, `pipeline/default.py`,
  `llm/confidence.py`, `classify/keyword.py`, `receipts/extract.py`,
  `pipeline/tier2/escalate.py`.
- `pytest_add_cli_args_test_selection` scopes the test run per mutant
  to `tests/core/{rules,actions,dispatch,pipeline}` plus
  `tests/core/classify`, `tests/core/receipts`, and (explicitly, not
  the whole `tests/core/llm` directory — see the comment in
  `pyproject.toml`) `test_confidence*.py` — fast enough for mutmut's
  per-mutant re-run loop; the full suite still runs in CI.

## Baseline (this run)

386 mutants generated across the eight in-scope files: **383 killed**,
**3 survived** — all three confirmed equivalent below (the same three
`rules.engine`/`pipeline.default` survivors the original four-module
baseline already recorded; none of the four newly-scoped files have
any surviving mutant), so the real kill rate against distinguishable
mutants is 383/383. `uv run mutmut results` after a fresh `uv run
mutmut run` should reproduce this same 3-survivor baseline; a new
survivor beyond these three means either a real gap (add a targeted
test, same as any other coverage gap) or a new equivalent mutant (add
it to the list below with the same reasoning this file already uses).

Re-baselined from an earlier 174/171/3 count (then 198/195/3): M10's
`archive_receipt` wiring (commit `0266d0e`) added real lines to
`actions/executor.py` and `pipeline/default.py`, which shifted
mutmut's per-file numbering — the two `process_message` survivors
below moved from `_mutmut_16`/`_mutmut_20` to `_mutmut_18`/`_mutmut_22`
(diffed against the previous baseline to confirm: same two literal-
`text=` mutations, same reasoning, no new gap). Scoping in
`llm.confidence`, `classify.keyword`, `receipts.extract`, and
`pipeline.tier2.escalate` added 188 more mutants on top of that
(386 total) without touching either file the three equivalents live
in, so their IDs are unchanged this round.

Scoping `pipeline.tier2.escalate` in surfaced 29 real, non-equivalent
survivors on its first run — all closed by strengthening/adding
tests (no `src/spork` change; see that commit's message for the full
list: `_utc_now_iso()`'s UTC-ness, `escalate_message()`'s
`thread_prior_subject`/`thread_user_has_replied`/`max_body_chars`/
`draft_creator` passthrough, and `escalate_message_or_quarantine()`'s
quarantine-branch `detail_json`/`tier_reached`/`action_taken`/alert-
content/correlation-id exactness) before this baseline was recorded.
`llm.confidence`, `classify.keyword`, and `receipts.extract` had zero
survivors on their first run — the property tests added alongside
already fully constrained them.

## Recorded equivalent mutants

Mutants that survive because the mutated code is behaviorally
identical to the original for every input — not a test gap, and no
test could kill them without asserting on something that doesn't
actually matter.

- **`spork.core.pipeline.default.x_process_message__mutmut_18`** and
  **`..._mutmut_22`** — both mutate the literal `text=""` passed to
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
`spork.core.dispatch.combine`, `spork.core.pipeline.default`,
`spork.core.llm.confidence`, `spork.core.classify.keyword`,
`spork.core.receipts.extract`, and `spork.core.pipeline.tier2.escalate`
— not every module already at 100% line coverage. These eight are both
*decision* logic (a bug here silently misfiles or misfires on real
mail — the exact failure mode docs/DESIGN.md §11 exists to bound) and
already fully covered by example-based tests, the two preconditions
that make a surviving mutant worth a human's time to look at. See
docs/DESIGN.md §16.1/§16.2 for the full reasoning, including why
property-based (Hypothesis) tests for the same eight modules run in
the ordinary `uv run pytest` gate while this doesn't.

The second four were added after a review of every other 100%-covered
module against the same two preconditions: `llm.confidence` (the
autoact/alert threshold ladder gating every Tier 2 verdict's
autonomous-action decision), `classify.keyword` (the default Tier 1
local classifier's match-fraction scoring and tie-break),
`receipts.extract` (the decline-rather-than-guess company/date
resolution chain), and `pipeline.tier2.escalate` (the
`QUARANTINABLE_ERRORS` quarantine-vs-propagate boundary that keeps a
bad model response from crash-looping the daemon) all met both bars.
`pipeline.tier2.modules` (the larger Tier 2 concrete-module set this
milestone's escalate.py calls into) is a plausible next candidate but
was deliberately left out of this round — scoping in a module is its
own decision worth a dedicated look, not a rider on this one.
