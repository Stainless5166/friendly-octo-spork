"""Failure/edge-case tests for `spork config show/edit`.

Companion to test_config.py's acceptance tests.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from spork.cli.commands.config import _format_show_lines
from spork.core.config.schema import BackendSpec, SporkConfig


def _run(*args: str, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "spork.cli.main", "config", *args],
        capture_output=True,
        text=True,
        timeout=10,
        env=env,
    )


def _env(tmp_path: Path) -> dict[str, str]:
    env = dict(os.environ)
    env["XDG_CONFIG_HOME"] = str(tmp_path / "xdg-config-home")
    env["XDG_CONFIG_DIRS"] = str(tmp_path / "xdg-config-dirs")
    return env


def test_config_show_help_works() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "spork.cli.main", "config", "show", "--help"],
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert result.returncode == 0
    assert "usage" in result.stdout.lower()


def test_config_edit_help_works() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "spork.cli.main", "config", "edit", "--help"],
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert result.returncode == 0
    assert "usage" in result.stdout.lower()


def test_config_edit_with_no_config_at_all_never_invokes_the_editor(tmp_path: Path) -> None:
    """No config.toml in any tier: the precondition check fails before
    $EDITOR is ever invoked — proven by a marker file $EDITOR would
    have created never appearing."""
    env = _env(tmp_path)
    marker = tmp_path / "editor-ran.marker"
    editor_path = tmp_path / "fake_editor.py"
    editor_path.write_text(f"import pathlib; pathlib.Path(r'{marker}').write_text('ran')")
    env["EDITOR"] = f"{sys.executable} {editor_path}"

    result = _run("edit", env=env)

    assert result.returncode == 1
    assert "Error:" in result.stderr
    assert not marker.exists()


def _config(*, llm_kwargs: dict[str, str] | None = None) -> SporkConfig:
    return SporkConfig(
        provider=BackendSpec(spec="spork.core.providers.file.provider:FileProvider"),
        llm=BackendSpec(
            spec="spork.core.llm.clients.recorded:RecordedLLMClient",
            kwargs=llm_kwargs or {},
        ),
        alerts=BackendSpec(spec="spork.core.alerts.log:LoggingAlerter"),
        rules_path=Path("/home/will/.config/spork/rules.toml"),
        db_path=Path("/home/will/.local/share/spork/state.sqlite3"),
        socket_path=None,
    )


def test_format_show_lines_handles_a_none_socket_path_without_crashing() -> None:
    lines = _format_show_lines(_config(), set())

    matching = [line for line in lines if line.startswith("socket_path")]
    assert matching == ["socket_path = None"]


def test_format_show_lines_prints_no_kwargs_lines_when_kwargs_is_empty() -> None:
    lines = _format_show_lines(_config(), set())

    assert not any(line.startswith("llm.kwargs.") for line in lines)


def test_format_show_lines_redacts_across_every_backend_section_independently() -> None:
    lines = _format_show_lines(_config(llm_kwargs={"api_key": "sk-real-secret"}), set())

    matching = [line for line in lines if line.startswith("llm.kwargs.api_key")]
    assert len(matching) == 1
    assert "sk-real-secret" not in matching[0]
    assert "<redacted>" in matching[0]
