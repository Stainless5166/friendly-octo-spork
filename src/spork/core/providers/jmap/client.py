"""JMAP session bootstrap, batched fetch, and mutation (docs/DESIGN.md §6.1, §8, §9.3).

Wraps `jmapc` session establishment, `Email/query`+`Email/get`
batching, and `Email/set` mutation. `connect()`, `fetch_new_messages()`,
and `apply_action()` are deliberately unimplemented: doing any of them
for real means an actual `jmapc` session against a live Fastmail
account, which this environment can't exercise honestly. Rather than
leaving the class's shape unspecified until that becomes possible,
it's settled now — constructor args, method names, signatures — and
each method raises a clear, catchable `NotImplementedError` in the
meantime (docs/ROADMAP.md M1), so callers get a specific signal
instead of the class silently pretending to work.
"""

from __future__ import annotations

from collections.abc import Sequence

from spork.core.models import NormalizedMessage
from spork.core.rules.schema import Action


class JmapClient:
    """A JMAP session against a single Fastmail account.

    `host`/`api_token` are stored but not used yet — real jmapc
    integration is where they'd actually be consumed.
    """

    def __init__(self, host: str, api_token: str) -> None:
        self._host = host
        self._api_token = api_token

    def connect(self) -> None:
        """Establish the JMAP session (docs/DESIGN.md §6.2 step 2)."""
        raise NotImplementedError(
            "JmapClient.connect() requires a live jmapc session — "
            "not implemented yet, see docs/ROADMAP.md M1"
        )

    def fetch_new_messages(self, since_cursor: str | None) -> Sequence[NormalizedMessage]:
        """Batched `Email/query` + `Email/get` fetch of new mail since
        `since_cursor` (docs/DESIGN.md §8), None meaning "from the start"."""
        raise NotImplementedError(
            "JmapClient.fetch_new_messages() requires a live jmapc session — "
            "not implemented yet, see docs/ROADMAP.md M1"
        )

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
