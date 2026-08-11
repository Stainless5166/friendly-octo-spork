"""Applying a rule engine verdict's action to a message (docs/DESIGN.md §9.3).

Provider-agnostic on purpose: `ActionExecutor` consumes whatever
`ActionApplier` a `Provider`'s `build_action_applier()` returns
(`spork.core.providers`), so this package depends on `providers/`, not
the other way around — the write-side I/O primitive lives with the
provider that implements it, the business logic that decides how to
use it lives here.
"""
