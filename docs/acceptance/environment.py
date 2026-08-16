"""Behave hooks for the acceptance specification.

The default run is intentionally safe: live scenarios are reported as
skipped until the operator explicitly opts into the live environment.
Harness-backed (non-@manual) scenarios run every time.
"""

import os
from typing import Any


def before_scenario(context: Any, scenario: Any) -> None:
    """Keep live-account scenarios from running without explicit opt-in.

    Step bindings for live JMAP, LLM, and systemd operations are added as
    those acceptance surfaces become executable. Until then, an opt-in run
    exposes missing bindings instead of claiming that a manual scenario ran.
    """
    del context
    tags = getattr(scenario, "effective_tags", getattr(scenario, "tags", []))
    if "manual" in tags and os.environ.get("SPORK_ACCEPTANCE_LIVE") != "1":
        scenario.skip(
            "manual acceptance is disabled; set SPORK_ACCEPTANCE_LIVE=1 "
            "after configuring the dedicated acceptance environment"
        )
    # @wip is the "not built yet" counterpart to @manual's "needs a live
    # account": a scenario with real step bindings that intentionally
    # raise NotImplementedError until the pipeline behind it exists
    # (docs/ROADMAP.md tracks which milestone). Skipped by the same safe
    # default so a scaffolded feature doesn't turn `uv run behave` red;
    # opt in to see the current gap directly.
    if "wip" in tags and os.environ.get("SPORK_ACCEPTANCE_WIP") != "1":
        scenario.skip(
            "work-in-progress acceptance is disabled; the pipeline behind "
            "this scenario isn't implemented yet (see docs/ROADMAP.md) — "
            "set SPORK_ACCEPTANCE_WIP=1 to run it and see the current gap"
        )


def after_scenario(context: Any, scenario: Any) -> None:
    """Tear down the mitmproxy fault-injection harness, if this scenario started one.

    `m1_fault_injection.py` opens jmap_mitm_harness() as a raw context
    manager (not a `with` block) so it can stay open across a scenario's
    Given/When/Then steps; this hook is the corresponding __exit__ call,
    run whether the scenario passed or failed.
    """
    del scenario
    harness_cm = getattr(context, "jmap_harness_cm", None)
    if harness_cm is not None:
        harness_cm.__exit__(None, None, None)
