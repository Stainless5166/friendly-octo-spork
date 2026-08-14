"""Failure/edge-case tests for spork.core.ipc.server.IpcServer.

Companion to test_server.py's acceptance tests.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from spork.core.ipc.protocol import IpcResponse
from spork.core.ipc.server import IpcServer


def test_ipc_server_returns_error_for_a_malformed_request_line(tmp_path: Path) -> None:
    """Garbage on the wire (not valid IpcRequest JSON) is a clear error
    response, not a dropped connection or a crashed server."""
    socket_path = tmp_path / "sporkd.sock"

    async def _body() -> None:
        stop_event = asyncio.Event()
        task = asyncio.create_task(IpcServer(socket_path, handlers={}).serve(stop_event))
        await asyncio.sleep(0.05)

        reader, writer = await asyncio.open_unix_connection(path=str(socket_path))
        writer.write(b"not json at all\n")
        await writer.drain()
        line = await reader.readline()
        writer.close()
        await writer.wait_closed()
        response = IpcResponse.model_validate_json(line)

        stop_event.set()
        await asyncio.wait_for(task, timeout=2)

        assert response.ok is False
        assert response.error is not None

    asyncio.run(_body())
