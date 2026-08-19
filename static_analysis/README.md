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
  "/tmp/spork-{uid}"`) — real. This is the fallback control-socket
  directory used when `$XDG_RUNTIME_DIR` is unset (expected outside a
  systemd user session). `IpcServer.serve()`
  (`core/ipc/server.py:47`) creates it with
  `self._socket_path.parent.mkdir(parents=True, exist_ok=True)` —
  default permissions, and `exist_ok=True` silently reuses whatever
  already exists at that path. On a multi-user machine, another local
  user could pre-create `/tmp/spork-<uid>` (or a symlink at that path)
  before the daemon ever starts; `mkdir(exist_ok=True)` won't notice.
  `os.chmod(self._socket_path, _SOCKET_MODE)` runs *after* the socket
  is bound, which restricts the socket file itself once it exists, but
  doesn't close the window on directory pre-creation/symlink
  redirection before that. Real, if narrow — exploitability depends on
  another local account existing on the same machine, and the
  documented-primary path (`$XDG_RUNTIME_DIR`, a systemd-managed,
  already-per-user directory) doesn't hit this code at all. Not fixed
  here — an application-code change, left for a deliberate decision
  rather than folded into a tooling commit.
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
Not fixed here — this is a routine `uv lock --upgrade-package
cryptography` (or a broader `uv lock --upgrade`) away, but that's a
real change to `uv.lock` that deserves its own verification pass
(`uv run pytest`, `uv run mypy`, confirm `secretstorage`/`keyring`
still resolve to compatible versions), not folded into a tooling
commit that's otherwise config-only.

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
