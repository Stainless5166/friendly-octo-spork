"""Acceptance tests for JmapProvider.query_messages() (docs/ROADMAP.md M8).

JmapClient.query_messages() itself is real and tested in
test_query.py; these tests only cover JmapProvider's composition —
delegating to the underlying client and wrapping the JmapClient-shaped
result as the backend-agnostic BackfillPage (spork.core.providers.base)
— same "composition, not behavior" scope as test_provider.py's other
tests, and the same provider._client-swap injection pattern.
"""

from __future__ import annotations

from spork.core.providers.base import BackfillPage, BackfillProvider
from spork.core.providers.jmap.client import JmapClient, JmapQueryResult
from spork.core.providers.jmap.provider import JmapProvider


def _provider(client: JmapClient) -> JmapProvider:
    provider = JmapProvider(host="api.fastmail.com", api_token="fake-token")
    provider._client = client
    return provider


def test_provider_satisfies_the_backfill_provider_protocol() -> None:
    provider = JmapProvider(host="api.fastmail.com", api_token="fake-token")

    assert isinstance(provider, BackfillProvider)


def test_query_messages_delegates_to_the_client_and_wraps_the_result(make_message) -> None:
    message = make_message(message_id="msg-1")

    class _Client(JmapClient):
        def __init__(self) -> None:
            self.calls: list[dict[str, object]] = []

        def query_messages(
            self, *, unread_only: bool = False, position: int = 0, limit: int = 50
        ) -> JmapQueryResult:
            self.calls.append({"unread_only": unread_only, "position": position, "limit": limit})
            return JmapQueryResult(messages=(message,), position=10, total=42, has_more=True)

    client = _Client()
    provider = _provider(client)

    page = provider.query_messages(unread_only=True, position=10, limit=20)

    assert isinstance(page, BackfillPage)
    assert page.messages == (message,)
    assert page.position == 10
    assert page.total == 42
    assert page.has_more is True
    assert client.calls == [{"unread_only": True, "position": 10, "limit": 20}]


def test_query_messages_uses_documented_defaults() -> None:
    class _Client(JmapClient):
        def __init__(self) -> None:
            self.calls: list[dict[str, object]] = []

        def query_messages(
            self, *, unread_only: bool = False, position: int = 0, limit: int = 50
        ) -> JmapQueryResult:
            self.calls.append({"unread_only": unread_only, "position": position, "limit": limit})
            return JmapQueryResult(messages=(), position=0, total=0, has_more=False)

    client = _Client()
    provider = _provider(client)

    provider.query_messages()

    assert client.calls == [{"unread_only": False, "position": 0, "limit": 50}]
