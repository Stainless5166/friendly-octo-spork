# Roadmap

Companion to `DESIGN.md`. Milestone-based rather than date-based — this is
a personal-scale project and calendar estimates would be noise. Each
milestone has a concrete exit criterion so "done" is checkable, not vibes.

Sizing tags (`S`/`M`/`L`) are rough effort, not calendar time.

## M0 — Project scaffolding

**Goal:** `uv run` works for both executables against a stub pipeline;
CI runs on every push.

- [x] `uv init`, `pyproject.toml` with `[project.scripts] sporkd`, `spork` (S)
- [x] `src/spork/` package layout per `DESIGN.md` §6.1 (S)
- [x] `secretspec.toml` with declared secrets (§7.3) (S) — plus
      `spork.core.secrets.resolve_secrets()`, the SDK wrapper §7.3
      describes sporkd will use at startup (`tests/core/test_secrets.py`)
- [x] Lint/format/type-check config (ruff + mypy or pyright) (S)
- [x] CI: lint, type-check, unit tests on push/PR (S)
- [x] `spork --help` / `sporkd --help` produce real (if empty) output (S)
      — CLI framework decided (§6.3: Typer); both also get `--version`
      for free (`tests/cli/test_main.py`, `tests/daemon/test_main.py`)

**Exit criteria:** fresh clone → `uv sync && uv run sporkd --help` and
`uv run spork --help` both work with no manual setup beyond secrets.
**Met.**

## M1 — JMAP connectivity

**Goal:** the daemon can authenticate, resolve mailboxes, and fetch mail
read-only. No actions taken yet.

- [ ] `spork.core.providers.jmap.client`: session bootstrap via `jmapc`, secrets
      wired through `secretspec` (M) — shape settled, `connect()` and
      `fetch_new_messages()` (also covers the `Email/query`+`Email/get`
      batched fetch item below) deliberately raise `NotImplementedError`:
      a real jmapc session against a live Fastmail account is real-network
      work this environment can't exercise honestly. See
      `tests/core/providers/jmap/test_client.py`.
- [x] Mailbox role resolution + caching (Inbox, Drafts, custom mailboxes) (S)
- [ ] ~~`Email/query` + `Email/get` batched fetch of new mail since a cursor (M)~~
      — folded into `JmapClient.fetch_new_messages()` above, same status.
- [ ] EventSource push listener with reconnect/backoff (M) — backoff
      *scheduling* is done and tested (`spork.core.providers.jmap.backoff`); the
      listener itself (`JmapPushTrigger.wait()`) is a settled-shape
      `NotImplementedError` stub for the same live-connection reason as
      the client. See `tests/core/providers/jmap/test_push.py`.
- [x] Poll-based fallback when push is unavailable/disconnected (S) —
      real, tested implementation (`spork.core.sources.timer.IntervalTimer`
      + `spork.core.sources.fallback.FallbackSource`), pure control flow
      with no network dependency. Ready to compose with a real
      `JmapClient`-backed fetcher once that exists.
- [x] State DB: `push_cursor`, `processed_messages` tables + migrations (S)
- [x] `spork doctor` reports JMAP auth + connectivity status (S) — CLI
      wiring is real (the earlier "CLI framework isn't chosen yet"
      note is stale: Typer's been in use since M2's `spork rules
      test`); the connectivity check itself is a settled-shape
      `NotImplementedError`, same blocker as `JmapClient.connect()`
      above, caught and reported as a clean CLI error rather than a
      traceback. Secrets/systemd/DB checks from docs/DESIGN.md §12
      aren't wired in yet — they need `spork.core.config`, which
      doesn't exist yet — so this command doesn't pretend to run them.

**Exit criteria:** `sporkd` runs, logs each new inbox message's subject
as it arrives (via push, verified by sending a real test email), survives
a forced network drop and reconnects. **Not yet met** — still blocked on
a real `jmapc` session (`JmapClient.connect()`/`JmapPushTrigger.wait()`),
which needs a live Fastmail account and API token to actually build and
test against, not just design.

## M1a — Source / dispatch pipeline

**Goal:** message acquisition (Trigger/ContentFetcher/Source) and
classifier fan-out (Dispatcher/Combiner) exist as protocols + pure-logic
implementations (docs/DESIGN.md §9.2), independent of any real JMAP/IMAP
I/O. Unblocks M1's JMAP `Source` and M2's rule engine consuming an
ensemble classifier, without either depending on live network access to
be developed or tested.

- [x] `spork.core.sources.base`: `Trigger`, `ContentFetcher`, `Source`
      protocols (S)
- [x] `spork.core.sources.triggered.TriggeredSource`: composes any
      Trigger + ContentFetcher into a Source (S)
