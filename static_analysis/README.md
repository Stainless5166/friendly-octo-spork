# Static analysis

Security/dead-code/dependency static analysis, distinct from
ruff/mypy's correctness checks in `pr-checks.yml`/`push-format-test.yml`
— these run manually and on a weekly schedule
(`.github/workflows/static-analysis.yml`), same non-blocking treatment
`mutation-testing.yml` already established (a finding is a prompt for a
human, not a gate on a schedule nobody's watching in real time).

```bash
uv run bandit -c pyproject.toml -r src/spork   # security patterns
uv run vulture src/spork static_analysis/vulture_whitelist.py  # dead code
uv run deptry .                                # unused/undeclared dependencies
uv export --no-dev --frozen --no-hashes --no-emit-project -o /tmp/prod-reqs.txt
uv run pip-audit -r /tmp/prod-reqs.txt --strict  # dependency CVEs
```

`pip-audit` needs the export step because it audits packages against
PyPI by name — pointed at the live environment (or a requirements file
that still lists the project itself) it errors out trying to look up
`spork`, which isn't a published package.

## Baseline (this run)

**bandit**: 6 issues (5 low, 1 medium) against `src/spork`, all
individually triaged below — none silently accepted.

**vulture**: 0 findings against `src/spork` once
`static_analysis/vulture_whitelist.py` is included — every one of its
47 entries was hand-verified against the real code (not accepted
blindly from `--make-whitelist`'s output); see the whitelist file
itself for the reasoning, grouped by category.

**deptry**: 0 findings once `[tool.deptry]` (`pyproject.toml`) sets
`known_first_party = ["spork"]` and per-rule-ignores for `jmapc`/
`litellm`/`behave`.

**pip-audit**: **7 known vulnerabilities in `cryptography` 44.0.3** —
a real, open finding, not suppressed. See below.

## Triaged bandit findings — skipped globally, reasoning per category

Configured in `pyproject.toml`'s `[tool.bandit]` `skips`:

- **B404** (`subprocess` import) / **B603** (`subprocess` call without
  `shell=True`) — five call sites total (`cli/commands/config.py`,
  `cli/commands/rules.py`'s `$EDITOR` spawn; `core/alerts/desktop.py`,
  `core/systemd/install.py`, `core/systemd/unit.py`). Every one uses a
  list of arguments (`shlex.split(...)`/explicit list), never
  `shell=True` — B603's own point is exactly this pattern *is* the safe
  one; bandit flags it anyway because it can't verify the arguments
  are trusted. `$EDITOR` is the invoking user's own environment
  variable, not attacker-supplied content (email body, JMAP response) —
  there's no untrusted-input path here to begin with.
- **B406** (`xml.sax.saxutils.escape`, `core/receipts/pdf.py`) —
  bandit's blacklist rule is written for the vulnerable XML *parsing*
  functions in the same stdlib module tree; `escape()` is an
  output-escaping helper (encoding text for a ReportLab-generated PDF),
  not a parser, and never touches untrusted XML input. A rule-name
  false positive, not a real finding.
- **B110** (`try/except/pass`, `core/receipts/pdf.py`, two sites) —
  already has its own `# noqa: BLE001` with documented reasoning ("any
  parse/decode failure degrades to a placeholder") right next to the
  code; bandit's version of the same objection, already answered.

## Triaged bandit findings — deliberately left visible, not skipped

- **B108** (hardcoded `/tmp` path, medium severity,
  `core/config/paths.py:31`, `_FALLBACK_RUNTIME_DIR_TEMPLATE =
  "/tmp/spork-{uid}"`) — real, and **fixed**, though bandit's own
  finding still fires (it's a lexical match on the hardcoded path
  string in this file, blind to the runtime mitigation in
  `core/ipc/server.py`). This is the fallback control-socket directory
  used when `$XDG_RUNTIME_DIR` is unset (expected outside a systemd
  user session). `IpcServer.serve()` used to create it with a bare
  `self._socket_path.parent.mkdir(parents=True, exist_ok=True)` —
  default permissions, silently reusing whatever already existed at
  that path. On a multi-user machine, another local user could have
  pre-created `/tmp/spork-<uid>` (or a symlink at that path) before
  the daemon ever started; `mkdir(exist_ok=True)` alone wouldn't
  notice. Fixed: `_ensure_private_dir()` (`core/ipc/server.py`) now
  refuses a pre-existing directory that's a symlink, owned by a
  different uid, or has any group/other permission bit set — raising
  `IpcServerError` instead of silently proceeding — and creates a
  fresh one at `0o700` explicitly rather than relying on umask. The
  documented-primary path (`$XDG_RUNTIME_DIR`, a systemd-managed,
  already-per-user directory) never trips any of the three checks in
  practice.
- **B101** (`assert` used, 5 sites: `core/alerts/smtp.py`,
  `core/context/clients/entities/provider.py`,
  `core/providers/jmap/client.py` ×3) — each is an internal
  invariant check ("this can't be `None` here, given the code path
  that already ran"), not input validation. Bandit's objection is real
  but narrow: `assert` statements are stripped under `python -O`,
  which nothing in this project's packaging/systemd unit ever invokes
  — but if that ever changed, these would silently stop checking
  anything instead of raising. Left visible as a low-priority, real
  category rather than globally skipped; a future pass could replace
  the ones that matter with real exceptions.

## Real, open finding: `pip-audit`

`cryptography` 44.0.3 has 7 known vulnerabilities (6 unique IDs; one
listed twice under `PYSEC-2026-35`), fixed in versions ranging 46.0.5
to 50.0.0 depending on the CVE. Traced with `uv tree --invert --package
cryptography`:

```
cryptography v44.0.3
├── aioquic → mitmproxy            (dev-only: the fault-injection test harness)
├── pyopenssl → aioquic/mitmproxy  (dev-only)
├── secretstorage → keyring        (production: keyring is a base dependency)
└── service-identity → aioquic     (dev-only)
```

Three of the four paths are dev-only (`mitmproxy`'s dependency tree,
never shipped). The fourth — `keyring` → `secretstorage` →
`cryptography` — **is** in the production dependency graph (`keyring`
is a base `[project]` dependency, used for the OS keychain backend).

**Not a routine lock refresh after all** — tried it, and it doesn't
work: every `mitmproxy` 11.x release (`pyproject.toml`'s current
`mitmproxy>=11,<12` pin) caps its own `cryptography` dependency at
`<44.1`, below every fix version (`uv lock --upgrade-package
cryptography` confirms 44.0.3 is already the newest version satisfying
all current constraints). Bumping the dev-only `mitmproxy` pin to
`>=12,<13` (the only way to relax that cap) hits a harder blocker:
`mitmproxy>=12.0.0` requires Python `>=3.12`, and this project's
`requires-python = ">=3.11"` — raising the project's own minimum
Python version is a real, consequential decision for a dev-only test
dependency's sake, not a tooling-commit change, and even mitmproxy
12.2.3's own cap (`cryptography<=48.1`) would only cover 4 of the 7
CVEs (the two requiring 49.0.0/50.0.0 would still be unresolved).
Reverted; left as a genuinely open item, not silently dropped — the
actual fix needs a `requires-python` decision made deliberately, on
its own, not folded into closing this one CVE.

## Scope rationale

Unlike mutation testing (`mutation/README.md`, scoped to eight
decision-critical modules), these four tools run against the whole
`src/spork` tree — dead code, security patterns, and dependency
hygiene aren't decision-correctness concerns the same
precondition-gated way §16.1/§16.2 reason about, so there's no
narrower "worth it" scope to apply. `deptry` additionally scans the
whole repo (not just `src/spork`) since its job is cross-checking
`pyproject.toml` against every real import site, including
`docs/acceptance/`'s Gherkin step definitions.
