"""Acceptance tests for the rules.toml loader (docs/DESIGN.md §7.5).

Kept separate from schema validation itself (spork.core.rules.schema is
already tested via the engine tests) — these cover the file-level
concerns: parsing, wrapping errors clearly, and duplicate-id detection
across a whole file.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from spork.core.rules.loader import RulesLoadError, load_rules


def test_load_rules_parses_valid_rules_toml(tmp_path: Path) -> None:
    """A well-formed rules.toml parses into Rule objects with the
    expected fields, in file order."""
    path = tmp_path / "rules.toml"
    path.write_text(
        """
        [[rule]]
        id = "catch-newsletter"
        description = "File newsletters"
        when = { from_domain_in = ["newsletter.example.com"] }
        action = { type = "move", mailbox = "Reading" }

        [[rule]]
        id = "fallback"
        when = { always = true }
        action = { type = "escalate" }
        """
    )

    rules = load_rules(path)

    assert [r.id for r in rules] == ["catch-newsletter", "fallback"]
    assert rules[0].action.type == "move"
    assert rules[0].action.mailbox == "Reading"
    assert rules[1].when.always is True


def test_load_rules_returns_empty_list_for_no_rules(tmp_path: Path) -> None:
    """A syntactically valid file with no [[rule]] entries at all is
    zero rules, not an error — an empty rules.toml is a legitimate
    (if inert) starting point."""
    path = tmp_path / "rules.toml"
    path.write_text("")

    assert load_rules(path) == []


def test_load_rules_raises_for_malformed_toml(tmp_path: Path) -> None:
    """Broken TOML syntax is a clear RulesLoadError, not a raw
    tomllib.TOMLDecodeError leaking through unwrapped."""
    path = tmp_path / "rules.toml"
    path.write_text("this is not [ valid toml")

    with pytest.raises(RulesLoadError):
        load_rules(path)


def test_load_rules_raises_for_invalid_rule_fields(tmp_path: Path) -> None:
    """A rule whose action.type isn't one of the closed set of valid
    values is a clear RulesLoadError, not a raw pydantic ValidationError."""
    path = tmp_path / "rules.toml"
    path.write_text(
        """
        [[rule]]
        id = "bad-rule"
        when = { always = true }
        action = { type = "delete" }
        """
    )

    with pytest.raises(RulesLoadError):
        load_rules(path)


def test_load_rules_raises_for_duplicate_ids(tmp_path: Path) -> None:
    """Two rules sharing an id is a clear RulesLoadError — ids must be
    unique for spork rules enable/disable <id> (M5) to mean anything."""
    path = tmp_path / "rules.toml"
    path.write_text(
        """
        [[rule]]
        id = "dup"
        when = { always = true }
        action = { type = "ignore" }

        [[rule]]
        id = "dup"
        when = { always = true }
        action = { type = "escalate" }
        """
    )

    with pytest.raises(RulesLoadError):
        load_rules(path)


def test_load_rules_raises_for_missing_file(tmp_path: Path) -> None:
    """A path that doesn't exist is a clear RulesLoadError, not a raw
    FileNotFoundError."""
    with pytest.raises(RulesLoadError):
        load_rules(tmp_path / "does-not-exist.toml")
