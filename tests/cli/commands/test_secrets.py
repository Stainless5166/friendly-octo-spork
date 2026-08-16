"""Acceptance tests for `spork secrets enroll`."""

from __future__ import annotations

from typer.testing import CliRunner

from spork.cli.commands.secrets import app
from spork.core.secret_store import SecretStoreError

runner = CliRunner()


def test_enroll_prompts_for_both_credentials_without_printing_values(monkeypatch) -> None:
    """Enrollment stores both names and never echoes either value."""
    calls: list[tuple[str, str]] = []
    monkeypatch.setattr(
        "spork.cli.commands.secrets.store_secret",
        lambda path, name, value: calls.append((name, value)),
    )

    result = runner.invoke(app, [], input="jmap-secret\njmap-secret\nllm-secret\nllm-secret\n")

    assert result.exit_code == 0
    assert calls == [("JMAP_API_TOKEN", "jmap-secret"), ("ANTHROPIC_API_KEY", "llm-secret")]
    assert "jmap-secret" not in result.output
    assert "llm-secret" not in result.output
    assert "OS keyring" in result.output


def test_enroll_reports_keyring_failure_without_traceback(monkeypatch) -> None:
    """A backend failure is a clean CLI error and does not expose input."""
    monkeypatch.setattr(
        "spork.cli.commands.secrets.store_secret",
        lambda path, name, value: (_ for _ in ()).throw(SecretStoreError("unexpected")),
    )

    result = runner.invoke(app, [], input="jmap-secret\njmap-secret\nllm-secret\nllm-secret\n")

    assert result.exit_code != 0
    assert "Traceback" not in result.output
