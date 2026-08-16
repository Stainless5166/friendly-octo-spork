"""Structured entity knowledge base backend (docs/DESIGN.md §10.8, docs/ROADMAP.md M9).

Tracks domains, companies, services, and people from a JSON fixture —
a real, fully offline-testable `ContextProvider` backend (`provider.py`),
distinct from `spork.core.context.clients.vault`'s free-text approach.
One of several knowledge base backends this seam is meant to hold; a
future live-lookup backend (e.g. WHOIS/RDAP) answering the same four
lookups is a sibling module, not a redesign of this one.
"""
