"""JMAP session bootstrap, cursor-safe fetch, and mutation (§6.1, §8, §9.3).

Keeps optional `jmapc` types inside this provider boundary and exposes
only `NormalizedMessage` plus an Email-state checkpoint. Mutation-side
methods use guarded `Email/set` requests after reading the current Email
state, so concurrent remote changes fail closed.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from importlib import import_module
from typing import Any, Protocol, cast

from spork.core.models import Attachment, NormalizedMessage
from spork.core.providers.base import ThreadContext
from spork.core.rules.schema import Action


class JmapError(Exception):
    """One catchable boundary for session, transport, and JMAP failures."""


@dataclass(frozen=True, slots=True)
class JmapPermissions:
    """Read/write permission facts derived from one authenticated account."""

    can_read_mail: bool
    can_write_mail: bool


@dataclass(frozen=True, slots=True)
class JmapFetchResult:
    """A fetched batch and the candidate Email state to acknowledge."""

    messages: tuple[NormalizedMessage, ...]
    cursor: str


@dataclass(frozen=True, slots=True)
class JmapQueryResult:
    """One windowed page from an explicit backfill query (§9.3, M8).

    Not a live-ingestion checkpoint — `position`/`total` describe a
    page in `Email/query`'s result window, not an Email state to
    acknowledge. `next_position` is where the *next* page should start
    — `position` plus how many ids `Email/query` actually matched at
    this window, not `len(messages)`. Those two diverge whenever
    `Email/get` returns fewer emails than requested ids (a message
    deleted/moved between the two calls, plausible mid-sweep on a
    live several-thousand-message backfill) — deriving pagination
    from the post-normalize message count would drift `has_more`
    and could stall a run instead of advancing past the gap. A caller
    should always resume from `next_position`, never
    `position + len(messages)`.
    """

    messages: tuple[NormalizedMessage, ...]
    position: int
    next_position: int
    total: int | None
    has_more: bool


class _JmapcClient(Protocol):
    """The small jmapc surface injected by recorded contract tests."""

    account_id: str
    jmap_session: Any

    @property
    def events(self) -> Iterable[object]: ...

    def request(self, method: object, *, raise_errors: bool = False) -> object: ...


ClientFactory = Callable[[str, str], _JmapcClient]


def _default_client_factory(host: str, api_token: str) -> _JmapcClient:
    """Import jmapc only when the dynamically selected provider needs it."""
    try:
        jmapc = import_module("jmapc")
        client_class = jmapc.Client
    except ImportError as exc:
        raise JmapError(
            "JMAP support requires the optional dependency: install spork[jmap]"
        ) from exc
    options: dict[str, object] = {}
    event_source_config = getattr(jmapc, "EventSourceConfig", None)
    if event_source_config is not None:
        options["event_source_config"] = event_source_config(
            types="EmailDelivery,Email", closeafter="no", ping=30
        )
    return cast(
        _JmapcClient,
        client_class.create_with_api_token(host=host, api_token=api_token, **options),
    )


def _method_types() -> tuple[type[Any], type[Any], type[Any], type[Any]]:
    """Load request classes lazily for the same optional-dependency boundary."""
    try:
        methods = import_module("jmapc.methods")
    except ImportError as exc:
        raise JmapError(
            "JMAP support requires the optional dependency: install spork[jmap]"
        ) from exc
    return methods.EmailChanges, methods.EmailGet, methods.MailboxGet, methods.ThreadGet


def _query_types() -> tuple[type[Any], type[Any]]:
    """Load the query-only request classes lazily, same optional-dependency boundary.

    Separate from `_method_types()` so that function's 4-tuple return
    doesn't grow a 5th element every existing unpacking call site has
    to account for — `query_messages()` is the only caller of these.
    """
    try:
        methods = import_module("jmapc.methods")
        models = import_module("jmapc.models")
    except ImportError as exc:
        raise JmapError(
            "JMAP support requires the optional dependency: install spork[jmap]"
        ) from exc
    return methods.EmailQuery, models.EmailQueryFilterCondition


def _write_types() -> tuple[type[Any], type[Any], type[Any], type[Any], type[Any]]:
    """Load the optional JMAP mutation models only for write operations."""
    try:
        methods = import_module("jmapc.methods")
        models = import_module("jmapc.models")
    except ImportError as exc:
        raise JmapError(
            "JMAP support requires the optional dependency: install spork[jmap]"
        ) from exc
    return (
        methods.EmailSet,
        models.Email,
        models.EmailAddress,
        models.EmailBodyPart,
        models.EmailBodyValue,
    )


def _field(value: object, *names: str) -> object:
    """Read an attribute or mapping key across jmapc model shapes."""
    for name in names:
        if isinstance(value, Mapping) and name in value:
            return value[name]
        result = getattr(value, name, None)
        if result is not None:
            return result
    return None


def _mapping(value: object) -> Mapping[object, object] | None:
    """Treat model/dict Session Object fields uniformly without trusting casts."""
    return value if isinstance(value, Mapping) else None


def _capability_names(value: object) -> set[object]:
    """Normalize jmapc's typed capabilities and plain Session dictionaries."""
    mapping = _mapping(value)
    if mapping is not None:
        return set(mapping)
    names: set[object] = set()
    if _field(value, "core") is not None:
        names.add("urn:ietf:params:jmap:core")
    extensions = _mapping(_field(value, "extensions"))
    if extensions is not None:
        names.update(extensions)
    urns = _field(value, "urns")
    if isinstance(urns, (set, frozenset, list, tuple)):
        names.update(urns)
    return names


