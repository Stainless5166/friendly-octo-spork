"""Acceptance test for spork.core.systemd.template.UNIT_FILE_CONTENT (docs/DESIGN.md §14).

Guards against drift between the runtime constant `install_service()`
writes and the tracked `systemd/sporkd@.service` file a human reads on
GitHub and the Arch `PKGBUILD` installs directly — the same "single
logical source of truth, drift caught by a test" pattern
`rules.writer.dump_rules()`'s round-trip test uses. `REPO_ROOT` is
walked up from this test file's own location, stable since tests
always run from a checked-out repo, never from an installed package.
"""

from __future__ import annotations

from pathlib import Path

from spork.core.systemd.template import UNIT_FILE_CONTENT

REPO_ROOT = Path(__file__).resolve().parents[3]


def test_unit_file_content_matches_the_tracked_systemd_service_file() -> None:
    tracked = REPO_ROOT / "systemd" / "sporkd@.service"
    assert tracked.exists(), f"{tracked} does not exist"

    assert UNIT_FILE_CONTENT == tracked.read_text()


def test_unit_file_content_is_type_notify() -> None:
    """docs/DESIGN.md §14: run_daemon() signals readiness via sd_notify,
    so the unit must actually be Type=notify for that to mean anything
    to systemctl --user status."""
    assert "Type=notify" in UNIT_FILE_CONTENT


def test_unit_file_content_is_an_instance_template_with_instance_paths() -> None:
    assert "sporkd@.service" not in UNIT_FILE_CONTENT
    assert "ExecStart=%h/.local/bin/sporkd" in UNIT_FILE_CONTENT
    assert "--config %h/.config/spork/%i/config.toml" in UNIT_FILE_CONTENT
    assert "--secretspec %h/.config/spork/%i/secretspec.toml" in UNIT_FILE_CONTENT


def test_unit_file_content_restarts_on_failure() -> None:
    assert "Restart=on-failure" in UNIT_FILE_CONTENT


def test_unit_file_content_never_embeds_a_secret() -> None:
    """§14/§15: secrets are resolved by sporkd itself via SecretSpec at
    startup — no secret material should ever be passed through the
    unit file."""
    lowered = UNIT_FILE_CONTENT.lower()
    for marker in ("token", "api_key", "password", "secret="):
        assert marker not in lowered
