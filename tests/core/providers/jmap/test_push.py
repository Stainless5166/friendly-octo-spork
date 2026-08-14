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


def test_wait_ignores_other_accounts_and_unrelated_events() -> None:
    trigger, _ = _trigger(
        [[_event("other", email=True), _event("account-1"), _event("account-1", delivery=True)]],
        [],
    )

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
