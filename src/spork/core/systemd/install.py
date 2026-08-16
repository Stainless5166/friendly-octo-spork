"""install_service(): the `spork install-service` mechanism (docs/DESIGN.md §14).

Writes the tracked unit file's content into place, then runs
`systemctl --user daemon-reload` and (unless told not to)
`enable --now` — the same three manual steps §14's install flow
documents, done for the user in one command.
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from pathlib import Path

from spork.core.config.paths import resolve_user_unit_path
from spork.core.systemd.template import UNIT_FILE_CONTENT

_Runner = Callable[..., "subprocess.CompletedProcess[str]"]


class InstallServiceError(Exception):
    """Raised when the unit file can't be written, or `systemctl` fails.

    Wraps a missing `systemctl` binary, an unreachable user session bus
    (a real, confirmed-in-sandbox failure mode, not hypothetical), a
    `daemon-reload`/`enable --now` failure, or an `OSError` writing the
    unit file itself — one catchable type per module boundary, the
    same convention as `RulesLoadError`/`ProviderLoadError`.
    """


def install_service(
    unit_name: str = "sporkd@",
    *,
    instance: str = "default",
    unit_path: Path | None = None,
    enable_now: bool = True,
    runner: _Runner = subprocess.run,
) -> Path:
    """Write the unit file, reload systemd, and (by default) enable+start it.

    `unit_path` defaults to `resolve_user_unit_path(unit_name)`;
    parent directories are created as needed (`~/.config/systemd/user/`
    doesn't exist on a fresh machine). `runner` is injected the same
    DI-for-subprocess pattern `check_unit_status()` uses, so tests never
    invoke a real `systemctl`. Returns the path written, for the
    caller (`spork install-service`) to report back.
    """
    path = unit_path if unit_path is not None else resolve_user_unit_path(unit_name)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(UNIT_FILE_CONTENT)
    except OSError as exc:
        raise InstallServiceError(f"could not write unit file to {path}: {exc}") from exc

    try:
        runner(
            ["systemctl", "--user", "daemon-reload"],
            check=True,
            capture_output=True,
            text=True,
        )
        if enable_now:
            runner(
                ["systemctl", "--user", "enable", "--now", f"{unit_name}{instance}"],
                check=True,
                capture_output=True,
                text=True,
            )
    except FileNotFoundError as exc:
        raise InstallServiceError("systemctl not found — is systemd installed?") from exc
    except subprocess.CalledProcessError as exc:
        detail = exc.stderr.strip() if exc.stderr else str(exc)
        raise InstallServiceError(f"systemctl failed: {detail}") from exc

    return path
