"""End-to-end acceptance test: replay a fixture through the real rule
engine with no JMAP/IMAP connection involved (docs/ROADMAP.md M1a exit
criteria; docs/DESIGN.md §9.2).
"""

from __future__ import annotations

from spork.core.sources.replay import ImmediateTrigger, SequenceContentFetcher
from spork.core.sources.triggered import TriggeredSource

from spork.core.rules.engine import evaluate
from spork.core.rules.schema import Action, Condition, Rule


def test_replaying_a_fixture_drives_the_rule_engine_end_to_end(make_message) -> None:
    """A TriggeredSource built from ImmediateTrigger + SequenceContentFetcher
    (no real I/O anywhere) replays a small fixture, and each message it
    produces is evaluated by the actual, unmodified Tier 1 rule engine."""
    fixture = [
        make_message(message_id="newsletter-1", from_domain="newsletter.example.com"),
        make_message(message_id="unrelated-1", from_domain="example.com"),
    ]
    source = TriggeredSource(ImmediateTrigger(), SequenceContentFetcher(fixture, batch_size=1))
    rules = [
        Rule(
            id="file-newsletters",
            when=Condition(from_domain_in=["newsletter.example.com"]),
            action=Action(type="move", mailbox="Reading"),
        )
    ]

    verdicts = {}
    while batch := source.poll():
        for message in batch:
            verdicts[message.message_id] = evaluate(
                message, rules, default_unmatched_action=Action(type="escalate")
            )

    assert verdicts["newsletter-1"].matched_rule_id == "file-newsletters"
    assert verdicts["unrelated-1"].action == Action(type="escalate")
