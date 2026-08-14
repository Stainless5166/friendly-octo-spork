"""Tier 2: LLM (Claude) escalation for mail the rule engine didn't
resolve on its own (docs/DESIGN.md §10).

`base.py` settles the boundary every backend adapts to (`LLMClient`,
`VerdictRequest`/`Verdict`/`LLMResult`); `clean.py`/`validate.py`/`confidence.py`/
`budget.py` are the pure-logic pieces around that boundary (body
cleaning, schema validation against a deployment's configured
mailbox/category set, confidence-band gating, daily-call-budget
enforcement); `prompt.py` builds the exact tool call; `clients/` holds
the concrete backends (`LiteLLMClient`, `RecordedLLMClient`) and
`recording.py` captures private acceptance corpora. `spork.core.pipeline.tier2`
composes all of it into the actual runnable pipeline (§10.7) — nothing
in this package runs on its own.
"""
