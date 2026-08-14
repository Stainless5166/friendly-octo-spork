"""UNIT_FILE_CONTENT: the sporkd systemd unit, as a string (docs/DESIGN.md §14).

Byte-identical to the tracked `systemd/sporkd.service` file (verified
by `tests/core/systemd/test_template.py`) — kept as a Python constant
here because `install_service()` needs it at runtime and an installed
`spork` has no guaranteed-reachable path back to that repo-root file
(a venv, a `uv tool install` location, a distro package's
site-packages could all put it somewhere `importlib.resources`-style
lookup would have to special-case). The tracked file is what a human
reads on GitHub and what the Arch `PKGBUILD` installs directly from a
full source checkout — it doesn't need this constant's runtime-lookup
problem solved.
"""

from __future__ import annotations

UNIT_FILE_CONTENT = """\
[Unit]
Description=Spork JMAP email triage daemon
After=network-online.target
Wants=network-online.target

[Service]
Type=notify
ExecStart=%h/.local/bin/sporkd
Restart=on-failure
RestartSec=5
# Secrets are resolved by sporkd itself via the SecretSpec SDK at
# startup — no secret material is passed through the unit file.

[Install]
WantedBy=default.target
"""
