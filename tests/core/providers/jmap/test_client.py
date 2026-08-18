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
        self.jmap_session = _session()
        self._responses = responses
        self.requests: list[object] = []

    def request(self, method: object, *, raise_errors: bool = False) -> object:
        self.requests.append(method)
        response = self._responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def _session(
    *,
    capabilities: dict[str, object] | None = None,
    account_capabilities: dict[str, object] | None = None,
    is_read_only: bool = False,
) -> _Response:
    """Build the authenticated Session Object shape the provider requires."""
    return _Response(
        api_url="https://api.example.test/jmap",
        capabilities=capabilities
        or {
            "urn:ietf:params:jmap:core": {},
            "urn:ietf:params:jmap:mail": {},
        },
        accounts={
            "account-1": _Response(
                account_capabilities=account_capabilities or {"urn:ietf:params:jmap:mail": {}},
                is_read_only=is_read_only,
            )
        },
        primary_accounts={"urn:ietf:params:jmap:mail": "account-1"},
    )


def _mailbox_response() -> _Response:
    return _Response(
        data=[
            _Response(id="inbox-id", name="Inbox", role="inbox"),
            _Response(id="sent-id", name="Sent", role="sent"),
            _Response(id="reading-id", name="Reading", role=None),
            _Response(id="drafts-id", name="Drafts", role="drafts"),
        ]
    )


