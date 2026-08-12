"""Three-tier config.toml loading (docs/DESIGN.md §7.2).

- `paths.py` — pure XDG/enforced-tier path resolution.
- `schema.py` — `SporkConfig`/`TieringConfig`/`BackendSpec` pydantic models.
- `loader.py` — `load_config()`: finds which tiers exist, deep-merges
  them in ascending precedence, validates the result.

Settled at design time (§6.4) before any of it existed, same as
`spork.core.alerts` before M4 built it.
"""