- [x] `spork.core.sources.replay`: `ImmediateTrigger` +
      `SequenceContentFetcher` — the test/demo "replay a fixture
      through a for-loop" source (S)
- [x] `spork.core.dispatch.dispatcher.Dispatcher`: fan a message out to
      N named `TextClassifier` targets, isolating per-target failures (M)
- [x] `spork.core.dispatch.combine`: `Combiner` protocol +
      `PrimaryCombiner` + `HighestConfidenceCombiner` (S)
- [x] `spork.core.dispatch.combine.DispatchingClassifier`: Dispatcher +
      Combiner wrapped as a `TextClassifier`, so `rules.engine.evaluate`
      needs no changes to consume an ensemble (S)

**Exit criteria:** a `TriggeredSource` built from `ImmediateTrigger` +
`SequenceContentFetcher` replays a fixture list of messages through the
existing Tier 1 rule engine end-to-end in a test, with no real JMAP/IMAP
connection; a `DispatchingClassifier` wrapping two stub classifiers and
a `HighestConfidenceCombiner` produces a single verdict the rule engine
accepts unmodified.

## M1b — Provider abstraction

**Goal:** JMAP restructured from a hardcoded package into one
**provider** behind a common adapter (docs/DESIGN.md §9.3), loaded by
config-string spec via `importlib` rather than a static import —
so a second backend (IMAP) is an addition later, not a rewrite, and
spork never imports a provider's dependencies unless that provider is
actually configured.

- [x] `spork.core.jmap` moved to `spork.core.providers.jmap` (pure
      structural move, no logic changes; git tracked as renames) (S)
- [x] `spork.core.providers.base.Provider`: the one-method adapter
      Protocol (`build_source() -> Source`) (S)
- [x] `spork.core.providers.jmap.provider.JmapProvider`: the Adapter,
      composing the existing `JmapClient` + `JmapPushTrigger` into a
      `Source` via `TriggeredSource` — no fetch/push logic
      reimplemented (S)
- [x] `spork.core.providers.loader.load_provider()`: `"module:Class"`
      spec -> constructed `Provider`, via `importlib`; every failure
      mode (malformed spec, unimportable module, missing class,
      rejected constructor args) raises one `ProviderLoadError` (M)
- [x] `spork.core.providers.file.provider.FileProvider`: a second,
      fully real `Provider` Adapter — a local JSON messages file for
      `build_source()`, a JSON-lines applied-actions log for
      `build_action_applier()`, no `NotImplementedError` anywhere (S)
      — proves the `Provider` abstraction itself (not just the
      loader) generalizes beyond JMAP, independent of `JmapProvider`
      ever reaching a live session. Not a "recent mail" fixture
      mechanism (docs/DESIGN.md §9.3/§13) — a real, honestly-named
      backend in its own right.

**Exit criteria:** `load_provider("spork.core.providers.jmap.provider:JmapProvider", host=..., api_token=...)`
returns a working `JmapProvider`; its `build_source()` composes a real
`Source` whose `.poll()` still raises `NotImplementedError` (propagated
honestly from the still-stubbed `JmapClient`/`JmapPushTrigger` — M1),
proving the adapter/loader machinery is correct independent of whether
the backend underneath it is actually implemented yet. `FileProvider`
goes one step further: loaded the same way, its `build_source()` and
`build_action_applier()` both actually work end to end, no live
network involved. **Met.**

## M2 — Rule engine (Tier 1) + action executor

**Goal:** deterministic rules file drives real mailbox actions, no LLM
involved yet.

- [x] Rule schema + `rules.toml` loader/validator (§7.5) (M) —
      schema (`Condition`/`Action`/`Rule`) now rejects unknown fields
      (`extra="forbid"`), a real gap an edge-case test caught: a
      typo'd field was previously silently ignored and fell back to
      its default instead of failing to load.
- [x] Tier 1 evaluator (first-match-wins, closed condition set) (M)
- [x] Action executor: applies `move`/`tag`/`ignore` via an injected
      `ActionApplier` (docs/DESIGN.md §9.3 — a provider's write side,
      not JMAP-specific); rejects `escalate` outright (M)
- [x] `processed_messages` idempotency check before acting (S) — wired
      into `spork.core.pipeline.process_message()`
