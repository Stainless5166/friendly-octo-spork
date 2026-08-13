"""Serializing Rules back to `rules.toml` (docs/DESIGN.md §7.5).

A small, purpose-built serializer for this exact closed schema
(`[[rule]]` blocks with inline `when`/`action` tables) — not a general
TOML-writing library. Nothing else in this codebase writes TOML, and
the schema is simple enough (strings, bools, string lists) that
hand-rolling the handful of lines it takes is cheaper and more
auditable than a new dependency. `spork rules enable/disable <id>`
(M5) is the one caller: it rewrites the whole file from the validated
`Rule` models, which means a hand-edited file's comments/formatting
don't survive — a real, stated tradeoff, not an oversight.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from spork.core.rules.schema import Rule


def _toml_string(value: str) -> str:
    """A double-quoted TOML basic string, backslash/quote-escaped."""
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _toml_value(value: Any) -> str:
    """Renders one Python value as a TOML literal — bool/str/list only,
    the closed set `Condition`/`Action`'s fields ever actually hold."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        return _toml_string(value)
    if isinstance(value, (list, tuple)):
        return "[" + ", ".join(_toml_value(item) for item in value) + "]"
    raise TypeError(f"dump_rules() cannot serialize value {value!r} of type {type(value)}")


def _inline_table(fields: dict[str, Any]) -> str:
    parts = [f"{key} = {_toml_value(value)}" for key, value in fields.items()]
    return "{ " + ", ".join(parts) + " }"


def dump_rules(rules: Sequence[Rule]) -> str:
    """Serializes `rules` to `rules.toml` text.

    The one property that matters: `load_rules()` parsing this output
    reproduces `rules` exactly (see tests/core/rules/test_writer.py) —
    field order/whitespace are implementation detail, not a contract.
    `model_dump(exclude_none=True)` on `when`/`action` drops unset
    Optional fields (`from_domain_in`, `mailbox`, etc.) rather than
    writing them out as TOML's non-existent "null", matching how a
    hand-written rules.toml would simply omit them too.
    """
    blocks: list[str] = []
    for rule in rules:
        lines = ["[[rule]]", f"id = {_toml_string(rule.id)}"]
        if rule.description:
            lines.append(f"description = {_toml_string(rule.description)}")
        lines.append(f"enabled = {_toml_value(rule.enabled)}")
        lines.append(f"when = {_inline_table(rule.when.model_dump(exclude_none=True))}")
        lines.append(f"action = {_inline_table(rule.action.model_dump(exclude_none=True))}")
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks) + "\n" if blocks else ""
