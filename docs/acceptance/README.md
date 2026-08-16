# Acceptance Specifications

The `.feature` files in this directory are the product acceptance
specification. They use Gherkin so the expected behavior is readable by
the maintainer before it is automated.

These files are not executed by pytest or CI. They are runnable with
Behave for discovery and, once step bindings exist, for live acceptance.
Scenarios tagged `@manual` require a dedicated Fastmail account, an
Anthropic account where marked, and usually a real systemd user session.
They must not contain credentials, real addresses, or private message
content.

## Running

The safe default discovers every feature and skips live scenarios:

```bash
uv run behave
```

Live execution requires explicit opt-in and the acceptance environment:

```bash
SPORK_ACCEPTANCE_LIVE=1 uv run behave
```

The first executable slice is the M1 baseline scenario. Configure the
installed SecretSpec manifest and run only that scenario:

```bash
SPORK_ACCEPTANCE_LIVE=1 uv run behave --tags="m1 and baseline"
```

Use `-D jmap_host=...` only when targeting an approved compatible JMAP
endpoint. Push, reconnect, and forced-outage scenarios currently expose
undefined step bindings rather than pretending to execute them. Bindings
are being added milestone by milestone.

## Status

| Feature | Scope | Current evidence |
|---|---|---|
| `m1_jmap.feature` | JMAP session, push, fallback, cursor safety | Baseline binding added; live baseline evidence still open. `@fallback`/`@network-recovery` await the mitmproxy harness (ROADMAP M1c) rather than being manual forever |
| `m2_rules.feature` | Live deterministic rules and actions | Offline pipeline tested; live JMAP actions still open |
| `m3_tier2.feature` | Live LLM verdicts, confidence, budget, drafts | Recorded/offline pipeline tested; live JMAP writes and live model run open |
| `m4_alerting.feature` | Alerts, push health, desktop delivery | Logging alerts tested; desktop backend and push-health alert open |
| `m5_control_surface.feature` | Daemon and CLI control surface | FileProvider/systemd-free integration tested; live JMAP path open |
| `m6_systemd.feature` | Service install and operational startup | Unit/install behavior tested; real user-session acceptance open |
| `m7_hardening.feature` | Unattended operation and v1 release | Requires real mailbox, model, rate-limit, and one-week run |

The scenarios are deliberately more demanding than the current automated
suite. A scenario is complete only when its stated live evidence exists,
not when an offline fixture imitates that evidence.

For local SMTP alert acceptance, run the dependency-free sink in one terminal:

```bash
python scripts/smtp_harness.py --record /tmp/spork-alerts.json --port 1025
```

Use the local alert profile with SMTP TLS and authentication disabled. Add
`--fail-after 1` to close the connection after the first accepted message and
exercise the alert-delivery failure path without contacting an external relay.
