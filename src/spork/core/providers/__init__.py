"""Mail-backend integrations, each adapted to a common contract (§9.3).

JMAP (`spork.core.providers.jmap`) is the only provider today. A
future backend (IMAP was the running example in docs/DESIGN.md §9.2)
lands as a sibling package here, not a special case bolted onto JMAP's
— see `base.py` for the `Provider` Protocol every provider adapts to,
and `loader.py` for how one gets selected and constructed at runtime
without spork importing backends nobody configured.
"""
