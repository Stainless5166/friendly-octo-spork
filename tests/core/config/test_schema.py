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

from spork.core.config.schema import (
    BackendSpec,
    LLMRecordingConfig,
    ReceiptArchiveConfig,
    SporkConfig,
    TieringConfig,
)


def _minimal_sporkconfig(**overrides: object) -> SporkConfig:
    defaults: dict[str, object] = {
        "provider": BackendSpec(spec="spork.core.providers.jmap.provider:JmapProvider"),
        "llm": BackendSpec(spec="spork.core.llm.clients.litellm:LiteLLMClient"),
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


def test_sporkconfig_log_level_defaults_to_info() -> None:
    """docs/DESIGN.md §6.2/§7.2 (M7): omitting log_level entirely is a
    valid, fully-specified config, same as every other defaulted field."""
    config = _minimal_sporkconfig()

    assert config.log_level == "INFO"


@pytest.mark.parametrize("level", ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])
def test_sporkconfig_accepts_every_documented_log_level(level: str) -> None:
    config = _minimal_sporkconfig(log_level=level)

    assert config.log_level == level


def test_sporkconfig_rejects_an_unknown_log_level() -> None:
    """A typo'd or lowercase log_level fails loudly at config-load time
    (ConfigLoadError wraps this — see test_loader.py), not silently at
    some later logging.setLevel() call."""
    with pytest.raises(ValidationError):
        _minimal_sporkconfig(log_level="verbose")


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


def test_backendspec_accepts_secret_name_mappings_separately_from_kwargs() -> None:
    spec = BackendSpec(
        spec="example:Backend",
        kwargs={"host": "api.example.com"},
        secret_kwargs={"api_token": "JMAP_API_TOKEN"},
    )

    assert spec.kwargs == {"host": "api.example.com"}
    assert spec.secret_kwargs == {"api_token": "JMAP_API_TOKEN"}


def test_backendspec_rejects_a_constructor_key_in_both_config_and_secrets() -> None:
    with pytest.raises(ValidationError, match="api_token"):
        BackendSpec(
            spec="example:Backend",
            kwargs={"api_token": "plaintext"},
            secret_kwargs={"api_token": "JMAP_API_TOKEN"},
        )


def test_sporkconfig_accepts_optional_llm_recording_configuration(tmp_path: Path) -> None:
    config = _minimal_sporkconfig(
        llm_recording=LLMRecordingConfig(corpus_path=tmp_path / "corpus" / "live.jsonl")
    )

    assert config.llm_recording is not None
    assert config.llm_recording.corpus_path == tmp_path / "corpus" / "live.jsonl"


def test_sporkconfig_context_defaults_to_none() -> None:
    """Unset means "no knowledgebase configured" — a real, valid state
    (spork.core.context.clients.null.NullContextProvider), not a
    missing-field error; same convention as tiering.local_classifier."""
    config = _minimal_sporkconfig()

    assert config.context is None


def test_sporkconfig_accepts_optional_context_provider_configuration() -> None:
    config = _minimal_sporkconfig(
        context=BackendSpec(spec="spork.core.context.clients.null:NullContextProvider")
    )

    assert config.context is not None
    assert config.context.spec == "spork.core.context.clients.null:NullContextProvider"


def test_sporkconfig_receipt_archive_defaults_to_none() -> None:
    """Unset means the feature is off entirely -- an archive_receipt
    rule with no [receipt_archive] configured fails at pipeline
    composition, not silently (docs/DESIGN.md §9.5, M10)."""
    config = _minimal_sporkconfig()

    assert config.receipt_archive is None


def test_sporkconfig_accepts_optional_receipt_archive_configuration(tmp_path: Path) -> None:
    config = _minimal_sporkconfig(
        receipt_archive=ReceiptArchiveConfig(
            output_dir=tmp_path / "receipts",
            extraction=BackendSpec(spec="spork.core.receipts.llm:RecordedReceiptExtractionClient"),
        )
    )

    assert config.receipt_archive is not None
    assert config.receipt_archive.output_dir == tmp_path / "receipts"
    assert (
        config.receipt_archive.extraction.spec
        == "spork.core.receipts.llm:RecordedReceiptExtractionClient"
    )


def test_receiptarchiveconfig_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        ReceiptArchiveConfig(
            output_dir=Path("/tmp/receipts"),
            extraction=BackendSpec(spec="a:B"),
            bogus_field="x",  # type: ignore[call-arg]
        )


def test_receiptarchiveconfig_requires_an_extraction_backend() -> None:
    """No default -- same "must be explicit, no fallback that could
    surprise later" stance provider/llm/alerts already have on
    SporkConfig itself; the one narrow Tier 2 fallback call has to
    know which backend to use."""
    with pytest.raises(ValidationError):
        ReceiptArchiveConfig(output_dir=Path("/tmp/receipts"))  # type: ignore[call-arg]
