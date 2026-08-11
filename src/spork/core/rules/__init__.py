"""Tier 1: deterministic, user-authored condition -> action rules.

Everything here is intentionally closed-schema rather than arbitrary
code (docs/DESIGN.md §7.5 and §11) so a candidate `rules.toml` can be
safely dry-run (`spork rules test`) without executing untrusted logic.
"""
