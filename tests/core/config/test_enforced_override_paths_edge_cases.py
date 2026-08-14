"""Failure/edge-case tests for enforced_override_paths().

Companion to test_enforced_override_paths.py's acceptance tests.
"""

from __future__ import annotations

from pathlib import Path

from spork.core.config.loader import enforced_override_paths


def test_enforced_override_paths_treats_a_list_value_as_one_leaf_not_recursed_into(
    tmp_path: Path,
) -> None:
    """A TOML array (e.g. tiering.allowed_categories) is a leaf value,
    not a table — it must not be mistaken for something to recurse
    into just because it's a compound type."""
    path = tmp_path / "enforced.toml"
    path.write_text('[tiering]\nallowed_categories = ["needs_reply", "spam"]\n')

    result = enforced_override_paths(enforced_config_path=path)

    assert result == {"tiering.allowed_categories"}


def test_enforced_override_paths_combines_flat_and_nested_keys_in_one_file(
    tmp_path: Path,
) -> None:
    path = tmp_path / "enforced.toml"
    path.write_text(
        """
        rules_path = "/etc/spork/rules.toml"

        [tiering]
        daily_call_budget = 200
        alert_threshold = 0.5
        """
    )

    result = enforced_override_paths(enforced_config_path=path)

    assert result == {"rules_path", "tiering.daily_call_budget", "tiering.alert_threshold"}


def test_enforced_override_paths_of_an_empty_file_is_empty(tmp_path: Path) -> None:
    path = tmp_path / "enforced.toml"
    path.write_text("")

    result = enforced_override_paths(enforced_config_path=path)

    assert result == set()
