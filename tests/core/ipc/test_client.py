"""Acceptance tests for spork.core.ipc.client.send_request() (docs/DESIGN.md §6.2.2).

The CLI's side: plain synchronous `socket`, tested against a real
`IpcServer` running in the background of the same event loop (via
asyncio.to_thread, since send_request() itself is sync).
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from spork.core.ipc.client import IpcConnectionError, send_request
from spork.core.ipc.server import IpcServer


def test_send_request_returns_the_servers_response(tmp_path: Path) -> None:
    """A real round trip: connect, send, get the handler's data back."""
    socket_path = tmp_path / "sporkd.sock"

    async def _body() -> None:
        stop_event = asyncio.Event()
        task = asyncio.create_task(
            IpcServer(socket_path, handlers={"echo": lambda params: {"got": params}}).serve(
                stop_event
            )
        )
        await asyncio.sleep(0.05)

        response = await asyncio.to_thread(send_request, socket_path, "echo", {"x": 1})

        stop_event.set()
        await asyncio.wait_for(task, timeout=2)

        assert response.ok is True
        assert response.data == {"got": {"x": 1}}

    asyncio.run(_body())


def test_send_request_defaults_params_to_empty_dict(tmp_path: Path) -> None:
    """Calling without params sends an empty dict, not None/omitted."""
    socket_path = tmp_path / "sporkd.sock"

    async def _body() -> None:
        stop_event = asyncio.Event()
        task = asyncio.create_task(
            IpcServer(socket_path, handlers={"echo": lambda params: {"got": params}}).serve(
                stop_event
            )
        )
        await asyncio.sleep(0.05)

        response = await asyncio.to_thread(send_request, socket_path, "echo")

        stop_event.set()
        await asyncio.wait_for(task, timeout=2)

        assert response.data == {"got": {}}

    asyncio.run(_body())


def test_send_request_raises_ipcconnectionerror_when_nothing_is_listening(
    tmp_path: Path,
) -> None:
    """No socket file at all — the "daemon not running" case every CLI
    command needs to detect and message clearly (docs/DESIGN.md §6.3)."""
    socket_path = tmp_path / "does-not-exist.sock"

    with pytest.raises(IpcConnectionError):
        send_request(socket_path, "status")
