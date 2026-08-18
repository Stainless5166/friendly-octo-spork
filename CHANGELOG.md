# Changelog

## 0.2.0b1 - Internal Tier 1 Beta

### Added

- Guarded live JMAP mailbox moves, additive tags, and draft creation.
- Account identity and write-capability validation for the configured JMAP
  account.
- Read-only `spork rules test` previews against recent JMAP mail.
- `scripts/send_test_email.py` for controlled SMTP acceptance messages.
- `scripts/docker_live_acceptance.py` for bounded release acceptance runs,
  including network outage recovery and restart idempotency.
- `spork alerts test` for local log and desktop alert verification.
- Tag-triggered GitHub release artifact automation.

### Beta Boundary

- This release is deterministic Tier 1 only.
- Tier 2 model-provider validation and live escalation are outside this
  release.
- Run the one-week internal burn-in described in `docs/BETA.md` before
  enabling broader mailbox scope.
