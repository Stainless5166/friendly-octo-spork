"""Loads NormalizedMessages from a JSON file (docs/DESIGN.md §9.3).

Kept separate from `spork.core.providers.file.provider` for the same
reason `spork.core.rules.loader` is separate from `rules.schema`:
parsing/validating a file is a distinct concern from what a Provider
does with the result, and it's independently useful (e.g. for a future
`spork rules test --input <file>` path that's honest about testing
against a literal supplied file, never "recent mail").
"""

from __future__ import annotations

import json
from pathlib import Path

from spork.core.models import NormalizedMessage


class MessagesLoadError(ValueError):
    """Raised when a messages JSON file can't be parsed into NormalizedMessages.

    Covers a missing file, malformed JSON, a non-array top level, and a
    message object missing a required field — one catchable type
    instead of letting json/KeyError leak through unwrapped, the same
    fail-loud pattern as `spork.core.rules.loader.RulesLoadError`.
    """


def load_messages(path: str | Path) -> list[NormalizedMessage]:
    """Parse a JSON array of message objects into NormalizedMessage instances.

    Returns messages in file order — FileProvider replays them in that
    order via SequenceContentFetcher, so a caller relying on ordering
    (e.g. a rules-test fixture meant to exercise first-match-wins) can
    rely on the file's own order being preserved.
    """
    path = Path(path)
    try:
        raw = json.loads(path.read_text())
    except FileNotFoundError as exc:
        raise MessagesLoadError(f"messages file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise MessagesLoadError(f"invalid JSON in {path}: {exc}") from exc

    if not isinstance(raw, list):
        raise MessagesLoadError(
            f"{path} must contain a JSON array of messages, got {type(raw).__name__}"
        )

    messages: list[NormalizedMessage] = []
    for index, entry in enumerate(raw):
        if not isinstance(entry, dict):
            raise MessagesLoadError(
                f"{path}: message {index} must be a JSON object, got {type(entry).__name__}"
            )
        try:
            messages.append(
                NormalizedMessage(
                    message_id=entry["message_id"],
                    thread_id=entry["thread_id"],
                    from_address=entry["from_address"],
                    from_domain=entry["from_domain"],
                    subject=entry["subject"],
                    body_text=entry["body_text"],
                    headers=entry.get("headers", {}),
                    mailbox_ids=tuple(entry.get("mailbox_ids", ())),
                )
            )
        except KeyError as exc:
            raise MessagesLoadError(
                f"{path}: message {index} missing required field {exc}"
            ) from exc

    return messages
