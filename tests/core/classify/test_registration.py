"""Acceptance test for the default classifier's self-registration
(docs/DESIGN.md §9.1).

Before this, `tiering.local_classifier` had no working out-of-the-box
value: nothing anywhere in the codebase ever called
`registry.register()`, so `classify_registry.get(<anything>)` always
raised `UnknownClassifierError` in every real deployment. Importing
`spork.core.classify` (as every real caller already does —
`from spork.core.classify import registry`) must be enough on its own
to make "keyword_heuristic" resolvable, with zero extra wiring at each
call site.
"""

from __future__ import annotations

from spork.core.classify import registry
from spork.core.classify.keyword import KeywordClassifier


def test_importing_the_classify_package_registers_the_default_keyword_backend() -> None:
    resolved = registry.get("keyword_heuristic")

    assert isinstance(resolved, KeywordClassifier)
