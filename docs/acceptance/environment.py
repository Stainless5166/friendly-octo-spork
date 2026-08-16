"""Behave hooks for the manual acceptance specification.

The default run is intentionally safe: live scenarios are reported as
skipped until the operator explicitly opts into the live environment.
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
