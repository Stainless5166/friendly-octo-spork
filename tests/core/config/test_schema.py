"""Acceptance tests for spork.core.config.schema (docs/DESIGN.md §7.2/§6.4).

Pure pydantic model tests — no TOML, no filesystem, no environment
variables. `loader.py` is what actually reads config.toml and
constructs these; this file only proves the schema itself matches
what §7.2 documents.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from spork.core.config.schema import BackendSpec, SporkConfig, TieringConfig


def _minimal_sporkconfig(**overrides: object) -> SporkConfig:
    defaults: dict[str, object] = {
        "provider": BackendSpec(spec="spork.core.providers.jmap.provider:JmapProvider"),
        "llm": BackendSpec(spec="spork.core.llm.clients.anthropic:AnthropicLLMClient"),
        "alerts": BackendSpec(spec="spork.core.alerts.log:LoggingAlerter"),
        "rules_path": Path("~/.config/spork/rules.toml"),
        "db_path": Path("~/.local/share/spork/state.sqlite3"),
    }
    defaults.update(overrides)
    return SporkConfig(**defaults)  # type: ignore[arg-type]


def test_sporkconfig_constructs_with_all_required_fields() -> None:
    """The five fields §7.2's example marks as always-present (provider/
    llm/alerts specs, rules_path, db_path) are enough on their own —
    everything else has a documented default."""
    config = _minimal_sporkconfig()

    assert config.provider.spec == "spork.core.providers.jmap.provider:JmapProvider"
    assert config.rules_path == Path("~/.config/spork/rules.toml")


def test_sporkconfig_rejects_unknown_fields() -> None:
    """A typo'd top-level key (extra="forbid") is rejected loudly, same
    convention as Condition/Action/Rule (rules/schema.py) and every
    other hand-edited TOML schema in this codebase."""
    with pytest.raises(ValidationError):
        _minimal_sporkconfig(nonexistent_field="x")


def test_sporkconfig_socket_path_defaults_to_none() -> None:
    """Unset means "resolve via paths.resolve_socket_path() at load
    time" (loader.py's job) — the schema itself just records "not
    overridden.\""""
    config = _minimal_sporkconfig()

    assert config.socket_path is None


def test_sporkconfig_tiering_defaults_when_omitted() -> None:
    """Omitting [tiering] entirely still produces a full TieringConfig
    with every documented default, not a missing-field error."""
    config = _minimal_sporkconfig()

    assert config.tiering == TieringConfig()


def test_tieringconfig_defaults_match_documented_values() -> None:
    """Every default matches §7.2's example config.toml exactly — the
    example isn't illustrative-only, it's what an empty [tiering]
    table actually resolves to."""
    tiering = TieringConfig()

    assert tiering.default_unmatched_action == "escalate"
    assert tiering.alert_threshold == 0.55
    assert tiering.autoact_threshold == 0.85
    assert tiering.daily_call_budget == 200
    assert tiering.max_body_chars == 4000
    assert tiering.local_classifier is None
    assert tiering.allowed_categories == []


def test_backendspec_kwargs_defaults_to_empty_dict() -> None:
    """A backend needing no constructor kwargs (LoggingAlerter, e.g.)
    doesn't have to write an empty [alerts.kwargs] table."""
    spec = BackendSpec(spec="spork.core.alerts.log:LoggingAlerter")

    assert spec.kwargs == {}
