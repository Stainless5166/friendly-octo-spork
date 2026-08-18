"""Acceptance tests for JmapClient.query_messages() (docs/ROADMAP.md M8).

Deliberately separate from fetch_new_messages() (M1): that method
baselines on first run and never replays existing mail by design.
query_messages() is the explicit, opt-in backfill read path — windowed
Email/query + Email/get over the Inbox, for retroactively categorizing
mail that arrived before spork was ever running. Same injected
jmapc-shaped fake convention as test_client.py/test_push.py, no live
network.
"""

from __future__ import annotations

from spork.core.providers.jmap.client import JmapClient, JmapQueryResult


class _Response:
    def __init__(self, **values: object) -> None:
        self.__dict__.update(values)


class _FakeJmapcClient:
    account_id = "account-1"

    def __init__(self, responses: list[object]) -> None:
        self.jmap_session = _Response(
            api_url="https://api.example.test/jmap",
            capabilities={
                "urn:ietf:params:jmap:core": {},
                "urn:ietf:params:jmap:mail": {},
            },
            accounts={
                "account-1": _Response(
                    account_capabilities={"urn:ietf:params:jmap:mail": {}},
                    is_read_only=False,
                )
            },
            primary_accounts={"urn:ietf:params:jmap:mail": "account-1"},
        )
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


def _email(message_id: str) -> _Response:
    return _Response(
        id=message_id,
        thread_id=f"thread-{message_id}",
        mailbox_ids={"inbox-id": True},
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


def _client(backend: _FakeJmapcClient) -> JmapClient:
    return JmapClient(
        host="api.fastmail.com",
        api_token="fake-token",
        client_factory=lambda host, token: backend,
    )


def test_query_messages_returns_a_page_of_normalized_messages_and_position() -> None:
    backend = _FakeJmapcClient(
        [
            _mailbox_response(),
            _Response(
                query_state="q-1",
                can_calculate_changes=False,
                position=0,
                ids=["msg-1", "msg-2"],
                total=2,
            ),
            _Response(state="state-1", data=[_email("msg-1"), _email("msg-2")], not_found=None),
        ]
    )

    result = _client(backend).query_messages(position=0, limit=50)

    assert isinstance(result, JmapQueryResult)
    assert [m.message_id for m in result.messages] == ["msg-1", "msg-2"]
    assert result.position == 0
    assert result.next_position == 2
    assert result.total == 2
    assert result.has_more is False


def test_query_messages_unread_only_sets_the_not_keyword_filter() -> None:
    backend = _FakeJmapcClient(
        [
            _mailbox_response(),
            _Response(query_state="q-1", can_calculate_changes=False, position=0, ids=[], total=0),
        ]
    )

    _client(backend).query_messages(unread_only=True, position=0, limit=50)

    query_request = backend.requests[-1]
    assert type(query_request).__name__ == "EmailQuery"
    assert query_request.filter.not_keyword == "$seen"
    assert query_request.filter.in_mailbox == "inbox-id"


def test_query_messages_has_more_true_when_a_later_page_remains() -> None:
    backend = _FakeJmapcClient(
        [
            _mailbox_response(),
            _Response(
                query_state="q-1",
                can_calculate_changes=False,
                position=0,
                ids=["msg-1"],
                total=5,
            ),
            _Response(state="state-1", data=[_email("msg-1")], not_found=None),
        ]
    )

    result = _client(backend).query_messages(position=0, limit=1)

    assert result.has_more is True


def test_query_messages_with_no_matching_ids_skips_the_get_call() -> None:
    backend = _FakeJmapcClient(
        [
            _mailbox_response(),
            _Response(query_state="q-1", can_calculate_changes=False, position=0, ids=[], total=0),
        ]
    )

    result = _client(backend).query_messages(position=0, limit=50)

    assert result.messages == ()
    assert result.has_more is False
    assert [type(r).__name__ for r in backend.requests] == ["MailboxGet", "EmailQuery"]


def test_query_messages_next_position_accounts_for_ids_not_returned_by_get() -> None:
    """A message deleted/moved between Email/query and Email/get (plausible

    mid-sweep on a live several-thousand-message Inbox) must not stall or
    drift pagination: next_position advances by how many ids Email/query
    matched, not by how many messages Email/get actually returned.
    """
    backend = _FakeJmapcClient(
        [
            _mailbox_response(),
            _Response(
                query_state="q-1",
                can_calculate_changes=False,
                position=0,
                ids=["msg-1", "msg-2", "msg-3"],
                total=5,
            ),
            # Email/get only returns 2 of the 3 requested ids (msg-2 was
            # deleted/moved in between) - not_found would list it in a real
            # response, irrelevant to this assertion.
            _Response(state="state-1", data=[_email("msg-1"), _email("msg-3")], not_found=None),
        ]
    )

    result = _client(backend).query_messages(position=0, limit=3)

    assert len(result.messages) == 2
    assert result.next_position == 3
    assert result.has_more is True


def test_query_messages_passes_the_requested_position_and_limit() -> None:
    backend = _FakeJmapcClient(
        [
            _mailbox_response(),
            _Response(
                query_state="q-1", can_calculate_changes=False, position=20, ids=[], total=20
            ),
        ]
    )

    _client(backend).query_messages(position=20, limit=10)

    query_request = backend.requests[-1]
    assert query_request.position == 20
    assert query_request.limit == 10
