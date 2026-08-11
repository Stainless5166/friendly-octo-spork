"""secretspec.toml exists and declares the required secrets (docs/ROADMAP.md M0).

Graduated from an `xfail` spec test: `secretspec.toml` and
`spork.core.secrets` now exist for real (see `tests/core/test_secrets.py`
for the resolution logic itself). This test only covers the manifest's
own structure — that it exists and declares the right names — since
resolving it for real needs a provider (keyring, 1Password, ...) this
environment doesn't have.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


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
