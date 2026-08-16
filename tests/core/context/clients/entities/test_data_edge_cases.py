"""Edge-case tests for the entity knowledge base fixture loader
(docs/DESIGN.md §10.8, docs/ROADMAP.md M9) — every failure mode wraps
as `EntityDataLoadError`, mirroring
`spork.core.providers.file.messages`'s edge-case coverage.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from spork.core.context.clients.entities.data import EntityDataLoadError, load_entity_data


def test_load_entity_data_raises_for_a_missing_file(tmp_path: Path) -> None:
    with pytest.raises(EntityDataLoadError, match="not found"):
        load_entity_data(tmp_path / "does-not-exist.json")


def test_load_entity_data_raises_for_malformed_json(tmp_path: Path) -> None:
    path = tmp_path / "entities.json"
    path.write_text("this is not { valid json")

    with pytest.raises(EntityDataLoadError):
        load_entity_data(path)


def test_load_entity_data_raises_for_non_object_top_level(tmp_path: Path) -> None:
    """A file whose top level is a JSON array (not an object) is a
    clear EntityDataLoadError, not an unhelpful AttributeError from
    calling `.get()` on a list further down."""
    path = tmp_path / "entities.json"
    path.write_text(json.dumps(["not", "an", "object"]))

    with pytest.raises(EntityDataLoadError):
        load_entity_data(path)


def test_load_entity_data_raises_when_a_company_entry_is_not_an_object(tmp_path: Path) -> None:
    path = tmp_path / "entities.json"
    path.write_text(json.dumps({"companies": ["Gandi"]}))

    with pytest.raises(EntityDataLoadError, match="companies\\[0\\]"):
        load_entity_data(path)


def test_load_entity_data_raises_when_a_company_is_missing_its_name(tmp_path: Path) -> None:
    path = tmp_path / "entities.json"
    path.write_text(json.dumps({"companies": [{"domains": ["gandi.com"]}]}))

    with pytest.raises(EntityDataLoadError, match="companies\\[0\\]"):
        load_entity_data(path)


def test_load_entity_data_raises_when_a_service_is_missing_its_name(tmp_path: Path) -> None:
    path = tmp_path / "entities.json"
    path.write_text(json.dumps({"services": [{"category": "infrastructure"}]}))

    with pytest.raises(EntityDataLoadError, match="services\\[0\\]"):
        load_entity_data(path)


def test_load_entity_data_raises_when_a_person_is_missing_its_name(tmp_path: Path) -> None:
    path = tmp_path / "entities.json"
    path.write_text(json.dumps({"people": [{"email": "jane@gandi.com"}]}))

    with pytest.raises(EntityDataLoadError, match="people\\[0\\]"):
        load_entity_data(path)
