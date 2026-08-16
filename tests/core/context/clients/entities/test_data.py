"""Acceptance tests for the entity knowledge base fixture loader
(docs/DESIGN.md §10.8, docs/ROADMAP.md M9).

Mirrors `spork.core.providers.file.messages`' test shape: parsing a
literal JSON fixture into typed records, one clear error type instead
of letting json/KeyError leak through unwrapped.
"""

from __future__ import annotations

import json
from pathlib import Path

from spork.core.context.clients.entities.data import load_entity_data
from spork.core.context.clients.entities.models import Company, Person, Service


def test_load_entity_data_parses_companies_services_and_people(tmp_path: Path) -> None:
    """A well-formed fixture parses into Company/Service/Person records,
    each field preserved as authored."""
    path = tmp_path / "entities.json"
    path.write_text(
        json.dumps(
            {
                "companies": [
                    {
                        "name": "Gandi",
                        "domains": ["gandi.com"],
                        "services": ["DNS hosting", "Cloud hosting"],
                    }
                ],
                "services": [{"name": "DNS hosting", "category": "infrastructure"}],
                "people": [{"name": "Jane Doe", "email": "jane@gandi.com", "company": "Gandi"}],
            }
        )
    )

    data = load_entity_data(path)

    assert data.companies == (
        Company(name="Gandi", domains=("gandi.com",), services=("DNS hosting", "Cloud hosting")),
    )
    assert data.service_metadata == (Service(name="DNS hosting", category="infrastructure"),)
    assert data.people == (Person(name="Jane Doe", email="jane@gandi.com", company="Gandi"),)


def test_load_entity_data_defaults_missing_sections_to_empty(tmp_path: Path) -> None:
    """A fixture with only "companies" is valid — "services"/"people"
    are optional sections, not required ones."""
    path = tmp_path / "entities.json"
    path.write_text(json.dumps({"companies": [{"name": "Gandi"}]}))

    data = load_entity_data(path)

    assert data.companies == (Company(name="Gandi"),)
    assert data.service_metadata == ()
    assert data.people == ()
