"""Concrete LLMClient adapters — one backend per module (docs/DESIGN.md §10.1).

Mirrors `spork.core.providers.<name>`: `LiteLLMClient` is the live
in-process backend and `RecordedLLMClient` is its deterministic CI
sibling, not a mode bolted onto the live client.
"""
