"""Getting a human's attention without them polling the CLI (docs/DESIGN.md §12).

`base.py` settles the adapter every backend implements (`Alerter`,
`AlertUrgency`); `log.py` is the v1 backend (`LoggingAlerter`);
`loader.py` resolves one by config the same way
`spork.core.providers.loader`/`spork.core.llm.loader` do. What
actually decides an alert is needed (§12.2 — confidence bands, VIP
rules, daemon health) isn't built yet.
"""
