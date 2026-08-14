"""systemd integration: readiness signaling, unit status, install (docs/DESIGN.md §14).

`notify.py` hand-rolls the sd_notify(3) wire protocol so `run_daemon()`
can tell `systemd --user` it's actually ready, not just alive.
`unit.py` reports the installed/enabled/active state `spork doctor`
surfaces. `template.py` holds the unit file's content as a Python
constant (kept in sync with the tracked `systemd/sporkd.service` by a
test, not read from it at runtime); `install.py`'s `install_service()`
is what `spork install-service` calls to write it into place.
"""
