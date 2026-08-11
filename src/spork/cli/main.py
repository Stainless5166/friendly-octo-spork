"""Entry point for the `spork` executable.

Placeholder for the same reason as `spork.daemon.main`: the command
surface in docs/DESIGN.md §12 (status/rules/config/logs/...) is built
milestone-by-milestone against acceptance tests, not stubbed out ahead
of the logic it would call.
"""


def main() -> None:
    """Process entry point registered as the `spork` console script.

    Raises NotImplementedError until the CLI command surface (M5 in
    docs/ROADMAP.md) is built; exists now purely so `uv run spork`
    resolves to something during scaffolding.
    """
    raise NotImplementedError(
        "spork CLI is not implemented yet — see docs/ROADMAP.md for milestone status."
    )


if __name__ == "__main__":
    main()
