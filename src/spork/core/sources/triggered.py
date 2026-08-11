"""Composing an independent Trigger and ContentFetcher into a Source.

The generic case from docs/DESIGN.md §9.2's Trigger/ContentFetcher
split: whenever the two genuinely vary independently (an interval
timer + an IMAP fetch; an immediate no-op trigger + a replayed
fixture), this is the only glue needed — no bespoke Source
implementation required.
"""

from __future__ import annotations

from collections.abc import Sequence

from spork.core.models import NormalizedMessage
from spork.core.sources.base import ContentFetcher, Trigger


class TriggeredSource:
    """A Source built from one Trigger and one ContentFetcher.

    poll() always triggers before fetching, never the reverse — a
    fetcher's result can legitimately depend on the trigger having
    already fired (e.g. a timer's tick determining what "new" means
    for the next fetch window).
    """

    def __init__(self, trigger: Trigger, fetcher: ContentFetcher) -> None:
        self._trigger = trigger
        self._fetcher = fetcher

    def poll(self) -> Sequence[NormalizedMessage]:
        self._trigger.wait()
        return self._fetcher.fetch()
