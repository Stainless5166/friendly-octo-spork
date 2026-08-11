"""Shared logic used by both the `sporkd` daemon and the `spork` CLI.

Nothing in here should import from `spork.daemon` or `spork.cli` — the
dependency direction is one-way (executables depend on core, never the
reverse) so core stays testable and reusable in isolation. See
docs/DESIGN.md §6.1 for the intended module layout as it fills in.
"""