def _session_permissions(session: object, account_id: str) -> JmapPermissions:
    """Validate core/mail read access and derive conservative mail write access."""
    capability_names = _capability_names(_field(session, "capabilities"))
    if "urn:ietf:params:jmap:core" not in capability_names:
        raise JmapError("JMAP Session Object has no core capability")
    if "urn:ietf:params:jmap:mail" not in capability_names:
        raise JmapError("JMAP Session Object has no mail capability")

    accounts = _mapping(_field(session, "accounts"))
    account = accounts.get(account_id) if accounts is not None else None

    primary_accounts = _field(session, "primary_accounts", "primaryAccounts")
    primary_mail_account = _field(primary_accounts, "mail", "urn:ietf:params:jmap:mail")
    if primary_mail_account != account_id:
        raise JmapError(f"JMAP account {account_id!r} is not the primary mail account")

    if account is not None:
        account_capabilities = _mapping(
            _field(account, "account_capabilities", "accountCapabilities")
        )
        if account_capabilities is None or "urn:ietf:params:jmap:mail" not in account_capabilities:
            raise JmapError(f"JMAP account {account_id!r} has no mail capability")

    is_read_only = _field(account, "is_read_only", "isReadOnly") if account is not None else None
    return JmapPermissions(
        can_read_mail=True,
        can_write_mail=is_read_only is False,
    )


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
        allow_writes: bool = False,
        expected_account_email: str | None = None,
    ) -> None:
        self._host = host
        self._api_token = api_token
        self._client_factory = client_factory
        self._allow_writes = allow_writes
        self._expected_account_email = expected_account_email
        self._client: _JmapcClient | None = None
        self._account_id: str | None = None
        self._inbox_id: str | None = None
        self._mailboxes: dict[str, tuple[str, str | None]] = {}
        self._permissions: JmapPermissions | None = None

    def connect(self) -> None:
        """Authenticate once and resolve the primary account and Inbox."""
        if self._client is not None:
            return

        _, _, mailbox_get, _ = _method_types()
        try:
            client = self._client_factory(self._host, self._api_token)
            session_username = _field(client.jmap_session, "username")
            if self._expected_account_email is not None:
                if not isinstance(session_username, str) or not session_username:
                    raise JmapError("JMAP session has no username for account verification")
                if session_username.casefold() != self._expected_account_email.casefold():
                    raise JmapError(
                        "authenticated account "
                        f"{session_username!r} does not match expected account "
                        f"{self._expected_account_email!r}"
                    )
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
            permissions = _session_permissions(client.jmap_session, account_id)
            if self._allow_writes and not permissions.can_write_mail:
                raise JmapError("JMAP account is read-only; write access was explicitly requested")
        except JmapError:
            raise
        except Exception as exc:
            raise JmapError(f"could not establish JMAP session: {exc}") from exc

        self._client = client
        self._account_id = account_id
        self._inbox_id = inbox_ids[0]
        self._mailboxes = {
            mailbox_id: (getattr(mailbox, "name", mailbox_id), getattr(mailbox, "role", None))
            for mailbox in mailboxes
            if isinstance((mailbox_id := getattr(mailbox, "id", None)), str)
        }
        self._permissions = permissions

    def _require_write_access(self) -> None:
        """Prevent mutation attempts unless session and config both allow them."""
        if not self._allow_writes:
            raise JmapError("JMAP client is read-only; write access is not enabled")
        if self._permissions is None:
            self.connect()
        if self._permissions is None or not self._permissions.can_write_mail:
            raise JmapError("JMAP account is read-only; write access is not enabled")

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
        email_changes, email_get, _, _ = _method_types()

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

    def query_messages(
        self, *, unread_only: bool = False, position: int = 0, limit: int = 50
    ) -> JmapQueryResult:
        """Windowed Email/query + Email/get over the Inbox — the explicit backfill read path.

        Deliberately not `fetch_new_messages()`: that method baselines
        on first run and never replays existing mail by design (§9.3,
        M1) — retroactively categorizing mail that arrived before spork
        was ever running needs its own, explicitly-named capability
        (docs/ROADMAP.md M8), not a flag on the live-ingestion method.
        Never called by the daemon's steady-state loop.
        """
        self.connect()
        _, email_get, _, _ = _method_types()
        email_query, filter_condition_cls = _query_types()

        query_filter = filter_condition_cls(
            in_mailbox=self._inbox_id,
            not_keyword="$seen" if unread_only else None,
        )
        query_response = self._request(
            email_query(filter=query_filter, position=position, limit=limit, calculate_total=True)
        )
        ids = getattr(query_response, "ids", None)
        response_position = getattr(query_response, "position", None)
        total = getattr(query_response, "total", None)
        if not isinstance(ids, list) or not all(isinstance(item, str) for item in ids):
            raise JmapError("Email/query returned invalid ids")
        if not isinstance(response_position, int):
            raise JmapError("Email/query returned invalid position")

        messages: tuple[NormalizedMessage, ...] = ()
        if ids:
            get_response = self._request(
                email_get(
                    ids=ids,
                    properties=self._email_properties(),
                    fetch_text_body_values=True,
                    fetch_html_body_values=False,
                )
            )
            emails = getattr(get_response, "data", None)
            if not isinstance(emails, list):
                raise JmapError("Email/get returned no message list")
            messages = tuple(self._normalize(email) for email in emails)

        # len(ids), not len(messages): the number of ids Email/query
        # actually matched at this window, regardless of how many
        # Email/get returned (see JmapQueryResult's docstring).
        next_position = response_position + len(ids)
        has_more = total is not None and next_position < total
        return JmapQueryResult(
            messages=messages,
            position=response_position,
            next_position=next_position,
            total=total,
            has_more=has_more,
        )

    def event_stream(self) -> Iterable[object]:
        """Return the connected jmapc EventSource stream for push handling."""
        self.connect()
        assert self._client is not None
        try:
            return self._client.events
        except Exception as exc:
            raise JmapError(f"could not open JMAP EventSource: {exc}") from exc

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

    def _current_email(self, message_id: str) -> tuple[str, Any]:
        """Read one message's state before an optimistic-concurrency update."""
        _, email_get, _, _ = _method_types()
        response = self._request(
            email_get(ids=[message_id], properties=["id", "mailboxIds", "keywords"])
        )
        state = getattr(response, "state", None)
        emails = getattr(response, "data", None)
        if not isinstance(state, str) or not state:
            raise JmapError("Email/get returned no state for a write")
        if not isinstance(emails, list) or len(emails) != 1:
            raise JmapError(f"Email/get returned no unique message for {message_id!r}")
        if getattr(emails[0], "id", None) != message_id:
            raise JmapError(f"Email/get returned the wrong message for {message_id!r}")
        return state, emails[0]

    def _mailbox_id(self, name: str, *, role: str | None = None) -> str:
        """Resolve a configured mailbox name or role from the session snapshot."""
        if role is not None:
            matches = [
                mailbox_id
                for mailbox_id, (_, item_role) in self._mailboxes.items()
                if item_role == role
            ]
        else:
            matches = [
                mailbox_id
                for mailbox_id, (mailbox_name, _) in self._mailboxes.items()
                if mailbox_name == name
            ]
        if len(matches) != 1:
            target = f"role {role!r}" if role is not None else f"mailbox {name!r}"
            raise JmapError(f"expected exactly one {target}; found {len(matches)}")
        return matches[0]

    def _email_set_update(self, state: str, message_id: str, update: dict[str, Any]) -> None:
        """Apply one guarded Email/set update and require its acknowledgement."""
        email_set, _, _, _, _ = _write_types()
        response = self._request(email_set(if_in_state=state, update={message_id: update}))
        updated = _mapping(_field(response, "updated"))
        if updated is None or message_id not in updated:
            raise JmapError(f"Email/set did not acknowledge update for {message_id!r}")

    def _draft_exists(self, drafts_id: str, message_id: str) -> bool:
        """Find an existing draft reply so uncertain retries stay idempotent."""
        email_query, filter_condition_cls = _query_types()
        response = self._request(
            email_query(
                filter=filter_condition_cls(
                    in_mailbox=drafts_id,
                    has_keyword="$draft",
                    header=["In-Reply-To", message_id],
                ),
                limit=1,
            )
        )
        ids = getattr(response, "ids", None)
        if not isinstance(ids, list) or not all(isinstance(item, str) for item in ids):
            raise JmapError("Email/query returned invalid draft IDs")
        return bool(ids)

    @staticmethod
    def _true_flags(value: object) -> dict[str, bool]:
        """Keep only active boolean flags from a JMAP map."""
        if not isinstance(value, Mapping):
            return {}
        return {
            key: True for key, enabled in value.items() if isinstance(key, str) and enabled is True
        }

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
        self._require_write_access()
        self.connect()
        if action.type == "ignore":
            return
        if action.type not in {"move", "tag"} or action.mailbox is None:
            raise JmapError(f"JMAP client cannot apply action {action!r}")
        target_id = self._mailbox_id(action.mailbox)
        state, email = self._current_email(message.message_id)
        current = self._true_flags(getattr(email, "mailbox_ids", None))
        if action.type == "move":
            mailbox_ids = {target_id: True}
        else:
            mailbox_ids = {**current, target_id: True}
        self._email_set_update(state, message.message_id, {"mailboxIds": mailbox_ids})

    def create_draft(self, message: NormalizedMessage, body: str) -> None:
        """Create a draft reply to `message` via `Email/set` into the
        account's Drafts mailbox — never `EmailSubmission/set`
        (docs/DESIGN.md §10.6, §11's "draft, never send" invariant)."""
        self._require_write_access()
        self.connect()
        drafts_id = self._mailbox_id("Drafts", role="drafts")
        message_id = message.headers.get("Message-ID")
        if message_id is None:
            raise JmapError("cannot create a threaded draft without a Message-ID")
        if self._draft_exists(drafts_id, message_id):
            return
        state, _ = self._current_email(message.message_id)
        email_set, email_type, address_type, body_part_type, body_value_type = _write_types()
        references = message.headers.get("References", "").split()
        if message_id is not None and message_id not in references:
            references.append(message_id)
        subject = (
            message.subject
            if message.subject.casefold().startswith("re:")
            else f"Re: {message.subject}"
        )
        draft = email_type(
            mailbox_ids={drafts_id: True},
            keywords={"$draft": True},
            to=[address_type(email=message.from_address)],
            subject=subject,
            in_reply_to=[message_id] if message_id is not None else None,
            references=references or None,
            text_body=[body_part_type(part_id="body")],
            body_values={"body": body_value_type(value=body)},
        )
        response = self._request(
            email_set(
                if_in_state=state,
                create={f"draft-{message.message_id}": draft},
            )
        )
        created = _mapping(_field(response, "created"))
        if created is None or f"draft-{message.message_id}" not in created:
            raise JmapError("Email/set did not acknowledge draft creation")

    def fetch_attachments(self, message: NormalizedMessage) -> Sequence[Attachment]:
        """Resolve `message`'s attachments via `Email/get`'s `blobId`s
        and a blob download (docs/DESIGN.md §9.5, M10) — unlike
        `get_thread_context()`/`list_mailboxes()`/`get_message()`
        (also reads, already real against injected jmapc-shaped
        responses), this one hasn't been built yet: real and buildable
        the same way, just out of this pass's scope, not blocked on
        anything the live account itself would prevent."""
        raise NotImplementedError(
            "JmapClient.fetch_attachments() is not implemented yet — see docs/ROADMAP.md M10"
        )

    def apply_keywords(self, message: NormalizedMessage, keywords: Sequence[str]) -> None:
        """Mutate `message`'s keywords map via `Email/set` (docs/DESIGN.md
        §9.5, M10) — the write side, alongside `apply_action()`/
        `create_draft()`."""
        self._require_write_access()
        self.connect()
        state, email = self._current_email(message.message_id)
        current = self._true_flags(getattr(email, "keywords", None))
        current.update({keyword: True for keyword in keywords if keyword})
        self._email_set_update(state, message.message_id, {"keywords": current})

    def get_thread_context(self, message: NormalizedMessage) -> ThreadContext:
        """Resolve prior subject and Sent-mail state through Thread/get."""
        self.connect()
        _, email_get, _, thread_get = _method_types()
        thread_response = self._request(thread_get(ids=[message.thread_id]))
        threads = getattr(thread_response, "data", None)
        if not isinstance(threads, list) or not threads:
            return ThreadContext(prior_subject=None, user_has_replied=False)
        email_ids = getattr(threads[0], "email_ids", None)
        if not isinstance(email_ids, list) or not all(isinstance(item, str) for item in email_ids):
            raise JmapError("Thread/get returned invalid email IDs")
        other_ids = [email_id for email_id in email_ids if email_id != message.message_id]
        if not other_ids:
            return ThreadContext(prior_subject=None, user_has_replied=False)
        response = self._request(email_get(ids=other_ids, properties=self._email_properties()))
        emails = getattr(response, "data", None)
        if not isinstance(emails, list):
            raise JmapError("Email/get returned no thread message list")
        sent_ids = {
            mailbox_id for mailbox_id, (_, role) in self._mailboxes.items() if role == "sent"
        }
        prior_subject = getattr(emails[0], "subject", None) if emails else None
        user_has_replied = any(
            bool(set(getattr(email, "mailbox_ids", {}).keys()) & sent_ids)
            for email in emails
            if isinstance(getattr(email, "mailbox_ids", None), dict)
        )
        return ThreadContext(
            prior_subject=prior_subject if isinstance(prior_subject, str) else None,
            user_has_replied=user_has_replied,
        )

    def list_mailboxes(self) -> Sequence[str]:
        """Return mailbox names from the authenticated Mailbox/get response."""
        self.connect()
        return [name for name, _ in self._mailboxes.values()]

    def get_message(self, message_id: str) -> NormalizedMessage:
        """Fetch and normalize one message by ID without mailbox mutation."""
        self.connect()
        _, email_get, _, _ = _method_types()
        response = self._request(email_get(ids=[message_id], properties=self._email_properties()))
        emails = getattr(response, "data", None)
        if not isinstance(emails, list) or not emails:
            raise JmapError(f"Email/get returned no message for {message_id!r}")
        return self._normalize(emails[0])

    @staticmethod
    def _email_properties() -> list[str]:
        """Keep read-side lookups aligned with new-mail normalization."""
        return [
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
        ]
