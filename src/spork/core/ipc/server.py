"""IpcServer: serves the control socket (docs/DESIGN.md §6.2.2).

Runs alongside `_run_message_loop()` inside `run_daemon()`'s
`asyncio.TaskGroup()` (§6.2.1) — `asyncio.start_unix_server()`, stdlib,
no new dependency.
"""

from __future__ import annotations

import asyncio
import os
import stat
from collections.abc import Callable
from pathlib import Path
from typing import Any

from spork.core.ipc.protocol import IpcRequest, IpcResponse, encode_line

# Owner read/write only — no group/other access (docs/DESIGN.md §15).
_SOCKET_MODE = stat.S_IRUSR | stat.S_IWUSR
# Owner read/write/execute only, for the socket's parent directory.
_DIR_MODE = stat.S_IRWXU


class IpcServerError(Exception):
    """Raised when the socket's parent directory can't be trusted.

    Covers the fallback `/tmp/spork-<uid>/` path
    (`spork.core.config.paths.resolve_socket_path()`) used when
    `$XDG_RUNTIME_DIR` is unset — a shared, world-writable parent
    directory where another local user could have pre-created
    something at this exact path before the daemon ever started
    (bandit B108: a hardcoded `/tmp` path with no ownership check was
    a real, if narrow, gap). `$XDG_RUNTIME_DIR/spork/` itself never
    hits any of these three checks in practice — it's already private,
    already ours, and never a symlink — so this only ever fires on the
    degraded fallback path, exactly where it matters.
    """


def _ensure_private_dir(path: Path) -> None:
    """Create `path` restricted to the current user, or verify a
    pre-existing one already is — refusing to reuse a directory
    `mkdir(exist_ok=True)` alone would silently trust.

    Three checks, in order of how cheaply each can be ruled out:
    a symlink (`Path.is_dir()` follows symlinks, so `exist_ok=True`
    alone would happily bind through one to wherever it points),
    ownership (a directory another uid controls, even with tight
    permissions, is still that uid's to recreate/replace), and group/
    other permission bits (readable/writable by anyone on the
    machine). `os.chmod` after `mkdir` normalizes the freshly-created
    case too, since `mkdir(mode=...)` is itself subject to umask.
    """
    if path.is_symlink():
        raise IpcServerError(f"refusing to use {path} for the control socket: it's a symlink")
    path.mkdir(parents=True, exist_ok=True, mode=_DIR_MODE)
    dir_stat = path.stat()
    if dir_stat.st_uid != os.getuid():
        raise IpcServerError(
            f"refusing to use {path} for the control socket: owned by "
            f"uid {dir_stat.st_uid}, not the current user (uid {os.getuid()})"
        )
    if stat.S_IMODE(dir_stat.st_mode) & (stat.S_IRWXG | stat.S_IRWXO):
        raise IpcServerError(
            f"refusing to use {path} for the control socket: its permissions "
            f"({oct(stat.S_IMODE(dir_stat.st_mode))}) grant group/other access"
        )
    os.chmod(path, _DIR_MODE)


class IpcServer:
    """Dispatches one `IpcRequest` per connection to a registered handler.

    `handlers` maps a command name to a plain sync callable taking
    `params` and returning a `dict` — `IpcServer` never knows what any
    command *means*, the same DI pattern as everything else in this
    codebase. A handler that raises never crashes the connection or
    the server: it becomes `IpcResponse(ok=False, error=str(exc))`,
    same as an unknown command or a malformed request line.
    """

    def __init__(
        self, socket_path: Path, handlers: dict[str, Callable[[dict[str, Any]], dict[str, Any]]]
    ) -> None:
        self._socket_path = socket_path
        self._handlers = handlers

    async def serve(self, stop_event: asyncio.Event) -> None:
        """Binds the socket and serves connections until `stop_event` is set.

        Removes any stale socket file at `socket_path` first — a
        leftover from a killed-not-stopped prior run would otherwise
        block binding with "address already in use".
        """
        _ensure_private_dir(self._socket_path.parent)
        self._socket_path.unlink(missing_ok=True)
        server = await asyncio.start_unix_server(self._handle_client, path=str(self._socket_path))
        os.chmod(self._socket_path, _SOCKET_MODE)
        try:
            async with server:
                await stop_event.wait()
        finally:
            self._socket_path.unlink(missing_ok=True)

    async def _handle_client(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        try:
            line = await reader.readline()
            request = IpcRequest.model_validate_json(line)
        except Exception as exc:
            response = IpcResponse(ok=False, error=f"invalid request: {exc}")
        else:
            response = self._dispatch(request)

        writer.write(encode_line(response))
        await writer.drain()
        writer.close()
        await writer.wait_closed()

    def _dispatch(self, request: IpcRequest) -> IpcResponse:
        handler = self._handlers.get(request.command)
        if handler is None:
            return IpcResponse(ok=False, error=f"unknown command: {request.command!r}")
        try:
            return IpcResponse(ok=True, data=handler(request.params))
        except Exception as exc:
            return IpcResponse(ok=False, error=str(exc))
