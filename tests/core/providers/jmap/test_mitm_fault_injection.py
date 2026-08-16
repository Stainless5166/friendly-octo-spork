"""Acceptance tests for the mitmproxy fault-injection harness (docs/ROADMAP.md M1c).

Every other JmapClient/JmapPushTrigger test in this package injects a
jmapc-shaped fake object directly, bypassing jmapc's real HTTP/SSE
transport entirely (see test_client.py, test_push.py). That's correct
for testing Spork's own request/checkpoint contract, but it cannot
prove anything about how the production path behaves when the *wire*
misbehaves — a dropped connection, a truncated body, a mid-stream
EventSource death, a 429. This module is that proof: it drives the
same unmodified production client_factory
(`spork.core.providers.jmap.client._default_client_factory`, i.e. real
jmapc.Client) through a local mitmproxy instance that can serve canned
JMAP responses and inject faults on top of them, with no DNS lookup or
socket ever reaching a real host (mitmproxy's addon sets a response
before mitmproxy would otherwise dial upstream).

`tests/support/jmap_mitm.py` does not exist yet — these tests define
its contract and are expected to fail on collection (ModuleNotFoundError)
until that harness is implemented. See docs/ROADMAP.md M1c.
"""

from __future__ import annotations

import pytest
from tests.support.jmap_mitm import jmap_mitm_harness

from spork.core.providers.jmap.client import JmapClient, JmapError
from spork.core.providers.jmap.push import JmapPushDisconnectedError, JmapPushTrigger


def test_client_round_trips_through_real_jmapc_over_the_harness_with_no_live_network() -> None:
    """The production client_factory, driven over the harness, fetches a baseline.

    Proves the harness is wired correctly end to end (session discovery,
    Mailbox/get, Email/get baseline) using the real jmapc HTTP client,
    not a fake. `requests_forwarded_upstream()` staying at 0 proves no
    real network egress happened even though the production factory
    made real HTTP calls.
    """
    with jmap_mitm_harness() as harness:
        harness.set_mailbox_response([{"id": "inbox-id", "name": "Inbox", "role": "inbox"}])
        harness.set_email_get_response(state="state-0", data=[])

        client = JmapClient(
            host=harness.host,
            api_token="fake-token",
            client_factory=harness.client_factory(),
        )
        client.connect()
        result = client.fetch_new_messages(since_cursor=None)

        assert client.account_id
        assert result.cursor == "state-0"
        assert result.messages == ()
        assert harness.requests_forwarded_upstream() == 0


def test_truncated_response_body_surfaces_as_jmap_error() -> None:
    """A response cut off mid-body over the real transport still hits JmapClient's

    one error boundary (JmapError), not an unhandled transport exception.
    """
    with jmap_mitm_harness() as harness:
        harness.set_mailbox_response([{"id": "inbox-id", "name": "Inbox", "role": "inbox"}])
        harness.truncate_next_response(after_bytes=8)

        client = JmapClient(
            host=harness.host,
            api_token="fake-token",
            client_factory=harness.client_factory(),
        )

        with pytest.raises(JmapError):
            client.connect()


def test_eventsource_mid_stream_disconnect_raises_push_disconnected_error_after_backoff() -> None:
    """A real EventSource stream killed mid-frame reaches JmapPushTrigger's

    existing disconnect/backoff path (JmapPushDisconnectedError), proving
    the generic `except Exception` boundary in push.py catches a genuine
    transport failure, not only the injected RuntimeError test doubles
    used in test_push.py.
    """
    with jmap_mitm_harness() as harness:
        harness.set_mailbox_response([{"id": "inbox-id", "name": "Inbox", "role": "inbox"}])
        harness.disconnect_event_stream_after(n_events=0)

        client = JmapClient(
            host=harness.host,
            api_token="fake-token",
            client_factory=harness.client_factory(),
        )
        client.connect()
        sleeps: list[float] = []
        trigger = JmapPushTrigger(
            client,
            sleep=sleeps.append,
            reconnect_backoff=(2.0, 5.0),
        )

        with pytest.raises(JmapPushDisconnectedError):
            trigger.wait()

        assert sleeps == [2.0]


def test_synthetic_429_with_retry_after_surfaces_as_jmap_error() -> None:
    """A real HTTP 429 with a Retry-After header still maps to JmapError.

    Retry-After handling itself isn't built yet (no item in M1/M1c
    promises it) — this test only pins today's honest behavior: the
    request fails closed through the one JMAP error boundary rather
    than raising an unhandled requests.HTTPError.
    """
    with jmap_mitm_harness() as harness:
        harness.fail_next_request(status=429, retry_after=30)

        client = JmapClient(
            host=harness.host,
            api_token="fake-token",
            client_factory=harness.client_factory(),
        )

        with pytest.raises(JmapError):
            client.connect()


def test_added_latency_does_not_change_the_returned_data() -> None:
    """Slow-but-eventually-complete responses over the real transport still

    parse correctly — the harness's latency fault must not itself
    corrupt or truncate a response it's merely delaying.
    """
    with jmap_mitm_harness() as harness:
        harness.set_mailbox_response([{"id": "inbox-id", "name": "Inbox", "role": "inbox"}])
        harness.set_email_get_response(state="state-latency", data=[])
        harness.add_latency(seconds=0.5)

        client = JmapClient(
            host=harness.host,
            api_token="fake-token",
            client_factory=harness.client_factory(),
        )
        client.connect()
        result = client.fetch_new_messages(since_cursor=None)

        assert result.cursor == "state-latency"


def test_harness_refuses_to_forward_a_request_upstream_without_explicit_opt_in() -> None:
    """No canned response configured means no live network, ever, by default.

    Safety property for a harness that will eventually be pointed at
    the maintainer's real (read-only) account to record fixtures
    (M1c's second checklist item): fault-injection/replay tests must
    never silently fall through to a live upstream call just because a
    test forgot to configure a canned response for some method.
    """
    with jmap_mitm_harness() as harness:
        client = JmapClient(
            host=harness.host,
            api_token="fake-token",
            client_factory=harness.client_factory(),
        )

        with pytest.raises(JmapError):
            client.connect()

        assert harness.requests_forwarded_upstream() == 0
