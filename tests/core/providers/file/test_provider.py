"""Acceptance tests for FileProvider, the local-file Adapter (docs/DESIGN.md §9.3).

Unlike JmapProvider (still NotImplementedError stubs pending a live
Fastmail session), FileProvider has no live-network blocker at all —
it's a second, fully real Provider implementation, and these tests
confirm the Provider/adapter abstraction actually holds for a backend
other than JMAP: build_source() really replays messages, and
build_action_applier() really records applied actions.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from spork.core.providers.base import MessageNotFoundError
from spork.core.providers.file.provider import FileProvider
from spork.core.rules.schema import Action
from spork.core.sources.triggered import TriggeredSource


def _write_messages(path: Path) -> None:
    path.write_text(
        json.dumps(
            [
                {
                    "message_id": "msg-1",
                    "thread_id": "thread-1",
                    "from_address": "a@example.com",
                    "from_domain": "example.com",
                    "subject": "Hello",
                    "body_text": "Hi there.",
                },
                {
                    "message_id": "msg-2",
                    "thread_id": "thread-2",
                    "from_address": "b@example.com",
                    "from_domain": "example.com",
                    "subject": "Hi again",
                    "body_text": "More text.",
                },
            ]
        )
    )


def test_build_source_returns_a_triggered_source(tmp_path: Path) -> None:
    """build_source() composes an ImmediateTrigger + SequenceContentFetcher
    via TriggeredSource — the same generic composition any Source
    consumer expects (docs/DESIGN.md §9.2), not a bespoke shape."""
    messages_path = tmp_path / "messages.json"
    _write_messages(messages_path)
    provider = FileProvider(messages_path, tmp_path / "actions.jsonl")

    source = provider.build_source()

    assert isinstance(source, TriggeredSource)


def test_source_poll_replays_every_message_then_settles_empty(tmp_path: Path) -> None:
    """The composed Source's first poll() returns every message in the
    file; once exhausted it settles into returning nothing, same as a
    live source that's caught up — proving the read side is real, not
    a placeholder."""
    messages_path = tmp_path / "messages.json"
    _write_messages(messages_path)
    provider = FileProvider(messages_path, tmp_path / "actions.jsonl")
    source = provider.build_source()

    first = source.poll()
    second = source.poll()

    assert [m.message_id for m in first] == ["msg-1", "msg-2"]
    assert second == []


def test_build_action_applier_returns_something_that_can_apply(
    tmp_path: Path, make_message
) -> None:
    """build_action_applier() returns an object satisfying ActionApplier
    (has a working .apply() method) — the write half of the Provider
    contract, per docs/DESIGN.md §9.3."""
    provider = FileProvider(tmp_path / "messages.json", tmp_path / "actions.jsonl")
    applier = provider.build_action_applier()

    applier.apply(make_message(message_id="msg-1"), Action(type="move", mailbox="Reading"))

    assert (tmp_path / "actions.jsonl").exists()


def test_action_applier_appends_one_jsonl_entry_per_apply_call(
    tmp_path: Path, make_message
) -> None:
    """Two apply() calls append two JSON-lines entries, in order, each
    recording the message and action involved — an inspectable,
    genuine record of what would have happened, not a silent no-op."""
    log_path = tmp_path / "actions.jsonl"
    provider = FileProvider(tmp_path / "messages.json", log_path)
    applier = provider.build_action_applier()

    applier.apply(make_message(message_id="msg-1"), Action(type="move", mailbox="Reading"))
    applier.apply(make_message(message_id="msg-2"), Action(type="tag", mailbox="Urgent"))

    lines = log_path.read_text().splitlines()
    entries = [json.loads(line) for line in lines]
    assert [e["message_id"] for e in entries] == ["msg-1", "msg-2"]
    assert entries[0]["action_type"] == "move"
    assert entries[0]["mailbox"] == "Reading"
    assert entries[1]["action_type"] == "tag"


def test_build_draft_creator_returns_something_that_can_create_a_draft(
    tmp_path: Path, make_message
) -> None:
    """build_draft_creator() returns an object satisfying DraftCreator
    (has a working .create_draft() method) — the third leg of the
    Provider contract per docs/DESIGN.md §10.6."""
    provider = FileProvider(tmp_path / "messages.json", tmp_path / "actions.jsonl")
    draft_creator = provider.build_draft_creator()

    draft_creator.create_draft(make_message(message_id="msg-1"), "Friday 2pm works for me.")

    assert (tmp_path / "drafts.jsonl").exists()


def test_draft_creator_appends_one_jsonl_entry_per_create_draft_call(
    tmp_path: Path, make_message
) -> None:
    """Two create_draft() calls append two JSON-lines entries, in
    order, each recording the message it's a reply to and the draft
    body — an inspectable record, same treatment as
    test_action_applier_appends_one_jsonl_entry_per_apply_call."""
    drafts_path = tmp_path / "drafts.jsonl"
    provider = FileProvider(
        tmp_path / "messages.json", tmp_path / "actions.jsonl", drafts_log_path=drafts_path
    )
    draft_creator = provider.build_draft_creator()

    draft_creator.create_draft(make_message(message_id="msg-1"), "Reply one.")
    draft_creator.create_draft(make_message(message_id="msg-2"), "Reply two.")

    lines = drafts_path.read_text().splitlines()
    entries = [json.loads(line) for line in lines]
    assert [e["in_reply_to_message_id"] for e in entries] == ["msg-1", "msg-2"]
    assert entries[0]["body"] == "Reply one."
    assert entries[1]["body"] == "Reply two."


def _write_threaded_messages(path: Path) -> None:
    """Two messages sharing thread-2: an earlier one spork sent
    (mailbox_ids includes "Sent"), and a later one that arrived after
    it — the shape get_thread_context()'s tests exercise."""
    path.write_text(
        json.dumps(
            [
                {
                    "message_id": "msg-solo",
                    "thread_id": "thread-1",
                    "from_address": "a@example.com",
                    "from_domain": "example.com",
                    "subject": "Solo",
                    "body_text": "No thread history.",
                    "mailbox_ids": ["Inbox"],
                },
                {
                    "message_id": "msg-sent",
                    "thread_id": "thread-2",
                    "from_address": "me@example.com",
                    "from_domain": "example.com",
                    "subject": "Re: Thursday call",
                    "body_text": "Friday works.",
                    "mailbox_ids": ["Sent"],
                },
                {
                    "message_id": "msg-reply",
                    "thread_id": "thread-2",
                    "from_address": "them@example.com",
                    "from_domain": "example.com",
                    "subject": "Re: Re: Thursday call",
                    "body_text": "Great, see you then.",
                    "mailbox_ids": ["Inbox", "Archive"],
                },
            ]
        )
    )


