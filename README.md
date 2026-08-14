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

## Quickstart

Two supported paths: the manual steps below, or — on Arch Linux —
`makepkg -si` from the tracked [`PKGBUILD`](PKGBUILD), which does the
same install (same unit file, same layout), just packaged. Either way
you end up with `sporkd` running as a systemd **user** service.

> **Honest caveat:** JMAP live connectivity (`JmapClient.connect()`/
> `fetch_new_messages()`) is still a settled-shape `NotImplementedError`
> — genuinely blocked on a live Fastmail session to build against
> honestly, see `docs/ROADMAP.md` M1. Following this quickstart with a
> real `spork.core.providers.jmap.provider:JmapProvider` config gets
> `sporkd` started (`sd_notify`'s `READY=1` fires, `systemctl --user
> status` shows it up) but it will stop shortly after, once its first
> poll hits that stub. Steps 1–3 and the install flow (steps 4–5) are
> all real today, independent of that gap; step 3 below configures
> `FileProvider`/`RecordedLLMClient` instead of `JmapProvider` for
> exactly this reason — everything through "the daemon is installed,
> enabled, and reports healthy" is genuinely demonstrable without a
> live account.

1. **Clone and install dependencies.**

   ```console
   $ git clone https://github.com/stainless5166/friendly-octo-spork.git
   $ cd friendly-octo-spork
   $ uv sync
   ```

2. **Set up secrets** ([SecretSpec](https://github.com/cachix/secretspec),
   §7.3 of `docs/DESIGN.md`). `spork` depends only on SecretSpec's
   *Python SDK* (already installed by `uv sync`) to resolve secrets at
   runtime — it doesn't need the separate `secretspec` CLI tool. The
   repo's own `secretspec.toml` only *declares* what's needed; copy it
   into place, then tell SecretSpec which *provider* actually stores
   values. A real credential manager (`keyring://`, `1password://`,
   ...) needs that separate CLI tool — see SecretSpec's own docs. The
   simplest path that needs no extra tooling at all is its `env://`
   provider, set once, globally:

   ```console
   $ mkdir -p ~/.config/spork ~/.config/secretspec
   $ cp secretspec.toml ~/.config/spork/secretspec.toml
   $ printf '[defaults]\nprovider = "env://"\n' > ~/.config/secretspec/config.toml
   ```

   Then export the two declared secrets. A systemd **user** unit
   doesn't inherit your interactive shell's environment, so for
   `sporkd` (not just `uv run spork doctor`) to see them, put them in
   `~/.config/environment.d/spork.conf` (systemd's own per-user
   environment mechanism) rather than `.bashrc`:

   ```console
   $ mkdir -p ~/.config/environment.d
   $ cat > ~/.config/environment.d/spork.conf <<EOF
   JMAP_API_TOKEN=your-fastmail-api-token
   ANTHROPIC_API_KEY=your-anthropic-api-key
   EOF
   ```

3. **Write `~/.config/spork/config.toml`** (§7.2). This example uses
   `FileProvider`/`RecordedLLMClient` — no live account needed to try
   the daemon end to end; swap `[provider]` for
   `spork.core.providers.jmap.provider:JmapProvider` once M1's live
   JMAP session lands. `config.toml`'s paths are **not** `~`-expanded
   (plain `pydantic.Path` fields, verified directly — TOML has no
   shell-variable syntax of its own either), so write real absolute
   paths — the heredoc below expands `$HOME` for you:

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

4. **Install the console scripts where the unit file expects them.**
   The tracked unit (`systemd/sporkd.service`) runs
   `%h/.local/bin/sporkd` — `uv tool install` (not `uv run`, which
   only runs inside this checkout's own venv) puts `spork`/`sporkd`
   there:

   ```console
   $ uv tool install .
   ```

5. **Install and enable the systemd user unit.**

   ```console
   $ uv run spork install-service
   ```

   This writes `systemd/sporkd.service`'s content to
   `~/.config/systemd/user/sporkd.service`, runs `systemctl --user
   daemon-reload`, and enables + starts it (`--no-enable-now` skips
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
real regardless. M7 (hardening/v1 release) hasn't started. See
`docs/ROADMAP.md` for the full milestone breakdown and what's still
open within each.
