"""Acceptance tests for spork.core.config.loader.enforced_override_paths() (docs/DESIGN.md §7.2/§13).

An injectable `enforced_config_path` argument, same reasoning as
`load_config()`'s own tier-path overrides (see test_loader.py) — tests
never touch the real fixed `/etc/spork/enforced.toml`.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from spork.core.config.loader import ConfigLoadError, enforced_override_paths


def test_enforced_override_paths_with_no_enforced_file_is_empty(tmp_path: Path) -> None:
    """No enforced.toml at all: nothing is enforced, an empty set —
    not an error, every tier is optional."""
    result = enforced_override_paths(enforced_config_path=tmp_path / "does-not-exist.toml")

    assert result == set()


def test_enforced_override_paths_includes_flat_top_level_keys(tmp_path: Path) -> None:
    path = tmp_path / "enforced.toml"
    path.write_text('rules_path = "/etc/spork/rules.toml"\n')

    result = enforced_override_paths(enforced_config_path=path)

    assert "rules_path" in result


def test_enforced_override_paths_flattens_nested_tables_with_dotted_names(tmp_path: Path) -> None:
    path = tmp_path / "enforced.toml"
    path.write_text("[tiering]\ndaily_call_budget = 200\n")

    result = enforced_override_paths(enforced_config_path=path)

    assert result == {"tiering.daily_call_budget"}


def test_enforced_override_paths_flattens_doubly_nested_kwargs_tables(tmp_path: Path) -> None:
    path = tmp_path / "enforced.toml"
    path.write_text('[provider.kwargs]\nhost = "api.fastmail.com"\n')

    result = enforced_override_paths(enforced_config_path=path)

    assert result == {"provider.kwargs.host"}


def test_enforced_override_paths_raises_configloaderror_for_malformed_toml(tmp_path: Path) -> None:
    path = tmp_path / "enforced.toml"
    path.write_text("this is not [ valid toml")

    with pytest.raises(ConfigLoadError):
        enforced_override_paths(enforced_config_path=path)
