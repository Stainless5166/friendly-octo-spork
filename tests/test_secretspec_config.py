"""Not-yet-implemented spec test for secretspec.toml (docs/ROADMAP.md M0).

secretspec.toml was never actually created — docs/DESIGN.md §7.3 has a
fully worked example, but no code, config file, or dependency for it
exists in this repo yet (not even `secretspec` in pyproject.toml's
dependencies). This test tracks that gap directly against the file, not
against any Python API, since none exists yet either.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.mark.xfail(
    reason="secretspec.toml doesn't exist — secretspec isn't wired into "
    "the project at all yet (no config file, no dependency, no "
    "spork.core.secrets module). See docs/DESIGN.md §7.3 and "
    "docs/ROADMAP.md M0.",
)
def test_secretspec_toml_declares_the_required_secrets() -> None:
    """secretspec.toml should exist at the repo root and declare, under
    profiles.default, at least the two secrets every planned code path
    already assumes exist: JMAP_API_TOKEN (the JMAP client, M1) and
    ANTHROPIC_API_KEY (Tier 2 LLM escalation, M3) — per the example in
    docs/DESIGN.md §7.3."""
    config_path = REPO_ROOT / "secretspec.toml"
    assert config_path.exists(), f"{config_path} does not exist"

    config = tomllib.loads(config_path.read_text())
    default_secrets = config.get("profiles", {}).get("default", {})

    assert "JMAP_API_TOKEN" in default_secrets
    assert "ANTHROPIC_API_KEY" in default_secrets
