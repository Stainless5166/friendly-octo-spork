"""Parsing and validating `rules.toml` (docs/DESIGN.md §7.5).

Kept separate from `spork.core.rules.schema` (the pydantic models) so
a rules file can be validated/loaded without any evaluation logic
involved — useful for `spork rules test`'s dry-run path (M2) and for
`spork doctor` (M5) to sanity-check a config file without touching the
rule engine at all.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

import pydantic

from spork.core.rules.schema import Rule


class RulesLoadError(Exception):
    """Raised when a rules.toml file can't be parsed into valid Rules.

    Covers malformed TOML, a rule that fails schema validation, and
    duplicate rule ids — one catchable type, the same fail-loud
    pattern as the rest of `spork.core`. A hand-edited rules.toml is
    exactly the kind of input that needs a clear, specific error
    message, not a stack trace from a parsing library.
    """


def load_rules(path: str | Path, *, allow_escalation: bool = True) -> list[Rule]:
    """Parse and validate every `[[rule]]` entry in the file at `path`.

    `allow_escalation=False` is the Tier 1 beta safety gate: escalation
    rules fail at load time instead of reaching the model pipeline.

    Returns rules in file order (the order the Tier 1 evaluator will
    check them in — first-match-wins depends on it). A file with no
    `[[rule]]` entries at all is zero rules, not an error.
    """
    try:
        raw = tomllib.loads(Path(path).read_text())
    except FileNotFoundError as exc:
        raise RulesLoadError(f"rules file not found: {path}") from exc
    except tomllib.TOMLDecodeError as exc:
        raise RulesLoadError(f"invalid TOML in {path}: {exc}") from exc

    rules: list[Rule] = []
    seen_ids: set[str] = set()
    for index, entry in enumerate(raw.get("rule", [])):
        try:
            rule = Rule.model_validate(entry)
        except pydantic.ValidationError as exc:
            raise RulesLoadError(f"invalid rule at index {index} in {path}: {exc}") from exc
        if rule.id in seen_ids:
            raise RulesLoadError(f"duplicate rule id {rule.id!r} in {path}")
        if not allow_escalation and rule.action.type == "escalate":
            raise RulesLoadError(
                f"rule {rule.id!r} escalates but Tier 2 is disabled; "
                "set [tiering].tier2_enabled = true before enabling this rule"
            )
        seen_ids.add(rule.id)
        rules.append(rule)

    return rules
