"""Failure/edge-case tests for the rules.toml loader.

Companion to test_loader.py's acceptance tests.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from spork.core.rules.loader import RulesLoadError, load_rules


def test_load_rules_raises_for_unknown_field_in_a_rule(tmp_path: Path) -> None:
    """A typo'd field name (e.g. "enalbed" instead of "enabled") is
    rejected rather than silently ignored while the mistyped field
    quietly falls back to its default — a rule author who thinks
    they've disabled a rule needs to know if that didn't work."""
    path = tmp_path / "rules.toml"
    path.write_text(
        """
        [[rule]]
        id = "typo-rule"
        when = { always = true }
        action = { type = "ignore" }
        enalbed = false
        """
    )

    with pytest.raises(RulesLoadError):
        load_rules(path)


def test_load_rules_raises_for_unknown_field_in_a_condition(tmp_path: Path) -> None:
    """Same, but for a typo'd field inside `when` — e.g.
    "form_domain_in" instead of "from_domain_in", which would
    otherwise silently match nothing instead of failing to load."""
    path = tmp_path / "rules.toml"
    path.write_text(
        """
        [[rule]]
        id = "typo-condition"
        when = { form_domain_in = ["example.com"] }
        action = { type = "ignore" }
        """
    )

    with pytest.raises(RulesLoadError):
        load_rules(path)
