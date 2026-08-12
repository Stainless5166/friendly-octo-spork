"""Failure/edge-case tests for spork.core.config.loader.load_config().

Companion to test_loader.py's acceptance tests.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from spork.core.config.loader import ConfigLoadError, load_config

_MINIMAL_TOML = """
rules_path = "/home/will/.config/spork/rules.toml"
db_path = "/home/will/.local/share/spork/state.sqlite3"
socket_path = "/home/will/.local/state/spork/sporkd.sock"

[provider]
spec = "spork.core.providers.file.provider:FileProvider"

[llm]
spec = "spork.core.llm.clients.recorded:RecordedLLMClient"

[alerts]
spec = "spork.core.alerts.log:LoggingAlerter"
"""


def _write(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    return path


def test_load_config_raises_configloaderror_for_an_unreadable_path(tmp_path: Path) -> None:
    """A path that exists but can't be read as a file (a directory, in
    this case — deterministic regardless of the running user's
    privilege level, unlike chmod-based permission denial) is a clear
    ConfigLoadError, not a raw OSError."""
    user_path = tmp_path / "user" / "config.toml"
    user_path.mkdir(parents=True)  # a directory, not a file
    missing_default = tmp_path / "default" / "config.toml"
    missing_enforced = tmp_path / "enforced.toml"

    with pytest.raises(ConfigLoadError):
        load_config(
            user_config_path=user_path,
            system_default_config_paths=[missing_default],
            enforced_config_path=missing_enforced,
        )


def test_load_config_treats_an_empty_but_present_tier_file_as_a_noop(tmp_path: Path) -> None:
    """A tier file that exists but is empty (0 bytes) contributes zero
    overrides, same as a missing file — not a parse error."""
    user_path = _write(tmp_path / "user" / "config.toml", _MINIMAL_TOML)
    empty_enforced = _write(tmp_path / "enforced.toml", "")
    missing_default = tmp_path / "default" / "config.toml"

    config = load_config(
        user_config_path=user_path,
        system_default_config_paths=[missing_default],
        enforced_config_path=empty_enforced,
    )

    assert config.provider.spec == "spork.core.providers.file.provider:FileProvider"


def test_load_config_deep_merges_nested_backendspec_kwargs(tmp_path: Path) -> None:
    """The recursive merge goes deeper than one level: system-default
    sets two provider.kwargs entries, user overrides only one — both
    survive, proving nested-table merge isn't limited to [tiering]."""
    system_default_path = _write(
        tmp_path / "default" / "config.toml",
        _MINIMAL_TOML
        + '\n[provider.kwargs]\nhost = "api.fastmail.com"\naccount_email = "old@example.com"\n',
    )
    user_path = _write(
        tmp_path / "user" / "config.toml",
        '[provider.kwargs]\naccount_email = "new@example.com"\n',
    )
    missing_enforced = tmp_path / "enforced.toml"

    config = load_config(
        user_config_path=user_path,
        system_default_config_paths=[system_default_path],
        enforced_config_path=missing_enforced,
    )

    assert config.provider.kwargs == {
        "host": "api.fastmail.com",
        "account_email": "new@example.com",
    }


def test_load_config_system_default_uses_first_existing_match_only(tmp_path: Path) -> None:
    """Given several system_default_config_paths, only the first one
    that actually exists is read — later candidates are ignored even
    if they'd also parse fine, matching XDG_CONFIG_DIRS's own
    first-match-wins precedence (paths.py)."""
    missing_first = tmp_path / "missing" / "config.toml"
    real_second = _write(
        tmp_path / "second" / "config.toml",
        _MINIMAL_TOML + "\n[tiering]\ndaily_call_budget = 111\n",
    )
    real_third_but_ignored = _write(
        tmp_path / "third" / "config.toml",
        _MINIMAL_TOML + "\n[tiering]\ndaily_call_budget = 999\n",
    )
    user_path = tmp_path / "user" / "config.toml"  # missing entirely
    missing_enforced = tmp_path / "enforced.toml"

    config = load_config(
        user_config_path=user_path,
        system_default_config_paths=[missing_first, real_second, real_third_but_ignored],
        enforced_config_path=missing_enforced,
    )

    assert config.tiering.daily_call_budget == 111
