"""Pluggable local (non-LLM) text classification — docs/DESIGN.md §9.1.

Deliberately separate from `spork.core.rules` (deterministic condition
matching) and `spork.core.llm` (Claude escalation): this is the cheap
middle tier, and its whole reason to exist is to make experimenting
with different local techniques (keyword heuristics, spaCy, a small
local model, ...) a config change rather than a rule-engine change.
"""
