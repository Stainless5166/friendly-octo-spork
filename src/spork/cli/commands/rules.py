"""`spork rules` subcommands (docs/DESIGN.md §12).

Only `test` exists so far — `list`/`edit`/`enable`/`disable` are M5
work needing the daemon control socket this CLI doesn't have yet.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import typer

from spork.core.rules.loader import RulesLoadError, load_rules
from spork.core.rules.schema import Rule

app = typer.Typer(
    name="rules",
    help="Inspect and dry-run rules.toml files.",
    no_args_is_help=True,
)


@app.command("test")
def test(
    rules_file: Path = typer.Argument(  # noqa: B008 - idiomatic Typer, not a mutable default
        ..., help="Path to a rules.toml file to dry-run."
    ),
) -> None:
    """Dry-run a rules.toml file against recent mail (docs/DESIGN.md §13).

    Loads and validates the file first — real, useful on its own, and
    catches a malformed rules.toml here rather than as a crash once it
    reaches the daemon. Actually running it against recent mail needs a
    live JMAP connection (docs/DESIGN.md §9.3, §13): spork has no local
    mail store to substitute for one, so that part isn't implemented
    until M1's real JMAP fetch exists — this fails loud rather than
    faking a result.
    """
    try:
        rules = load_rules(rules_file)
    except RulesLoadError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    typer.echo(f"Loaded {len(rules)} rule(s) from {rules_file}.")

    # Caught and re-reported as a clean message rather than left to
    # propagate: this is a genuinely unimplemented feature (real
    # NotImplementedError semantics, see spork.core.rules.loader's
    # docstring and docs/ROADMAP.md M1), not a bug — a user shouldn't
    # see a stack trace for "this part isn't built yet."
    try:
        _dry_run_against_recent_mail(rules)
    except NotImplementedError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc


def _dry_run_against_recent_mail(rules: Sequence[Rule]) -> None:
    """The part that genuinely needs a live JMAP connection (docs/DESIGN.md §13).

    Spork has no local mail store to substitute for "recent mail" —
    fetching it here means a real `JmapClient.fetch_new_messages()`
    call, which is itself a settled-shape `NotImplementedError` stub
    pending a live Fastmail account (docs/ROADMAP.md M1). This function
    exists so that blocker has one clearly-named place to live, instead
    of being inlined into the command body.
    """
    raise NotImplementedError(
        "spork rules test requires a live JMAP connection to fetch recent mail — "
        "not implemented yet, see docs/ROADMAP.md M1"
    )
