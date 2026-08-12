"""Acceptance tests for spork.core.ipc.protocol (docs/DESIGN.md §6.2.2).

Newline-delimited JSON, one request per connection — no TOML, no
sockets, no asyncio here at all; this is purely the wire shape.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from spork.core.ipc.protocol import IpcRequest, IpcResponse, encode_line


def test_ipc_request_defaults_params_to_empty_dict() -> None:
    """A command needing no arguments (status, e.g.) doesn't require
    an explicit empty params dict."""
    request = IpcRequest(command="status")

    assert request.params == {}


def test_ipc_response_defaults_data_and_error() -> None:
    """A bare success response needs only ok=True."""
    response = IpcResponse(ok=True)

    assert response.data == {}
    assert response.error is None


def test_ipc_request_rejects_unknown_fields() -> None:
    """A typo'd field is rejected loudly, same extra="forbid"
    convention as every other hand-authored schema in this codebase."""
    with pytest.raises(ValidationError):
        IpcRequest(command="status", bogus_field="x")  # type: ignore[call-arg]


def test_encode_line_produces_one_newline_terminated_json_line() -> None:
    """encode_line() output round-trips through the model it came
    from, and ends in exactly one newline — the framing the server/
    client both read against."""
    request = IpcRequest(command="pause", params={"reason": "maintenance"})

    line = encode_line(request)

    assert line.endswith(b"\n")
    assert line.count(b"\n") == 1
    assert IpcRequest.model_validate_json(line) == request


def test_encode_line_works_for_responses_too() -> None:
    """encode_line() isn't request-specific — the server uses it for
    IpcResponse the same way the client uses it for IpcRequest."""
    response = IpcResponse(ok=False, error="daemon busy")

    line = encode_line(response)

    assert IpcResponse.model_validate_json(line) == response
