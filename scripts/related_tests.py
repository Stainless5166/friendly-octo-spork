#!/usr/bin/env python3
"""Map a set of changed files to the test files that cover them.

Used by the on-push CI workflow (.github/workflows/push-format-test.yml)
to run a fast, targeted subset of the suite on every push instead of the
whole thing, without pulling in a separate test-selection dependency.
Mapping is by mirrored path (src/spork/a/b.py -> tests/a/test_b.py)
since the package layout in docs/DESIGN.md §6.1 deliberately mirrors
tests/ 1:1. Anything that can't be confidently mapped to a specific
test file falls back to "run everything", since guessing wrong here
would silently drop coverage rather than just cost some CI minutes.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

SRC_ROOT = Path("src/spork")
TEST_ROOT = Path("tests")


def changed_files(base_ref: str, head_ref: str) -> list[str]:
    """Return paths changed between base_ref and head_ref, per git.

    Split out from main() purely so the git invocation is the only
    part of this module that touches process/filesystem state — the
    mapping logic in related_test_files() stays a pure function.
    """
    result = subprocess.run(
        ["git", "diff", "--name-only", base_ref, head_ref],
        check=True,
        capture_output=True,
        text=True,
    )
    return [line for line in result.stdout.splitlines() if line]


def related_test_files(paths: list[str]) -> set[str] | None:
    """Map changed source/test paths to the test files that cover them.

    Returns `None` (meaning "run the whole suite") the moment any
    changed path can't be confidently mapped to one specific test file
    — a non-.py file, a package `__init__.py`, anything outside
    src/spork or tests/ — rather than narrowing on a guess and risking
    a change that silently skips its own coverage.
    """
    tests: set[str] = set()
    for path in paths:
        p = Path(path)
        if not path.endswith(".py"):
            return None
        if str(p).startswith(f"{TEST_ROOT}/") or str(p) == str(TEST_ROOT):
            if p.name.startswith("test_"):
                tests.add(str(p))
                continue
            return None
        if str(p).startswith(f"{SRC_ROOT}/"):
            if p.name == "__init__.py":
                return None
            rel = p.relative_to(SRC_ROOT)
            candidate = TEST_ROOT / rel.parent / f"test_{rel.name}"
            if candidate.exists():
                tests.add(str(candidate))
                continue
            return None
        # Workflow files, docs, pyproject.toml, etc. can affect test
        # behavior in ways this path-based mapping can't see.
        return None
    return tests


def main(argv: list[str]) -> int:
    """CLI wrapper: print either a space-separated test file list, the
    literal token "tests" (meaning "run the whole tests/ dir"), or
    nothing (meaning "no .py changes worth testing")."""
    if len(argv) != 2:
        print("usage: related_tests.py <base_ref> <head_ref>", file=sys.stderr)
        return 2
    base_ref, head_ref = argv
    paths = changed_files(base_ref, head_ref)
    tests = related_test_files(paths)
    if tests is None:
        print("tests")
    elif tests:
        print(" ".join(sorted(tests)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
