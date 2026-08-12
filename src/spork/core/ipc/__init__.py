"""The control-socket protocol + server/client (docs/DESIGN.md §6.2.2).

- `protocol.py` — `IpcRequest`/`IpcResponse`, newline-delimited JSON.
- `server.py` — `IpcServer`, run alongside the message loop.
- `client.py` — `send_request()`, the CLI's side.
"""
