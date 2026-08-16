"""Acceptance tests for `spork config show/edit` (docs/DESIGN.md §7.2/§13).

Subprocess-based for the CLI surface, matching test_status.py's
pattern. `_format_show_lines()`/`_looks_like_secret()` are tested
directly (imported, not through a subprocess) since the "(enforced)"
flagging they implement depends on the real, fixed
`/etc/spork/enforced.toml` when reached through `spork config show`
for real — same reasoning `test_enforced_override_paths.py` gives for
testing `enforced_override_paths()` with an injectable path instead of
touching that real file.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from typer.testing import CliRunner

from spork.cli.commands.config import _format_show_lines, _looks_like_secret, app
from spork.core.config.schema import BackendSpec, SporkConfig, TieringConfig
from spork.core.state.db import StateDB

runner = CliRunner()


def _run(*args: str, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "spork.cli.main", "config", *args],
        capture_output=True,
        text=True,
        timeout=10,
        env=env,
    )


def _write_config(config_dir: Path, tmp_path: Path) -> None:
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "config.toml").write_text(
        f"""
        rules_path = "{tmp_path / "rules.toml"}"
        db_path = "{tmp_path / "state.sqlite3"}"
        socket_path = "{tmp_path / "sporkd.sock"}"

        [provider]
        spec = "spork.core.providers.jmap.provider:JmapProvider"
        [provider.kwargs]
        host = "api.fastmail.com"
        api_token = "super-secret-value"

        [llm]
        spec = "spork.core.llm.clients.recorded:RecordedLLMClient"
        [llm.kwargs]
        responses_path = "{tmp_path / "responses.json"}"

        [alerts]
        spec = "spork.core.alerts.log:LoggingAlerter"
        """
    )


def _env(tmp_path: Path) -> dict[str, str]:
    env = dict(os.environ)
    env["XDG_CONFIG_HOME"] = str(tmp_path / "xdg-config-home")
    env["XDG_CONFIG_DIRS"] = str(tmp_path / "xdg-config-dirs")
    return env


def _fake_editor(tmp_path: Path, script: str) -> str:
    editor_path = tmp_path / "fake_editor.py"
    editor_path.write_text(script)
    return f"{sys.executable} {editor_path}"


def test_config_show_prints_effective_values(tmp_path: Path) -> None:
    env = _env(tmp_path)
    _write_config(tmp_path / "xdg-config-home" / "spork", tmp_path)

    result = _run("show", env=env)

    assert result.returncode == 0
    assert "spork.core.providers.jmap.provider:JmapProvider" in result.stdout
    assert "api.fastmail.com" in result.stdout


def test_config_init_writes_a_valid_jmap_setup_without_credentials(
    tmp_path: Path, monkeypatch
) -> None:
    """Initialization creates usable paths and keeps secret values out of TOML."""
    config_path = tmp_path / "config.toml"
    monkeypatch.setattr("spork.cli.commands.config.resolve_user_config_path", lambda: config_path)

    result = runner.invoke(app, ["init"], env={"HOME": str(tmp_path)})

    assert result.exit_code == 0
    assert config_path.is_file()
    assert (tmp_path / "rules.toml").is_file()
    text = config_path.read_text()
    assert "JMAP_API_TOKEN" in text
    assert "ANTHROPIC_API_KEY" in text
    assert "api.fastmail.com" in text
    assert "super-secret" not in text


def test_config_init_refuses_to_overwrite_existing_config(tmp_path: Path, monkeypatch) -> None:
    """An existing user config is protected unless --force is explicit."""
    config_path = tmp_path / "config.toml"
    config_path.write_text("existing = true\n")
    monkeypatch.setattr("spork.cli.commands.config.resolve_user_config_path", lambda: config_path)

    result = runner.invoke(app, ["init"])

    assert result.exit_code == 1
    assert "already exists" in result.output
    assert config_path.read_text() == "existing = true\n"


def test_config_init_force_replaces_existing_config(tmp_path: Path, monkeypatch) -> None:
    """--force is the only path that replaces an existing generated config."""
    config_path = tmp_path / "config.toml"
    config_path.write_text("existing = true\n")
    monkeypatch.setattr("spork.cli.commands.config.resolve_user_config_path", lambda: config_path)

    result = runner.invoke(app, ["init", "--force", "--model", "anthropic/test-model"])

    assert result.exit_code == 0
    assert "anthropic/test-model" in config_path.read_text()
    assert "existing = true" not in config_path.read_text()


def test_config_show_redacts_a_token_like_kwarg(tmp_path: Path) -> None:
    env = _env(tmp_path)
    _write_config(tmp_path / "xdg-config-home" / "spork", tmp_path)

    result = _run("show", env=env)

    assert result.returncode == 0
    assert "super-secret-value" not in result.stdout
    assert "provider.kwargs.api_token" in result.stdout


def test_config_show_with_no_config_produces_a_clean_error(tmp_path: Path) -> None:
    env = _env(tmp_path)

    result = _run("show", env=env)

    assert result.returncode == 1
    assert "Error:" in result.stderr
    assert "Traceback" not in result.stderr


def test_config_edit_with_a_noop_editor_saves_and_says_restart(tmp_path: Path) -> None:
    env = _env(tmp_path)
    _write_config(tmp_path / "xdg-config-home" / "spork", tmp_path)
    env["EDITOR"] = _fake_editor(tmp_path, "")  # does nothing

    result = _run("edit", env=env)

    assert result.returncode == 0
    assert "restart" in result.stdout.lower()


def test_config_edit_writes_a_control_plane_audit_entry_on_success(tmp_path: Path) -> None:
    """docs/DESIGN.md §7.4/§13 (M7): a "config_edit" control-plane
    audit_log entry on a successful save."""
    env = _env(tmp_path)
    _write_config(tmp_path / "xdg-config-home" / "spork", tmp_path)
    env["EDITOR"] = _fake_editor(tmp_path, "")  # does nothing, still a valid save

    _run("edit", env=env)

    with StateDB(tmp_path / "state.sqlite3") as db:
        entries = [e for e in db.get_audit_entries() if e.event == "config_edit"]

    assert len(entries) == 1
    assert entries[0].jmap_id == ""


def test_config_edit_writes_no_audit_entry_on_a_rejected_save(tmp_path: Path) -> None:
    """An invalid save never reaches load_config() successfully, so
    nothing gets written — same "only a real success is recorded"
    principle as every other control-plane entry."""
    env = _env(tmp_path)
    config_path = tmp_path / "xdg-config-home" / "spork" / "config.toml"
    _write_config(config_path.parent, tmp_path)
    corrupt_script = (
        f"import pathlib; pathlib.Path(r'{config_path}').write_text('this is not [ valid toml')"
    )
    env["EDITOR"] = _fake_editor(tmp_path, corrupt_script)

    _run("edit", env=env)

    with StateDB(tmp_path / "state.sqlite3") as db:
        entries = [e for e in db.get_audit_entries() if e.event == "config_edit"]

    assert entries == []


def test_config_edit_rejects_an_invalid_save(tmp_path: Path) -> None:
    env = _env(tmp_path)
    config_path = tmp_path / "xdg-config-home" / "spork" / "config.toml"
    _write_config(config_path.parent, tmp_path)
    corrupt_script = (
        f"import pathlib; pathlib.Path(r'{config_path}').write_text('this is not [ valid toml')"
    )
    env["EDITOR"] = _fake_editor(tmp_path, corrupt_script)

    result = _run("edit", env=env)

    assert result.returncode == 1
    assert "Error:" in result.stderr
    assert "Traceback" not in result.stderr


def test_config_group_appears_in_top_level_help() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "spork.cli.main", "--help"],
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert result.returncode == 0
    assert "config" in result.stdout.lower()


def _config() -> SporkConfig:
    return SporkConfig(
        provider=BackendSpec(
            spec="spork.core.providers.jmap.provider:JmapProvider",
            kwargs={"host": "api.fastmail.com", "api_token": "super-secret-value"},
        ),
        llm=BackendSpec(spec="spork.core.llm.clients.recorded:RecordedLLMClient"),
        alerts=BackendSpec(spec="spork.core.alerts.log:LoggingAlerter"),
        rules_path=Path("/home/will/.config/spork/rules.toml"),
        db_path=Path("/home/will/.local/share/spork/state.sqlite3"),
        socket_path=Path("/home/will/.local/state/spork/sporkd.sock"),
        tiering=TieringConfig(daily_call_budget=200),
    )


def test_format_show_lines_flags_a_path_present_in_the_enforced_set() -> None:
    lines = _format_show_lines(_config(), {"tiering.daily_call_budget"})

    matching = [line for line in lines if line.startswith("tiering.daily_call_budget")]
    assert len(matching) == 1
    assert "(enforced)" in matching[0]


def test_format_show_lines_does_not_flag_paths_outside_the_enforced_set() -> None:
    lines = _format_show_lines(_config(), set())

    assert not any("(enforced)" in line for line in lines)


def test_format_show_lines_redacts_provider_kwargs_api_token() -> None:
    lines = _format_show_lines(_config(), set())

    matching = [line for line in lines if line.startswith("provider.kwargs.api_token")]
    assert len(matching) == 1
    assert "super-secret-value" not in matching[0]


def test_looks_like_secret_matches_common_credential_key_names() -> None:
    assert _looks_like_secret("api_token") is True
    assert _looks_like_secret("API_KEY") is True
    assert _looks_like_secret("client_secret") is True
    assert _looks_like_secret("password") is True
    assert _looks_like_secret("host") is False
    assert _looks_like_secret("fallback_poll_interval_seconds") is False
