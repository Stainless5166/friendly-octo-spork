"""Loads entity knowledge base records from a JSON file (docs/DESIGN.md §10.8).

Kept separate from `spork.core.context.clients.entities.provider` for
the same reason `spork.core.providers.file.messages` is separate from
`spork.core.providers.file.provider`: parsing/validating a file is a
distinct concern from what a backend does with the result.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from spork.core.context.clients.entities.models import Company, Person, Service


class EntityDataLoadError(ValueError):
    """Raised when an entity knowledge base JSON file can't be parsed.

    Covers a missing file, malformed JSON, a non-object top level, a
    non-array section, and an entry missing a required field — one
    catchable type instead of letting json/KeyError leak through
    unwrapped, the same fail-loud pattern as
    `spork.core.providers.file.messages.MessagesLoadError`.
    """


@dataclass(frozen=True, slots=True)
class EntityData:
    """Everything parsed from one entity knowledge base fixture.

    `service_metadata` holds only the *optional* standalone `services`
    section (currently just `category`) — the company -> service
    association itself lives in each `Company.services`, never
    duplicated here.
    """

    companies: tuple[Company, ...]
    service_metadata: tuple[Service, ...]
    people: tuple[Person, ...]


def _require_object(entry: Any, *, section: str, index: int, path: Path) -> dict[str, Any]:
    """A section entry must be a JSON object — the one shape check every
    entry-level parser below shares."""
    if not isinstance(entry, dict):
        raise EntityDataLoadError(
            f"{path}: {section}[{index}] must be a JSON object, got {type(entry).__name__}"
        )
    return entry


def _parse_company(entry: dict[str, Any], *, index: int, path: Path) -> Company:
    try:
        return Company(
            name=entry["name"],
            domains=tuple(entry.get("domains", ())),
            services=tuple(entry.get("services", ())),
        )
    except KeyError as exc:
        raise EntityDataLoadError(
            f"{path}: companies[{index}] missing required field {exc}"
        ) from exc


def _parse_service(entry: dict[str, Any], *, index: int, path: Path) -> Service:
    try:
        return Service(name=entry["name"], category=entry.get("category"))
    except KeyError as exc:
        raise EntityDataLoadError(
            f"{path}: services[{index}] missing required field {exc}"
        ) from exc


def _parse_person(entry: dict[str, Any], *, index: int, path: Path) -> Person:
    try:
        return Person(name=entry["name"], email=entry.get("email"), company=entry.get("company"))
    except KeyError as exc:
        raise EntityDataLoadError(f"{path}: people[{index}] missing required field {exc}") from exc


def load_entity_data(path: str | Path) -> EntityData:
    """Parse a JSON object of companies/services/people into `EntityData`.

    "companies" is the only section actually required to have entries
    for a fixture to be useful, but even it defaults to `()` — a
    syntactically valid, entirely empty knowledge base is a legitimate
    (if useless) starting point, same as `load_messages()` treating
    `[]` as zero messages rather than an error.
    """
    path = Path(path)
    try:
        raw = json.loads(path.read_text())
    except FileNotFoundError as exc:
        raise EntityDataLoadError(f"entity knowledge base file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise EntityDataLoadError(f"invalid JSON in {path}: {exc}") from exc

    if not isinstance(raw, dict):
        raise EntityDataLoadError(f"{path} must contain a JSON object, got {type(raw).__name__}")

    companies = []
    for index, entry in enumerate(raw.get("companies", ())):
        obj = _require_object(entry, section="companies", index=index, path=path)
        companies.append(_parse_company(obj, index=index, path=path))

    service_metadata = []
    for index, entry in enumerate(raw.get("services", ())):
        obj = _require_object(entry, section="services", index=index, path=path)
        service_metadata.append(_parse_service(obj, index=index, path=path))

    people = []
    for index, entry in enumerate(raw.get("people", ())):
        obj = _require_object(entry, section="people", index=index, path=path)
        people.append(_parse_person(obj, index=index, path=path))

    return EntityData(
        companies=tuple(companies),
        service_metadata=tuple(service_metadata),
        people=tuple(people),
    )
