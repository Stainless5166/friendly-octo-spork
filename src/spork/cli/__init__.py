"""The `spork` CLI: status, config, and rule management against `sporkd`.

Kept separate from `spork.daemon` — see docs/DESIGN.md §6.3. Talks to the
daemon over the local control socket for anything live, and reads/writes
config and rule files directly for anything that's just editing state on
disk (also §6.3).
"""
