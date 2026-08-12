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


def test_draft_creator_appends_across_separate_build_calls(tmp_path: Path, make_message) -> None:
    """Same guarantee as actions: two separately-obtained draft
    creators pointed at the same log path both append rather than
    truncating."""
    drafts_path = tmp_path / "drafts.jsonl"
    provider = FileProvider(
        tmp_path / "messages.json", tmp_path / "actions.jsonl", drafts_log_path=drafts_path
    )

    provider.build_draft_creator().create_draft(make_message(message_id="msg-1"), "First.")
    provider.build_draft_creator().create_draft(make_message(message_id="msg-2"), "Second.")

    entries = [json.loads(line) for line in drafts_path.read_text().splitlines()]
    assert [e["in_reply_to_message_id"] for e in entries] == ["msg-1", "msg-2"]


def test_create_draft_with_an_empty_body_is_recorded_as_is(tmp_path: Path, make_message) -> None:
    """An empty draft body is a legitimate (if unusual) input — recorded
    as an empty string, not silently dropped or rejected."""
    drafts_path = tmp_path / "drafts.jsonl"
    provider = FileProvider(
        tmp_path / "messages.json", tmp_path / "actions.jsonl", drafts_log_path=drafts_path
    )

    provider.build_draft_creator().create_draft(make_message(), "")

    entry = json.loads(drafts_path.read_text().splitlines()[0])
    assert entry["body"] == ""


def test_pointing_drafts_log_path_at_the_actions_log_path_interleaves_both_shapes(
    tmp_path: Path, make_message
) -> None:
    """EDGE CASE FOUND WHILE TESTING: nothing stops a caller from
    passing the same path for both actions_log_path and
    drafts_log_path — each writer only ever appends, so both differently-
    shaped JSON objects (one with "action_type"/"mailbox", the other
    with "in_reply_to_message_id"/"body") land in the same file, in
    call order. Not guarded against here: FileProvider is a dev/CI
    tool, not a production data store, and rejecting the collision
    would add a check with no real backend behind it to justify.
    Documented so a reader who does this on purpose (or by copy-paste
    mistake) finds the actual behavior here rather than being surprised
    by a file that doesn't match either log's expected schema."""
    shared_path = tmp_path / "shared.jsonl"
    provider = FileProvider(tmp_path / "messages.json", shared_path, drafts_log_path=shared_path)

    provider.build_action_applier().apply(make_message(message_id="msg-1"), Action(type="ignore"))
    provider.build_draft_creator().create_draft(make_message(message_id="msg-2"), "A reply.")

    entries = [json.loads(line) for line in shared_path.read_text().splitlines()]
    assert "action_type" in entries[0]
    assert "in_reply_to_message_id" in entries[1]
