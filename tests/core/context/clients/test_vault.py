"""Acceptance test for MarkdownVaultContextProvider — a settled-shape
stub (docs/DESIGN.md §10.8, docs/ROADMAP.md M9), same pattern as
`JmapClient`: the real constructor argument and method signature are
settled now, `get_context()` raises `NotImplementedError` until the
actual retrieval algorithm (keyword vs. embedding-based ranking over
real note content) is decided — not blocked on a live network call
the way `JmapClient` is, but on a real design choice this environment
has no real vault content to validate against honestly.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from spork.core.context.clients.vault import MarkdownVaultContextProvider


def test_get_context_raises_not_implemented_yet(tmp_path: Path, make_message) -> None:
    provider = MarkdownVaultContextProvider(vault_path=tmp_path)

    with pytest.raises(NotImplementedError, match="docs/ROADMAP.md"):
        provider.get_context(make_message(message_id="msg-1"))


def test_constructor_settles_the_real_shape_without_reading_the_vault(tmp_path: Path) -> None:
    """Constructing one doesn't require the vault directory to exist
    yet or do any I/O — same "settle the shape, defer the behavior"
    split JmapClient's constructor makes."""
    provider = MarkdownVaultContextProvider(vault_path=tmp_path / "does-not-exist-yet")

    assert provider.vault_path == tmp_path / "does-not-exist-yet"
