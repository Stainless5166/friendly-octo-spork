"""Acceptance tests for JmapClient (docs/ROADMAP.md M1).

Session and fetch behavior use a jmapc-shaped injected client so CI
asserts Spork's exact request/checkpoint/normalization contract without
making a network call. The mutation-side methods remain settled-shape
NotImplementedError placeholders until their own live work lands.
"""

from __future__ import annotations

import pytest

from spork.core.providers.jmap.client import JmapClient, JmapError, JmapFetchResult
from spork.core.rules.schema import Action


class _Response:
    def __init__(self, **values: object) -> None:
        self.__dict__.update(values)


class _FakeJmapcClient:
    account_id = "account-1"

    def __init__(self, responses: list[object]) -> None:
        self.jmap_session = _Response(api_url="https://api.example.test/jmap")
        self._responses = responses
        self.requests: list[object] = []

    def request(self, method: object, *, raise_errors: bool = False) -> object:
        self.requests.append(method)
        response = self._responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def _mailbox_response() -> _Response:
    return _Response(data=[_Response(id="inbox-id", name="Inbox", role="inbox")])


def _email(
    message_id: str,
    *,
    mailbox_ids: dict[str, bool] | None = None,
) -> _Response:
    return _Response(
        id=message_id,
        thread_id=f"thread-{message_id}",
        mailbox_ids=mailbox_ids or {"inbox-id": True},
        mail_from=[_Response(email="sender@example.com")],
        to=[_Response(email="recipient@example.com")],
        cc=None,
        subject="A subject",
        text_body=[_Response(part_id="part-1")],
        body_values={"part-1": _Response(value="Message body")},
        message_id=[f"<{message_id}@example.com>"],
        in_reply_to=None,
        references=None,
    )


def test_connect_authenticates_once_and_exposes_the_primary_account() -> None:
    calls: list[tuple[str, str]] = []
    backend = _FakeJmapcClient([_mailbox_response()])

    def factory(host: str, api_token: str) -> _FakeJmapcClient:
        calls.append((host, api_token))
        return backend

    client = JmapClient(
        host="api.fastmail.com",
        api_token="fake-token",
        client_factory=factory,
    )

    client.connect()
    client.connect()

    assert client.account_id == "account-1"
    assert calls == [("api.fastmail.com", "fake-token")]
    assert [type(request).__name__ for request in backend.requests] == ["MailboxGet"]


def test_first_fetch_baselines_current_email_state_without_replaying_history() -> None:
    backend = _FakeJmapcClient(
        [_mailbox_response(), _Response(state="state-1", data=[], not_found=None)]
    )
    client = JmapClient(
        host="api.fastmail.com",
        api_token="fake-token",
        client_factory=lambda host, token: backend,
    )

    result = client.fetch_new_messages(since_cursor=None)

    assert result == JmapFetchResult(messages=(), cursor="state-1")
    baseline_request = backend.requests[-1]
    assert type(baseline_request).__name__ == "EmailGet"
    assert baseline_request.ids == []


def test_fetch_pages_created_messages_normalizes_and_filters_to_inbox() -> None:
    backend = _FakeJmapcClient(
        [
            _mailbox_response(),
            _Response(
                old_state="state-1",
                new_state="state-2",
                has_more_changes=True,
                created=["msg-1", "msg-not-inbox"],
                updated=[],
                destroyed=[],
            ),
            _Response(
                state="state-2",
                data=[_email("msg-1"), _email("msg-not-inbox", mailbox_ids={"archive": True})],
                not_found=None,
            ),
            _Response(
                old_state="state-2",
                new_state="state-3",
                has_more_changes=False,
                created=["msg-2"],
                updated=[],
                destroyed=[],
            ),
            _Response(state="state-3", data=[_email("msg-2")], not_found=None),
        ]
    )
    client = JmapClient(
        host="api.fastmail.com",
        api_token="fake-token",
        client_factory=lambda host, token: backend,
    )

    result = client.fetch_new_messages(since_cursor="state-1")

    assert result.cursor == "state-3"
    assert [message.message_id for message in result.messages] == ["msg-1", "msg-2"]
    assert result.messages[0].from_address == "sender@example.com"
    assert result.messages[0].from_domain == "example.com"
    assert result.messages[0].body_text == "Message body"
    assert result.messages[0].headers == {
        "Message-ID": "<msg-1@example.com>",
        "To": "recipient@example.com",
    }


def test_session_and_request_failures_share_one_jmap_error_boundary() -> None:
    backend = _FakeJmapcClient([RuntimeError("network unavailable")])
    client = JmapClient(
        host="api.fastmail.com",
        api_token="fake-token",
        client_factory=lambda host, token: backend,
    )

    with pytest.raises(JmapError, match="network unavailable"):
        client.connect()


def test_apply_action_raises_not_implemented(make_message) -> None:
    """apply_action() would mutate the mailbox via Email/set against a
    live session (docs/DESIGN.md §9.3) — not built yet."""
    client = JmapClient(host="api.fastmail.com", api_token="fake-token")

    with pytest.raises(NotImplementedError):
        client.apply_action(make_message(), Action(type="move", mailbox="Reading"))


def test_create_draft_raises_not_implemented(make_message) -> None:
    """create_draft() would create a draft via Email/set into Drafts
    against a live session (docs/DESIGN.md §10.6) — not built yet."""
    client = JmapClient(host="api.fastmail.com", api_token="fake-token")

    with pytest.raises(NotImplementedError):
        client.create_draft(make_message(), "Friday 2pm works for me.")


def test_get_thread_context_raises_not_implemented(make_message) -> None:
    """get_thread_context() would search a live session's thread history
    via Email/query (docs/DESIGN.md §9.3) — not built yet."""
    client = JmapClient(host="api.fastmail.com", api_token="fake-token")

    with pytest.raises(NotImplementedError):
        client.get_thread_context(make_message())


def test_list_mailboxes_raises_not_implemented() -> None:
    """list_mailboxes() would fetch Mailbox/get against a live session
    (docs/DESIGN.md §9.3) — not built yet."""
    client = JmapClient(host="api.fastmail.com", api_token="fake-token")

    with pytest.raises(NotImplementedError):
        client.list_mailboxes()


def test_get_message_raises_not_implemented() -> None:
    """get_message() would fetch one message by id via Email/get
    against a live session (docs/DESIGN.md §9.3, for spork reclassify)
    — not built yet."""
    client = JmapClient(host="api.fastmail.com", api_token="fake-token")

    with pytest.raises(NotImplementedError):
        client.get_message("msg-1")
