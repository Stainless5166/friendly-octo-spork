"""Failure/edge-case tests for the concrete message-pipeline modules.

Companion to test_modules.py's acceptance tests — covers each
module's MissingMetaError, raised when it's run before the module it
depends on.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from spork.core.actions.executor import ActionExecutor
from spork.core.models import NormalizedMessage
from spork.core.pipeline.core import Payload
from spork.core.pipeline.meta import MessageMeta, MissingMetaError
from spork.core.pipeline.modules import (
    ApplyActionFilter,
    MarkProcessedFilter,
    WriteAuditEntryFilter,
)
from spork.core.rules.schema import Action
from spork.core.state.db import StateDB


class _RecordingApplier:
    def apply(self, message: NormalizedMessage, action: Action) -> None:
        pass


def _payload(make_message, **meta_overrides: object) -> Payload[MessageMeta]:
    defaults: dict[str, object] = {
        "message": make_message(message_id="msg-1"),
        "rules": [],
        "default_unmatched_action": Action(type="escalate"),
    }
    defaults.update(meta_overrides)
    return Payload(text="", meta=MessageMeta(**defaults))  # type: ignore[arg-type]


def test_apply_action_filter_raises_when_verdict_is_missing(make_message) -> None:
    """Run standalone, without RuleEvaluationSelector having set
    meta.verdict, ApplyActionFilter fails loud rather than crashing on
    a None attribute access."""
    executor = ActionExecutor(_RecordingApplier())

    with pytest.raises(MissingMetaError):
        ApplyActionFilter(executor).apply(_payload(make_message))


def test_write_audit_entry_filter_raises_when_ts_is_missing(tmp_path: Path, make_message) -> None:
    """No TimestampFilter has run yet — meta.ts is still None."""
    with StateDB(tmp_path / "state.sqlite3") as db:
        with pytest.raises(MissingMetaError):
            WriteAuditEntryFilter(db).apply(_payload(make_message, audit_event="action_applied"))


def test_write_audit_entry_filter_raises_when_audit_event_is_missing(
    tmp_path: Path, make_message
) -> None:
    """Neither ApplyActionFilter nor RecordEscalationFilter has run —
    meta.audit_event is still None."""
    with StateDB(tmp_path / "state.sqlite3") as db:
        with pytest.raises(MissingMetaError):
            WriteAuditEntryFilter(db).apply(_payload(make_message, ts="t1"))


def test_mark_processed_filter_raises_when_verdict_is_missing(tmp_path: Path, make_message) -> None:
    """No RuleEvaluationSelector has run — meta.verdict is still None."""
    with StateDB(tmp_path / "state.sqlite3") as db:
        with pytest.raises(MissingMetaError):
            MarkProcessedFilter(db).apply(_payload(make_message, ts="t1"))


def test_mark_processed_filter_raises_when_ts_is_missing(tmp_path: Path, make_message) -> None:
    """No TimestampFilter has run — meta.ts is still None, even though
    meta.verdict is present."""
    from spork.core.rules.engine import RuleVerdict

    verdict = RuleVerdict(action=Action(type="ignore"), matched_rule_id=None)

    with StateDB(tmp_path / "state.sqlite3") as db:
        with pytest.raises(MissingMetaError):
            MarkProcessedFilter(db).apply(_payload(make_message, verdict=verdict))