def _email(
    message_id: str,
    *,
    mailbox_ids: dict[str, bool] | None = None,
    keywords: dict[str, bool] | None = None,
) -> _Response:
    return _Response(
        id=message_id,
        thread_id=f"thread-{message_id}",
        mailbox_ids=mailbox_ids or {"inbox-id": True},
        keywords=keywords or {"$seen": True},
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


def test_connect_requires_core_and_mail_session_capabilities() -> None:
    backend = _FakeJmapcClient([_mailbox_response()])
    backend.jmap_session = _session(capabilities={"urn:ietf:params:jmap:core": {}})
    client = JmapClient(
        host="api.fastmail.com",
        api_token="fake-token",
        client_factory=lambda host, token: backend,
    )

    with pytest.raises(JmapError, match="mail capability"):
        client.connect()


def test_write_access_requires_an_explicitly_writeable_account() -> None:
    backend = _FakeJmapcClient([_mailbox_response()])
    backend.jmap_session = _session(is_read_only=True)
    client = JmapClient(
        host="api.fastmail.com",
        api_token="fake-token",
        allow_writes=True,
        client_factory=lambda host, token: backend,
    )

    with pytest.raises(JmapError, match="read-only"):
        client.connect()


def test_apply_action_is_blocked_for_the_default_read_only_client(make_message) -> None:
    """The default client cannot reach the future Email/set implementation."""
    client = JmapClient(host="api.fastmail.com", api_token="fake-token")

    with pytest.raises(JmapError, match="read-only"):
        client.apply_action(make_message(), Action(type="move", mailbox="Reading"))


def test_create_draft_is_blocked_for_the_default_read_only_client(make_message) -> None:
    """The default client cannot reach the future Drafts Email/set path."""
    client = JmapClient(host="api.fastmail.com", api_token="fake-token")

    with pytest.raises(JmapError, match="read-only"):
        client.create_draft(make_message(), "Friday 2pm works for me.")


def test_list_mailboxes_returns_names_from_mailbox_get() -> None:
    """Mailbox names are read from the authenticated JMAP session."""
    backend = _FakeJmapcClient(
        [
            _Response(
                data=[
                    _Response(id="inbox-id", name="Inbox", role="inbox"),
                    _Response(id="sent-id", name="Sent", role="sent"),
                ]
            )
        ]
    )
    client = JmapClient(
        host="api.fastmail.com", api_token="fake-token", client_factory=lambda host, token: backend
    )

    assert client.list_mailboxes() == ["Inbox", "Sent"]


def test_get_thread_context_reads_prior_subject_and_sent_state(make_message) -> None:
    """Thread context is derived from Thread/get and the related emails."""
    backend = _FakeJmapcClient(
        [
            _mailbox_response(),
            _Response(data=[_Response(id="thread-1", email_ids=["prior", "current"])]),
            _Response(
                data=[
                    _email("prior", mailbox_ids={"sent-id": True}),
                    _email("current"),
                ]
            ),
        ]
    )
    client = JmapClient(
        host="api.fastmail.com", api_token="fake-token", client_factory=lambda host, token: backend
    )

    context = client.get_thread_context(make_message(message_id="current", thread_id="thread-1"))

    assert context.prior_subject == "A subject"
    assert context.user_has_replied is True
    assert [type(request).__name__ for request in backend.requests] == [
        "MailboxGet",
        "ThreadGet",
        "EmailGet",
    ]


def test_get_message_fetches_and_normalizes_one_email() -> None:
    """Message lookup returns the same normalized shape as new-mail fetch."""
    backend = _FakeJmapcClient([_mailbox_response(), _Response(data=[_email("msg-1")])])
    client = JmapClient(
        host="api.fastmail.com", api_token="fake-token", client_factory=lambda host, token: backend
    )

    message = client.get_message("msg-1")

    assert message.message_id == "msg-1"
    assert message.subject == "A subject"
    assert type(backend.requests[-1]).__name__ == "EmailGet"


def test_fetch_attachments_raises_not_implemented(make_message) -> None:
    """fetch_attachments() would resolve blobId-backed attachments via
    Email/get against a live session (docs/DESIGN.md §9.5, M10) --
    not built yet."""
    client = JmapClient(host="api.fastmail.com", api_token="fake-token")

    with pytest.raises(NotImplementedError):
        client.fetch_attachments(make_message())


def test_apply_keywords_is_blocked_for_the_default_read_only_client(make_message) -> None:
    """The default client cannot reach the future keyword Email/set path."""
    client = JmapClient(host="api.fastmail.com", api_token="fake-token")

    with pytest.raises(JmapError, match="read-only"):
        client.apply_keywords(make_message(), ["receipt"])


def test_apply_action_moves_message_with_email_state_guard(make_message) -> None:
    backend = _FakeJmapcClient(
        [
            _mailbox_response(),
            _Response(state="email-state-1", data=[_email("msg-1")]),
            _Response(updated={"msg-1": {}}),
        ]
    )
    client = JmapClient(
        host="api.fastmail.com",
        api_token="fake-token",
        allow_writes=True,
        client_factory=lambda host, token: backend,
    )

    client.apply_action(make_message(message_id="msg-1"), Action(type="move", mailbox="Reading"))

    request = backend.requests[-1]
    assert type(request).__name__ == "EmailSet"
    assert request.if_in_state == "email-state-1"
    assert request.update == {"msg-1": {"mailboxIds": {"reading-id": True}}}


def test_apply_action_tags_without_removing_existing_mailboxes(make_message) -> None:
    backend = _FakeJmapcClient(
        [
            _mailbox_response(),
            _Response(
                state="email-state-1",
                data=[_email("msg-1", mailbox_ids={"inbox-id": True, "existing-id": True})],
            ),
            _Response(updated={"msg-1": {}}),
        ]
    )
    client = JmapClient(
        host="api.fastmail.com",
        api_token="fake-token",
        allow_writes=True,
        client_factory=lambda host, token: backend,
    )

    client.apply_action(make_message(message_id="msg-1"), Action(type="tag", mailbox="Reading"))

    assert backend.requests[-1].update == {
        "msg-1": {"mailboxIds": {"inbox-id": True, "existing-id": True, "reading-id": True}}
    }


def test_apply_keywords_merges_existing_keyword_flags(make_message) -> None:
    backend = _FakeJmapcClient(
        [
            _mailbox_response(),
            _Response(
                state="email-state-1",
                data=[_email("msg-1", keywords={"$seen": True, "$flagged": True})],
            ),
            _Response(updated={"msg-1": {}}),
        ]
    )
    client = JmapClient(
        host="api.fastmail.com",
        api_token="fake-token",
        allow_writes=True,
        client_factory=lambda host, token: backend,
    )

    client.apply_keywords(make_message(message_id="msg-1"), ["receipt", "company:Acme"])

    assert backend.requests[-1].update == {
        "msg-1": {
            "keywords": {"$seen": True, "$flagged": True, "receipt": True, "company:Acme": True}
        }
    }


def test_create_draft_uses_drafts_mailbox_and_reply_headers(make_message) -> None:
    backend = _FakeJmapcClient(
        [
            _mailbox_response(),
            _Response(state="email-state-1", data=[_email("msg-1")]),
            _Response(created={"draft-msg-1": _Response(id="draft-id")}),
        ]
    )
    client = JmapClient(
        host="api.fastmail.com",
        api_token="fake-token",
        allow_writes=True,
        client_factory=lambda host, token: backend,
    )

    client.create_draft(make_message(message_id="msg-1", subject="Question"), "A reply.")

    request = backend.requests[-1]
    draft = request.create["draft-msg-1"]
    assert request.if_in_state == "email-state-1"
    assert draft.mailbox_ids == {"drafts-id": True}
    assert draft.keywords == {"$draft": True}
    assert draft.to[0].email == "sender@example.com"
    assert draft.subject == "Re: Question"
    assert draft.in_reply_to == ["<msg-1@example.com>"]
    assert draft.body_values["body"].value == "A reply."
