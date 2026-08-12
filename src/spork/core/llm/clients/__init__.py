"""Concrete LLMClient adapters — one backend per module (docs/DESIGN.md §10.1).

Mirrors `spork.core.providers.<name>`: `AnthropicLLMClient` is the
first (and today, only) backend; a second is a sibling module here,
not a special case bolted onto this one.
"""
