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
- [ ] `secretspec.toml` with declared secrets (§7.3) (S) — tracked as
      `xfail`, `tests/test_secretspec_config.py`
- [x] Lint/format/type-check config (ruff + mypy or pyright) (S)
- [x] CI: lint, type-check, unit tests on push/PR (S)
- [ ] `spork --help` / `sporkd --help` produce real (if empty) output (S)
      — tracked as `xfail`, `tests/cli/test_main.py`,
      `tests/daemon/test_main.py`; blocked on a CLI framework choice
      (click vs. typer, §6.1, undecided)

**Exit criteria:** fresh clone → `uv sync && uv run sporkd --help` and
`uv run spork --help` both work with no manual setup beyond secrets.
**Not yet met** — both crash with `NotImplementedError` today.

## M1 — JMAP connectivity

**Goal:** the daemon can authenticate, resolve mailboxes, and fetch mail
read-only. No actions taken yet.

- [ ] `spork.core.jmap.client`: session bootstrap via `jmapc`, secrets
      wired through `secretspec` (M) — shape settled, `connect()` and
      `fetch_new_messages()` (also covers the `Email/query`+`Email/get`
      batched fetch item below) deliberately raise `NotImplementedError`:
      a real jmapc session against a live Fastmail account is real-network
      work this environment can't exercise honestly. See
      `tests/core/jmap/test_client.py`.
- [x] Mailbox role resolution + caching (Inbox, Drafts, custom mailboxes) (S)
- [ ] ~~`Email/query` + `Email/get` batched fetch of new mail since a cursor (M)~~
      — folded into `JmapClient.fetch_new_messages()` above, same status.
- [ ] EventSource push listener with reconnect/backoff (M) — backoff
      *scheduling* is done and tested (`spork.core.jmap.backoff`); the
      listener itself (`JmapPushTrigger.wait()`) is a settled-shape
      `NotImplementedError` stub for the same live-connection reason as
      the client. See `tests/core/jmap/test_push.py`.
- [x] Poll-based fallback when push is unavailable/disconnected (S) —
      real, tested implementation (`spork.core.sources.timer.IntervalTimer`
      + `spork.core.sources.fallback.FallbackSource`), pure control flow
      with no network dependency. Ready to compose with a real
      `JmapClient`-backed fetcher once that exists.
- [x] State DB: `push_cursor`, `processed_messages` tables + migrations (S)
- [ ] `spork doctor` reports JMAP auth + connectivity status (S) —
      deferred to M5: it's a CLI command, and the CLI framework (§6.1:
      click or typer) isn't chosen yet. The connectivity check it will
      call is blocked on `JmapClient.connect()` above regardless.

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

## M2 — Rule engine (Tier 1) + action executor

**Goal:** deterministic rules file drives real mailbox actions, no LLM
involved yet.

- [ ] Rule schema + `rules.toml` loader/validator (§7.5) (M)
- [ ] Tier 1 evaluator (first-match-wins, closed condition set) (M)
- [ ] Action executor: move/tag via `Email/set` `mailboxIds` (M)
- [ ] `processed_messages` idempotency check before acting (S)
- [ ] `audit_log` writes for every action taken (S)
- [ ] `spork rules test <file>` dry-run against recent mail, no side effects (M)
- [ ] Unit tests: condition matching, dry-run output, idempotency (M)

**Exit criteria:** a hand-written `rules.toml` with 3–4 real rules
correctly files live test mail with no LLM calls; `spork rules test`
matches what actually happens when the rule goes live.

## M3 — LLM escalation (Tier 2)

**Goal:** unmatched/escalated mail gets a real Claude verdict and it
drives an action.

- [ ] Body cleaning: HTML strip, quote-chain collapse, truncation (M)
- [ ] Claude client wrapper + structured verdict schema (§10) (M)
- [ ] Verdict validation against configured mailbox/category set (S)
- [ ] Confidence-band logic: autoact / autoact+alert / alert-only (§9) (M)
- [ ] `daily_call_budget` enforcement + `llm_usage` tracking (S)
- [ ] Draft creation path (`Email/set` into Drafts, never `EmailSubmission`) (M)
- [ ] Recorded-response fixtures for CI (no live API calls in tests) (M)

**Exit criteria:** an escalated test email gets a sane structured verdict,
the corresponding action is applied, and a drafted reply lands in Drafts
un-sent. Budget cutoff verified by lowering `daily_call_budget` to 1 in a
test run.

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
