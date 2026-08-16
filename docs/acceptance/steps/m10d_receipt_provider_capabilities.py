"""Real step bindings for the AttachmentFetcher/KeywordApplier Provider
capabilities (spork.core.providers.file.provider.FileProvider).

Fully implemented, unlike m10_receipt_archiving.feature (still @wip).
No live account or network -- a fresh tmp directory per scenario.
"""

from __future__ import annotations

import base64
import json
import tempfile
from pathlib import Path
from typing import Any

from behave import given, then, when

from spork.core.providers.file.provider import FileProvider


def _tmp_dir() -> Path:
    return Path(tempfile.mkdtemp(prefix="spork-m10d-acceptance-"))


def _write_messages(path: Path, *, with_attachment: bool) -> None:
    message: dict[str, Any] = {
        "message_id": "msg-1",
        "thread_id": "thread-1",
        "from_address": "billing@acmecloud.com",
        "from_domain": "acmecloud.com",
        "subject": "Your receipt",
        "body_text": "Thanks for your payment.",
    }
    if with_attachment:
        message["attachments"] = [
            {
                "filename": "invoice.pdf",
                "content_type": "application/pdf",
                "data_base64": base64.b64encode(b"%PDF-1.4 fake").decode("ascii"),
            }
        ]
    path.write_text(json.dumps([message]))


@given("a FileProvider fixture with a message that has one PDF attachment")
def fixture_with_pdf_attachment(context: Any) -> None:
    tmp_dir = _tmp_dir()
    messages_path = tmp_dir / "messages.json"
    _write_messages(messages_path, with_attachment=True)
    context.provider = FileProvider(messages_path, tmp_dir / "actions.jsonl")
    context.tmp_dir = tmp_dir


@given("a FileProvider fixture with a message that has no attachments")
def fixture_with_no_attachments(context: Any) -> None:
    tmp_dir = _tmp_dir()
    messages_path = tmp_dir / "messages.json"
    _write_messages(messages_path, with_attachment=False)
    context.provider = FileProvider(messages_path, tmp_dir / "actions.jsonl")
    context.tmp_dir = tmp_dir


@given("a FileProvider fixture with one message")
def fixture_with_one_message(context: Any) -> None:
    fixture_with_no_attachments(context)


@when("the attachment fetcher resolves that message's attachments")
def attachment_fetcher_resolves(context: Any) -> None:
    fetcher = context.provider.build_attachment_fetcher()
    from spork.core.models import NormalizedMessage

    message = NormalizedMessage(
        message_id="msg-1",
        thread_id="thread-1",
        from_address="billing@acmecloud.com",
        from_domain="acmecloud.com",
        subject="Your receipt",
        body_text="Thanks for your payment.",
    )
    context.attachments = fetcher.fetch_attachments(message)


@when('the keyword applier applies "{first}" and "{second}" to that message')
def keyword_applier_applies(context: Any, first: str, second: str) -> None:
    applier = context.provider.build_keyword_applier()
    from spork.core.models import NormalizedMessage

    message = NormalizedMessage(
        message_id="msg-1",
        thread_id="thread-1",
        from_address="billing@acmecloud.com",
        from_domain="acmecloud.com",
        subject="Your receipt",
        body_text="Thanks for your payment.",
    )
    applier.apply_keywords(message, [first, second])


@then('exactly one attachment named "{filename}" is returned')
def exactly_one_attachment_named(context: Any, filename: str) -> None:
    assert len(context.attachments) == 1
    assert context.attachments[0].filename == filename


@then("no attachments are returned")
def no_attachments_returned(context: Any) -> None:
    assert len(context.attachments) == 0


@then('the keywords log records "{first}" and "{second}" for that message')
def keywords_log_records(context: Any, first: str, second: str) -> None:
    log_path = context.tmp_dir / "keywords.jsonl"
    assert log_path.exists()
    entry = json.loads(log_path.read_text().splitlines()[0])
    assert entry["message_id"] == "msg-1"
    assert entry["keywords"] == [first, second]
