"""Secret resolution via SecretSpec (docs/DESIGN.md §7.3).

A thin wrapper over the `secretspec` SDK: resolves the `Path`/provider/
profile down to the small, injectable surface the rest of spork.core
needs (name -> value), and translates SecretSpec's own exceptions into
one project-specific error type so callers only need to know about
`SecretsError`, not SecretSpec's exception hierarchy.
"""

from __future__ import annotations

import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from getpass import getuser
from pathlib import Path

import keyring
import secretspec

_get_password = keyring.get_password


class SecretsError(Exception):
    """Raised when secrets can't be resolved, or an unresolved name is
    requested.

    Wraps whatever `secretspec.SecretSpecError` says (missing required
    secret, bad manifest path, no provider available, ...) so callers
    catch one type instead of learning SecretSpec's hierarchy — the
    same "fail loud with a specific, catchable type" pattern as the
    rest of spork.core (`UnknownClassifierError`, etc.).
    """


@dataclass(frozen=True, slots=True, repr=False)
class Secrets:
    """The resolved secret values spork needs, held in memory only.

    A read-only, name -> value view over SecretSpec's richer
    `Resolved` object — downstream consumers (the JMAP client, the
    LLM client) just need a value by name; provenance/source-provider
    detail is what `spork doctor` (M5/M6) will want from SecretSpec
    directly, not something every consumer needs to carry around.

    `repr=False` (docs/DESIGN.md §15's security review, M7): the
    dataclass-generated `__repr__` would print every resolved value
    verbatim — a real leak risk if an instance ever ends up in an
    uncaught-exception traceback's local-variable dump, a debug log
    line, or a stray `print()`. `__repr__` below shows only the
    declared names, never a value, regardless of what `get()`
    legitimately returns to a caller that actually needs one.
    """

    _values: Mapping[str, str]

    def __repr__(self) -> str:
        return f"Secrets(names={sorted(self._values)})"

    def get(self, name: str) -> str:
        """Return the resolved value for `name`.

        Raises `SecretsError` (not `KeyError`) for a name that wasn't
        declared, or was declared but never resolved (e.g. an optional
        secret nothing provided a value for) — see `resolve_secrets`.
        """
        try:
            return self._values[name]
        except KeyError as exc:
            raise SecretsError(
                f"secret {name!r} was not resolved; available: {sorted(self._values)}"
            ) from exc


def resolve_secrets(
    path: str | Path,
    *,
    reason: str,
    provider: str | None = None,
    profile: str | None = None,
) -> Secrets:
    """Resolve every secret declared in the `secretspec.toml` at `path`.

    `reason` is required, not optional with a generic default: it's
    SecretSpec's own audit-log policy (every access is recorded
    "who, when, why" — docs/DESIGN.md §7.3), and a reason like "spork
    startup" is only meaningful if every call site is honest about why
    it's actually resolving secrets, which a shared default would
    quietly undermine. `provider`/`profile` pass straight through to
    SecretSpec; `None` means "use SecretSpec's own default resolution"
    (e.g. the manifest's `[providers]` table). Raises `SecretsError` on
    any resolution failure — sporkd should fail fast at startup with
    partial secrets, not limp along and fail later in a confusing
    place.
    """
    if provider is None:
        provider = _manifest_provider(path)
    if provider == "keyring":
        return _resolve_keyring(path, profile)
    try:
        resolved = secretspec.resolve(
            path=str(path), provider=provider, profile=profile, reason=reason
        )
    except secretspec.SecretSpecError as exc:
        raise SecretsError(str(exc)) from exc

    values = {name: value for name, value in resolved.fields().items() if value is not None}
    return Secrets(values)


def _resolve_keyring(path: str | Path, profile: str | None) -> Secrets:
    """Read SecretSpec's keyring scope through the working Python backend.

    SecretSpec's native keyring resolver can report a usable Secret Service
    while failing to read values on some Linux keyring setups. The Python
    backend used by enrollment reads the same documented service/account
    scope, so this compatibility path keeps the application usable without
    falling back to files or environment variables.
    """
    manifest_path = Path(path)
    try:
        with manifest_path.open("rb") as manifest_file:
            document = tomllib.load(manifest_file)
        project = document["project"]["name"]
        selected_profile = profile or "default"
        declarations = document["profiles"][selected_profile]
    except (KeyError, OSError, TypeError, tomllib.TOMLDecodeError) as exc:
        raise SecretsError(f"could not read SecretSpec keyring manifest: {exc}") from exc

    if not isinstance(project, str) or not isinstance(declarations, dict):
        raise SecretsError("invalid SecretSpec keyring manifest")

    account = getuser()
    values: dict[str, str] = {}
    missing: list[str] = []
    for name, declaration in declarations.items():
        if not isinstance(name, str) or not isinstance(declaration, dict):
            raise SecretsError("invalid SecretSpec secret declaration")
        service = f"secretspec/{project}/{selected_profile}/{name}"
        try:
            value = _get_password(service, account)
        except Exception as exc:
            raise SecretsError(f"could not read {name} from the OS keyring: {exc}") from exc
        if value is None:
            if declaration.get("required", True):
                missing.append(name)
        else:
            values[name] = value

    if missing:
        raise SecretsError(f"missing required secret(s): {', '.join(sorted(missing))}")
    return Secrets(values)


def _manifest_provider(path: str | Path) -> str | None:
    """Honor the manifest provider when the SDK's global default is unset."""
    try:
        with Path(path).open("rb") as manifest_file:
            document = tomllib.load(manifest_file)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise SecretsError(f"could not read SecretSpec manifest: {exc}") from exc
    providers = document.get("providers", {})
    if not isinstance(providers, dict):
        raise SecretsError("SecretSpec [providers] must be a table")
    default = providers.get("default")
    if default is not None and not isinstance(default, str):
        raise SecretsError("SecretSpec providers.default must be a string")
    if default == "keyring://":
        return "keyring"
    return default
