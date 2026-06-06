"""Tests for the suite-wide xdist-safety fixtures in conftest.py.

These guard the two shared-resource collisions that ``pytest -n auto`` could otherwise
race: a hard-coded TCP port, and the shared dashboard STATEFILE. ``ops.dashboard_ctl`` is
imported at module level on purpose, so the autouse statefile guard sees it loaded.
"""
import socket

import ops.dashboard_ctl as dc  # noqa: E402  (module-level so the autouse guard fires)


def test_free_port_hands_back_a_bindable_port(free_port):
    port = free_port()
    assert 1024 < port < 65536
    # The port the factory returned must actually be free to bind right now.
    s = socket.socket()
    try:
        s.bind(("127.0.0.1", port))
    finally:
        s.close()


def test_free_port_is_a_reusable_factory(free_port):
    # It returns a callable, not a single value, so a test can allocate more than one.
    assert callable(free_port)
    assert isinstance(free_port(), int)


def test_dashboard_statefile_redirected_off_the_shared_path():
    # The autouse _isolate_dashboard_statefile fixture must have moved STATEFILE away from
    # the real .ops/dashboard.json, so no test (or xdist worker) writes the shared file.
    assert dc.STATEFILE != dc.OPS_DIR / "dashboard.json"
    assert ".ops" not in dc.STATEFILE.parts
