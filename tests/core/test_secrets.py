"""Acceptance tests for secret resolution via SecretSpec (docs/DESIGN.md §7.3).

Uses SecretSpec's own env:// provider (reads process environment
variables) rather than a real keyring — genuinely exercises spork's
resolve_secrets() wrapper against the real SecretSpec SDK (not a mock
of it), without needing a live keyring/1Password/Vault backend this
environment doesn't have. Verified empirically before writing these:
keyring:// fails headlessly here (no secret-service/dbus), env:/// and
dotenv:// don't — see the commit message for how that was checked.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from spork.core.secrets import SecretsError, resolve_secrets


def _write_manifest(tmp_path: Path, body: str) -> Path:
    manifest = tmp_path / "secretspec.toml"
    manifest.write_text(body)
    return manifest


def test_resolve_secrets_reads_declared_values_via_env_provider(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A required secret set as an environment variable resolves to
    that value through the real SecretSpec SDK."""
    manifest = _write_manifest(
        tmp_path,
        """
        [project]
        name = "test"
        revision = "1.0"

        [profiles.default]
        FOO_TOKEN = { description = "test secret" }
        """,
    )
    monkeypatch.setenv("FOO_TOKEN", "hello-from-env")

    secrets = resolve_secrets(manifest, provider="env://", reason="test")

    assert secrets.get("FOO_TOKEN") == "hello-from-env"


def test_resolve_secrets_raises_on_missing_required_secret(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A required secret with nothing resolving it fails loudly at
    resolve time — sporkd should refuse to start with partial secrets."""
    manifest = _write_manifest(
        tmp_path,
        """
        [project]
        name = "test"
        revision = "1.0"

        [profiles.default]
        FOO_TOKEN = { description = "test secret" }
        """,
    )
    monkeypatch.delenv("FOO_TOKEN", raising=False)

    with pytest.raises(SecretsError):
        resolve_secrets(manifest, provider="env://", reason="test")


def test_secrets_get_raises_clear_error_for_undeclared_name(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Asking for a name that wasn't declared/resolved fails loudly,
    not with a bare KeyError."""
    manifest = _write_manifest(
        tmp_path,
        """
        [project]
        name = "test"
        revision = "1.0"

        [profiles.default]
        FOO_TOKEN = { description = "test secret" }
        """,
    )
    monkeypatch.setenv("FOO_TOKEN", "hello")
    secrets = resolve_secrets(manifest, provider="env://", reason="test")

    with pytest.raises(SecretsError):
        secrets.get("NEVER_DECLARED")


def test_resolve_secrets_raises_for_a_nonexistent_manifest_file(tmp_path: Path) -> None:
    """A missing secretspec.toml is a clear, specific failure, not a
    confusing SecretSpec-internal error leaking through unwrapped."""
    with pytest.raises(SecretsError):
        resolve_secrets(tmp_path / "does-not-exist.toml", provider="env://", reason="test")


def test_resolve_secrets_supports_optional_secrets_without_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An optional (required = false) secret with nothing resolving it
    doesn't fail resolution — only required-but-missing does."""
    manifest = _write_manifest(
        tmp_path,
        """
        [project]
        name = "test"
        revision = "1.0"

        [profiles.default]
        OPTIONAL_TOKEN = { description = "optional", required = false }
        """,
    )
    monkeypatch.delenv("OPTIONAL_TOKEN", raising=False)

    secrets = resolve_secrets(manifest, provider="env://", reason="test")

    with pytest.raises(SecretsError):
        secrets.get("OPTIONAL_TOKEN")
