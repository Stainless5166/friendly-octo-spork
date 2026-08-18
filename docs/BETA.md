# Beta Release Plan

This document defines the release boundary for Spork's internal beta. It is
deliberately narrower than the eventual Tier 2 and v1 release.

## Confirmed Scope

- Release artifact: signed `v0.2.0b1` tag and built wheel.
- First beta: deterministic Tier 1 rules only.
- First target after the dedicated test account: the maintainer's personal
  work account.
- Alerts: operational logs plus local desktop notifications.
- LLM support: provider-agnostic and outside the first beta release. Personal
  use may later combine Ollama and Anthropic for different tasks.
- Burn-in: one week for deterministic Tier 1, two weeks for Tier 2, then one
  month of stable operation before `v1.0.0`.
- Release automation: a tag-triggered GitHub Actions workflow builds the wheel
  and creates a draft GitHub release. The maintainer signs the tag locally with
  the downstream GPG release key before pushing it.

## Phase 0: `v0.2.0b1`

1. Update version and packaging metadata in `pyproject.toml` and `PKGBUILD`.
2. Add the beta changelog and refresh README caveats.
3. Update the roadmap and test inventory with the live JMAP and Docker
   acceptance evidence.
4. Run the full test, lint, format, and mypy gates.
5. Build the wheel with `uv build --wheel`.
6. Create and locally verify a GPG-signed `v0.2.0b1` tag.
7. Push the tag to trigger the draft-release workflow.

## Phase 1: Tier 1 Internal Beta

The beta account must use a narrow deterministic ruleset. Tier 2 remains
disabled and unmatched mail remains in the configured safe treatment.

Set this explicit gate in the beta config:

```toml
[tiering]
tier2_enabled = false
default_unmatched_action = "ignore"
```

1. Add `spork rules validate` with human-readable output and `--json` output.
2. Fail closed when an `escalate` rule is present without an explicitly
   configured LLM backend.
3. Warn from `spork doctor` when writes are enabled without
   `expected_account_email`.
4. Add `spork alerts test` to verify the configured log and desktop alert
   paths without requiring a real message.
5. Run the Docker release acceptance harness against the dedicated account.
6. Configure the personal work account only after the dedicated-account run
   passes and `spork report` has been reviewed.
7. Run deterministic Tier 1 for one week, reviewing the audit log daily.

## Phase 1 Exit Criteria

- `v0.2.0b1` exists as a signed tag and wheel artifact.
- Full CI gates pass on the tagged source.
- `spork rules validate` passes for the intended Tier 1 configuration.
- Escalation rules fail closed when Tier 2 is not configured.
- `spork doctor` warns about unsafe write-account configuration.
- `spork alerts test` is confirmed in logs and by a visible desktop
  notification on the maintainer's machine.
- The Docker release acceptance report passes.
- The personal work account completes one week with no major error or
  unexplained audit event.

## Phase 2: Tier 2 Beta

Phase 2 is intentionally not part of `v0.2.0b1`. It will add a provider
validator that can exercise any configured model provider, then run two weeks
of explicitly approved Tier 2 behavior. The validator must cover structured
verdict shape, invalid output, confidence bands, budget exhaustion, alerting,
draft creation, and the never-send invariant.

## Phase 3: `v1.0.0`

After the Tier 1 and Tier 2 burn-ins, run one month with no major errors before
tagging `v1.0.0`. Final release approval also requires systemd restart
evidence, rate-limit evidence, push-health alert evidence, and a complete
audit reconstruction of selected messages and control-plane changes.

## Release Commands

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv build --wheel
git tag -s v0.2.0b1 -m "Internal beta: deterministic Tier 1 triage"
git show --show-signature v0.2.0b1
git push origin main v0.2.0b1
```

The tag-triggered workflow creates a draft release. It does not create or
manage a private GPG key; signing remains a local release-owner operation.
