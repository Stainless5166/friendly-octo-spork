"""Write Spork credentials into the SecretSpec keyring scope.

SecretSpec's Python SDK intentionally exposes resolution, not mutation. This
module owns the small write-side boundary used by `spork secrets enroll` and
uses the same service/account convention as SecretSpec's `keyring://` provider.
"""

from __future__ import annotations

import tomllib
from getpass import getuser
from pathlib import Path

import keyring


class SecretStoreError(Exception):
    """Raised when a credential cannot be written to the local keyring."""


_set_password = keyring.set_password


def keyring_service_name(manifest_path: Path, name: str, *, profile: str = "default") -> str:
    """Return SecretSpec's deterministic service name for one declared secret."""
    try:
        with manifest_path.open("rb") as manifest_file:
            document = tomllib.load(manifest_file)
        project = document["project"]["name"]
    except (KeyError, OSError, TypeError, tomllib.TOMLDecodeError) as exc:
        raise SecretStoreError(f"invalid SecretSpec manifest: {manifest_path}: {exc}") from exc
    if not isinstance(project, str) or not project:
        raise SecretStoreError(f"invalid SecretSpec project name in {manifest_path}")
    return f"secretspec/{project}/{profile}/{name}"


def store_secret(
    manifest_path: Path,
    name: str,
    value: str,
    *,
    profile: str = "default",
) -> None:
    """Store one value in the OS keyring without writing it to disk or logs."""
    if not value:
        raise SecretStoreError(f"cannot store an empty value for {name}")
    service = keyring_service_name(manifest_path, name, profile=profile)
    try:
        _set_password(service, getuser(), value)
    except Exception as exc:
        raise SecretStoreError(f"could not store {name} in the OS keyring: {exc}") from exc
