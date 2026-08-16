"""Executable bindings for the harness-driven push/fallback scenario.

Unlike m1.py's live bindings, these need no Fastmail account, no
SPORK_ACCEPTANCE_LIVE opt-in, and no real network — they drive the real
JmapProvider composition (docs/DESIGN.md §9.3) through the in-process
mitmproxy harness (tests/support/jmap_mitm.py, docs/ROADMAP.md M1c).
The harness is torn down in environment.py's after_scenario hook.
"""

from typing import Any

from behave import given, then, when

from spork.core.providers.jmap.provider import JmapProvider
from tests.support.jmap_mitm import jmap_mitm_harness


@given("the JMAP fault-injection harness is running")
def harness_running(context: Any) -> None:
    """Start the harness and seed the canned responses every scenario needs."""
    context.jmap_harness_cm = jmap_mitm_harness()
    context.harness = context.jmap_harness_cm.__enter__()
    context.harness.set_mailbox_response([{"id": "inbox-id", "name": "Inbox", "role": "inbox"}])
    context.harness.set_email_get_response(state="state-0", data=[])


@given("sporkd uses JmapProvider routed through the harness")
def provider_routed_through_harness(context: Any) -> None:
    """Build the real JmapProvider/CheckpointedFallbackSource composition."""
    context.provider = JmapProvider(
        host=context.harness.host,
        api_token="fake-token",
        poll_interval_seconds=0.01,
        reconnect_backoff_seconds=(0.1, 0.2),
    )
    context.source = context.provider.build_checkpointed_source(cursor=None)


@given("the EventSource connection will fail on the next cycle")
def eventsource_will_fail(context: Any) -> None:
    """Queue a clean-close-then-failed-reconnect outcome (see jmap_mitm.py)."""
    context.harness.disconnect_event_stream_after(n_events=0)


@when("the first source cycle runs")
@when("the next source cycle runs")
def a_source_cycle_runs(context: Any) -> None:
    """Poll the composed fallback source exactly once."""
    context.connections_before_cycle = context.harness.event_stream_connection_count()
    context.batch = context.source.poll_batch()


@then("the batch is served by polling after push fails")
def served_by_polling_after_push_fails(context: Any) -> None:
    """Push must have made at least two connection attempts before falling back."""
    made = context.harness.event_stream_connection_count() - context.connections_before_cycle
    assert made >= 2, f"expected push to fail and retry before fallback, made {made} attempts"
    assert context.batch.checkpoint == "state-0"


@then("the batch is served by push with no wasted fallback")
def served_by_push_with_no_fallback(context: Any) -> None:
    """A single successful EventSource connection means primary served the cycle."""
    made = context.harness.event_stream_connection_count() - context.connections_before_cycle
    assert made == 1, f"expected exactly one push connection, made {made}"
    assert context.batch.checkpoint == "state-1"


@then("the shared cursor advances from the poll response")
def cursor_advances_from_poll(context: Any) -> None:
    assert context.batch.checkpoint == "state-0"


@then("the shared cursor advances again")
def cursor_advances_again(context: Any) -> None:
    assert context.batch.checkpoint == "state-1"


@when("the EventSource connection becomes available again")
def eventsource_available_again(context: Any) -> None:
    """Queue a successful push event and the Email/changes page it wakes."""
    context.harness.push_event(relevant=True)
    context.harness.set_email_changes_response(new_state="state-1", created=[])