- [x] `audit_log` writes for every action taken (S)
- [x] `spork rules test <file>` dry-run against recent mail, no side effects (M)
      — CLI wiring + rules loading is real, tested, and shipped
      (`spork.cli.commands.rules`, `tests/cli/commands/test_rules.py`);
      "against recent mail" itself genuinely needs a live JMAP fetch
      (there's no local mail store spork could substitute — it's a
      pure client to JMAP as the source of truth, docs/DESIGN.md
      §9.3), so that step is a settled-shape `NotImplementedError`,
      caught and reported as a clean CLI error rather than a
      traceback, same blocker/treatment as
      `JmapClient.fetch_new_messages()` (M1). No fixture-file
      workaround — `FileProvider` (M1b) proves the `Provider`
      abstraction generalizes, but it isn't and was never meant to be
      a stand-in for "recent mail" here.
- [x] Unit tests: condition matching, idempotency (M) — dry-run output
      still pending the JMAP fetch above

**Exit criteria:** a hand-written `rules.toml` with 3–4 real rules
correctly files live test mail with no LLM calls; `spork rules test`
matches what actually happens when the rule goes live. **Not yet
met** — blocked on the same live Fastmail account/API token as the
rest of M1's real JMAP work. Everything through action execution +
idempotency + audit + the CLI command's own loading/error-handling is
real and tested; only the live fetch inside `spork rules test` remains.

## M3 — LLM escalation (Tier 2)

**Goal:** unmatched/escalated mail gets a real Claude verdict and it
drives an action.

- [x] Body cleaning: HTML strip, quote-chain collapse, truncation (M) —
      `spork.core.llm.clean.clean_body()`, pure string transformation,
      no dependency on `NormalizedMessage`/JMAP/the Claude API — HTML
      via a hand-rolled `HTMLParser` subclass (no new dependency),
      quote chains cut at the earliest of several marker patterns,
      word-boundary truncation with an explicit marker.
- [x] Claude client wrapper + structured verdict schema (§10) (M) —
      `LLMClient` Protocol adapter (§10.1, mirrors `Provider`'s
      pattern for mail backends) + `spork.core.llm.loader` dynamic
      `"module:ClassName"` loading + a pydantic `Verdict` schema
      (reuses `rules.schema.Action` for `suggested_action`).
      `AnthropicLLMClient` is a settled-shape stub like `JmapClient`:
      real constructor/method signature, `get_verdict()` a clean
      `NotImplementedError` until a live Anthropic API session is
      possible — no `anthropic` import yet, same as `jmapc`.
- [x] Verdict validation against configured mailbox/category set (S) —
      `spork.core.llm.validate.validate_verdict()` (§10.2): checks
      `category`/`suggested_action.mailbox` against sets passed in
      already resolved from config — pure logic, no `Provider`/JMAP
      dependency, no live-account blocker.
- [x] Confidence-band logic: autoact / autoact+alert / alert-only (§9) (M) —
      `spork.core.llm.confidence.confidence_band()` (§10.3): a pure
      function of confidence + the two `config.toml` thresholds, with
      an eager `ValueError` guard against a misconfigured
      `alert_threshold > autoact_threshold`.
- [x] `daily_call_budget` enforcement + `llm_usage` tracking (S) —
      `StateDB` gains an `llm_usage` table + `record_llm_call()`/
      `get_llm_usage()` (§7.4, §10.4); `spork.core.llm.budget.has_budget_remaining()`
      is the pure enforcement half, decoupled from `StateDB` the same
      way `confidence_band()` is decoupled from `Verdict`.
- [x] Draft creation path (`Email/set` into Drafts, never `EmailSubmission`) (M) —
      `Provider` gains `build_draft_creator()` (§9.3, §10.6); `JmapClient.create_draft()`
      is a fourth settled-shape `NotImplementedError` stub (needs a
      live Fastmail session, same as `connect()`/`fetch_new_messages()`/
      `apply_action()`); `FileProvider.build_draft_creator()` is real,
      appending to a second JSON-lines log distinct from the actions
      one. Never wired to `EmailSubmission` anywhere — §11's invariant
      enforced by omission.
- [x] Recorded-response fixtures for CI (no live API calls in tests) (M) —
      `spork.core.llm.clients.recorded.RecordedLLMClient` (§10.5): the
      `LLMClient` equivalent of `FileProvider` — a second, fully real
      adapter with no `NotImplementedError` anywhere, replaying
      pre-recorded `Verdict`s from a JSON fixture keyed by subject.

- [x] Tier 2 pipeline wired end to end (§10.7) —
      `spork.core.pipeline.tier2` (`Tier2Meta` + 13 modules +
      `build_tier2_pipeline()`/`process_tier2_message()`) composes all
      seven items above into one runnable pipeline: budget gate → LLM
      call → usage recording → verdict validation → confidence gating
      → action application/draft creation → audit → idempotency.
      `test_default.py` runs it end to end against `RecordedLLMClient`
      — a real escalated message gets a real (recorded) verdict, a
      real action applied, a real draft created, zero live API calls.
      Not one of the original 7 checklist items; called out separately
      since it's the integration work those items existed to enable.

