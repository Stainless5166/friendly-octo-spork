#!/usr/bin/env python3
"""Small local SMTP sink for acceptance tests.

It deliberately supports only the plaintext SMTP subset used by the local
acceptance profile. ``--fail-after`` closes the connection after that many
messages, which makes alert-delivery failure deterministic without involving
an external relay or a real mailbox.
"""

from __future__ import annotations

import argparse
import json
import socket
import socketserver
import threading
from pathlib import Path


class _State:
    """Thread-safe message store shared by SMTP handler instances."""

    def __init__(self, record_path: Path, fail_after: int | None) -> None:
        self.record_path = record_path
        self.fail_after = fail_after
        self.messages: list[str] = []
        self.lock = threading.Lock()

    def record(self, message: str) -> bool:
        """Record one message and return whether the connection should fail."""
        with self.lock:
            self.messages.append(message)
            self.record_path.write_text(json.dumps(self.messages, indent=2) + "\n")
            return self.fail_after is not None and len(self.messages) >= self.fail_after


class _Handler(socketserver.StreamRequestHandler):
    """Minimal SMTP conversation handler for local, unauthenticated tests."""

    def _send(self, line: str) -> None:
        self.wfile.write((line + "\r\n").encode("ascii"))
        self.wfile.flush()

    def handle(self) -> None:
        state: _State = self.server.state  # type: ignore[attr-defined]
        self._send("220 spork acceptance SMTP")
        data_mode = False
        lines: list[str] = []
        while True:
            raw = self.rfile.readline()
            if not raw:
                return
            line = raw.decode("utf-8", errors="replace").rstrip("\r\n")
            if data_mode:
                if line == ".":
                    should_fail = state.record("\n".join(lines))
                    if should_fail:
                        self.request.shutdown(socket.SHUT_RDWR)
                        return
                    self._send("250 2.0.0 accepted")
                    data_mode = False
                    lines = []
                else:
                    lines.append(line[1:] if line.startswith("..") else line)
                continue
            command = line.upper()
            if command.startswith(("EHLO", "HELO")):
                self._send("250-spork")
                self._send("250 SIZE 10485760")
            elif command.startswith("MAIL FROM:") or command.startswith("RCPT TO:"):
                self._send("250 2.1.0 ok")
            elif command == "DATA":
                self._send("354 End data with <CR><LF>.<CR><LF>")
                data_mode = True
            elif command == "RSET":
                lines = []
                self._send("250 2.0.0 reset")
            elif command == "QUIT":
                self._send("221 2.0.0 bye")
                return
            else:
                self._send("250 2.0.0 ok")


class _Server(socketserver.ThreadingTCPServer):
    """Reusable threaded server exposing the shared harness state."""

    allow_reuse_address = True

    def __init__(self, address: tuple[str, int], state: _State) -> None:
        self.state = state
        super().__init__(address, _Handler)


def main() -> None:
    """Run the sink until interrupted."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=1025)
    parser.add_argument("--record", type=Path, required=True)
    parser.add_argument(
        "--fail-after",
        type=int,
        help="Close the connection after recording this many messages.",
    )
    args = parser.parse_args()
    args.record.parent.mkdir(parents=True, exist_ok=True)
    state = _State(args.record, args.fail_after)
    with _Server((args.host, args.port), state) as server:
        print(f"SMTP harness listening on {args.host}:{args.port}", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
