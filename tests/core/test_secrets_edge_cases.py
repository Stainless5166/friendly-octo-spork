"""Failure/edge-case tests for secret resolution.

Companion to test_secrets.py's acceptance tests.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from spork.core.secrets import Secrets, SecretsError, resolve_secrets


def test_resolve_secrets_wraps_malformed_toml_as_secrets_error(tmp_path: Path) -> None:
    """A hand-edited secretspec.toml with broken syntax is still a
    SecretsError, not a raw SecretSpec parse error leaking through
    unwrapped — callers only need to know about one exception type."""
    manifest = tmp_path / "secretspec.toml"
    manifest.write_text("this is not [ valid toml")

    with pytest.raises(SecretsError):
        resolve_secrets(manifest, provider="env://", reason="test")


def test_resolve_secrets_respects_the_given_profile(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The profile= argument actually reaches SecretSpec: a secret
    required in one profile but optional in another resolves
    successfully under the profile that makes it optional, with
    nothing providing a value."""
    manifest = tmp_path / "secretspec.toml"
    manifest.write_text(
        """
        [project]
        name = "test"
        revision = "1.0"

        [profiles.default]
        FOO_TOKEN = { description = "test secret" }

        [profiles.development]
        FOO_TOKEN = { required = false }
        """
    )
    monkeypatch.delenv("FOO_TOKEN", raising=False)

    # Would raise under the default profile (FOO_TOKEN is required
    # there) — succeeding here proves profile="development" was
    # actually forwarded, not silently ignored.
    resolve_secrets(manifest, provider="env://", reason="test", profile="development")


def test_secrets_repr_never_exposes_resolved_values() -> None:
    """docs/DESIGN.md §15's security review (M7): a plain dataclass
    repr would print every resolved secret's real value verbatim —
    a real leak risk if a Secrets instance ever ends up in an
    uncaught-exception traceback's local-variable dump, a debug log
    line, or a stray print(). repr() must never show the values,
    regardless of what get() legitimately returns."""
    secrets = Secrets({"JMAP_API_TOKEN": "super-secret-value-12345"})

    assert "super-secret-value-12345" not in repr(secrets)
