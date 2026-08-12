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
polling the CLI. **v1 scope: Linux desktop notifications only** — a
webhook/ntfy/Pushover backend is real and useful but explicitly deferred
(see Stretch / post-v1 below), not because it's hard, just because
desktop-only covers the daily-driver use case this project targets.
**v1 backend is a logging `Alerter`, not a real desktop popup** — a
genuine, working delivery channel (structured, greppable log output),
not a stub; a `notify-send`/D-Bus backend is a deliberate near-term
follow-up behind the same `Alerter` protocol, not built this round.

- [x] `Alerter` protocol (mirrors the `Provider`/`LLMClient` adapter
      pattern, §9.3/§10.1/§12.1 — one Protocol, backends loaded the
      same `"module:ClassName"` way) + `LoggingAlerter` (M) —
      `AlertUrgency`'s low/normal/critical vocabulary checked against
      the real Desktop Notifications Specification and `notify-send(1)`
      before being settled; `LoggingAlerter` is a genuinely real
      backend (logs each alert via `logging.getLogger(__name__)`,
      never configures handlers itself), not a stub for the future
      desktop-notification backend.
- [ ] Alert triggers wired to confidence bands + VIP rules + daemon health (M)
      — the pipeline-visible half is done: `spork.core.pipeline.observer.PipelineObserver`
      (§12.2, bundles correlation-ID tracing with `Alerter` delegation —
      the "combine logging and alerting" decision) is injected into
      both `build_*_pipeline()`s; `RecordEscalationFilter` alerts on
      `Action.alert_immediately` (the flag a VIP-sender rule sets, now
      that `Condition.from_in` closes the schema gap §7.5's
      `vip-senders` example assumed all along —
      `extra="forbid"` would've rejected it before); `RecordAlertOnlyFilter`
      and `RecordBudgetExhaustedFilter` always alert;
      `ApplyVerdictActionFilter` alerts on `autoact_alert` or
      `verdict.urgency == "high"` regardless of band. **Daemon health
      is NOT done and can't be yet** — JMAP push disconnected /
      crash-looping are `sporkd` lifecycle events, not a
      `Payload`/`Pipeline.run()` for any message, so there's nothing
      for a pipeline module to attach to; needs the M5 daemon loop
      first. See docs/TEST_COVERAGE.md tests 318–346.
- [ ] Graceful degrade when no DBus session bus is available (e.g. no
      active desktop session — sporkd keeps running, alerts just don't
      display, logged instead) (S) — moot for now: `LoggingAlerter`
      has no DBus dependency to degrade from; this item is really
      "graceful degrade for the future desktop backend," revisit when
      that backend actually exists.

**Exit criteria:** a VIP-sender test email and a low-confidence test
email both produce a visible desktop notification; killing network
connectivity for 10+ minutes produces a "push disconnected" alert.
The first half is proven at the pipeline level today (`process_message()`/
`process_tier2_message()` called directly, `LoggingAlerter` standing in
for the still-future desktop popup); nothing produces a *visible
desktop* notification yet (that's the deferred `notify-send` backend),
and neither half runs against a live, running `sporkd` yet — that
needs M5's daemon loop.

## M5 — CLI + daemon control surface

**Goal:** the full `spork` command surface from §13 works against a
running `sporkd` over the control socket.

Two prerequisites landed as this milestone's own first items, not
silently assumed: `spork.core.config` didn't exist at all before this
milestone (flagged in `DESIGN.md` §6.1's component-tree caption, but
untracked as work anywhere), and `sporkd`'s event loop was never
actually assembled — `daemon/main.py` was still M0's `--version`-only
stub, and M1's own exit criteria said so explicitly ("sporkd runs, logs
each new inbox message's subject... **Not yet met**" — still true for
the JMAP-specific path, since that's genuinely blocked on a live
account, but no longer true of the loop itself). Neither was genuinely
blocked on a live JMAP account: both were buildable and testable
against `FileProvider` + `RecordedLLMClient` + `LoggingAlerter`, the
same "settle the real shape, let only the actual network leaf calls
stay `NotImplementedError`" pattern M1a/M1b/M3 used — not new scope
invented for M5, just work that had nowhere else on the roadmap to
live until M5 needed something to control.

- [x] `spork.core.config`: `SporkConfig`/`TieringConfig`/`BackendSpec`
      pydantic schema + `load_config()` (M) — three-tier precedence
      (system enforced `/etc/spork/enforced.toml` > user
      `$XDG_CONFIG_HOME/spork/config.toml` > system default via
      `$XDG_CONFIG_DIRS`), settled and documented in §7.2/§6.4 against
      the real XDG Base Directory Specification (v0.8) and comparable
      tools (`git`'s system/global scopes, Chromium/Firefox managed
      policy), not invented. `ConfigLoadError` wraps every failure
      mode, same convention as `RulesLoadError`/`ProviderLoadError`.
      Exit criterion's enforced-tier-wins test is real: see
      `docs/TEST_COVERAGE.md`'s `test_load_config_enforced_tier_overrides_user_tier`.
- [x] Daemon event loop assembly: `daemon/loop.py` composes
      `load_config()` → `Provider.build_source()` → Tier 1
      `process_message()` → `PipelineObserver`/`Alerter` → `StateDB`,
      as a real asyncio loop, blocking calls bridged via
      `asyncio.to_thread()` (§6.2.1) (M) — proven end-to-end against
      `FileProvider`; the JMAP-specific path stays the settled-shape
      `NotImplementedError` it already is (M1) until a live account
      exists to test against. **Tier 1 only this round** — chaining a
      freshly-escalated message into `process_tier2_message()` needs
      `to_addresses`/thread-history/`available_mailboxes` that nothing
      resolves yet (`NormalizedMessage` has no `to` field; `Provider`
      exposes no thread-history or mailbox-listing method); see the
      new item below. Also required: `StateDB`'s SQLite connection
      gains `check_same_thread=False` (§6.4's `spork.core.state` note)
      — safe under this loop's sequential (never concurrent)
      `to_thread` access pattern, not a general concurrency change.
- [ ] Wire Tier 2 into the daemon loop: resolve `to_addresses` (real
      data — parseable from `NormalizedMessage.headers`, not invented)
      and add whatever `Provider` capability thread-history/
      `available_mailboxes` actually needs (a new method on the
      `Provider` protocol, most likely) so an escalated message can
      flow straight into `process_tier2_message()` in the same poll
      cycle (S)
- [ ] IPC protocol + Unix socket server in `sporkd` (M) — newline-
      delimited JSON over the socket (§15's filesystem-permission
      model already rules out needing an auth scheme; no new
      dependency, human-inspectable with `nc`/`socat` while debugging)
- [ ] `spork status` (queue depth, push state, today's LLM spend) (M)
- [ ] `spork pause`/`resume` (S)
- [ ] `spork rules list/edit/enable/disable` with live reload (M)
- [ ] `spork config show/edit` with validation on save (S) — `edit`
      only ever opens the *user* tier (§7.2); `show` flags any value
      the enforced tier is overriding
- [ ] `spork logs` (tail, filter by message ID / time range) (S)
- [ ] `spork reclassify <id>` (S)

**Exit criteria:** every command in §13 works end-to-end against a live
daemon; editing `rules.toml` via `spork rules edit` takes effect without
a daemon restart; a value in `/etc/spork/enforced.toml` can't be
overridden by a user's own `config.toml`, verified by a test that
tries.

## M6 — systemd packaging + install flow

**Goal:** a new user can go from clone to "running at every login" in a
few documented commands — via the manual systemd install flow, or via
an Arch Linux package.

- [ ] `systemd/sporkd.service` unit file (§14) (S)
- [ ] `Type=notify` / `sd_notify` on ready (S)
- [ ] Install helper (`spork install-service` or a documented script) (S)
- [ ] README quickstart: secretspec setup → config → rules → enable unit (M)
- [ ] `spork doctor` checks unit install/enabled/active state (S)
- [ ] Arch Linux packaging: a `PKGBUILD` (AUR-style) that builds `spork`/
      `sporkd` and installs the systemd unit, so `makepkg -si` (and later
      an AUR submission) is a supported install path alongside the manual
      quickstart — not a second, divergent install story, the same
      package layout and unit file the quickstart uses (M)

**Exit criteria:** on a clean machine, following only the README quickstart
gets `sporkd` running under systemd at login, with `spork status` reporting
healthy. On Arch Linux, `makepkg -si` from the `PKGBUILD` produces the
same result.

## M7 — Hardening & v1 release

**Goal:** confident enough to run unattended against a real daily-driver
mailbox, with enough observability to actually explain what it did and
why after the fact — not just correctness, but the ability to debug and
audit correctness once it's running unattended.

- [ ] Confidence threshold tuning pass against real triage volume (M)
- [ ] Rate-limit / 429 handling verified against Fastmail's real limits (S)
- [ ] Crash-loop / restart behavior verified (`Restart=on-failure`) (S)
- [ ] Structured application logging: Python `logging` wired through
      `sporkd`/`spork` (level configurable via `config.toml`/CLI flag,
      journal-friendly output since M6 runs it under systemd) — separate
      from `audit_log` (§7.4), which is a per-message decision record,
      not an operational log stream (M)
- [ ] Per-message tracing through the pipeline: a correlation ID attached
      to a message at ingestion, threaded through every Tier 1/Tier 2
      Filter/Selector/Augment stage (§9.4/§10.7) and included in that
      message's log lines, so one message's full journey — which
      modules ran, in what order, how long each took — is reconstructable
      from logs alone. Lightweight and stdlib-based (the correlation ID
      + structured logging above); no distributed-tracing dependency
      (OpenTelemetry etc.) — this is a single-process daemon, not a
      distributed system, and a heavier dependency isn't justified (M)
- [ ] Audit trail completeness: extend `audit_log` beyond per-message
      triage outcomes to cover control-plane changes too — `spork rules
      enable/disable`, `spork config edit`, `spork pause`/`resume`,
      `spork reclassify` (M5) — so there's a full "what changed this
      daemon's behavior, and when" trail, not just "what happened to
      this message" (M)
- [ ] Security review pass against §15 (control socket perms, no
      secrets on disk, no send capability) (M)
- [ ] Full test suite green in CI; coverage of rule engine + action
      executor especially (M)
- [ ] Tag v1.0.0

**Exit criteria:** the daemon runs against the maintainer's real inbox for
a full week with no manual intervention beyond normal `spork` CLI use, and
no verdict-schema or action-executor bug reaches an unattended irreversible
action. A week's worth of triage decisions and every control-plane change
can be fully reconstructed from logs + the audit trail alone, without
needing to re-derive anything from memory.

## Stretch / post-v1 (not scoped, not blocking)

- Webhook `Alerter` backend (ntfy/Pushover-style, URL from secretspec) —
  deferred out of M4, which targets Linux desktop notifications only for
  v1. The `Alerter` protocol M4 builds makes this an additional backend
  loaded like any other, not a redesign, whenever it's actually wanted.
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
