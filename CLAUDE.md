# CLAUDE.md

Guidance for Claude Code (or any agent) working in this repository.

## What this is

**Spork** is a tiered, JMAP-native email triage tool for a single
Fastmail account: `sporkd` (a daemon) fetches mail, runs it through a
deterministic rule engine (Tier 1), and — once M3 lands — escalates
unmatched mail to a Claude verdict (Tier 2). `spork` is the CLI for
status/config/rules. Full design: `docs/DESIGN.md`. Milestone plan and
current status: `docs/ROADMAP.md`. A test-by-test inventory
cross-checked against the roadmap: `docs/TEST_COVERAGE.md`.

**Read those three docs before making any non-trivial change.** They
are kept in sync with the code as a hard rule, not a nice-to-have —
see "Keeping docs in sync" below.

## Stack

- **UV** for dependency management (`uv sync`, `uv run ...`).
- **Typer** (built on Click) for both CLIs — `spork` is a command
  group, `sporkd` is a single-command app.
- **pydantic** for the rule schema; **SecretSpec** for secrets
  (`secretspec.toml` + `spork.core.secrets`); **jmapc** for JMAP (not
  yet a dependency — still behind `NotImplementedError` stubs, see
  below).
- **ruff** (lint + format), **mypy --strict**, **pytest** + **pytest-cov**.

## Architecture in one paragraph

Everything downstream of mail acquisition works against
`NormalizedMessage` (`spork.core.models`), never a transport-specific
type. A `Provider` (`spork.core.providers.base`) is a backend's *entire*
relationship to spork: `build_source()` (read) and
`build_action_applier()` (write) on one Protocol, not two — because for
any one backend both are the same relationship to the same source of
truth. `JmapProvider` and `FileProvider` are the two adapters today;
providers are loaded dynamically by `"module:Class"` spec
(`spork.core.providers.loader`) so an unconfigured provider's
dependencies are never imported. Message acquisition itself is a
`Trigger` (when) + `ContentFetcher` (what) composed into a `Source`
(`spork.core.sources`). `spork.core.pipeline.process_message()` ties
idempotency (`StateDB`) + rule evaluation (`spork.core.rules.engine`) +
action application (`spork.core.actions.executor.ActionExecutor`) +
audit logging together for one message. Local classifiers are
pluggable via a `TextClassifier` Protocol + registry
(`spork.core.classify`), fanned out and combined via
`spork.core.dispatch` when more than one is configured.

Read `docs/DESIGN.md` §6 (components) and §9 (pipeline/modularity) for
the full picture — this paragraph is a map, not a substitute.

## The one rule that shapes everything else: TDD, strictly

This codebase was built test-first, every time, without exception, and
new work must continue that discipline:

1. **Design first if the change is non-trivial.** A real architectural
   decision (a new Protocol, a restructuring) gets its own commit
   before any test — see recent history for examples
   (`git log --oneline` — commits like "Design: JMAP as a provider...").
2. **Write 3–7 acceptance tests for the unit of work.** Not tests of a
   library's own behavior — tests of what *this codebase* promises.
   Confirm they fail for the *right* reason (missing module/attribute,
   not a typo) before committing.
3. **Commit the tests alone.** Never application code and test code in
   the same commit.
4. **Implement until green.** Re-run the new tests, then the whole
   suite, then `ruff check --fix && ruff format`, then `mypy`. Commit
   the implementation alone.
5. **Add failure/edge-case tests** (usually a sibling
   `test_x_edge_cases.py` file) after the acceptance round. If they
   pass against the existing implementation with no code change,
   that's fine and worth noting in the commit message — it's not
   wasted effort, it's coverage that was already earned. If they
   reveal a gap, fix it in its own commit.
6. **Check coverage** (`--cov=spork.core.X --cov-report=term-missing`)
   and close any real gap with one more targeted test.
7. **Never delete or weaken a test to make it pass.** If a test turns
   out to encode the wrong behavior, that's a design conversation, not
   a quiet edit.
8. **Update `docs/ROADMAP.md` and `docs/TEST_COVERAGE.md`** as their
   own commit once the milestone item is actually done.

### Two ways to handle "not implemented yet" — pick the right one

- **`NotImplementedError`, settled shape, ordinary passing test.** Use
  this when the real implementation needs something this environment
  genuinely cannot exercise honestly — almost always a live network
  call (a live Fastmail/JMAP session is the recurring example). Settle
  the constructor args and method signatures for real, raise
  `NotImplementedError` with a message pointing at the relevant
  `docs/ROADMAP.md` milestone, and write a normal `pytest.raises(...)`
  test — the raise *is* the currently-correct behavior, not a stand-in
  for one. See `JmapClient`, `JmapPushTrigger`, `spork doctor`'s
  connectivity check.
- **`@pytest.mark.xfail`.** Use this only when the target behavior is
  fully specified and buildable in principle, just not built yet.
  `xfail_strict = true` is set in `pyproject.toml`, so an accidental
  pass fails CI — verify a graduation with `pytest --runxfail` *before*
  removing the marker, to confirm the test now passes for the reason
  it's supposed to. As of the M2 PR, **no `xfail` tests remain** in the
  suite; if you add one, expect to graduate it, not leave it.

