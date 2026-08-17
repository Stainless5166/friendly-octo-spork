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

`m9_entity_context.feature` is also not `@manual`, for a different
reason than the fault-injection feature above: `EntityContextProvider`
(docs/DESIGN.md §10.8) has no live dependency at all — it's a
self-contained, JSON-fixture-backed knowledge base lookup, the same
"buildable and testable fully offline" category `FileProvider`
already established. No step bindings exist yet; the described
behavior is covered directly by
`tests/core/context/clients/entities/`'s pytest suite instead.

`m10_receipt_archiving.feature` is the same "not `@manual`" shape for a
different reason: the whole pipeline it specifies (docs/DESIGN.md §9.5,
docs/ROADMAP.md M10) is designed to be offline-testable end to end —
`FileProvider`, a recorded receipt-extraction fixture, and local PDF
output, no live account ever required. Fully bound and passing
(`docs/acceptance/steps/m10_receipt_archiving.py`) — the integration
proof composing the modules `m10a`/`m10b`/`m10c`/`m10d` already prove
independently. (`@wip` was used while `spork.core.receipts` was being
built, same mechanism `@manual` uses for "needs a live account" but
for "not built yet" instead, via `SPORK_ACCEPTANCE_WIP` — dropped once
the real step bindings replaced the `NotImplementedError` stubs and
every scenario passed for real, same discipline as graduating an
`xfail` test.) Originally numbered M9; renumbered to M10 when the real
M9 (`m9_entity_context.feature`, above) landed independently on `main`
first — see `docs/ROADMAP.md` M10's own note on the collision.

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
| `m9_entity_context.feature` | Structured domain/company/service/person knowledge base | Fully covered by pytest (`tests/core/context/clients/entities/`); no behave bindings, no live dependency to wait on |
| `m10a_receipt_pdf.feature` | Receipt PDF building + archiving (`spork.core.receipts.pdf`/`archive`) | Fully bound and passing on every run — no live account, no network |
| `m10b_receipt_senders.feature` | Known-sender registry + deterministic extraction (`spork.core.receipts.registry`/`extract`) | Fully bound and passing on every run — no live account, no network |
| `m10c_receipt_extraction_llm.feature` | Recorded Tier 2 receipt-extraction fallback (`spork.core.receipts.llm`) | Fully bound and passing on every run — no live model call |
| `m10d_receipt_provider_capabilities.feature` | Attachment fetching + keyword tagging as Provider capabilities | Fully bound and passing on every run — no live account, no network |
| `m10_receipt_archiving.feature` | Receipt tagging + combined-PDF archiving, deterministic-first with learned Tier 2 fallback | Fully bound and passing on every run — no live account, no network |

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
