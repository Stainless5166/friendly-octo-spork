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

- [x] `spork.core.providers.jmap.client`: session bootstrap via `jmapc`, secrets
      wired through `secretspec` (M) — `connect()` performs authenticated
      session discovery and Inbox-role resolution; `fetch_new_messages()`
      baselines without replaying history, then uses cursor-correct
      `Email/changes`+`Email/get` paging and returns a candidate Email-state
      checkpoint with normalized Inbox messages. The earlier “Email/query
      since cursor” wording was not valid JMAP and has been removed. CI uses
      injected jmapc-shaped responses; the production factory and baseline
      were also exercised successfully against the maintainer's live Fastmail
      account without retrieving historical message bodies.
- [x] Mailbox role resolution + caching (Inbox, Drafts, custom mailboxes) (S)
- [x] ~~`Email/changes` + `Email/get` batched fetch of new mail since a cursor (M)~~
      — folded into `JmapClient.fetch_new_messages()` above, same status.
- [x] EventSource push listener with reconnect/backoff (M) — backoff
      scheduling, account/event filtering, transient disconnect handling,
      and checkpoint-preserving polling fallback are implemented. Live
      Fastmail push/reconnect acceptance remains part of the M1 exit
      criterion. Disconnect-duration alerting remains separately tracked
      under M4. **Finding from M1c's fault-injection harness** (real
      transport, not a fake): `jmapc`'s SSE layer (`sseclient`) swallows
      a clean end-of-stream and silently retries on its own fixed 3s
      timer *inside* `client.events`, before `JmapPushTrigger` ever sees
      an exception — `reconnect_backoff` only actually engages once that
      internal retry itself fails, not on the first disconnect. Not yet
      a filed gap/fix — recorded here so it isn't lost before a
      deliberate decision (accept the double-layer retry, or bypass
      `sseclient`'s reconnect and drive `EventSource` directly).
- [x] Poll-based fallback when push is unavailable/disconnected (S) —
      real, tested implementation (`spork.core.sources.timer.IntervalTimer`
      + `spork.core.sources.fallback.FallbackSource`), pure control flow
      with no network dependency. Ready to compose with a real
      `JmapClient`-backed fetcher once that exists.
- [x] State DB: `push_cursor`, `processed_messages` tables + migrations (S)
- [x] Cursor-safe daemon acknowledgement (M) — `CheckpointedSource` returns
      an immutable `MessageBatch`; `sporkd` reads the account cursor before
      composing JMAP, processes the complete batch, and persists the candidate
      state only after success. Empty batches advance state; failures and
      shutdowns leave the previous cursor for replay on restart.
 - [x] `spork doctor` reports JMAP auth + connectivity status (S) — CLI
       wiring is real (the earlier "CLI framework isn't chosen yet"
       note is stale: Typer's been in use since M2's `spork rules
       test`). The check now builds the configured provider and calls its
       checkpoint capability's `account_id()`; non-JMAP providers report
       that the check is not applicable. Secrets/systemd/DB checks from
       docs/DESIGN.md §12 remain independently reported, never hidden behind
       a failed config or provider check.

**Exit criteria:** `sporkd` runs, logs each new inbox message's subject
as it arrives (via push, verified by sending a real test email), survives
a forced network drop and reconnects. **Partially met.** The
push-via-real-test-email half is now live-verified:
`docs/acceptance/steps/m1.py`'s `@push` binding sends a real tagged
message through the operator's SMTP relay, opens the real EventSource
connection first, and confirms the resulting state event, fetch, and
cursor advance all happen for real
(`SPORK_ACCEPTANCE_LIVE=1 uv run behave --tags="m1 and push"` — 1
feature passed, 12 steps passed). The forced-network-drop/reconnect
half remains open — `@network-recovery` needs actual network-level
outage control (iptables/unplugging) this environment can't safely
automate; `@cursor-safety` needs a real `sporkd` restart cycle, same
reason.

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
- [x] `spork.core.classify.keyword.KeywordClassifier`: the
      dependency-free default backend §9.1 always documented but never
      shipped (S) — confirmed via `grep -rn "register(" src/spork`
      returning nothing outside `registry.py` itself: `tiering.local_classifier`
      was completely non-functional in every real deployment, since
      nothing anywhere ever called `registry.register()`. Scores each
      configured category by the fraction of its own keyword list
      matched (case-insensitive substring), not a raw count; falls
      back to a named `"uncategorized"` default when nothing matches.
      Self-registers as `"keyword_heuristic"` (matching §7.2's example
      config.toml, which has named it that since before this existed)
      as an import-time side effect of `spork.core.classify.__init__`
      — every real caller already imports that package, so this needed
      zero changes to `daemon/loop.py`/any CLI command.

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

## M1c — Test harness & corpus tooling

**Goal:** a mitmproxy-based fault-injection harness for `JmapClient`
that doubles as the recorder for a JMAP response corpus, plus a real
LLM corpus built from the `RecordingLLMClient` wrapper that already
exists (`spork.core.llm.recording`). Unblocks the two acceptance
scenarios that are currently manual-only (`@fallback`,
`@network-recovery` in `docs/acceptance/m1_jmap.feature`) and gives
M8 (backfill) a real, varied corpus to build the retroactive-run
against instead of hand-written fixtures. M8 depends on this
milestone; this milestone does not depend on M8.

- [x] `tests/support/jmap_mitm.py`: an in-process mitmproxy instance
      driving the real, unmodified production `client_factory` (real
      `jmapc.Client`, not a fake) through a local proxy, with an addon
      answering session discovery/API calls/EventSource from canned
      responses and injecting faults (truncated body, synthetic
      429+`Retry-After`, added latency, EventSource disconnect) —
      6 acceptance tests in
      `tests/core/providers/jmap/test_mitm_fault_injection.py`, all
      passing against the real `JmapClient`/`JmapPushTrigger` error
      boundaries (M). Surfaced a real finding about the *existing*
      push path, not a harness bug — see this file's M1 EventSource
      item above.
- [x] `tests/fixtures/jmap/flows/`: recorded `Session`/`Mailbox/get`/
      `Email/get`/`Email/changes`/EventSource flows captured once
      against the live read-only account, via the mitm harness's own
      embedding (`save_stream_file`, mitmdump's underlying mechanism)
      rather than a separate CLI invocation — `m1_live_session.flow`
      (baseline + a no-op changes cycle) and `m1_live_push.flow` (a
      **real** EventSource push event, triggered by one live test
      email, captured start to finish). Gitignored like
      `tests/fixtures/corpus/`. The real `Authorization: Bearer …`
      token was captured in every request by mitmproxy as normal proxy
      traffic and has been redacted post-capture (rewritten to `Bearer
      REDACTED` via `mitmproxy.io.FlowWriter`) — the session response
      body still contains the account's real username/email and its
      real mailbox name list (no message bodies: every captured fetch
      returned an empty batch), which is real-account content by the
      same privacy rule as the corpus, kept local/gitignored only, not
      further scrubbed (S). **Now wired in:**
      `jmap_mitm_harness(replay_flows=[...])` loads mitmproxy's own
      `ServerPlayback` addon against these files — a matching request
      is answered from the real recorded shape, ahead of and
      independent from the harness's hand-built canned responses
      (which still cover anything a recording doesn't).
      `test_flow_replay.py` proves it end to end with zero canned
      responses configured, and skips (not fails) when the gitignored
      flow file isn't present — verified both the pass and the skip
      path locally. `test_mitm_fault_injection.py`'s existing tests
      still use hand-built canned responses, unchanged; nothing
      required them to switch.
- [x] Automatable, non-`@manual` coverage of the `@fallback` guarantee:
      `docs/acceptance/m1_jmap_fault_injection.feature` +
      `docs/acceptance/steps/m1_fault_injection.py`, driving the real
      `JmapProvider.build_checkpointed_source()` composition (push
      primary + poll secondary, shared cursor) through the harness (M).
      Deliberately a new, separate feature rather than binding
      `m1.py`'s existing `@fallback`/`@network-recovery` steps
      directly: those scenarios' `Background` requires a real Fastmail
      account/token, which a harness-driven run doesn't have and
      shouldn't fake having — see docs/acceptance/README.md. Runs on
      every `uv run behave`, no opt-in required. `@network-recovery`'s
      sustained-outage-with-eventual-delivery shape (not just a single
      disconnect/recover cycle) remains live-only — a real forced
      network drop against a real account is still the honest way to
      prove that, not a simulated timer.
- [x] Build an initial `tests/fixtures/corpus/live.jsonl` by wrapping
      the configured `LiteLLMClient` with `RecordingLLMClient` and
      running it over a diverse hand-picked sample of real mail (S) —
      seeds the corpus ahead of the much larger backfill-driven pass
      in M8. 14 tagged sample emails (`[spork-corpus-test]` subject
      prefix) sent via real SMTP across two batches — newsletter,
      receipt, personal, security-notification, promo/spam-like,
      urgent-invoice, calendar-invite, shipping-notification,
      subscription-renewal, recruiting-outreach, event-webinar,
      survey-request, legal-terms-update, appointment-reminder (a 15th,
      a push-recording trigger email, has no distinct triage category
      and wasn't corpus-seeded). Second batch fetched via the new
      `query_messages()` (M8) rather than a cursor, doubling as a real
      usage smoke test of it. **13 of 14 categorizable samples produced
      valid verdicts and are in the corpus** (one, the "50% off"
      promo, was initially thought Junk-filtered — turned out to be
      Fastmail indexing lag, not a real spam-filter action, but wasn't
      re-fetched for the corpus; low priority to backfill). 15 emails
      sent this session total, within the 25-email session budget.
      Genuinely large-volume, backfill-driven diversity is still what
      M8's full backfill run is for — this is a hand-picked seed, not
      a substitute for that.

**Exit criteria:** `pytest` can force an EventSource disconnect and a
JMAP request-level fault through the mitmproxy harness and assert
`JmapClient`'s existing reconnect/backoff/fallback behavior handles
both, with no real network or live account involved in the test run
itself; the two previously-manual M1 acceptance scenarios have real
step bindings; an initial LLM corpus file exists and
`RecordedLLMClient` can replay it.

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
- [x] Replace the direct-Anthropic settled-shape stub with a real
      in-process `LiteLLMClient` using a forced `deliver_verdict` tool
      call; add exact prompt construction, real token usage, and an
      append-only acceptance-corpus recorder. `litellm` is an optional
      `spork[llm]` dependency; LiteLLM proxy mode is explicitly out of
      scope for v1. Live corpora are written under the gitignored
      `tests/fixtures/corpus/` and may be supplied privately to CI from
      S3 later (M) — implemented with an SDK-independent prompt
      builder, lazy optional import, mocked upstream acceptance tests,
      real usage propagation, and 100% coverage on the changed LLM/Tier
      2 modules.
- [x] Verdict validation against configured mailbox/category set (S) —
      `spork.core.llm.validate.validate_verdict()` (§10.2): checks
      `category`/`suggested_action.mailbox` against sets passed in
      already resolved from config — pure logic, no `Provider`/JMAP
      dependency, no live-account blocker.
- [x] Confidence-band logic: autoact / autoact+alert / alert-only (§9) (M) —
      `spork.core.llm.confidence.confidence_band()` (§10.3): a pure
      function of confidence + the two `config.toml` thresholds, with
      an eager `ValueError` guard against a misconfigured
      `alert_threshold > autoact_threshold`. **Finding from M1c's live
      corpus-seeding run** (real Claude call, not a fixture): given a
      genuinely ambiguous email (a personal "want to get dinner
      Friday?" note; an overdue-invoice notice), the live model twice
      returned `suggested_action.type = "escalate"` — the one value
      `Verdict`'s validator explicitly rejects
      (`spork.core.llm.base._suggested_action_must_be_terminal`),
      failing the call outright instead of producing a usable verdict.
      `alert_only` (low `confidence`, a terminal action) is exactly
      the schema's intended way to express "a human should look at
      this" — but `build_prompt()`'s system message
      (`spork.core.llm.prompt`) never says so, and the tool's JSON
      schema still legally allows `"escalate"` in the enum (shared
      with Tier 1's `Action.type`), so the model reaches for the
      semantically obvious-but-illegal choice. **Fixed:** both
      candidate fixes applied —
      `spork.core.llm.prompt.verdict_tool_schema()` strips
      `"escalate"` from the tool's `suggested_action.type` enum before
      it reaches the model, and the system prompt now explicitly says
      uncertainty belongs in `confidence`, not the action type.
      Live-verified against the same two messages that failed before
      (no new emails sent): both now return valid terminal actions
      with appropriately moderate confidence. Corpus grew from 3 to 5
      entries as a result.
- [x] `daily_call_budget` enforcement + `llm_usage` tracking (S) —
      `StateDB` gains an `llm_usage` table + `record_llm_call()`/
      `get_llm_usage()` (§7.4, §10.4); `spork.core.llm.budget.has_budget_remaining()`
      is the pure enforcement half, decoupled from `StateDB` the same
      way `confidence_band()` is decoupled from `Verdict`.
- [x] Draft creation path (`Email/set` into Drafts, never `EmailSubmission`) (M) —
      `Provider` gains `build_draft_creator()` (§9.3, §10.6); `JmapClient.create_draft()`
      is a fourth settled-shape `NotImplementedError` stub (needs a
      live Fastmail write contract, unlike the now-real read-only
      `connect()`/`fetch_new_messages()` path); `FileProvider.build_draft_creator()` is real,
      appending to a second JSON-lines log distinct from the actions
      one. Never wired to `EmailSubmission` anywhere — §11's invariant
      enforced by omission.
- [x] Recorded-response fixtures for CI (no live API calls in tests) (M) —
      `spork.core.llm.clients.recorded.RecordedLLMClient` (§10.5): the
      `LLMClient` equivalent of `FileProvider` — a second, fully real
      adapter with no `NotImplementedError` anywhere, replaying
      pre-recorded `Verdict`s from a JSON fixture keyed by subject.

- [x] Category taxonomy actually sent to the model, plus a freeform
      metadata field on `Verdict` (S) — a real gap, not a hypothetical
      one: `TieringConfig.allowed_categories` only ever reached
      `ValidateVerdictFilter`'s post-hoc check
      (`spork.core.llm.validate.validate_verdict()`); the model itself
      was never told the configured category set, despite the system
      prompt already claiming "Choose category and mailbox only from
      the values supplied in the user message" for mailboxes. Fixed:
      `VerdictRequest` gains `available_categories: tuple[str, ...]`,
      `build_prompt()` includes it in the exact user-message JSON
      alongside `available_mailboxes`, and `BuildVerdictRequestFilter`
      takes `available_categories` as a constructor argument (the same
      relationship `max_body_chars` already has to it — a
      deployment-config value, not a per-message `Provider` read).
      Also added `Verdict.metadata: dict[str, str] = {}` — freeform
      extracted data (dates, order numbers, reference ids) the model
      judges worth surfacing from one specific email, deliberately
      open-ended and never validated against any configured set,
      unlike `category`/`suggested_action.mailbox`. String-valued
      only (not `dict[str, Any]`) so the forced tool schema stays a
      flat, deterministic object.
- [x] Tier 2 pipeline wired end to end (§10.7) —
      `spork.core.pipeline.tier2` (`Tier2Meta` + 13 modules +
      `build_tier2_pipeline()`/`process_tier2_message()`) composes the
      seven original items into one runnable pipeline: budget gate → LLM
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
test run. **All 7 original items above, plus the Tier 2 pipeline wiring,
are done in the same sense M1's JMAP work is "done"; the LiteLLM
integration follow-up is now done too.** The exit
criterion is still **not yet met** as an
end-to-end exit criterion, still blocked on the Fastmail write path
(`JmapClient.apply_action()`/`create_draft()`) plus a live model API session through
`LiteLLMClient` to swap in for `RecordedLLMClient`.
One piece is deliberately still unbuilt even with those two live
  sessions: deciding *which* escalated message needs a Tier 2 run remains
  real `sporkd` main-loop work (M5). Tier 1 now leaves escalations pending
  and Tier 2 owns the terminal processed mark, so failed Tier 2 work can
  be retried; the scheduling decision still needs a live JMAP session and
  is not invented here to appear more done than it is.

## M4 — Alerting

**Goal:** the human actually finds out about Tier 3 / urgent mail without
polling the CLI. **v1 scope: Linux desktop notifications only** — a
webhook/ntfy/Pushover backend is real and useful but explicitly deferred
(see Stretch / post-v1 below), not because it's hard, just because
desktop-only covers the daily-driver use case this project targets.
**`LoggingAlerter` shipped first as a genuine, working delivery
channel** (structured, greppable log output, not a stub), with a real
`notify-send`/D-Bus backend, `DesktopAlerter`, following behind the
same `Alerter` protocol once this round's other work was done — now
built, and `LoggingAlerter` stays on as its fallback destination
rather than being retired.

- [x] `Alerter` protocol (mirrors the `Provider`/`LLMClient` adapter
      pattern, §9.3/§10.1/§12.1 — one Protocol, backends loaded the
      same `"module:ClassName"` way) + `LoggingAlerter` (M) —
      `AlertUrgency`'s low/normal/critical vocabulary checked against
      the real Desktop Notifications Specification and `notify-send(1)`
      before being settled; `LoggingAlerter` is a genuinely real
      backend (logs each alert via `logging.getLogger(__name__)`,
      never configures handlers itself), not a stub for the future
       desktop-notification backend.
- [x] SMTP alert backend for burn-in and unattended acceptance runs (S) —
      `spork.core.alerts.smtp.SmtpAlerter` supports authenticated STARTTLS
      delivery and an explicit plaintext mode for the local acceptance sink;
      credentials remain constructor inputs mapped through SecretSpec.
- [x] Real desktop-notification backend (M) —
      `spork.core.alerts.desktop.DesktopAlerter` wraps `notify-send(1)`
      (→ `org.freedesktop.Notifications` over the session D-Bus, no new
      DBus library dependency, per the design settled in §12.1).
      `runner` injected the same DI-for-subprocess pattern
      `install_service()` uses, so no test invokes a real
      `notify-send`. 5 acceptance tests
      (`tests/core/alerts/test_desktop.py`), 100% coverage on the new
      module. This item also closes the graceful-degrade item below —
      see there rather than duplicating.
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
      is now 1/2 done.** Of the two daemon-lifecycle signals actually
      in scope here (crash-loop detection was re-scoped to M6/systemd
      below, not this loop's job — a daemon babysitting its own
      restart count duplicates what systemd's `Restart=`/
      `StartLimitBurst` already does):
      - [x] **Daily LLM budget exhausted at the daemon level**
        (docs/DESIGN.md §12.3) — a one-shot-per-day critical alert,
        distinct from `RecordBudgetExhaustedFilter`'s existing
        per-message alert, wired into `_run_message_loop()` right
        after each escalation. Needed no live network to build
        honestly (it's a `StateDB` read `BudgetGateSelector` already
        does per message, asked once more from the loop), so it's the
        one daemon-health signal this item was actually blocked on
        M5's daemon loop for, not on anything else. See
        docs/TEST_COVERAGE.md tests 503–508.
      - [ ] **JMAP push disconnected > N minutes** — still genuinely
        blocked: detecting "disconnected" needs a live JMAP
        EventSource connection to have something to time out on in
        the first place (docs/ROADMAP.md M1). The design-gap comment
        lives directly on the stub it blocks:
        `spork.core.providers.jmap.push.JmapPushTrigger`.
- [x] Graceful degrade when no DBus session bus is available (e.g. no
      active desktop session — sporkd keeps running, alerts just don't
      display, logged instead) (S) — `DesktopAlerter`'s own job, not a
      separate mechanism: `notify-send` missing (not installed) or
      failing (no session D-Bus bus, a headless/SSH-only login) both
      fall back to a `LoggingAlerter` instead of raising. Two of the
      five acceptance tests above cover this directly (`FileNotFoundError`,
      `CalledProcessError`); a third confirms the default fallback
      (no explicit `fallback=` given) still works without losing the
      alert.

**Exit criteria:** a VIP-sender test email and a low-confidence test
email both produce a visible desktop notification; killing network
connectivity for 10+ minutes produces a "push disconnected" alert.
**Not yet met, but for a narrower reason than before:** the pipeline
wiring, `DesktopAlerter` itself, and `sporkd`'s daemon loop (M5) are
all real and tested now — nothing left to build offline.
`DesktopAlerter().notify(...)` was run live against this environment's
actual session D-Bus bus (`DISPLAY`/`DBUS_SESSION_BUS_ADDRESS` both
present) and completed with no exception — real evidence the
mechanism works end to end, not just against the injected-runner
tests — but that only confirms `notify-send` accepted and delivered
the call, not that a human actually saw the popup; visual confirmation
is the maintainer's to give. The "killing network connectivity for
10+ minutes" half is the same forced-outage control M1's
`@network-recovery` scenario is already blocked on, plus the still-open
"JMAP push disconnected > N minutes" daemon-health signal above.
Configuring `[alerts] spec =
"spork.core.alerts.desktop:DesktopAlerter"` on the maintainer's own
machine and confirming a real popup appears is the actual remaining
step, not further code.

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
- [x] Runtime backend composition: `BackendSpec.secret_kwargs` maps
      constructor arguments to SecretSpec names; daemon/doctor/
      reclassify resolve once and share the same provider/LLM/alerter
      builders. Optional `[llm_recording]` wraps the configured client
      with the private acceptance-corpus recorder. This closes a real
      gap: `spork doctor` validated secrets, but `sporkd` never resolved
      or passed them to any backend (M).
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
- [x] Wire Tier 2 into the daemon loop (S) — `to_addresses` parsed
      from `NormalizedMessage.headers["To"]` (real data, not
      invented); `Provider` gained `build_thread_history_reader()`/
      `build_mailbox_lister()` (§9.3) for the two reads
      `process_tier2_message()` needs, real against `FileProvider`,
      the same settled-shape `NotImplementedError` as every other
      `JmapProvider` leaf pending a live account. An escalated message
      now flows straight into `process_tier2_message()` in the same
      poll cycle, via a second, strictly-sequential `asyncio.to_thread()`
      call (§6.2.1) — `spork status`'s LLM-spend field stays deferred
      regardless (§6.2.2: no synchronization from `StateDB` into
      `DaemonState` yet, a separate gap from "Tier 2 doesn't run").
- [x] IPC protocol + Unix socket server in `sporkd` (M) — newline-
      delimited JSON over the socket (§15's filesystem-permission
      model already rules out needing an auth scheme; no new
      dependency, human-inspectable with `nc`/`socat` while debugging).
      `DaemonState`'s fields are touched only from coroutine code,
      never from inside `to_thread()`, so no lock is needed — see
      §6.2.2's note on the concurrent-`StateDB`-access bug this caught
      before any code was written.
- [x] `spork status` (M) — reports `paused`/`started_at` only; "queue
      depth", "push state", and "LLM spend vs budget" are explicitly
      deferred (§6.2.2), not fabricated with no backing data
- [x] `spork pause`/`resume` (S) — honest caveat: also stops fetching
      new mail, not just acting on it (`Source.poll()` fuses wait+fetch,
      §9.2); a real push connection "staying live" while paused isn't
      achievable without splitting that abstraction further, not done
      here
- [x] `spork rules list/edit/enable/disable` with live reload (M) —
      `RulesState` (`spork.daemon.state`) mirrors `DaemonState`: a new
      `reload` IPC command re-runs `load_rules()` and reassigns
      `rules_state.rules` wholesale on success (a single atomic
      reference swap, not an in-place mutation — safe with no lock,
      same reasoning as `DaemonState`), leaving it untouched on a
      `RulesLoadError` so a bad hand-edit can't take the daemon down.
      `_run_message_loop()` reads `rules_state.rules` fresh right after
      every `poll()` call, so a reload takes effect for the very next
      batch. `enable`/`disable` rewrite the whole file via
      `spork.core.rules.writer.dump_rules()` — a small purpose-built
      serializer for this closed schema, not a new dependency; real,
      stated tradeoff: comments/formatting in a hand-edited
      `rules.toml` don't survive it (`edit`, which only opens
      `$EDITOR`, is unaffected). Corrected two stale `docs/DESIGN.md`
      §13 claims found while building this: `spork status` doesn't
      actually report LLM spend yet, and `spork rules list` doesn't
      have per-rule match stats to show (that's `rule_stats`, a
      separate, still-unbuilt table behind a different command).
 - [x] `spork config init/show/edit` with validation on save (S) — `init`
      flags every value the enforced tier sets via a new
      `spork.core.config.loader.enforced_override_paths()` (flattens
      the enforced tier's raw TOML into dotted paths, independent of
      `load_config()`'s merge) and redacts any `kwargs` entry whose key
      looks like a credential (`token`/`key`/`secret`/`password`
      substring match — a stated heuristic, not a guarantee). `edit`
      only ever opens the *user* tier (§7.2), validates the real
      merged `load_config()` result on save, and — deliberately unlike
      `spork rules edit`/`enable`/`disable` — never pushes a live
      reload: config controls the `Provider`/`LLMClient`/`Alerter`
      objects `run_daemon()` only ever builds once at startup, not a
      plain list re-read every poll cycle, so "restart sporkd to
      apply" is the honest answer here.
- [x] `spork logs` (S) — reads `StateDB` directly, no socket/daemon
      needed; `--tail`/`--since` filter client-side, `--message-id`
      storage-side
- [x] `spork reclassify <id>` (S) — standalone, like `spork logs`: opens
      its own `Provider`/`StateDB` directly, works whether or not
      `sporkd` is running, no new IPC command needed. Safe under
      SQLite's WAL mode (already on, §7.4) plus `sqlite3.connect()`'s
      unmodified 5-second default busy timeout — a rare write
      collision with a running daemon is a bounded retry, not a
      correctness risk. `Provider` gained a sixth capability,
      `build_message_lookup()` (real against `FileProvider`,
      settled-shape `NotImplementedError` against `JmapProvider`, same
      split as the others); `process_message()`/`build_default_pipeline()`
      gained `force: bool = False`, which omits `IdempotencyGateSelector`
      from the composed pipeline entirely rather than consulting and
      overriding it. `spork.core.pipeline.tier2.escalate.{escalate_message,
      parse_to_addresses}` were extracted out of what was
      `spork.daemon.loop`'s private helpers, so the daemon loop and
      `spork reclassify` share one real Tier 2 escalation
      implementation instead of duplicating it.

**Exit criteria:** every command in §13 works end-to-end against a live
daemon; editing `rules.toml` via `spork rules edit` takes effect without
a daemon restart; a value in `/etc/spork/enforced.toml` can't be
overridden by a user's own `config.toml`, verified by a test that
tries.

## M6 — systemd packaging + install flow

**Goal:** a new user can go from clone to "running at every login" in a
few documented commands — via the manual systemd install flow, or via
an Arch Linux package.

- [x] `systemd/sporkd@.service` unit template (§14) (S) — tracked at the
      repo root, `Type=notify`/`Restart=on-failure`, no secret
      material in the unit itself; `spork.core.systemd.template.UNIT_FILE_CONTENT`
      is a byte-identical copy `install_service()` writes at runtime,
      drift-guarded by a test rather than read from the tracked file
      directly (an installed `spork` has no guaranteed-reachable path
      back to it).
- [x] `Type=notify` / `sd_notify` on ready (S) — `spork.core.systemd.notify.notify()`
      hand-rolls the real `AF_UNIX SOCK_DGRAM` wire protocol against
      the stdlib `socket` module (no new dependency, same call
      `llm/clean.py`'s hand-rolled `HTMLParser` made); `run_daemon()`
      calls it once provider/rules/LLM client/alerter/IPC server have
      all composed successfully, right before opening `StateDB` and
      starting the message loop.
- [x] Install helper (`spork install-service [<instance>]` or a documented script) (S) —
      built as a real command: `spork.core.systemd.install.install_service()`
      writes the unit file to `resolve_user_unit_path()` (creating
      `~/.config/systemd/user/` if needed), then `systemctl --user
      daemon-reload` + (unless `--no-enable-now`) `enable --now
      sporkd@<instance>`, one `InstallServiceError` wrapping every failure.
- [x] README quickstart: secretspec setup → config → rules → enable unit (M)
- [x] `spork secrets enroll` writes required credentials to the
      SecretSpec OS keyring scope without requiring the daemon to be running
      (S)
- [x] `spork doctor` checks unit install/enabled/active state (S) —
      `spork.core.systemd.unit.check_unit_status()`, reported as one
      of `spork doctor`'s checks; a missing `systemctl` binary or an
      unreachable user session bus (confirmed real in this project's
      own dev sandbox) reports `"unknown"`, never crashes.
- [x] `spork doctor` wires in the secrets/config/provider checks
      docs/DESIGN.md §7.3/§9.1/§9.3 describe (`secretspec check`
      equivalent, `load_config()`/`load_provider()`/`load_rules()`
      called eagerly and any `ConfigLoadError`/`ProviderLoadError`/
      `RulesLoadError`/`UnknownClassifierError` reported in plain
      language) — no longer blocked on `spork.core.config` not
      existing (that landed in M5); genuinely new scope, not assumed
      done by any of M5's items (S) — `spork doctor` is now seven
      independent checks (secrets, config, provider, rules, the
      configured local classifier if any, JMAP connectivity, the
      systemd unit above), each its own `[ok]`/`[FAIL]` line, unlike
      every other command in this codebase it never stops at the
      first failure. One real gap found and fixed along the way:
      SecretSpec 0.18.0's Python SDK resolves the secrets *provider*
      from a separate, genuinely global
      `~/.config/secretspec/config.toml` — the manifest's own
      `[providers]` table §7.3's example shows is real (what the
      separate `secretspec` CLI reads) but is silently ignored by the
      SDK's `resolve()` without an explicit `provider=` argument,
      confirmed empirically against the installed library, not
      assumed; `resolve_secretspec_path()` resolves the installed
      manifest's own location (colocated with `config.toml`), §7.3
      updated to describe this correctly.
- [x] Arch Linux packaging: a `PKGBUILD` (AUR-style) that builds `spork`/
      `sporkd` and installs the systemd unit, so `makepkg -si` (and later
      an AUR submission) is a supported install path alongside the manual
      quickstart — not a second, divergent install story, the same
      package layout and unit file the quickstart uses (M) — builds
      directly from a full source checkout via `uv build --wheel` (a
      real tagged-release `source=()` tarball is follow-up AUR-submission
      work, not this round); installs the same tracked unit file to
      the vendor path (`/usr/lib/systemd/user/`, not
      `~/.config/systemd/user/`). `python-secretspec` has no known
      Arch/AUR package as of this writing — noted honestly in the
      file rather than invented. `makepkg`/`pacman` aren't available
      in this sandbox (confirmed, Ubuntu) — the same
      can't-exercise-honestly-here situation `JmapClient.connect()` is
      in, just for a shell script; what's checkable without Arch
      tooling (syntax validity, required fields, the unit-file install
      path) is real and tested.

**Exit criteria:** on a clean machine, following only the README quickstart
gets `sporkd` running under systemd at login, with `spork status` reporting
healthy. On Arch Linux, `makepkg -si` from the `PKGBUILD` produces the
same result. **All 8 checklist items above are done in the same sense
every prior milestone's items are** — everything buildable and testable
without a live JMAP/Anthropic account or an actual Arch machine is real
and tested (604 tests, this milestone's own). **The exit criterion
itself is not yet met**, and can't be until M1 is: `sporkd` under a
freshly-installed unit still can't stay up against a real Fastmail
      account, because cursor-safe daemon ingestion and JMAP push remain
      incomplete — the first live poll still reaches the push-listener stub,
      taking the daemon down shortly after
`sd_notify`'s own `READY=1` fires. Every piece of *this* milestone's
own scope (the unit file, `sd_notify`, the install flow, `spork
doctor`'s checks, the package) is real; "running healthy against a
real account" was never this milestone's blocker to unblock — it's
M1's, same as `spork rules test`'s live-fetch gap always was.

## M7 — Hardening & v1 release

**Goal:** confident enough to run unattended against a real daily-driver
mailbox, with enough observability to actually explain what it did and
why after the fact — not just correctness, but the ability to debug and
audit correctness once it's running unattended.

- [ ] Confidence threshold tuning pass against real triage volume (M) —
      genuinely blocked: needs real triage decisions from a live
      account to tune against, same live-account blocker every prior
      milestone's "not yet met" items share. Nothing to invent here
      that wouldn't be tuning against fabricated data.
- [ ] Rate-limit / 429 handling verified against Fastmail's real limits (S) —
      genuinely blocked, same live-account reasoning; there's no real
      429 response to verify against without one.
- [ ] Crash-loop / restart behavior verified (`Restart=on-failure`) (S) —
      the unit file itself has carried `Restart=on-failure` since M6
      (`systemd/sporkd@.service`); *verifying* it needs a real systemd
      user session actually restarting a crashed `sporkd`, which this
      sandbox doesn't have either (confirmed, M6: no `systemctl`/`pacman`
      tooling here) — not re-confirmed instead of genuinely verified.
- [x] Structured application logging: Python `logging` wired through
      `sporkd`/`spork` (level configurable via `config.toml`/CLI flag,
      journal-friendly output since M6 runs it under systemd) — separate
      from `audit_log` (§7.4), which is a per-message decision record,
      not an operational log stream (M) — `spork.core.logging_setup.configure_logging()`:
      one journal-friendly `StreamHandler` (no timestamp — journald
      stamps its own; `extra` fields appended generically, the same
      mechanism `PipelineObserver.trace()` already used for
      `correlation_id`), no new dependency
      (`systemd.journal.JournalHandler`), same call `sd_notify`'s own
      hand-rolled implementation made (M6). `SporkConfig.log_level`
      (default `"INFO"`); `sporkd --log-level` overrides it, never
      merged; `spork --log-level` defaults to `"WARNING"` (a
      short-lived CLI, not the daemon).
- [x] Per-message tracing through the pipeline: a correlation ID attached
      to a message at ingestion, threaded through every Tier 1/Tier 2
      Filter/Selector/Augment stage (§9.4/§10.7) and included in that
      message's log lines, so one message's full journey — which
      modules ran, in what order, how long each took — is reconstructable
      from logs alone. Lightweight and stdlib-based (the correlation ID
      + structured logging above); no distributed-tracing dependency
      (OpenTelemetry etc.) — this is a single-process daemon, not a
      distributed system, and a heavier dependency isn't justified (M) —
      `spork.core.pipeline.tracing.{TracingStage,TracingSelector}`: a
      generic wrapper around any `Filter`/`Augment`/`Selector`, applied
      by `build_default_pipeline()`/`build_tier2_pipeline()` at
      composition time to every stage they compose — no change to any
      of the 8+13 concrete module classes, or to what their existing
      bare-`Payload` unit tests exercise. Cross-tier stitching (Tier
      1's correlation ID into Tier 2's, on escalation) stays a real,
      separately-tracked open gap (§12.2) — not part of what this item
      resolves.
- [x] Audit trail completeness: extend `audit_log` beyond per-message
      triage outcomes to cover control-plane changes too — `spork rules
      enable/disable`, `spork config edit`, `spork pause`/`resume`,
      `spork reclassify` (M5) — so there's a full "what changed this
      daemon's behavior, and when" trail, not just "what happened to
      this message" (M) — `StateDB.write_control_plane_audit_entry()`
      (`jmap_id=""` sentinel, no schema change/migration needed).
      `pause`/`resume` needed real design work, not just plumbing: a
      first-draft "make the IPC handler async, write directly" doesn't
      actually serialize against `_run_message_loop()`'s own in-flight
      `to_thread(process_message, ...)` call — fixed by queuing a
      `PendingAuditEvent` onto `DaemonState` instead (an in-memory
      append, same as flipping `.paused`) and having
      `_run_message_loop()` — the one code path that already safely
      owns every `StateDB` access — drain it each iteration, even
      while paused. One stated tradeoff: a pause/resume entry lands on
      the next iteration, not synchronously with the IPC response.
- [x] Security review pass against §15 (control socket perms, no
      secrets on disk, no send capability) (M) — verified all six of
      §15's claims against the actual code (grepped for `eval`/`exec`/
      `pickle`/`shell=True`/`EmailSubmission`/`smtp`, not just re-read
      the doc). Two real gaps found and fixed, not just documented:
      the README never actually disclosed that ambiguous mail goes to
      Claude despite §15 explicitly claiming it did (added a real
      Privacy note); `Secrets` (`spork.core.secrets`) is a plain
      `@dataclass` whose default `__repr__` printed every resolved
      secret's real value verbatim — confirmed empirically before
      fixing (`repr=False` + a custom `__repr__` showing only the
      declared names).
- [x] Full test suite green in CI; coverage of rule engine + action
      executor especially (M) — `spork.core.rules`/`spork.core.actions.executor`
      were already at 100% line *and* branch coverage before this
      pass, with real edge-case tests already covering every
      documented behavioral claim (AND semantics across multiple
      `Condition` fields, classifier invoked at most once, `escalate`
      rejected outright, `move`/`tag` rejected without a mailbox) —
      prior milestones' own TDD discipline already met this, confirmed
      rather than assumed. One small, cheap gap found and closed
      opportunistically while checking the rest of the suite's
      coverage: `spork pause`/`resume` had no test for a missing
      `config.toml` (`spork status` already did). 653 tests, ruff+mypy
      clean.
- [x] Poison-message resiliency: a single malformed Tier 2 verdict
      (out-of-set category/mailbox, a malformed suggested action, a
      failed LLM call) must never crash `_run_message_loop()`/`spork
      reclassify`/`spork backfill` outright and leave the offending
      message stuck retrying forever on every subsequent run — it
      needs to be quarantined once, loudly, and left alone (M) —
      `spork.core.pipeline.tier2.escalate.escalate_message_or_quarantine()`
      wraps `escalate_message()`, catching a narrow, explicit tuple
      (`QUARANTINABLE_ERRORS`: `LiteLLMClientError`,
      `VerdictValidationError`, `ActionExecutionError` — deliberately
      not a bare `except Exception`, so a genuine pipeline bug still
      surfaces instead of being silently swallowed), writing a
      `tier2_quarantined` audit entry, marking the message processed
      (`action_taken="quarantined"`) so it isn't retried forever, and
      firing a `critical`-urgency alert. Returns a new `QuarantinedMessage`
      dataclass (distinct from `Verdict`/`None`) that all three callers
      now branch on and report explicitly rather than letting the
      original `escalate_message()` exception propagate uncaught.
- [ ] Tag v1.0.0 — not done here: gated on this milestone's own exit
      criteria (below), which are gated on a live account this
      environment doesn't have. A real-world-readiness call for the
      maintainer to make once that week actually happens, not
      something to do from this sandbox.

**Exit criteria:** the daemon runs against the maintainer's real inbox for
a full week with no manual intervention beyond normal `spork` CLI use, and
no verdict-schema or action-executor bug reaches an unattended irreversible
action. A week's worth of triage decisions and every control-plane change
can be fully reconstructed from logs + the audit trail alone, without
needing to re-derive anything from memory. **6 of 10 checklist items above
are done in the same sense every prior milestone's buildable-without-a-
live-account items are** — real and tested. **The
exit criterion itself is not met, and can't be from this sandbox**: it
needs a live JMAP account (still M1's blocker) and a live Anthropic
account running unattended for a full week, neither available here. The
three remaining checklist items (confidence tuning, rate-limit
verification, crash-loop verification) and the exit criterion all share
that one blocker — not new scope invented for M7, the same one M1's own
exit criteria has stated since the beginning.

## M7a — Mutation & fuzz testing hardening

**Goal:** verify that the modules already at 100% line coverage are
actually *checked*, not just executed — property-based tests catch
input shapes example-based tests never tried, mutation testing catches
assertions weak enough to survive a deliberately wrong implementation.
Scoped to spork's actual decision logic (docs/DESIGN.md §16.1/§16.2):
`spork.core.rules.engine`, `spork.core.actions.executor`,
`spork.core.dispatch.combine`, `spork.core.pipeline.default`.

- [x] Design: property-based + mutation testing strategy, scope, and
      why neither runs in the fast per-push loop (docs/DESIGN.md
      §16.1/§16.2) (S)
- [x] Hypothesis property tests for the four in-scope modules —
      `test_<module>_fuzz.py` siblings, part of the ordinary `uv run
      pytest` gate like any other correctness test (M) — 19 tests
      (docs/TEST_COVERAGE.md 707–725), all passing against the
      existing implementation with no `src/spork` change: coverage
      that was already earned, per CLAUDE.md's TDD discipline for this
      kind of gap-closing round.
- [x] `mutmut` wired up: dev dependency, `[tool.mutmut]` scoped to the
      four in-scope modules, `mutation/README.md` documenting manual
      invocation and the current baseline mutation score (S) —
      `source_paths` copies the whole package (so the four mutated
      files still have the rest of `spork.core` importable),
      `only_mutate` narrows what actually gets mutated to the four in
      scope.
- [x] `.github/workflows/mutation-testing.yml`: weekly + manual
      (`workflow_dispatch`) run, uploads the result summary as a build
      artifact — deliberately non-blocking, same reasoning as
      `benchmarks/` staying outside the PR gate (S)
- [x] First baseline mutation run against the four modules; every
      surviving mutant either killed with a targeted test (committed
      as an ordinary test-improvement commit) or recorded as
      equivalent in `mutation/README.md` (M) — 174 mutants generated,
      171 killed. Five real, behavior-changing gaps found and closed
      (docs/TEST_COVERAGE.md 726–730): a classifier/dispatch call
      receiving the wrong argument in two places
      (`rules.engine.evaluate`, `DispatchingClassifier.classify`),
      `process_message()` silently dropping its `new_correlation_id=`/
      `classifier=` injection points, the default clock never checked
      for being UTC, `build_default_pipeline()`'s own `force` default
      never exercised, and one docstring-documented "no scores = 0.0
      confidence" contract with no deterministic test (a property test
      only reached that path by chance, so the mutant's kill status
      flickered between runs — fixed with two pinned examples, not a
      bigger Hypothesis budget). 3 remaining survivors confirmed
      equivalent and documented in `mutation/README.md`, not silently
      ignored.

**Exit criteria met:** `uv run pytest` includes the new property-based
tests and stays green (785 tests total); `uv run mutmut run` against
the four in-scope modules has no surviving mutant that isn't recorded
as equivalent in `mutation/README.md` — verified reproducible across
repeated runs.

## M8 — Backfill / retroactive categorization

**Goal:** triage the maintainer's existing several-thousand-message
Inbox (read and unread), not just mail that arrives after `sporkd` is
enabled. `fetch_new_messages(since_cursor=None)` deliberately
baselines and discards history (docs/DESIGN.md §9.3, "a separate
explicit import/backfill feature would need its own policy and is not
implicit startup behavior") — this milestone is that separate feature.
Depends on M1c's harness/corpus existing first: backfill is exactly
the kind of large, real, varied run that should be developed and
regression-tested against recorded flows, not live-fired against the
real account on every test run.

- [x] `JmapClient.query_messages()`: `Email/query` + `Email/get`,
      windowed by `position`/`limit` paging, filterable (`unread_only`
      → `notKeyword: $seen`, unconditional for a full sweep) — a new,
      explicitly-named read path, not a flag on `fetch_new_messages()`
      (M). `JmapQueryResult` carries `position`/`next_position`/`total`/
      `has_more`, distinct in shape from `JmapFetchResult`'s cursor
      semantics — a query page isn't an acknowledgeable Email state.
      6 acceptance tests (`tests/core/providers/jmap/test_query.py`),
      same injected jmapc-shaped fake convention as the rest of the
      package. Live-verified against the real (read-only) account:
      4181 total Inbox messages, 2849 unread, real pagination, no
      writes. **PR #20 review finding, fixed:** pagination originally
      derived `has_more`/the next page's position from
      `len(messages)` (the post-normalize count) instead of the
      actual `Email/query` match count — a message deleted/moved
      between `Email/query` and `Email/get` mid-sweep would have
      drifted position and could stall a run before reaching `total`.
      `next_position` now derives from `len(ids)`, and `spork
      backfill` resumes from `page.next_position`, not
      `position + len(page.messages)`.
- [x] A bounded, resumable backfill CLI command (`spork backfill`),
      separate from the daemon's steady-state push/poll
      `TriggeredSource` (M) — standalone like `reclassify`/`logs`
      (works whether or not `sporkd` is running), reuses
      `process_message()`/`escalate_message()` exactly as `reclassify`
      does, over `BackfillProvider.query_messages()` pages instead of
      one message-id. Not a `Source` — a one-shot CLI run, not part of
      the daemon's loop. `--unread-only`/`--limit`/`--page-size`
      options. 6 acceptance tests + 3 edge cases (all 3 passed against
      the existing implementation with no code change — the
      idempotency gate, capability check, and per-message limit
      counter were already correct), same
      subprocess/FileProvider/RecordedLLMClient convention as
      `test_reclassify.py`. **PR #20 review finding, fixed:**
      `build_thread_history_reader()`/`build_mailbox_lister()`/
      `build_draft_creator()` were built inside the per-message loop,
      once per escalation — for `FileProvider` that re-reads and
      re-parses the whole messages file from disk every time. Now
      built once before the loop and reused across every escalation.
      A new test (`tests/support/counting_provider.py`'s
      `CountingFileProvider`) confirms each is built exactly once
      across 3 escalating messages.
- [x] Backfill reuses `StateDB`/`processed_messages` for dedup so an
      overlapping backfill run and live ingestion never double-process
      the same message (S) — comes for free from
      `process_message()`'s own idempotency gate (docs/DESIGN.md §11):
      a message already marked processed (by live ingestion or a
      prior backfill run) returns `verdict=None`, never reprocessed.
      No new dedup mechanism needed; the existing one already covers
      backfill honestly.
- [x] A backfill-specific throttle/budget policy — `tiering.
      daily_call_budget` (default 200) exists for steady-state live
      triage and will be exhausted almost immediately by a
      several-thousand-message sweep; backfill must not silently
      inherit it unmodified (S) — `--limit` defaults to 50 messages
      per run (not the Inbox's actual size), an explicit CLI-level cap
      independent of `daily_call_budget`, which still applies and
      layers on top: if Tier 2's budget is exhausted mid-run, the loop
      stops early and reports it (`stderr`), rather than silently
      continuing to escalate messages that will keep failing budget.
      **PR #20 review finding, fixed:** `--limit`/`--page-size` had no
      positivity validation — `--limit 0` ran successfully and
      reported "0 messages processed" instead of being rejected as a
      mistake. Both now use Typer's `min=1`, rejecting a non-positive
      value with a clean usage error (exit 2, no traceback) before any
      provider/network call.
- [ ] `spork backfill` run against the recorded/replayed corpus from
      M1c is used to grow `tests/fixtures/corpus/live.jsonl` with real
      category diversity (newsletters, receipts, personal, spam, …)
      for prompt/threshold tuning ahead of M7's confidence-tuning item
      (S). **Not done via `spork backfill` itself** — the corpus
      already has 13 entries (M1c item 4) from hand-sent tagged
      samples, not a `spork backfill` run, because `spork backfill`
      against the real account would hit
      `JmapClient.apply_action()`/`create_draft()`'s still-`NotImplementedError`
      write-side stubs the moment any rule resolves to anything but
      `ignore` — safe (a clean crash, not a mutation, since the JMAP
      key is read-only anyway), but not something to run live
      un-gated. A real `spork backfill` corpus-growth run needs either
      an all-`ignore` rules file or the write-side JMAP stubs resolved
      first.

**Exit criteria:** a backfill run categorizes a large recorded sample
of the maintainer's real Inbox end-to-end through the same Tier 1/
Tier 2 pipeline live ingestion uses, respects its own budget policy,
and never reprocesses a message the live path has already claimed.
Applying the resulting categorization as real mailbox actions (labels,
moves) is gated on write-scoped JMAP credentials, same limitation as
M2/M3/M5's own live-action items — this milestone's exit criterion is
about correct read-side categorization, not the write.

## M9 — Read-only knowledgebase context retrieval

**Goal:** a Tier 2 verdict can draw on relevant background beyond the
email itself — a generic, read-only "context/knowledgebase" seam, not
a bespoke integration with any one note-taking tool. (Explicit
correction from an earlier 4-item proposal that pasted Obsidian-
specific pseudocode: "I do not exactly want a bespoke obsidian config,
but a read right context/knowledgebase interface.")

- [x] `ContextProvider` Protocol + dynamic loader + pipeline wiring (M) —
      `spork.core.context.base.ContextProvider` (`get_context(message)
      -> ContextResult`), `spork.core.context.loader.load_context_provider()`
      (identical "module:ClassName" mechanics to every other backend
      loader in this codebase). `FetchContextAugment` (a new Tier 2
      pipeline Augment) runs before `BuildVerdictRequestFilter`, which
      flattens the result into `VerdictRequest.context_snippets` —
      sent in the actual prompt (`build_prompt()`), framed explicitly
      as reference material, never instructions, and never a
      substitute for `available_categories`/`available_mailboxes` as
      the source of truth for what the model may choose.
      `SporkConfig.context: BackendSpec | None = None` — omitting
      `[context]` is a fully valid config, same convention
      `tiering.local_classifier: None` already has.
- [x] `NullContextProvider` — the real default when `[context]` is
      unconfigured (S) — always answers "no relevant context," zero
      configuration, zero I/O. Not a stand-in for a missing backend;
      "no knowledgebase configured" is a legitimate deployment state
      in its own right.
- [ ] A real backend that actually reads content (S/M, genuinely
      undecided) — `spork.core.context.clients.vault.MarkdownVaultContextProvider`
      settles the likely real shape (`vault_path` constructor arg) as
      a stub, `get_context()` raising `NotImplementedError` — but
      *not* for the usual "blocked on a live network call" reason
      every other settled-shape stub in this codebase has. The actual
      blocker is a real design choice: plain substring/keyword match
      vs. something ranked (embeddings, an LLM re-rank pass) against
      real note content, and this environment has no real vault to
      validate either choice against honestly — unlike `FileProvider`,
      which could be built and tested fully offline from fixtures
      alone. Needs a decision once real vault content is available to
      test against, not more design-from-nothing.
- [x] `EntityContextProvider` — a second real backend (prototype),
      structured rather than free-text: tracks domains, companies,
      services, and people from a JSON fixture (e.g. "gandi.com is
      operated by Gandi, which provides DNS hosting and Cloud
      hosting"), not a redo of the vault backend above. Unlike
      `MarkdownVaultContextProvider`, structured domain/company/
      service/person facts have no undecided-retrieval-algorithm
      blocker — the same "buildable and testable fully offline from
      fixtures alone" reasoning `FileProvider` already established —
      so this ships complete, not as a stub. `lookup_domain()`/
      `lookup_company()`/`lookup_service()`/`lookup_person()` are
      exposed directly (case-insensitive keys, aggregate
      `Service.provided_by` computed from every company listing that
      service rather than stored redundantly) and `get_context()`
      builds on them, turning a recognized `from_domain`/`from_address`
      into `ContextSnippet`s. Explicitly one of several knowledge base
      backends this seam is meant to hold — a future live-lookup
      backend (WHOIS/RDAP) answering the same four lookups is a
      sibling implementation, not a redesign; this prototype doesn't
      build that second one, only proves the shape. Specified in
      Gherkin (`docs/acceptance/m9_entity_context.feature`) and backed
      by a full pytest acceptance + edge-case suite
      (`tests/core/context/clients/entities/`) — see
      docs/DESIGN.md §10.8.

**Exit criteria:** a Tier 2 verdict on a test message demonstrably
changes (a different `suggested_action`, a materially different
`reasoning`) when relevant context is present in `context_snippets`
versus absent — proving the seam actually influences the model's
answer, not just that it's wired through unused. `EntityContextProvider`
is the first backend actually capable of demonstrating this (unlike
`NullContextProvider`, which never supplies any snippets) — but the
demonstration itself (a recorded-LLM-fixture test showing the verdict
actually differ, mirroring M3's prompt→verdict test convention) is
still open, tracked here rather than assumed from the backend existing.

## M10 — Receipt archiving

**Goal:** recognize automatic-payment receipt emails, tag them
(`receipt`, `company:<name>`, `date:<iso-date>`), and archive a single
combined PDF — the message plus every attachment — to a configured
location. Deterministic wherever possible: a known sender is tagged
and archived with zero LLM calls; an unrecognized sender costs exactly
one narrow Tier 2 extraction call, after which it's learned and never
asked about again. Full design: docs/DESIGN.md §9.5. Unlike M1/M3, this
milestone has **no live-account blocker** — the whole pipeline is
designed to be offline-testable (`FileProvider` + a recorded
extraction fixture), so its exit criterion should be fully met once
the modules below are actually built, not partially met the way
JMAP-dependent milestones are.

Originally numbered M9; renumbered when M9 landed independently as
"Read-only knowledgebase context retrieval" (above) — an unrelated,
concurrently-developed milestone that reached `main` first. The two
turn out related in one real way: `EntityContextProvider.lookup_domain()`
(M9) is a curated, read-only domain→company source this milestone's
deterministic extractor can consult *ahead of* its own StateDB-backed
learned cache, rather than inventing a second static-seed-file format
— see the extractor item below.

- [ ] `Provider.build_attachment_fetcher()` (§9.3/§9.5): a new
      read-side capability — `FileProvider` real, `JmapProvider` a
      settled-shape `NotImplementedError` (M)
- [ ] `Provider.build_keyword_applier()` (§9.5): JMAP-keyword-based
      free-form per-message tagging, distinct from the existing
      mailbox-based `tag` action — `FileProvider` real, `JmapProvider`
      a settled-shape `NotImplementedError` (S)
- [x] `spork.core.receipts.registry`: `StateDB` gains
      `known_receipt_senders` (`get_known_sender()`/
      `learn_known_sender()`, matching the existing one-class-owns-
      every-table convention rather than a separate wrapper class) —
      the "learning system" the milestone is named for.
      `registry.normalize_sender_domain()` is the pure logic half (S)
- [x] `spork.core.receipts.extract`: deterministic company/date
      extraction — an optionally-injected `EntityContextProvider`-style
      domain lookup first (M9's curated data), then the learned
      `known_receipt_senders` cache, then a closed set of date patterns;
      declining rather than guessing when company or date doesn't
      resolve (M) — 7 acceptance tests
      (`tests/core/receipts/test_extract.py`), plus
      `docs/acceptance/m10b_receipt_senders.feature` (5 scenarios,
      fully bound and passing, including the learn-then-deterministic
      loop end to end minus the Tier 2 call itself).
- [x] `spork.core.receipts.llm.ReceiptExtractionClient` Protocol +
      `RecordedReceiptExtractionClient` fixture-replay implementation,
      mirroring `LLMClient`/`RecordedLLMClient` (§10.1/§10.5) (M) — 7
      acceptance tests (`tests/core/receipts/test_llm.py`), plus
      `docs/acceptance/m10c_receipt_extraction_llm.feature` (3
      scenarios, fully bound and passing, no live model call).
- [ ] `rules.schema.Action` gains a fourth terminal type,
      `"archive_receipt"` (S)
- [x] `spork.core.receipts.pdf.build_receipt_pdf()`: message +
      attachments -> one PDF (cover page + merged/rendered
      attachments, or cover page alone with no attachments); new
      optional `spork[receipts]` extra (`pypdf`, `reportlab`,
      `Pillow`) (M) — 9 acceptance tests
      (`tests/core/receipts/test_pdf.py`), plus
      `docs/acceptance/m10a_receipt_pdf.feature` (4 scenarios, fully
      bound and passing, no live account/network).
- [x] `spork.core.receipts.archive.save_pdf()`: writes to a caller-
      supplied output directory (wired to
      `SporkConfig.receipt_archive.output_dir` once that config
      section exists — still open below), deterministic filename, one
      wrapped `ReceiptArchiveError` on write failure (S) — 6 acceptance
      tests (`tests/core/receipts/test_archive.py`), same
      `m10a_receipt_pdf.feature` covers the archived-filename scenario.
- [ ] `SporkConfig.receipt_archive: ReceiptArchiveConfig | None` (S)
- [ ] Pipeline wiring: a new Filter/Augment pair on the `"terminal"`
      branch for `action.type == "archive_receipt"` (M)
- [ ] `docs/acceptance/m10_receipt_archiving.feature` bound for real —
      `@wip` dropped, scenarios passing offline under the safe default
      `uv run behave` (M)

**Current status:** in progress. `docs/DESIGN.md` §9.5 records the
architecture; `docs/acceptance/m10_receipt_archiving.feature` specifies
the full pipeline's target behavior in Gherkin, with every step bound
(not left undefined) but raising `NotImplementedError` — real
scaffolding, not a placeholder, tagged `@wip` so it's skipped by the
safe-default `uv run behave` the same way `@manual` scenarios are (see
docs/acceptance/README.md's `SPORK_ACCEPTANCE_WIP` note). The PDF/
archive module and the known-sender registry's storage are built and
independently Gherkin-specified (`m10a_receipt_pdf.feature`); the rest
of the checklist above is built module by module, each following
CLAUDE.md's design-then-tests-then-implementation order, same as every
prior milestone.

**Exit criteria:** a known-sender receipt is tagged and archived with
zero Tier 2 calls; an unrecognized sender is extracted via exactly one
Tier 2 call and learned; a second message from that now-learned sender
is handled deterministically; a message with attachments and a message
with none both produce exactly one PDF at the configured location; an
unwritable archive location fails safely and leaves the message
retryable. **Not yet met** — still in progress.

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
