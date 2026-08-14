"""Failure/edge-case tests for spork.core.ipc.client.send_request().

Companion to test_client.py's acceptance tests.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from spork.core.ipc.client import IpcConnectionError, send_request


def test_send_request_raises_when_server_closes_without_responding(tmp_path: Path) -> None:
    """A listener that accepts the connection but closes it without
    ever writing a response line — a misbehaving/crashed handler on
    the other end, not just "nothing listening" at all."""
    socket_path = tmp_path / "sporkd.sock"

    async def _accept_and_close(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        writer.close()
        await writer.wait_closed()

    async def _body() -> None:
        server = await asyncio.start_unix_server(_accept_and_close, path=str(socket_path))
        async with server:
            with pytest.raises(IpcConnectionError):
                await asyncio.to_thread(send_request, socket_path, "status")

    asyncio.run(_body())
