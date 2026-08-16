"""Acceptance tests for SecretSpec keyring enrollment."""

from __future__ import annotations

from pathlib import Path

import pytest

from spork.core.secret_store import SecretStoreError, keyring_service_name, store_secret


def test_keyring_service_name_matches_secretspec_scope(tmp_path: Path) -> None:
    """Enrollment must write the exact service path SecretSpec reads."""
    manifest = tmp_path / "secretspec.toml"
    manifest.write_text('[project]\nname = "spork"\n\n[profiles.default]\nJMAP_API_TOKEN = {}\n')

    assert keyring_service_name(manifest, "JMAP_API_TOKEN") == (
        "secretspec/spork/default/JMAP_API_TOKEN"
    )


def test_keyring_service_name_rejects_a_malformed_manifest(tmp_path: Path) -> None:
    """Malformed manifests fail before any keyring operation."""
    manifest = tmp_path / "secretspec.toml"
    manifest.write_text("not = [valid")

    with pytest.raises(SecretStoreError, match="invalid SecretSpec manifest"):
        keyring_service_name(manifest, "JMAP_API_TOKEN")


def test_store_secret_uses_current_user_as_keyring_account(tmp_path: Path, monkeypatch) -> None:
    """Values go to keyring with no file or environment fallback."""
    manifest = tmp_path / "secretspec.toml"
    manifest.write_text('[project]\nname = "spork"\n')
    calls: list[tuple[str, str, str]] = []

    monkeypatch.setattr("spork.core.secret_store.getuser", lambda: "test-user")
    monkeypatch.setattr(
        "spork.core.secret_store._set_password",
        lambda service, account, value: calls.append((service, account, value)),
    )

    store_secret(manifest, "JMAP_API_TOKEN", "read-only-token")

    assert calls == [("secretspec/spork/default/JMAP_API_TOKEN", "test-user", "read-only-token")]


def test_store_secret_wraps_keyring_failures_without_echoing_value(
    tmp_path: Path, monkeypatch
) -> None:
    """Backend errors cross the boundary without including credential material."""
    manifest = tmp_path / "secretspec.toml"
    manifest.write_text('[project]\nname = "spork"\n')
    monkeypatch.setattr(
        "spork.core.secret_store._set_password",
        lambda service, account, value: (_ for _ in ()).throw(RuntimeError("no keyring")),
    )

    with pytest.raises(SecretStoreError, match="no keyring") as error:
        store_secret(manifest, "JMAP_API_TOKEN", "must-not-appear")

    assert "must-not-appear" not in str(error.value)


def test_store_secret_rejects_an_empty_value(tmp_path: Path) -> None:
    """Enrollment cannot create an unusable empty keyring entry."""
    manifest = tmp_path / "secretspec.toml"
    manifest.write_text('[project]\nname = "spork"\n')

    with pytest.raises(SecretStoreError, match="empty value"):
        store_secret(manifest, "JMAP_API_TOKEN", "")
