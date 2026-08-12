"""Tier 2: LLM (Claude) escalation for mail the rule engine didn't
resolve on its own (docs/DESIGN.md §10).

`base.py` settles the boundary every backend adapts to (`LLMClient`,
`VerdictRequest`/`Verdict`); `clean.py`/`validate.py`/`confidence.py`/
`budget.py` are the pure-logic pieces around that boundary (body
cleaning, schema validation against a deployment's configured
mailbox/category set, confidence-band gating, daily-call-budget
enforcement); `clients/` holds the concrete backends
(`AnthropicLLMClient`, `RecordedLLMClient`). `spork.core.pipeline.tier2`
composes all of it into the actual runnable pipeline (§10.7) — nothing
in this package runs on its own.
"""
