"""JMAP session bootstrap, cursor-safe fetch, and mutation (§6.1, §8, §9.3).

Keeps optional `jmapc` types inside this provider boundary and exposes
only `NormalizedMessage` plus an Email-state checkpoint. Mutation-side
methods remain settled `NotImplementedError` leaves until their own
recorded Fastmail contracts land.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from importlib import import_module
from typing import Any, Protocol, cast

from spork.core.models import NormalizedMessage
from spork.core.providers.base import ThreadContext
from spork.core.rules.schema import Action


class JmapError(Exception):
    """One catchable boundary for session, transport, and JMAP failures."""


@dataclass(frozen=True, slots=True)
class JmapFetchResult:
    """A fetched batch and the candidate Email state to acknowledge."""

    messages: tuple[NormalizedMessage, ...]
    cursor: str


class _JmapcClient(Protocol):
    """The small jmapc surface injected by recorded contract tests."""

    account_id: str
    jmap_session: Any

    def request(self, method: object, *, raise_errors: bool = False) -> object: ...


ClientFactory = Callable[[str, str], _JmapcClient]


def _default_client_factory(host: str, api_token: str) -> _JmapcClient:
    """Import jmapc only when the dynamically selected provider needs it."""
    try:
        client_class = import_module("jmapc").Client
    except ImportError as exc:
        raise JmapError(
            "JMAP support requires the optional dependency: install spork[jmap]"
        ) from exc
    return cast(
        _JmapcClient,
        client_class.create_with_api_token(host=host, api_token=api_token),
    )


def _method_types() -> tuple[type[Any], type[Any], type[Any]]:
    """Load request classes lazily for the same optional-dependency boundary."""
    try:
        methods = import_module("jmapc.methods")
    except ImportError as exc:
        raise JmapError(
            "JMAP support requires the optional dependency: install spork[jmap]"
        ) from exc
    return methods.EmailChanges, methods.EmailGet, methods.MailboxGet


class JmapClient:
    """A JMAP session against a single Fastmail account.

    The client factory is injectable so CI can replay exact response
    shapes while production uses `jmapc.Client.create_with_api_token()`.
    """

    def __init__(
        self,
        host: str,
        api_token: str,
        *,
        client_factory: ClientFactory = _default_client_factory,
    ) -> None:
        self._host = host
        self._api_token = api_token
        self._client_factory = client_factory
        self._client: _JmapcClient | None = None
        self._account_id: str | None = None
        self._inbox_id: str | None = None

    def connect(self) -> None:
        """Authenticate once and resolve the primary account and Inbox."""
        if self._client is not None:
            return

        _, _, mailbox_get = _method_types()
        try:
            client = self._client_factory(self._host, self._api_token)
            _ = client.jmap_session
            response = client.request(mailbox_get(ids=None), raise_errors=True)
            mailboxes = getattr(response, "data", None)
            if not isinstance(mailboxes, list):
                raise JmapError("Mailbox/get returned no mailbox list")
            inbox_ids = [
                getattr(mailbox, "id", None)
                for mailbox in mailboxes
                if getattr(mailbox, "role", None) == "inbox"
            ]
            if len(inbox_ids) != 1 or not isinstance(inbox_ids[0], str):
                raise JmapError(f"expected exactly one Inbox-role mailbox; found {len(inbox_ids)}")
            account_id = client.account_id
            if not account_id:
                raise JmapError("JMAP session has no primary mail account")
        except JmapError:
            raise
        except Exception as exc:
            raise JmapError(f"could not establish JMAP session: {exc}") from exc

        self._client = client
        self._account_id = account_id
        self._inbox_id = inbox_ids[0]

    @property
    def account_id(self) -> str:
        """Return the connected primary account ID used as the cursor key."""
        self.connect()
        assert self._account_id is not None
        return self._account_id

    def fetch_new_messages(self, since_cursor: str | None) -> JmapFetchResult:
        """Fetch Inbox messages created after an acknowledged Email state.

        A missing cursor establishes a current-state baseline and never
        replays existing mail. The returned cursor is only a candidate;
        the daemon owns persistence after processing the whole batch.
        """
        self.connect()
        email_changes, email_get, _ = _method_types()

        if since_cursor is None:
            response = self._request(email_get(ids=[]))
            state = getattr(response, "state", None)
            if not isinstance(state, str) or not state:
                raise JmapError("Email/get baseline returned no state")
            return JmapFetchResult(messages=(), cursor=state)

        cursor = since_cursor
        messages: list[NormalizedMessage] = []
        while True:
            changes = self._request(email_changes(since_state=cursor))
            created = getattr(changes, "created", None)
            new_state = getattr(changes, "new_state", None)
            has_more = getattr(changes, "has_more_changes", None)
            if not isinstance(created, list) or not all(isinstance(item, str) for item in created):
                raise JmapError("Email/changes returned invalid created IDs")
            if not isinstance(new_state, str) or not isinstance(has_more, bool):
                raise JmapError("Email/changes returned invalid state metadata")

            if created:
                response = self._request(
                    email_get(
                        ids=created,
                        properties=[
                            "id",
                            "threadId",
                            "mailboxIds",
                            "from",
                            "to",
                            "cc",
                            "subject",
                            "textBody",
                            "bodyValues",
                            "messageId",
                            "inReplyTo",
                            "references",
                        ],
                        fetch_text_body_values=True,
                        fetch_html_body_values=False,
                    )
                )
                emails = getattr(response, "data", None)
                if not isinstance(emails, list):
                    raise JmapError("Email/get returned no message list")
                messages.extend(
                    self._normalize(email) for email in emails if self._is_inbox_message(email)
                )

            cursor = new_state
            if not has_more:
                return JmapFetchResult(messages=tuple(messages), cursor=cursor)

    def _request(self, method: object) -> object:
        """Apply the module's single error boundary to one JMAP method."""
        assert self._client is not None
        try:
            return self._client.request(method, raise_errors=True)
        except Exception as exc:
            raise JmapError(f"JMAP request failed: {exc}") from exc

    def _is_inbox_message(self, email: object) -> bool:
        mailbox_ids = getattr(email, "mailbox_ids", None)
        return (
            self._inbox_id is not None
            and isinstance(mailbox_ids, dict)
            and mailbox_ids.get(self._inbox_id) is True
        )

    @staticmethod
    def _normalize(email: object) -> NormalizedMessage:
        """Reduce an optional-heavy jmapc Email to the pipeline model."""
        message_id = getattr(email, "id", None)
        thread_id = getattr(email, "thread_id", None)
        if not isinstance(message_id, str) or not isinstance(thread_id, str):
            raise JmapError("Email/get returned a message without id/threadId")

        senders = getattr(email, "mail_from", None) or []
        from_address = getattr(senders[0], "email", "") if senders else ""
        if not isinstance(from_address, str):
            from_address = ""
        _, separator, from_domain = from_address.rpartition("@")
        if not separator:
            from_domain = ""

        body_values = getattr(email, "body_values", None) or {}
        text_parts = getattr(email, "text_body", None) or []
        body_text = "\n\n".join(
            value
            for part in text_parts
            if isinstance((part_id := getattr(part, "part_id", None)), str)
            if (body_value := body_values.get(part_id)) is not None
            if isinstance((value := getattr(body_value, "value", None)), str)
        )

        headers: dict[str, str] = {}
        JmapClient._add_address_header(headers, "To", getattr(email, "to", None))
        JmapClient._add_address_header(headers, "Cc", getattr(email, "cc", None))
        JmapClient._add_list_header(headers, "Message-ID", getattr(email, "message_id", None))
        JmapClient._add_list_header(headers, "In-Reply-To", getattr(email, "in_reply_to", None))
        JmapClient._add_list_header(
            headers, "References", getattr(email, "references", None), joiner=" "
        )

        mailbox_ids = getattr(email, "mailbox_ids", None) or {}
        return NormalizedMessage(
            message_id=message_id,
            thread_id=thread_id,
            from_address=from_address,
            from_domain=from_domain,
            subject=getattr(email, "subject", None) or "",
            body_text=body_text,
            headers=headers,
            mailbox_ids=tuple(key for key, present in mailbox_ids.items() if present),
        )

    @staticmethod
    def _add_address_header(headers: dict[str, str], name: str, addresses: object) -> None:
        if not isinstance(addresses, list):
            return
        values = [getattr(address, "email", None) for address in addresses]
        rendered = ", ".join(value for value in values if isinstance(value, str))
        if rendered:
            headers[name] = rendered

    @staticmethod
    def _add_list_header(
        headers: dict[str, str],
        name: str,
        values: object,
        *,
        joiner: str = ", ",
    ) -> None:
        if isinstance(values, list) and all(isinstance(value, str) for value in values):
            rendered = joiner.join(values)
            if rendered:
                headers[name] = rendered

    def apply_action(self, message: NormalizedMessage, action: Action) -> None:
        """Mutate `message`'s mailboxes via `Email/set` per `action`
        (docs/DESIGN.md §9.3) — the write side of the JMAP provider."""
        raise NotImplementedError(
            "JmapClient.apply_action() requires a live jmapc session — "
            "not implemented yet, see docs/ROADMAP.md M1"
        )

    def create_draft(self, message: NormalizedMessage, body: str) -> None:
        """Create a draft reply to `message` via `Email/set` into the
        account's Drafts mailbox — never `EmailSubmission/set`
        (docs/DESIGN.md §10.6, §11's "draft, never send" invariant)."""
        raise NotImplementedError(
            "JmapClient.create_draft() requires a live jmapc session — "
            "not implemented yet, see docs/ROADMAP.md M3"
        )

    def get_thread_context(self, message: NormalizedMessage) -> ThreadContext:
        """Resolve `message`'s thread history via `Email/query` against
        `message.thread_id` (docs/DESIGN.md §9.3) — the fifth
        `NotImplementedError` stub, same reason as the other four."""
        raise NotImplementedError(
            "JmapClient.get_thread_context() requires a live jmapc session — "
            "not implemented yet, see docs/ROADMAP.md M5"
        )

    def list_mailboxes(self) -> Sequence[str]:
        """Fetch the account's mailbox names via `Mailbox/get`
        (docs/DESIGN.md §9.3) — the sixth `NotImplementedError` stub,
        same reason as the other five."""
        raise NotImplementedError(
            "JmapClient.list_mailboxes() requires a live jmapc session — "
            "not implemented yet, see docs/ROADMAP.md M5"
        )

    def get_message(self, message_id: str) -> NormalizedMessage:
        """Fetch one message by id via `Email/get` (docs/DESIGN.md §7.4/§13,
        for `spork reclassify <id>`) — the seventh `NotImplementedError`
        stub, same reason as the other six."""
        raise NotImplementedError(
            "JmapClient.get_message() requires a live jmapc session — "
            "not implemented yet, see docs/ROADMAP.md M5"
        )
