# Test Suite Inventory & Milestone Coverage

**Status:** snapshot as of the M1a (source/dispatch pipeline) milestone,
updated to add xfail coverage for two known M0 gaps, then updated again
to cover most of M1's remainder (state DB, poll fallback, and settled-
shape `NotImplementedError` stubs for the JMAP client/push listener),
then updated once more: both M0 xfail gaps are now closed for real
(`secretspec.toml` + `spork.core.secrets`, and Typer-based `--help`/
`--version` for both entry points). **No xfail tests remain.** Updated
again for M1b: JMAP moved from `spork.core.jmap` to
`spork.core.providers.jmap`, behind a new `Provider` adapter Protocol
and a dynamic `importlib`-based loader. Updated once more for most of
M2: the `rules.toml` loader, `audit_log`, `Provider`'s write side
(`ActionApplier`), `ActionExecutor`, and the `process_message()`
orchestration tying idempotency + evaluation + action + audit
together. Updated once more for `FileProvider` (M1b): a second, fully
real `Provider` Adapter with no `NotImplementedError` anywhere, proving
the abstraction itself generalizes beyond `JmapProvider`. Updated again
for `spork rules test` (M2's last item): real CLI wiring + rules
loading + clean error handling, with the live-JMAP-fetch step a
settled-shape `NotImplementedError` reported cleanly rather than left
to traceback. **M2 is now 7/7.** Updated once more for `spork doctor`
(M1's last unstubbed item): real CLI wiring, connectivity check a
settled-shape `NotImplementedError`. **Every item in M0–M2 is now
either fully implemented or a settled-shape stub with a passing test —
none are unspecified.** Updated once more for M3's first item:
`spork.core.llm.clean.clean_body()` — pure, dependency-free body
cleaning (HTML strip, quote-chain collapse, truncation). **M3 is 1/7.**
Updated once more: `spork.core.pipeline` rebuilt on a generic Filter/
Selector/Pipeline framework (docs/DESIGN.md §9.4), `process_message()`
unchanged in signature/behavior, plus a `benchmarks/` directory for
per-module performance measurement outside the correctness suite.
Updated once more: a third module kind, `Augment[M]`, added to that
framework for stages that enrich a Payload via I/O (a thread-history
search, a contact-details lookup) — `Filter`/`Selector` stay
conventionally pure, `Pipeline`'s stage list now dispatches each stage
to `.apply()` or `.augment()` by type. No concrete Augment exists yet;
this is the framework-level Protocol only. Updated once more for M3's
second item: `spork.core.llm.base`/`loader`/`clients.anthropic` — an
`LLMClient` Protocol adapter for Tier 2 backends (mirroring
`spork.core.providers`' `Provider` pattern), a pydantic `Verdict`
schema, and `AnthropicLLMClient` as a settled-shape stub like
`JmapClient`. **M3 is 2/7.** Updated once more for M3's remaining five
items, all in one pass: verdict validation against a deployment's
configured mailbox/category set (`spork.core.llm.validate`);
confidence-band logic (`spork.core.llm.confidence`); `daily_call_budget`
enforcement + `llm_usage` tracking (`StateDB` extended,
`spork.core.llm.budget`); `RecordedLLMClient` (`spork.core.llm.clients.recorded`)
— the `LLMClient` equivalent of `FileProvider`, a second fully real
adapter for CI/offline use; and the draft creation path
(`Provider.build_draft_creator()`, a `JmapClient.create_draft()`
settled-shape stub, a real `FileProvider` implementation). **M3 is
7/7** — see the milestone table below for the same "done in the same
sense JmapProvider was" caveat that applies to every item touching a
live account. Two real gaps were found and fixed along the way (not
just documented): `StateDB.record_llm_call()` had no guard against
negative token counts, and DESIGN.md's §7.4 "indicative, not final"
framing was stale for tables built since M1. Updated once more:
`spork.core.pipeline.tier2` (§10.7) wires all seven M3 items into one
runnable pipeline over a new `Tier2Meta`, reusing the generic
Filter/Selector/Augment/Pipeline framework — proven end to end against
`RecordedLLMClient` with zero live API calls. Still M3, still 7/7 (not
a new checklist item); what's still open is deciding *which* escalated
message needs a Tier 2 run, deliberately left to a future daemon loop
that needs a live JMAP session anyway. Updated once more for M4's
first item: `spork.core.alerts.base`/`log`/`loader` — an `Alerter`
Protocol adapter (mirrors `Provider`/`LLMClient`), `LoggingAlerter` as
a genuinely real v1 backend (not a stub for the desktop-notification
backend the roadmap originally described — see M4's table below for
why), and `load_alerter()` for config-driven backend selection.
`AlertUrgency`'s vocabulary was checked against the actual Desktop
Notifications Specification and `notify-send(1)` before being settled.
**M4 is 1/3.** Updated once more for M4's second item's pipeline-visible
portion: `Condition.from_in` (closes a real gap — docs/DESIGN.md
§7.5's own `vip-senders` example predated the field existing);
`Action.alert_immediately`; `spork.core.pipeline.observer.PipelineObserver`
(bundles correlation-ID tracing with `Alerter` delegation, the
"combine logging and alerting" design decision); `CorrelationIdFilter`
on both pipelines; and alert-trigger wiring at all four
pipeline-visible hook points (`RecordEscalationFilter` for VIP-style
escalations, `RecordAlertOnlyFilter`, `ApplyVerdictActionFilter` for
`autoact_alert` + the orthogonal `urgency=="high"` dimension,
`RecordBudgetExhaustedFilter`). Daemon-health alerts (JMAP push
disconnected, crash-looping) remain unbuilt — no `Payload`/
`Pipeline.run()` exists for them, so they're explicitly deferred to
the M5 daemon loop, not invented here. **M4 is 2/3** (its "graceful
degrade" item stays moot until a real desktop backend exists, per the
note already on M4's table). Updated once more for M5's first item:
`spork.core.config` (`schema.py`/`paths.py`/`loader.py`) — a three-tier
`config.toml` (system enforced/user/system default) settled against
the real XDG Base Directory Specification v0.8, not invented; deep
merge is per-key, not whole-file. **M5 is 1/9.** Updated once more for
M5's second prerequisite: `spork.daemon.loop.run_daemon()` — every
blocking call (`Source.poll()`, the whole `process_message()` call)
bridged into the asyncio loop via `asyncio.to_thread()`, since every
I/O dependency this daemon has is synchronous (confirmed against
`jmapc` directly). Tier 1 only; Tier 2 daemon-loop chaining is
tracked as a new, separate roadmap item rather than faked.
`StateDB` gained `check_same_thread=False` as a required companion
fix. **M5 is 2/10** (a checklist item was added along with this work,
not just checked off). Updated once more: `spork.core.ipc`
(newline-delimited JSON, one request per connection, real Unix
sockets throughout) plus `DaemonState` and `run_daemon()`'s
`asyncio.TaskGroup()` now serving it alongside Tier 1 processing, and
the `spork status`/`spork pause`/`spork resume`/`spork logs` CLI
commands. A real concurrency bug (an IPC handler racing `StateDB`
against a `to_thread(process_message, ...)` call) was found and
designed out before any code was written — `spork status` defers its
LLM-spend field as a direct, stated consequence rather than accepting
the race. **M5 is 6/10.** Updated once more for "Wire Tier 2 into the
daemon loop": `Provider` gained `build_thread_history_reader()`/
`build_mailbox_lister()` (real against `FileProvider`, settled-shape
`NotImplementedError` against `JmapProvider`, same split as every
other JMAP leaf); `run_daemon()`/`_run_message_loop()` now carry an
escalated message straight into `process_tier2_message()` in the same
poll cycle via a second, strictly-sequential `asyncio.to_thread()`
call. `to_addresses` is parsed from real `NormalizedMessage.headers`.
**M5 is 7/10.** Updated once more for `spork rules list/edit/enable/disable`
with live reload: `RulesState` (mirrors `DaemonState`) + a new `reload`
IPC command that reassigns `rules_state.rules` wholesale (never
mutated in place) on a successful re-`load_rules()`, read fresh by
`_run_message_loop()` right after every `poll()` call; a
`RulesLoadError` from a bad hand-edit is reported as `ok=False`
without touching the daemon's last-known-good rules.
`spork.core.rules.writer.dump_rules()` is a small purpose-built TOML
serializer (no new dependency) `enable`/`disable` use to rewrite
`rules.toml` — real, stated tradeoff: doesn't preserve hand-written
comments/formatting. Two stale `docs/DESIGN.md` §13 claims were found
and corrected along the way (`spork status`'s LLM-spend claim, `spork
rules list`'s "match stats" claim — neither has real backing data).
**M5 is 8/10.** Updated once more for `spork config show/edit`:
`spork.core.config.loader.enforced_override_paths()` flattens the
enforced tier's raw TOML into dotted paths (independent of
`load_config()`'s merge) so `show` can flag every value the enforced
tier sets, plus a stated-heuristic credential redaction
(`token`/`key`/`secret`/`password` substring match) for `kwargs`
entries. `edit` validates the real merged `load_config()` result on
save and — deliberately, unlike rules — never pushes a live reload:
config controls objects `run_daemon()` only builds once at startup.
Also rebuilt the `spork.cli` §6.4 UML diagram, stale since
status/pause/resume/logs/rules-list/edit/enable/disable landed and
were never added to it. **M5 is 9/10.**
**Purpose:** (1) a plain-English description of every test currently in
the suite, so "what does this test do" never requires re-reading code;
(2) an honest cross-check of that suite against `docs/ROADMAP.md`'s
checklists — not "are the tests good" (they are, see verdict below) but
"how much of each milestone do they actually cover."

Regenerate/update this after any milestone that adds or changes tests —
it goes stale otherwise.

## Verdict, up front

Every test below is **accurate**: each one's assertion matches the
behavior it claims to verify, traced against the actual test source (not
inferred from the test's name), and cross-checked against the design
decisions in `docs/DESIGN.md` that motivated it. No mismatched
assertions or misleading test names were found.

What the suite is **not** is complete relative to the milestones' full
scope — and that's expected, not a defect: a checklist item with no
tests, in every case found, has no tests *because it has no
implementation yet*, not because someone forgot to test working code.

Both gaps that were previously "no test at all", then `xfail` — **M0's
own exit criterion (`spork --help` / `sporkd --help` producing real
output)** and **the missing `secretspec.toml`** — are now closed for
real. `secretspec.toml` exists with `spork.core.secrets` wrapping the
real SDK (tested against its own `env://` provider, not a mock — see
`tests/core/test_secrets.py`); both entry points use Typer and pass
their `--help`/`--version` tests without any marker
(`tests/cli/test_main.py`, `tests/daemon/test_main.py`). Each
graduation was verified with `--runxfail` *before* removing the
marker, confirming the test passed for the reason it was supposed to,
not by accident. `xfail_strict = true` (`pyproject.toml`) would have
failed the suite if either marker had been left in place — it wasn't
needed this time, but stays in place for the next gap that gets this
treatment.

Most of M1's remainder is now covered too. Three pieces turned out to
be pure, network-free logic and were built and tested for real:
`spork.core.state` (the SQLite state store), and
`spork.core.sources.timer`/`fallback` (poll-based fallback, composed
from the `Trigger`/`Source` protocols M1a already established). Three
pieces — `spork.core.providers.jmap.client.JmapClient`,
`spork.core.providers.jmap.push.JmapPushTrigger`, and now `spork
doctor`'s connectivity check — genuinely need a live Fastmail session
to implement for real; rather than leaving them unspecified, their
shape is settled and each raises a specific `NotImplementedError`,
verified by an ordinary *passing* test (not `xfail` — the raise is the
correct, specified behavior right now, not a stand-in for one). Every
M1 item now has at least a settled shape and a test. See the coverage
tables below.

---

## Milestone coverage

### M0 — Project scaffolding — **fully done**

| Checklist item | Implemented | Tested |
|---|---|---|
| `uv init` / `pyproject.toml` scripts | ✅ | Not directly — no test asserts the entry points resolve |
| `src/spork/` package layout | ✅ | Indirectly — every test's imports depend on it |
| `secretspec.toml` w/ declared secrets | ✅ | ✅ — test 46 (manifest structure) + tests 72–78 (resolution, `spork.core.secrets`) |
| Lint/format/type-check config | ✅ | Validated by CI runs, not pytest |
| CI: lint/type-check/tests on push+PR | ✅ | Validated by the workflows themselves, not pytest |
| `spork --help` / `sporkd --help` work | ✅ | ✅ — tests 47, 48 (`--help`) + tests 79, 80 (`--version`) |

Every item is real now. `secretspec.toml`/`--help` were previously
tracked as `xfail`; both graduated to ordinary passing tests once
implemented (see the Verdict section above for how that was
verified).

### M1 — JMAP connectivity

| Checklist item | Implemented | Tested |
|---|---|---|
| `jmap.client` session bootstrap (`jmapc`) | 🟡 stub — raises `NotImplementedError` | ✅ (that it raises) — tests 49, 50 |
| Mailbox role resolution + caching | ✅ | ✅ — tests 20–26 (7 tests) |
| `Email/query`+`Email/get` batched fetch | 🟡 stub — same `JmapClient.fetch_new_messages()` | ✅ (that it raises) — test 50 |
| EventSource push listener + backoff | 🟡 stub (listener) / ✅ (backoff math) | ✅ (that it raises) — tests 51, 52 / ✅ (math) — tests 16–19 |
| Poll-based fallback | ✅ (real, network-free) | ✅ — tests 53–61 (9 tests) |
| State DB (`push_cursor`, `processed_messages`) | ✅ | ✅ — tests 62–71 (10 tests) |
| `spork doctor` | 🟡 stub — CLI wiring real, connectivity check raises `NotImplementedError` | ✅ (that it raises cleanly) — tests 147–149 |

Three of these are genuinely done: mailbox resolution (unchanged),
poll-based fallback (`IntervalTimer` + `FallbackSource`, pure control
flow, no network needed to build or test), and the state DB (SQLite,
same story). The push-listener's backoff *scheduling* is real and
tested too, separately from the listener itself.

The other four — client session bootstrap, batched fetch, the actual
push listener, and now `spork doctor`'s connectivity check — all
genuinely require a live Fastmail session to implement for real, which
this environment can't exercise honestly. Rather than leaving them
untested, their shape is settled (constructor args, method
names/signatures, CLI wiring) and each raises a specific
`NotImplementedError`, verified by a normal *passing* test (not
`xfail` — the raise is the correct, specified behavior at this stage,
not a stand-in for a real assertion). `spork doctor`'s CLI command
itself is real (registered, `--help` works, appears in `spork --help`)
— only the connectivity check underneath is stubbed, same relationship
`spork rules test` has to its own live-fetch gap. **Every M1 item now
has at least a settled shape and a test — none are unspecified.**

### M1a — Source / dispatch pipeline

| Checklist item | Implemented | Tested |
|---|---|---|
| `Trigger`/`ContentFetcher`/`Source` protocols | ✅ | ✅ — exercised via every concrete implementation below (protocols themselves aren't directly testable, only structurally) |
| `TriggeredSource` | ✅ | ✅ — tests 43, 44, 45 |
| `ImmediateTrigger` + `SequenceContentFetcher` | ✅ | ✅ — tests 37–42 |
| `Dispatcher` | ✅ | ✅ — tests 12, 13, 14, 15 |
| `Combiner` (`Primary`, `HighestConfidence`) | ✅ | ✅ — tests 5, 6, 8, 9, 10, 11 |
| `DispatchingClassifier` | ✅ | ✅ — test 7 |
| Exit criteria (replay → rule engine; ensemble → rule engine) | ✅ | ✅ — tests 36 and 7 directly demonstrate each half |

**6 of 6 items done, all tested, exit criteria directly demonstrated by
name.** This is the one milestone where "implemented" and "tested"
are both complete — 21 of the 45 suite tests exist for this milestone
alone.

### M1b — Provider abstraction

| Checklist item | Implemented | Tested |
|---|---|---|
| `spork.core.jmap` → `spork.core.providers.jmap` move | ✅ | ✅ — same 26 jmap tests, unchanged assertions, just new import paths |
| `Provider` protocol | ✅ | ✅ — exercised via `JmapProvider` and `FileProvider` (protocols aren't directly testable, only structurally) |
| `JmapProvider` (the Adapter) | ✅ | ✅ — tests 81–83 |
| `load_provider()` (the dynamic loader) | ✅ | ✅ — tests 84–89 |
| `FileProvider` (a second, fully real Adapter) | ✅ | ✅ — tests 122–138 (17 tests), 100% line coverage |

**5 of 5 items done, all tested, 100% coverage on `spork.core.providers`.**
Two things worth calling out. First: `JmapProvider`'s tests only prove
*composition* is correct (it assembles `JmapClient` + `JmapPushTrigger`
into a working `Source` shape) — they can't prove real fetch/push
behavior, because there isn't any yet (M1). That's expected, not a gap:
the adapter and loader machinery is independently correct regardless
of whether the backend underneath is implemented. Second: `FileProvider`
exists precisely to close the resulting hole — until a live JMAP
session exists, `JmapProvider` can never prove `Provider`'s read/write
split *actually works end to end*, only that it's wired up correctly.
`FileProvider` is a second, unrelated, fully working `Provider` with no
`NotImplementedError` anywhere, so the abstraction itself is proven
sound independent of JMAP ever going live. It is explicitly not a
"recent mail" fixture mechanism for `spork rules test` (docs/DESIGN.md
§9.3, §13) — that command still has no fixture-file mode and won't
until M1's real JMAP fetch exists.

### M2 — Rule engine (Tier 1) + action executor

| Checklist item | Implemented | Tested |
|---|---|---|
| Rule schema + `rules.toml` loader/validator | ✅ | ✅ — schema: engine tests (27–35) + `extra="forbid"` edge cases (96, 97) / loader: tests 90–97 (8 tests) |
| Tier 1 evaluator | ✅ | ✅ — tests 27–35 (9 tests) |
| Action executor | ✅ (`ActionApplier`-agnostic, real backend still `NotImplementedError`-stubbed per M1) | ✅ — tests 107–113 (7 tests) |
| `processed_messages` idempotency | ✅ — wired into `process_message()` | ✅ — tests 114–121 (8 tests) |
| `audit_log` writes | ✅ | ✅ — tests 98–103 (6 tests) |
| `spork rules test` dry-run | ✅ (loading+errors real; live-fetch step `NotImplementedError`, M1) | ✅ — tests 139–146 (8 tests) |
| Unit tests: condition matching / idempotency | ✅ | ✅ |

**7 of 7 items done.** The schema fix is worth calling out: an
edge-case test (96) caught that pydantic's default `extra="ignore"`
meant a typo'd field (e.g. `"enalbed"` instead of `"enabled"`) was
silently dropped, falling back to its default instead of failing to
load — `extra="forbid"` fixed it, verified red-then-green same as
everything else. `ActionApplier` itself is documented under M1b (it's
part of `Provider`'s contract, docs/DESIGN.md §9.3) but its *executor*
(the provider-agnostic consumer) is M2 work, tested here. `spork rules
test` is "done" in the same sense `JmapProvider` is done under M1b:
everything buildable without a live JMAP session is real and tested
(CLI wiring, rules loading, clean error handling for both bad and
missing files), and the one piece that isn't — the actual fetch of
recent mail — is a settled-shape `NotImplementedError`, caught and
reported as a clean CLI error (test 140) rather than left to produce a
raw traceback.

**Internal refactor (not a new checklist item — M2 stays 7/7):**
`spork.core.pipeline` was rebuilt on the Filter/Selector framework
(docs/DESIGN.md §9.4) — `process_message()`'s signature and behavior
are unchanged (proven by tests 114-121 passing verbatim, relocated but
not rewritten), now composed from a generic `Payload`/`Filter`/
`Selector`/`Pipeline` framework plus seven concrete modules, each
independently tested (161-185) and independently benchmarkable
(`benchmarks/core/pipeline/`, outside `testpaths`). Motivated by M3:
the escalate branch is a `Pipeline[MessageMeta]` value like any other
route, so a future Tier 2 escalation stage is a change to what that
route points at, not a rewrite. A third module kind, `Augment[M]`, was
then added to the same framework (tests 186-191) for stages that
enrich a Payload via I/O — a thread-history search, a contact-details
lookup — keeping `Filter`/`Selector` conventionally pure. No concrete
Augment exists yet (no live lookup backend to call); this is the
Protocol-level seam M3's prompt-building chain is expected to use.

### M3 — LLM escalation (Tier 2) — 7/7

| Checklist item | Implemented | Tested |
|---|---|---|
| Body cleaning (HTML strip, quote-chain collapse, truncation) | ✅ | ✅ — tests 150–160 (11 tests), 100% line coverage |
| Claude client wrapper + verdict schema | ✅ | ✅ — tests 192–210 (19 tests), 100% line coverage |
| Verdict validation against configured mailbox/category set | ✅ | ✅ — tests 211–217 (7 tests), 100% line coverage |
| Confidence-band logic | ✅ | ✅ — tests 218–225 (8 tests), 100% line coverage |
| `daily_call_budget` + `llm_usage` tracking | ✅ | ✅ — tests 226–239 (14 tests), 100% line coverage |
| Recorded-response fixtures for CI | ✅ | ✅ — tests 240–252 (13 tests), 100% line coverage |
| Draft creation path | ✅ | ✅ — tests 253–261 (9 tests), 100% line coverage |

`spork.core.llm.clean.clean_body()` is pure string transformation with
no dependency on `NormalizedMessage`, JMAP, or the Claude API — HTML
stripped via a hand-rolled `HTMLParser` subclass (no new dependency),
quoted-reply chains collapsed at the earliest of several marker
patterns, truncated on a word boundary with an explicit marker, and
excess blank lines normalized.

`spork.core.llm.base`/`loader`/`clients.anthropic` ("Claude client
wrapper + verdict schema") is "done" in the same sense `JmapProvider`
was under M1: everything buildable without a live API session is real
and tested (`LLMClient` Protocol, the `VerdictRequest`/`Verdict`
schema — a pydantic model since it parses untrusted LLM output, same
reasoning as `rules.schema` — and `load_llm_client()`'s dynamic
"module:ClassName" loading, mirroring
`spork.core.providers.loader.load_provider()` exactly), and the one
piece that isn't — an actual Anthropic API call — is a settled-shape
`NotImplementedError` on `AnthropicLLMClient.get_verdict()`, same
treatment as `JmapClient`'s stubs (§9.3). No `anthropic` import
anywhere, matching `jmapc`'s not-yet-a-dependency status.

The remaining five items are all real, no live-account blocker: the
budget/draft items depend on `StateDB`/`Provider`, both fully testable
without a network call, and `RecordedLLMClient`'s whole point is *not*
needing one. **M3 is 7/7**, in the same sense M1's JMAP client is
"complete" — everything buildable without a live Fastmail/Anthropic
session is real and tested; the genuinely-blocked pieces
(`JmapClient.connect()`/`fetch_new_messages()`/`apply_action()`/
`create_draft()`, `AnthropicLLMClient.get_verdict()`) are settled-shape
`NotImplementedError` stubs, not gaps.

**Also done (not a new checklist item — still M3, 7/7):**
`spork.core.pipeline.tier2` (docs/DESIGN.md §10.7, tests 262–298)
wires all seven items above into one runnable pipeline — budget gate,
LLM call, usage recording, verdict validation, confidence gating,
action application, draft creation, audit, idempotency — over a new
`Tier2Meta`, reusing the generic Filter/Selector/Augment/Pipeline
framework and `MissingMetaError`, never Tier 1's concrete modules
(`RuleVerdict`/`llm.base.Verdict` are different shapes).
`test_default.py` runs it end to end against `RecordedLLMClient` — a
real escalated message gets a real (recorded) verdict, a real action
applied, a real draft created, with zero live API calls anywhere in
the suite. What's still open: deciding *which* escalated message to
call `process_tier2_message()` on — Tier 1's escalate branch already
marks a message processed, so this pipeline deliberately doesn't
duplicate that idempotency check; the scheduling decision needs a live
JMAP session to know what's actually pending (M5, same blocker M1's
daemon loop has), and isn't invented here.

### M4 — Alerting — 2/3

| Checklist item | Implemented | Tested |
|---|---|---|
| `Alerter` protocol + `LoggingAlerter` | ✅ | ✅ — tests 303–317 (15 tests), 100% line coverage |
| Alert triggers wired to confidence bands + VIP rules + daemon health | ✅ pipeline-visible portion only — VIP escalation, alert_only, autoact_alert + urgency=="high", budget exhausted; ❌ daemon health (no `Payload`/`Pipeline.run()` for it — M5 daemon loop) | ✅ pipeline-visible portion — tests 318–346 (29 tests: `from_in` prerequisite 318–322, `PipelineObserver`/`CorrelationIdFilter`/wiring 323–346), 100% line coverage on the touched modules |
| Graceful degrade when no DBus session bus is available | — | moot for now — see below |

`spork.core.alerts.base`/`log`/`loader` mirror
`spork.core.providers.base`/`loader` and `spork.core.llm.base`/`loader`
exactly: an `Alerter` Protocol, a `LoggingAlerter` v1 backend, and
`load_alerter()` for config-driven backend selection.
`AlertUrgency`'s three levels (`low`/`normal`/`critical`) were checked
against the actual [Desktop Notifications
Specification](https://specifications.freedesktop.org/notification/1.2/urgency-levels.html)
and `notify-send(1)`'s `-u` flag before being settled, not guessed —
so a future real desktop backend needs no translation layer.
`LoggingAlerter` is a genuine, working delivery channel (not a stub):
each alert is logged via `logging.getLogger(__name__)`, urgency mapped
to a log level, never configuring handlers itself (Python logging best
practice — that's the application's job, M7). The "graceful degrade
when no DBus session bus is available" checklist item doesn't apply to
`LoggingAlerter` (no DBus dependency to degrade from) — it's really
about the future desktop-notification backend, and gets its own
checkbox once that backend exists.

`spork.core.pipeline.observer.PipelineObserver` (`docs/DESIGN.md`
§12.2) bundles per-message correlation-ID tracing with `Alerter`
delegation — the "combine logging and alerting" design decision — and
is injected into `build_default_pipeline()`/`build_tier2_pipeline()`
the same way `state_db` is. `CorrelationIdFilter` (one per tier,
mirroring `TimestampFilter`'s DI) sets `meta.correlation_id`, read by
whichever module fires an alert. The four pipeline-visible trigger
points are wired: `RecordEscalationFilter` alerts when a matched
rule's `Action.alert_immediately` is `True` (the mechanism that
finally makes docs/DESIGN.md's `vip-senders` example rule actually
alert, once `from_in` closed the schema gap); `RecordAlertOnlyFilter`
always alerts; `ApplyVerdictActionFilter` alerts on the
`"autoact_alert"` band *or* `verdict.urgency == "high"` regardless of
band (the orthogonal dimension, exercised even inside a plain
`"autoact"` outcome since both bands share this filter);
`RecordBudgetExhaustedFilter` always alerts at `"critical"` urgency.
Daemon-health alerts (JMAP push disconnected, LLM budget exhausted at
the daemon level, crash-looping) are **not** built here and can't be —
they're about `sporkd`'s own lifecycle, not any one message's
`Pipeline.run()`, so there's no `Payload` for a module to attach to;
that's explicitly M5 daemon-loop work. `PipelineObserver`'s
correlation-ID mechanism also partially satisfies M7's "per-message
tracing" roadmap item for the pipeline-internal piece (a known,
stated limitation: a correlation ID is scoped to one pipeline *run*,
not one message's full cross-tier lifetime, since nothing calls
`process_tier2_message()` outside tests until the M5 scheduler
exists) — M7 still separately owns `sporkd`'s overall structured
logging setup and audit-trail completeness beyond triage outcomes.

### M5 — CLI + daemon control surface — 9/10

| Checklist item | Implemented | Tested |
|---|---|---|
| `spork.core.config` | ✅ | ✅ — tests 347–374 (28 numbered entries, 51 actual test cases — see note below), 100% line coverage |
| Daemon event loop assembly | ✅ | ✅ — tests 375–383 (9 tests), 100% line coverage on `spork.daemon.loop` |
| Wire Tier 2 into the daemon loop | ✅ | ✅ — tests 418–435 (18 tests), 100% line coverage on the touched `spork.core.providers.*`/`spork.daemon.loop` code |
| IPC protocol + Unix socket server | ✅ | ✅ — tests 384–399 + 400–403 (20 tests), 99–100% line coverage on `spork.core.ipc` |
| `spork status` | ✅ | ✅ — tests 404–407 (4 tests), including a full end-to-end test against a real `sporkd` subprocess |
| `spork pause`/`resume` | ✅ | ✅ — tests 408–410 (3 tests), including a full pause→status→resume→status round trip |
| `spork rules list/edit/enable/disable` w/ live reload | ✅ | ✅ — tests 436–454 (19 tests), 100% line coverage on `spork.core.rules.writer`/`spork.daemon.state`/`spork.cli.commands.rules`, no gaps on the touched part of `spork.daemon.loop` |
| `spork config show/edit` | ✅ | ✅ — tests 455–478 (24 tests), 100% line coverage on `spork.core.config.*`/`spork.cli.commands.config` |
| `spork logs` | ✅ | ✅ — tests 411–417 (7 tests) |
| `spork reclassify <id>` | ❌ | — |

`spork.core.config` (`schema.py`/`paths.py`/`loader.py`) is the first
of M5's two prerequisite items — settled and documented (§7.2/§6.4)
against the real XDG Base Directory Specification v0.8 and comparable
tools (`git`'s system/global scopes, Chromium/Firefox managed policy),
not invented. Three-tier precedence (system enforced
`/etc/spork/enforced.toml` > user `$XDG_CONFIG_HOME/spork/config.toml`
> system default via `$XDG_CONFIG_DIRS`), deep-merged per-key rather
than whole-file, validated once against `SporkConfig`. The concrete
exit-criterion test — an enforced-tier value a user's own config.toml
can't override — is real:
`test_loader.py::test_load_config_enforced_tier_overrides_user_tier`.

**Test-count note:** the 28 numbered entries below (347–374) represent
**51 actual pytest test cases** — several are parametrized across a
spread of realistic Linux path shapes (spaces, unicode, deep nesting,
multi-entry `XDG_CONFIG_DIRS` strings) per instruction, and this
file's own numbering convention counts one entry per test *function*,
not per parametrize instance. The "Full test inventory" header count
below is the true `pytest --collect-only` total; from here on, the
highest numbered entry and that true collected count no longer
coincide — a real, intentional gap (the extra parametrize instances),
not a numbering error.

`spork.daemon.loop.run_daemon()` (§6.2.1) is the second prerequisite
— every I/O dependency this daemon has (`jmapc`, and by extension
anything a live `ActionApplier` does) is synchronous, confirmed
against the library directly rather than assumed, so the asyncio loop
bridges every blocking call via `asyncio.to_thread()`. Proven end to
end against `FileProvider`/`LoggingAlerter`: a matched rule's action
really applies, both messages land in a real `StateDB`, a VIP-sender
rule's alert fires through the real `LoggingAlerter` loaded from
config, and the loop actually stops (bounded `asyncio.wait_for`, not a
sleep-and-hope) once `stop_event` is set. **Tier 1 only** — chaining
an escalated message into `process_tier2_message()` needs a `Provider`
capability (thread-history/mailbox-listing) that doesn't exist yet,
tracked as its own new roadmap item rather than faked with placeholder
values. `StateDB` also gained `check_same_thread=False`, itself
covered by a dedicated cross-thread test (test 375, `tests/core/state`).

**`spork.core.ipc`** (`protocol.py`/`server.py`/`client.py`) is
newline-delimited JSON, one request per connection, over the real Unix
domain control socket — tested against real sockets throughout, never
mocked. `IpcServer` never crashes or hangs on an unknown command, a
malformed request line, or a handler that raises; the socket file gets
0600 permissions (§15) and any stale leftover is removed before
binding. `send_request()` (the CLI's plain synchronous side) raises
one `IpcConnectionError` for every "nothing reached the daemon" case —
no socket file, connection refused, or a listener that accepts and
closes without responding.

**`DaemonState`** carries only `paused`/`started_at`, deliberately
never anything derived from `StateDB` — a real concurrency bug (an
`IpcServer` handler reading `StateDB` from the event-loop thread while
a `to_thread(process_message, ...)` call touches the same connection
from a worker thread) was caught and designed out *before* any code
was written, not found by a flaky test later. `spork status`'s
LLM-spend field is deferred as a direct consequence — the data is real
(`StateDB.get_llm_usage()`, since M3) but reporting it safely needs
either Tier 2 wired into the loop or a `StateDB` synchronization
mechanism this round doesn't add.

`spork pause`/`spork resume`'s honest caveat is tested, not just
documented: `test_run_message_loop_never_polls_while_paused` proves
`Source.poll()` is never called while paused (a real behavioral skip),
and the full CLI round trip is proven against a real `sporkd`
subprocess, not simulated.

`spork logs` needed no new `StateDB` query surface — `--tail`/`--since`
filter the already-returned list client-side; `--message-id` reuses
`get_audit_entries(jmap_id=...)`'s existing storage-side filter.

### M6–M7

No implementation, no tests. Not evaluated here — nothing to check yet.

---

## Full test inventory (501 tests, all passing — 0 xfail)

### tests/core/classify

1. **`test_registry.py::test_registry_resolves_registered_classifier_by_name`**
   Sets up a minimal `_StubClassifier` (implements `classify()` returning a
   fixed `ClassificationResult`) and registers it under
   `"test-stub-classifier"` via `registry.register`. Calls
   `registry.get("test-stub-classifier")` and asserts the returned object
   is an instance of `_StubClassifier`, proving the registry correctly
   looks up and constructs a backend by name. An autouse
   `_isolated_registry` fixture snapshots/restores the registry around
   every test so this doesn't leak.

2. **`test_registry.py::test_registry_raises_clear_error_for_unknown_classifier_name`**
   Calls `registry.get("this-name-was-never-registered")` with no
   matching registration. Asserts it raises `UnknownClassifierError`,
   verifying an unregistered name fails loudly rather than returning
   `None` or a default backend.

3. **`test_registry_edge_cases.py::test_registering_a_duplicate_name_raises`**
   Registers `_StubClassifier` under `"dup-name"`, then registers the
   same name again. Asserts the second call raises `ValueError`,
   confirming duplicate registration is rejected rather than silently
   overwriting.

4. **`test_registry_edge_cases.py::test_unselected_backends_are_never_constructed`**
   Two tracked classes whose `__init__` appends to a shared list are
   registered under `"tracked-a"`/`"tracked-b"`; only `"tracked-b"` is
   `get()`'d. Asserts `constructed == ["b"]`, proving only the selected
   backend's factory runs — the unselected one is never instantiated.

### tests/core/dispatch

5. **`test_combine.py::test_primary_combiner_returns_the_named_targets_result`**
   Dispatches a message to two stub classifiers ("production"→newsletter,
   "candidate"→urgent), feeds the results into
   `PrimaryCombiner(primary_name="production")`. Asserts the combined
   result equals production's, showing the combiner always defers to one
   named target regardless of the others.

6. **`test_combine.py::test_highest_confidence_combiner_picks_the_highest_scoring_result`**
   Dispatches to two classifiers with different confidence scores (0.4 vs
   0.9), combines with `HighestConfidenceCombiner()`. Asserts the
   higher-confidence category wins — real ensemble/voting behavior.

7. **`test_combine.py::test_dispatching_classifier_feeds_the_existing_rule_engine_unmodified`**
   Wraps a `Dispatcher` + `HighestConfidenceCombiner` into a
   `DispatchingClassifier`, passes it as `classifier=` to the real
   `rules.engine.evaluate()` alongside an
   `local_classifier_category_in=["urgent"]` rule. Asserts the verdict
   matches that rule, proving the ensemble plugs into the rule engine
   with zero changes to it.

8. **`test_combine_edge_cases.py::test_primary_combiner_raises_when_named_target_missing`**
   `PrimaryCombiner(primary_name="does-not-exist")` combined against
   results only containing `"production"`. Asserts `CombineError`,
   confirming a typo'd primary name fails loudly rather than substituting
   another target.

9. **`test_combine_edge_cases.py::test_primary_combiner_raises_when_named_target_failed`**
   Primary target's entry is a `RuntimeError` (simulating that target
   having failed). Asserts `CombineError` — a failed primary isn't
   silently swallowed.

10. **`test_combine_edge_cases.py::test_highest_confidence_combiner_raises_when_all_targets_failed`**
    Every entry in the results dict is a `RuntimeError`. Asserts
    `CombineError` — never resolves to a default/empty result when
    nothing succeeded.

11. **`test_combine_edge_cases.py::test_highest_confidence_combiner_breaks_ties_by_target_order`**
    Two targets report the same top score (0.5) for different categories.
    Asserts the first-listed target's category wins — ties resolved
    deterministically by insertion order, not hash order.

12. **`test_dispatcher.py::test_dispatch_runs_all_targets_and_collects_results`**
    Two named stub classifiers, `dispatch()` called. Asserts both results
    present under their names, confirming fan-out collects every target's
    output.

13. **`test_dispatcher.py::test_dispatch_with_a_single_target`**
    One target only. Asserts the result dict is exactly that one entry —
    single-target dispatch is just N=1, not a special path.

14. **`test_dispatcher.py::test_dispatch_isolates_a_failing_target_from_the_others`**
    One working classifier + one that raises `RuntimeError`. Asserts the
    working one's result is normal and the failing one's entry is the
    caught exception — failure isolation, not an aborted dispatch.

15. **`test_dispatcher_edge_cases.py::test_dispatch_with_no_targets_returns_empty_dict`**
    `Dispatcher({})`, zero targets. Asserts `dispatch()` returns `{}` — a
    no-op, not an error; "is this useful" is pushed to the Combiner
    layer.

### tests/core/providers/jmap

16. **`test_backoff.py::test_next_delay_returns_schedule_value_for_attempt_in_range`**
    Schedule `[2,5,15,60,300]`; `next_delay(attempt=0)` and
    `next_delay(attempt=2)`. Asserts `2.0` and `15.0` — attempt N indexes
    the Nth scheduled delay.

17. **`test_backoff.py::test_next_delay_clamps_to_final_value_beyond_schedule_length`**
    3-element schedule, `attempt=10`. Asserts result is the last value
    (`15.0`) — attempts past the end clamp instead of raising or
    escalating forever.

18. **`test_backoff_edge_cases.py::test_next_delay_raises_on_empty_schedule`**
    `next_delay([], attempt=0)`. Asserts `ValueError` matching "empty" —
    a misconfigured empty schedule is a config error, not instant/infinite
    reconnect.

19. **`test_backoff_edge_cases.py::test_next_delay_raises_on_negative_attempt`**
    `next_delay([2,5], attempt=-1)`. Asserts `ValueError` matching
    "attempt" — a negative attempt (caller bug) is rejected explicitly.

20. **`test_mailboxes.py::test_resolve_returns_mailbox_id_for_known_role`**
    Fetch returns an "inbox" and a "drafts" mailbox. Asserts
    `resolve("inbox")`/`resolve("drafts")` return the right ids.

21. **`test_mailboxes.py::test_resolve_only_fetches_once_across_multiple_calls`**
    Counting `fetch()`, `resolve("inbox")` called 3x. Asserts
    `calls == 1` — caching, not re-fetching per lookup.

22. **`test_mailboxes.py::test_resolve_raises_clear_error_for_unknown_role`**
    Only "inbox" exists; `resolve("drafts")` called. Asserts
    `UnknownMailboxRoleError` — fails loudly, not `None`/bare `KeyError`.

23. **`test_mailboxes.py::test_refresh_forces_a_re_fetch_on_next_resolve`**
    `resolve("inbox")`, then `refresh()`, then `resolve("inbox")` again.
    Asserts `calls == 2` — `refresh()` invalidates the cache.

24. **`test_mailboxes_edge_cases.py::test_a_failed_fetch_is_not_cached`**
    Fetch raises on first call, succeeds on second. First `resolve()`
    raises; second returns `"mb-1"` with `attempts == 2` — a failed fetch
    isn't permanently cached.

25. **`test_mailboxes_edge_cases.py::test_duplicate_role_across_mailboxes_raises_ambiguous_error`**
    Two mailboxes both claim role "inbox". Asserts
    `AmbiguousMailboxRoleError` — refuses to silently pick a winner
    (misfile risk).

26. **`test_mailboxes_edge_cases.py::test_mailboxes_without_a_role_are_ignored`**
    One "inbox" mailbox + one `role=None` custom mailbox. Asserts
    `resolve("inbox")` still works — role-less mailboxes are skipped, not
    disruptive.

### tests/core/rules

27. **`test_engine.py::test_first_matching_enabled_rule_wins`**
    Two enabled rules both match a newsletter-domain message; earlier one
    wins. Confirms first-match-wins ordering.

28. **`test_engine.py::test_disabled_rule_is_skipped_even_if_condition_matches`**
    Same setup but the first rule is `enabled=False`. Asserts the
    fallback rule matches instead — disabled rules are skipped entirely.

29. **`test_engine.py::test_unmatched_message_falls_back_to_default_policy`**
    Message from an unrelated domain against a rule that doesn't match
    it. Asserts `matched_rule_id is None` and the caller-supplied default
    action is used.

30. **`test_engine.py::test_from_domain_in_condition_matches_sender_domain`**
    Matching vs. non-matching domain messages against one
    `from_domain_in` rule. Confirms exact, specific domain matching.

31. **`test_engine.py::test_local_classifier_category_condition_consults_configured_classifier`**
    A `StubUrgentClassifier` always returns "urgent"; a rule keys off
    `local_classifier_category_in=["urgent"]`. Asserts the rule fires
    with the right reason — the engine defers entirely to the injected
    classifier.

32. **`test_engine_edge_cases.py::test_empty_rule_list_returns_default_policy`**
    `evaluate(message, [], ...)`. Asserts zero rules behaves identically
    to "no rule matched".

33. **`test_engine_edge_cases.py::test_condition_with_no_fields_set_never_matches`**
    An all-default `Condition()` ahead of an `always=True` fallback.
    Asserts the fallback wins — an empty condition matches nothing,
    guarding against an accidental catch-all from a malformed rule file.

34. **`test_engine_edge_cases.py::test_classifier_condition_without_configured_classifier_raises`**
    A classifier-dependent rule, but no `classifier=` passed to
    `evaluate()`. Asserts `RuntimeError` — fails loudly rather than
    silently not matching.

35. **`test_engine_edge_cases.py::test_classifier_is_invoked_at_most_once_per_evaluation`**
    A `CountingClassifier` and three classifier-backed rules checked in
    sequence. Asserts `calls == 1` — the classification result is
    memoized within one `evaluate()` call.

### tests/core/sources

36. **`test_integration.py::test_replaying_a_fixture_drives_the_rule_engine_end_to_end`**
    A `TriggeredSource` built from real `ImmediateTrigger` +
    `SequenceContentFetcher` (no I/O) replays two fixture messages
    through a `while source.poll()` loop, each fed to the real rule
    engine. Asserts correct verdicts for both — proves the whole
    trigger→fetcher→source→rule-engine chain works together.

37. **`test_replay.py::test_immediate_trigger_never_blocks`**
    `ImmediateTrigger().wait()`. Asserts it returns `None` immediately —
    no sleeping or side effects.

38. **`test_replay.py::test_sequence_content_fetcher_returns_messages_in_batches`**
    3 messages, `batch_size=2`, `fetch()` called twice. Asserts batches
    of `[msg-0, msg-1]` then `[msg-2]` — ordered, batch_size-at-a-time
    consumption.

39. **`test_replay.py::test_sequence_content_fetcher_returns_empty_once_exhausted`**
    1 message consumed, then `fetch()` called twice more. Asserts both
    return `[]` — steady-state "caught up" behavior, not an error.

40. **`test_replay_edge_cases.py::test_sequence_content_fetcher_rejects_non_positive_batch_size`**
    `batch_size=0` and `batch_size=-1` construction attempts. Asserts
    both raise `ValueError` at construction — rejected immediately, not
    left to fail later.

41. **`test_replay_edge_cases.py::test_sequence_content_fetcher_with_empty_messages_returns_empty_immediately`**
    Empty fixture list, `batch_size=5`. Asserts `fetch()` returns `[]` —
    behaves like already-exhausted, not an error.

42. **`test_replay_edge_cases.py::test_sequence_content_fetcher_batch_larger_than_remaining_returns_partial_batch`**
    1 message, `batch_size=100`. Asserts first `fetch()` returns just the
    one message (not padded), second returns `[]`.

43. **`test_triggered.py::test_triggered_source_calls_wait_before_fetch`**
    Recording trigger/fetcher append markers to a shared list on
    `poll()`. Asserts order is `["wait", "fetch"]` — trigger always fires
    before fetch, never the reverse.

44. **`test_triggered.py::test_triggered_source_returns_the_fetchers_result`**
    No-op trigger + fixed fetcher. Asserts `poll()` returns exactly the
    fetcher's list — no transformation applied.

45. **`test_triggered_edge_cases.py::test_triggered_source_re_triggers_on_every_poll_call`**
    Counting trigger, `poll()` called 3x. Asserts `wait_calls == 3` —
    every poll re-triggers, not just the first.

### Graduated from xfail (M0 — now ordinary passing tests)

These three started as `pytest.mark.xfail`, each describing real
target behavior from `docs/DESIGN.md` before it was implemented, each
verified with `--runxfail` to fail for the right reason before being
marked. All three are now implemented; each marker was removed only
after re-verifying with `--runxfail` that the test passed for real.

46. **`test_secretspec_config.py::test_secretspec_toml_declares_the_required_secrets`**
    Reads `secretspec.toml` from the repo root and parses it as TOML,
    then asserts `profiles.default` declares both `JMAP_API_TOKEN` and
    `ANTHROPIC_API_KEY` — the secrets `docs/DESIGN.md` §7.3 specifies.
    Passes now that the real manifest exists at the repo root.

47. **`tests/cli/test_main.py::test_help_prints_usage_and_exits_zero`**
    Runs `python -m spork.cli.main --help` as a subprocess. Asserts exit
    code 0, "usage" present in stdout, and no traceback in stderr.
    Passes now that `spork.cli.main` is a Typer app.

48. **`tests/daemon/test_main.py::test_help_prints_usage_and_exits_zero`**
    Same as 47, for `python -m spork.daemon.main --help`. Passes now
    that `spork.daemon.main` is a Typer single-command app.

### tests/core (secrets) — real implementation

49–71 are jmap/sources/state, described earlier in their own
sections above (numbers assigned in commit order, not file order —
see each section heading). These pick back up at 72.

72. **`test_secrets.py::test_resolve_secrets_reads_declared_values_via_env_provider`**
    Writes a temp manifest declaring `FOO_TOKEN`, sets it as an env var,
    calls `resolve_secrets(manifest, provider="env://", reason="test")`.
    Asserts `secrets.get("FOO_TOKEN")` returns the env var's value —
    exercised against the real SecretSpec SDK's `env://` provider, not
    a mock.

73. **`test_secrets.py::test_resolve_secrets_raises_on_missing_required_secret`**
    Same manifest, but the env var is unset (`monkeypatch.delenv`).
    Asserts `resolve_secrets()` raises `SecretsError` — a required
    secret with nothing providing it fails at resolve time.

74. **`test_secrets.py::test_secrets_get_raises_clear_error_for_undeclared_name`**
    After a successful resolution, calls `secrets.get("NEVER_DECLARED")`.
    Asserts `SecretsError`, not a bare `KeyError`.

75. **`test_secrets.py::test_resolve_secrets_raises_for_a_nonexistent_manifest_file`**
    Calls `resolve_secrets()` with a path that doesn't exist. Asserts
    `SecretsError` — SecretSpec's own "no manifest found" error wrapped,
    not leaked through unwrapped.

76. **`test_secrets.py::test_resolve_secrets_supports_optional_secrets_without_error`**
    A manifest with one `required = false` secret, nothing providing a
    value. Asserts `resolve_secrets()` itself doesn't raise (only a
    later `.get()` on that specific name would).

77. **`test_secrets_edge_cases.py::test_resolve_secrets_wraps_malformed_toml_as_secrets_error`**
    A manifest file containing deliberately broken TOML syntax. Asserts
    `SecretsError`, confirming SecretSpec's own parse error (verified
    empirically to also be a `SecretSpecError`) gets wrapped like every
    other failure mode.

78. **`test_secrets_edge_cases.py::test_resolve_secrets_respects_the_given_profile`**
    A manifest where `FOO_TOKEN` is required under `profiles.default`
    but `required = false` under `profiles.development`, with no value
    provided. Asserts resolving with `profile="development"` succeeds
    (would raise under the default profile) — proving `profile=` is
    actually forwarded to SecretSpec, not silently ignored.

79. **`tests/cli/test_main.py::test_version_prints_the_installed_version_and_exits_zero`**
    Runs `python -m spork.cli.main --version` as a subprocess. Asserts
    exit code 0 and `"spork"` present in stdout.

80. **`tests/daemon/test_main.py::test_version_prints_the_installed_version_and_exits_zero`**
    Runs `python -m spork.daemon.main --version` as a subprocess.
    Asserts exit code 0 and `"sporkd"` present in stdout — and that it
    exits cleanly rather than falling through to the daemon loop's
    `NotImplementedError`.

### tests/core/providers/jmap — NotImplementedError-catching (M1)

These pass normally — raising `NotImplementedError` is the correct,
specified behavior at this stage (see the M1 coverage table above),
not a placeholder assertion.

49. **`test_client.py::test_connect_raises_not_implemented`**
    Constructs `JmapClient(host=..., api_token=...)` and calls
    `connect()`. Asserts `NotImplementedError`, confirming the
    session-bootstrap placeholder is in place with the right shape.

50. **`test_client.py::test_fetch_new_messages_raises_not_implemented`**
    Calls `client.fetch_new_messages(since_cursor=None)`. Asserts
    `NotImplementedError`, covering the batched-fetch checklist item
    (folded into this same method).

51. **`test_push.py::test_wait_raises_not_implemented`**
    Constructs `JmapPushTrigger(client)` and calls `wait()` directly.
    Asserts `NotImplementedError`.

52. **`test_push.py::test_composes_into_triggered_source_like_any_other_trigger`**
    Wires a `JmapPushTrigger` into a real `TriggeredSource` alongside a
    fetcher that would raise `AssertionError` if ever called. Asserts
    calling `source.poll()` raises `NotImplementedError` (from
    `wait()`, before the fetcher runs), proving `JmapPushTrigger`
    satisfies the `Trigger` contract structurally — it plugs into the
    M1a machinery exactly like `ImmediateTrigger`/`IntervalTimer` do,
    even though its own behavior isn't implemented yet.

### tests/core/sources — timer + fallback (M1)

53. **`test_timer.py::test_interval_timer_sleeps_for_the_configured_interval`**
    Constructs `IntervalTimer(30.0, sleep=slept.append)` (an injected
    fake sleep) and calls `wait()`. Asserts `slept == [30.0]`.

54. **`test_timer.py::test_interval_timer_waits_again_on_every_call`**
    Calls `wait()` three times on one timer. Asserts the fake sleep was
    invoked three times with the same interval — every call re-waits,
    not just the first.

55. **`test_timer_edge_cases.py::test_interval_timer_rejects_non_positive_interval`**
    Attempts `IntervalTimer(0.0)` and `IntervalTimer(-1.0)`. Asserts
    both raise `ValueError` at construction.

56. **`test_fallback.py::test_fallback_uses_primary_when_it_succeeds`**
    Builds a `FallbackSource` from a working primary and a
    `_FailingSource` secondary. Asserts `poll()` returns the primary's
    result, confirming the secondary is never touched when primary
    works.

57. **`test_fallback.py::test_fallback_switches_to_secondary_when_primary_raises`**
    Primary is `_FailingSource` (raises `ConnectionError`), secondary
    returns fixed messages. Asserts `poll()` returns the secondary's
    result instead of propagating the error.

58. **`test_fallback.py::test_fallback_retries_primary_on_the_next_poll_call`**
    A `RecoveringSource` fails only on its first call. After one
    fallback-triggering `poll()`, a second `poll()` is asserted to
    return the (now-recovered) primary's result — proving the source
    doesn't latch onto the secondary permanently.

59. **`test_fallback.py::test_fallback_only_catches_configured_exception_types`**
    Constructs `FallbackSource(..., catch=(TimeoutError,))` with a
    primary that raises `ConnectionError`. Asserts `ConnectionError`
    propagates uncaught, confirming `catch` actually narrows what
    triggers a fallback rather than swallowing everything.

60. **`test_fallback_edge_cases.py::test_fallback_propagates_when_both_primary_and_secondary_fail`**
    Both primary and secondary are failing sources. Asserts the
    resulting `poll()` call still raises — nothing left to fall back
    to, so the error isn't hidden.

61. **`test_fallback_edge_cases.py::test_fallback_does_not_catch_baseexception_subclasses`**
    Primary raises `KeyboardInterrupt` (a `BaseException`, not
    `Exception`). Asserts it propagates through the default
    `catch=(Exception,)` rather than being swallowed — a daemon must
    never suppress a shutdown signal because it superficially resembles
    a connection error.

### tests/core/state (M1)

62. **`test_db.py::test_set_and_get_cursor_roundtrips`**
    Opens a `StateDB` against a tmp-path file, calls
    `set_cursor("account-1", "state-abc123")`, then `get_cursor`.
    Asserts the exact value round-trips.

63. **`test_db.py::test_get_cursor_returns_none_when_never_set`**
    Calls `get_cursor` for an account with no prior `set_cursor` call.
    Asserts `None`, not an error.

64. **`test_db.py::test_set_cursor_overwrites_previous_value`**
    Calls `set_cursor` twice for the same account with different
    values. Asserts `get_cursor` returns the second (latest) value.

65. **`test_db.py::test_has_processed_is_false_for_unknown_message`**
    Calls `has_processed("msg-1")` with nothing ever marked. Asserts
    `False`.

66. **`test_db.py::test_mark_processed_then_has_processed_is_true`**
    Calls `mark_processed("msg-1", ...)` then `has_processed("msg-1")`.
    Asserts `True` — the idempotency primitive M2's action executor
    will consult.

67. **`test_db.py::test_schema_is_created_on_a_fresh_db_file`**
    Opens `StateDB` against a path that doesn't exist yet, performs one
    write. Asserts the file now exists — schema creation is automatic,
    no separate init step.

68. **`test_db_edge_cases.py::test_mark_processed_twice_updates_the_record`**
    Calls `mark_processed` twice for the same `jmap_id` with different
    `action_taken`/`processed_at` values, then reads the row back via a
    *separate* SQLite connection to the same file (not `StateDB`'s own
    internals). Asserts the second call's values won — an upsert, not
    an error on the duplicate key.

69. **`test_db_edge_cases.py::test_multiple_accounts_have_independent_push_cursors`**
    Sets different cursors for `"account-1"` and `"account-2"`. Asserts
    each `get_cursor` call returns only its own account's value —
    no cross-account bleed.

70. **`test_db_edge_cases.py::test_reopening_an_existing_db_file_preserves_data`**
    Writes a cursor and a processed-message record via one `StateDB`
    instance, closes it, opens a *new* `StateDB` instance against the
    same file path. Asserts both pieces of data are still there —
    genuine on-disk persistence, not in-memory-only state.

71. **`test_db_edge_cases.py::test_using_the_db_after_close_raises`**
    Calls `close()`, then calls `get_cursor` on the same instance.
    Asserts an exception is raised (sqlite3's `ProgrammingError` on a
    closed connection) rather than the call silently no-op-ing.

### tests/core/providers (M1b)

81. **`jmap/test_provider.py::test_build_source_returns_a_triggered_source`**
    Constructs `JmapProvider(host=..., api_token=...)` and calls
    `build_source()`. Asserts the result is a `TriggeredSource` —
    the same composition shape any `Source` consumer expects.

82. **`jmap/test_provider.py::test_source_poll_raises_not_implemented`**
    Calls `.poll()` on the built `Source`. Asserts `NotImplementedError`,
    propagated from `JmapPushTrigger.wait()` — proving `JmapProvider`
    wires the real (if still-stubbed) pieces together.

83. **`jmap/test_provider.py::test_content_fetcher_delegates_to_the_client_directly`**
    Constructs `_JmapContentFetcher(client)` directly (not via
    `build_source()`, where `wait()` would raise first and mask this)
    and calls `.fetch()`. Asserts `NotImplementedError`, propagated from
    `JmapClient.fetch_new_messages()` — proving the fetcher half is a
    real delegation, not a second placeholder.

84. **`test_loader.py::test_load_provider_imports_and_instantiates_by_spec`**
    Calls `load_provider(f"{__name__}:_FixtureProvider")` (a fixture
    class defined in the test module, self-referenced via `__name__`).
    Asserts the result is an instance of that class with its default
    `label`.

85. **`test_loader.py::test_load_provider_passes_through_constructor_kwargs`**
    Same, but with `label="custom"` passed to `load_provider()`.
    Asserts the constructed instance's `label` reflects it — kwargs
    reach the provider unmodified.

86. **`test_loader.py::test_load_provider_raises_for_malformed_spec`**
    Calls `load_provider("no-colon-in-this-spec")`. Asserts
    `ProviderLoadError` — a spec missing the `:` separator is rejected
    before any import is attempted.

87. **`test_loader_edge_cases.py::test_load_provider_raises_for_unimportable_module`**
    Calls `load_provider("this.module.does.not.exist:Whatever")`.
    Asserts `ProviderLoadError`, not a raw `ImportError`.

88. **`test_loader_edge_cases.py::test_load_provider_raises_for_missing_class_attribute`**
    Calls `load_provider(f"{__name__}:ThisClassDoesNotExist")` against a
    real, importable module that just doesn't define that class.
    Asserts `ProviderLoadError`, not a raw `AttributeError`.

89. **`test_loader_edge_cases.py::test_load_provider_raises_when_construction_fails`**
    Calls `load_provider(f"{__name__}:_FixtureProvider", unexpected_kwarg=True)`
    — a kwarg the fixture class's `__init__` doesn't accept. Asserts
    `ProviderLoadError`, not a raw `TypeError`.

### tests/core/rules (loader, M2)

90. **`test_loader.py::test_load_rules_parses_valid_rules_toml`**
    A well-formed rules.toml with two `[[rule]]` entries. Asserts the
    parsed `Rule` objects match in id order, and that nested
    `when`/`action` fields came through correctly.

91. **`test_loader.py::test_load_rules_returns_empty_list_for_no_rules`**
    An empty file. Asserts `load_rules()` returns `[]`, not an error.

92. **`test_loader.py::test_load_rules_raises_for_malformed_toml`**
    Broken TOML syntax. Asserts `RulesLoadError`, not a raw
    `tomllib.TOMLDecodeError`.

93. **`test_loader.py::test_load_rules_raises_for_invalid_rule_fields`**
    A rule with `action.type = "delete"` (not in the closed set).
    Asserts `RulesLoadError`, not a raw pydantic `ValidationError`.

94. **`test_loader.py::test_load_rules_raises_for_duplicate_ids`**
    Two `[[rule]]` entries sharing `id = "dup"`. Asserts
    `RulesLoadError`.

95. **`test_loader.py::test_load_rules_raises_for_missing_file`**
    A path that doesn't exist. Asserts `RulesLoadError`, not a raw
    `FileNotFoundError`.

96. **`test_loader_edge_cases.py::test_load_rules_raises_for_unknown_field_in_a_rule`**
    A rule with `enalbed = false` (typo for `enabled`). Asserts
    `RulesLoadError` — confirmed red against the pre-fix schema before
    `extra="forbid"` was added, proving the fix actually closes the
    silent-typo gap it targets.

97. **`test_loader_edge_cases.py::test_load_rules_raises_for_unknown_field_in_a_condition`**
    Same, for a typo'd `when` field (`form_domain_in` instead of
    `from_domain_in`). Same reasoning.

### tests/core/state (audit_log, M2)

98. **`test_audit_log.py::test_write_audit_entry_then_get_audit_entries_returns_it`**
    Writes one entry, reads it back. Asserts all fields round-trip.

99. **`test_audit_log.py::test_get_audit_entries_filters_by_jmap_id`**
    Two entries for different `jmap_id`s. Asserts `jmap_id=` filtering
    returns only the matching one.

100. **`test_audit_log.py::test_get_audit_entries_returns_oldest_first`**
    Two entries for the same message, written in order. Asserts they
    come back in write order.

101. **`test_audit_log.py::test_get_audit_entries_returns_empty_list_when_none_written`**
    A fresh DB. Asserts `get_audit_entries()` returns `[]`.

102. **`test_audit_log_edge_cases.py::test_get_audit_entries_for_unknown_jmap_id_returns_empty`**
    Filters to a `jmap_id` with no entries (while others exist).
    Asserts `[]`, not an error.

103. **`test_audit_log_edge_cases.py::test_audit_log_persists_across_reopening_the_db_file`**
    Writes an entry, closes the DB, reopens the same file with a fresh
    `StateDB` instance. Asserts the entry is still there.

### tests/core/providers (ActionApplier, M2)

104. **`jmap/test_client.py::test_apply_action_raises_not_implemented`**
    Calls `client.apply_action(message, Action(type="move", ...))`.
    Asserts `NotImplementedError` — same live-session blocker as
    `connect()`/`fetch_new_messages()`.

105. **`jmap/test_provider.py::test_build_action_applier_returns_something_that_can_apply`**
    Calls `provider.build_action_applier()`, then `.apply(...)` on the
    result. Asserts `NotImplementedError` — the write-side counterpart
    to `test_source_poll_raises_not_implemented`.

106. **`jmap/test_provider.py::test_action_applier_delegates_to_the_client_directly`**
    Constructs `_JmapActionApplier(client)` directly and calls
    `.apply(...)`. Asserts `NotImplementedError`, propagated from
    `JmapClient.apply_action()` — proving it's a real delegation, not
    a second placeholder (mirrors the content-fetcher equivalent, 83).

### tests/core/actions (ActionExecutor, M2)

107. **`test_executor.py::test_executor_applies_move_action_via_the_applier`**
    A move action, executed. Asserts the stub applier's `.apply()` was
    called with the exact message/action.

108. **`test_executor.py::test_executor_applies_tag_action_via_the_applier`**
    Same, for `tag`.

109. **`test_executor.py::test_executor_ignore_action_is_a_noop_applier_never_called`**
    An `ignore` action. Asserts the applier's `.apply()` was never
    called — nothing to apply.

110. **`test_executor.py::test_executor_rejects_escalate_action`**
    An `escalate` action. Asserts `ActionExecutionError`, and that the
    applier was never called.

111. **`test_executor.py::test_executor_rejects_move_action_without_a_mailbox`**
    A `move` action with `mailbox=None`. Asserts `ActionExecutionError`
    before the applier is ever reached.

112. **`test_executor_edge_cases.py::test_executor_rejects_tag_action_without_a_mailbox`**
    Same as 111, for `tag`.

113. **`test_executor_edge_cases.py::test_executor_propagates_applier_failure`**
    A stub applier that always raises. Asserts the exception
    propagates out of `execute()` rather than being swallowed.

### tests/core/pipeline (process_message, M2)

Relocated from `tests/core/test_pipeline.py`/`test_pipeline_edge_cases.py`
(pure structural move, no content changes — entries 114-121 below are
unchanged from their original M2 form) now that `process_message()`
lives in `spork.core.pipeline.default`, one file among several in the
`spork.core.pipeline` package built from composable Filter/Selector
modules (§9.4). See "tests/core/pipeline (Filter/Selector pipeline
framework, §9.4)" further down for the modules themselves.

114. **`test_default.py::test_process_message_skips_already_processed_messages`**
    A message already `mark_processed()`-ed. Asserts `process_message()`
    returns `None` and never touches the applier.

115. **`test_default.py::test_process_message_applies_matched_rule_action_and_marks_processed`**
    A message matching a `move` rule. Asserts the applier was called,
    `has_processed()` becomes `True`, and the returned verdict matches.

116. **`test_default.py::test_process_message_writes_an_audit_entry_for_applied_actions`**
    After processing, asserts exactly one audit entry exists with the
    injected clock's timestamp.

117. **`test_default.py::test_process_message_handles_escalate_without_calling_executor`**
    A verdict resolving to `escalate`. Asserts the applier was never
    called, but the message is still marked processed (the interim
    pending-Tier-2 policy, docs/DESIGN.md §9).

118. **`test_default.py::test_process_message_returns_the_verdict`**
    Asserts the returned `RuleVerdict` matches what was actually acted
    on.

119. **`test_default_edge_cases.py::test_process_message_propagates_executor_failure_and_does_not_mark_processed`**
    A failing applier. Asserts the exception propagates AND that
    neither `has_processed()` nor the audit log reflect the message —
    the retry-on-next-cycle guarantee the ordering exists for.

120. **`test_default_edge_cases.py::test_mark_processed_uses_the_injected_clock`**
    Checks `processed_messages.processed_at` directly (via a fresh
    connection) after processing with a fixed clock. Asserts it
    matches — not just the audit entry's timestamp, per 116.

121. **`test_default_edge_cases.py::test_default_clock_produces_a_real_parseable_timestamp`**
    Calls `process_message()` without `now=` at all (the real default
    clock). Asserts the recorded timestamp is genuinely parseable —
    proving the default itself works, not just that a fake one can
    replace it.

### tests/core/providers/file (FileProvider, M1b)

122. **`test_messages.py::test_load_messages_parses_a_valid_json_file`**
    A well-formed messages.json with two entries. Asserts
    `NormalizedMessage`s come back in file order with the right fields,
    including a non-default `headers`/`mailbox_ids`.

123. **`test_messages.py::test_load_messages_returns_empty_list_for_empty_array`**
    A file containing `[]`. Asserts zero messages, not an error.

124. **`test_messages.py::test_load_messages_raises_for_malformed_json`**
    Broken JSON syntax. Asserts `MessagesLoadError`, not a raw
    `json.JSONDecodeError`.

125. **`test_messages.py::test_load_messages_raises_for_non_array_json`**
    A file whose top level is a JSON object, not an array. Asserts
    `MessagesLoadError`.

126. **`test_messages.py::test_load_messages_raises_for_missing_required_field`**
    An entry missing `thread_id` etc. Asserts `MessagesLoadError`
    naming the field, not a raw `KeyError`.

127. **`test_messages.py::test_load_messages_raises_for_missing_file`**
    A nonexistent path. Asserts `MessagesLoadError`, not a raw
    `FileNotFoundError`.

128. **`test_provider.py::test_build_source_returns_a_triggered_source`**
    Asserts `FileProvider.build_source()` returns a `TriggeredSource` —
    the same generic composition any `Source` consumer expects
    (docs/DESIGN.md §9.2), not a bespoke shape.

129. **`test_provider.py::test_source_poll_replays_every_message_then_settles_empty`**
    Two messages in the file. Asserts the first `poll()` returns both,
    in order, and the second `poll()` returns `[]` — the same
    steady-state a live, caught-up source settles into.

130. **`test_provider.py::test_build_action_applier_returns_something_that_can_apply`**
    Asserts calling `.apply()` on what `build_action_applier()` returns
    actually creates the actions log file — the write half of the
    `Provider` contract, real, not a placeholder.

131. **`test_provider.py::test_action_applier_appends_one_jsonl_entry_per_apply_call`**
    Two `.apply()` calls. Asserts two JSON-lines entries land in order,
    each with the right `message_id`/`action_type`/`mailbox`.

132. **`test_messages_edge_cases.py::test_load_messages_raises_when_an_entry_is_not_an_object`**
    An array containing a bare string instead of an object. Asserts
    `MessagesLoadError` naming the index.

133. **`test_messages_edge_cases.py::test_load_messages_defaults_headers_and_mailbox_ids_when_omitted`**
    An entry with no `headers`/`mailbox_ids` keys at all. Asserts
    `NormalizedMessage`'s own empty defaults, not a load error.

134. **`test_messages_edge_cases.py::test_load_messages_ignores_unknown_fields_on_an_entry`**
    An entry with an extra field `NormalizedMessage` doesn't have.
    Asserts it loads anyway — deliberately unlike `rules.schema`'s
    `extra="forbid"`, since a message fixture isn't hand-edited config.

135. **`test_messages_edge_cases.py::test_load_messages_accepts_a_str_path`**
    Calls `load_messages()` with a `str` instead of a `Path`. Asserts
    it works the same.

136. **`test_provider_edge_cases.py::test_build_source_with_an_empty_messages_file_polls_to_nothing`**
    An empty messages.json. Asserts `poll()` returns `[]`, not an
    error.

137. **`test_provider_edge_cases.py::test_action_applier_appends_across_separate_build_calls`**
    Two separately-obtained appliers pointed at the same log path.
    Asserts both entries land — `build_action_applier()` doesn't own
    exclusive state a second call would reset.

138. **`test_provider_edge_cases.py::test_file_provider_accepts_str_paths`**
    Constructs `FileProvider` with `str` paths for both arguments.
    Asserts both `build_source()` and `build_action_applier()` still
    work.

### tests/cli/commands (spork rules test, M2)

139. **`test_rules.py::test_rules_test_help_works`**
    `spork rules test --help` via subprocess. Asserts exit 0 and usage
    text.

140. **`test_rules.py::test_rules_test_with_a_valid_file_loads_then_fails_on_the_live_jmap_gap`**
    A well-formed rules.toml. Asserts exit 1, `"Loaded 1 rule"` really
    printed (proving loading isn't stubbed), and no raw traceback in
    stderr for the live-JMAP `NotImplementedError`.

141. **`test_rules.py::test_rules_test_with_an_invalid_file_reports_a_clean_error`**
    Malformed TOML. Asserts exit 1, `"Error"` in stderr, no
    `"Traceback"` — `RulesLoadError` caught and reported cleanly, not
    left to propagate.

142. **`test_rules.py::test_rules_test_with_a_missing_file_reports_a_clean_error`**
    A nonexistent path. Same clean-error assertions as 141.

143. **`test_rules.py::test_rules_group_appears_in_top_level_help`**
    `spork --help`. Asserts `"rules"` appears — confirms
    `app.add_typer()` wiring, not just that the module imports.

144. **`test_rules_edge_cases.py::test_rules_test_with_a_file_containing_no_rules_still_loads_then_hits_the_gap`**
    An empty rules.toml (zero `[[rule]]` entries — valid, per
    `load_rules()`). Asserts `"Loaded 0 rule(s)"` and still reaches the
    live-JMAP gap, same as a file with rules.

145. **`test_rules_edge_cases.py::test_rules_test_with_no_file_argument_is_a_usage_error`**
    Omits the required `rules_file` argument entirely. Asserts exit 2
    (Typer's own usage error) and no traceback — proves this path never
    reaches `load_rules()` at all.

146. **`test_rules_edge_cases.py::test_rules_group_help_lists_the_test_command`**
    `spork rules --help`. Asserts `"test"` is listed.

### tests/cli/commands (spork doctor, M1)

147. **`test_doctor.py::test_doctor_help_works`**
    `spork doctor --help` via subprocess. Asserts exit 0 and usage
    text.

148. **`test_doctor.py::test_doctor_reports_a_clean_error_not_a_traceback`**
    `spork doctor` with no live JMAP session available. Asserts exit
    1, `"Error"` in stderr, no `"Traceback"` — the connectivity-check
    `NotImplementedError` caught and reported cleanly.

149. **`test_doctor.py::test_doctor_appears_in_top_level_help`**
    `spork --help`. Asserts `"doctor"` is listed — confirms
    `app.command("doctor")(doctor)` wiring, not just that the module
    imports.

### tests/core/llm (body cleaning, M3)

150. **`test_clean.py::test_clean_body_strips_html_tags`**
    A body with nested `<p>`/`<b>` tags. Asserts no `<` survives and
    the text content is preserved.

151. **`test_clean.py::test_clean_body_collapses_a_quote_chain_introduced_by_wrote_line`**
    A body with new content followed by an "On ... wrote:" header and
    quoted lines. Asserts the new content survives and everything from
    the header onward is dropped.

152. **`test_clean.py::test_clean_body_collapses_a_quote_chain_introduced_by_gt_prefixed_lines`**
    A body going straight into `>`-prefixed lines with no "wrote:"
    header. Asserts the quoted portion is still dropped.

153. **`test_clean.py::test_clean_body_truncates_long_bodies`**
    A body far longer than `max_chars`. Asserts the result length is
    bounded and a truncation marker is present.

154. **`test_clean.py::test_clean_body_leaves_a_short_plain_body_unchanged_in_substance`**
    A short, already-plain, unquoted body. Asserts it passes through
    intact — cleaning doesn't mangle the common case.

155. **`test_clean.py::test_clean_body_normalizes_excess_blank_lines`**
    An HTML-sourced body producing runs of blank lines after tag
    stripping. Asserts they collapse rather than bloating the prompt.

156. **`test_clean_edge_cases.py::test_clean_body_handles_an_empty_string`**
    Empty input. Asserts empty output, not an error.

157. **`test_clean_edge_cases.py::test_clean_body_decodes_html_entities`**
    A body containing `&amp;`/`&mdash;`. Asserts entities decode to
    real characters, not the literal escape sequence.

158. **`test_clean_edge_cases.py::test_clean_body_uses_the_earliest_quote_marker_when_several_are_present`**
    A body with both a "wrote:" header and a later "-----Original
    Message-----" line. Asserts the cut happens at the earliest
    marker, so no quoted content leaks through either path.

159. **`test_clean_edge_cases.py::test_clean_body_does_not_add_a_truncation_marker_at_exactly_max_chars`**
    A body exactly `max_chars` long. Asserts it's returned unchanged
    with no spurious truncation marker — the limit is inclusive.

160. **`test_clean_edge_cases.py::test_clean_body_truncates_a_single_long_word_with_no_space_to_break_on`**
    A single unbroken "word" longer than `max_chars`. Asserts
    truncation still completes cleanly rather than crashing on the
    word-boundary split.

### tests/core/pipeline (Filter/Selector/Augment pipeline framework, §9.4)

`spork.core.pipeline.core` (generic Payload/Filter/Selector/Augment/
Pipeline) tested with a plain `int` metadata type to prove genuine
generality; `spork.core.pipeline.meta`/`modules` (the concrete message
pipeline) tested against a bare `Payload[MessageMeta]` per module, no
`Pipeline` or `process_message()` call needed.

161. **`test_core.py::test_pipeline_runs_filters_in_order`**
    Three filters each appending a letter. Asserts the result reflects
    all three, in order.

162. **`test_core.py::test_empty_pipeline_is_the_identity`**
    `Pipeline()` with no filters, no selector. Asserts the payload
    passes through unchanged.

163. **`test_core.py::test_pipeline_with_a_selector_routes_to_the_chosen_branch`**
    A selector fixed to branch `"a"`, two routes. Asserts only `"a"`'s
    filters ran — `"b"`'s never executed.

164. **`test_core.py::test_pipeline_branches_compose_recursively`**
    A route's `Pipeline` itself ends in a selector. Asserts the nested
    branch's filter ran — branching composes by nesting, with no
    special-casing in `Pipeline`.

165. **`test_core.py::test_unknown_branch_name_raises_a_clear_error`**
    A selector returning a branch name absent from `routes`. Asserts
    `UnknownBranchError`, not a raw `KeyError`.

166. **`test_core.py::test_filters_can_update_meta_not_just_text`**
    Three filters each incrementing an int meta. Asserts the final
    meta reflects all three — filters aren't limited to transforming
    text.

167. **`test_core_edge_cases.py::test_payload_is_frozen`**
    Asserts `Payload` can't be mutated in place
    (`dataclasses.FrozenInstanceError`).

168. **`test_core_edge_cases.py::test_pipeline_with_only_a_selector_and_no_filters_routes_immediately`**
    A selector-only `Pipeline` (empty filters). Asserts it routes
    correctly with no filters to run first.

169. **`test_core_edge_cases.py::test_branch_pipeline_receives_the_selectors_own_payload_edits`**
    A selector that both edits the payload and routes. Asserts the
    branch pipeline sees the selector's edit, not the pre-select
    payload.

170. **`test_core_edge_cases.py::test_pipeline_is_reusable_across_independent_runs`**
    The same `Pipeline` instance run twice with different inputs.
    Asserts two independent, correct results — no leaked state.

171. **`test_core_edge_cases.py::test_unknown_branch_error_names_the_known_routes`**
    Asserts the `UnknownBranchError` message names the routes that
    *were* available, not just that the lookup failed.

172. **`test_modules.py::test_idempotency_gate_selector_routes_skip_for_an_already_processed_message`**
    A message already `mark_processed()`-ed. Asserts the selector
    routes `"skip"`.

173. **`test_modules.py::test_idempotency_gate_selector_routes_continue_for_a_new_message`**
    A never-seen message. Asserts the selector routes `"continue"`.

174. **`test_modules.py::test_timestamp_filter_sets_ts_from_the_injected_clock`**
    Asserts `meta.ts` is set from whatever clock callable was given.

175. **`test_modules.py::test_rule_evaluation_selector_routes_terminal_for_a_matched_rule`**
    A message matching a terminal rule. Asserts the branch is
    `"terminal"` and `meta.verdict` carries the matched rule's id.

176. **`test_modules.py::test_rule_evaluation_selector_routes_escalate_when_nothing_matches`**
    No matching rule, default policy escalate. Asserts the branch is
    `"escalate"`.

177. **`test_modules.py::test_apply_action_filter_calls_the_executor_and_sets_audit_fields`**
    A terminal verdict. Asserts the executor was called and
    `meta.audit_event`/`audit_detail_json` are set for the next
    module.

178. **`test_modules.py::test_record_escalation_filter_sets_the_escalation_audit_event`**
    The escalate branch's counterpart to 177 — no executor call,
    just `meta.audit_event = "escalated_pending_tier2"`.

179. **`test_modules.py::test_write_audit_entry_filter_writes_what_meta_describes`**
    Asserts the audit entry written matches whatever
    `meta.audit_event`/`audit_detail_json` say — generic across both
    branches.

180. **`test_modules.py::test_mark_processed_filter_writes_the_processed_row`**
    Asserts `has_processed()` becomes `True` after the filter runs.

181. **`test_modules_edge_cases.py::test_apply_action_filter_raises_when_verdict_is_missing`**
    `ApplyActionFilter` run standalone with no prior
    `RuleEvaluationSelector`. Asserts `MissingMetaError`, not a raw
    `AttributeError`/`None` access.

182. **`test_modules_edge_cases.py::test_write_audit_entry_filter_raises_when_ts_is_missing`**
    Same pattern for `WriteAuditEntryFilter` missing `meta.ts`.

183. **`test_modules_edge_cases.py::test_write_audit_entry_filter_raises_when_audit_event_is_missing`**
    Same pattern for `WriteAuditEntryFilter` missing `meta.audit_event`.

184. **`test_modules_edge_cases.py::test_mark_processed_filter_raises_when_verdict_is_missing`**
    Same pattern for `MarkProcessedFilter` missing `meta.verdict`.

185. **`test_modules_edge_cases.py::test_mark_processed_filter_raises_when_ts_is_missing`**
    Same pattern for `MarkProcessedFilter` missing `meta.ts`, with
    `meta.verdict` present — proves each field is checked
    independently, not just "is anything missing."

186. **`test_core.py::test_pipeline_runs_augments_via_their_augment_method`**
    A stage implementing only `.augment()` (no `.apply()`). Asserts it
    runs correctly in a `Pipeline`'s stage list — `Augment` is a
    first-class stage type, not a `Filter` in disguise.

187. **`test_core.py::test_pipeline_interleaves_filters_and_augments_in_call_order`**
    A stage list mixing `Filter`, `Augment`, `Filter`. Asserts each ran
    in call order — the two kinds compose freely in one list.

188. **`test_core.py::test_augment_can_update_meta_not_just_text`**
    Two augments each incrementing an int meta. Asserts the final meta
    reflects both — same meta-mutation contract as `Filter`.

189. **`test_core.py::test_augment_then_selector_pipeline_composes_like_a_filter_would`**
    An augment followed by a selector-routed branch. Asserts it works
    the same way a filter-then-selector `Pipeline` does — `Augment`
    needs no special-case support beyond the stage-dispatch loop.

190. **`test_core_edge_cases.py::test_a_stage_implementing_both_methods_dispatches_via_augment`**
    A stage implementing both `.apply()` and `.augment()`, each
    producing a distinguishable result. Asserts `.augment()` wins —
    documents `Pipeline.run`'s isinstance-checks-Augment-first
    precedence for this (unlikely) ambiguous case.

191. **`test_core_edge_cases.py::test_a_stage_with_neither_apply_nor_augment_fails_loudly`**
    A stage satisfying neither `Filter` nor `Augment` (a wiring
    mistake). Asserts a clear `AttributeError` naming the missing
    method, not a silent no-op.

### tests/core/llm (LLMClient adapter, §10.1)

`spork.core.llm.base` (`VerdictRequest`/`Verdict`/`LLMClient`),
`spork.core.llm.loader` (`load_llm_client()`, tested against a fixture
class the same way `tests/core/providers/test_loader.py` tests
`load_provider()`), and `spork.core.llm.clients.anthropic`
(`AnthropicLLMClient`, tested the same way
`tests/core/providers/jmap/test_client.py` tests `JmapClient`'s
settled-shape `NotImplementedError` stubs).

192. **`test_base.py::test_verdict_request_holds_the_assembled_prompt_inputs`**
    Constructs a `VerdictRequest` and reads fields back. Asserts they
    match what was passed in.

193. **`test_base.py::test_verdict_parses_a_valid_llm_response`**
    A well-formed response dict matching §10's JSON example. Asserts
    it parses into a `Verdict` with a nested `Action`.

194. **`test_base.py::test_verdict_draft_reply_defaults_to_none_when_omitted`**
    A response with no `draft_reply` key. Asserts the field defaults
    to `None` — it's optional per §10.

195. **`test_base.py::test_verdict_accepts_an_explicit_draft_reply`**
    Asserts a present `draft_reply` round-trips through validation.

196. **`test_base.py::test_verdict_rejects_unknown_fields`**
    A response with a field spork never asked for. Asserts
    `ValidationError` — `extra="forbid"`, same rule as
    `rules.schema.Condition`/`Action`.

197. **`test_base.py::test_verdict_rejects_a_missing_required_field`**
    A response missing `reasoning`. Asserts `ValidationError` rather
    than a silently-defaulted field.

198. **`test_base_edge_cases.py::test_verdict_rejects_a_suggested_action_of_escalate`**
    A response whose `suggested_action.type` is `"escalate"`. Asserts
    `ValidationError` — a verdict is already Tier 2's output, so
    escalating again is a schema-level contradiction.

199. **`test_base_edge_cases.py::test_verdict_rejects_confidence_above_one`**
    `confidence: 1.5`. Asserts `ValidationError` — confidence is a
    probability, not silently clamped.

200. **`test_base_edge_cases.py::test_verdict_rejects_confidence_below_zero`**
    `confidence: -0.1`. Asserts `ValidationError`.

201. **`test_base_edge_cases.py::test_verdict_rejects_an_urgency_outside_the_closed_set`**
    `urgency: "critical"`. Asserts `ValidationError` — `urgency` is a
    closed `Literal`, not an open string.

202. **`test_base_edge_cases.py::test_verdict_rejects_a_malformed_nested_suggested_action`**
    A `suggested_action` with an extra field. Asserts `ValidationError`
    — `Action`'s own validation applies transitively through `Verdict`.

203. **`test_loader.py::test_load_llm_client_imports_and_instantiates_by_spec`**
    A well-formed `"module:ClassName"` spec. Asserts it resolves to an
    instance of that class.

204. **`test_loader.py::test_load_llm_client_passes_through_constructor_kwargs`**
    Asserts extra kwargs reach the client's constructor unmodified.

205. **`test_loader.py::test_load_llm_client_raises_for_malformed_spec`**
    A spec with no `:` separator. Asserts `LLMClientLoadError` before
    any import is attempted.

206. **`test_loader_edge_cases.py::test_load_llm_client_raises_for_unimportable_module`**
    A spec naming a nonexistent module. Asserts `LLMClientLoadError`,
    not a raw `ImportError`.

207. **`test_loader_edge_cases.py::test_load_llm_client_raises_for_missing_class_attribute`**
    A spec naming a real module but an undefined class. Asserts
    `LLMClientLoadError`, not a raw `AttributeError`.

208. **`test_loader_edge_cases.py::test_load_llm_client_raises_when_construction_fails`**
    A client whose constructor rejects the given kwargs. Asserts
    `LLMClientLoadError`, not a raw `TypeError`.

209. **`clients/test_anthropic.py::test_get_verdict_raises_not_implemented`**
    Asserts `AnthropicLLMClient.get_verdict()` raises
    `NotImplementedError` — a live Anthropic API session isn't
    something this environment can exercise honestly.

210. **`clients/test_anthropic.py::test_constructor_accepts_configured_model_and_max_tokens`**
    Constructs with non-default `model`/`max_tokens`. Asserts
    construction itself doesn't raise — only `get_verdict()` is
    unimplemented.

### tests/core/llm (verdict validation, §10.2)

`spork.core.llm.validate.validate_verdict()` — pure logic, no
`Provider`/JMAP dependency.

211. **`test_validate.py::test_validate_verdict_returns_the_verdict_unchanged_on_success`**
    A verdict whose category and mailbox are both configured. Asserts
    it's returned unchanged — validation never coerces.

212. **`test_validate.py::test_validate_verdict_rejects_a_category_outside_the_configured_set`**
    An unconfigured category. Asserts `VerdictValidationError` naming
    the bad value.

213. **`test_validate.py::test_validate_verdict_rejects_a_mailbox_outside_the_configured_set`**
    An unconfigured `suggested_action.mailbox`. Asserts
    `VerdictValidationError` naming the bad value.

214. **`test_validate.py::test_validate_verdict_skips_the_mailbox_check_when_mailbox_is_none`**
    An `ignore` verdict (no mailbox set). Asserts it passes even
    against an empty `allowed_mailboxes`.

215. **`test_validate_edge_cases.py::test_validate_verdict_reports_the_category_error_first_when_both_are_invalid`**
    Both category and mailbox invalid. Asserts the category error is
    the one raised — documents actual precedence.

216. **`test_validate_edge_cases.py::test_validate_verdict_category_check_is_case_sensitive`**
    A configured `"Needs_Reply"` vs. a verdict's `"needs_reply"`.
    Asserts `VerdictValidationError` — no fuzzy matching.

217. **`test_validate_edge_cases.py::test_validate_verdict_does_not_itself_require_a_mailbox_for_move_or_tag`**
    A `move` verdict with no mailbox at all. Asserts it passes
    `validate_verdict()` — documents that `ActionExecutor`, not this
    function, is what rejects a mailbox-less move/tag.

### tests/core/llm (confidence-band logic, §10.3)

`spork.core.llm.confidence.confidence_band()` — pure function of
`(confidence, alert_threshold, autoact_threshold)`.

218. **`test_confidence.py::test_confidence_above_autoact_threshold_is_autoact`**
    High confidence. Asserts `"autoact"`.

219. **`test_confidence.py::test_confidence_between_thresholds_is_autoact_alert`**
    Mid-band confidence. Asserts `"autoact_alert"`.

220. **`test_confidence.py::test_confidence_below_alert_threshold_is_alert_only`**
    Low confidence. Asserts `"alert_only"`.

221. **`test_confidence.py::test_confidence_at_autoact_threshold_is_autoact`**
    Confidence exactly equal to `autoact_threshold`. Asserts
    `"autoact"` — inclusive on its own side.

222. **`test_confidence.py::test_confidence_at_alert_threshold_is_autoact_alert`**
    Confidence exactly equal to `alert_threshold`. Asserts
    `"autoact_alert"` — inclusive on its own side.

223. **`test_confidence_edge_cases.py::test_misconfigured_thresholds_raise_value_error`**
    `alert_threshold > autoact_threshold`. Asserts `ValueError` rather
    than silently picking a band.

224. **`test_confidence_edge_cases.py::test_equal_thresholds_never_produce_autoact_alert`**
    `alert_threshold == autoact_threshold` (a legitimate degenerate
    config). Asserts `"autoact_alert"` is unreachable — documented so
    it isn't mistaken for a bug.

225. **`test_confidence_edge_cases.py::test_confidence_of_exactly_zero_and_one_are_handled`**
    `confidence` at the extremes of `Verdict`'s valid range. Asserts
    both classify without error.

### tests/core/state (llm_usage tracking, §7.4, §10.4)

`StateDB.record_llm_call()`/`get_llm_usage()` — extends the existing
`StateDB`, same real-SQLite-under-tmp_path style as `test_db.py`.

226. **`test_llm_usage.py::test_get_llm_usage_is_zeroed_for_a_date_never_recorded`**
    A date with no recorded calls. Asserts `LLMUsage` with all zeros,
    not `None`.

227. **`test_llm_usage.py::test_record_llm_call_then_get_llm_usage_reflects_it`**
    One recorded call. Asserts it's reflected in the next read.

228. **`test_llm_usage.py::test_record_llm_call_accumulates_across_multiple_calls_same_day`**
    Two calls, same date. Asserts both `calls` and token counts sum.

229. **`test_llm_usage.py::test_record_llm_call_keeps_different_dates_independent`**
    Calls on two different dates. Asserts each date's usage is
    tracked independently.

230. **`test_llm_usage_edge_cases.py::test_record_llm_call_with_zero_tokens_still_increments_calls`**
    A call with `tokens_in=tokens_out=0`. Asserts `calls` still
    increments.

231. **`test_llm_usage_edge_cases.py::test_llm_usage_persists_across_reopening_the_database`**
    Usage recorded, DB closed and reopened. Asserts it's still there —
    same durability contract as `push_cursor`/`processed_messages`.

232. **`test_llm_usage_edge_cases.py::test_record_llm_call_rejects_negative_tokens_in`**
    `tokens_in=-1`. Asserts `ValueError` — found a real gap (no guard
    existed) and fixed it in the same round.

233. **`test_llm_usage_edge_cases.py::test_record_llm_call_rejects_negative_tokens_out`**
    Same guard, `tokens_out=-1`.

### tests/core/llm (budget enforcement, §10.4)

`spork.core.llm.budget.has_budget_remaining()` — pure function,
decoupled from `StateDB` the same way `confidence_band()` is decoupled
from `Verdict`.

234. **`test_budget.py::test_budget_remaining_when_calls_are_below_the_limit`**
    `calls < daily_call_budget`. Asserts `True`.

235. **`test_budget.py::test_no_budget_remaining_once_the_limit_is_reached`**
    `calls == daily_call_budget`. Asserts `False` — the limit is
    exclusive.

236. **`test_budget.py::test_no_budget_remaining_once_the_limit_is_exceeded`**
    `calls > daily_call_budget`. Asserts `False`.

237. **`test_budget.py::test_budget_remaining_on_a_never_called_day`**
    `calls=0`, any positive budget. Asserts `True`.

238. **`test_budget_edge_cases.py::test_a_zero_daily_call_budget_always_denies`**
    `daily_call_budget=0`. Asserts `False` even with zero calls made.

239. **`test_budget_edge_cases.py::test_a_negative_daily_call_budget_always_denies`**
    `daily_call_budget=-5` (nonsensical but not ambiguous). Asserts
    `False` — documented as intentionally unguarded, unlike
    `confidence.py`'s threshold-ordering check.

### tests/core/llm/clients (RecordedLLMClient, §10.5)

`spork.core.llm.clients.recorded` — the `LLMClient` equivalent of
`FileProvider`: a second, fully real adapter with no
`NotImplementedError` anywhere.

240. **`test_recorded.py::test_get_verdict_returns_the_recorded_verdict_for_a_matching_subject`**
    A request whose subject matches a recorded entry. Asserts the
    matching `Verdict` is returned.

241. **`test_recorded.py::test_get_verdict_returns_different_verdicts_for_different_subjects`**
    Two different recorded subjects. Asserts each returns its own
    distinct verdict.

242. **`test_recorded.py::test_get_verdict_raises_for_a_subject_with_no_recorded_response`**
    An unrecorded subject. Asserts `UnrecordedResponseError` naming
    what *was* recorded.

243. **`test_recorded_responses.py::test_load_recorded_responses_parses_a_valid_json_file`**
    A well-formed `responses.json`. Asserts it parses into `Verdict`s
    keyed by subject.

244. **`test_recorded_responses.py::test_load_recorded_responses_returns_empty_dict_for_empty_object`**
    A file containing `{}`. Asserts zero responses, not an error.

245. **`test_recorded_responses.py::test_load_recorded_responses_raises_for_malformed_json`**
    Broken JSON syntax. Asserts `RecordedResponsesLoadError`, not a
    raw `json.JSONDecodeError`.

246. **`test_recorded_responses.py::test_load_recorded_responses_raises_for_non_object_json`**
    A top-level JSON array instead of an object. Asserts
    `RecordedResponsesLoadError`.

247. **`test_recorded_responses.py::test_load_recorded_responses_raises_for_an_invalid_verdict_entry`**
    An entry that fails `Verdict`'s own validation. Asserts
    `RecordedResponsesLoadError` naming the subject.

248. **`test_recorded_responses.py::test_load_recorded_responses_raises_for_missing_file`**
    A nonexistent path. Asserts `RecordedResponsesLoadError`, not a
    raw `FileNotFoundError`.

249. **`test_recorded_edge_cases.py::test_load_recorded_responses_fails_entirely_when_any_entry_is_invalid`**
    One valid entry + one invalid entry. Asserts the whole load fails
    — no silent partial success dropping the bad entry.

250. **`test_recorded_edge_cases.py::test_duplicate_subject_keys_in_the_json_keep_only_the_last`**
    A JSON object with a literal duplicate key. Asserts only the last
    occurrence survives — documents `json.loads`'s own behavior, not
    anything spork does.

251. **`test_recorded_edge_cases.py::test_a_directory_path_raises_an_unwrapped_os_error`**
    A directory instead of a file. Asserts a raw `IsADirectoryError`
    leaks through — a known gap shared with
    `providers.file.messages.load_messages()`'s identical limitation,
    deliberately left unfixed to keep this loader an intentional
    mirror of its sibling.

252. **`test_recorded_edge_cases.py::test_get_verdict_can_be_called_more_than_once_for_the_same_subject`**
    The same subject requested twice. Asserts both calls return the
    same recorded `Verdict` — not a single-use queue.

### tests/core/providers (draft creation, §10.6)

Extends `JmapClient`/`JmapProvider`/`FileProvider` with
`create_draft()`/`build_draft_creator()` — same acceptance pattern as
the existing action-applier tests for each.

253. **`jmap/test_client.py::test_create_draft_raises_not_implemented`**
    `JmapClient.create_draft()`. Asserts `NotImplementedError` — a
    live Fastmail session isn't something this environment can
    exercise honestly.

254. **`jmap/test_provider.py::test_build_draft_creator_returns_something_that_can_create_a_draft`**
    `JmapProvider.build_draft_creator()`. Asserts the returned object's
    `create_draft()` raises `NotImplementedError`.

255. **`jmap/test_provider.py::test_draft_creator_delegates_to_the_client_directly`**
    `_JmapDraftCreator` used standalone. Asserts it's a real delegation
    to `JmapClient.create_draft()`, not a second placeholder.

256. **`file/test_provider.py::test_build_draft_creator_returns_something_that_can_create_a_draft`**
    `FileProvider.build_draft_creator()`. Asserts the returned object
    genuinely creates a draft (the `drafts.jsonl` file exists after).

257. **`file/test_provider.py::test_draft_creator_appends_one_jsonl_entry_per_create_draft_call`**
    Two `create_draft()` calls. Asserts two JSON-lines entries, in
    order, each recording the replied-to message and the body.

258. **`file/test_provider.py::test_drafts_log_defaults_next_to_the_actions_log`**
    `drafts_log_path` not given explicitly. Asserts a real
    `drafts.jsonl` is created next to `actions_log_path` — existing
    two-arg `FileProvider(...)` call sites keep working unchanged.

259. **`file/test_provider_edge_cases.py::test_draft_creator_appends_across_separate_build_calls`**
    Two separately-obtained draft creators, same log path. Asserts
    both append rather than truncating.

260. **`file/test_provider_edge_cases.py::test_create_draft_with_an_empty_body_is_recorded_as_is`**
    An empty draft body. Asserts it's recorded as `""`, not rejected.

261. **`file/test_provider_edge_cases.py::test_pointing_drafts_log_path_at_the_actions_log_path_interleaves_both_shapes`**
    `drafts_log_path` set equal to `actions_log_path`. Asserts both
    differently-shaped JSON entries land in the same file, in call
    order — documented, not guarded against (a dev/CI tool, not a
    production data store).

### tests/core/pipeline/tier2 (the Tier 2 pipeline, §10.7)

`spork.core.pipeline.tier2` composes every §10.1–§10.6 piece into one
runnable pipeline over a new `Tier2Meta` — reuses the generic
`Payload`/`Filter`/`Selector`/`Augment`/`Pipeline` framework and
`MissingMetaError` verbatim, never Tier 1's `MessageMeta`/modules.
Module tests construct a bare `Payload[Tier2Meta]`, same style as
`tests/core/pipeline/test_modules.py`; `test_default.py`/
`test_default_edge_cases.py` run `process_tier2_message()` end to end
against `RecordedLLMClient` — zero live Anthropic API calls anywhere
in this suite.

262. **`test_modules.py::test_timestamp_filter_sets_ts_from_the_injected_clock`**
    Asserts `meta.ts` is set from the given clock.

263. **`test_modules.py::test_budget_gate_selector_routes_budget_ok_when_under_the_limit`**
    Fewer calls today than the budget. Asserts `"budget_ok"`.

264. **`test_modules.py::test_budget_gate_selector_routes_budget_exhausted_at_the_limit`**
    Calls already at the budget for today. Asserts `"budget_exhausted"`.

265. **`test_modules.py::test_build_verdict_request_filter_cleans_the_body_and_builds_the_request`**
    An HTML body. Asserts `payload.text` is cleaned and `meta.request`
    is built from the cleaned text plus meta's caller-supplied fields.

266. **`test_modules.py::test_call_llm_augment_delegates_to_the_client_and_sets_the_verdict`**
    A stub `LLMClient`. Asserts `.augment()` calls `get_verdict(meta.request)`
    and stores the result in `meta.verdict` — the pipeline's one I/O
    stage, proven without a live API.

267. **`test_modules.py::test_record_llm_usage_filter_records_one_call`**
    Asserts one call is recorded against `meta.ts`'s date.

268. **`test_modules.py::test_validate_verdict_filter_passes_through_a_valid_verdict`**
    A verdict whose category/mailbox are both configured. Asserts it
    passes through unchanged.

269. **`test_modules.py::test_confidence_band_selector_routes_autoact_for_high_confidence`**
    Asserts branch `"autoact"` and `meta.band == "autoact"`.

270. **`test_modules.py::test_confidence_band_selector_routes_alert_only_for_low_confidence`**
    Asserts branch `"alert_only"` and `meta.band == "alert_only"`.

271. **`test_modules.py::test_apply_verdict_action_filter_calls_the_executor_and_sets_audit_fields`**
    Asserts the executor is called with `verdict.suggested_action` and
    the audit detail names the band.

272. **`test_modules.py::test_record_alert_only_filter_sets_the_audit_event`**
    Asserts `meta.audit_event` is set — no executor dependency at all.

273. **`test_modules.py::test_record_budget_exhausted_filter_sets_the_audit_event`**
    Asserts `meta.audit_event` is set.

274. **`test_modules.py::test_create_draft_if_wanted_filter_creates_a_draft_when_one_is_present`**
    A verdict with `draft_reply` set. Asserts `DraftCreator.create_draft()`
    is called with the message and the reply text.

275. **`test_modules.py::test_create_draft_if_wanted_filter_is_a_noop_when_no_draft_reply`**
    A verdict with `draft_reply=None`. Asserts no draft is created.

276. **`test_modules.py::test_write_audit_entry_filter_writes_what_meta_describes`**
    Asserts the written entry matches `meta.audit_event`/`audit_detail_json`.

277. **`test_modules.py::test_mark_processed_filter_writes_the_processed_row_with_a_verdict`**
    Asserts `has_processed()` becomes `True`.

278. **`test_modules.py::test_mark_processed_filter_writes_the_processed_row_without_a_verdict`**
    The budget-exhausted case (no verdict). Asserts `has_processed()`
    still becomes `True` — unlike Tier 1's, this filter doesn't
    require `meta.verdict`.

279. **`test_modules_edge_cases.py::test_budget_gate_selector_raises_when_ts_is_missing`**
280. **`test_modules_edge_cases.py::test_call_llm_augment_raises_when_request_is_missing`**
281. **`test_modules_edge_cases.py::test_record_llm_usage_filter_raises_when_ts_is_missing`**
282. **`test_modules_edge_cases.py::test_validate_verdict_filter_raises_when_verdict_is_missing`**
283. **`test_modules_edge_cases.py::test_confidence_band_selector_raises_when_verdict_is_missing`**
284. **`test_modules_edge_cases.py::test_apply_verdict_action_filter_raises_when_verdict_is_missing`**
285. **`test_modules_edge_cases.py::test_record_alert_only_filter_raises_when_verdict_is_missing`**
286. **`test_modules_edge_cases.py::test_create_draft_if_wanted_filter_raises_when_verdict_is_missing`**
287. **`test_modules_edge_cases.py::test_write_audit_entry_filter_raises_when_ts_is_missing`**
288. **`test_modules_edge_cases.py::test_write_audit_entry_filter_raises_when_audit_event_is_missing`**
289. **`test_modules_edge_cases.py::test_mark_processed_filter_raises_when_ts_is_missing`**
    (279–289) Each of the 10 `MissingMetaError` raise branches across
    the 13 modules, run standalone before the module it depends on —
    same pattern as Tier 1's `test_modules_edge_cases.py`.

290. **`test_default.py::test_process_tier2_message_autoacts_on_a_high_confidence_verdict`**
    A high-confidence recorded verdict. Asserts its `suggested_action`
    is applied, the message is marked processed, and the verdict is
    returned.

291. **`test_default.py::test_process_tier2_message_does_not_act_on_a_low_confidence_verdict`**
    A low-confidence recorded verdict. Asserts no action is applied,
    but the message is still marked processed and the verdict returned.

292. **`test_default.py::test_process_tier2_message_creates_a_draft_when_the_verdict_wants_one`**
    A verdict with `draft_reply` set. Asserts a real draft is created.

293. **`test_default.py::test_process_tier2_message_returns_none_when_budget_is_exhausted`**
    `daily_call_budget` already reached. Asserts `None` is returned, no
    action applied, and the `LLMClient` is never called at all (proven
    with a client that fails the test if invoked).

294. **`test_default.py::test_process_tier2_message_writes_an_audit_entry`**
    Asserts one audit entry is written for the run.

295. **`test_default_edge_cases.py::test_process_tier2_message_does_not_mark_processed_when_validation_fails`**
    A verdict naming an unconfigured category. Asserts
    `VerdictValidationError` propagates and the message is NOT marked
    processed — the same accepted M2 tradeoff (a raise aborts the run,
    retried next cycle), not a new one.

296. **`test_default_edge_cases.py::test_process_tier2_message_applies_the_action_on_the_autoact_alert_band_too`**
    A mid-confidence (`autoact_alert`) verdict. Asserts its action is
    still applied — the shared `act` `Pipeline` object genuinely
    handles both routes.

297. **`test_default_edge_cases.py::test_process_tier2_message_does_not_record_llm_usage_when_budget_is_exhausted`**
    Asserts today's call count is unchanged — `RecordLLMUsageFilter`
    is skipped entirely on the budget-exhausted branch, not just its
    result discarded.

298. **`test_default_edge_cases.py::test_default_clock_produces_a_real_parseable_timestamp`**
    Omitting `now=`. Asserts a genuine, parseable timestamp — mirrors
    Tier 1's equivalent test.

### Closing checks (verifying claims made, not new features)

Before declaring M3 done, checked whether two things repeatedly
claimed in `docs/DESIGN.md` were ever actually exercised by a test —
both were correct, neither had been verified until now.

299. **`pipeline/tier2/test_integration_with_tier1.py::test_tier2_run_overwrites_tier1s_escalation_row`**
    Escalates a message via `process_message()`, then runs
    `process_tier2_message()` on the *same* message against the same
    `StateDB`. Asserts the `processed_messages` row's `tier_reached`
    flips `"tier1"` → `"tier2"` with the real action and
    `verdict_json`, `has_processed()` never lapses to `False` in
    between, and both tiers' audit entries survive — the specific
    scenario §10.7 cites as the reason Tier 2 doesn't need its own
    idempotency gate, never exercised end to end before this test.

300. **`llm/test_loader_integration.py::test_load_llm_client_resolves_anthropic_llm_client_by_its_documented_spec`**
    `load_llm_client()` with the exact spec string §10.1 documents for
    `config.toml`. Asserts a real `AnthropicLLMClient` is returned.

301. **`llm/test_loader_integration.py::test_load_llm_client_resolves_recorded_llm_client_by_its_documented_spec`**
    Same, for §10.5's `RecordedLLMClient` spec. Asserts the loaded
    client genuinely works (`get_verdict()` returns the recorded
    response), not just that it constructs.

302. **`llm/test_loader_integration.py::test_load_llm_client_propagates_anthropic_client_get_verdict_not_implemented`**
    A loaded `AnthropicLLMClient`'s `get_verdict()` still raises
    `NotImplementedError` — the loader doesn't change a class's own
    behavior.

### tests/core/alerts (the Alerter adapter, §12.1)

`spork.core.alerts.log.LoggingAlerter` tested with pytest's built-in
`caplog` fixture; `spork.core.alerts.loader.load_alerter()` tested the
same way `providers.loader`/`llm.loader` are — a fixture stand-in
class, self-referenced via `__name__`.

303. **`test_log.py::test_notify_logs_the_title_and_body`**
    Asserts both land in the captured log text.

304. **`test_log.py::test_notify_defaults_to_normal_urgency_at_warning_level`**
    Omitting `urgency=`. Asserts the record's level is `WARNING`.

305. **`test_log.py::test_notify_logs_low_urgency_at_info_level`**
    Asserts `INFO`.

306. **`test_log.py::test_notify_logs_critical_urgency_at_error_level`**
    Asserts `ERROR`.

307. **`test_log.py::test_notify_appends_the_url_to_the_body_when_given`**
    Asserts the URL appears in the logged text — appended, not
    dropped (desktop notifications have no first-class link target).

308. **`test_log_edge_cases.py::test_notify_falls_back_to_warning_for_an_unrecognized_urgency`**
    A caller ignoring `AlertUrgency`'s `Literal` contract (reachable
    only past mypy). Asserts `WARNING`, not a raw `KeyError` that
    would lose the alert.

309. **`test_log_edge_cases.py::test_notify_with_an_empty_title_and_body_still_logs`**
    Degenerate but valid input. Asserts a record is still produced.

310. **`test_log_edge_cases.py::test_each_notify_call_produces_its_own_log_record`**
    Two `notify()` calls. Asserts two independent records, in order —
    not deduplicated or batched.

311. **`test_log_edge_cases.py::test_the_logger_name_follows_the_module_for_future_per_package_filtering`**
    Asserts the logger name is `"spork.core.alerts.log"` — enables a
    future per-package log-level config (M7).

312. **`test_loader.py::test_load_alerter_imports_and_instantiates_by_spec`**
    A well-formed `"module:ClassName"` spec. Asserts it resolves to an
    instance of that class.

313. **`test_loader.py::test_load_alerter_passes_through_constructor_kwargs`**
    Asserts extra kwargs reach the alerter's constructor unmodified.

314. **`test_loader.py::test_load_alerter_raises_for_malformed_spec`**
    A spec with no `:` separator. Asserts `AlerterLoadError` before
    any import is attempted.

315. **`test_loader_edge_cases.py::test_load_alerter_raises_for_unimportable_module`**
    A spec naming a nonexistent module. Asserts `AlerterLoadError`,
    not a raw `ImportError`.

316. **`test_loader_edge_cases.py::test_load_alerter_raises_for_missing_class_attribute`**
    A spec naming a real module but an undefined class. Asserts
    `AlerterLoadError`, not a raw `AttributeError`.

317. **`test_loader_edge_cases.py::test_load_alerter_raises_when_construction_fails`**
    An alerter whose constructor rejects the given kwargs. Asserts
    `AlerterLoadError`, not a raw `TypeError`.

### tests/core/rules (from_in condition kind — VIP-sender gap, §7.5)

Closes a real gap found while reviewing M4's alert-trigger hook points:
docs/DESIGN.md §7.5's own `vip-senders` example rule has used
`from_in = [...]` since it was first written, but `Condition` never
grew the field — `extra="forbid"` meant that example would be rejected
by `load_rules()` today. `from_in` is an exact-sender-address match,
deliberately distinct from `from_domain_in` (same-mailbox vs.
same-domain). Numbered here rather than inlined into 27–35/90–97 per
this file's own rule: numbers are stable once assigned, so later
additions to an already-numbered section go at the end of the
inventory, not renumbered into it.

318. **`test_engine.py::test_from_in_condition_matches_exact_sender_address`**
    A `from_in=["boss@example.com", "spouse@example.com"]` rule against
    a matching and a non-matching sender. Confirms exact-address
    matching, and that a message is correctly turned away too.

319. **`test_engine.py::test_from_in_condition_does_not_match_on_domain_alone`**
    A sender sharing a VIP's domain but not their exact address.
    Asserts no match — guards the from_in/from_domain_in distinction.

320. **`test_loader.py::test_load_rules_parses_from_in_condition`**
    A real `rules.toml` using `from_in`. Asserts it round-trips through
    `load_rules()` into `Condition.from_in` — the schema actually
    accepts the shape docs/DESIGN.md's example has shown all along.

321. **`test_engine_edge_cases.py::test_from_in_and_from_domain_in_together_use_and_semantics`**
    A `Condition` setting both `from_in` and `from_domain_in`, against
    a message matching one but not the other. Asserts no match — AND
    across fields, not OR, same as every other multi-field `Condition`.
    Passed against the existing implementation with no code change.

322. **`test_engine_edge_cases.py::test_from_in_with_empty_list_never_matches`**
    `from_in=[]` ahead of an `always=True` fallback. Asserts the
    fallback wins — a set-but-empty list is a real constraint ("match
    nothing"), not equivalent to the field being unset. Passed against
    the existing implementation with no code change.

### tests/core/rules (`Action.alert_immediately`, §12.2)

323. **`test_loader.py::test_load_rules_parses_alert_immediately_on_an_action`**
    A `vip-senders` rule setting `alert_immediately = true` alongside a
    plain `default-escalate` rule that doesn't. Asserts the flag
    round-trips per-rule and defaults to `False`.

### tests/core/pipeline/observer (PipelineObserver, §12.2)

The "combine logging and alerting" object — `trace()` always logs with
a correlation ID on the record; `alert()` does that and delegates to
an injected (fake) `Alerter`.

324. **`test_observer.py::test_trace_logs_the_event_with_correlation_id_on_the_record`**
    Asserts the event string lands in the log text and
    `record.correlation_id` matches what was passed.

325. **`test_observer.py::test_trace_includes_extra_fields_on_the_record`**
    `trace(..., category="newsletter", band="autoact")`. Asserts both
    keyword fields land on the record as attributes.

326. **`test_observer.py::test_alert_logs_and_delegates_to_the_alerter`**
    Asserts both a log record and exactly one `Alerter.notify()` call,
    with `url=None`/`urgency="normal"` when omitted.

327. **`test_observer.py::test_alert_passes_through_url_and_urgency`**
    Non-default `url`/`urgency` reach the `Alerter` call unchanged.

328. **`test_observer.py::test_two_correlation_ids_stay_distinguishable_in_the_log`**
    Two `trace()` calls with two different ids. Asserts each record
    keeps its own — no leakage between messages.

329. **`test_observer_edge_cases.py::test_alert_with_empty_title_and_body_still_delegates`**
    Degenerate but valid input. Asserts a record and an `Alerter` call
    are still produced, never silently swallowed.

330. **`test_observer_edge_cases.py::test_trace_field_colliding_with_a_reserved_logrecord_attribute_raises`**
    A field named `message` (a real `LogRecord` attribute) raises
    `KeyError` from stdlib `logging` — documents the constraint rather
    than hiding it; acceptable since every field name passed today is
    chosen by spork's own modules, never untrusted input.

### tests/core/pipeline (CorrelationIdFilter + alert-trigger wiring, §12.2)

`spork.core.pipeline.modules`/`tier2.modules` gain `CorrelationIdFilter`
(mirrors `TimestampFilter`'s DI) and four alerting filters, each
injected with a `PipelineObserver`.

331. **`test_modules.py::test_correlation_id_filter_sets_correlation_id_from_the_injected_generator`** (Tier 1)
    Mirrors the equivalent `TimestampFilter` test.

332. **`test_modules.py::test_record_escalation_filter_does_not_alert_for_a_plain_escalation`**
    An unmatched message escalating via `default_unmatched_action`
    (no `alert_immediately`). Asserts zero `Alerter` calls.

333. **`test_modules.py::test_record_escalation_filter_alerts_when_action_opts_in`**
    A `vip-senders`-style rule (`alert_immediately=True`). Asserts one
    alert fires, with the escalation reason in its title.

334. **`test_modules_edge_cases.py::test_record_escalation_filter_raises_when_verdict_is_missing`** (Tier 1)
    Run standalone, before `RuleEvaluationSelector`. Asserts `MissingMetaError`.

335. **`test_modules_edge_cases.py::test_record_escalation_filter_raises_when_correlation_id_is_missing_and_alerting`**
    `alert_immediately=True` but no `CorrelationIdFilter` has run.
    Asserts `MissingMetaError` — only enforced on the alerting path.

336. **`test_default.py::test_process_message_alerts_immediately_for_a_vip_sender_rule`** (Tier 1, end to end)
    A `vip-senders` rule through the real `process_message()`. Asserts
    one alert fires, with `"vip_sender"` in its title — no Tier 2
    needed.

337. **`tier2/test_modules.py::test_correlation_id_filter_sets_correlation_id_from_the_injected_generator`** (Tier 2)
    Tier 2's own module — mirrors Tier 1's.

338. **`tier2/test_modules.py::test_apply_verdict_action_filter_does_not_alert_for_plain_autoact`**
    `band="autoact"`, `urgency="medium"`. Asserts zero `Alerter` calls
    — the vanilla case stays silent.

339. **`tier2/test_modules.py::test_apply_verdict_action_filter_alerts_for_autoact_alert_band`**
    `band="autoact_alert"`, `urgency="medium"`. Asserts one alert —
    the band alone is enough to trigger it.

340. **`tier2/test_modules.py::test_apply_verdict_action_filter_alerts_for_high_urgency_even_in_plain_autoact`**
    `band="autoact"`, `urgency="high"`. Asserts one alert at
    `urgency="critical"` — the orthogonal dimension from §12's intro,
    exercised even inside the plain-autoact band.

341. **`tier2/test_modules.py::test_record_alert_only_filter_always_alerts`**
    `urgency="low"`. Asserts one alert at `urgency="low"` —
    `alert_only`'s whole purpose is "a human must decide."

342. **`tier2/test_modules.py::test_record_budget_exhausted_filter_always_alerts_at_critical_urgency`**
    Asserts one alert at `urgency="critical"` — §10's cost-control
    policy, never silently dropped.

343. **`tier2/test_modules_edge_cases.py::test_apply_verdict_action_filter_raises_when_correlation_id_is_missing_and_alerting`**
    `band="autoact_alert"` (about to alert), no `CorrelationIdFilter`.
    Asserts `MissingMetaError`.

344. **`tier2/test_modules_edge_cases.py::test_record_alert_only_filter_raises_when_correlation_id_is_missing`**
    Asserts `MissingMetaError` — this filter always alerts, so it
    always needs a correlation id.

345. **`tier2/test_modules_edge_cases.py::test_record_budget_exhausted_filter_raises_when_correlation_id_is_missing`**
    Same reasoning as 344.

346. **`tier2/test_default.py::test_process_tier2_message_alerts_for_a_low_confidence_verdict`** (Tier 2, end to end)
    A low-confidence verdict through the real `process_tier2_message()`.
    Asserts one alert fires.

### tests/core/config (spork.core.config — three-tier config.toml, §7.2)

One entry per test *function*; several are parametrized (noted inline)
— see the test-count note under M5's table above for why the numbered
range (347–374, 28 entries) undercounts the true 51 collected cases.

347. **`test_paths.py::test_resolve_user_config_path_uses_xdg_config_home_when_set`** (parametrized, 8 cases)
    `XDG_CONFIG_HOME` set to a spread of realistic paths (plain,
    spaces, unicode, deep nesting, root-level, trailing slash,
    dashes/underscores/digits). Asserts `.../spork/config.toml` for each.

348. **`test_paths.py::test_resolve_user_config_path_falls_back_to_home_dot_config_when_unset`**
    No `XDG_CONFIG_HOME`. Asserts `$HOME/.config/spork/config.toml` —
    the spec's own documented default.

349. **`test_paths.py::test_resolve_system_default_config_paths_uses_xdg_config_dirs_in_order`** (parametrized, 5 cases)
    A spread of `XDG_CONFIG_DIRS` strings (single dir, multiple,
    a dir with a space, unicode). Asserts one candidate per entry, in
    the variable's own preference order.

350. **`test_paths.py::test_resolve_system_default_config_paths_falls_back_to_etc_xdg_when_unset`**
    No `XDG_CONFIG_DIRS`. Asserts `["/etc/xdg/spork/config.toml"]`.

351. **`test_paths.py::test_resolve_enforced_config_path_is_always_etc_spork_enforced_toml`**
    `XDG_CONFIG_HOME`/`XDG_CONFIG_DIRS` both set to attacker-controlled-
    looking values. Asserts `/etc/spork/enforced.toml` regardless —
    the enforced tier's whole point is that no env var relocates it.

352. **`test_paths.py::test_resolve_socket_path_uses_xdg_runtime_dir_when_set`** (parametrized, 8 cases)
    Same path spread as 347. Asserts `.../spork/sporkd.sock` for each.

353. **`test_paths_edge_cases.py::test_resolve_user_config_path_treats_relative_or_empty_as_unset`** (parametrized, 3 cases)
    A relative path, an empty string, and `"./here"`. Asserts all three
    fall back to `$HOME/.config/...`, same as genuinely unset.

354. **`test_paths_edge_cases.py::test_resolve_system_default_config_paths_drops_relative_entries`**
    A relative entry mixed between two absolute ones in
    `XDG_CONFIG_DIRS`. Asserts it's dropped; the absolute entries
    survive in their original order.

355. **`test_paths_edge_cases.py::test_resolve_system_default_config_paths_skips_empty_segments`** (parametrized, 3 cases)
    `"/a::/b"`, `"/a:/b:"`, `":/a:/b"` — doubled/leading/trailing
    colons. Asserts the empty segments are skipped, not treated as
    `"."` or raising.

356. **`test_paths_edge_cases.py::test_resolve_system_default_config_paths_falls_back_when_entirely_relative`**
    Every `XDG_CONFIG_DIRS` entry relative. Asserts the spec's own
    `/etc/xdg` default applies, as if unset.

357. **`test_paths_edge_cases.py::test_resolve_socket_path_falls_back_and_warns_when_xdg_runtime_dir_unset`**
    No `XDG_RUNTIME_DIR`. Asserts a fallback to `/tmp/spork-<uid>/sporkd.sock`
    *and* a `UserWarning` mentioning `XDG_RUNTIME_DIR` — the spec's own
    "fall back and print a warning" guidance for this specific variable.

358. **`test_paths_edge_cases.py::test_resolve_socket_path_falls_back_for_relative_or_empty_too`** (parametrized, 2 cases)
    A relative path and an empty string. Same fallback-and-warn
    treatment as 357.

359. **`test_schema.py::test_sporkconfig_constructs_with_all_required_fields`**
    The five always-required fields (provider/llm/alerts specs,
    rules_path, db_path) alone construct a valid `SporkConfig`.

360. **`test_schema.py::test_sporkconfig_rejects_unknown_fields`**
    A typo'd top-level key. Asserts `pydantic.ValidationError`
    (`extra="forbid"`, same convention as `rules.schema.Condition`).

361. **`test_schema.py::test_sporkconfig_socket_path_defaults_to_none`**
    Omitting `socket_path`. Asserts `None` — `loader.py`'s job to fill
    it in via `resolve_socket_path()`, not the schema's.

362. **`test_schema.py::test_sporkconfig_tiering_defaults_when_omitted`**
    Omitting `[tiering]` entirely. Asserts a full, default-valued
    `TieringConfig`, not a missing-field error.

363. **`test_schema.py::test_tieringconfig_defaults_match_documented_values`**
    Asserts every `TieringConfig` default matches §7.2's example
    config.toml exactly.

364. **`test_schema.py::test_backendspec_kwargs_defaults_to_empty_dict`**
    A `BackendSpec` with no `kwargs` table. Asserts `{}`.

365. **`test_loader.py::test_load_config_reads_the_user_tier_alone`**
    Only the user tier's file exists, fully specified. Asserts it
    loads correctly with no system-default/enforced files present.

366. **`test_loader.py::test_load_config_merges_three_tiers_per_key_not_whole_file`**
    System-default sets `alert_threshold`+`daily_call_budget`+specs;
    user overrides only `alert_threshold`. Asserts both the user's
    override and the system-default's untouched values survive.

367. **`test_loader.py::test_load_config_enforced_tier_overrides_user_tier`**
    The concrete exit-criterion test: user sets `daily_call_budget=200`,
    enforced sets `50`. Asserts `50` wins.

368. **`test_loader.py::test_load_config_raises_configloaderror_for_malformed_toml`**
    Broken TOML syntax. Asserts `ConfigLoadError`, not a raw
    `tomllib.TOMLDecodeError`.

369. **`test_loader.py::test_load_config_raises_configloaderror_when_required_fields_are_missing`**
    No tier ever sets `provider`. Asserts `ConfigLoadError`, not a raw
    `pydantic.ValidationError`.

370. **`test_loader.py::test_load_config_resolves_socket_path_when_not_set_by_any_tier`**
    `socket_path` omitted everywhere. Asserts it's filled in via
    `paths.resolve_socket_path()`.

371. **`test_loader_edge_cases.py::test_load_config_raises_configloaderror_for_an_unreadable_path`**
    The user-tier path is a directory, not a file — deterministic
    regardless of the running user's privilege level (unlike
    chmod-based permission denial, meaningless when tests run as
    root). Asserts `ConfigLoadError`, not a raw `OSError`.

372. **`test_loader_edge_cases.py::test_load_config_treats_an_empty_but_present_tier_file_as_a_noop`**
    A 0-byte enforced-tier file. Asserts it contributes zero
    overrides, same as a missing file — not a parse error.

373. **`test_loader_edge_cases.py::test_load_config_deep_merges_nested_backendspec_kwargs`**
    System-default sets two `provider.kwargs` entries; user overrides
    only one. Asserts both survive — the recursive merge goes deeper
    than one level, not just `[tiering]`.

374. **`test_loader_edge_cases.py::test_load_config_system_default_uses_first_existing_match_only`**
    Three `system_default_config_paths` candidates, only the middle one
    exists. Asserts it's the one read — later real candidates are
    ignored, matching `XDG_CONFIG_DIRS`'s first-match-wins precedence.

### tests/core/state + tests/daemon (the asyncio daemon loop, §6.2.1)

375. **`state/test_db.py::test_state_db_usable_from_a_different_thread_than_it_was_created_on`**
    `StateDB` created on the test's thread, then used (via a spawned
    `threading.Thread`, joined before asserting) from another thread.
    Asserts no `sqlite3.ProgrammingError` — the exact sequential
    cross-thread pattern `asyncio.to_thread(process_message, ...)`
    relies on.

376. **`daemon/test_loop.py::test_run_daemon_applies_a_matched_rules_action`**
    A message matching a catch-all rule, run through `run_daemon()`
    against a real `FileProvider`. Asserts the action lands in
    `FileProvider`'s real JSON-lines actions log.

377. **`daemon/test_loop.py::test_run_daemon_marks_processed_messages_in_state_db`**
    Asserts both fixture messages end up `has_processed() == True` in
    a real `StateDB` after running through the real asyncio loop.

378. **`daemon/test_loop.py::test_run_daemon_fires_a_vip_alert_through_pipeline_observer`**
    A VIP-sender rule's `alert_immediately`. Asserts the alert fires
    through the real `LoggingAlerter` loaded from `config.alerts.spec`
    — not a hand-constructed `PipelineObserver`.

379. **`daemon/test_loop.py::test_run_daemon_stops_promptly_after_stop_event_is_set`**
    Asserts `run_daemon()` actually returns once `stop_event` is set,
    via a bounded `asyncio.wait_for()` that would itself fail the test
    if the loop never stopped.

380. **`daemon/test_loop_edge_cases.py::test_run_message_loop_stops_mid_batch_without_processing_the_rest`**
    A fake `ActionApplier` sets `stop_event` as a side effect of
    applying the first of two messages in one batch. Asserts the
    second message is never processed.

381. **`daemon/test_loop_edge_cases.py::test_run_message_loop_sleeps_rather_than_busy_looping_on_an_empty_source`**
    An always-empty `Source` with a short `idle_delay_seconds`, run
    for a fixed wall-clock window. Asserts a bounded `poll()` call
    count (proving `asyncio.sleep()` actually elapsed, not a spin) and
    separately asserts real wall-clock time actually passed.

382. **`daemon/test_loop_edge_cases.py::test_run_daemon_propagates_a_missing_rules_file_error`**
    A `rules_path` that doesn't exist. Asserts `RulesLoadError`
    propagates as-is — `run_daemon()` is a library function, not a CLI
    command, so it doesn't catch/report this itself.

383. **`daemon/test_main.py::test_no_usable_config_produces_a_clean_error_not_a_traceback`**
    `sporkd` run via subprocess with `XDG_CONFIG_HOME`/`XDG_CONFIG_DIRS`
    pointed at empty tmp dirs (no config anywhere). Asserts exit code 1,
    an `"Error:"` message, and no `"Traceback"` in stderr.

### tests/core/ipc + tests/daemon + tests/cli/commands (the control socket, §6.2.2)

384. **`ipc/test_protocol.py::test_ipc_request_defaults_params_to_empty_dict`**
    A command needing no arguments. Asserts `params == {}`.

385. **`ipc/test_protocol.py::test_ipc_response_defaults_data_and_error`**
    A bare success response. Asserts `data == {}` and `error is None`.

386. **`ipc/test_protocol.py::test_ipc_request_rejects_unknown_fields`**
    A typo'd field. Asserts `pydantic.ValidationError` (`extra="forbid"`).

387. **`ipc/test_protocol.py::test_encode_line_produces_one_newline_terminated_json_line`**
    Asserts the framed bytes end in exactly one `\n` and round-trip
    back through `IpcRequest.model_validate_json()`.

388. **`ipc/test_protocol.py::test_encode_line_works_for_responses_too`**
    Same round-trip, for `IpcResponse`.

389. **`ipc/test_server.py::test_ipc_server_dispatches_to_the_registered_handler`**
    A real connection, over a real Unix socket. Asserts the handler's
    return value comes back as the response's `data`.

390. **`ipc/test_server.py::test_ipc_server_returns_error_for_an_unknown_command`**
    No handler registered. Asserts a clear error response, never a hang.

391. **`ipc/test_server.py::test_ipc_server_returns_error_when_a_handler_raises`**
    A handler that raises `ValueError`. Asserts an error response, not
    a crashed connection or server.

392. **`ipc/test_server.py::test_ipc_server_removes_a_stale_socket_file_before_binding`**
    A leftover non-socket file at the target path. Asserts startup
    still succeeds.

393. **`ipc/test_server.py::test_ipc_server_socket_file_has_restrictive_permissions`**
    Asserts the bound socket file is mode `0600` (§15).

394. **`ipc/test_server.py::test_ipc_server_stops_promptly_after_stop_event_is_set`**
    Asserts `serve()` actually returns once `stop_event` is set.

395. **`ipc/test_server_edge_cases.py::test_ipc_server_returns_error_for_a_malformed_request_line`**
    Garbage bytes (not valid `IpcRequest` JSON) on the wire. Asserts a
    clear error response.

396. **`ipc/test_client.py::test_send_request_returns_the_servers_response`**
    A real round trip against a real `IpcServer`. Asserts the
    handler's data comes back.

397. **`ipc/test_client.py::test_send_request_defaults_params_to_empty_dict`**
    Calling without `params`. Asserts an empty dict was sent.

398. **`ipc/test_client.py::test_send_request_raises_ipcconnectionerror_when_nothing_is_listening`**
    No socket file at all. Asserts `IpcConnectionError` — the "daemon
    not running" signal every CLI command checks for.

399. **`ipc/test_client_edge_cases.py::test_send_request_raises_when_server_closes_without_responding`**
    A listener that accepts then closes without writing a response.
    Asserts `IpcConnectionError` either way that failure surfaces.

400. **`daemon/test_loop_ipc.py::test_run_daemon_serves_status_over_the_socket`**
    A real status request against a real running `run_daemon()`.
    Asserts `paused is False` and `started_at` is set.

401. **`daemon/test_loop_ipc.py::test_run_daemon_pause_then_status_reports_paused`**
    pause -> status -> resume -> status, over the real socket. Asserts
    each step's `paused` value.

402. **`daemon/test_loop_ipc.py::test_run_daemon_still_processes_messages_while_serving_ipc`**
    A status request during a real Tier 1 run. Asserts the message
    still gets processed — both `TaskGroup` tasks genuinely coexist.

403. **`daemon/test_loop_ipc.py::test_run_message_loop_never_polls_while_paused`**
    `daemon_state.paused = True` from the start, against a
    call-counting fake `Source`. Asserts `poll()` is never called —
    pause is a real behavioral skip, not just an unread flag.

404. **`cli/commands/test_status.py::test_status_help_works`**
    `spork status --help`. Asserts exit 0, usage text.

405. **`cli/commands/test_status.py::test_status_with_no_config_produces_a_clean_error`**
    No config anywhere. Asserts exit 1, a clear `ConfigLoadError`
    message, no traceback.

406. **`cli/commands/test_status.py::test_status_when_daemon_not_running_produces_a_clear_message`**
    A valid config, nothing listening. Asserts "not running" messaging.

407. **`cli/commands/test_status.py::test_status_reports_real_daemon_state`**
    A real `sporkd` subprocess (started, polled for its socket file),
    then a real `spork status` subprocess against it. Asserts exit 0
    and `"paused"` in the output.

408. **`cli/commands/test_pause.py::test_pause_and_resume_help_work`**
    `--help` for both commands. Asserts exit 0, usage text.

409. **`cli/commands/test_pause.py::test_pause_when_daemon_not_running_produces_a_clear_message`**
    Same "not running" convention as `spork status`.

410. **`cli/commands/test_pause.py::test_pause_then_resume_actually_toggles_daemon_state`**
    A full end-to-end round trip against a real `sporkd` subprocess,
    verified via `spork status`'s own output.

411. **`cli/commands/test_logs.py::test_logs_help_works`**
    Asserts exit 0, usage text.

412. **`cli/commands/test_logs.py::test_logs_with_no_config_produces_a_clean_error`**
    Asserts exit 1, clean error, no traceback.

413. **`cli/commands/test_logs.py::test_logs_prints_nothing_for_a_fresh_never_run_daemon`**
    A `StateDB` that's never had anything written to it. Asserts empty
    output, not an error.

414. **`cli/commands/test_logs.py::test_logs_prints_entries_oldest_first`**
    Two entries written out of display order. Asserts oldest-first.

415. **`cli/commands/test_logs.py::test_logs_filters_by_message_id`**
    `--message-id` against two entries for different messages. Asserts
    only the matching one prints.

416. **`cli/commands/test_logs.py::test_logs_filters_by_since`**
    `--since` against two entries either side of the cutoff. Asserts
    only the later one prints.

417. **`cli/commands/test_logs.py::test_logs_tail_shows_only_the_last_n_entries`**
    `--tail 2` against five entries. Asserts only the last two print,
    in order.

418. **`core/providers/jmap/test_client.py::test_get_thread_context_raises_not_implemented`**
    `JmapClient.get_thread_context()` is a settled-shape stub, same
    pattern as `connect()`/`fetch_new_messages()`/etc.

419. **`core/providers/jmap/test_client.py::test_list_mailboxes_raises_not_implemented`**
    Same, for `JmapClient.list_mailboxes()`.

420. **`core/providers/jmap/test_provider.py::test_build_thread_history_reader_returns_something_that_can_get_context`**
    `JmapProvider.build_thread_history_reader()` returns an object
    satisfying `ThreadHistoryReader`; calling it raises
    `NotImplementedError`, propagated from `JmapClient`.

421. **`core/providers/jmap/test_provider.py::test_thread_history_reader_delegates_to_the_client_directly`**
    `_JmapThreadHistoryReader` is a real delegation to
    `JmapClient.get_thread_context()`, not a second placeholder.

422. **`core/providers/jmap/test_provider.py::test_build_mailbox_lister_returns_something_that_can_list_mailboxes`**
    Same shape as 420, for `build_mailbox_lister()`.

423. **`core/providers/jmap/test_provider.py::test_mailbox_lister_delegates_to_the_client_directly`**
    Same shape as 421, for `_JmapMailboxLister`.

424. **`core/providers/file/test_provider.py::test_build_thread_history_reader_returns_no_history_for_a_singleton_thread`**
    A message alone in its thread: `prior_subject is None`,
    `user_has_replied is False` — real absence, not a placeholder.

425. **`core/providers/file/test_provider.py::test_thread_history_reader_finds_prior_subject_and_a_reply_already_sent`**
    Two messages sharing a thread, one with `"Sent"` in `mailbox_ids`.
    Asserts the later message's context resolves the earlier one's
    subject and `user_has_replied is True`.

426. **`core/providers/file/test_provider.py::test_build_mailbox_lister_returns_the_explicit_available_mailboxes_when_given`**
    An explicit `available_mailboxes=` constructor argument wins over
    anything derived from the messages file.

427. **`core/providers/file/test_provider.py::test_mailbox_lister_derives_the_sorted_union_of_mailbox_ids_when_not_given`**
    With no `available_mailboxes=`, the list is the sorted union of
    every message's `mailbox_ids` in the file.

428. **`daemon/test_loop.py::test_run_daemon_runs_an_escalated_message_through_tier2`**
    End to end against `FileProvider` + `RecordedLLMClient`: the
    VIP-sender rule's escalation lands `tier_reached="tier2"` with the
    recorded verdict's action, not stuck at Tier 1's placeholder
    `"escalate"` row.

429. **`core/providers/file/test_provider_edge_cases.py::test_mailbox_lister_returns_empty_for_an_empty_messages_file`**
    No `available_mailboxes=`, no messages to derive from — `[]`, not
    an error.

430. **`core/providers/file/test_provider_edge_cases.py::test_mailbox_lister_respects_an_explicit_empty_list`**
    `available_mailboxes=[]` is respected as a deliberate empty answer
    (`is not None`, not truthiness) rather than falling back to
    derivation from a file that has real mailbox_ids in it.

431. **`core/providers/file/test_provider_edge_cases.py::test_thread_history_reader_ignores_messages_in_other_threads`**
    A same-subject message in an unrelated thread doesn't leak in as
    "prior" history.

432. **`core/providers/file/test_provider_edge_cases.py::test_thread_history_reader_raises_a_clean_error_for_a_missing_messages_file`**
    Same `MessagesLoadError` `build_source()` already raises for a
    missing file.

433. **`daemon/test_loop_edge_cases.py::test_parse_to_addresses_splits_and_strips_a_comma_separated_to_header`**
    `_parse_to_addresses()` unit test: comma-split, whitespace-stripped.

434. **`daemon/test_loop_edge_cases.py::test_parse_to_addresses_returns_empty_tuple_when_no_to_header`**
    No `To:` header at all — `()`, not a `KeyError` or a fabricated
    address.

435. **`daemon/test_loop_edge_cases.py::test_run_daemon_propagates_an_unrecorded_tier2_response_error`**
    An escalated message with no recorded Tier 2 response:
    `UnrecordedResponseError` propagates through `run_daemon()`'s
    `asyncio.TaskGroup()` (as an `ExceptionGroup`) rather than being
    swallowed or silently marking the message processed.

436. **`core/rules/test_writer.py::test_dump_rules_round_trips_a_single_simple_rule`**
    `dump_rules([rule])`, reparsed via `load_rules()`, reproduces the
    original `Rule` exactly.

437. **`core/rules/test_writer.py::test_dump_rules_round_trips_multiple_rules_preserving_order`**
    Two rules (one disabled, one with `alert_immediately`) round-trip
    in file order.

438. **`core/rules/test_writer.py::test_dump_rules_of_an_empty_list_produces_a_valid_empty_rules_file`**
    `dump_rules([])` parses back to `[]`, not an error.

439. **`core/rules/test_writer.py::test_dump_rules_escapes_double_quotes_in_string_fields`**
    A description/reason containing a literal `"` still round-trips —
    valid TOML, not corrupted output.

440. **`core/rules/test_writer_edge_cases.py::test_toml_value_raises_type_error_for_an_unsupported_python_type`**
    `_toml_value()` on a `float` (outside the closed bool/str/list[str]
    set) raises `TypeError` rather than emitting something invalid.

441. **`daemon/test_loop_ipc.py::test_run_daemon_reload_with_a_valid_rewritten_rules_file_returns_ok`**
    A `rules.toml` rewritten after `sporkd` started: the `reload`
    command re-reads it and reports `ok=True`.

442. **`daemon/test_loop_ipc.py::test_run_daemon_reload_with_invalid_rules_returns_ok_false_and_keeps_running`**
    A hand-edit that breaks `rules.toml`: `reload` reports `ok=False`
    with a real error message, but a subsequent `status` request over
    the same socket still succeeds — the daemon itself never crashes.

443. **`daemon/test_loop_ipc.py::test_run_message_loop_picks_up_a_reloaded_rules_list_on_the_next_poll_iteration`**
    A `_MutatingSource` whose second `poll()` call mutates
    `rules_state.rules` as a side effect: the first batch's message is
    tagged Inbox (old rule), the second is moved to Archive (new rule)
    — `rules_state.rules` is read fresh per poll iteration, not
    captured once at loop start.

444. **`cli/commands/test_rules_list_edit_enable_disable.py::test_rules_list_prints_id_status_and_action_per_rule`**
    Two rules (one enabled, one disabled): both ids and both
    `enabled`/`disabled` labels appear in the output.

445. **`cli/commands/test_rules_list_edit_enable_disable.py::test_rules_list_with_no_rules_says_so`**
    An empty `rules.toml`: "no rules" printed, exit 0, not an error.

446. **`cli/commands/test_rules_list_edit_enable_disable.py::test_rules_list_with_no_config_produces_a_clean_error`**
    No `config.toml` anywhere: exit 1, clean `Error:`, no traceback.

447. **`cli/commands/test_rules_list_edit_enable_disable.py::test_rules_edit_with_no_daemon_running_still_saves_and_says_so`**
    A no-op `$EDITOR`: the still-valid file re-validates fine, and with
    no `sporkd` reachable the command says "not running" rather than
    erroring.

448. **`cli/commands/test_rules_list_edit_enable_disable.py::test_rules_edit_rejects_an_invalid_save`**
    `$EDITOR` that corrupts the file: `spork rules edit` reports a
    clean error and never pushes a reload.

449. **`cli/commands/test_rules_list_edit_enable_disable.py::test_rules_enable_flips_a_disabled_rule_and_rewrites_the_file`**
    `spork rules enable newsletters` then `spork rules list`: the rule
    now shows `enabled`.

450. **`cli/commands/test_rules_list_edit_enable_disable.py::test_rules_disable_flips_an_enabled_rule`**
    Same, the other direction, for `disable`.

451. **`cli/commands/test_rules_list_edit_enable_disable.py::test_rules_enable_with_an_unknown_id_reports_a_clean_error`**
    `spork rules enable no-such-rule`: exit 1, error names the unknown
    id, no traceback.

452. **`cli/commands/test_rules_list_edit_enable_disable_edge_cases.py::test_rules_enable_reports_success_against_a_real_running_sporkd`**
    End to end: a real `sporkd` subprocess, `spork rules enable`
    against it — "reloaded" appears in the output, the `_push_reload()`
    success branch its sibling acceptance tests never reach.

453. **`cli/commands/test_rules_list_edit_enable_disable_edge_cases.py::test_push_reload_reports_a_warning_when_sporkd_rejects_the_reload`**
    A bare `IpcServer` whose `reload` handler raises: `_push_reload()`
    prints a warning naming the real error, not a silent success.

454. **`cli/commands/test_rules_list_edit_enable_disable_edge_cases.py::test_push_reload_with_no_socket_path_falls_back_to_resolve_socket_path`**
    `_push_reload(None)` resolves a socket path itself (same defensive
    pattern `run_daemon()` uses) rather than crashing on `None`.

455. **`core/config/test_enforced_override_paths.py::test_enforced_override_paths_with_no_enforced_file_is_empty`**
    No `enforced.toml` at all: an empty set, not an error.

456. **`core/config/test_enforced_override_paths.py::test_enforced_override_paths_includes_flat_top_level_keys`**
    A flat key (`rules_path`) at the enforced tier's top level appears
    in the result unqualified.

457. **`core/config/test_enforced_override_paths.py::test_enforced_override_paths_flattens_nested_tables_with_dotted_names`**
    `[tiering] daily_call_budget = 200` becomes `"tiering.daily_call_budget"`.

458. **`core/config/test_enforced_override_paths.py::test_enforced_override_paths_flattens_doubly_nested_kwargs_tables`**
    `[provider.kwargs] host = "..."` becomes `"provider.kwargs.host"`.

459. **`core/config/test_enforced_override_paths.py::test_enforced_override_paths_raises_configloaderror_for_malformed_toml`**
    Invalid TOML in the enforced file: `ConfigLoadError`, same as
    `load_config()` itself.

460. **`cli/commands/test_config.py::test_config_show_prints_effective_values`**
    A real merged config: `provider.spec` and a non-secret `kwargs`
    value both appear in the output.

461. **`cli/commands/test_config.py::test_config_show_redacts_a_token_like_kwarg`**
    `provider.kwargs.api_token`'s real value never appears in the
    output; the key itself does.

462. **`cli/commands/test_config.py::test_config_show_with_no_config_produces_a_clean_error`**
    No `config.toml` anywhere: exit 1, clean `Error:`, no traceback.

463. **`cli/commands/test_config.py::test_config_edit_with_a_noop_editor_saves_and_says_restart`**
    A no-op `$EDITOR`: exit 0, "restart" appears in the output — never
    a reload push.

464. **`cli/commands/test_config.py::test_config_edit_rejects_an_invalid_save`**
    `$EDITOR` that corrupts the user tier's file: exit 1, clean
    `Error:`, no traceback.

465. **`cli/commands/test_config.py::test_config_group_appears_in_top_level_help`**
    `spork --help` lists the `config` subcommand group.

466. **`cli/commands/test_config.py::test_format_show_lines_flags_a_path_present_in_the_enforced_set`**
    `_format_show_lines()` directly: a path in the given enforced set
    gets exactly one `(enforced)`-suffixed line.

467. **`cli/commands/test_config.py::test_format_show_lines_does_not_flag_paths_outside_the_enforced_set`**
    An empty enforced set: no line is ever flagged.

468. **`cli/commands/test_config.py::test_format_show_lines_redacts_provider_kwargs_api_token`**
    `_format_show_lines()` directly: `provider.kwargs.api_token`'s
    value is redacted regardless of the enforced set.

469. **`cli/commands/test_config.py::test_looks_like_secret_matches_common_credential_key_names`**
    `_looks_like_secret()` on `api_token`/`API_KEY`/`client_secret`/
    `password` (all `True`) vs. `host`/an ordinary tiering-style key
    (both `False`).

470. **`core/config/test_enforced_override_paths_edge_cases.py::test_enforced_override_paths_treats_a_list_value_as_one_leaf_not_recursed_into`**
    A TOML array (`allowed_categories`) is one leaf path, not something
    recursed into just because it's a compound type.

471. **`core/config/test_enforced_override_paths_edge_cases.py::test_enforced_override_paths_combines_flat_and_nested_keys_in_one_file`**
    A flat key and a nested table in the same file both appear
    correctly in the result.

472. **`core/config/test_enforced_override_paths_edge_cases.py::test_enforced_override_paths_of_an_empty_file_is_empty`**
    An empty (zero-byte) enforced file: an empty set.

473. **`cli/commands/test_config_edge_cases.py::test_config_show_help_works`**
    Asserts exit 0, usage text.

474. **`cli/commands/test_config_edge_cases.py::test_config_edit_help_works`**
    Asserts exit 0, usage text.

475. **`cli/commands/test_config_edge_cases.py::test_config_edit_with_no_config_at_all_never_invokes_the_editor`**
    No config in any tier: the precondition check fails (exit 1) before
    `$EDITOR` ever runs — proven by a marker file it would have created
    never appearing.

476. **`cli/commands/test_config_edge_cases.py::test_format_show_lines_handles_a_none_socket_path_without_crashing`**
    `socket_path=None` (before `load_config()` would normally resolve
    it) prints `"socket_path = None"` rather than raising.

477. **`cli/commands/test_config_edge_cases.py::test_format_show_lines_prints_no_kwargs_lines_when_kwargs_is_empty`**
    An empty `kwargs` dict: no `.kwargs.` lines for that section.

478. **`cli/commands/test_config_edge_cases.py::test_format_show_lines_redacts_across_every_backend_section_independently`**
    `llm.kwargs.api_key` is redacted too, not just `provider.kwargs.*`
    — the heuristic applies per-entry, not per-section.
