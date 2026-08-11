"""Entry point for the `sporkd` executable.

This is a placeholder: the daemon event loop (JMAP session, push
listener, rule engine, action executor, alerting, control socket —
docs/DESIGN.md §6.2) lands incrementally across the roadmap milestones
in docs/ROADMAP.md, each behind its own acceptance tests. Wiring it up
here before those pieces exist would give a runnable-looking daemon that
does nothing correct, which is worse than an explicit "not yet".
"""


def main() -> None:
    """Process entry point registered as the `sporkd` console script.

    Raises NotImplementedError until the roadmap milestones that build
    the daemon's actual event loop (M1-M6) land; exists now purely so
    `uv run sporkd` resolves to something during scaffolding.
    """
    raise NotImplementedError(
        "sporkd is not implemented yet — see docs/ROADMAP.md for milestone status."
    )


if __name__ == "__main__":
    main()