**Do not fake the thing that's genuinely missing.** The concrete
lesson this project learned the hard way: don't build a JSON-fixture
mode to pretend `spork rules test` is dry-running against "recent
mail" when there's no live JMAP fetch yet — that's testing against
fake data, not against recent mail, and the command would be lying
about what it does. If a fixture-backed implementation is independently
useful (see `FileProvider`), build and document it as what it actually
is, not as a stand-in for the blocked thing.

## Conventions

- **Typed Python everywhere**, `mypy --strict` must stay clean.
  `packages = ["spork"]` in `pyproject.toml` means mypy only checks
  `src/spork`, not `tests/` — that's deliberate, not a gap to fix.
- **Non-boilerplate comments** on every function and data structure:
  say *why* it exists / what it's for, not what the next line
  obviously does.
- **Protocol-based DI, structurally satisfied** — `Trigger`,
  `ContentFetcher`, `Source`, `TextClassifier`, `Combiner`, `Provider`,
  `ActionApplier` are all `typing.Protocol`s. Nothing inherits from
  them.
- **Mirrored test/src paths**: `src/spork/core/x/y.py` ↔
  `tests/core/x/test_y.py`. `scripts/related_tests.py` (used by the
  push-workflow) and the `--import-mode=importlib` pytest setting both
  depend on this convention — don't break it without checking both.
- **One catchable error type per module boundary** — `RulesLoadError`,
  `MessagesLoadError`, `ProviderLoadError`, `SecretsError`,
  `ActionExecutionError` — wrapping whatever the underlying
  library/stdlib call actually raised, so callers (and `spork doctor`,
  eventually) only need to know one type per boundary.
- **Clean CLI errors, never raw tracebacks.** Typer's default "pretty
  exceptions" rendering *does* print something containing the literal
  word "Traceback" for an uncaught exception — catch anything a command
  can legitimately fail on (a load error, a settled-shape
  `NotImplementedError`) and `typer.echo(f"Error: {exc}", err=True)` +
  `raise typer.Exit(code=1)` instead. Every CLI test asserts
  `"Traceback" not in result.stderr` for exactly this reason.
- **`# noqa: B008`** is expected and correct on Typer
  `Argument(...)`/`Option(...)` defaults — that's idiomatic Typer, not
  a mutable-default bug; ruff's bugbear rule doesn't know the
  difference, so it's suppressed with a one-line reason, not disabled
  project-wide.

## Commands

```bash
uv sync                                   # set up the dev environment
uv run pytest                             # full suite
uv run pytest --cov=spork --cov-report=term-missing   # with coverage
uv run pytest path/to/test_x.py -v        # one file
uv run ruff check --fix . && uv run ruff format .
uv run mypy                               # strict, src/spork only
uv run spork --help                       # or: uv run python -m spork.cli.main --help
uv run sporkd --help
```

## Git workflow

- Work on a feature branch, never commit directly to `main`.
- Commits are split by TDD phase (see above) — check `git log
  --oneline` on this repo for the pattern before assuming a different
  convention applies.
- **`.github/workflows/push-format-test.yml`** auto-formats and runs
  related tests on every push to a non-`main` branch, and may commit
  back as `github-actions[bot]` with `[skip ci]`. After pushing,
  `git fetch origin <branch> && git log --oneline
  HEAD..origin/<branch>` to check for that commit, and `git rebase
  origin/<branch>` before pushing again if it's there.
- **`.github/workflows/pr-checks.yml`** gates PRs into `main`: ruff
  lint + format check, `mypy src`, `pytest --cov=spork`, and a `pdoc`
  API-docs build (a broken docs build usually means a docstring/type
  hint drifted from reality — treat it like a failing test).
- Do not open a PR unless asked to. When asked, check for a PR
  template first (none exists in this repo as of the M2 PR — write the
  body from scratch, summarizing what changed, verification results,
  and what's still genuinely blocked).
- **If your designated branch's PR has already been merged**, don't
  stack new commits on old, already-merged history. Restart the branch
  from the latest `main` (`git fetch origin main && git checkout -B
  <branch> origin/main`) before starting new work.

## Keeping docs in sync

Every milestone-sized change should touch, in its own commit(s):

- **`docs/DESIGN.md`** — if the change adds/changes a component,
  Protocol, or CLI command, update the relevant section (§6 component
  tree, §9 pipeline/modularity, §12 CLI reference, etc).
- **`docs/ROADMAP.md`** — check off the item, and if the "why" behind
  an unchecked item has gone stale (e.g. "CLI framework not chosen
  yet" after Typer's already in use elsewhere), fix the stale
  reasoning too, not just the checkbox.
- **`docs/TEST_COVERAGE.md`** — append new numbered test-inventory
  entries (numbers are stable once assigned — never renumber existing
  entries even if a new one is inserted out of order), and update the
  relevant milestone's coverage table and the file's own status header
  at the top.

If a change doesn't touch these, ask whether it should before treating
it as done.
