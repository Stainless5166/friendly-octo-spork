"""Pluggable local (non-LLM) text classification — docs/DESIGN.md §9.1.

Deliberately separate from `spork.core.rules` (deterministic condition
matching) and `spork.core.llm` (Claude escalation): this is the cheap
middle tier, and its whole reason to exist is to make experimenting
with different local techniques (keyword heuristics, spaCy, a small
local model, ...) a config change rather than a rule-engine change.
"""

from __future__ import annotations

# Import-time side effect: registers "keyword_heuristic" under
# spork.core.classify.registry. Every real caller already does
# `from spork.core.classify import registry`, which runs this
# package's __init__.py first — so the shipped default backend
# (§9.1: "ships dependency-free") is resolvable with zero extra
# wiring at any call site, not something each of them has to remember
# to import.
from spork.core.classify import keyword as _keyword  # noqa: F401
