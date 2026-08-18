"""Spork: tiered JMAP email triage for a single Fastmail account.

See docs/DESIGN.md for the architecture this package implements and
docs/ROADMAP.md for what's built so far vs. planned.
"""

# Single source of truth for the installed version, read by packaging
# metadata and (eventually) `spork status` / `spork doctor` output.
__version__ = "0.2.0b1"
