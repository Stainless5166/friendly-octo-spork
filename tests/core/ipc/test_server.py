"""Acceptance tests for spork.core.ipc.server.IpcServer (docs/DESIGN.md §6.2.2).

Real Unix domain sockets under pytest's tmp_path, connected to via
asyncio.open_unix_connection — this is the actual wire behavior under
test, not a mocked transport.
"""

from __future__ import annotations

import asyncio
import stat
from pathlib import Path
from typing import Any

from spork.core.ipc.protocol import IpcRequest, IpcResponse, encode_line
from spork.core.ipc.server import IpcServer


async def _send(
    socket_path: Path, command: str, params: dict[str, Any] | None = None
) -> IpcResponse:
    reader, writer = await asyncio.open_unix_connection(path=str(socket_path))
    writer.write(encode_line(IpcRequest(command=command, params=params or {})))
    await writer.drain()
    line = await reader.readline()
    writer.close()
    await writer.wait_closed()
    return IpcResponse.model_validate_json(line)


def test_ipc_server_dispatches_to_the_registered_handler(tmp_path: Path) -> None:
    """A request for a registered command reaches its handler, and the
    handler's return value comes back as the response's data."""
    socket_path = tmp_path / "sporkd.sock"

    async def _body() -> None:
        stop_event = asyncio.Event()
        server = IpcServer(socket_path, handlers={"echo": lambda params: {"got": params}})
        task = asyncio.create_task(server.serve(stop_event))
        await asyncio.sleep(0.05)

        response = await _send(socket_path, "echo", {"x": 1})

        stop_event.set()
        await asyncio.wait_for(task, timeout=2)

        assert response.ok is True
        assert response.data == {"got": {"x": 1}}

    asyncio.run(_body())


def test_ipc_server_returns_error_for_an_unknown_command(tmp_path: Path) -> None:
    """No handler registered for the command: a clear error response,
    never a hang or a crash."""
    socket_path = tmp_path / "sporkd.sock"

    async def _body() -> None:
        stop_event = asyncio.Event()
        task = asyncio.create_task(IpcServer(socket_path, handlers={}).serve(stop_event))
        await asyncio.sleep(0.05)

        response = await _send(socket_path, "nonexistent")

        stop_event.set()
        await asyncio.wait_for(task, timeout=2)

        assert response.ok is False
        assert response.error is not None
        assert "nonexistent" in response.error

    asyncio.run(_body())


def test_ipc_server_returns_error_when_a_handler_raises(tmp_path: Path) -> None:
    """A handler that raises never crashes the server or the
    connection — it's converted to an error response."""
    socket_path = tmp_path / "sporkd.sock"

    def _boom(params: dict[str, Any]) -> dict[str, Any]:
        raise ValueError("something went wrong")

    async def _body() -> None:
        stop_event = asyncio.Event()
        task = asyncio.create_task(
            IpcServer(socket_path, handlers={"boom": _boom}).serve(stop_event)
        )
        await asyncio.sleep(0.05)

        response = await _send(socket_path, "boom")

        stop_event.set()
        await asyncio.wait_for(task, timeout=2)

        assert response.ok is False
        assert "something went wrong" in (response.error or "")

    asyncio.run(_body())


def test_ipc_server_removes_a_stale_socket_file_before_binding(tmp_path: Path) -> None:
    """A leftover socket file from a killed-not-stopped prior run
    doesn't block startup."""
    socket_path = tmp_path / "sporkd.sock"
    socket_path.write_text("stale")  # not even a real socket, just a leftover file

    async def _body() -> None:
        stop_event = asyncio.Event()
        task = asyncio.create_task(
            IpcServer(socket_path, handlers={"status": lambda params: {}}).serve(stop_event)
        )
        await asyncio.sleep(0.05)

        response = await _send(socket_path, "status")

        stop_event.set()
        await asyncio.wait_for(task, timeout=2)

        assert response.ok is True

    asyncio.run(_body())


def test_ipc_server_socket_file_has_restrictive_permissions(tmp_path: Path) -> None:
    """0600 per docs/DESIGN.md §15 — owner read/write only, no group/other access."""
    socket_path = tmp_path / "sporkd.sock"

    async def _body() -> None:
        stop_event = asyncio.Event()
        task = asyncio.create_task(IpcServer(socket_path, handlers={}).serve(stop_event))
        await asyncio.sleep(0.05)

        mode = stat.S_IMODE(socket_path.stat().st_mode)

        stop_event.set()
        await asyncio.wait_for(task, timeout=2)

        assert mode == 0o600

    asyncio.run(_body())


def test_ipc_server_stops_promptly_after_stop_event_is_set(tmp_path: Path) -> None:
    """serve() actually returns once stop_event is set."""
    socket_path = tmp_path / "sporkd.sock"

    async def _body() -> None:
        stop_event = asyncio.Event()
        task = asyncio.create_task(IpcServer(socket_path, handlers={}).serve(stop_event))
        await asyncio.sleep(0.05)
        stop_event.set()

        await asyncio.wait_for(task, timeout=2)

    asyncio.run(_body())
