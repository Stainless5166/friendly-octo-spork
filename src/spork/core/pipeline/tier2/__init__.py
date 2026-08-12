"""process_tier2_message(): the Tier 2 (LLM escalation) pipeline (§10.7).

Composed from the same generic Filter/Selector/Augment/Pipeline
framework spork.core.pipeline uses for Tier 1 (§9.4), over its own
Tier2Meta and concrete modules — never Tier 1's MessageMeta/modules,
which are a different shape.
"""

from __future__ import annotations

from spork.core.pipeline.tier2.default import build_tier2_pipeline as build_tier2_pipeline
from spork.core.pipeline.tier2.default import process_tier2_message as process_tier2_message
from spork.core.pipeline.tier2.meta import Tier2Meta as Tier2Meta
