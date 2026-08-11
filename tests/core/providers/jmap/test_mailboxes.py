"""Acceptance tests for JMAP mailbox role resolution (docs/DESIGN.md §6.2).

MailboxResolver is exercised against a plain injected fetch callable —
never a real jmapc client or live JMAP session — so these test only
spork's own resolve/cache logic.
"""

from __future__ import annotations

import pytest

from spork.core.providers.jmap.mailboxes import (
    MailboxInfo,
    MailboxResolver,
    UnknownMailboxRoleError,
)


def test_resolve_returns_mailbox_id_for_known_role() -> None:
    """resolve() maps a JMAP role name to that mailbox's id."""
    resolver = MailboxResolver(
        lambda: [
            MailboxInfo(id="mb-1", name="Inbox", role="inbox"),
            MailboxInfo(id="mb-2", name="Drafts", role="drafts"),
        ]
    )

    assert resolver.resolve("inbox") == "mb-1"
    assert resolver.resolve("drafts") == "mb-2"


def test_resolve_only_fetches_once_across_multiple_calls() -> None:
    """Repeated resolve() calls reuse the first fetch (caching), rather
    than hitting the JMAP session again for every lookup."""
    calls = 0

    def fetch() -> list[MailboxInfo]:
        nonlocal calls
        calls += 1
        return [MailboxInfo(id="mb-1", name="Inbox", role="inbox")]

    resolver = MailboxResolver(fetch)

    resolver.resolve("inbox")
    resolver.resolve("inbox")
    resolver.resolve("inbox")

    assert calls == 1


def test_resolve_raises_clear_error_for_unknown_role() -> None:
    """A role with no matching mailbox fails loudly, not with None/KeyError."""
    resolver = MailboxResolver(lambda: [MailboxInfo(id="mb-1", name="Inbox", role="inbox")])

    with pytest.raises(UnknownMailboxRoleError):
        resolver.resolve("drafts")


def test_refresh_forces_a_re_fetch_on_next_resolve() -> None:
    """refresh() invalidates the cache so the next resolve() re-fetches —
    needed after e.g. creating a new custom mailbox mid-session."""
    calls = 0

    def fetch() -> list[MailboxInfo]:
        nonlocal calls
        calls += 1
        return [MailboxInfo(id="mb-1", name="Inbox", role="inbox")]

    resolver = MailboxResolver(fetch)
    resolver.resolve("inbox")
    resolver.refresh()
    resolver.resolve("inbox")

    assert calls == 2
