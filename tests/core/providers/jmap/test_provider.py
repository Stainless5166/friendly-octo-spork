"""Acceptance tests for JmapProvider, the JMAP Adapter (docs/DESIGN.md §9.3).

JmapClient/JmapPushTrigger are still NotImplementedError stubs (they
need a live Fastmail session — docs/ROADMAP.md M1), so these tests
only cover composition: does build_source() assemble the right pieces,
and does the resulting Source correctly propagate the underlying
stub's NotImplementedError when actually used.
"""

from __future__ import annotations

import pytest

from spork.core.providers.jmap.client import JmapClient
from spork.core.providers.jmap.provider import (
    JmapProvider,
    _JmapActionApplier,
    _JmapContentFetcher,
    _JmapDraftCreator,
)
from spork.core.rules.schema import Action
from spork.core.sources.triggered import TriggeredSource


def test_build_source_returns_a_triggered_source() -> None:
    """build_source() composes a JmapPushTrigger + JMAP fetcher via
    TriggeredSource — the same composition any Source consumer expects
    from docs/DESIGN.md §9.2, not a bespoke JMAP-only shape."""
    provider = JmapProvider(host="api.fastmail.com", api_token="fake-token")

    source = provider.build_source()

    assert isinstance(source, TriggeredSource)


def test_source_poll_raises_not_implemented() -> None:
    """Polling the composed Source raises NotImplementedError, propagated
    from JmapPushTrigger.wait() — proving JmapProvider actually wires the
    real (if still-stubbed) pieces together, not placeholders of its own."""
    provider = JmapProvider(host="api.fastmail.com", api_token="fake-token")
    source = provider.build_source()

    with pytest.raises(NotImplementedError):
        source.poll()


def test_content_fetcher_delegates_to_the_client_directly() -> None:
    """The fetcher half of build_source()'s composition also raises
    NotImplementedError on its own (not just when reached via the
    trigger firing first) — it's a real delegation to
    JmapClient.fetch_new_messages(), not a second placeholder."""
    client = JmapClient(host="api.fastmail.com", api_token="fake-token")
    fetcher = _JmapContentFetcher(client)

    with pytest.raises(NotImplementedError):
        fetcher.fetch()


def test_build_action_applier_returns_something_that_can_apply(make_message) -> None:
    """build_action_applier() returns an object satisfying ActionApplier
    (has an .apply() method) — the write half of the Provider contract,
    per docs/DESIGN.md §9.3's "read and write are the same relationship"."""
    provider = JmapProvider(host="api.fastmail.com", api_token="fake-token")

    applier = provider.build_action_applier()

    with pytest.raises(NotImplementedError):
        applier.apply(make_message(), Action(type="move", mailbox="Reading"))


def test_action_applier_delegates_to_the_client_directly(make_message) -> None:
    """The applier is a real delegation to JmapClient.apply_action(),
    not a second placeholder — mirrors
    test_content_fetcher_delegates_to_the_client_directly."""
    client = JmapClient(host="api.fastmail.com", api_token="fake-token")
    applier = _JmapActionApplier(client)

    with pytest.raises(NotImplementedError):
        applier.apply(make_message(), Action(type="tag", mailbox="Urgent"))


def test_build_draft_creator_returns_something_that_can_create_a_draft(make_message) -> None:
    """build_draft_creator() returns an object satisfying DraftCreator
    (has a .create_draft() method) — the third leg of the Provider
    contract per docs/DESIGN.md §10.6."""
    provider = JmapProvider(host="api.fastmail.com", api_token="fake-token")

    draft_creator = provider.build_draft_creator()

    with pytest.raises(NotImplementedError):
        draft_creator.create_draft(make_message(), "Friday 2pm works for me.")


def test_draft_creator_delegates_to_the_client_directly(make_message) -> None:
    """The draft creator is a real delegation to JmapClient.create_draft(),
    not a second placeholder — mirrors
    test_action_applier_delegates_to_the_client_directly."""
    client = JmapClient(host="api.fastmail.com", api_token="fake-token")
    draft_creator = _JmapDraftCreator(client)

    with pytest.raises(NotImplementedError):
        draft_creator.create_draft(make_message(), "Friday 2pm works for me.")
