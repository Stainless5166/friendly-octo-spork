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
endpoint. `@baseline` and `@push` are bound and live-verified
(`SPORK_ACCEPTANCE_LIVE=1 uv run behave --tags="m1 and push"`).
`@cursor-safety` and `@network-recovery` in `m1_jmap.feature` still
expose undefined step bindings — a real `sporkd` restart cycle and
real network-level outage control (iptables/unplugging) respectively,
neither safely automatable from here. Bindings are being added
milestone by milestone.

`m1_jmap_fault_injection.feature` is not `@manual` and needs none of
the above: it drives the real `JmapProvider` push/fallback composition
through the in-process mitmproxy harness (`tests/support/jmap_mitm.py`,
ROADMAP M1c), so it runs in the safe default `uv run behave` with no
opt-in, no credentials, and no network. It's a complement to, not a
replacement for, `m1_jmap.feature`'s `@fallback`/`@network-recovery` —
those remain the real evidence for M1's exit criterion (an actual
forced network drop against a real account); this feature makes the
same Source-composition behavior regression-tested on every run.

## Status

| Feature | Scope | Current evidence |
|---|---|---|
| `m1_jmap.feature` | JMAP session, push, fallback, cursor safety | `@baseline` and `@push` bound, live-verified; `@cursor-safety`/`@network-recovery` still open (need a real restart cycle / real network control) |
| `m1_jmap_fault_injection.feature` | Push/fallback composition, simulated | Fully bound and passing on every run — mitmproxy harness, no live account |
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
