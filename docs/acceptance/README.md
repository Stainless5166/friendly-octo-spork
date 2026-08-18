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
already established. Its Behave bindings use a fresh temporary JSON
fixture per scenario; the described behavior is also covered directly
by `tests/core/context/clients/entities/`'s pytest suite.

The `m2_local.feature` through `m6_local.feature` specifications apply
the same split to behavior that is locally deterministic but whose
original feature also records live evidence. They use real Spork
components with temporary files, injected collaborators, recorded model
responses, subprocess boundaries, or Unix sockets. They do not replace
the original live specifications:

- M2 local rules and retry behavior run without JMAP; `spork rules test`
  against recent live mail remains in `m2_rules.feature`.
- M3 local confidence, budget, draft, and failure-safety behavior runs
  with recorded responses; live LiteLLM/Anthropic evidence remains in
  `m3_tier2.feature`.
- M4 local VIP, Tier 2, and DBus fallback behavior runs with injected
  alerters; prolonged push-health acceptance remains live.
- M5 local control-surface behavior uses a real temporary daemon socket;
  the live feature remains the daemon-account acceptance specification.
- M6 local unit, install, doctor, and `sd_notify` boundaries use fake
  systemctl and temporary sockets; real user-manager lifecycle remains
  live.

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

## Docker Release Run

For release evidence, use the bounded Docker runner instead of leaving a
manually assembled daemon container running:

```bash
uv run python scripts/docker_live_acceptance.py \
  --account validate@fastmail.com \
  --output /tmp/spork-acceptance-report.json
```

The runner creates a temporary Docker network and a non-root, read-only daemon
container. It checks status, pause/resume, live rule preview, additive tag,
move, first-match precedence, restart idempotency, and recovery after the
daemon's network is disconnected while three messages are sent. The verifier
queries Fastmail from outside the daemon and compares final mailbox membership
with the durable SQLite `audit_log`. The report contains message IDs and
counts, never message bodies or credentials.

The default dependency mounts match the disposable acceptance environment. For
another prepared image environment, set `SPORK_ACCEPTANCE_VENV` and
`SPORK_ACCEPTANCE_PACKAGES`, or pass `--venv` and `--packages` explicitly. A
non-zero exit means at least one check failed; the report is still written.

## Status

| Feature | Scope | Current evidence |
|---|---|---|
| `m1_jmap.feature` | JMAP session, push, fallback, cursor safety | `@baseline` and `@push` bound, live-verified; `@cursor-safety`/`@network-recovery` still open (need a real restart cycle / real network control) |
| `m1_jmap_fault_injection.feature` | Push/fallback composition, simulated | Fully bound and passing on every run — mitmproxy harness, no live account |
| `m2_rules.feature` | Live deterministic rules and actions | Live JMAP evidence open; local rules/retry coverage is in `m2_local.feature` |
| `m2_local.feature` | Offline deterministic rules and retry safety | Fully bound and passing; no live account or network |
| `m3_tier2.feature` | Live LLM verdicts, confidence, budget, drafts | Live model and JMAP evidence open; local policy coverage is in `m3_local.feature` |
| `m3_local.feature` | Offline recorded Tier 2 policy and safety | Fully bound and passing; no live model or mailbox |
| `m4_alerting.feature` | Alerts, push health, desktop delivery | Push-health/live delivery evidence remains open; local policy coverage is in `m4_local.feature` |
| `m4_local.feature` | Offline alert policy and DBus fallback | Fully bound and passing; no desktop session or live daemon |
| `m5_control_surface.feature` | Live daemon and CLI control surface | Live-account path remains open; local control coverage is in `m5_local.feature` |
| `m5_local.feature` | Offline daemon and CLI control surface | Fully bound and passing; real temporary Unix socket, no live account |
| `m6_systemd.feature` | Live service install and operational startup | Real user-session lifecycle remains open; local boundaries are in `m6_local.feature` |
| `m6_local.feature` | Offline systemd file, install, doctor, and notify boundaries | Fully bound and passing; no user manager or JMAP |
| `m7_hardening.feature` | Unattended operation and v1 release | Requires real mailbox, model, rate-limit, and one-week run |
| `m9_entity_context.feature` | Structured domain/company/service/person knowledge base | Fully bound and passing; temporary JSON fixture, no live dependency |
| `m10a_receipt_pdf.feature` | Receipt PDF building + archiving (`spork.core.receipts.pdf`/`archive`) | Fully bound and passing on every run — no live account, no network |
| `m10b_receipt_senders.feature` | Known-sender registry + deterministic extraction (`spork.core.receipts.registry`/`extract`) | Fully bound and passing on every run — no live account, no network |
| `m10c_receipt_extraction_llm.feature` | Recorded Tier 2 receipt-extraction fallback (`spork.core.receipts.llm`) | Fully bound and passing on every run — no live model call |
| `m10d_receipt_provider_capabilities.feature` | Attachment fetching + keyword tagging as Provider capabilities | Fully bound and passing on every run — no live account, no network |
| `m8_safety.feature` | Company-mail observer, read-only report/action plan, and production safety gate | Manual evidence specification; observer/report implementation is locally tested, live account approval remains open |
| `m11_classification.feature` | Classification accumulation and one-mailbox/many-tag decisions | Fully bound and passing locally; live provider execution remains open |
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
