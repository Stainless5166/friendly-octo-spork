"""EventSource push listener and transient reconnect boundary (§6.2, §8)."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from time import sleep as default_sleep

from spork.core.providers.jmap.backoff import next_delay
from spork.core.providers.jmap.client import JmapClient


class JmapPushDisconnectedError(Exception):
    """A transient EventSource failure that should activate polling fallback."""


class JmapPushTrigger:
    """Block until a relevant account event, retrying with explicit backoff.

    `events_factory`/`sleep` are injectable for recorded contract tests;
    production uses the client's jmapc stream and `time.sleep`. The
    trigger owns retry timing but not fallback selection or durable
    cursor state.
    """

    def __init__(
        self,
        client: JmapClient,
        *,
        account_id: str | None = None,
        events_factory: Callable[[], Iterable[object]] | None = None,
        sleep: Callable[[float], None] = default_sleep,
        reconnect_backoff: Sequence[float] = (2.0, 5.0, 15.0, 60.0, 300.0),
    ) -> None:
        self._client = client
        self._account_id = account_id
        self._events_factory = events_factory if events_factory is not None else client.event_stream
        self._sleep = sleep
        self._reconnect_backoff = tuple(reconnect_backoff)
        self._attempt = 0

    def wait(self) -> None:
        """Consume events until the configured account has mail activity."""
        try:
            for event in self._events_factory():
                if self._is_relevant(event):
                    self._attempt = 0
                    return
        except Exception as exc:
            self._disconnect(str(exc))
        self._disconnect("EventSource ended")

    def _disconnect(self, reason: str) -> None:
        """Delay one retry, then hand transient failure to fallback."""
        try:
            delay = next_delay(self._reconnect_backoff, self._attempt)
        except ValueError as exc:
            raise JmapPushDisconnectedError(str(exc)) from exc
        self._sleep(delay)
        self._attempt += 1
        raise JmapPushDisconnectedError(reason)

    def _is_relevant(self, event: object) -> bool:
        """Accept only Email or EmailDelivery state for this account."""
        data = getattr(event, "data", None)
        changed = getattr(data, "changed", None)
        if not isinstance(changed, dict):
            return False
        account_id = self._account_id if self._account_id is not None else self._client.account_id
        state = changed.get(account_id)
        if state is None:
            return False
        return (
            getattr(state, "email", None) is not None
            or getattr(state, "email_delivery", None) is not None
        )
