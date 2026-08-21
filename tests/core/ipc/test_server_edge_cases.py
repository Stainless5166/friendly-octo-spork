"""Failure/edge-case tests for spork.core.ipc.server.IpcServer.

Companion to test_server.py's acceptance tests.
"""

from __future__ import annotations

import asyncio
import os
import stat
from pathlib import Path

import pytest

from spork.core.ipc.protocol import IpcResponse
from spork.core.ipc.server import IpcServer, IpcServerError


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


def test_ipc_server_creates_a_fresh_socket_directory_with_owner_only_permissions(
    tmp_path: Path,
) -> None:
    """A socket parent directory that doesn't exist yet is created
    private to the current user (0700) -- the same "restrictive by
    construction, not by relying on umask" guarantee the socket file
    itself already gets (docs/DESIGN.md Section 15). This is the
    primary case: /tmp/spork-<uid>/ (the fallback used when
    $XDG_RUNTIME_DIR is unset) genuinely doesn't exist on a fresh boot."""
    socket_dir = tmp_path / "runtime" / "spork"
    socket_path = socket_dir / "sporkd.sock"

    async def _body() -> None:
        stop_event = asyncio.Event()
        task = asyncio.create_task(IpcServer(socket_path, handlers={}).serve(stop_event))
        await asyncio.sleep(0.05)

        mode = stat.S_IMODE(socket_dir.stat().st_mode)

        stop_event.set()
        await asyncio.wait_for(task, timeout=2)

        assert mode == 0o700

    asyncio.run(_body())


def test_ipc_server_accepts_a_preexisting_correctly_permissioned_own_directory(
    tmp_path: Path,
) -> None:
    """Reusing the socket directory across daemon restarts (the normal
    case for $XDG_RUNTIME_DIR/spork/, which persists for the whole
    login session) still works when it's already private to us."""
    socket_dir = tmp_path / "runtime" / "spork"
    socket_dir.mkdir(parents=True, mode=0o700)
    socket_path = socket_dir / "sporkd.sock"

    async def _body() -> None:
        stop_event = asyncio.Event()
        task = asyncio.create_task(IpcServer(socket_path, handlers={}).serve(stop_event))
        await asyncio.sleep(0.05)

        assert socket_path.exists()

        stop_event.set()
        await asyncio.wait_for(task, timeout=2)

    asyncio.run(_body())


def test_ipc_server_refuses_a_world_writable_socket_directory(tmp_path: Path) -> None:
    """A pre-existing socket directory group/other-writable by anyone
    -- exactly what another local user could have left behind at a
    predictable /tmp/spork-<uid>/ path before the daemon ever started
    -- is refused outright, not silently reused (bandit B108)."""
    socket_dir = tmp_path / "runtime" / "spork"
    socket_dir.mkdir(parents=True, mode=0o777)
    socket_path = socket_dir / "sporkd.sock"

    async def _body() -> None:
        with pytest.raises(IpcServerError, match="permissions"):
            await IpcServer(socket_path, handlers={}).serve(asyncio.Event())

    asyncio.run(_body())


def test_ipc_server_refuses_a_socket_directory_owned_by_another_user(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A pre-existing socket directory whose owner doesn't match the
    current process's uid is refused outright -- proof the check is a
    real ownership check, not just a permission-bits check.

    Patches os.getuid() rather than actually os.chown()-ing the
    directory to a different uid: real chown to an arbitrary uid needs
    root/CAP_CHOWN, which this test had (this sandbox runs as root)
    but a normal CI runner legitimately doesn't -- PermissionError
    there, not the IpcServerError this test means to prove.
    """
    socket_dir = tmp_path / "runtime" / "spork"
    socket_dir.mkdir(parents=True, mode=0o700)
    real_uid = os.getuid()
    monkeypatch.setattr(os, "getuid", lambda: real_uid + 1)
    socket_path = socket_dir / "sporkd.sock"

    async def _body() -> None:
        with pytest.raises(IpcServerError, match="owned by"):
            await IpcServer(socket_path, handlers={}).serve(asyncio.Event())

    asyncio.run(_body())


def test_ipc_server_refuses_a_symlinked_socket_directory(tmp_path: Path) -> None:
    """A symlink at the socket directory's path -- pointing anywhere,
    including a location the daemon's own user owns -- is refused
    outright: Path.is_dir() follows symlinks, so exist_ok=True alone
    would silently trust whatever the link resolves to."""
    real_dir = tmp_path / "elsewhere"
    real_dir.mkdir(mode=0o700)
    socket_dir = tmp_path / "runtime" / "spork"
    socket_dir.parent.mkdir(parents=True)
    socket_dir.symlink_to(real_dir)
    socket_path = socket_dir / "sporkd.sock"

    async def _body() -> None:
        with pytest.raises(IpcServerError, match="symlink"):
            await IpcServer(socket_path, handlers={}).serve(asyncio.Event())

    asyncio.run(_body())
