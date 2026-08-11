"""Message acquisition: decoupling *when* to fetch from *what* to fetch
(docs/DESIGN.md §9.2).

Nothing downstream (the dispatcher, the rule engine) should ever need
to know which kind of Source produced a `NormalizedMessage` — that's
the whole point of the split. Real-I/O `Source`/`Trigger`/
`ContentFetcher` implementations (JMAP push, IMAP polling) land with
M1's remainder; this package currently holds the protocols plus the
dependency-free replay pieces used for tests and demos.
"""
