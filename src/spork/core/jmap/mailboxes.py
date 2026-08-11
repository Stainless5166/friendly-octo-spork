"""Mailbox role resolution + caching (docs/DESIGN.md §6.2 step 2).

The daemon resolves mailbox roles (inbox, drafts, ...) to JMAP mailbox
IDs exactly once per session and reuses that mapping for every
action-executor call afterward — re-fetching `Mailbox/get` on every
single message would be wasted round trips for data that essentially
never changes mid-session.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class MailboxInfo:
    """The subset of a JMAP `Mailbox` object role resolution needs.

    Not a full mirror of JMAP's Mailbox object on purpose — this type
    exists solely to decouple `MailboxResolver` from jmapc's actual
    response shape, the same reason `NormalizedMessage` exists for
    messages (spork.core.models).
    """

    id: str
    name: str
    role: str | None


class UnknownMailboxRoleError(KeyError):
    """Raised when a role (e.g. "inbox") has no matching mailbox.

    A distinct type rather than a bare KeyError so `spork doctor` can
    catch precisely this and report a specific, actionable problem
    ("your account has no Drafts mailbox?") rather than a generic
    lookup failure.
    """


class MailboxResolver:
    """Resolves JMAP mailbox roles to mailbox IDs, fetched once and cached.

    Takes a plain fetch callable rather than a jmapc client directly,
    so it can be unit-tested (and reused for a future non-JMAP
    transport, in principle) without any real session — see
    docs/DESIGN.md §6.1's decoupling rationale.
    """

    def __init__(self, fetch_mailboxes: Callable[[], Sequence[MailboxInfo]]) -> None:
        self._fetch = fetch_mailboxes
        self._by_role: dict[str, str] | None = None

    def resolve(self, role: str) -> str:
        """Return the mailbox id for `role`, fetching (once) if needed."""
        if self._by_role is None:
            self._by_role = self._build_role_map(self._fetch())
        try:
            return self._by_role[role]
        except KeyError as exc:
            known = sorted(self._by_role)
            raise UnknownMailboxRoleError(
                f"no mailbox with role {role!r}; known roles: {known}"
            ) from exc

    def refresh(self) -> None:
        """Drop the cached role map so the next resolve() re-fetches.

        Needed after anything that can change the account's mailbox
        set mid-session — e.g. a custom mailbox created via the CLI.
        """
        self._by_role = None

    @staticmethod
    def _build_role_map(mailboxes: Sequence[MailboxInfo]) -> dict[str, str]:
        """Build the role->id map, skipping mailboxes with no role.

        Split out from resolve() so the "how do raw mailboxes become a
        lookup table" step is a pure, independently-readable function.
        """
        return {mailbox.role: mailbox.id for mailbox in mailboxes if mailbox.role is not None}
