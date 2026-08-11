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
none are unspecified.**
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

### M3–M7

No implementation, no tests. Not evaluated here — nothing to check yet.

---

## Full test inventory (121 tests, all passing — 0 xfail)

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

### tests/core (pipeline, M2)

114. **`test_pipeline.py::test_process_message_skips_already_processed_messages`**
    A message already `mark_processed()`-ed. Asserts `process_message()`
    returns `None` and never touches the applier.

115. **`test_pipeline.py::test_process_message_applies_matched_rule_action_and_marks_processed`**
    A message matching a `move` rule. Asserts the applier was called,
    `has_processed()` becomes `True`, and the returned verdict matches.

116. **`test_pipeline.py::test_process_message_writes_an_audit_entry_for_applied_actions`**
    After processing, asserts exactly one audit entry exists with the
    injected clock's timestamp.

117. **`test_pipeline.py::test_process_message_handles_escalate_without_calling_executor`**
    A verdict resolving to `escalate`. Asserts the applier was never
    called, but the message is still marked processed (the interim
    pending-Tier-2 policy, docs/DESIGN.md §9).

118. **`test_pipeline.py::test_process_message_returns_the_verdict`**
    Asserts the returned `RuleVerdict` matches what was actually acted
    on.

119. **`test_pipeline_edge_cases.py::test_process_message_propagates_executor_failure_and_does_not_mark_processed`**
    A failing applier. Asserts the exception propagates AND that
    neither `has_processed()` nor the audit log reflect the message —
    the retry-on-next-cycle guarantee the ordering exists for.

120. **`test_pipeline_edge_cases.py::test_mark_processed_uses_the_injected_clock`**
    Checks `processed_messages.processed_at` directly (via a fresh
    connection) after processing with a fixed clock. Asserts it
    matches — not just the audit entry's timestamp, per 116.

121. **`test_pipeline_edge_cases.py::test_default_clock_produces_a_real_parseable_timestamp`**
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
