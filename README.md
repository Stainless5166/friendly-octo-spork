# friendly-octo-spork

A Python-based email triage tool targeting the JMAP spec (built for
Fastmail). Listens for new mail via JMAP push, runs it through a tiered
pipeline — cheap rules first, LLM (Claude) only when ambiguous or
important — and files, tags, or drafts a reply, alerting a human for
anything uncertain or high-stakes. Never auto-sends.

Ships as two executables:

- **`sporkd`** — the daemon. Runs as a systemd user service at login,
  owns the JMAP connection, evaluates rules, calls out to the LLM when
  needed, and raises alerts.
- **`spork`** — the CLI. Check daemon status, edit configuration, and
  manage/test triage rules.

Secrets (JMAP API token, Anthropic API key, etc.) are declared with
[SecretSpec](https://github.com/cachix/secretspec) rather than `.env`
files. Dependencies are managed with [UV](https://docs.astral.sh/uv/).

## Docs

- [`docs/DESIGN.md`](docs/DESIGN.md) — architecture, data formats, JMAP
  and LLM integration details, safety model.
- [`docs/ROADMAP.md`](docs/ROADMAP.md) — milestones from scaffolding to
  v1.
- [`docs/TEST_COVERAGE.md`](docs/TEST_COVERAGE.md) — test-by-test
  inventory, cross-checked against the roadmap.

## Status

M0, M2, M3, and M5 are complete; M4 is 2.5/3 (the daily-LLM-budget-
exhausted daemon-health alert is done; JMAP push disconnected is still
open, genuinely blocked on a live EventSource connection); M1 is done
except for the pieces that genuinely need a live
Fastmail account (JMAP session bootstrap, the real push listener) —
everything buildable without one, including the whole
`Provider`/`Source` abstraction proven against a second, fully real
adapter (`FileProvider`), is real and tested. M6 (systemd packaging)
and M7 (hardening/v1 release) haven't started. See `docs/ROADMAP.md`
for the full milestone breakdown and what's still open within each.
