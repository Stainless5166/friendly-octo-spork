# Test Suite Inventory & Milestone Coverage

**Status:** snapshot as of the deployment-hardening work following M6,
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
were never added to it. **M5 is 9/10.** Updated once more, and last,
for `spork reclassify <id>`: standalone like `spork logs` (no daemon
required — safe under SQLite's already-on WAL mode plus
`sqlite3.connect()`'s unmodified 5-second default busy timeout, a
bounded retry rather than a correctness risk on the rare write
collision with a running daemon). `Provider` gained a sixth
capability, `build_message_lookup()` (real against `FileProvider`,
settled-shape `NotImplementedError` against `JmapProvider`);
`process_message()`/`build_default_pipeline()` gained
`force: bool = False`, omitting `IdempotencyGateSelector` from the
composed pipeline entirely rather than consulting and overriding it.
`spork.core.pipeline.tier2.escalate.{escalate_message,
parse_to_addresses}` were extracted out of what was
`spork.daemon.loop`'s private helpers — one real implementation, two
callers (the daemon loop, and `spork reclassify`), not a daemon-only
helper duplicated for the CLI. **M5 is 10/10 — the milestone is
complete.** Updated once more for a docs-normalization pass across the
whole document set (not tied to a single checklist item): found and
fixed two real bugs it surfaced along the way — `spork.daemon.main`
never caught `LLMClientLoadError` even though `run_daemon()` has
constructed an `LLMClient` at startup since Tier 2 was wired in, and
`spork reclassify` had no exception handling at all around
`load_provider()`/`load_rules()`/`classify_registry.get()`/
`load_alerter()`/`load_llm_client()` — both would have printed a raw
traceback for exactly the kind of misconfiguration this CLI otherwise
always catches cleanly. Also corrected several stale "blocked on the
M5 daemon loop, which doesn't exist" claims (daemon-health alerts,
cross-tier correlation-ID stitching, `spork doctor`'s secrets/config
checks) now that it does. Updated once more for M4's daemon-health
item's first half: a daemon-level daily-budget-exhausted alert
(docs/DESIGN.md §12.3) — a one-shot-per-day critical alert distinct
from `RecordBudgetExhaustedFilter`'s existing per-message alert,
self-resetting across date rollover by a date-equality guard rather
than a boolean flag. **M4 is now 2.5/3** (JMAP push disconnected still
genuinely blocked on a live EventSource connection; crash-loop
detection re-scoped to M6/systemd, not this loop's job — see
docs/ROADMAP.md). Updated once more for M6, all 7 items in one pass:
`spork.core.systemd` (`notify.py`/`unit.py`/`template.py`/`install.py`,
all dependency-free, hand-rolled against the stdlib the same way
`llm/clean.py`'s `HTMLParser` was), the tracked `systemd/sporkd@.service`
unit file, `spork install-service`, `run_daemon()` signaling readiness
via `sd_notify`, `spork doctor` rebuilt from one JMAP-only check into
seven independent checks (secrets/config/provider/rules/local-classifier/
JMAP/systemd-unit, each its own `[ok]`/`[FAIL]` line), and a `PKGBUILD`.
One real gap surfaced and fixed along the way: SecretSpec 0.18.0's
Python SDK resolves the *provider* from a separate, genuinely global
`~/.config/secretspec/config.toml`, not the manifest's own `[providers]`
table `docs/DESIGN.md` §7.3 previously assumed sufficient — confirmed
empirically, `resolve_secretspec_path()` and §7.3's prose both updated.
**M6 is 8/8 — the milestone is complete** in the same sense every prior
one is: everything buildable and testable without a live
account/Arch-tooling-having-machine is real, 753 tests all green.
Updated once more for M7's five buildable items: structured
application logging (`spork.core.logging_setup`), per-message pipeline
tracing (`spork.core.pipeline.tracing`), audit trail completeness
(control-plane `audit_log` entries), a security review pass against
§15 (two real gaps found and fixed: a missing README privacy
disclosure, and `Secrets.__repr__` leaking resolved values), and a
coverage pass confirming `spork.core.rules`/`spork.core.actions.executor`
were already fully covered by prior milestones. **M7 is now 5/9** — the
remaining four (confidence tuning, rate-limit verification, crash-loop
verification, tagging v1.0.0) all share the one live-account/live-week
blocker the milestone's own exit criteria state explicitly, same
"not yet met" pattern as M1's. 653 tests, all green.
Updated once more for M3's live-client follow-up: the direct Anthropic
stub is replaced by an in-process `LiteLLMClient` with forced
`deliver_verdict` tool calling, an SDK-independent exact prompt
builder, real per-call token usage, and an append-only private corpus
recorder. LiteLLM is an optional runtime extra; tests inject the
upstream completion callable and make no network calls. The changed
LLM and Tier 2 modules have 100% line coverage. **M3 is now 8/8 and
the full suite is 670 tests, all green.** Updated once more for runtime
backend composition: `BackendSpec.secret_kwargs` now maps constructor
arguments to SecretSpec names, one resolved `Secrets` object feeds the
provider/LLM/alerter builders used by daemon, doctor, and reclassify,
and optional `[llm_recording]` configuration wraps the chosen client.
The runtime module and changed config/daemon paths have 100% line
coverage. **M5 is now 11/11 and the full suite is 684 tests, all green.**
Updated once more for cursor-safe daemon acknowledgement:
`MessageBatch`/`CheckpointedSource` provide an optional candidate state,
and the daemon persists it only after a complete batch passes. Empty
batches advance; processing failures, shutdown, and restart replay
preserve the prior state. **The full suite is 713 tests, all green.**
Updated once more for JMAP EventSource: the trigger now filters account
and mail state events, retries after transient stream failures using the
configured backoff, and composes with a checkpoint-preserving polling
fallback. **The full suite is 726 tests, all green.**
Updated once more for the first live JMAP leaf: `JmapClient.connect()`
and `fetch_new_messages()` now authenticate through optional `jmapc`,
baseline current Email state, page `Email/changes`, normalize Inbox
messages, and return a candidate checkpoint under one `JmapError`
boundary. The production path was manually verified against Fastmail
without fetching historical message bodies; CI remains network-free.
The changed JMAP client has 100% line coverage. That increment brought
the suite to 704 tests. **The full suite is now 714 tests, all green.**
Updated once more for M7a: Hypothesis property-based tests plus
mutation testing (`mutmut`) for the four decision-critical, already
100%-covered modules (`rules.engine`, `actions.executor`,
`dispatch.combine`, `pipeline.default`) — docs/DESIGN.md §16.1/§16.2,
`mutation/README.md`'s recorded baseline (174 mutants, 171 killed, 3
confirmed equivalent). Several real gaps mutation testing surfaced
were closed with targeted tests, not implementation changes (a
classifier/dispatch call receiving the wrong argument, two silently-
dropped injection points, an unverified UTC clock, an unexercised
default parameter, and one docstring-documented contract with no
deterministic test). **The full suite is now 785 tests, all green.**
Updated once more for M1c's fault-injection harness
(`tests/support/jmap_mitm.py`): a mitmproxy instance driving the real,
unmodified production `client_factory` (real `jmapc.Client`) through a
local proxy, so `JmapClient`/`JmapPushTrigger` get exercised against
genuine wire faults (truncated body, synthetic 429, EventSource death,
added latency) instead of only injected fake exceptions. Building it
surfaced a real finding about the *existing* production path, not a
harness bug: jmapc's SSE transport (`sseclient`) swallows a clean
end-of-stream and silently reconnects on a fixed 3s timer internally —
`JmapPushTrigger`'s own `reconnect_backoff` schedule only actually
engages once that internal reconnect itself fails, not on the first
disconnect. No code change yet; recorded as-is since M1c's scope was
the harness, not a push.py behavior change. This section's per-test
counts elsewhere in the file were not otherwise reconciled to the
suite's current total in this pass. Combined with M7a and M8's own
work below, and merged with M7a's own fuzz/mutation-testing work,
the full suite reached 815 tests, all green. Updated once more for
M7's poison-message resiliency item:
`spork.core.pipeline.tier2.escalate.escalate_message_or_quarantine()`
wraps `escalate_message()`, catching a narrow, explicit tuple
(`QUARANTINABLE_ERRORS`) of known bad-model-output/action-execution
failures rather than a bare `except Exception`, quarantining the
message (marked processed, audited, a `critical` alert fired) instead
of letting a single malformed Tier 2 verdict crash
`_run_message_loop()`/`spork reclassify`/`spork backfill` and leave
the message stuck retrying forever. Wired into all three real callers.
**M7 is now 6/10.** Updated once more for an M3 follow-up: the model
was never actually sent this deployment's configured category set
(`TieringConfig.allowed_categories` only ever reached
`ValidateVerdictFilter`'s post-hoc check, never the prompt) — fixed via
`VerdictRequest.available_categories`/`BuildVerdictRequestFilter`;
`Verdict` also gained a freeform `metadata: dict[str, str]` field for
extracted data outside any closed/validated set. Updated once more for
item 3, a new M9: `spork.core.context` — `ContextProvider` Protocol,
dynamic loader, `NullContextProvider` (the real default) and
`MarkdownVaultContextProvider` (a settled-shape stub, blocked on an
undecided retrieval-algorithm choice rather than a live call), wired
into the Tier 2 pipeline via a new `FetchContextAugment` and
`VerdictRequest.context_snippets`, `SporkConfig.context` +
`runtime.build_context_provider()`, threaded through all three real
Tier 2 callers. Updated once more for item 4:
`spork.core.classify.keyword.KeywordClassifier`, the dependency-free
default local classifier §9.1 always documented but never shipped —
self-registers as `"keyword_heuristic"` at import time, fixing
`tiering.local_classifier`'s previously complete non-functionality in
every real deployment. **The full suite is now 870 tests, all green**
— the running per-paragraph totals above this point were not
individually reconciled to that figure; treat this line as the
current authority. Updated once more for M9's `EntityContextProvider`
(prototype): a second real `context/clients` backend, structured
rather than free-text — domains, companies, services, and people
parsed from a JSON fixture, `Service.provided_by` aggregated across
every company that lists a given service, `get_context()` turning a
recognized `from_domain`/`from_address` into `ContextSnippet`s. Unlike
`MarkdownVaultContextProvider`, this has no undecided-retrieval-
algorithm blocker, so it ships complete, backed by Gherkin
(`docs/acceptance/m9_entity_context.feature`) and 100%-covered pytest.
**M9 is now 3/4; the full suite is 892 tests, all green.** Updated
once more for M10 (originally numbered M9, renumbered when the real M9
above landed first): receipt tagging + combined-PDF archiving,
deterministic-first with a learned Tier 2 fallback
(`spork.core.receipts.*`, docs/DESIGN.md §9.5) — `build_receipt_pdf()`/
`save_pdf()`, `StateDB`'s new `known_receipt_senders` table +
`registry.normalize_sender_domain()`, the deterministic
`extract_receipt()` path (an `EntityContextProvider`-shaped
`domain_lookup` collaborator checked ahead of the learned cache),
`ReceiptExtractionClient`/`RecordedReceiptExtractionClient`, two new
`Provider` capabilities (`build_attachment_fetcher()`/
`build_keyword_applier()`), a fourth `rules.schema.Action` terminal
type (`archive_receipt`), `SporkConfig.receipt_archive`, and
`ArchiveReceiptAugment` wiring it all into `build_default_pipeline()`/
`process_message()` via one new optional parameter. One real
cross-cutting gap found and fixed along the way: `archive_receipt` had
to be excluded from `Verdict.suggested_action`'s legal values and
`verdict_tool_schema()`'s tool enum too, same reasoning `escalate`
already was. Backed by 22 Gherkin scenarios across 5 feature files
(`docs/acceptance/m10_receipt_archiving.feature` — the full pipeline —
plus `m10a`/`m10b`/`m10c`/`m10d` for the independently-reusable
sub-modules), all fully bound and passing, no live account or network
anywhere. Updated once more to close M10's own stated runtime-wiring
gap: `spork.core.receipts.loader.load_receipt_extraction_client()` +
`spork.core.runtime.build_receipt_archive_components()` (the real
`EntityContextProvider`-as-`domain_lookup` synergy, proven end to end
this time, not just designed) + `run_daemon()`/`_run_message_loop()`
actually building and passing `ReceiptArchiveComponents` through to
`process_message()`, with a new `ArchiveReceiptAugment.dry_run` +
`_ObserveKeywordApplier` pair making `--observe` genuinely suppress
receipt archiving's real side effects too. A real circular import this
surfaced (`spork.core.runtime` -> `spork.core.receipts.pipeline` ->
`spork.core.pipeline.core`, looping back through
`spork.core.pipeline.default`'s own import of the same module) was
found and fixed by making that import function-local. **M10 is now
fully wired end to end; the full suite is 975 tests, 971 green, 1
skipped.** The remaining 3 are pre-existing, unrelated
`test_mitm_fault_injection.py` failures — a sandbox/proxy limitation
confirmed present on `main` before this work started, not a
regression this milestone introduced.
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
| `jmap.client` session bootstrap (`jmapc`) | ✅ | ✅ — tests 49–50, 640–651; 100% line coverage plus a live Fastmail session/baseline check |
| Mailbox role resolution + caching | ✅ | ✅ — tests 20–26 (7 tests) |
| `Email/changes`+`Email/get` batched fetch | ✅ client leaf + cursor-safe daemon acknowledgement | ✅ — tests 50, 640–651, 656–660 |
| EventSource push listener + backoff | ✅ implementation; live acceptance open | ✅ — tests 51–52, 665–673; backoff math tests 16–19 |
| Poll-based fallback | ✅ (real, network-free) | ✅ — tests 53–61 (9 tests) |
| State DB (`push_cursor`, `processed_messages`) | ✅ | ✅ — tests 62–71 (10 tests) |
| Cursor-safe daemon acknowledgement | ✅ | ✅ — tests 652–660; candidate state is written only after a complete batch succeeds |
| `spork doctor` | ✅ configured checkpoint-capable providers connect; other providers report not applicable | ✅ — tests 147–149, 684–694 |

Session bootstrap, read-only fetch, mailbox resolution, poll fallback,
state persistence, and the configured-provider connectivity check are real
and tested. The push listener's backoff scheduling is also real and tested;
live push/reconnect evidence remains a manual acceptance item.

### M1a — Source / dispatch pipeline

| Checklist item | Implemented | Tested |
|---|---|---|
| `Trigger`/`ContentFetcher`/`Source` protocols | ✅ | ✅ — exercised via every concrete implementation below (protocols themselves aren't directly testable, only structurally) |
| `TriggeredSource` | ✅ | ✅ — tests 43, 44, 45 |
| `ImmediateTrigger` + `SequenceContentFetcher` | ✅ | ✅ — tests 37–42 |
| `Dispatcher` | ✅ | ✅ — tests 12, 13, 14, 15 |
| `Combiner` (`Primary`, `HighestConfidence`) | ✅ | ✅ — tests 5, 6, 8, 9, 10, 11 |
| `DispatchingClassifier` | ✅ | ✅ — test 7 |
| `KeywordClassifier` (default backend, item 4) | ✅ | ✅ — tests 812–819 (100% line coverage) |
| Exit criteria (replay → rule engine; ensemble → rule engine) | ✅ | ✅ — tests 36 and 7 directly demonstrate each half |

**7 of 7 items done, all tested, exit criteria directly demonstrated by
name.**

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

### M1c — Test harness & corpus tooling

| Checklist item | Implemented | Tested |
|---|---|---|
| `tests/support/jmap_mitm.py` fault-injection harness | ✅ | ✅ — tests 731–736 (6 tests) |
| `tests/fixtures/jmap/flows/` recorded flows | ✅ captured, gitignored, token-redacted; wired into the harness as a replay source via mitmproxy's own ServerPlayback addon | ✅ — test 761 (skips, not fails, when the gitignored flow file is absent; verified both paths locally) |
| Automatable push/fallback acceptance coverage | ✅ (new feature, not a bind of `m1.py`'s live steps) | ✅ — `docs/acceptance/m1_jmap_fault_injection.feature` + `steps/m1_fault_injection.py`, passing in the safe-default `uv run behave` |
| Initial `tests/fixtures/corpus/live.jsonl` seed | ✅ 13 entries, 13 distinct categories | — (not a pytest-covered artifact) |

**4 of 4 items done.** The harness itself is real and network-free (an
in-process mitmproxy instance answers every request locally; nothing
is ever forwarded to a real upstream host), and it drives the actual
production `client_factory`/`jmapc.Client`, not a fake — the first time
any test in this repo has exercised `JmapClient`/`JmapPushTrigger`
against genuine transport failures rather than injected exceptions.
The Gherkin coverage exercises the real `JmapProvider.
build_checkpointed_source()` composition (push primary, poll
secondary, one shared cursor) rather than the lower-level client/push
tests alone — a disconnected push cycle falls back to polling, and a
recovered push cycle is served with zero wasted fallback attempts, both
asserted via the harness's own EventSource connection counter, not
just cursor values. Recorded flows now exist
(`tests/fixtures/jmap/flows/`) including a genuine EventSource push
event triggered by a real test email — replaying them from
`jmap_mitm.py` instead of hand-built canned responses is still open.
The LLM corpus grew to 13 entries across 13 distinct categories (M8's
`query_messages()` used for the second batch's fetch). Larger,
backfill-driven volume remains M8's job, not this milestone's.

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

### M3 — LLM escalation (Tier 2) — 8/8

| Checklist item | Implemented | Tested |
|---|---|---|
| Body cleaning (HTML strip, quote-chain collapse, truncation) | ✅ | ✅ — tests 150–160 (11 tests), 100% line coverage |
| LLM client wrapper + verdict schema | ✅ | ✅ — tests 192–208, 300–301, 611–620, 100% line coverage |
| Live LiteLLM tool-calling adapter + acceptance corpus recorder | ✅ | ✅ — tests 611–625, 100% line coverage on changed LLM/Tier 2 modules |
| Verdict validation against configured mailbox/category set | ✅ | ✅ — tests 211–217 (7 tests), 100% line coverage |
| Confidence-band logic | ✅ | ✅ — tests 218–225 (8 tests), 100% line coverage |
| `daily_call_budget` + `llm_usage` tracking | ✅ | ✅ — tests 226–239 (14 tests), 100% line coverage |
| Recorded-response fixtures for CI | ✅ | ✅ — tests 240–252 (13 tests), 100% line coverage |
| Draft creation path | ✅ | ✅ — tests 253–261 (9 tests), 100% line coverage |
| Category taxonomy sent to the model + `Verdict.metadata` (follow-up) | ✅ | ✅ — tests 780–786, 100% line coverage on every touched module |

`spork.core.llm.clean.clean_body()` is pure string transformation with
no dependency on `NormalizedMessage`, JMAP, or the Claude API — HTML
stripped via a hand-rolled `HTMLParser` subclass (no new dependency),
quoted-reply chains collapsed at the earliest of several marker
patterns, truncated on a word boundary with an explicit marker, and
excess blank lines normalized.

`spork.core.llm.base`/`prompt`/`loader`/`clients.litellm` now provide a
real live-client path without putting provider-specific response types
into the pipeline. `build_prompt()` produces the exact messages,
Verdict-derived tool schema, and forced tool choice; `LiteLLMClient`
calls the optional SDK in-process and returns an `LLMResult` containing
the validated `Verdict` plus real token usage. Tests inject a mocked
completion callable, so they verify Spork's complete request and
response parsing without a network call.

The other five original items are all real, no live-account blocker: the
budget/draft items depend on `StateDB`/`Provider`, both fully testable
without a network call, and `RecordedLLMClient`'s whole point is *not*
needing one. **M3 is 8/8**: everything buildable without a live
Fastmail/model-provider session is real and tested; the genuinely-blocked pieces
(`JmapClient.connect()`/`fetch_new_messages()`/`apply_action()`/
`create_draft()`) remain settled-shape `NotImplementedError` stubs; the
live LLM adapter itself is no longer one.

**Also done (not a new checklist item):**
`spork.core.pipeline.tier2` (docs/DESIGN.md §10.7, tests 262–298)
wires the seven original items into one runnable pipeline — budget gate,
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

### M4 — Alerting — 4.5/5

| Checklist item | Implemented | Tested |
|---|---|---|
| `Alerter` protocol + `LoggingAlerter` | ✅ | ✅ — tests 303–317 (15 tests), 100% line coverage |
| SMTP alert backend (burn-in/unattended acceptance) | ✅ | ✅ — tests 699–701 (3 tests) |
| Real desktop-notification backend (`DesktopAlerter`) | ✅ | ✅ — tests 766–770 (5 tests), 100% line coverage |
| Alert triggers wired to confidence bands + VIP rules + daemon health | ✅ pipeline-visible portion — VIP escalation, alert_only, autoact_alert + urgency=="high", budget exhausted; ✅ daemon health, daily-budget-exhausted half (one-shot-per-day critical alert, `_check_daily_budget_alert()`); ❌ daemon health, JMAP-push-disconnected half (still genuinely blocked on a live EventSource connection to time out on — see `spork.core.providers.jmap.push.JmapPushTrigger`'s docstring) | ✅ pipeline-visible portion — tests 318–346 (29 tests: `from_in` prerequisite 318–322, `PipelineObserver`/`CorrelationIdFilter`/wiring 323–346), 100% line coverage on the touched modules; ✅ daily-budget-exhausted alert — tests 503–508 (6 tests), 100% line coverage on `spork.daemon` |
| Graceful degrade when no DBus session bus is available | ✅ `DesktopAlerter`'s own job — `notify-send` missing/failing falls back to `LoggingAlerter` | ✅ — 2 of tests 766–770 cover this directly |

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
practice — that's the application's job, M7).

`spork.core.alerts.desktop.DesktopAlerter` is the real backend the
above always pointed toward: wraps `notify-send(1)` (→
`org.freedesktop.Notifications` over the session D-Bus, no new DBus
library dependency), `runner` injected the same DI-for-subprocess
pattern `install_service()` uses. The "graceful degrade when no DBus
session bus is available" checklist item is this backend's own job,
not a separate mechanism — `notify-send` missing (not installed) or
failing (no session bus, a headless/SSH-only login) both fall back to
a fresh `LoggingAlerter` rather than raising, so `sporkd` keeps
running and the alert lands in the log instead of popping up. `spork
doctor`-style live proof (a real popup actually appearing) needs a
real desktop session this sandbox doesn't have — same shape of gap as
every other live-account item, just for a desktop session instead.

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
the daemon level, crash-looping) are **not** pipeline modules — they're
about `sporkd`'s own lifecycle, not any one message's `Pipeline.run()`,
so there's no `Payload` for a *pipeline* module to attach to. One of
the three is now built directly on the daemon loop instead:
`spork.daemon.loop._check_daily_budget_alert()` reads `StateDB` after
each `escalate_message()` call and fires a one-shot-per-day critical
alert the same way `BudgetGateSelector` already checks per message —
distinct from `RecordBudgetExhaustedFilter`'s existing per-message
alert (that one legitimately fires every time; this one fires once a
day, guarded by `DaemonState.budget_exhausted_alert_date` — a
date-equality check, not a boolean flag, so it self-resets across
midnight with no explicit reset logic). JMAP push disconnected stays
genuinely blocked (needs a live EventSource connection to time out
on); crash-loop detection was re-scoped to M6/systemd (`Restart=`/
`RestartSec=` in the unit file already does this — a daemon
babysitting its own restart count would duplicate that). See
docs/ROADMAP.md M4 for the up-to-date split. `PipelineObserver`'s correlation-ID
mechanism also partially satisfies M7's "per-message tracing" roadmap
item for the pipeline-internal piece (a known, stated limitation: a
correlation ID is scoped to one pipeline *run*, not one message's full
cross-tier lifetime — `escalate_message()`, the real Tier 2 caller M5
built, doesn't thread Tier 1's correlation ID into `Tier2Meta`) — M7
still separately owns `sporkd`'s overall structured logging setup and
audit-trail completeness beyond triage outcomes.

### M5 — CLI + daemon control surface — 11/11 (complete)

| Checklist item | Implemented | Tested |
|---|---|---|
| `spork.core.config` | ✅ | ✅ — tests 347–374 (28 numbered entries, 51 actual test cases — see note below), 100% line coverage |
| Runtime backend composition | ✅ | ✅ — tests 626–639 (14 tests), 100% line coverage on `spork.core.runtime`, `spork.core.config.schema`, `spork.cli.commands.config`, `spork.cli.commands.reclassify`, and `spork.daemon.loop` |
| Daemon event loop assembly | ✅ | ✅ — tests 375–383 (9 tests), 100% line coverage on `spork.daemon.loop` |
| Wire Tier 2 into the daemon loop | ✅ | ✅ — tests 418–435 + 502 (19 tests), 100% line coverage on the touched `spork.core.providers.*`/`spork.daemon.loop` code |
| IPC protocol + Unix socket server | ✅ | ✅ — tests 384–399 + 400–403 (20 tests), 99–100% line coverage on `spork.core.ipc` |
| `spork status` | ✅ | ✅ — tests 404–407 (4 tests), including a full end-to-end test against a real `sporkd` subprocess |
| `spork pause`/`resume` | ✅ | ✅ — tests 408–410 (3 tests), including a full pause→status→resume→status round trip |
| `spork rules list/edit/enable/disable` w/ live reload | ✅ | ✅ — tests 436–454 (19 tests), 100% line coverage on `spork.core.rules.writer`/`spork.daemon.state`/`spork.cli.commands.rules`, no gaps on the touched part of `spork.daemon.loop` |
| `spork config init/show/edit` | ✅ | ✅ — tests 455–478 plus 695–698, 100% line coverage on `spork.core.config.*`/`spork.cli.commands.config` |
| `spork logs` | ✅ | ✅ — tests 411–417 (7 tests) |
| `spork reclassify <id>` | ✅ | ✅ — tests 479–498 + 499–501 (23 tests), 100% line coverage on `spork.core.providers.*`/`spork.core.pipeline.*`/`spork.daemon.loop`/`spork.cli.commands.reclassify` |

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

### M6 — systemd packaging + install flow — 8/8 (complete)

| Checklist item | Implemented | Tested |
|---|---|---|
| `systemd/sporkd@.service` unit template | ✅ | ✅ — tests 530–533 (drift-guarded against the runtime constant), plus PKGBUILD's own tests 560–565 |
| `Type=notify`/`sd_notify` on ready | ✅ | ✅ — tests 516–522 (`spork.core.systemd.notify`, real `AF_UNIX SOCK_DGRAM` round trips), 558–559 (`run_daemon()` wiring) |
| Install helper (`spork install-service`) | ✅ | ✅ — tests 534–542 (`install_service()`, 100% line coverage), 543–548 (CLI, including a real fake-`systemctl`-on-`$PATH` success path) |
| README quickstart | ✅ | Not testable — prose, no test asserts README content (same as every prior README update in this repo's history) |
| `spork secrets enroll` keyring enrollment | ✅ | ✅ — tests 674–683; values are mocked and never printed or persisted by the test process |
| `spork doctor` checks unit install/enabled/active state | ✅ | ✅ — tests 523–529 (`check_unit_status()`, 100% line coverage), 553 (CLI) |
| `spork doctor` wires in secrets/config/backend checks | ✅ | ✅ — tests 509–510 (`resolve_secretspec_path()`), 548–557 and 637–639 (CLI, including provider/LLM/alerter construction with mapped secrets) |
| Arch Linux packaging (`PKGBUILD`) | ✅ | ✅ — tests 560–565 (syntax, required fields, unit-file install path, version match) — `makepkg -si` itself isn't run (no Arch tooling in this sandbox, confirmed) |

`spork.core.systemd` (`notify.py`/`unit.py`/`template.py`/`install.py`)
is four small, dependency-free modules — `notify()` hand-rolls the real
`sd_notify(3)` wire protocol against the stdlib `socket` module rather
than a new dependency, the same call `llm/clean.py`'s hand-rolled
`HTMLParser` made. `check_unit_status()`'s "unknown" (not
"inactive"/"disabled") treatment of a missing `systemctl` binary or an
unreachable user session bus was verified against this project's own
dev sandbox directly (`systemctl --user is-active` really does fail
with "Failed to connect to bus" here), not assumed.

`spork doctor`'s secrets check surfaced a real, empirically-confirmed
gap between `docs/DESIGN.md` §7.3's assumption and SecretSpec 0.18.0's
actual behavior: the Python SDK's `resolve()` resolves the *provider*
from a separate, genuinely global `~/.config/secretspec/config.toml`
(or `$XDG_CONFIG_HOME/secretspec/config.toml`) — the manifest's own
`[providers]` table (what the separate `secretspec` CLI tool reads) is
silently ignored by `resolve()` without an explicit `provider=`
argument. `tests/cli/commands/test_doctor.py`'s "full setup" fixture
writes both files now; `docs/DESIGN.md` §7.3 was updated to describe
the real (colocated, `resolve_secretspec_path()`-resolved) manifest
location, not the repo-root documentation copy.

`spork doctor` itself is a deliberate exception to every other command
in this codebase: it never stops at the first failure. Seven
independent checks, each its own `[ok]`/`[FAIL]` line, exit 1 only
once all seven have run and at least one failed — proven by a
from-scratch environment failing every check cleanly (test 148) and a
fully-configured one passing every check this milestone can actually
make pass, leaving only JMAP connectivity (M1, genuinely blocked) and
the never-installed systemd unit non-zero (test 552).

### M7 — Hardening & v1 release — 6/10

| Checklist item | Implemented | Tested |
|---|---|---|
| Confidence threshold tuning pass | — | Genuinely blocked — needs real triage volume from a live account |
| Rate-limit / 429 handling verified | — | Genuinely blocked — same live-account reason |
| Crash-loop / restart behavior verified | — | `Restart=on-failure` has been in the unit file since M6; *verifying* it needs a real systemd session this sandbox doesn't have either |
| Structured application logging | ✅ | ✅ — tests 566–574 (`spork.core.logging_setup`, 100% line coverage), 578–582 (CLI wiring) |
| Per-message tracing through the pipeline | ✅ | ✅ — tests 583–595 (`spork.core.pipeline.tracing`, 100% line+branch coverage on `spork.core.pipeline`) |
| Audit trail completeness (control-plane changes) | ✅ | ✅ — tests 596–609 (`StateDB.write_control_plane_audit_entry()`, `DaemonState.pending_control_plane_events`, CLI wiring across rules/config/pause/resume/reclassify — 100% coverage on every touched module) |
| Security review pass against §15 | ✅ | ✅ — test 610 (the one gap that needed a code fix: `Secrets.__repr__`); the README privacy-disclosure gap needed no test (prose) |
| Full test suite green; rule engine + action executor coverage | ✅ | ✅ — `spork.core.rules`/`spork.core.actions.executor` were already 100% line+branch before this pass; one small opportunistic gap closed (tests 608–609) |
| Poison-message resiliency (Tier 2 quarantine, not a crash) | ✅ | ✅ — tests 771–777 (`escalate_message_or_quarantine()`, `QUARANTINABLE_ERRORS`), 778–779 (`spork reclassify`/`spork backfill` wiring) |
| Tag v1.0.0 | — | Gated on the exit criteria below, which are gated on a live account |

`spork.core.pipeline.tracing` (`TracingStage`/`TracingSelector`) is a
generic wrapper layered on top of `build_default_pipeline()`/
`build_tier2_pipeline()` at composition time — no change to any of the
21 concrete Filter/Selector/Augment classes across both pipelines, and
no change to what their existing bare-`Payload` unit tests exercise
(tests 583–593 use a minimal local metadata type, not
`MessageMeta`/`Tier2Meta`, proving the wrapper is genuinely reusable,
not hardcoded to either pipeline's shape).

The audit-trail-completeness item needed a real design correction, not
just plumbing: a first-draft "make the `pause`/`resume` IPC handler
`async`, `await asyncio.to_thread(state_db.write_control_plane_audit_entry,
...)` directly from it" turns out not to actually serialize against
`_run_message_loop()`'s own in-flight `to_thread(process_message,
...)` call — two independent `to_thread()` calls from two different
coroutines can still race the same `sqlite3` connection object, the
exact hazard `docs/DESIGN.md` §6.2.2 already exists to avoid. Fixed by
not adding a second call site at all: `DaemonState` gains
`pending_control_plane_events`, appended to synchronously (an
in-memory mutation, same as flipping `.paused`) and drained once per
`_run_message_loop()` iteration — the one code path that already
safely, sequentially owns every `StateDB` access.

The security review pass found and fixed two real gaps, not just
confirmed the six existing claims: the README never actually disclosed
that ambiguous mail goes to Claude despite §15 explicitly claiming it
did (a real prose gap, now fixed), and `Secrets` (`spork.core.secrets`)
is a plain `@dataclass` whose default `__repr__` printed every
resolved secret's real value verbatim — confirmed empirically
(`repr(Secrets({"JMAP_API_TOKEN": "..."}))` really did leak the value)
before fixing with `repr=False` + a custom `__repr__` showing only the
declared names.

### M7a — Mutation & fuzz testing hardening — 4/4

| Checklist item | Implemented | Tested |
|---|---|---|
| Design: property-based + mutation testing strategy | ✅ | — prose (docs/DESIGN.md §16.1/§16.2) |
| Hypothesis property tests, four in-scope modules | ✅ | ✅ — tests 707–730 (`test_*_fuzz.py` siblings), part of the ordinary `uv run pytest` gate |
| `mutmut` wired up (dev dep, config, `mutation/README.md`) | ✅ | ✅ — `uv run mutmut run` reproduces the recorded baseline |
| First baseline mutation run + gap closure | ✅ | ✅ — tests 707–730 also cover the real gaps mutmut surfaced; 174 mutants, 171 killed, 3 recorded-equivalent survivors |

Mutation testing itself deliberately isn't part of `uv run pytest` or
either CI gate (mutation/README.md, same "different kind of test"
reasoning `benchmarks/` established) — its own weekly/manual workflow
(`.github/workflows/mutation-testing.yml`) is what "tested" means for
that one checklist item, not a pytest run. The gaps mutmut surfaced in
`rules.engine`, `dispatch.combine`, and `pipeline.default` were real
(a classifier/dispatch call receiving the wrong argument unverified, a
`new_correlation_id`/`classifier` injection point silently unforwarded,
a default clock never checked for being UTC, `build_default_pipeline()`'s
own `force` default never exercised, and one docstring-documented
"empty scores = exactly 0.0 confidence" contract with no deterministic
test) — closed with targeted tests, not implementation changes; no
`src/spork` behavior changed in this pass.

### M8 — Backfill / retroactive categorization — 4/5

| Checklist item | Implemented | Tested |
|---|---|---|
| `JmapClient.query_messages()` | ✅ | ✅ — tests 740–744, 762 (6 tests), live-verified against the real account |
| `BackfillPage`/`BackfillProvider` capability (`JmapProvider`, `FileProvider`) | ✅ | ✅ — tests 745–751 (7 tests) |
| Bounded, resumable `spork backfill` CLI | ✅ | ✅ — tests 752–760, 763–765 (12 tests: 6 acceptance + 6 edge cases) |
| `StateDB`/`processed_messages` dedup reuse | ✅ (reuses `process_message()`'s existing idempotency gate, no new mechanism) | ✅ — test 758 |
| Backfill-specific throttle/budget policy | ✅ (`--limit`, default 50) | ✅ — tests 756, 760 |
| Full backfill run growing the corpus at volume | — | not started — a 13-entry hand-picked seed exists (M1c) via direct SMTP+LLM calls, not a `spork backfill` run; that needs an all-`ignore` rules file or the write-side JMAP stubs resolved first (`apply_action()`/`create_draft()` are still `NotImplementedError`) |

### M9 — Read-only knowledgebase context retrieval — 3/4

| Checklist item | Implemented | Tested |
|---|---|---|
| `ContextProvider` Protocol + dynamic loader + pipeline wiring | ✅ | ✅ — tests 787–796, 801–805, 811 (100% line coverage on `spork.core.context`) |
| `NullContextProvider` (the real default) | ✅ | ✅ — tests 797–798 |
| A real backend that actually reads content (free-text vault) | — | genuinely undecided design work, not a live-account blocker — `MarkdownVaultContextProvider` (tests 799–800) settles the shape as a stub; the retrieval algorithm choice needs real vault content to validate against |
| `EntityContextProvider` (structured domain/company/service/person knowledge base, prototype) | ✅ | ✅ — tests 820–841 (100% line coverage on `spork.core.context.clients.entities`); specified in Gherkin (`docs/acceptance/m9_entity_context.feature`) |

### M10 — Receipt archiving — 10/10 built, fully wired end to end

Originally numbered M9; renumbered when the real M9 above landed
independently on `main` first (see docs/ROADMAP.md M10's own note).

| Checklist item | Implemented | Tested |
|---|---|---|
| `Provider.build_attachment_fetcher()` | ✅ (`FileProvider` real; `JmapProvider` a settled-shape `NotImplementedError`, out of scope not live-blocked) | ✅ — tests 879–886, 891–892 |
| `Provider.build_keyword_applier()` | ✅ (`FileProvider` real; `JmapProvider` a settled-shape `NotImplementedError`, genuinely write-blocked) | ✅ — tests 885, 887, 893–894 |
| `spork.core.receipts.registry` (`StateDB.known_receipt_senders` + `normalize_sender_domain()`) | ✅ | ✅ — tests 856–864 |
| `spork.core.receipts.extract` (deterministic path) | ✅ | ✅ — tests 865–871 |
| `spork.core.receipts.llm.ReceiptExtractionClient`/`RecordedReceiptExtractionClient` | ✅ | ✅ — tests 872–878 |
| `rules.schema.Action` gains `"archive_receipt"` | ✅ | ✅ — tests 895–896; found and fixed a real cross-cutting gap in `Verdict`/`verdict_tool_schema()` (test 906) |
| `spork.core.receipts.pdf.build_receipt_pdf()` | ✅ | ✅ — tests 842–849 |
| `spork.core.receipts.archive.save_pdf()` | ✅ | ✅ — tests 850–855 |
| `SporkConfig.receipt_archive` (`output_dir` + required `extraction: BackendSpec`) | ✅ | ✅ — tests 901–903, 914 |
| Pipeline wiring (`ArchiveReceiptAugment` + `build_default_pipeline()`/`process_message()`, `dry_run`) | ✅ | ✅ — tests 897–900, 904–905, 920–921 |
| `docs/acceptance/m10_receipt_archiving.feature` bound for real | ✅ | ✅ — 7 scenarios, fully passing; plus 15 more across `m10a`/`m10b`/`m10c`/`m10d` (22 total) |
| **Runtime wiring** (`spork.core.receipts.loader` + `spork.core.runtime.build_receipt_archive_components()` + `run_daemon()`/`_run_message_loop()`) | ✅ | ✅ — tests 907–913 (loader), 915–919 (runtime composition, including the real M9/M10 `EntityContextProvider` synergy), 922–923 (`run_daemon()` end to end, including `--observe`) |

`sporkd` now builds `ReceiptArchiveComponents` from
`[receipt_archive]`/`[context]` config at startup and actually uses
it — the acceptance suite's pipeline-level wiring and the real daemon
loop are both proven, not just one or the other. The only genuinely
open item is a live, LLM-backed `ReceiptExtractionClient`
implementation (docs/ROADMAP.md's Stretch section) — the `Protocol`,
loader, and config field are all real; only a second backend beyond
`RecordedReceiptExtractionClient` is missing, the same shape
`LiteLLMClient` already has relative to `LLMClient`/`RecordedLLMClient`.

---

## Full test inventory (892 tests, all passing — 0 xfail)

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

### tests/core/providers/jmap — live reads, push, and remaining stubs (M1)

The read-side client and push tests are real and network-free through
injected jmapc-shaped clients and event streams. Mutation-side tests still
pass normally by asserting their settled `NotImplementedError` behavior.

49. **`test_client.py::test_connect_authenticates_once_and_exposes_the_primary_account`**
    Authenticates once despite two `connect()` calls, resolves the Inbox
    role, and exposes the primary account ID used for cursor storage.

50. **`test_client.py::test_first_fetch_baselines_current_email_state_without_replaying_history`**
    `since_cursor=None` requests no Email objects and returns the current
    state with an empty batch, preventing an implicit historical replay.

51. **`test_push.py::test_wait_returns_for_a_relevant_email_event`**
    A relevant Email state event wakes the trigger.

52. **`test_push.py::test_wait_ignores_other_accounts_and_unrelated_events`**
    Events for another account and unrelated state types are ignored.

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

83. **`jmap/test_provider.py::test_content_fetcher_returns_messages_from_the_clients_candidate_batch`**
    The temporary TriggeredSource adapter unwraps messages from
    `JmapFetchResult`; cursor acknowledgement remains a separate daemon
    composition unit.

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

148. **`test_doctor.py::test_doctor_fails_every_check_cleanly_against_a_bare_environment`**
    (M6 redesign — supersedes the single-check-era
    `test_doctor_reports_a_clean_error_not_a_traceback`.) A bare
    environment (no config/secretspec anywhere): secrets/config/JMAP
    connectivity all `[FAIL]`, exit 1, no `"Traceback"` anywhere.

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

`spork.core.llm.base` (`VerdictRequest`/`Verdict`/`LLMResult`/`LLMClient`),
`spork.core.llm.loader` (`load_llm_client()`, tested against a fixture
class the same way `tests/core/providers/test_loader.py` tests
`load_provider()`), plus the prompt/LiteLLM/recording tests appended as
stable entries 611–625 below.

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

209. **Retired: `clients/test_anthropic.py::test_get_verdict_raises_not_implemented`**
    Removed when the settled-shape Anthropic stub was replaced by the
    real `LiteLLMClient`; number retained and never reused.

210. **Retired: `clients/test_anthropic.py::test_constructor_accepts_configured_model_and_max_tokens`**
    Removed with the direct Anthropic adapter; equivalent live-client
    constructor/request behavior is covered by tests 613 and 618.

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
against `RecordedLLMClient` — zero live model API calls anywhere
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
    and stores its verdict and per-call usage in metadata — the
    pipeline's one I/O stage, proven without a live API.

267. **`test_modules.py::test_record_llm_usage_filter_records_one_call`**
    Asserts one call and its real input/output token counts are recorded
    against `meta.ts`'s date.

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
    (279–289) The original `MissingMetaError` raise branches across
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

300. **`llm/test_loader_integration.py::test_load_llm_client_resolves_litellm_client_by_its_documented_spec`**
    `load_llm_client()` with the exact spec string §10.1 documents for
    `config.toml`. Asserts a real `LiteLLMClient` is returned.

301. **`llm/test_loader_integration.py::test_load_llm_client_resolves_recorded_llm_client_by_its_documented_spec`**
    Same, for §10.5's `RecordedLLMClient` spec. Asserts the loaded
    client genuinely works (`get_verdict()` returns the recorded
    response), not just that it constructs.

302. **Retired: `llm/test_loader_integration.py::test_load_llm_client_propagates_anthropic_client_get_verdict_not_implemented`**
    Removed with the Anthropic stub; number retained and never reused.

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

433. **`core/pipeline/tier2/test_escalate.py::test_parse_to_addresses_splits_and_strips_a_comma_separated_to_header`**
    `parse_to_addresses()` unit test: comma-split, whitespace-stripped.
    Relocated from `daemon/test_loop_edge_cases.py`'s
    `_parse_to_addresses()` (same assertion) once `spork reclassify
    <id>` (M5) needed the same function outside the daemon loop —
    number kept stable, path/name updated to match the real move.

434. **`core/pipeline/tier2/test_escalate.py::test_parse_to_addresses_returns_empty_tuple_when_no_to_header`**
    No `To:` header at all — `()`, not a `KeyError` or a fabricated
    address. Relocated alongside entry 433, same reason.

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

479. **`core/providers/jmap/test_client.py::test_get_message_raises_not_implemented`**
    `JmapClient.get_message()` is a settled-shape stub, same pattern as
    its other six methods.

480. **`core/providers/jmap/test_provider.py::test_build_message_lookup_returns_something_that_can_get_a_message`**
    `JmapProvider.build_message_lookup()` returns an object satisfying
    `MessageLookup`; calling it raises `NotImplementedError`,
    propagated from `JmapClient`.

481. **`core/providers/jmap/test_provider.py::test_message_lookup_delegates_to_the_client_directly`**
    `_JmapMessageLookup` is a real delegation to
    `JmapClient.get_message()`, not a second placeholder.

482. **`core/providers/file/test_provider.py::test_build_message_lookup_finds_a_message_by_id`**
    `get_message()` scans the same fixture file `build_source()`
    replays from and returns the matching `NormalizedMessage`.

483. **`core/providers/file/test_provider.py::test_message_lookup_raises_a_clean_error_for_an_unknown_id`**
    An unknown `message_id`: `MessageNotFoundError`, not a silent
    `None` or an unhandled exception.

484. **`core/pipeline/test_default.py::test_process_message_with_force_reprocesses_an_already_processed_message`**
    `force=True` bypasses `IdempotencyGateSelector` entirely — an
    already-processed message is evaluated and acted on again, its
    `processed_messages` row overwritten.

485. **`core/pipeline/tier2/test_escalate.py::test_escalate_message_wires_thread_history_and_mailbox_lister_into_tier2`**
    `escalate_message()` calls both Provider-supplied reads with the
    escalated message, and the resulting `Verdict`'s action is
    actually applied — a real end-to-end call into
    `process_tier2_message()`, not a passthrough.

486. **`cli/commands/test_reclassify.py::test_reclassify_help_works`**
    Asserts exit 0, usage text.

487. **`cli/commands/test_reclassify.py::test_reclassify_with_no_config_produces_a_clean_error`**
    Asserts exit 1, clean error, no traceback.

488. **`cli/commands/test_reclassify.py::test_reclassify_with_an_unknown_message_id_reports_a_clean_error`**
    Asserts exit 1, the unknown id named in the error, no traceback.

489. **`cli/commands/test_reclassify.py::test_reclassify_reruns_tier1_and_records_the_new_outcome`**
    A message matching a terminal rule: the new action appears in the
    output and `processed_messages` (`tier_reached="tier1"`).

490. **`cli/commands/test_reclassify.py::test_reclassify_escalates_through_tier2_when_the_rule_says_so`**
    A message matching an escalating rule: `processed_messages` ends
    up `tier_reached="tier2"` with the recorded verdict's action.

491. **`cli/commands/test_reclassify.py::test_reclassify_reprocesses_a_message_already_marked_processed`**
    The whole point: running `reclassify` twice on the same message
    both succeed and both record the outcome.

492. **`core/pipeline/test_default_edge_cases.py::test_process_message_with_force_on_a_never_processed_message_behaves_normally`**
    `force=True` on a message that was never processed to begin with
    behaves exactly like `force=False` — not double-applied or treated
    specially.

493. **`core/pipeline/tier2/test_escalate.py::test_escalate_message_returns_none_when_the_daily_budget_is_exhausted`**
    `escalate_message()` passes `process_tier2_message()`'s
    None-on-budget-exhausted result straight through.

494. **`cli/commands/test_reclassify_edge_cases.py::test_reclassify_help_lists_the_message_id_argument`**
    `--help` mentions the `message_id` argument.

495. **`cli/commands/test_reclassify_edge_cases.py::test_reclassify_reports_budget_exhausted_rather_than_crashing`**
    A rule that escalates, but the daily call budget is already zero:
    a clear message, exit 0, not an unhandled exception.

496. **`cli/commands/test_reclassify_edge_cases.py::test_reclassify_with_no_message_id_argument_is_a_usage_error`**
    Omitting the required argument entirely is Typer's own usage error
    (exit 2), never our own error handling.

497. **`cli/commands/test_reclassify_edge_cases.py::test_reclassify_appears_in_top_level_help`**
    `spork --help` lists the `reclassify` subcommand.

498. **`cli/commands/test_reclassify_edge_cases.py::test_reclassify_works_while_a_real_sporkd_is_running`**
    The real point of being standalone: `reclassify` against the same
    `StateDB` a running `sporkd` is using, concurrently, without either
    side failing (docs/DESIGN.md §7.4's WAL-mode reasoning).

499. **`cli/commands/test_reclassify_edge_cases.py::test_reclassify_with_an_unloadable_provider_spec_reports_a_clean_error`**
    A real bug found during a docs-normalization pass: `load_provider()`
    had no exception handling around it at all — a bad `provider.spec`
    produced a raw traceback. Fixed (`_reclassify()` now wraps the
    whole body in one `except (*_LoadError, MessageNotFoundError)`,
    mirroring `spork.daemon.main`'s tuple).

500. **`cli/commands/test_reclassify_edge_cases.py::test_reclassify_with_an_unloadable_rules_file_reports_a_clean_error`**
    Same bug, `load_rules()` — a malformed `rules.toml` also produced a
    raw traceback before the fix above.

501. **`cli/commands/test_reclassify_edge_cases.py::test_reclassify_with_an_unloadable_llm_spec_reports_a_clean_error_only_when_it_escalates`**
    Same bug, `load_llm_client()` — only reachable once Tier 1
    escalates, but still uncaught before the fix.

502. **`daemon/test_main.py::test_an_unloadable_llm_spec_produces_a_clean_error_not_a_traceback`**
    A second real bug found the same pass: `spork.daemon.main`'s
    except tuple never included `LLMClientLoadError`, even though
    `run_daemon()` has constructed an `LLMClient` at startup since Tier
    2 was wired into the loop — a bad `llm.spec` crashed `sporkd` with
    a raw traceback instead of the clean error every other load
    failure gets. Fixed by adding `LLMClientLoadError` to the tuple.

503. **`daemon/test_loop.py::test_run_daemon_fires_a_daemon_level_alert_when_the_daily_budget_is_exhausted`**
    `run_daemon()` end to end with `daily_call_budget=0`: the new
    one-shot daemon-health alert (docs/DESIGN.md §12.3) fires when an
    escalated message lands on an already-exhausted budget.

504. **`daemon/test_loop.py::test_run_daemon_fires_the_daemon_level_budget_alert_only_once`**
    Two messages escalate onto the same exhausted budget in one run;
    the daemon-level alert delivers exactly once (counted via
    `LoggingAlerter`'s own log records, not raw substring occurrences —
    a single `PipelineObserver.alert()` call legitimately logs its
    title twice, once via `trace()` and once via delivery).

505. **`daemon/test_loop.py::test_run_daemon_does_not_fire_the_daemon_level_budget_alert_when_budget_remains`**
    The ordinary default-budget config never trips the new alert —
    it's specific to exhaustion, not a side effect of any escalation.

506. **`daemon/test_loop_edge_cases.py::test_check_daily_budget_alert_fires_once_and_stamps_todays_date`**
    Unit-tests `_check_daily_budget_alert()` directly: fires once
    against an already-exhausted budget and stamps
    `DaemonState.budget_exhausted_alert_date`; a second check the same
    day is a no-op.

507. **`daemon/test_loop_edge_cases.py::test_check_daily_budget_alert_does_nothing_one_call_below_the_limit`**
    `has_budget_remaining()`'s limit is exclusive (§10.4) — one call
    short of the budget is still "remaining," not exhausted, so no
    alert fires.

508. **`daemon/test_loop_edge_cases.py::test_check_daily_budget_alert_fires_again_after_a_date_rollover`**
    The guard is a date-equality check against `now()`, not a boolean
    flag: a second exhausted-budget day fires again and re-stamps the
    date, with no explicit reset step anywhere.

### M6 — systemd packaging + install flow

509. **`core/config/test_paths.py::test_resolve_secretspec_path_uses_xdg_config_home_when_set`**
    (parametrized, 8 path shapes) `XDG_CONFIG_HOME/spork/secretspec.toml`.

510. **`core/config/test_paths.py::test_resolve_secretspec_path_falls_back_to_home_dot_config_when_unset`**
    Same `$HOME/.config` fallback as `resolve_user_config_path()`.

511. **`core/config/test_paths.py::test_resolve_user_unit_path_uses_xdg_config_home_when_set`**
    (parametrized, 8 path shapes) `XDG_CONFIG_HOME/systemd/user/sporkd@.service`
    — systemd's own real user-unit search path, not a spork subdirectory.

512. **`core/config/test_paths.py::test_resolve_user_unit_path_falls_back_to_home_dot_config_when_unset`**
    Same `$HOME/.config` fallback, systemd's documented default.

513. **`core/config/test_paths.py::test_resolve_user_unit_path_accepts_a_different_unit_name`**
    `unit_name` is a parameter, not hardcoded to `"sporkd"`.

514. **`core/config/test_paths_edge_cases.py::test_resolve_secretspec_path_treats_relative_or_empty_as_unset`**
    (parametrized, 3 cases) Same "relative/empty counts as unset" rule
    as every other resolver.

515. **`core/config/test_paths_edge_cases.py::test_resolve_user_unit_path_treats_relative_or_empty_as_unset`**
    (parametrized, 3 cases) Same rule.

516. **`core/systemd/test_notify.py::test_notify_sends_the_given_state_to_notify_socket`**
    A real `AF_UNIX SOCK_DGRAM` socket bound in `tmp_path`: `notify()`
    sends the exact bytes, real wire protocol, no mock.

517. **`core/systemd/test_notify.py::test_notify_returns_false_and_sends_nothing_when_notify_socket_is_unset`**
    The common case (not running under `Type=notify`): a safe no-op.

518. **`core/systemd/test_notify.py::test_notify_prefers_an_explicit_socket_path_over_the_environ`**
    `socket_path` wins over `$NOTIFY_SOCKET` when both are given.

519. **`core/systemd/test_notify.py::test_notify_supports_the_abstract_namespace_form`**
    A leading `@` translates to the real `'\0'`-prefixed Linux
    abstract-namespace address, bound and read back for real.

520. **`core/systemd/test_notify_edge_cases.py::test_notify_reads_the_real_os_environ_by_default`**
    No `environ` override: falls back to the real process environment.

521. **`core/systemd/test_notify_edge_cases.py::test_notify_returns_false_when_the_socket_path_does_not_exist`**
    A stale/never-created socket path returns `False`, never raises —
    a best-effort readiness signal shouldn't crash `sporkd`'s startup.

522. **`core/systemd/test_notify_edge_cases.py::test_notify_returns_false_when_the_state_is_empty`**
    An empty state string is a no-op before the socket is even touched.

523. **`core/systemd/test_unit.py::test_check_unit_status_reports_installed_enabled_active_when_all_good`**
    The healthy case, via an injected fake `systemctl` runner.

524. **`core/systemd/test_unit.py::test_check_unit_status_reports_not_installed_when_no_unit_file_exists`**
    `installed` is a plain filesystem check, independent of `systemctl`.

525. **`core/systemd/test_unit.py::test_check_unit_status_reports_unknown_when_systemctl_is_not_installed`**
    No `systemctl` binary at all — reports `"unknown"`, never crashes.

526. **`core/systemd/test_unit.py::test_check_unit_status_reports_unknown_when_the_user_bus_is_unreachable`**
    "Failed to connect to bus" (confirmed real in this sandbox) is
    `"unknown"`, not misreported as `"inactive"`/`"disabled"`.

527. **`core/systemd/test_unit.py::test_check_unit_status_uses_the_given_unit_name`**
    `unit_name` flows through to the actual `systemctl` invocation.

528. **`core/systemd/test_unit_edge_cases.py::test_check_unit_status_default_unit_path_uses_resolve_user_unit_path`**
    No `unit_path` override: `installed` reflects the real resolver.

529. **`core/systemd/test_unit_edge_cases.py::test_check_unit_status_reports_unknown_on_a_timeout`**
    `subprocess.TimeoutExpired` gets the same `"unknown"` treatment as
    a missing binary (already covered — no code change needed).

530. **`core/systemd/test_template.py::test_unit_file_content_matches_the_tracked_systemd_service_file`**
    `UNIT_FILE_CONTENT` byte-matches the tracked `systemd/sporkd@.service`
    — the drift guard.

531. **`core/systemd/test_template.py::test_unit_file_content_is_type_notify`**
    `Type=notify` is present — `run_daemon()`'s `sd_notify` call means
    something to `systemctl --user status` only if this holds.

532. **`core/systemd/test_template.py::test_unit_file_content_restarts_on_failure`**
    `Restart=on-failure` is present.

533. **`core/systemd/test_template.py::test_unit_file_content_never_embeds_a_secret`**
    No `token`/`api_key`/`password`/`secret=` marker anywhere in the
    unit file content.

534. **`core/systemd/test_install.py::test_install_service_writes_the_unit_file_content`**
    Writes `UNIT_FILE_CONTENT` verbatim to `unit_path`.

535. **`core/systemd/test_install.py::test_install_service_creates_missing_parent_directories`**
    `~/.config/systemd/user/` doesn't exist on a fresh machine —
    created, not failed on.

536. **`core/systemd/test_install.py::test_install_service_returns_the_written_path`**

537. **`core/systemd/test_install.py::test_install_service_runs_daemon_reload_and_enable_now_by_default`**
    Both `systemctl` calls happen, via the injected runner.

538. **`core/systemd/test_install.py::test_install_service_skips_enable_now_when_asked`**
    `enable_now=False` still runs `daemon-reload`, skips `enable --now`.

539. **`core/systemd/test_install.py::test_install_service_raises_when_systemctl_is_not_installed`**
    Wrapped as `InstallServiceError`.

540. **`core/systemd/test_install.py::test_install_service_raises_when_daemon_reload_fails`**
    A `CalledProcessError` (e.g. "Failed to connect to bus") wrapped
    as one `InstallServiceError`.

541. **`core/systemd/test_install.py::test_install_service_uses_the_given_unit_name`**

542. **`core/systemd/test_install_edge_cases.py::test_install_service_raises_when_the_unit_file_cannot_be_written`**
    `unit_path`'s parent blocked by an existing regular file — a real
    `NotADirectoryError`, wrapped before `systemctl` is ever touched.

543. **`cli/commands/test_install_service.py::test_install_service_help_works`**

544. **`cli/commands/test_install_service.py::test_install_service_appears_in_top_level_help`**

545. **`cli/commands/test_install_service.py::test_install_service_writes_the_unit_file_even_when_systemctl_fails`**
    The write happens before `daemon-reload` — a real, inspectable
    unit file on disk even in this systemd-less sandbox.

546. **`cli/commands/test_install_service.py::test_install_service_reports_a_clean_error_not_a_traceback`**
    Real subprocess, real (bus-less) `systemctl` in this sandbox —
    confirmed deterministic failure, not mocked. Exit 1, no traceback.

547. **`cli/commands/test_install_service_edge_cases.py::test_install_service_reports_success_when_systemctl_succeeds`**
    A fake `systemctl` script prepended onto `$PATH`: exit 0, both
    success messages printed.

548. **`cli/commands/test_install_service_edge_cases.py::test_install_service_no_enable_now_skips_the_enable_message`**
    `--no-enable-now`'s different closing message.

549. **`cli/commands/test_doctor.py::test_doctor_help_works`** (unchanged from the single-check era)

550. **`cli/commands/test_doctor.py::test_doctor_appears_in_top_level_help`** (unchanged)

551. **`cli/commands/test_doctor.py::test_doctor_skips_provider_rules_and_classifier_checks_when_config_fails`**
    provider/rules/local-classifier report `"skipped — config failed
    to load"`, not silently omitted or crashed on.

552. **`cli/commands/test_doctor.py::test_doctor_passes_every_check_a_full_setup_can_pass`**
    A fully valid config+secretspec setup (`env://` provider, plus the
    separate *global* `~/.config/secretspec/config.toml` SecretSpec's
    SDK actually reads the provider from — verified empirically):
    secrets/config/provider/rules/local-classifier all `[ok]`, only
     the systemd unit (never installed here) keeps exit code 1; JMAP is
     not applicable to this fixture's FileProvider.

553. **`cli/commands/test_doctor.py::test_doctor_reports_systemd_unit_state`**
    `"installed=False"` in an isolated `$XDG_CONFIG_HOME` that never
    had `spork install-service` run against it.

554. **`cli/commands/test_doctor_edge_cases.py::test_doctor_reports_provider_failure_when_the_spec_is_bad`**
    A valid config naming an unloadable provider spec — `[FAIL]
    provider`, `[ok] config`.

555. **`cli/commands/test_doctor_edge_cases.py::test_doctor_reports_rules_failure_when_the_rules_file_is_missing`**
    `[FAIL] rules`, `[ok] config`.

556. **`cli/commands/test_doctor_edge_cases.py::test_doctor_reports_local_classifier_failure_when_unregistered`**
    No classifier backend is registered anywhere in this codebase yet
    (`classify/keyword.py` still planned, §9.1) — naming any
    `local_classifier` is always `UnknownClassifierError` today.

557. **`cli/commands/test_doctor_edge_cases.py::test_doctor_reports_local_classifier_ok_when_none_configured`**
    The default (no `local_classifier` at all) is valid, not a failure.

558. **`daemon/test_loop.py::test_run_daemon_signals_readiness_via_notify_fn`**
    `run_daemon()` calls `notify_fn("READY=1")` once composition has
    succeeded, proven via an injected stub.

559. **`daemon/test_loop.py::test_run_daemon_signals_readiness_exactly_once`**
    Not once per poll iteration — one "I'm up" per process lifetime.

560. **`test_pkgbuild.py::test_pkgbuild_exists`**

561. **`test_pkgbuild.py::test_pkgbuild_is_syntactically_valid_bash`**
    `bash -n` — a real parse, not a guess. `makepkg`/`pacman` aren't
    available in this sandbox (confirmed, Ubuntu) — same
    can't-exercise-honestly-here situation as `JmapClient.connect()`,
    for a shell script instead of a Python function.

562. **`test_pkgbuild.py::test_pkgbuild_declares_the_fields_makepkg_requires`**
    `pkgname`/`pkgver`/`pkgrel`/`arch`/`license`/`pkgdesc`.

563. **`test_pkgbuild.py::test_pkgbuild_has_build_and_package_functions`**

564. **`test_pkgbuild.py::test_pkgbuild_installs_the_tracked_systemd_unit_file`**
    The same `systemd/sporkd@.service` `spork install-service` embeds a
    copy of — one unit definition, two install paths.

565. **`test_pkgbuild.py::test_pkgbuild_pkgver_matches_pyproject`**
    No drift between the Arch package version and `pyproject.toml`'s own.

### M7 — Hardening & v1 release

566. **`core/test_logging_setup.py::test_configure_logging_defaults_the_spork_logger_to_info`**

567. **`core/test_logging_setup.py::test_configure_logging_sets_the_given_level`**

568. **`core/test_logging_setup.py::test_configure_logging_writes_a_line_to_the_given_stream`**

569. **`core/test_logging_setup.py::test_configure_logging_output_includes_level_and_logger_name`**
    Journal-friendly: no timestamp, but level + logger name so
    `spork.pipeline`/`spork.daemon.loop`/etc. lines are distinguishable.

570. **`core/test_logging_setup.py::test_configure_logging_respects_the_configured_level`**
    A DEBUG message is dropped when configured at INFO.

571. **`core/test_logging_setup.py::test_configure_logging_is_idempotent_not_accumulating_handlers`**
    A second `configure_logging()` call replaces the handler rather
    than adding a second one.

572. **`core/test_logging_setup_edge_cases.py::test_configure_logging_appends_extra_fields_as_key_value_pairs`**
    The exact mechanism `PipelineObserver.trace()` relies on for
    `correlation_id`.

573. **`core/test_logging_setup_edge_cases.py::test_configure_logging_includes_exception_info_when_logged_with_exc_info`**

574. **`core/test_logging_setup_edge_cases.py::test_configure_logging_raises_valueerror_for_an_unknown_level`**

575. **`core/config/test_schema.py::test_sporkconfig_log_level_defaults_to_info`**

576. **`core/config/test_schema.py::test_sporkconfig_accepts_every_documented_log_level`**
    (parametrized, 5 level names)

577. **`core/config/test_schema.py::test_sporkconfig_rejects_an_unknown_log_level`**
    A typo'd/lowercase `log_level` fails loudly at config-load time.

578. **`daemon/test_main.py::test_log_level_option_appears_in_help`**

579. **`daemon/test_main.py::test_an_invalid_log_level_produces_a_clean_error_not_a_traceback`**

580. **`daemon/test_main.py::test_sporkd_starts_successfully_with_a_log_level_override`**
    A real running `sporkd` subprocess, same spawn-and-wait-for-the-
    socket pattern `test_status.py`'s own end-to-end test uses.

581. **`cli/test_main.py::test_log_level_option_appears_in_help`**

582. **`cli/test_main.py::test_an_invalid_log_level_produces_a_clean_error_not_a_traceback`**
    Fails before the subcommand (`doctor`) ever runs.

583. **`core/pipeline/test_tracing.py::test_tracing_stage_delegates_to_the_wrapped_filter`**

584. **`core/pipeline/test_tracing.py::test_tracing_stage_delegates_to_the_wrapped_augment_via_augment_not_apply`**
    The real point: a `TracingStage` wrapping an `Augment` still calls
    `.augment()` on it, even though the wrapper itself only ever
    exposes `.apply()` to the outer `Pipeline`.

585. **`core/pipeline/test_tracing.py::test_tracing_stage_traces_the_wrapped_stage_name`**

586. **`core/pipeline/test_tracing.py::test_tracing_stage_includes_the_correlation_id_in_the_trace`**

587. **`core/pipeline/test_tracing.py::test_tracing_stage_defaults_correlation_id_when_meta_has_none`**
    A run before `CorrelationIdFilter` never crashes for lack of one.

588. **`core/pipeline/test_tracing.py::test_tracing_stage_includes_duration_ms`**

589. **`core/pipeline/test_tracing.py::test_tracing_selector_delegates_to_the_wrapped_selector`**

590. **`core/pipeline/test_tracing.py::test_tracing_selector_traces_the_chosen_branch`**

591. **`core/pipeline/test_tracing.py::test_wrap_stages_wraps_every_element_preserving_order`**

592. **`core/pipeline/test_tracing.py::test_wrap_stages_wrapped_list_still_runs_in_order`**

593. **`core/pipeline/test_tracing.py::test_wrap_selector_wraps_the_given_selector`**

594. **`core/pipeline/test_default.py::test_process_message_traces_every_stage_it_runs`**
    A real message through `process_message()`: every one of the 7
    stages it runs is traced, not just the alert-worthy ones.

595. **`core/pipeline/tier2/test_default.py::test_process_tier2_message_traces_every_stage_it_runs`**
    Same, for the Tier 2 pipeline's 8 stages on a high-confidence
    autoact path.

596. **`core/state/test_audit_log.py::test_write_control_plane_audit_entry_uses_the_empty_string_jmap_id_sentinel`**

597. **`core/state/test_audit_log.py::test_write_control_plane_audit_entry_records_detail_json`**

598. **`core/state/test_audit_log.py::test_get_audit_entries_returns_control_plane_and_message_entries_together`**
    `spork logs` needed no new filtering — both kinds share one
    unfiltered, oldest-first listing.

599. **`core/state/test_audit_log.py::test_get_audit_entries_filtered_by_jmap_id_excludes_control_plane_entries`**
    `--message-id` only ever matches per-message rows, by design.

600. **`daemon/test_loop_edge_cases.py::test_run_message_loop_drains_pending_control_plane_events`**
    A pre-queued `PendingAuditEvent` is written on the first iteration
    and cleared from the pending list — proven directly against
    `_run_message_loop()`.

601. **`daemon/test_loop_edge_cases.py::test_run_message_loop_drains_pending_events_even_while_paused`**
    Otherwise a repeated pause (or a resume the loop hasn't observed
    yet) would never get its own audit entry written.

602. **`daemon/test_loop_ipc.py::test_run_daemon_pause_and_resume_write_control_plane_audit_entries`**
    End to end: pause/resume over a real socket against a real
    running `run_daemon()` eventually produce `"daemon_paused"`/
    `"daemon_resumed"` rows.

603. **`cli/commands/test_rules_list_edit_enable_disable.py::test_rules_enable_writes_a_control_plane_audit_entry`**
    `detail_json` names the rule.

604. **`cli/commands/test_rules_list_edit_enable_disable.py::test_rules_disable_writes_a_control_plane_audit_entry`**

605. **`cli/commands/test_config.py::test_config_edit_writes_a_control_plane_audit_entry_on_success`**

606. **`cli/commands/test_config.py::test_config_edit_writes_no_audit_entry_on_a_rejected_save`**
    A save that fails validation never reaches `load_config()`
    successfully, so nothing gets written.

607. **`cli/commands/test_reclassify.py::test_reclassify_writes_a_control_plane_audit_entry`**
    Distinct from the per-message outcome row `process_message()`'s
    own `WriteAuditEntryFilter` already writes.

608. **`cli/commands/test_pause.py::test_pause_with_no_config_produces_a_clean_error`**
    Same `ConfigLoadError`-before-ever-touching-the-socket convention
    `spork status` already had.

609. **`cli/commands/test_pause.py::test_resume_with_no_config_produces_a_clean_error`**

610. **`core/test_secrets_edge_cases.py::test_secrets_repr_never_exposes_resolved_values`**
    Security review finding: the default dataclass `__repr__` printed
    every resolved secret's real value verbatim — confirmed
    empirically before fixing.

### M3 LiteLLM follow-up (tests 611–625)

611. **`core/llm/test_prompt.py::test_build_prompt_contains_the_complete_message_context`**
    Asserts the exact system/user message list contains every cleaned
    `VerdictRequest` field, including thread and mailbox context.

612. **`core/llm/test_prompt.py::test_build_prompt_forces_one_deliver_verdict_tool_with_the_verdict_schema`**
    Asserts the tool parameters equal `Verdict.model_json_schema()` and
    `tool_choice` explicitly names `deliver_verdict`.

613. **`core/llm/clients/test_litellm.py::test_litellm_client_sends_the_exact_prompt_and_forced_tool_choice`**
    A mocked completion callable receives the configured model, key,
    token limit, full messages, tool schema, and forced choice.

614. **`core/llm/clients/test_litellm.py::test_litellm_client_parses_the_tool_arguments_and_real_token_usage`**
    A LiteLLM-shaped response produces a validated `Verdict` and real
    prompt/completion token counts in `LLMResult`.

615. **`core/llm/test_recording.py::test_recording_client_appends_the_complete_prompt_result_and_usage`**
    Asserts one JSONL corpus entry contains subject, exact prompt,
    canonical SHA-256, validated verdict, usage, and timestamp.

616. **`core/llm/test_recording.py::test_live_acceptance_corpus_directory_is_gitignored`**
    Protects potentially unpublishable live mail under
    `tests/fixtures/corpus/` from accidental commits.

617. **`core/llm/clients/test_litellm_edge_cases.py::test_constructor_reports_how_to_install_the_missing_optional_dependency`**
    A missing SDK raises `LiteLLMClientError` naming `spork[llm]`.

618. **`core/llm/clients/test_litellm_edge_cases.py::test_constructor_loads_the_optional_sdk_completion_when_not_injected`**
    Covers the real lazy-import path without making a network call.

619. **`core/llm/clients/test_litellm_edge_cases.py::test_upstream_completion_failure_is_wrapped_at_the_client_boundary`**
    An upstream timeout becomes one catchable client error while
    retaining the original exception as `__cause__`.

620. **`core/llm/clients/test_litellm_edge_cases.py::test_malformed_tool_responses_fail_closed`**
    Parametrized across zero/multiple/wrong tool calls, malformed JSON,
    an invalid Verdict, and missing usage; every case fails closed.

621. **`core/llm/test_recording_edge_cases.py::test_failed_call_is_never_recorded`**
    A delegated failure creates no corpus file or misleading fixture.

622. **`core/llm/test_recording_edge_cases.py::test_successful_calls_append_independent_json_lines`**
    Two calls append in order and retain distinct prompt hashes.

623. **`core/llm/test_recording_edge_cases.py::test_prompt_hash_is_stable_but_sensitive_to_message_content`**
    Identical prompts hash identically; changing only body content
    changes the hash.

624. **`core/llm/test_recording_edge_cases.py::test_default_recording_clock_writes_a_parseable_utc_timestamp`**
    Covers the production clock path and confirms timezone awareness.

625. **`core/pipeline/tier2/test_modules_edge_cases.py::test_record_llm_usage_filter_raises_when_call_usage_is_missing`**
    A timestamp cannot silently invent token counts when
    `CallLLMAugment` did not populate `meta.llm_usage`.

### M5 runtime composition follow-up (tests 626–639)

626. **`core/config/test_schema.py::test_backendspec_accepts_secret_name_mappings_separately_from_kwargs`**
    Keeps SecretSpec field names separate from ordinary constructor
    values.

627. **`core/config/test_schema.py::test_backendspec_rejects_a_constructor_key_in_both_config_and_secrets`**
    Rejects ambiguous constructor argument sources during validation.

628. **`core/config/test_schema.py::test_sporkconfig_accepts_optional_llm_recording_configuration`**
    Validates the private corpus path as top-level configuration.

629. **`core/test_runtime.py::test_materialize_backend_kwargs_injects_values_without_mutating_config`**
    Resolves mapped values into a fresh constructor dictionary; the
    validated config still contains names, never resolved credentials.

630. **`core/test_runtime.py::test_runtime_resolves_secret_spec_once_for_all_configured_backends`**
    One resolution supplies every backend in a command invocation.

631. **`core/test_runtime.py::test_runtime_builders_inject_secrets_and_wrap_llm_recording`**
    Provider, LLM, and alerter receive mapped values, and an LLM call
    writes the configured corpus file.

632. **`daemon/test_loop.py::test_run_daemon_injects_mapped_secrets_and_records_the_live_llm_path`**
    End-to-end daemon composition reaches Tier 2 using secret-mapped
    file paths and records the successful verdict.

633. **`core/test_runtime_edge_cases.py::test_runtime_skips_secretspec_when_no_backend_maps_a_secret`**
    Existing secret-free configurations do not require a manifest.

634. **`core/test_runtime_edge_cases.py::test_materialization_reports_an_unresolved_mapped_name_cleanly`**
    A missing mapped name remains one catchable `SecretsError`.

635. **`core/test_runtime_edge_cases.py::test_llm_builder_does_not_record_when_recording_is_unconfigured`**
    Omitting `[llm_recording]` returns the configured client directly.

636. **`cli/commands/test_config_edge_cases.py::test_format_show_lines_displays_secret_names_and_recording_path`**
    Effective config output shows safe SecretSpec names and corpus
    configuration without resolving credentials.

637. **`cli/commands/test_doctor_edge_cases.py::test_doctor_injects_a_mapped_provider_secret`**
    Doctor validates a real provider constructor using a resolved
    SecretSpec mapping.

638. **`cli/commands/test_doctor_edge_cases.py::test_doctor_reports_llm_failure_when_the_spec_is_bad`**
    A bad LLM spec is an independent failed check, never a traceback.

639. **`cli/commands/test_doctor_edge_cases.py::test_doctor_reports_alerter_failure_when_the_spec_is_bad`**
    A bad alerter spec is likewise reported cleanly and independently.

### M1 live JMAP read follow-up (tests 640–651)

640. **`core/providers/jmap/test_client.py::test_fetch_pages_created_messages_normalizes_and_filters_to_inbox`**
    Exhausts multiple changes pages, fetches created objects, filters
    non-Inbox mail, and normalizes sender/body/header fields.

641. **`core/providers/jmap/test_client.py::test_session_and_request_failures_share_one_jmap_error_boundary`**
    A backend failure becomes one catchable `JmapError`.

642. **`core/providers/jmap/test_client_edge_cases.py::test_missing_optional_dependency_names_the_install_extra`**
    Both lazy import paths identify `spork[jmap]` when absent.

643. **`core/providers/jmap/test_client_edge_cases.py::test_default_factory_passes_credentials_to_jmapc`**
    The production factory passes host and token to jmapc without
    retaining another representation.

644. **`core/providers/jmap/test_client_edge_cases.py::test_connect_rejects_missing_or_ambiguous_inbox_roles`**
    Parametrized across no Inbox and duplicate Inbox-role mailboxes.

645. **`core/providers/jmap/test_client_edge_cases.py::test_connect_rejects_incomplete_session_metadata`**
    Rejects a missing mailbox list or primary account ID.

646. **`core/providers/jmap/test_client_edge_cases.py::test_baseline_requires_a_nonempty_email_state`**
    Refuses a checkpoint that cannot be resumed later.

647. **`core/providers/jmap/test_client_edge_cases.py::test_empty_changes_advance_the_candidate_cursor_without_email_get`**
    Empty change pages advance state without an unnecessary object fetch.

648. **`core/providers/jmap/test_client_edge_cases.py::test_changes_reject_malformed_state_metadata`**
    Invalid created IDs, states, and pagination flags fail closed.

649. **`core/providers/jmap/test_client_edge_cases.py::test_email_get_failures_are_reported_at_the_jmap_boundary`**
    Transport failures and malformed object lists share `JmapError`.

650. **`core/providers/jmap/test_client_edge_cases.py::test_normalization_rejects_a_message_without_jmap_ids`**
    Required transport identity fields cannot be fabricated.

651. **`core/providers/jmap/test_client_edge_cases.py::test_normalization_tolerates_missing_optional_sender_body_and_headers`**
    Optional RFC fields safely normalize to empty pipeline values.

### M1 cursor-safe daemon follow-up (tests 652–660)

652. **`core/providers/jmap/test_provider.py::test_checkpointed_source_exposes_the_clients_candidate_state`**
    The JMAP source carries the candidate Email state forward between
    polls while exposing the ordinary Source view.

653. **`core/sources/test_checkpoint.py::test_message_batch_holds_messages_and_a_candidate_checkpoint`**
    `MessageBatch` keeps messages and a checkpoint together immutably.

654. **`core/sources/test_checkpoint.py::test_checkpointed_source_is_structurally_distinct_from_plain_source`**
    A source opts into cursor-aware polling through the separate
    structural protocol.

655. **`core/sources/test_checkpoint.py::test_message_batch_accepts_an_empty_checkpoint_for_non_cursor_sources`**
    Plain providers can use the batch shape without a cursor.

656. **`daemon/test_loop_edge_cases.py::test_checkpoint_is_acknowledged_after_the_whole_batch_succeeds`**
    A successful batch persists its candidate state after processing.

657. **`daemon/test_loop_edge_cases.py::test_checkpoint_is_not_acknowledged_when_processing_fails`**
    An action failure leaves the cursor unchanged.

658. **`daemon/test_loop_edge_cases.py::test_checkpoint_is_not_acknowledged_when_shutdown_interrupts_a_batch`**
    Shutdown between messages does not acknowledge a partial batch.

659. **`daemon/test_loop_edge_cases.py::test_empty_checkpointed_batches_are_acknowledged`**
    A no-message state transition is still persisted.

660. **`daemon/test_loop_edge_cases.py::test_failed_batch_leaves_the_previous_cursor_for_a_restart`**
    Restart-visible state remains at the prior checkpoint so the failed
    batch is replayable.

661. **`core/providers/jmap/test_provider.py::test_provider_builds_a_checkpointed_source_and_exposes_account_id`**
    Covers the provider capability used by daemon composition to load the
    account cursor before readiness.

### M1 EventSource and polling fallback follow-up (tests 662–673)

662. **`core/providers/jmap/test_client_edge_cases.py::test_default_factory_configures_mail_event_types`**
    The production jmapc factory requests Email and EmailDelivery events.

663. **`core/providers/jmap/test_client_edge_cases.py::test_event_stream_connects_once_and_returns_the_backend_stream`**
    Event stream access reuses one authenticated JMAP session.

664. **`core/providers/jmap/test_client_edge_cases.py::test_event_stream_wraps_backend_stream_failures`**
    EventSource opening failures remain inside `JmapError`.

665. **`core/providers/jmap/test_push.py::test_wait_sleeps_using_backoff_and_reports_a_disconnect`**
    Stream failure uses the first configured delay before handing control
    to fallback.

666. **`core/providers/jmap/test_push.py::test_next_wait_retries_push_and_resets_backoff_after_recovery`**
    The next poll retries push and a relevant event resets the attempt
    counter.

667. **`core/providers/jmap/test_push.py::test_wait_rejects_an_empty_reconnect_schedule`**
    Invalid retry configuration fails through the push boundary.

668. **`core/providers/jmap/test_push.py::test_wait_ignores_events_with_malformed_state_data`**
    Malformed event data is ignored until a relevant event arrives.

669. **`core/sources/test_checkpoint_fallback.py::test_checkpoint_fallback_uses_polling_after_push_disconnect`**
    A transient push failure returns the polling source's candidate batch.

670. **`core/sources/test_checkpoint_fallback.py::test_checkpoint_fallback_retries_push_on_the_next_poll`**
    Fallback does not latch permanently; recovered push is tried again.

671. **`core/sources/test_checkpoint_fallback.py::test_checkpoint_fallback_does_not_hide_unconfigured_failures`**
    Failures outside the configured transient set propagate.

672. **`core/sources/test_checkpoint_fallback.py::test_checkpoint_fallback_exposes_the_plain_source_view`**
    Checkpoint fallback remains usable through the ordinary Source method.

673. **`core/sources/test_checkpoint_fallback.py::test_checkpoint_fallback_propagates_secondary_failures`**
    Polling failures are not hidden after push has already disconnected.

### M6 SecretSpec keyring enrollment follow-up (tests 674–683)

674. **`core/test_secret_store.py::test_keyring_service_name_matches_secretspec_scope`**
     Enrollment derives the exact `secretspec/{project}/{profile}/{key}`
     service path consumed by the native keyring provider.

675. **`core/test_secret_store.py::test_store_secret_uses_current_user_as_keyring_account`**
     A secret is sent to the OS keyring with the current user as account,
     never to a file or environment variable.

676. **`core/test_secret_store.py::test_store_secret_wraps_keyring_failures_without_echoing_value`**
     Backend failures cross the boundary as `SecretStoreError` without
     including the credential in the error.

677. **`cli/commands/test_secrets.py::test_enroll_prompts_for_both_credentials_without_printing_values`**
     The enrollment command prompts for both required names, stores them,
     and does not echo either value.

678. **`cli/commands/test_secrets.py::test_enroll_reports_keyring_failure_without_traceback`**
     A keyring failure produces a clean CLI failure rather than a traceback.

679. **`core/test_secret_store.py::test_keyring_service_name_rejects_a_malformed_manifest`**
     Malformed manifests fail before any keyring write is attempted.

680. **`core/test_secret_store.py::test_store_secret_rejects_an_empty_value`**
     Empty credentials are rejected at the storage boundary.

681. **`core/test_secrets.py::test_resolve_secrets_wraps_keyring_backend_failure`**
     OS keyring read failures become one catchable `SecretsError`.

682. **`core/test_secrets.py::test_resolve_secrets_rejects_an_invalid_keyring_declaration`**
     Non-table SecretSpec declarations fail closed.

683. **`core/test_secrets.py::test_resolve_secrets_rejects_a_missing_keyring_profile`**
     An unknown profile cannot silently fall back to the default profile.

### M6 doctor failure-boundary follow-up (tests 684–692)

684. **`cli/commands/test_doctor_unexpected_failures.py::test_secrets_check_catches_unexpected_failure`**
     An unexpected secret backend error becomes a single-line failed check.

685. **`cli/commands/test_doctor_unexpected_failures.py::test_config_check_catches_unexpected_failure`**
     Unexpected configuration failures are caught and summarized without
     validation-detail leakage.

686. **`cli/commands/test_doctor_unexpected_failures.py::test_backend_checks_catch_unexpected_failure[provider]`**
     Provider construction failures are contained at the doctor boundary.

687. **`cli/commands/test_doctor_unexpected_failures.py::test_backend_checks_catch_unexpected_failure[LLM client]`**
     LLM construction failures are contained at the doctor boundary.

688. **`cli/commands/test_doctor_unexpected_failures.py::test_backend_checks_catch_unexpected_failure[alerter]`**
     Alerter construction failures are contained at the doctor boundary.

689. **`cli/commands/test_doctor_unexpected_failures.py::test_rules_check_catches_unexpected_failure`**
     Rules loading failures are caught and reported as one line.

690. **`cli/commands/test_doctor_unexpected_failures.py::test_classifier_check_catches_unexpected_failure`**
     Classifier registry failures are caught and reported as one line.

691. **`cli/commands/test_doctor_unexpected_failures.py::test_jmap_check_catches_unexpected_failure`**
     JMAP connectivity failures are caught separately from the planned
     M1 not-implemented result.

692. **`cli/commands/test_doctor_unexpected_failures.py::test_systemd_check_catches_unexpected_failure`**
     Systemd inspection failures are caught and reported as one line.

693. **`cli/commands/test_doctor_unexpected_failures.py::test_jmap_check_connects_checkpointed_provider`**
     Doctor calls `account_id()` on a configured checkpoint-capable
     provider and reports the connected account.

694. **`cli/commands/test_doctor_unexpected_failures.py::test_jmap_check_rejects_an_empty_account_id`**
     A provider that cannot identify an account fails the connectivity check.

695. **`cli/commands/test_config.py::test_config_init_writes_a_valid_jmap_setup_without_credentials`**
     Initialization creates a JMAP/LiteLLM configuration and disabled
     starter rules without writing secret values.

696. **`cli/commands/test_config.py::test_config_init_refuses_to_overwrite_existing_config`**
     Existing configuration is protected unless `--force` is explicit.

697. **`cli/commands/test_config.py::test_config_init_force_replaces_existing_config`**
     Explicit force replacement writes the requested model and removes the
     old configuration.

698. **`core/config/test_paths.py::test_runtime_config_overrides_are_explicit_and_resettable`**
      Launch-time config and SecretSpec path overrides are process-local and
      resettable.

699. **`core/alerts/test_smtp.py::test_smtp_alerter_sends_urgency_and_url`**
      SMTP alerts preserve urgency, body, and URL context while authenticating
      through STARTTLS.

700. **`core/alerts/test_smtp.py::test_smtp_alerter_can_send_to_local_plaintext_harness`**
      The local acceptance profile can disable TLS and authentication without
      changing the alert contract.

701. **`core/alerts/test_smtp_edge_cases.py::test_smtp_username_requires_password`**
      Authenticated SMTP configuration fails closed before opening a relay
      connection when its password is missing.

702. **`daemon/test_loop.py::test_run_daemon_observe_mode_never_enters_tier2`**
      Observe mode processes an escalation without entering Tier 2, creating
      a draft, or invoking a provider action path.

703. **`core/providers/jmap/test_client.py::test_list_mailboxes_returns_names_from_mailbox_get`**
      Read-only mailbox listing uses the authenticated Mailbox/get response.

704. **`core/providers/jmap/test_client.py::test_get_thread_context_reads_prior_subject_and_sent_state`**
      Thread context uses Thread/get and Email/get to identify prior subject
      and whether Spork has already replied.

705. **`core/providers/jmap/test_client.py::test_get_message_fetches_and_normalizes_one_email`**
      Read-only message lookup returns the same normalized shape as new-mail
      acquisition.

706. **`core/pipeline/test_default.py::test_escalation_remains_retryable_until_tier2_completes`**
      Tier 1 leaves an escalation unprocessed so Tier 2 or a later retry can
      claim terminal ownership.

### M7a mutation & fuzz testing hardening (tests 707–730)

Property-based (Hypothesis) tests for the four modules docs/DESIGN.md
§16.1 scopes, plus deterministic tests for the real gaps an initial
`mutmut` baseline run surfaced in those same modules (§16.2,
mutation/README.md) — see that file for the full mutant-by-mutant
accounting. Several pre-existing tests were also strengthened in
place rather than replaced (`pytest.raises(..., match=...)` widened to
exact string equality in `test_engine_edge_cases.py`,
`test_executor.py`, `test_executor_edge_cases.py`, and
`test_combine_edge_cases.py`; `test_classifier_is_invoked_at_most_once_per_evaluation`
now also asserts on which message the classifier received) — those
don't get new numbered entries here since they're the same test
functions, just harder to fool.

707. **`core/rules/test_engine_fuzz.py::test_first_enabled_always_true_rule_wins_regardless_of_count`**
      For any Hypothesis-generated enabled/disabled pattern over
      unconditionally-matching rules, the winner is always the earliest
      enabled one.

708. **`core/rules/test_engine_fuzz.py::test_empty_conditions_never_match_any_generated_message`**
      Any number of all-default `Condition()` rules never match, for any
      generated message.

709. **`core/rules/test_engine_fuzz.py::test_from_domain_in_matches_iff_domain_is_a_member`**
      `from_domain_in` matches exactly when the message's domain is a
      member of the generated list.

710. **`core/rules/test_engine_fuzz.py::test_from_in_matches_iff_address_is_a_member`**
      Same membership property as above for the exact-address condition
      kind.

711. **`core/rules/test_engine_fuzz.py::test_disabled_rules_are_always_skipped_regardless_of_condition`**
      Every rule disabled — even ones that unconditionally match — always
      falls through to the default policy.

712. **`core/actions/test_executor_fuzz.py::test_escalate_always_rejected_and_never_reaches_the_applier`**
      Any generated escalate Action is rejected outright and never reaches
      the applier.

713. **`core/actions/test_executor_fuzz.py::test_move_or_tag_without_mailbox_always_rejected`**
      Any generated move/tag Action with `mailbox=None` is rejected.

714. **`core/actions/test_executor_fuzz.py::test_move_or_tag_with_a_mailbox_always_reaches_the_applier_unchanged`**
      Any generated move/tag Action carrying a mailbox reaches `apply()`
      exactly once, unchanged.

715. **`core/actions/test_executor_fuzz.py::test_ignore_is_always_a_pure_no_op`**
      Any generated ignore Action never reaches the applier and never
      raises.

716. **`core/actions/test_executor_fuzz.py::test_execute_never_both_raises_and_calls_the_applier`**
      Across every generated Action, raising and applying are mutually
      exclusive outcomes.

717. **`core/dispatch/test_combine_fuzz.py::test_primary_combiner_returns_exactly_the_named_targets_success_or_raises`**
      `PrimaryCombiner`'s decision is entirely a function of the named
      target's own outcome, for any generated dispatch map.

718. **`core/dispatch/test_combine_fuzz.py::test_highest_confidence_combiner_picks_the_max_confidence_success_or_raises`**
      `HighestConfidenceCombiner` either raises (no successes) or returns a
      result tying the true maximum confidence among successes.

719. **`core/dispatch/test_combine_fuzz.py::test_highest_confidence_tie_break_favors_earlier_insertion_order`**
      A tie at any generated confidence value resolves to the
      earlier-inserted target, generalizing the fixed-0.5 example test.

720. **`core/dispatch/test_combine_fuzz.py::test_dispatching_classifier_matches_manual_dispatch_then_combine`**
      `DispatchingClassifier.classify()` is exactly dispatch-then-combine
      for any generated set of successful targets.

721. **`core/pipeline/test_default_fuzz.py::test_process_message_never_applies_a_terminal_action_twice`**
      For any generated message and terminal action type, a second
      `process_message()` call never re-applies.

722. **`core/pipeline/test_default_fuzz.py::test_escalate_verdict_never_marks_processed_or_applies`**
      For any generated message, an escalate verdict is never marked
      processed and never reaches the applier.

723. **`core/pipeline/test_default_fuzz.py::test_non_escalate_verdict_always_marks_processed`**
      The complement of the above: every terminal verdict marks the
      message processed, for any generated message/action type.

724. **`core/pipeline/test_default_fuzz.py::test_force_bypasses_idempotency_on_every_call`**
      `force=True` re-evaluates and re-applies on every call, even a
      second time on the same message.

725. **`core/pipeline/test_default_fuzz.py::test_process_message_verdict_matches_the_rule_engines_own_evaluate`**
      `process_message()`'s routing never diverges from calling
      `rules.engine.evaluate()` directly with the same inputs, for any
      generated message and rule list.

726. **`core/dispatch/test_combine_edge_cases.py::test_dispatching_classifier_forwards_the_actual_message_to_dispatch`**
      `classify(message)` hands that exact message to the dispatcher, not
      some other value — closes a real mutmut survivor
      (`dispatcher.dispatch(None)`).

727. **`core/dispatch/test_combine_edge_cases.py::test_highest_confidence_combiner_treats_no_scores_as_exactly_zero_confidence`**
      A target reporting no scores is exactly 0.0 confidence — beats a
      real negative score, loses to a real positive one — pinned
      deterministically after a property test's kill status flickered
      between runs on this same mutant.

728. **`core/pipeline/test_default_edge_cases.py::test_process_message_uses_the_injected_correlation_id_generator`**
      The `new_correlation_id=` callable actually reaches
      `CorrelationIdFilter` — closes a real mutmut survivor (the forward
      silently dropped).

729. **`core/pipeline/test_default_edge_cases.py::test_process_message_uses_the_injected_classifier`**
      The `classifier=` argument actually reaches rule evaluation — closes
      a real mutmut survivor (`classifier=None`/dropped entirely).

730. **`core/pipeline/test_default_edge_cases.py::test_build_default_pipeline_defaults_to_not_forcing`**
      Calling `build_default_pipeline()` without `force=` still includes
      the idempotency gate — its own default was otherwise never
      exercised, since `process_message()` always passes it explicitly.
### tests/core/providers/jmap — mitmproxy fault-injection harness (M1c)

`tests/support/jmap_mitm.py` drives the real, unmodified production
`client_factory` (real `jmapc.Client`) through a local in-process
mitmproxy instance instead of an injected jmapc-shaped fake, so these
tests exercise `JmapClient`/`JmapPushTrigger` against genuine transport
faults. Nothing is ever forwarded to a real upstream host — the addon
always answers locally, from a canned response or a synthetic fault.

731. **`test_mitm_fault_injection.py::test_client_round_trips_through_real_jmapc_over_the_harness_with_no_live_network`**
     The production `client_factory`, driven over the harness, completes
     session discovery and a baseline fetch with zero requests forwarded
     upstream.

732. **`test_mitm_fault_injection.py::test_truncated_response_body_surfaces_as_jmap_error`**
     A response body cut short over the real transport still raises
     `JmapError`, not an unhandled `JSONDecodeError`.

733. **`test_mitm_fault_injection.py::test_eventsource_mid_stream_disconnect_raises_push_disconnected_error_after_backoff`**
     A real EventSource stream ending with no events reaches
     `JmapPushDisconnectedError` after one backoff sleep. Building this
     test found that `jmapc`'s `sseclient` transport silently retries a
     clean stream end on its own fixed 3s timer before `JmapPushTrigger`
     ever sees an exception — the harness models a disconnect whose
     *reconnect* attempt also fails, since that's what actually reaches
     spork's own backoff (see docs/ROADMAP.md M1's EventSource item).

734. **`test_mitm_fault_injection.py::test_synthetic_429_with_retry_after_surfaces_as_jmap_error`**
     A real HTTP 429 with `Retry-After` fails closed through `JmapError`
     rather than an unhandled `requests.HTTPError`.

735. **`test_mitm_fault_injection.py::test_added_latency_does_not_change_the_returned_data`**
     A deliberately slow-but-complete response still parses correctly —
     the harness's latency fault doesn't itself corrupt what it delays.

736. **`test_mitm_fault_injection.py::test_harness_refuses_to_forward_a_request_upstream_without_explicit_opt_in`**
     No canned response configured means every request fails closed
     locally; `requests_forwarded_upstream()` stays 0 — the harness's
     core safety property ahead of ever pointing it at a live account.

### tests/core/llm — exclude escalate from the Tier 2 tool schema (M3, live-corpus finding)

Fix for the finding recorded under M3's confidence-band item: a live
Claude call chose `suggested_action.type = "escalate"` for ambiguous
mail, which `Verdict`'s own validator rejects. `verdict_tool_schema()`
now strips it from what the model is offered.

737. **`test_prompt.py::test_build_prompt_forces_one_deliver_verdict_tool_with_the_verdict_schema`**
     (updated) The tool's `parameters` equal `verdict_tool_schema()`,
     not the raw, unmodified `Verdict.model_json_schema()`.

738. **`test_prompt.py::test_verdict_tool_schema_excludes_escalate_from_suggested_action_type`**
     `suggested_action.type`'s enum is exactly `{"move", "tag",
     "ignore"}` — `"escalate"` is never offered to the model.

739. **`test_prompt.py::test_verdict_tool_schema_leaves_every_other_field_unchanged`**
     Every other part of the schema is byte-for-byte identical to
     `Verdict.model_json_schema()` — the fix is a single-field edit,
     not a schema rewrite.

### tests/core/providers/jmap — query_messages() backfill read path (M8)

740. **`test_query.py::test_query_messages_returns_a_page_of_normalized_messages_and_position`**
     A two-message `Email/query`+`Email/get` page normalizes correctly
     and reports `position`/`total`/`has_more` from the response.

741. **`test_query.py::test_query_messages_unread_only_sets_the_not_keyword_filter`**
     `unread_only=True` sends `Email/query` with `filter.not_keyword ==
     "$seen"` and `filter.in_mailbox` set to the resolved Inbox id.

742. **`test_query.py::test_query_messages_has_more_true_when_a_later_page_remains`**
     `position=0, limit=1` against a `total=5` response reports
     `has_more=True` — the caller can page without re-deriving the
     arithmetic itself.

743. **`test_query.py::test_query_messages_with_no_matching_ids_skips_the_get_call`**
     An empty `Email/query` result never issues an `Email/get` call —
     only `MailboxGet` and `EmailQuery` appear in the request log.

744. **`test_query.py::test_query_messages_passes_the_requested_position_and_limit`**
     `position=20, limit=10` are forwarded to `Email/query` exactly,
     unmodified.

### tests/core/providers — BackfillPage/BackfillProvider capability (M8)

745. **`jmap/test_backfill.py::test_provider_satisfies_the_backfill_provider_protocol`**
     `JmapProvider` structurally satisfies `BackfillProvider`
     (`isinstance` check, `@runtime_checkable`).

746. **`jmap/test_backfill.py::test_query_messages_delegates_to_the_client_and_wraps_the_result`**
     `JmapProvider.query_messages()` forwards every argument to the
     underlying `JmapClient` and wraps its `JmapQueryResult` as the
     backend-agnostic `BackfillPage`.

747. **`jmap/test_backfill.py::test_query_messages_uses_documented_defaults`**
     Called with no arguments, the client sees
     `unread_only=False, position=0, limit=50`.

748. **`file/test_backfill.py::test_provider_satisfies_the_backfill_provider_protocol`**
     `FileProvider` structurally satisfies `BackfillProvider` too — a
     second, real implementation, same "the abstraction generalizes"
     proof `Provider` itself already has (M1b).

749. **`file/test_backfill.py::test_query_messages_returns_a_windowed_page`**
     A 5-message fixture file, `position=0, limit=2`, returns the
     first two messages with `total=5, has_more=True`.

750. **`file/test_backfill.py::test_query_messages_has_more_false_on_the_last_page`**
     `position=4, limit=2` against 5 messages returns the last one with
     `has_more=False`.

751. **`file/test_backfill.py::test_query_messages_unread_only_is_accepted_but_has_no_filter_to_apply`**
     `unread_only=True` still returns every message — a fixture file
     has no "seen" state to filter on, documented rather than silently
     misleading.

### tests/cli/commands — spork backfill (M8)

752. **`test_backfill.py::test_backfill_help_works`**
     `spork backfill --help` exits 0 with usage text.

753. **`test_backfill.py::test_backfill_with_no_config_produces_a_clean_error`**
     No `config.toml` present: exit 1, `Error:` on stderr, no
     traceback.

754. **`test_backfill.py::test_backfill_processes_every_message_through_tier1`**
     A 3-message `FileProvider` fixture: every message ends up in
     `processed_messages` after one run.

755. **`test_backfill.py::test_backfill_escalates_through_tier2_when_rules_say_so`**
     A message an `always`-matching catch-all rule escalates gets a
     real Tier 2 verdict via `RecordedLLMClient`, recorded as
     `tier_reached="tier2"`.

756. **`test_backfill.py::test_backfill_respects_the_limit_option`**
     5 messages available, `--limit 2`: exactly 2 end up processed.

757. **`test_backfill.py::test_backfill_writes_a_control_plane_audit_entry`**
     One `backfill_triggered` audit entry per run, same pattern as
     `reclassify_triggered`.

758. **`test_backfill_edge_cases.py::test_backfill_never_reprocesses_a_message_already_marked_processed`**
     Running backfill twice: the second run reports 0 Tier 1 actions
     and 0 Tier 2 verdicts, and `processed_messages` still has exactly
     3 rows, not 6 — `process_message()`'s idempotency gate is what
     M8's dedup guarantee actually rests on.

759. **`test_backfill_edge_cases.py::test_backfill_reports_a_clean_error_for_a_provider_without_the_capability`**
     A provider with no `query_messages()` (`NoBackfillProvider`,
     `tests/support/`): exit 1, `"does not support backfill"` on
     stderr, no traceback.

760. **`test_backfill_edge_cases.py::test_backfill_with_a_page_size_larger_than_the_limit_still_stops_at_the_limit`**
     `--limit 1 --page-size 50` against 5 available messages still
     processes exactly 1.

### tests/core/providers/jmap — recorded flow replay (M1c)

761. **`test_flow_replay.py::test_baseline_fetch_replays_from_the_recorded_flow_not_a_canned_response`**
     With zero canned responses configured, `jmap_mitm_harness(replay_flows=[...])`
     answers `JmapClient.connect()`/`fetch_new_messages()` entirely
     from the real recorded flow — the real captured account id and
     baseline cursor come back. Skips (not fails) when the gitignored
     flow file isn't present on this clone.

### tests/core/providers/jmap — pagination drift fix (PR #20 review finding)

Inserted here out of file order (sits physically alongside 740–744 in
`test_query.py`) but numbered at the end per this doc's stable-
numbering convention.

762. **`test_query.py::test_query_messages_next_position_accounts_for_ids_not_returned_by_get`**
     `Email/query` matches 3 ids but `Email/get` only returns 2 (a
     message deleted/moved in between) — `next_position` still
     advances by 3 (the actual match count) and `has_more` stays
     correct, instead of drifting from the post-normalize message
     count.

### tests/cli/commands — Tier 2 capability build frequency fix (PR #20 review finding)

763. **`test_backfill_edge_cases.py::test_backfill_builds_tier2_provider_capabilities_once_per_run_not_per_message`**
     3 escalating messages, `CountingFileProvider`
     (`tests/support/counting_provider.py`): `build_thread_history_reader()`/
     `build_mailbox_lister()`/`build_draft_creator()` are each called
     exactly once for the whole run, not once per escalation.

### tests/cli/commands — --limit/--page-size positivity (PR #20 review finding)

764. **`test_backfill_edge_cases.py::test_backfill_rejects_a_non_positive_limit`**
     `--limit 0` exits non-zero with a clean usage error, no traceback
     — previously ran successfully and reported "0 messages processed".

765. **`test_backfill_edge_cases.py::test_backfill_rejects_a_non_positive_page_size`**
     `--page-size 0` exits non-zero with a clean usage error, no
     traceback — same previous silent-no-op gap.

### tests/core/alerts — DesktopAlerter (M4)

766. **`test_desktop.py::test_desktop_alerter_calls_notify_send_with_title_body_and_urgency`**
     `notify-send -u critical "Needs review" "Please inspect"` — the
     exact argv, urgency passed straight through as `-u`.

767. **`test_desktop.py::test_desktop_alerter_appends_the_url_to_the_body`**
     A given `url` is appended to the message body, same convention
     `SmtpAlerter` already uses.

768. **`test_desktop.py::test_desktop_alerter_falls_back_to_logging_when_notify_send_is_missing`**
     `notify-send` not installed (`FileNotFoundError`) — falls back to
     the injected `Alerter`, never raises.

769. **`test_desktop.py::test_desktop_alerter_falls_back_to_logging_when_notify_send_fails`**
     A non-zero exit (`CalledProcessError` — e.g. no session D-Bus bus,
     a headless/SSH-only login) — same fallback, never raises.

770. **`test_desktop.py::test_desktop_alerter_defaults_to_a_real_logging_alerter_fallback`**
     No explicit `fallback=` given: still degrades gracefully using a
     real `LoggingAlerter`, not losing the alert entirely.

### tests/core/pipeline/tier2 — poison-message resiliency (`escalate_message_or_quarantine`)

771. **`test_escalate.py::test_escalate_message_or_quarantine_passes_through_a_normal_verdict`**
     The common path is unaffected: a valid, in-set verdict comes back
     exactly as `escalate_message()` itself would return it.

772. **`test_escalate.py::test_escalate_message_or_quarantine_still_returns_none_on_budget_exhausted`**
     `None` (budget exhausted) and `QuarantinedMessage` are distinct
     signals — a caller must be able to tell them apart.

773. **`test_escalate.py::test_escalate_message_or_quarantine_quarantines_an_out_of_set_category`**
     `VerdictValidationError` (a category outside `allowed_categories`)
     is quarantined, not raised: the message is marked processed
     (never retried forever, never re-burning budget) and a
     `tier2_quarantined` audit entry is written.

774. **`test_escalate.py::test_escalate_message_or_quarantine_quarantines_a_malformed_action`**
     `ActionExecutionError` (a `move` with no mailbox — a shape check
     `Verdict`'s own pydantic model doesn't catch, since `Action.mailbox`
     is optional) is quarantined the same way.

775. **`test_escalate.py::test_escalate_message_or_quarantine_quarantines_a_failed_llm_call`**
     `LiteLLMClientError` (the live call itself failed) is quarantined
     the same way as a malformed-but-successful response.

776. **`test_escalate.py::test_escalate_message_or_quarantine_fires_a_critical_alert`**
     A quarantined verdict fires exactly one `critical`-urgency alert
     through the injected `Alerter`.

777. **`test_escalate.py::test_escalate_message_or_quarantine_does_not_catch_a_real_pipeline_bug`**
     A `MissingMetaError` (a genuine wiring bug, not a bad model
     response) is deliberately not in `QUARANTINABLE_ERRORS` — it still
     propagates rather than being silently absorbed as if it were a
     quarantinable model-output failure.

### tests/cli/commands — poison-message resiliency wired into `reclassify`/`backfill`

778. **`test_reclassify_edge_cases.py::test_reclassify_quarantines_instead_of_crashing_on_an_out_of_set_category`**
     `spork reclassify` on a message whose Tier 2 verdict names an
     out-of-set category exits 0, reports `"...quarantined..."` on
     stdout, no traceback — instead of the prior uncaught
     `VerdictValidationError` crashing the command.

779. **`test_backfill_edge_cases.py::test_backfill_quarantines_instead_of_crashing_on_an_out_of_set_category`**
     Same fix, `spork backfill`: an out-of-set category is quarantined
     (counted separately from Tier 2 verdicts, reported as
     `"1 quarantined"`, `StateDB`-marked) instead of crashing the run.

### tests/core/llm, tests/core/pipeline/tier2 — category taxonomy sent to the model + Verdict.metadata (M3 follow-up)

780. **`test_base.py::test_verdict_request_holds_the_assembled_prompt_inputs`** (updated)
     `VerdictRequest.available_categories` round-trips like every
     other field.

781. **`test_base.py::test_verdict_metadata_defaults_to_an_empty_dict_when_omitted`**
     `metadata` is optional freeform extraction — omitting it from the
     response is valid, same convention as `draft_reply`.

782. **`test_base.py::test_verdict_accepts_freeform_metadata_key_value_pairs`**
     A model may surface arbitrary extracted data (dates, order
     numbers, reference ids) via `metadata` — not a closed set, unlike
     `category`/`suggested_action.mailbox`.

783. **`test_base_edge_cases.py::test_verdict_rejects_a_non_string_metadata_value`**
     `metadata` is `dict[str, str]`, not `dict[str, Any]` — an int
     value is a validation failure. Passes against the existing
     implementation with no code change: pydantic's default strict
     string coercion already enforces it.

784. **`test_prompt.py::test_build_prompt_contains_the_complete_message_context`** (updated)
     `available_categories` now appears in the exact user-message JSON
     sent upstream, alongside `available_mailboxes`; the system
     prompt's "Choose category and mailbox only from the values
     supplied" claim is now literally true. System message also gained
     a sentence describing the optional `metadata` field.

785. **`test_modules.py::test_build_verdict_request_filter_cleans_the_body_and_builds_the_request`** (updated)
     `BuildVerdictRequestFilter(available_categories, max_body_chars)`
     threads `available_categories` into the `VerdictRequest` it
     builds — a constructor argument (deployment config), not a
     `Tier2Meta` field (per-message Provider read), same relationship
     `max_body_chars` already has to this filter.

786. **`test_default.py::test_process_tier2_message_sends_allowed_categories_to_the_model`**
     `build_tier2_pipeline()` wires `TieringConfig.allowed_categories`
     into the actual prompt via `BuildVerdictRequestFilter`, not just
     `ValidateVerdictFilter`'s post-hoc check — a recording `LLMClient`
     spy asserts the exact `VerdictRequest.available_categories` it
     received.

### tests/core/context — ContextProvider, the read-only knowledgebase interface (item 3, docs/DESIGN.md §10.8)

787. **`test_base.py::test_context_snippet_holds_a_source_and_text`**
     `ContextSnippet(source, text)` round-trips both fields.

788. **`test_base.py::test_context_result_holds_zero_or_more_snippets`**
     `ContextResult.snippets` is an ordered tuple of however many
     `ContextSnippet`s a backend returned.

789. **`test_base.py::test_context_result_empty_is_a_valid_no_context_answer`**
     `ContextResult(snippets=())` — "no relevant context found" is a
     real, first-class answer, not an error or a missing field.

790. **`test_base.py::test_a_plain_class_with_get_context_structurally_satisfies_contextprovider`**
     Protocol-based DI, same as every other backend seam in this
     codebase — nothing needs to import or inherit from
     `ContextProvider` to satisfy it.

791. **`test_loader.py::test_load_context_provider_imports_and_instantiates_by_spec`**
     A well-formed `"module:ClassName"` spec resolves to an instance —
     mirrors `test_load_llm_client_imports_and_instantiates_by_spec`.

792. **`test_loader.py::test_load_context_provider_passes_through_constructor_kwargs`**
     Extra kwargs reach the provider's constructor unmodified.

793. **`test_loader.py::test_load_context_provider_raises_for_malformed_spec`**
     A spec with no `':'` separator is rejected before any import is
     attempted.

794. **`test_loader.py::test_load_context_provider_raises_for_an_unimportable_module`**
     An unimportable module name fails loudly via
     `ContextProviderLoadError`, not a raw `ImportError`.

795. **`test_loader.py::test_load_context_provider_raises_for_a_missing_class`**
     A real module but a nonexistent class name fails loudly via
     `ContextProviderLoadError`, not a raw `AttributeError`.

796. **`test_loader_edge_cases.py::test_load_context_provider_raises_when_construction_fails`**
     A provider whose constructor rejects the given kwargs fails
     loudly rather than a raw `TypeError` leaking through unwrapped.

797. **`clients/test_null.py::test_null_context_provider_always_returns_an_empty_result`**
     `NullContextProvider` — the real "no knowledgebase configured"
     default — always answers `ContextResult(snippets=())` regardless
     of the message.

798. **`clients/test_null.py::test_null_context_provider_takes_no_constructor_arguments`**
     No config, no kwargs to get wrong — the safe default a minimal
     config.toml (no `[context]` table) resolves to.

799. **`clients/test_vault.py::test_get_context_raises_not_implemented_yet`**
     `MarkdownVaultContextProvider.get_context()` raises
     `NotImplementedError` naming `docs/ROADMAP.md` — a settled-shape
     stub, same pattern `JmapClient` uses, but blocked on an undecided
     retrieval-algorithm design question rather than a live call.

800. **`clients/test_vault.py::test_constructor_settles_the_real_shape_without_reading_the_vault`**
     Constructing one doesn't require the vault directory to exist yet
     or do any I/O — same "settle the shape, defer the behavior"
     split `JmapClient`'s constructor makes.

### tests/core/context/clients/entities — EntityContextProvider, a structured knowledge base backend (M9 prototype)

Inserted here out of file order (sits physically alongside 797–800 as
a third `context/clients` backend) but numbered at the end per this
doc's stable-numbering convention.

820. **`test_data.py::test_load_entity_data_parses_companies_services_and_people`**
     A well-formed companies/services/people fixture parses into
     `Company`/`Service`/`Person` records, each field preserved as
     authored.

821. **`test_data.py::test_load_entity_data_defaults_missing_sections_to_empty`**
     A fixture with only `"companies"` is valid — `"services"`/`"people"`
     are optional sections, not required ones.

822. **`test_provider.py::test_lookup_domain_returns_the_operating_company`**
     `EntityContextProvider.lookup_domain()` resolves a tracked domain
     to the company known to operate it.

823. **`test_provider.py::test_lookup_company_returns_its_domains_and_services`**
     `lookup_company()` returns the domains it operates and the
     services it provides, exactly as authored in the fixture.

824. **`test_provider.py::test_lookup_service_aggregates_providers_across_companies`**
     A service several companies list independently (e.g. both Gandi
     and Cloudflare offering "DNS hosting") comes back as one
     `Service` record naming every provider — computed by the
     backend, not stored redundantly in the fixture.

825. **`test_provider.py::test_lookup_person_returns_their_affiliated_company`**
     `lookup_person()` resolves a tracked person (by email) to their
     affiliated company.

826. **`test_provider.py::test_get_context_returns_a_snippet_for_a_known_sender_and_empty_for_unknown`**
     The whole point of this backend: `get_context()` gives a
     recognized sender's domain a real `ContextSnippet` naming its
     company, and an unrecognized sender an empty `ContextResult` —
     not an error either way.

827. **`test_data_edge_cases.py::test_load_entity_data_raises_for_a_missing_file`**
     A nonexistent fixture path is a clear `EntityDataLoadError`, not a
     raw `FileNotFoundError`.

828. **`test_data_edge_cases.py::test_load_entity_data_raises_for_malformed_json`**
     Broken JSON syntax is a clear `EntityDataLoadError`, not a raw
     `json.JSONDecodeError` leaking through unwrapped.

829. **`test_data_edge_cases.py::test_load_entity_data_raises_for_non_object_top_level`**
     A file whose top level isn't a JSON object (e.g. a bare array) is
     a clear `EntityDataLoadError`, not an `AttributeError` from
     calling `.get()` on the wrong type further down.

830. **`test_data_edge_cases.py::test_load_entity_data_raises_when_a_company_entry_is_not_an_object`**
     A `"companies"` entry that isn't a JSON object (e.g. a bare
     string) is rejected before any field is read.

831. **`test_data_edge_cases.py::test_load_entity_data_raises_when_a_company_is_missing_its_name`**
     A company entry missing the required `"name"` field is a clear
     `EntityDataLoadError` naming which entry.

832. **`test_data_edge_cases.py::test_load_entity_data_raises_when_a_service_is_missing_its_name`**
     Same missing-required-field guarantee for a standalone `"services"`
     entry.

833. **`test_data_edge_cases.py::test_load_entity_data_raises_when_a_person_is_missing_its_name`**
     Same missing-required-field guarantee for a `"people"` entry.

834. **`test_provider_edge_cases.py::test_lookup_domain_returns_none_for_an_unknown_domain`**
     An untracked domain is `None`, not an error — the overwhelmingly
     common case for a hand-curated fixture.

835. **`test_provider_edge_cases.py::test_lookup_company_returns_none_for_an_unknown_company`**
     Same not-found contract for `lookup_company()`.

836. **`test_provider_edge_cases.py::test_lookup_service_returns_none_for_an_unknown_service`**
     Same not-found contract for `lookup_service()`.

837. **`test_provider_edge_cases.py::test_lookup_person_returns_none_for_an_unknown_person`**
     Same not-found contract for `lookup_person()`.

838. **`test_provider_edge_cases.py::test_lookups_are_case_insensitive_on_the_key`**
     `"GANDI.COM"`/`"gandi"`/`"dns hosting"` all resolve to the same
     records; the record returned keeps its original fixture casing —
     only the lookup key is folded.

839. **`test_provider_edge_cases.py::test_lookup_person_falls_back_to_name_when_no_email_matches`**
     A person with no `"email"` in the fixture is still resolvable by
     name.

840. **`test_provider_edge_cases.py::test_lookup_service_includes_category_only_entries_with_no_provider_yet`**
     A standalone `"services"` entry's `category` and its
     `provided_by` list are independent facts — a service can be
     categorized before any company is recorded as providing it.

841. **`test_provider_edge_cases.py::test_get_context_includes_a_person_snippet_when_the_sender_is_known`**
     A message whose exact `from_address` matches a tracked person
     gets a second `ContextSnippet` naming their affiliation, alongside
     the domain/company snippet.

### tests/core/pipeline/tier2 — context wired into the Tier 2 pipeline

801. **`test_modules.py::test_fetch_context_augment_delegates_to_the_provider_and_sets_context`**
     `FetchContextAugment` calls `context_provider.get_context(meta.message)`
     and stores the result in `meta.context` — same one-I/O-stage
     shape as `CallLLMAugment`.

802. **`test_modules.py::test_build_verdict_request_filter_requires_context_to_be_set_first`**
     `MissingMetaError` if `meta.context` isn't set — same
     ordering contract every other stage in this pipeline enforces;
     run `FetchContextAugment` first.

803. **`test_default.py::test_process_tier2_message_sends_context_snippets_to_the_model`**
     A configured `ContextProvider`'s result reaches the actual
     prompt end to end, flattened into
     `VerdictRequest.context_snippets` — the read-only knowledgebase
     seam wired through the whole pipeline, not just constructible in
     isolation.

804. **`test_default.py::test_process_tier2_message_sends_no_context_snippets_when_none_configured`**
     The default `NullContextProvider` produces an empty
     `context_snippets` tuple, not a missing field or a crash.

805. **`test_escalate.py::test_escalate_message_wires_context_provider_into_tier2`**
     `escalate_message()` threads its `context_provider` argument all
     the way to the actual prompt — same depth of wiring
     `thread_history_reader`/`mailbox_lister` already get.

### tests/core/config, tests/core — SporkConfig.context + runtime wiring

806. **`test_schema.py::test_sporkconfig_context_defaults_to_none`**
     Unset means "no knowledgebase configured" — a real, valid state,
     not a missing-field error, same convention as
     `tiering.local_classifier`.

807. **`test_schema.py::test_sporkconfig_accepts_optional_context_provider_configuration`**
     A `[context]` table round-trips into `SporkConfig.context` like
     any other `BackendSpec`.

808. **`test_runtime.py::test_build_context_provider_defaults_to_null_when_unconfigured`**
     No `[context]` table: `build_context_provider()` returns the real
     "no knowledgebase configured" backend, not `None`/a crash.

809. **`test_runtime.py::test_build_context_provider_loads_the_configured_backend`**
     A configured `[context]` spec + kwargs resolves to a real
     instance via `load_context_provider()`.

810. **`test_runtime.py::test_resolve_runtime_secrets_includes_a_configured_context_providers_secret_kwargs`**
     A `[context]` table's `secret_kwargs` count toward "does anything
     configured need SecretSpec resolved" the same way
     provider/llm/alerts already do — `context` isn't a silent fourth
     exception.

811. **`test_base.py::test_verdict_request_carries_context_snippets_from_the_knowledgebase`**
     `VerdictRequest.context_snippets` round-trips like every other
     field — the flattened `"source: text"` strings the prompt
     actually sends.

### tests/core/classify — KeywordClassifier, the default local classifier (item 4, docs/DESIGN.md §9.1)

812. **`test_keyword.py::test_keyword_classifier_picks_the_category_whose_keywords_matched`**
     A message whose subject/body contain a category's keywords is
     classified into that category.

813. **`test_keyword.py::test_keyword_classifier_matching_is_case_insensitive`**
     `"Urgent"`/`"ASAP"` match the same as their lowercase forms.

814. **`test_keyword.py::test_keyword_classifier_falls_back_to_the_default_category_when_nothing_matches`**
     A message matching no configured category's keywords gets the
     named `"uncategorized"` default, every score 0.0 — not an
     arbitrarily-chosen first category.

815. **`test_keyword.py::test_keyword_classifier_exposes_every_configured_categorys_score`**
     `scores` is an open bag exposing every configured category's
     fraction, not just the winning one — a rule or a future tuning
     pass can key off finer-grained signals.

816. **`test_keyword.py::test_keyword_classifier_accepts_a_custom_category_keyword_mapping`**
     Not hardcoded to the shipped default set — a deployment can
     supply its own vocabulary entirely via the constructor.

817. **`test_keyword.py::test_keyword_classifier_structurally_satisfies_textclassifier`**
     Protocol-based DI, same as every other backend seam in this
     codebase.

818. **`test_registration.py::test_importing_the_classify_package_registers_the_default_keyword_backend`**
     Importing `spork.core.classify` (as every real caller already
     does) is enough on its own to make `"keyword_heuristic"`
     resolvable via `registry.get()` — no extra wiring needed at any
     call site. Before this fix, nothing anywhere in the codebase ever
     called `registry.register()`, so `tiering.local_classifier` was
     completely non-functional in every real deployment.

819. **`test_keyword_edge_cases.py::test_keyword_classifier_scores_a_category_with_an_empty_keyword_list_as_zero`**
     A misconfigured category (an empty keyword tuple) never crashes
     with a divide-by-zero — it just can never win, scored 0.0 like
     any other unmatched category.

### tests/core/receipts — build_receipt_pdf() (docs/ROADMAP.md M10, docs/DESIGN.md §9.5)

842. **`test_pdf.py::test_no_attachments_produces_a_single_cover_page_with_the_tags`**
     No attachments still produces a valid one-page PDF from the cover
     content alone (subject/company/date/tags).

843. **`test_pdf.py::test_a_pdf_attachment_is_merged_page_for_page`**
     An existing PDF attachment's pages are merged into the archive
     after the cover page, not just referenced.

844. **`test_pdf.py::test_an_image_attachment_becomes_its_own_page`**
     An image attachment is scaled onto its own full page.

845. **`test_pdf.py::test_an_unrenderable_attachment_gets_a_placeholder_page_naming_it`**
     An attachment type this module can't render directly (e.g. CSV)
     becomes a named placeholder page rather than being silently
     dropped.

846. **`test_pdf.py::test_multiple_attachments_are_combined_in_input_order`**
     Cover page, then every attachment in the order given — order is
     preserved, not re-sorted.

847. **`test_pdf.py::test_result_is_exactly_one_valid_pdf_document`**
     The returned bytes parse as one coherent PDF document.

848. **`test_pdf.py::test_long_body_text_still_produces_one_document_not_a_crash`**
     A long message body paginates via reportlab's flowable layout
     instead of crashing or truncating silently.

849. **`test_pdf.py::test_missing_extraction_field_is_rejected`**
     An empty `company` or `date` raises `ValueError` — this function
     never builds an archive for a half-resolved extraction.

### tests/core/receipts — save_pdf() (M10)

850. **`test_archive.py::test_saves_bytes_to_a_deterministic_filename_under_output_dir`**
     Bytes round-trip through `save_pdf()` to a real file under
     `output_dir`.

851. **`test_archive.py::test_filename_contains_date_company_and_message_id`**
     The generated filename is sortable by date and human-identifiable
     by company/message id.

852. **`test_archive.py::test_company_with_spaces_and_punctuation_is_slugified`**
     A company name with spaces/commas produces a filesystem-safe
     slug — no raw punctuation in the saved filename.

853. **`test_archive.py::test_creates_output_dir_if_missing`**
     `output_dir` (and any missing parents) is created on demand.

854. **`test_archive.py::test_unwritable_output_dir_raises_one_wrapped_error_type`**
     A path component that's a file, not a directory, raises one
     `ReceiptArchiveError` — deterministic regardless of the running
     user's privilege level, unlike a chmod-based check (which a
     root-run suite can't exercise honestly).

855. **`test_archive.py::test_two_saves_for_the_same_message_do_not_collide`**
     Two different messages, same company/date, produce two distinct
     files — the message-id slug guarantees uniqueness.

### tests/core/state — known_receipt_senders (M10's learning system)

856. **`test_db_known_senders.py::test_get_known_sender_returns_none_when_never_learned`**
     An unrecognized domain is `None`, not an error.

857. **`test_db_known_senders.py::test_learn_known_sender_then_get_known_sender_roundtrips`**
     A learned sender's company/provenance/timestamp round-trip
     exactly.

858. **`test_db_known_senders.py::test_learn_known_sender_overwrites_a_previous_entry_for_the_same_domain`**
     Re-learning a domain (a corrected company name) replaces the old
     row rather than duplicating or erroring.

859. **`test_db_known_senders.py::test_seeded_and_learned_senders_are_both_stored_the_same_way`**
     `learned_from` ("seed" vs "tier2") is provenance only — both are
     ordinary rows, looked up identically.

860. **`test_db_known_senders.py::test_known_senders_persist_across_reconnecting_to_the_same_db_file`**
     Learned senders survive a `StateDB` reconnect, like every other
     table.

### tests/core/receipts — registry.normalize_sender_domain() (M10)

861. **`test_registry.py::test_lowercases_a_mixed_case_domain`**
     `BillING.AcmeCloud.com` → `billing.acmecloud.com`.

862. **`test_registry.py::test_strips_surrounding_whitespace`**
     Leading/trailing whitespace is removed.

863. **`test_registry.py::test_already_normalized_domain_is_unchanged`**
     Idempotent on an already-canonical domain.

864. **`test_registry.py::test_a_learned_domain_is_found_regardless_of_the_lookup_domain_casing`**
     A domain learned via one casing is found via any other — the
     real reason this function exists, proven end to end against a
     real `StateDB`.

### tests/core/receipts — extract.extract_receipt() (M10)

865. **`test_extract.py::test_known_sender_plus_date_header_produces_an_extraction`**
     A `KnownSender` hit plus a `Date` header produces a full
     extraction with no LLM involved.

866. **`test_extract.py::test_domain_lookup_is_checked_before_and_wins_over_known_sender`**
     An injected `domain_lookup` collaborator (EntityContextProvider-
     shaped, M9) is checked first and wins over a conflicting learned
     `KnownSender`.

867. **`test_extract.py::test_falls_back_to_known_sender_when_domain_lookup_has_no_match`**
     No `domain_lookup` hit falls through to the learned cache.

868. **`test_extract.py::test_domain_lookup_hit_with_no_company_falls_back_to_known_sender`**
     A tracked `Domain` with no owning company (a real, documented
     state) isn't treated as a match — falls through instead.

869. **`test_extract.py::test_no_known_sender_and_no_domain_lookup_match_declines`**
     No company resolvable anywhere declines (`None`), never guesses.

870. **`test_extract.py::test_company_resolved_but_no_date_anywhere_declines`**
     A resolvable company with no date anywhere still declines — both
     halves are required.

871. **`test_extract.py::test_falls_back_to_a_body_date_marker_when_no_date_header`**
     No `Date` header falls back to a literal body marker
     ("Invoice date:").

### tests/core/receipts — llm.RecordedReceiptExtractionClient (M10)

872. **`test_llm.py::test_extract_receipt_returns_the_recorded_extraction_for_a_matching_domain`**
     A recorded fixture entry is replayed for its `from_domain`.

873. **`test_llm.py::test_extract_receipt_picks_the_matching_domain_not_just_the_first`**
     Multiple recorded domains each resolve to their own entry.

874. **`test_llm.py::test_extract_receipt_raises_for_an_unrecorded_domain`**
     `UnrecordedReceiptExtractionError` names the domains that were
     recorded.

875. **`test_llm.py::test_missing_responses_file_raises_load_error`**
     A missing fixture file is `RecordedReceiptExtractionsLoadError`.

876. **`test_llm.py::test_malformed_json_raises_load_error`**
     Invalid JSON is the same wrapped error.

877. **`test_llm.py::test_non_object_top_level_raises_load_error`**
     A non-object top level (e.g. a JSON array) is rejected.

878. **`test_llm.py::test_entry_missing_a_required_field_raises_load_error`**
     An entry missing `company`/`date` is rejected at load time, not
     lazily on first use.

### tests/core/providers/file — attachments.load_attachments() (M10)

879. **`test_attachments.py::test_load_attachments_parses_attachments_keyed_by_message_id`**
     A fixture's base64-encoded `"attachments"` array parses into real
     `Attachment` objects, keyed by `message_id`.

880. **`test_attachments.py::test_a_message_with_no_attachments_key_maps_to_an_empty_list`**
     Every message gets an entry — `[]`, not a missing key, when it
     has no attachments.

881. **`test_attachments.py::test_a_message_can_have_multiple_attachments_in_order`**
     Order is preserved across multiple attachments.

882. **`test_attachments.py::test_missing_file_raises_load_error`**
     A missing fixture file is `AttachmentsLoadError`.

883. **`test_attachments.py::test_invalid_base64_raises_load_error`**
     Malformed base64 data is rejected at load time.

884. **`test_attachments.py::test_attachment_missing_a_required_field_raises_load_error`**
     An attachment entry missing `content_type`/`data_base64` is
     rejected.

### tests/core/providers — AttachmentFetcher/KeywordApplier capabilities (M10)

885. **`test_provider.py (file)::test_build_attachment_fetcher_returns_attachments_from_the_fixture`**
     `FileProvider.build_attachment_fetcher()` reads real attachments
     from the same fixture `build_source()` replays from.

886. **`test_provider.py (file)::test_build_attachment_fetcher_returns_empty_for_a_message_with_none`**
     A message with no attachments fetches an empty sequence.

887. **`test_provider.py (file)::test_build_keyword_applier_logs_applied_keywords`**
     Applied keywords are logged to `keywords.jsonl`, distinct from
     the actions/drafts logs.

888. **`test_provider.py (file)::test_keywords_log_defaults_next_to_the_actions_log`**
     Not passing `keywords_log_path=` still produces a real,
     inspectable log next to `actions_log_path` — same convention
     `drafts_log_path` already has.

889. **`test_client.py (jmap)::test_fetch_attachments_raises_not_implemented`**
     `JmapClient.fetch_attachments()` is a settled-shape
     `NotImplementedError`.

890. **`test_client.py (jmap)::test_apply_keywords_raises_not_implemented`**
     `JmapClient.apply_keywords()` is a settled-shape
     `NotImplementedError`, blocked on write-scoped credentials like
     `apply_action()`/`create_draft()`.

891. **`test_provider.py (jmap)::test_build_attachment_fetcher_returns_something_that_propagates_not_implemented`**
     `JmapProvider.build_attachment_fetcher()` returns an
     `AttachmentFetcher` whose call propagates the client's
     `NotImplementedError`.

892. **`test_provider.py (jmap)::test_attachment_fetcher_delegates_to_the_client_directly`**
     A real delegation to `JmapClient.fetch_attachments()`, not a
     second placeholder.

893. **`test_provider.py (jmap)::test_build_keyword_applier_returns_something_that_propagates_not_implemented`**
     Same shape for `build_keyword_applier()`.

894. **`test_provider.py (jmap)::test_keyword_applier_delegates_to_the_client_directly`**
     A real delegation to `JmapClient.apply_keywords()`.

### tests/core/actions, tests/core/pipeline — archive_receipt routing (M10)

895. **`test_executor.py::test_executor_rejects_archive_receipt_action`**
     `ActionExecutor` rejects `archive_receipt` outright — a routing
     bug if it ever reaches the plain `ActionApplier` path, mirroring
     the existing `escalate` rejection.

896. **`test_modules.py::test_rule_evaluation_selector_routes_archive_receipt_for_a_matched_rule`**
     `RuleEvaluationSelector` routes a matched `archive_receipt` rule
     to its own branch, distinct from `"terminal"`.

### tests/core/receipts — ArchiveReceiptAugment pipeline module (M10)

897. **`test_pipeline.py (receipts)::test_known_sender_is_archived_deterministically_with_no_tier2_call`**
     A known sender is tagged/archived with zero calls to the
     injected `ReceiptExtractionClient`.

898. **`test_pipeline.py (receipts)::test_unrecognized_sender_calls_tier2_once_and_learns_the_sender`**
     An unrecognized sender costs exactly one Tier 2 call, and the
     result is learned into `StateDB` afterward.

899. **`test_pipeline.py (receipts)::test_a_message_with_attachments_produces_a_multi_page_saved_pdf`**
     A real attachment produces a real multi-page saved PDF file, not
     just an in-memory assertion.

900. **`test_pipeline.py (receipts)::test_a_write_failure_propagates_instead_of_being_swallowed`**
     `ReceiptArchiveError` from an unwritable output location
     propagates out of `augment()` rather than being caught — the
     fail-open-for-retry contract.

### tests/core/config — ReceiptArchiveConfig (M10)

901. **`test_schema.py (config)::test_sporkconfig_receipt_archive_defaults_to_none`**
     Unset means the feature is off entirely, same convention as
     `context`/`tiering.local_classifier`.

902. **`test_schema.py (config)::test_sporkconfig_accepts_optional_receipt_archive_configuration`**
     A configured `[receipt_archive]` table round-trips.

903. **`test_schema.py (config)::test_receiptarchiveconfig_rejects_unknown_fields`**
     `extra="forbid"`, same convention as every other hand-edited
     config table.

### tests/core/pipeline — process_message() with receipt_archive wired (M10)

904. **`test_default.py (pipeline)::test_process_message_archives_a_matched_receipt_end_to_end`**
     A `receipt_archive=` components bundle wired into
     `process_message()` archives a matched message and marks it
     processed — the full integration, not just the standalone
     `Augment`.

905. **`test_default.py (pipeline)::test_process_message_without_receipt_archive_configured_fails_clearly`**
     Omitting `receipt_archive=` entirely on an `archive_receipt` rule
     raises `UnknownBranchError` rather than silently doing nothing.

### tests/core/llm — Verdict/tool-schema archive_receipt exclusion (M10)

906. **`test_base_edge_cases.py::test_verdict_rejects_a_suggested_action_of_archive_receipt`**
     A real gap the full pytest run caught: adding `archive_receipt`
     to `Action`'s Literal leaked it into `Verdict.suggested_action`'s
     legal values too — now rejected the same way `escalate` is
     (`verdict_tool_schema()` also excludes it from the tool's enum,
     covered by the existing `test_prompt.py` tests once updated for
     the new value).

### tests/core/receipts, tests/core/config, tests/core, tests/daemon — M10 runtime wiring (docs/ROADMAP.md M10 follow-up)

907. **`test_loader.py (receipts)::test_load_receipt_extraction_client_imports_and_instantiates_by_spec`**
     `load_receipt_extraction_client()` (mirrors `load_context_provider()`)
     imports and constructs a backend by "module:ClassName" spec.

908. **`test_loader.py (receipts)::test_load_receipt_extraction_client_passes_through_constructor_kwargs`**
     Kwargs reach the backend's constructor unchanged.

909. **`test_loader.py (receipts)::test_load_receipt_extraction_client_raises_for_malformed_spec`**
     A spec with no `:` separator is `ReceiptExtractionClientLoadError`.

910. **`test_loader.py (receipts)::test_load_receipt_extraction_client_raises_for_an_unimportable_module`**
     An unimportable module path is the same wrapped error.

911. **`test_loader.py (receipts)::test_load_receipt_extraction_client_raises_for_a_missing_class`**
     A missing class name is the same wrapped error.

912. **`test_loader.py (receipts)::test_load_receipt_extraction_client_can_load_the_real_recorded_client`**
     Not just fixture mechanics — proves the loader resolves the one
     real, shipped backend (`RecordedReceiptExtractionClient`).

913. **`test_loader_edge_cases.py (receipts)::test_load_receipt_extraction_client_raises_when_construction_fails`**
     A constructor that rejects the given kwargs fails loudly rather
     than a raw `TypeError` leaking through unwrapped.

914. **`test_schema.py (config)::test_receiptarchiveconfig_requires_an_extraction_backend`**
     `extraction: BackendSpec` has no default — same "must be
     explicit" stance `provider`/`llm`/`alerts` have on `SporkConfig`
     itself.

915. **`test_runtime.py::test_build_receipt_archive_components_returns_none_when_unconfigured`**
     No `[receipt_archive]` table: the feature is off entirely, not a
     crash and not an empty-but-present components bundle.

916. **`test_runtime.py::test_build_receipt_archive_components_builds_real_collaborators`**
     `attachment_fetcher`/`keyword_applier` come from a real
     `FileProvider` and actually work; `extraction_client` is the real
     loaded `RecordedReceiptExtractionClient`.

917. **`test_runtime.py::test_build_receipt_archive_components_leaves_domain_lookup_none_for_null_context`**
     `NullContextProvider` doesn't structurally support `lookup_domain()`
     — `domain_lookup` stays `None`, same as `[context]` unconfigured.

918. **`test_runtime.py::test_build_receipt_archive_components_wires_an_entitycontextprovider_as_domain_lookup`**
     The real M9/M10 synergy, proven end to end: a configured
     `EntityContextProvider` is passed straight through as
     `domain_lookup`, and a real `lookup_domain()` call against it
     resolves the expected company.

919. **`test_runtime.py::test_resolve_runtime_secrets_includes_a_configured_receipt_archives_extraction_secret_kwargs`**
     A `[receipt_archive]` table's `extraction.secret_kwargs` count
     toward "does anything configured need SecretSpec resolved" the
     same way provider/llm/alerts/context already do.

920. **`test_pipeline.py (receipts)::test_dry_run_skips_the_pdf_write_but_still_sets_audit_fields`**
     `ArchiveReceiptAugment(dry_run=True)` never writes a PDF, but
     still tags (via whatever `keyword_applier` it's given) and sets
     audit fields — extraction and auditing still happen.

921. **`test_pipeline.py (receipts)::test_dry_run_does_not_require_a_writable_output_dir`**
     A dry run never touches the filesystem — an unwritable/
     nonexistent `output_dir` doesn't raise, unlike the real write path.

922. **`test_loop.py (daemon)::test_run_daemon_archives_a_matched_receipt_message`**
     A known-sender receipt message is archived end to end through the
     real `run_daemon()` asyncio loop — PDF written, keyword applied,
     message marked processed — using
     `build_receipt_archive_components()`'s real composition, not
     hand-wired collaborators.

923. **`test_loop.py (daemon)::test_run_daemon_observe_mode_does_not_archive_or_tag_receipts`**
     `--observe` suppresses both the PDF write and the keyword tag for
     `archive_receipt` too, while the message still ends up marked
     processed — the same contract every other observe-mode action has.
