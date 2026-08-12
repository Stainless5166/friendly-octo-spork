# Benchmarks

Performance measurements for `spork.core` modules — a different kind
of test than correctness, so this directory lives outside `tests/`
(pytest's `testpaths`) and never runs as part of `uv run pytest`.

```bash
uv run pytest benchmarks/                    # run all benchmarks
uv run pytest benchmarks/ --benchmark-only    # skip any plain assertions mixed in
uv run pytest benchmarks/core/pipeline/       # one module's benchmarks
```

Uses [`pytest-benchmark`](https://pytest-benchmark.readthedocs.io/):
each `test_*` function calls the `benchmark` fixture on exactly the
callable being measured (e.g. `benchmark(selector.select, payload)`),
timed over several rounds with statistics printed at the end.

See docs/DESIGN.md §9.4 for why `spork.core.pipeline`'s modules are
built to be benchmarkable in isolation — a bare `Payload` and the one
module under test, no `Pipeline` or full `process_message()` call
needed.
