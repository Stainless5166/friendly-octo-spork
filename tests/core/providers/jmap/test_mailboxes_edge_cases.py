"""Failure/edge-case tests for JMAP mailbox role resolution.

Companion to test_mailboxes.py's acceptance tests — covers a failed
fetch not poisoning the cache, and a server reporting two mailboxes
with the same role.
"""

from __future__ import annotations

import pytest

from spork.core.providers.jmap.mailboxes import (
    AmbiguousMailboxRoleError,
    MailboxInfo,
    MailboxResolver,
)


def test_a_failed_fetch_is_not_cached() -> None:
    """resolve() raising due to a fetch error must not prevent the next
    resolve() call from retrying — a transient JMAP error shouldn't
    permanently break role resolution for the rest of the session."""
    attempts = 0

    def flaky_fetch() -> list[MailboxInfo]:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise RuntimeError("simulated transient JMAP error")
        return [MailboxInfo(id="mb-1", name="Inbox", role="inbox")]

    resolver = MailboxResolver(flaky_fetch)

    with pytest.raises(RuntimeError):
        resolver.resolve("inbox")

    assert resolver.resolve("inbox") == "mb-1"
    assert attempts == 2


def test_duplicate_role_across_mailboxes_raises_ambiguous_error() -> None:
    """Two mailboxes claiming the same role is a server-side anomaly the
    resolver refuses to silently pick a winner for — acting on the
    wrong one of two "inbox"-role mailboxes is exactly the kind of
    misfile this tool exists to prevent."""
    resolver = MailboxResolver(
        lambda: [
            MailboxInfo(id="mb-1", name="Inbox", role="inbox"),
            MailboxInfo(id="mb-2", name="Inbox Copy", role="inbox"),
        ]
    )

    with pytest.raises(AmbiguousMailboxRoleError):
        resolver.resolve("inbox")


def test_mailboxes_without_a_role_are_ignored() -> None:
    """A custom, role-less mailbox (most user-created folders) doesn't
    interfere with resolving the roles that *are* present — the
    resolver must skip it rather than erroring or mis-mapping it."""
    resolver = MailboxResolver(
        lambda: [
            MailboxInfo(id="mb-1", name="Inbox", role="inbox"),
            MailboxInfo(id="mb-2", name="My Custom Folder", role=None),
        ]
    )

    assert resolver.resolve("inbox") == "mb-1"
