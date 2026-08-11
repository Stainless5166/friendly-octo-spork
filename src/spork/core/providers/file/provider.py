"""FileProvider: a local-file Adapter to the Provider contract (§9.3).

Exists to prove the Provider/adapter abstraction generalizes beyond
JMAP with a second, *fully real* implementation — nothing here raises
NotImplementedError, unlike JmapProvider which is still blocked on a
live Fastmail session (docs/ROADMAP.md M1). It is explicitly not a
stand-in for "recent mail" from any live backend: spork has no local
mail store to substitute for one (docs/DESIGN.md §13), and this
doesn't pretend to be one either. It reads a literal, explicitly
supplied JSON file of messages, and on the write side appends every
applied action to a JSON-lines log — a real, inspectable backend in
its own right, useful for local dev/demo/CI work.
"""

from __future__ import annotations

import json
from pathlib import Path

from spork.core.models import NormalizedMessage
from spork.core.providers.base import ActionApplier
from spork.core.providers.file.messages import load_messages
from spork.core.rules.schema import Action
from spork.core.sources.base import Source
from spork.core.sources.replay import ImmediateTrigger, SequenceContentFetcher
from spork.core.sources.triggered import TriggeredSource


class _FileActionApplier:
    """Appends each applied action to a JSON-lines log instead of mutating anything.

    There's no real mailbox underneath a FileProvider to move a
    message into — recording what *would* have happened, one JSON
    object per line, is the whole point (see this module's docstring).
    """

    def __init__(self, log_path: Path) -> None:
        self._log_path = log_path

    def apply(self, message: NormalizedMessage, action: Action) -> None:
        entry = {
            "message_id": message.message_id,
            "action_type": action.type,
            "mailbox": action.mailbox,
        }
        with self._log_path.open("a") as f:
            f.write(json.dumps(entry) + "\n")


class FileProvider:
    """Adapts a local JSON messages file to the `Provider` contract.

    `build_source()` replays every message in `messages_path` exactly
    once via `ImmediateTrigger` + `SequenceContentFetcher`
    (`spork.core.sources.replay`) — no polling, no push, just the
    fixed set of messages the file contains at the moment `poll()` is
    first called. `build_action_applier()` is the write-side
    counterpart: it logs to `actions_log_path` rather than mutating
    anything, since there's no real backend underneath to mutate.
    """

    def __init__(self, messages_path: str | Path, actions_log_path: str | Path) -> None:
        self._messages_path = Path(messages_path)
        self._actions_log_path = Path(actions_log_path)

    def build_source(self) -> Source:
        messages = load_messages(self._messages_path)
        # batch_size = len(messages): a FileProvider has no notion of
        # "new since last poll" the way a live source does, so the
        # first poll() hands back everything the file contains, in one
        # batch, rather than trickling it out one message at a time.
        fetcher = SequenceContentFetcher(messages, batch_size=max(len(messages), 1))
        return TriggeredSource(ImmediateTrigger(), fetcher)

    def build_action_applier(self) -> ActionApplier:
        return _FileActionApplier(self._actions_log_path)
