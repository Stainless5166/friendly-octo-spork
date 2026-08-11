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

## Status

Pre-implementation. See `docs/ROADMAP.md` for current milestone.
