"""Property-based tests for spork.core.pipeline.tier2.escalate (docs/DESIGN.md §16.1).

Companion to test_escalate.py's example-based tests. Two properties
worth stating over generated inputs rather than one example apiece:
parse_to_addresses()'s comma-split/strip parsing, and
escalate_message_or_quarantine()'s quarantine-vs-propagate boundary —
QUARANTINABLE_ERRORS classifies by exception *type* alone, so every
member must always be quarantined and every non-member must always
propagate, whatever message string or call-site origin it carries.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from spork.core.actions.executor import ActionExecutor
from spork.core.alerts.log import LoggingAlerter
from spork.core.config.schema import TieringConfig
from spork.core.context.clients.null import NullContextProvider
from spork.core.llm.base import LLMResult, VerdictRequest
from spork.core.models import NormalizedMessage
from spork.core.pipeline.observer import PipelineObserver
from spork.core.pipeline.tier2.escalate import (
    QUARANTINABLE_ERRORS,
    QuarantinedMessage,
    escalate_message_or_quarantine,
    parse_to_addresses,
)
from spork.core.providers.base import ThreadContext
from spork.core.state.db import StateDB

# Address-shaped tokens with no comma inside — parse_to_addresses()
# splits on comma, so a token containing one would fuse with its
# neighbor and defeat the property being tested, not the code.
_TOKEN = st.text(alphabet=st.characters(blacklist_characters=","), min_size=1, max_size=15).filter(
    lambda s: s.strip() != ""
)


@given(tokens=st.lists(_TOKEN, max_size=6), padding=st.text(alphabet=" \t", max_size=3))
def test_parse_to_addresses_recovers_every_stripped_nonempty_token(
    tokens: list[str], padding: str
) -> None:
    """Joining any generated token list with a comma (plus variable
    whitespace padding) and parsing it back always recovers exactly the
    stripped tokens, in order — for any tokens Hypothesis generates, not
    just a couple of hand-picked addresses."""
    header = (padding + ",").join(t + padding for t in tokens)
    message = NormalizedMessage(
        message_id="msg-1",
        thread_id="thread-1",
        from_address="a@example.com",
        from_domain="example.com",
        subject="",
        body_text="",
        headers={"To": header},
    )

    assert parse_to_addresses(message) == tuple(t.strip() for t in tokens)


@given(to_header=st.text(max_size=30))
def test_parse_to_addresses_never_returns_an_empty_string(to_header: str) -> None:
    """No element of the result is ever "" — empty-after-split entries
    (a leading/trailing/doubled comma) are always dropped, for any
    generated header text."""
    message = NormalizedMessage(
        message_id="msg-1",
        thread_id="thread-1",
        from_address="a@example.com",
        from_domain="example.com",
        subject="",
        body_text="",
        headers={"To": to_header},
    )

    assert "" not in parse_to_addresses(message)


class _RecordingApplier:
    def __init__(self) -> None:
        self.calls: list[tuple[NormalizedMessage, object]] = []

    def apply(self, message: NormalizedMessage, action: object) -> None:
        self.calls.append((message, action))


class _RecordingDraftCreator:
    def create_draft(self, in_reply_to: NormalizedMessage, body: str) -> None:
        pass


class _EmptyMailboxLister:
    def list_mailboxes(self) -> list[str]:
        return []


class _EmptyThreadHistoryReader:
    def get_thread_context(self, message: NormalizedMessage) -> ThreadContext:
        return ThreadContext(prior_subject=None, user_has_replied=False)


class _RaisingLLMClient:
    """Raises whatever exception instance it's constructed with — the
    property under test is escalate_message_or_quarantine()'s own
    except-by-type boundary, not which real call site a given error
    type happens to originate from in production."""

    def __init__(self, exc: Exception) -> None:
        self._exc = exc

    def get_verdict(self, request: VerdictRequest) -> LLMResult:
        raise self._exc


def _run(tmp_path: Path, exc: Exception) -> QuarantinedMessage | None:
    message = NormalizedMessage(
        message_id="msg-1",
        thread_id="thread-1",
        from_address="a@example.com",
        from_domain="example.com",
        subject="Urgent",
        body_text="",
    )
    with StateDB(tmp_path / "state.sqlite3") as state_db:
        return escalate_message_or_quarantine(
            message,
            thread_history_reader=_EmptyThreadHistoryReader(),
            mailbox_lister=_EmptyMailboxLister(),
            llm_client=_RaisingLLMClient(exc),
            executor=ActionExecutor(_RecordingApplier()),
            draft_creator=_RecordingDraftCreator(),
            state_db=state_db,
            ops=PipelineObserver(LoggingAlerter()),
            tiering=TieringConfig(allowed_categories=["needs_reply"]),
            context_provider=NullContextProvider(),
        )


@given(
    exc_type=st.sampled_from(QUARANTINABLE_ERRORS),
    message_text=st.text(max_size=30),
)
def test_every_quarantinable_error_type_is_always_quarantined(
    tmp_path_factory: pytest.TempPathFactory, exc_type: type[Exception], message_text: str
) -> None:
    """Every member of QUARANTINABLE_ERRORS, with any message string
    Hypothesis generates, always comes back as a QuarantinedMessage —
    never propagates, whatever exact text the model/validation/executor
    failure happened to carry."""
    tmp_path = tmp_path_factory.mktemp("escalate-fuzz")

    result = _run(tmp_path, exc_type(message_text))

    assert isinstance(result, QuarantinedMessage)
    assert result.reason == message_text


@given(
    exc_type=st.sampled_from([RuntimeError, KeyError, TypeError, ValueError]),
    message_text=st.text(max_size=30),
)
def test_every_non_quarantinable_error_type_always_propagates(
    tmp_path_factory: pytest.TempPathFactory, exc_type: type[Exception], message_text: str
) -> None:
    """None of these four types are QUARANTINABLE_ERRORS members (plain
    ValueError is not ActionExecutionError, its own subclass) — every
    one of them always propagates rather than being silently absorbed,
    for any message string Hypothesis generates."""
    tmp_path = tmp_path_factory.mktemp("escalate-fuzz")

    with pytest.raises(exc_type):
        _run(tmp_path, exc_type(message_text))
