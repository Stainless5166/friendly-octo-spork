"""Failure/edge-case tests for classifier dispatch fan-out.

Companion to test_dispatcher.py's acceptance tests.
"""

from __future__ import annotations

from spork.core.dispatch.dispatcher import Dispatcher


def test_dispatch_with_no_targets_returns_empty_dict(make_message) -> None:
    """A Dispatcher configured with zero targets is a no-op, not an
    error — whether that's actually useful is a Combiner's problem
    (see test_combine_edge_cases.py), not the Dispatcher's."""
    dispatcher: Dispatcher = Dispatcher({})

    assert dispatcher.dispatch(make_message()) == {}
