"""notify(): the sd_notify(3) wire protocol (docs/DESIGN.md §14).

Hand-rolled against the stdlib `socket` module rather than a new
dependency (`sdnotify`/`cysystemd`, e.g.) — the same "no new dependency
for something this small" call `spork.core.llm.clean`'s hand-rolled
`HTMLParser` subclass made. The real protocol is one `AF_UNIX
SOCK_DGRAM` datagram to whatever path `$NOTIFY_SOCKET` names (a
leading `@` means the Linux abstract namespace, not a real filesystem
path — translated to the actual `\0`-prefixed address libsystemd
uses).
"""

from __future__ import annotations

import os
import socket
from collections.abc import Mapping


def notify(
    state: str,
    *,
    socket_path: str | None = None,
    environ: Mapping[str, str] | None = None,
) -> bool:
    """Send `state` (e.g. `"READY=1"`) to systemd's notification socket.

    `socket_path` overrides `$NOTIFY_SOCKET` when given (mainly for
    tests); otherwise it's read from `environ` (defaulting to the real
    `os.environ`). Returns `False` and sends nothing when there's
    nothing meaningful to do — an empty `state`, no socket address
    available (the common case whenever the calling process isn't
    running under a `Type=notify` unit: every test run, every plain
    `uv run sporkd`), or the address turning out to be stale/unreachable
    once connected to — this is a best-effort readiness signal, not
    something worth taking `sporkd`'s own startup down over. Returns
    `True` once the datagram has actually been sent.
    """
    if not state:
        return False

    env = environ if environ is not None else os.environ
    address = socket_path if socket_path is not None else env.get("NOTIFY_SOCKET")
    if not address:
        return False

    # A leading '@' is systemd's own shorthand for the Linux abstract
    # namespace (no filesystem entry) — the real address is the same
    # string with a NUL byte in place of the '@' (confirmed against
    # libsystemd's own sd_notify() source, not guessed).
    if address.startswith("@"):
        address = "\0" + address[1:]

    sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
    try:
        sock.connect(address)
        sock.sendall(state.encode())
    except OSError:
        return False
    finally:
        sock.close()
    return True
