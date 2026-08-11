"""JMAP session concerns: connection, push, and mailbox bookkeeping.

Everything here talks to (or prepares to talk to) a Fastmail JMAP
account via `jmapc`. Kept separate from `spork.core.rules` and
`spork.core.classify` so those can be unit-tested without any JMAP
client at all (docs/DESIGN.md §6.1) — this package is where the actual
network-facing code lives.
"""
