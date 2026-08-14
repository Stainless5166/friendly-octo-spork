"""send_request(): the CLI's side of the control socket (docs/DESIGN.md §6.2.2).

Plain synchronous `socket` — `spork` is a short-lived process, not
another asyncio loop, so there's nothing to gain from bridging this
into asyncio the way `sporkd`'s own blocking calls are (§6.2.1).
"""

from __future__ import annotations

import socket
from pathlib import Path
from typing import Any

from spork.core.ipc.protocol import IpcRequest, IpcResponse, encode_line


class IpcConnectionError(Exception):
    """Raised when nothing's listening on the control socket.

    The single signal every CLI command that talks to the daemon
    checks for, to print "daemon not running" (docs/DESIGN.md §6.3)
    instead of a raw traceback.
    """


def send_request(
    socket_path: Path,
    command: str,
    params: dict[str, Any] | None = None,
    *,
    timeout: float = 5.0,
) -> IpcResponse:
    """Sends one `IpcRequest` and returns `sporkd`'s `IpcResponse`.

    One connection per call, matching `IpcServer`'s one-request-per-
    connection contract (§6.2.2).
    """
    request = IpcRequest(command=command, params=params or {})
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
            sock.settimeout(timeout)
            sock.connect(str(socket_path))
            sock.sendall(encode_line(request))
            with sock.makefile("rb") as f:
                line = f.readline()
    except OSError as exc:
        raise IpcConnectionError(f"could not reach sporkd at {socket_path}: {exc}") from exc

    if not line:
        raise IpcConnectionError(
            f"sporkd at {socket_path} closed the connection without responding"
        )
    return IpcResponse.model_validate_json(line)
