# Test Suite Inventory & Milestone Coverage

**Status:** snapshot as of the M1a (source/dispatch pipeline) milestone,
updated to add xfail coverage for two known M0 gaps.
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

Two gaps that were previously "no test at all" — **M0's own exit
criterion (`spork --help` / `sporkd --help` producing real output)**
and **the missing `secretspec.toml`** — now have `xfail`-marked tests
(`tests/cli/test_main.py`, `tests/daemon/test_main.py`,
`tests/test_secretspec_config.py`) describing the actual target
behavior from `docs/DESIGN.md`, verified to fail for the right reason
(`--runxfail` shows the real `NotImplementedError`/missing-file error,
not a bug in the test). `xfail_strict = true` (`pyproject.toml`) means
if either ever starts passing without its marker being removed, the
suite fails — so these can't quietly go stale once the feature lands.
The remaining gaps in M1/M2 don't have tests yet because their
interfaces aren't designed yet, not because writing the test was
skipped; see the coverage tables below.

---

## Milestone coverage

### M0 — Project scaffolding

| Checklist item | Implemented | Tested |
|---|---|---|
| `uv init` / `pyproject.toml` scripts | ✅ | Not directly — no test asserts the entry points resolve |
| `src/spork/` package layout | ✅ | Indirectly — every test's imports depend on it |
| `secretspec.toml` w/ declared secrets | ❌ | `xfail` — test 46 |
| Lint/format/type-check config | ✅ | Validated by CI runs, not pytest |
| CI: lint/type-check/tests on push+PR | ✅ | Validated by the workflows themselves, not pytest |
| `spork --help` / `sporkd --help` work | ❌ (crashes) | `xfail` — tests 47, 48 |

M0 was never meant to carry unit tests of its own (it's scaffolding).
The `--help` and `secretspec.toml` gaps are now tracked as `xfail`
tests rather than silent gaps — still not implemented, but no longer
invisible to the suite.

### M1 — JMAP connectivity

| Checklist item | Implemented | Tested |
|---|---|---|
| `jmap.client` session bootstrap (`jmapc`) | ❌ | — |
| Mailbox role resolution + caching | ✅ | ✅ — tests 20–26 (7 tests) |
| `Email/query`+`Email/get` batched fetch | ❌ | — |
| EventSource push listener + backoff | ❌ (listener) / ✅ (backoff math only) | ❌ (listener) / ✅ (backoff math: tests 16–19) |
| Poll-based fallback | ❌ | — |
| State DB (`push_cursor`, `processed_messages`) | ❌ | — |
| `spork doctor` | ❌ | — |

One nuance: tests 16–19 test `next_delay()`'s scheduling math
correctly and thoroughly, but that's a helper *for* the "EventSource
push listener with reconnect/backoff" checklist item, not the listener
itself — the listener doesn't exist, so the checklist item as a whole
is still untested where it matters (does a real disconnect actually
trigger a reconnect on this schedule).

1 of 7 items is actually done (mailbox resolution), and it's well
tested. The other 6 are simply not built yet.

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

### M2 — Rule engine (Tier 1) + action executor

| Checklist item | Implemented | Tested |
|---|---|---|
| Rule schema + `rules.toml` loader/validator | ✅ schema / ❌ loader | Schema: exercised implicitly via every engine test (27–35), no dedicated `test_schema.py` / Loader: — |
| Tier 1 evaluator | ✅ | ✅ — tests 27–35 (9 tests) |
| Action executor (`Email/set`) | ❌ | — |
| `processed_messages` idempotency | ❌ | — |
| `audit_log` writes | ❌ | — |
| `spork rules test` dry-run | ❌ | — |
| Unit tests: condition matching / dry-run / idempotency | ✅ (condition matching only) | — (dry-run, idempotency: nothing to test yet) |

The evaluator is thoroughly tested, including its edge cases (empty
rule list, all-default condition, missing classifier, memoization).
The schema (`Condition`/`Action`/`Rule`) has no dedicated test file,
but every field it defines gets exercised through the engine tests
that construct rules with it — including defaults (`enabled=True`,
`description=""`) working correctly, since several tests rely on them
implicitly rather than setting them explicitly. That's adequate, not
ideal: a `test_schema.py` asserting validation behavior directly (e.g.
an invalid `Action.type` value being rejected) doesn't exist.

2 of 7 items done; both are well tested, including edge cases. The
other 5 — loader, action executor, idempotency, audit log, dry-run CLI
— have zero implementation and therefore zero tests.

### M3–M7

No implementation, no tests. Not evaluated here — nothing to check yet.

---

## Full test inventory (48 tests: 45 passing + 3 xfail)

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

### tests/core/jmap

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

### xfail — known, specified, unimplemented (M0)

These three are `pytest.mark.xfail`, not part of the "45 passing"
count above. Each describes real target behavior from `docs/DESIGN.md`
(not today's `NotImplementedError` placeholder), and each was verified
with `--runxfail` to fail for the right reason before being marked.

46. **`test_secretspec_config.py::test_secretspec_toml_declares_the_required_secrets`**
    Reads `secretspec.toml` from the repo root and parses it as TOML,
    then asserts `profiles.default` declares both `JMAP_API_TOKEN` and
    `ANTHROPIC_API_KEY` — the secrets `docs/DESIGN.md` §7.3 specifies.
    Currently xfails because the file doesn't exist at all.

47. **`tests/cli/test_main.py::test_help_prints_usage_and_exits_zero`**
    Runs `python -m spork.cli.main --help` as a subprocess. Asserts exit
    code 0, "usage" present in stdout, and no traceback in stderr.
    Currently xfails because `main()` ignores `argv` and unconditionally
    raises `NotImplementedError`, so the process exits 1 with a
    traceback instead.

48. **`tests/daemon/test_main.py::test_help_prints_usage_and_exits_zero`**
    Same as 47, for `python -m spork.daemon.main --help`. Same current
    failure mode, same reasoning.
