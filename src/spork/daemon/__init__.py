"""The `sporkd` daemon: owns the JMAP connection, rule engine, and alerts.

Kept separate from `spork.cli` so the daemon can run headless under
systemd (docs/DESIGN.md §14) without pulling in anything CLI-specific.
"""
