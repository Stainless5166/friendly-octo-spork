"""Shared pytest fixtures for the spork test suite."""

from __future__ import annotations

from collections.abc import Callable, Mapping

import pytest
from spork.core.models import NormalizedMessage


@pytest.fixture
def make_message() -> Callable[..., NormalizedMessage]:
    """Factory for NormalizedMessage fixtures with sane defaults.

    Exists so individual tests only specify the one or two fields their
    scenario actually cares about, instead of repeating every required
    NormalizedMessage field in every test that needs a message.
    """

    def _make(
        *,
        message_id: str = "msg-1",
        thread_id: str = "thread-1",
        from_address: str = "someone@example.com",
        from_domain: str = "example.com",
        subject: str = "Test subject",
        body_text: str = "Test body.",
        headers: Mapping[str, str] | None = None,
        mailbox_ids: tuple[str, ...] = (),
    ) -> NormalizedMessage:
        return NormalizedMessage(
            message_id=message_id,
            thread_id=thread_id,
            from_address=from_address,
            from_domain=from_domain,
            subject=subject,
            body_text=body_text,
            headers=headers or {},
            mailbox_ids=mailbox_ids,
        )

    return _make