**Exit criteria:** an escalated test email gets a sane structured verdict,
the corresponding action is applied, and a drafted reply lands in Drafts
un-sent. Budget cutoff verified by lowering `daily_call_budget` to 1 in a
test run. **All 7 items above, plus the Tier 2 pipeline wiring, are done
in the same sense M1's JMAP work is "done"** — every piece buildable
without a live account is real and tested; **not yet met** as an
end-to-end exit criterion, still blocked on the same live Fastmail
session M1 needs (`JmapClient.connect()`/`fetch_new_messages()`/
`apply_action()`/`create_draft()`) plus a live Anthropic API session
(`AnthropicLLMClient.get_verdict()`) to swap in for `RecordedLLMClient`.
One piece is deliberately still unbuilt even with those two live
sessions: deciding *which* escalated message needs a Tier 2 run — Tier
1's escalate branch already marks a message processed (the interim M2
policy), so `process_tier2_message()` can't reuse that idempotency
check to find pending work; that scheduling decision is real `sporkd`
main-loop work (M5), needing a live JMAP session to know what's
actually pending, not something invented here to appear more done than
it is.

## M4 — Alerting

**Goal:** the human actually finds out about Tier 3 / urgent mail without
polling the CLI.

- [ ] `Alerter` protocol + desktop backend (DBus/`notify-send`) (M)
- [ ] Webhook backend (ntfy/Pushover-style), URL from secretspec (S)
- [ ] Alert triggers wired to confidence bands + VIP rules + daemon health (M)
- [ ] Graceful degrade when no DBus session bus is available (S)

**Exit criteria:** a VIP-sender test email and a low-confidence test
email both produce a visible desktop notification; killing network
connectivity for 10+ minutes produces a "push disconnected" alert.

## M5 — CLI + daemon control surface

**Goal:** the full `spork` command surface from §12 works against a
running `sporkd` over the control socket.

- [ ] IPC protocol + Unix socket server in `sporkd` (M)
- [ ] `spork status` (queue depth, push state, today's LLM spend) (M)
- [ ] `spork pause`/`resume` (S)
- [ ] `spork rules list/edit/enable/disable` with live reload (M)
- [ ] `spork config show/edit` with validation on save (S)
- [ ] `spork logs` (tail, filter by message ID / time range) (S)
- [ ] `spork reclassify <id>` (S)

**Exit criteria:** every command in §12 works end-to-end against a live
daemon; editing `rules.toml` via `spork rules edit` takes effect without
a daemon restart.

## M6 — systemd packaging + install flow

**Goal:** a new user can go from clone to "running at every login" in a
few documented commands.

- [ ] `systemd/sporkd.service` unit file (§14) (S)
- [ ] `Type=notify` / `sd_notify` on ready (S)
- [ ] Install helper (`spork install-service` or a documented script) (S)
- [ ] README quickstart: secretspec setup → config → rules → enable unit (M)
- [ ] `spork doctor` checks unit install/enabled/active state (S)

**Exit criteria:** on a clean machine, following only the README quickstart
gets `sporkd` running under systemd at login, with `spork status` reporting
healthy.

## M7 — Hardening & v1 release

**Goal:** confident enough to run unattended against a real daily-driver
mailbox.

- [ ] Confidence threshold tuning pass against real triage volume (M)
- [ ] Rate-limit / 429 handling verified against Fastmail's real limits (S)
- [ ] Crash-loop / restart behavior verified (`Restart=on-failure`) (S)
- [ ] Security review pass against §15 (control socket perms, no
      secrets on disk, no send capability) (M)
- [ ] Full test suite green in CI; coverage of rule engine + action
      executor especially (M)
- [ ] Tag v1.0.0

**Exit criteria:** the daemon runs against the maintainer's real inbox for
a full week with no manual intervention beyond normal `spork` CLI use, and
no verdict-schema or action-executor bug reaches an unattended irreversible
action.

## Stretch / post-v1 (not scoped, not blocking)

- Sieve JMAP client (RFC 9661) so Tier 0 rules can be managed from `spork`
  itself instead of Fastmail's web UI (noted as an open risk in
  `DESIGN.md` §17).
- Natural-language rule authoring (describe a rule in English, Spork
  proposes a `rules.toml` entry, human reviews before enabling).
- Per-category auto-send opt-in, gated hard behind explicit, individually
  confirmed configuration — deliberately deferred, not default-on ever.
- Thread-level triage (act on a whole thread's disposition, not just the
  newest message).
- Weekly digest alert ("here's what auto-filed this week") as a
  lower-friction way to audit Tier 1/2 behavior than reading raw logs.
