"""Failure/edge-case tests for spork.core.rules.writer.

Companion to test_writer.py's round-trip acceptance tests.
"""

from __future__ import annotations

import pytest

from spork.core.rules.writer import _toml_value


def test_toml_value_raises_type_error_for_an_unsupported_python_type() -> None:
    """`Condition`/`Action`'s fields are only ever bool/str/list[str]/None
    (None already excluded by model_dump(exclude_none=True) before this
    is called) — an int or dict reaching here would mean the schema
    grew a field kind this serializer doesn't know about yet. Fails
    loud rather than silently emitting something invalid."""
    with pytest.raises(TypeError):
        _toml_value(3.14)