def test_build_thread_history_reader_returns_no_history_for_a_singleton_thread(
    tmp_path: Path, make_message
) -> None:
    """A message alone in its thread has no prior subject and no reply
    on record — real absence, not a placeholder default standing in
    for real data."""
    messages_path = tmp_path / "messages.json"
    _write_threaded_messages(messages_path)
    provider = FileProvider(messages_path, tmp_path / "actions.jsonl")
    reader = provider.build_thread_history_reader()

    context = reader.get_thread_context(make_message(message_id="msg-solo", thread_id="thread-1"))

    assert context.prior_subject is None
    assert context.user_has_replied is False


def test_thread_history_reader_finds_prior_subject_and_a_reply_already_sent(
    tmp_path: Path, make_message
) -> None:
    """Real thread history, derived from the other messages in the same
    file that share a thread_id — prior_subject from the earlier
    message, user_has_replied True because one of them carries "Sent"
    in mailbox_ids (docs/DESIGN.md §9.3)."""
    messages_path = tmp_path / "messages.json"
    _write_threaded_messages(messages_path)
    provider = FileProvider(messages_path, tmp_path / "actions.jsonl")
    reader = provider.build_thread_history_reader()

    context = reader.get_thread_context(make_message(message_id="msg-reply", thread_id="thread-2"))

    assert context.prior_subject == "Re: Thursday call"
    assert context.user_has_replied is True


def test_build_mailbox_lister_returns_the_explicit_available_mailboxes_when_given(
    tmp_path: Path,
) -> None:
    """An explicit available_mailboxes= constructor argument wins over
    anything derived from the messages file — a deployment's real
    mailbox list, not guessed."""
    messages_path = tmp_path / "messages.json"
    _write_threaded_messages(messages_path)
    provider = FileProvider(
        messages_path,
        tmp_path / "actions.jsonl",
        available_mailboxes=["Inbox", "Needs-Review"],
    )
    lister = provider.build_mailbox_lister()

    assert lister.list_mailboxes() == ["Inbox", "Needs-Review"]


def test_mailbox_lister_derives_the_sorted_union_of_mailbox_ids_when_not_given(
    tmp_path: Path,
) -> None:
    """With no available_mailboxes= given, the mailbox list is derived
    from real data already in the file — the sorted union of every
    message's mailbox_ids — rather than an empty/invented default."""
    messages_path = tmp_path / "messages.json"
    _write_threaded_messages(messages_path)
    provider = FileProvider(messages_path, tmp_path / "actions.jsonl")
    lister = provider.build_mailbox_lister()

    assert lister.list_mailboxes() == ["Archive", "Inbox", "Sent"]


