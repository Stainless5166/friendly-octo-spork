# friendly-octo-spork

A Python-based email triage tool targeting the JMAP spec (built for
Fastmail). Listens for new mail via JMAP push, runs it through a tiered
pipeline — cheap rules first, an LLM only when ambiguous or
important — and files, tags, or drafts a reply, alerting a human for
anything uncertain or high-stakes. Never auto-sends.

Ships as two executables:

- **`sporkd`** — the daemon. Runs as a systemd user service at login,
  owns the JMAP connection, evaluates rules, calls out to the LLM when
  needed, and raises alerts.
- **`spork`** — the CLI. Check daemon status, edit configuration, and
  manage/test triage rules.

Secrets (JMAP API token, model-provider API key, etc.) are declared with
[SecretSpec](https://github.com/cachix/secretspec) rather than `.env`
files. Dependencies are managed with [UV](https://docs.astral.sh/uv/).

**Privacy note:** when a message doesn't match any Tier 1 rule and
needs a judgment call, its cleaned body text is sent through LiteLLM
to the configured model provider for classification — that's the whole
point of Tier 2.
Only use `spork` if you're comfortable with ambiguous mail going to
that configured provider. Rule-matched mail (Tier 1) never leaves your
machine; nothing is ever auto-sent to anyone regardless of tier
(docs/DESIGN.md §15).

## Quickstart

Two supported paths: the manual steps below, or — on Arch Linux —
`makepkg -si` from the tracked [`PKGBUILD`](PKGBUILD), which does the
same install (same unit file, same layout), just packaged. Either way
you end up with `sporkd` running as a systemd **user** service.

> **Honest caveat:** authenticated JMAP session discovery and read-only
> `Email/changes`/`Email/get` fetching are now real and verified against
> Fastmail. Cursor-safe daemon acknowledgement and EventSource push are
> still incomplete; see `docs/ROADMAP.md` M1. Following this quickstart with a
> real `spork.core.providers.jmap.provider:JmapProvider` config gets
> `sporkd` started (`sd_notify`'s `READY=1` fires, `systemctl --user
> status` shows it up) but it will stop shortly after, once its first
> poll hits the push-listener stub. Steps 1–3 and the install flow (steps 4–5) are
> all real today, independent of that gap; step 3 below configures
> `FileProvider`/`RecordedLLMClient` instead of `JmapProvider` for
> exactly this reason — everything through "the daemon is installed,
> enabled, and reports healthy" is genuinely demonstrable without a
> live account.

> **Company-mail safety gate:** the current JMAP token is expected to be
> read-only by operator configuration, but Spork does not yet verify JMAP
> Session Object capabilities. Do not run `spork backfill` against company
> mail yet: it uses the normal action/Tier 2 pipeline. Use `spork report
> --limit 25` first; it writes only aggregate metadata to an isolated output
> path. External LLM processing and JMAP
> writes require separate approval and are not enabled by this documentation.

1. **Clone and install dependencies.**

   ```console
   $ git clone https://github.com/stainless5166/friendly-octo-spork.git
   $ cd friendly-octo-spork
   $ uv sync
   ```

   `litellm` and `jmapc` are optional runtime dependencies. The
   repository's dev environment installs both for tests; a production
   live install uses `uv tool install '.[llm,jmap]'`.
   `RecordedLLMClient` and `FileProvider` need neither extra.

2. **Set up secrets** ([SecretSpec](https://github.com/cachix/secretspec),
   §7.3 of `docs/DESIGN.md`). `spork` uses SecretSpec's Python SDK
   (already installed by `uv sync`) to resolve secrets at runtime. The
   repo's own `secretspec.toml` only *declares* what's needed; copy it
   into place and enroll the values in the OS keyring:

   ```console
    $ mkdir -p ~/.config/spork/default ~/.config/secretspec
    $ cp secretspec.toml ~/.config/spork/default/secretspec.toml
   $ printf '[defaults]\nprovider = "keyring"\n' > ~/.config/secretspec/config.toml
   $ uv run spork secrets enroll
   ```

   The command prompts without echoing either value and stores them in
   the current user's OS keyring. An environment provider remains
   available for environments that intentionally inject secrets:

   ```console
   $ printf '[defaults]\nprovider = "env://"\n' > ~/.config/secretspec/config.toml
   $ mkdir -p ~/.config/environment.d
   $ cat > ~/.config/environment.d/spork.conf <<EOF
   JMAP_API_TOKEN=your-fastmail-api-token
   ANTHROPIC_API_KEY=your-anthropic-api-key
   EOF
   ```

3. **Create `config.toml`** (§7.2). For the live JMAP path, use the
   generated safe starter configuration:

   ```console
    $ uv run spork --config ~/.config/spork/default/config.toml config init
   ```

   It creates a JMAP provider, LiteLLM backend, logging alerter, state
   path, and a disabled starter rule. It never writes credential values.
   Edit `~/.config/spork/rules.toml` before enabling triage. Paths in
   `config.toml` are absolute; TOML does not expand `~`.

   For the older offline FileProvider setup, write the following instead:

   ```console
   $ mkdir -p ~/.local/share/spork
   $ cat > ~/.config/spork/config.toml <<EOF
   rules_path = "$HOME/.config/spork/rules.toml"
   db_path = "$HOME/.local/share/spork/state.sqlite3"

   [provider]
   spec = "spork.core.providers.file.provider:FileProvider"
   [provider.kwargs]
   messages_path = "$HOME/.config/spork/messages.json"
   actions_log_path = "$HOME/.local/share/spork/actions.jsonl"

   [llm]
   spec = "spork.core.llm.clients.recorded:RecordedLLMClient"
   [llm.kwargs]
   responses_path = "$HOME/.config/spork/responses.json"

   [alerts]
   spec = "spork.core.alerts.log:LoggingAlerter"
   EOF
   $ echo '[]' > ~/.config/spork/messages.json
   $ echo '{}' > ~/.config/spork/responses.json
   ```

   Then a starter `rules.toml` (§7.5) — one rule is enough to start:

   ```console
   $ cat > ~/.config/spork/rules.toml <<EOF
   [[rule]]
   id = "catch-all"
   when = { always = true }
   action = { type = "tag", mailbox = "Inbox" }
   EOF
   ```

   `spork doctor` validates all of this — secrets, config, provider,
   rules — before you go any further:

   ```console
   $ uv run spork doctor
   ```

   Diagnostic launches can override either file without changing XDG
   state:

   ```console
   $ uv run spork --config /tmp/spork/config.toml --secretspec /tmp/spork/secretspec.toml doctor
   $ uv run sporkd --config /tmp/spork/config.toml --secretspec /tmp/spork/secretspec.toml
   ```

4. **Install the console scripts where the unit file expects them.**
    The tracked unit template (`systemd/sporkd@.service`) runs
   `%h/.local/bin/sporkd` — `uv tool install` (not `uv run`, which
   only runs inside this checkout's own venv) puts `spork`/`sporkd`
   there:

   ```console
   $ uv tool install .
   ```

5. **Install and enable the systemd user unit.**

   ```console
    $ uv run spork install-service default
   ```

    This writes `systemd/sporkd@.service`'s content to
    `~/.config/systemd/user/sporkd@.service`, runs `systemctl --user
    daemon-reload`, and enables + starts `sporkd@default` (`--no-enable-now` skips
   that last part). Want it running even fully logged out?
   `loginctl enable-linger $USER` — not run automatically, since it
   needs privileges this command has no business assuming it has.

6. **Verify.**

   ```console
   $ spork status
   $ spork doctor
   $ journalctl --user -u sporkd -f
   ```

## Docs

- [`docs/DESIGN.md`](docs/DESIGN.md) — architecture, data formats, JMAP
  and LLM integration details, safety model.
- [`docs/ROADMAP.md`](docs/ROADMAP.md) — milestones from scaffolding to
  v1.
- [`docs/TEST_COVERAGE.md`](docs/TEST_COVERAGE.md) — test-by-test
  inventory, cross-checked against the roadmap.
- [`docs/reports/`](docs/reports/) — dated, point-in-time status
  snapshots (open the HTML file directly in a browser) — not kept in
  sync like the three docs above; each one reflects the repo at the
  commit it names.

## Status

M0, M2, M3, M5, and M6 are complete; M4 is 2.5/3 (the daily-LLM-budget-
exhausted daemon-health alert is done; JMAP push disconnected is still
open, genuinely blocked on a live EventSource connection); M1 is done
except for the pieces that genuinely need a live
Fastmail account (JMAP session bootstrap, the real push listener) —
everything buildable without one, including the whole
`Provider`/`Source` abstraction proven against a second, fully real
adapter (`FileProvider`), is real and tested. M6's own exit criterion
("`spork status` reporting healthy" against a real account) still
can't be fully met until M1 is — the unit file, `sd_notify`, the
install flow, `spork doctor`'s checks, and the Arch package are all
real regardless. M7 (hardening/v1 release) is 5/9: structured logging,
per-message pipeline tracing, audit trail completeness, a security
review pass, and rule-engine/action-executor coverage are all done;
confidence tuning, rate-limit verification, crash-loop verification,
and tagging v1.0.0 all share the same live-account/live-week blocker
M7's own exit criteria state explicitly. See `docs/ROADMAP.md` for the
full milestone breakdown and what's still open within each.
