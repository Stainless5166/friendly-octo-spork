"""A FileProvider that counts calls to its Tier 2 capability builders.

Exists only to let `spork backfill`'s CLI tests (subprocess-based, so
no in-process hook access) assert that `build_thread_history_reader()`/
`build_mailbox_lister()`/`build_draft_creator()` are built once per
run, not once per escalated message (PR #20 review finding #2) —
counts persist to a small JSON file so the test process can read them
back after the subprocess exits.
"""

from __future__ import annotations

import json
from pathlib import Path

from spork.core.providers.base import DraftCreator, MailboxLister, ThreadHistoryReader
from spork.core.providers.file.provider import FileProvider


class CountingFileProvider(FileProvider):
    """Same behavior as `FileProvider`, plus a call counter written to disk."""

    def __init__(
        self,
        messages_path: str | Path,
        actions_log_path: str | Path,
        counts_path: str | Path,
        **kwargs: object,
    ) -> None:
        super().__init__(messages_path, actions_log_path, **kwargs)  # type: ignore[arg-type]
        self._counts_path = Path(counts_path)

    def _bump(self, name: str) -> None:
        counts: dict[str, int] = {}
        if self._counts_path.exists():
            counts = json.loads(self._counts_path.read_text())
        counts[name] = counts.get(name, 0) + 1
        self._counts_path.write_text(json.dumps(counts))

    def build_thread_history_reader(self) -> ThreadHistoryReader:
        self._bump("build_thread_history_reader")
        return super().build_thread_history_reader()

    def build_mailbox_lister(self) -> MailboxLister:
        self._bump("build_mailbox_lister")
        return super().build_mailbox_lister()

    def build_draft_creator(self) -> DraftCreator:
        self._bump("build_draft_creator")
        return super().build_draft_creator()