def test_build_message_lookup_finds_a_message_by_id(tmp_path: Path) -> None:
    """get_message() (docs/DESIGN.md §13, for spork reclassify) scans
    the same fixture file build_source() replays from and returns the
    matching NormalizedMessage."""
    messages_path = tmp_path / "messages.json"
    _write_messages(messages_path)
    provider = FileProvider(messages_path, tmp_path / "actions.jsonl")
    lookup = provider.build_message_lookup()

    message = lookup.get_message("msg-2")

    assert message.message_id == "msg-2"
    assert message.subject == "Hi again"


def test_message_lookup_raises_a_clean_error_for_an_unknown_id(tmp_path: Path) -> None:
    messages_path = tmp_path / "messages.json"
    _write_messages(messages_path)
    provider = FileProvider(messages_path, tmp_path / "actions.jsonl")
    lookup = provider.build_message_lookup()

    with pytest.raises(MessageNotFoundError):
        lookup.get_message("no-such-message")


def test_drafts_log_defaults_next_to_the_actions_log(tmp_path: Path, make_message) -> None:
    """Not passing drafts_log_path= explicitly still produces a real,
    inspectable log — a drafts.jsonl next to actions_log_path — so
    existing two-arg FileProvider(...) call sites keep working
    unchanged."""
    provider = FileProvider(tmp_path / "messages.json", tmp_path / "actions.jsonl")
    draft_creator = provider.build_draft_creator()

    draft_creator.create_draft(make_message(), "A reply.")

    assert (tmp_path / "drafts.jsonl").exists()
    assert not (tmp_path / "actions.jsonl").exists()  # nothing applied, only drafted


def test_build_attachment_fetcher_returns_attachments_from_the_fixture(
    tmp_path: Path, make_message
) -> None:
    """build_attachment_fetcher() (docs/DESIGN.md §9.5, M10) reads the
    same fixture file build_source() replays from -- attachments are
    real, not invented, matching build_thread_history_reader()'s own
    "derive from the fixture" convention."""
    import base64

    messages_path = tmp_path / "messages.json"
    messages_path.write_text(
        json.dumps(
            [
                {
                    "message_id": "msg-1",
                    "thread_id": "thread-1",
                    "from_address": "a@example.com",
                    "from_domain": "example.com",
                    "subject": "Receipt",
                    "body_text": "Thanks.",
                    "attachments": [
                        {
                            "filename": "invoice.pdf",
                            "content_type": "application/pdf",
                            "data_base64": base64.b64encode(b"%PDF-1.4 fake").decode("ascii"),
                        }
                    ],
                }
            ]
        )
    )
    provider = FileProvider(messages_path, tmp_path / "actions.jsonl")
    fetcher = provider.build_attachment_fetcher()

    attachments = fetcher.fetch_attachments(make_message(message_id="msg-1"))

    assert [a.filename for a in attachments] == ["invoice.pdf"]
    assert attachments[0].data == b"%PDF-1.4 fake"


def test_build_attachment_fetcher_returns_empty_for_a_message_with_none(
    tmp_path: Path, make_message
) -> None:
    messages_path = tmp_path / "messages.json"
    _write_messages(messages_path)
    provider = FileProvider(messages_path, tmp_path / "actions.jsonl")
    fetcher = provider.build_attachment_fetcher()

    assert fetcher.fetch_attachments(make_message(message_id="msg-1")) == ()


def test_build_keyword_applier_logs_applied_keywords(tmp_path: Path, make_message) -> None:
    """build_keyword_applier() (docs/DESIGN.md §9.5, M10) logs to its
    own JSON-lines file, distinct from actions/drafts -- a keyword
    isn't a mailbox action or a draft."""
    provider = FileProvider(tmp_path / "messages.json", tmp_path / "actions.jsonl")
    applier = provider.build_keyword_applier()

    applier.apply_keywords(make_message(message_id="msg-1"), ["receipt", "company:Acme Cloud"])

    log_path = tmp_path / "keywords.jsonl"
    assert log_path.exists()
    entry = json.loads(log_path.read_text().splitlines()[0])
    assert entry["message_id"] == "msg-1"
    assert entry["keywords"] == ["receipt", "company:Acme Cloud"]


def test_keywords_log_defaults_next_to_the_actions_log(tmp_path: Path, make_message) -> None:
    provider = FileProvider(tmp_path / "messages.json", tmp_path / "actions.jsonl")
    applier = provider.build_keyword_applier()

    applier.apply_keywords(make_message(), ["receipt"])

    assert (tmp_path / "keywords.jsonl").exists()
    assert not (tmp_path / "actions.jsonl").exists()
