"""Loads Attachments from a JSON messages file (docs/DESIGN.md §9.5, M10).

Kept separate from `spork.core.providers.file.messages` for the same
reason that module is separate from `rules.schema` — parsing/validating
a file is a distinct concern from what a Provider does with the
result. Reads the same fixture file `load_messages()` does, but pulls
each message's optional `"attachments"` array instead of its message
fields — `load_messages()` itself ignores that key entirely, so one
fixture file serves both loaders without either needing to know about
the other's fields.
"""

from __future__ import annotations

import base64
import binascii
import json
from pathlib import Path

from spork.core.models import Attachment


class AttachmentsLoadError(ValueError):
    """Raised when a messages file's attachments can't be parsed.

    Covers a missing file, malformed JSON, a non-array top level, an
    attachment missing a required field, and invalid base64 data — one
    catchable type, same fail-loud pattern as `MessagesLoadError`.
    """


def load_attachments(path: str | Path) -> dict[str, list[Attachment]]:
    """Parse every message's `"attachments"` array into `Attachment`s,
    keyed by `message_id`. A message with no `"attachments"` key (or
    an empty one) maps to `[]`, not a missing key — every message in
    the file gets an entry, so a caller never needs to special-case
    "never had any."
    """
    path = Path(path)
    try:
        raw = json.loads(path.read_text())
    except FileNotFoundError as exc:
        raise AttachmentsLoadError(f"messages file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise AttachmentsLoadError(f"invalid JSON in {path}: {exc}") from exc

    if not isinstance(raw, list):
        raise AttachmentsLoadError(
            f"{path} must contain a JSON array of messages, got {type(raw).__name__}"
        )

    attachments_by_message_id: dict[str, list[Attachment]] = {}
    for index, entry in enumerate(raw):
        if not isinstance(entry, dict):
            raise AttachmentsLoadError(
                f"{path}: message {index} must be a JSON object, got {type(entry).__name__}"
            )
        try:
            message_id = entry["message_id"]
        except KeyError as exc:
            raise AttachmentsLoadError(f"{path}: message {index} missing 'message_id'") from exc

        parsed: list[Attachment] = []
        for att_index, att in enumerate(entry.get("attachments", [])):
            if not isinstance(att, dict):
                raise AttachmentsLoadError(
                    f"{path}: {message_id!r} attachment {att_index} must be a JSON object"
                )
            try:
                filename = att["filename"]
                content_type = att["content_type"]
                data_base64 = att["data_base64"]
            except KeyError as exc:
                raise AttachmentsLoadError(
                    f"{path}: {message_id!r} attachment {att_index} missing required field {exc}"
                ) from exc
            try:
                data = base64.b64decode(data_base64, validate=True)
            except (binascii.Error, ValueError) as exc:
                raise AttachmentsLoadError(
                    f"{path}: {message_id!r} attachment {att_index} has invalid base64 data"
                ) from exc
            parsed.append(Attachment(filename=filename, content_type=content_type, data=data))

        attachments_by_message_id[message_id] = parsed

    return attachments_by_message_id
