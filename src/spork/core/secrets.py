"""Secret resolution via SecretSpec (docs/DESIGN.md §7.3).

A thin wrapper over the `secretspec` SDK: resolves the `Path`/provider/
profile down to the small, injectable surface the rest of spork.core
needs (name -> value), and translates SecretSpec's own exceptions into
one project-specific error type so callers only need to know about
`SecretsError`, not SecretSpec's exception hierarchy.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

import secretspec


class SecretsError(Exception):
    """Raised when secrets can't be resolved, or an unresolved name is
    requested.

    Wraps whatever `secretspec.SecretSpecError` says (missing required
    secret, bad manifest path, no provider available, ...) so callers
    catch one type instead of learning SecretSpec's hierarchy — the
    same "fail loud with a specific, catchable type" pattern as the
    rest of spork.core (`UnknownClassifierError`, etc.).
    """


@dataclass(frozen=True, slots=True)
class Secrets:
    """The resolved secret values spork needs, held in memory only.

    A read-only, name -> value view over SecretSpec's richer
    `Resolved` object — downstream consumers (the JMAP client, the
    LLM client) just need a value by name; provenance/source-provider
    detail is what `spork doctor` (M5/M6) will want from SecretSpec
    directly, not something every consumer needs to carry around.
    """

    _values: Mapping[str, str]

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
    try:
        resolved = secretspec.resolve(
            path=str(path), provider=provider, profile=profile, reason=reason
        )
    except secretspec.SecretSpecError as exc:
        raise SecretsError(str(exc)) from exc

    values = {name: value for name, value in resolved.fields().items() if value is not None}
    return Secrets(values)
