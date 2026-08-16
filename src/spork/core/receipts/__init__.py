"""Automatic-payment receipt tagging and archiving (docs/DESIGN.md §9.5).

Deterministic-first: a known sender is tagged/archived with no LLM
call at all; an unrecognized sender costs one narrow Tier 2 extraction
call, after which it's learned (`registry.KnownSenderStore`) and never
asked about again. Not part of the general Tier 1/Tier 2 triage split
(`spork.core.rules`/`spork.core.llm`) — this package answers one
closed question ("what company, what date, put it where") for a
message a Tier 1 rule has already decided is a receipt, via its own
`archive_receipt` terminal action.
"""
