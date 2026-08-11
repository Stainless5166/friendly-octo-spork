"""Failure/edge-case tests for FileProvider.

Companion to test_provider.py's acceptance tests.
"""

from __future__ import annotations

import json
from pathlib import Path

from spork.core.providers.file.provider import FileProvider
from spork.core.rules.schema import Action


def test_build_source_with_an_empty_messages_file_polls_to_nothing(tmp_path: Path) -> None:
    """An empty messages.json is a legitimate, valid FileProvider input
    — poll() returns an empty batch, not an error."""
    messages_path = tmp_path / "messages.json"
    messages_path.write_text("[]")
    provider = FileProvider(messages_path, tmp_path / "actions.jsonl")

    source = provider.build_source()

    assert source.poll() == []


def test_action_applier_appends_across_separate_build_calls(tmp_path: Path, make_message) -> None:
    """Two separately-obtained appliers pointed at the same log path
    both append to it rather than truncating — build_action_applier()
    doesn't own exclusive state that a second call would reset."""
    log_path = tmp_path / "actions.jsonl"
    provider = FileProvider(tmp_path / "messages.json", log_path)

    provider.build_action_applier().apply(make_message(message_id="msg-1"), Action(type="ignore"))
    provider.build_action_applier().apply(make_message(message_id="msg-2"), Action(type="ignore"))

    entries = [json.loads(line) for line in log_path.read_text().splitlines()]
    assert [e["message_id"] for e in entries] == ["msg-1", "msg-2"]


def test_file_provider_accepts_str_paths(tmp_path: Path, make_message) -> None:
    """str paths work the same as Path objects for both constructor
    arguments — FileProvider shouldn't force every caller to wrap them."""
    messages_path = tmp_path / "messages.json"
    messages_path.write_text("[]")
    log_path = tmp_path / "actions.jsonl"
    provider = FileProvider(str(messages_path), str(log_path))

    assert provider.build_source().poll() == []
    provider.build_action_applier().apply(make_message(), Action(type="ignore"))
    assert log_path.exists()
