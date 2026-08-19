"""Acceptance tests for JMAP EventSource push triggering."""

from __future__ import annotations

from collections.abc import Sequence

import pytest

from spork.core.providers.jmap.client import JmapClient
from spork.core.providers.jmap.push import JmapPushDisconnectedError, JmapPushTrigger


class _Response:
    def __init__(self, **values: object) -> None:
        self.__dict__.update(values)


def _event(account_id: str, *, email: bool = False, delivery: bool = False) -> _Response:
    return _Response(
        data=_Response(
            changed={
                account_id: _Response(
                    email=_Response(state="email-state") if email else None,
                    email_delivery=_Response(state="delivery-state") if delivery else None,
                )
            }
        )
    )


def _trigger(
    streams: list[Sequence[object] | BaseException], sleeps: list[float]
) -> tuple[JmapPushTrigger, list[float]]:
    client = JmapClient(host="api.fastmail.com", api_token="fake-token")

    def events_factory() -> Sequence[object]:
        stream = streams.pop(0)
        if isinstance(stream, BaseException):
            raise stream
        return stream

    return JmapPushTrigger(
        client,
        account_id="account-1",
        events_factory=events_factory,
        sleep=sleeps.append,
        reconnect_backoff=(2.0, 5.0),
    ), sleeps


def test_wait_returns_for_a_relevant_email_event() -> None:
    trigger, _ = _trigger([[_event("account-1", email=True)]], [])

    trigger.wait()


def test_wait_keeps_scanning_past_non_matching_events_in_one_batch() -> None:
    """A relevant event later in the same batch is still found — wait()
    doesn't stop at (or get confused by) the wrong-account/no-state-change
    events ahead of it. Doesn't by itself prove either of those two is
    individually rejected — see the two isolated tests below for that;
    a batch already containing a real match can't distinguish "correctly
    skipped the earlier events" from "incorrectly matched on one of them
    instead," since either way wait() returns without raising."""
    trigger, _ = _trigger(
        [[_event("other", email=True), _event("account-1"), _event("account-1", delivery=True)]],
        [],
    )

    trigger.wait()


def test_wait_does_not_treat_an_event_for_a_different_account_as_relevant() -> None:
    """Isolates the account-filtering claim: given *only* a wrong-account
    event (nothing genuinely relevant anywhere in the batch), wait() must
    disconnect rather than return — the only way to tell "correctly
    rejected" apart from "incorrectly accepted" when there's no second,
    real match to mask the difference."""
    trigger, _ = _trigger([[_event("other", email=True)]], [])

    with pytest.raises(JmapPushDisconnectedError):
        trigger.wait()


def test_wait_does_not_treat_a_state_with_no_email_or_delivery_change_as_relevant() -> None:
    """Same isolation for account-1's own state carrying neither an email
    nor an email_delivery change — must disconnect, not return."""
    trigger, _ = _trigger([[_event("account-1")]], [])

    with pytest.raises(JmapPushDisconnectedError):
        trigger.wait()


def test_wait_sleeps_using_backoff_and_reports_a_disconnect() -> None:
    trigger, sleeps = _trigger([RuntimeError("stream closed")], [])

    with pytest.raises(JmapPushDisconnectedError, match="stream closed"):
        trigger.wait()

    assert sleeps == [2.0]


def test_next_wait_retries_push_and_resets_backoff_after_recovery() -> None:
    trigger, sleeps = _trigger([RuntimeError("first"), [_event("account-1", email=True)]], [])

    with pytest.raises(JmapPushDisconnectedError):
        trigger.wait()
    trigger.wait()

    assert sleeps == [2.0]


def test_wait_rejects_an_empty_reconnect_schedule() -> None:
    client = JmapClient(host="api.fastmail.com", api_token="fake-token")
    trigger = JmapPushTrigger(
        client,
        account_id="account-1",
        events_factory=lambda: (),
        reconnect_backoff=(),
    )

    with pytest.raises(JmapPushDisconnectedError, match="must not be empty"):
        trigger.wait()


def test_wait_keeps_scanning_past_malformed_state_data_in_one_batch() -> None:
    """A relevant event after a malformed one in the same batch is still
    found. Same masking caveat as test_wait_keeps_scanning_past_non_matching_events_in_one_batch —
    see test_wait_does_not_treat_malformed_state_data_as_relevant below
    for the isolated claim."""
    trigger, _ = _trigger(
        [[_Response(data=_Response(changed=None)), _event("account-1", email=True)]], []
    )

    trigger.wait()


def test_wait_does_not_treat_malformed_state_data_as_relevant() -> None:
    """Isolates the malformed-data claim: a batch containing *only* an
    event whose data.changed isn't a dict must disconnect, not return —
    proves the isinstance(changed, dict) guard actually rejects it,
    rather than being masked by a later real match."""
    trigger, _ = _trigger([[_Response(data=_Response(changed=None))]], [])

    with pytest.raises(JmapPushDisconnectedError):
        trigger.wait()
