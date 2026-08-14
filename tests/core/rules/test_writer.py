"""Acceptance tests for spork.core.rules.writer.dump_rules() (docs/DESIGN.md §7.5).

A small, purpose-built TOML serializer for the closed Rule schema —
not a general TOML library. The one property that actually matters:
dump_rules(rules), reparsed through load_rules(), reproduces the
original rules exactly. Everything else (exact formatting) is an
implementation detail these tests don't pin down.
"""

from __future__ import annotations

from pathlib import Path

from spork.core.rules.loader import load_rules
from spork.core.rules.schema import Action, Condition, Rule
from spork.core.rules.writer import dump_rules


def test_dump_rules_round_trips_a_single_simple_rule(tmp_path: Path) -> None:
    rules = [
        Rule(
            id="catch-all",
            when=Condition(always=True),
            action=Action(type="tag", mailbox="Inbox"),
        )
    ]

    path = tmp_path / "rules.toml"
    path.write_text(dump_rules(rules))

    assert load_rules(path) == rules


def test_dump_rules_round_trips_multiple_rules_preserving_order(tmp_path: Path) -> None:
    rules = [
        Rule(
            id="vip-senders",
            description="Anything from these addresses always alerts",
            when=Condition(from_in=["boss@example.com"]),
            action=Action(type="escalate", reason="vip_sender", alert_immediately=True),
        ),
        Rule(
            id="newsletters",
            when=Condition(from_domain_in=["newsletter.example.com"]),
            action=Action(type="move", mailbox="Reading"),
            enabled=False,
        ),
    ]

    path = tmp_path / "rules.toml"
    path.write_text(dump_rules(rules))

    assert load_rules(path) == rules


def test_dump_rules_of_an_empty_list_produces_a_valid_empty_rules_file(tmp_path: Path) -> None:
    path = tmp_path / "rules.toml"
    path.write_text(dump_rules([]))

    assert load_rules(path) == []


def test_dump_rules_escapes_double_quotes_in_string_fields(tmp_path: Path) -> None:
    """A description/reason containing a literal double quote must
    still round-trip — not produce invalid TOML."""
    rules = [
        Rule(
            id="quoted",
            description='Files things marked "urgent"',
            when=Condition(always=True),
            action=Action(type="tag", mailbox="X", reason='says "now"'),
        )
    ]

    path = tmp_path / "rules.toml"
    path.write_text(dump_rules(rules))

    assert load_rules(path) == rules
