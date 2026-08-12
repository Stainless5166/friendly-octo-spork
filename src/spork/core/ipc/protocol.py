"""The control-socket wire shape (docs/DESIGN.md §6.2.2).

Newline-delimited JSON, one request per connection — settled when M5
was first scoped: no new dependency (stdlib `json` via pydantic), and
§15 already establishes filesystem permissions as the only access
control v1 needs, so nothing fancier is warranted.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class IpcRequest(BaseModel):
    """One command sent from `spork` to `sporkd` over the control socket."""

    model_config = ConfigDict(extra="forbid")

    command: str
    params: dict[str, Any] = Field(default_factory=dict)


class IpcResponse(BaseModel):
    """`sporkd`'s reply to one `IpcRequest`.

    `error` is set (and `ok=False`) whenever a handler raises —
    `IpcServer` converts every exception into this shape rather than
    ever writing a raw traceback back down the socket.
    """

    model_config = ConfigDict(extra="forbid")

    ok: bool
    data: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None


def encode_line(message: IpcRequest | IpcResponse) -> bytes:
    """Frame `message` as one newline-terminated JSON line, UTF-8 encoded.

    Shared by both `IpcServer` (encoding responses) and
    `send_request()` (encoding requests) so the framing logic exists
    in exactly one place.
    """
    return (message.model_dump_json() + "\n").encode("utf-8")
