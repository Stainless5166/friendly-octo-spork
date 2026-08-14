"""Failure and boundary coverage for the live JMAP read client."""

from __future__ import annotations

from collections.abc import Iterable

import pytest

from spork.core.providers.jmap import client as client_module
from spork.core.providers.jmap.client import JmapClient, JmapError, JmapFetchResult


class _Response:
    def __init__(self, **values: object) -> None:
        self.__dict__.update(values)


class _FakeClient:
    account_id = "account-1"
    events: Iterable[object] = ()

    def __init__(self, responses: list[object]) -> None:
        self.jmap_session = _Response(api_url="https://api.example.test/jmap")
        self.responses = responses
        self.requests: list[object] = []

    def request(self, method: object, *, raise_errors: bool = False) -> object:
        self.requests.append(method)
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def _client(responses: list[object]) -> tuple[JmapClient, _FakeClient]:
    backend = _FakeClient(responses)
    client = JmapClient(
        "api.fastmail.com",
        "fake-token",
        client_factory=lambda host, token: backend,
    )
    return client, backend


def _mailboxes(*roles: str | None) -> _Response:
    return _Response(
        data=[
            _Response(id=f"mailbox-{index}", name=f"Mailbox {index}", role=role)
            for index, role in enumerate(roles)
        ]
    )


@pytest.mark.parametrize("target", ["client", "methods"])
def test_missing_optional_dependency_names_the_install_extra(
    target: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def missing_import(name: str) -> object:
        raise ImportError(name)

    monkeypatch.setattr(client_module, "import_module", missing_import)

    with pytest.raises(JmapError, match=r"spork\[jmap\]"):
        if target == "client":
            client_module._default_client_factory("api.fastmail.com", "fake-token")
        else:
            client_module._method_types()


def test_default_factory_passes_credentials_to_jmapc(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, str]] = []
    backend = _FakeClient([])

    class _ClientClass:
        @staticmethod
        def create_with_api_token(*, host: str, api_token: str) -> _FakeClient:
            calls.append((host, api_token))
            return backend

    monkeypatch.setattr(
        client_module,
        "import_module",
        lambda name: _Response(Client=_ClientClass),
    )

    result = client_module._default_client_factory("api.fastmail.com", "fake-token")

    assert result is backend
    assert calls == [("api.fastmail.com", "fake-token")]


def test_default_factory_configures_mail_event_types(monkeypatch: pytest.MonkeyPatch) -> None:
    options: list[dict[str, object]] = []
    backend = _FakeClient([])

    class _EventSourceConfig:
        def __init__(self, **values: object) -> None:
            self.values = values

    class _ClientClass:
        @staticmethod
        def create_with_api_token(**values: object) -> _FakeClient:
            options.append(values)
            return backend

    monkeypatch.setattr(
        client_module,
        "import_module",
        lambda name: _Response(Client=_ClientClass, EventSourceConfig=_EventSourceConfig),
    )

    client_module._default_client_factory("api.fastmail.com", "fake-token")

    config = options[0]["event_source_config"]
    assert isinstance(config, _EventSourceConfig)
    assert config.values == {"types": "EmailDelivery,Email", "closeafter": "no", "ping": 30}


def test_event_stream_connects_once_and_returns_the_backend_stream() -> None:
    client, backend = _client([_mailboxes("inbox")])
    backend.events = ("event",)

    assert tuple(client.event_stream()) == ("event",)
    assert tuple(client.event_stream()) == ("event",)


@pytest.mark.parametrize("roles", [(), (None,), ("inbox", "inbox")])
def test_connect_rejects_missing_or_ambiguous_inbox_roles(
    roles: tuple[str | None, ...],
) -> None:
    client, _ = _client([_mailboxes(*roles)])

    with pytest.raises(JmapError, match="exactly one Inbox-role mailbox"):
        client.connect()


@pytest.mark.parametrize("failure", ["missing-list", "missing-account"])
def test_connect_rejects_incomplete_session_metadata(failure: str) -> None:
    response = _Response(data=None) if failure == "missing-list" else _mailboxes("inbox")
    client, backend = _client([response])
    if failure == "missing-account":
        backend.account_id = ""

    with pytest.raises(JmapError, match="mailbox list|primary mail account"):
        client.connect()


def test_baseline_requires_a_nonempty_email_state() -> None:
    client, _ = _client([_mailboxes("inbox"), _Response(state=None, data=[])])

    with pytest.raises(JmapError, match="baseline returned no state"):
        client.fetch_new_messages(None)


def test_empty_changes_advance_the_candidate_cursor_without_email_get() -> None:
    client, backend = _client(
        [
            _mailboxes("inbox"),
            _Response(
                old_state="state-1",
                new_state="state-2",
                has_more_changes=False,
                created=[],
                updated=["msg-updated"],
                destroyed=[],
            ),
        ]
    )

    result = client.fetch_new_messages("state-1")

    assert result == JmapFetchResult(messages=(), cursor="state-2")
    assert [type(request).__name__ for request in backend.requests] == [
        "MailboxGet",
        "EmailChanges",
    ]


@pytest.mark.parametrize(
    ("created", "new_state", "has_more", "message"),
    [
        (None, "state-2", False, "created IDs"),
        ([1], "state-2", False, "created IDs"),
        ([], None, False, "state metadata"),
        ([], "state-2", None, "state metadata"),
    ],
)
def test_changes_reject_malformed_state_metadata(
    created: object,
    new_state: object,
    has_more: object,
    message: str,
) -> None:
    client, _ = _client(
        [
            _mailboxes("inbox"),
            _Response(
                old_state="state-1",
                new_state=new_state,
                has_more_changes=has_more,
                created=created,
                updated=[],
                destroyed=[],
            ),
        ]
    )

    with pytest.raises(JmapError, match=message):
        client.fetch_new_messages("state-1")


@pytest.mark.parametrize(
    ("response", "message"),
    [
        (RuntimeError("connection reset"), "connection reset"),
        (_Response(data=None), "no message list"),
    ],
)
def test_email_get_failures_are_reported_at_the_jmap_boundary(
    response: object,
    message: str,
) -> None:
    client, _ = _client(
        [
            _mailboxes("inbox"),
            _Response(
                old_state="state-1",
                new_state="state-2",
                has_more_changes=False,
                created=["msg-1"],
                updated=[],
                destroyed=[],
            ),
            response,
        ]
    )

    with pytest.raises(JmapError, match=message):
        client.fetch_new_messages("state-1")


def test_normalization_rejects_a_message_without_jmap_ids() -> None:
    client, _ = _client(
        [
            _mailboxes("inbox"),
            _Response(
                old_state="state-1",
                new_state="state-2",
                has_more_changes=False,
                created=["msg-1"],
                updated=[],
                destroyed=[],
            ),
            _Response(data=[_Response(id=None, thread_id=None, mailbox_ids={"mailbox-0": True})]),
        ]
    )

    with pytest.raises(JmapError, match="without id/threadId"):
        client.fetch_new_messages("state-1")


def test_normalization_tolerates_missing_optional_sender_body_and_headers() -> None:
    message = JmapClient._normalize(
        _Response(
            id="msg-1",
            thread_id="thread-1",
            mailbox_ids={},
            mail_from=[_Response(email=123)],
            to=None,
            cc=None,
            subject=None,
            text_body=None,
            body_values=None,
            message_id=None,
            in_reply_to=None,
            references=None,
        )
    )

    assert message.from_address == ""
    assert message.from_domain == ""
    assert message.subject == ""
    assert message.body_text == ""
    assert message.headers == {}
