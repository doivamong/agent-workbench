"""Tests for ops/dashboard_ctl.py — stdlib only (no Flask). The healthcheck is
exercised against a throwaway http.server; stop() against a dummy child process."""
import os
import socket
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import ops.dashboard_ctl as dc  # noqa: E402


def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/health":
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"ok")
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, *a):  # silence
        pass


@pytest.fixture
def server():
    port = _free_port()
    httpd = HTTPServer(("127.0.0.1", port), _Handler)
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    try:
        yield port
    finally:
        httpd.shutdown()


def test_pidfile_roundtrip(tmp_path):
    pf = tmp_path / "d.pid"
    assert dc.read_pid(pf) is None
    dc.write_pid(4242, pf)
    assert dc.read_pid(pf) == 4242
    dc.clear_pid(pf)
    assert dc.read_pid(pf) is None


def test_read_pid_garbage(tmp_path):
    pf = tmp_path / "d.pid"
    pf.write_text("not-a-pid", encoding="utf-8")
    assert dc.read_pid(pf) is None


def test_pid_alive_self_and_dead():
    assert dc.pid_alive(os.getpid()) is True
    assert dc.pid_alive(None) is False
    assert dc.pid_alive(2_000_000_000) is False  # almost certainly not a live PID


def test_port_and_health(server):
    port = server
    assert dc.port_listening("127.0.0.1", port) is True
    assert dc.health_ok("127.0.0.1", port) is True
    st = dc.status("127.0.0.1", port)
    assert st["listening"] and st["healthy"]


def test_port_not_listening():
    p = _free_port()  # bound then closed → nothing listening
    assert dc.port_listening("127.0.0.1", p) is False
    assert dc.health_ok("127.0.0.1", p) is False


def test_connect_host_normalises_wildcard():
    # Wildcard bind addresses are not valid connect targets on every OS (Windows
    # rejects 0.0.0.0) — they must be dialled on the matching loopback instead.
    assert dc._connect_host("0.0.0.0") == "127.0.0.1"
    assert dc._connect_host("::") == "::1"
    assert dc._connect_host("0000:0000:0000:0000:0000:0000:0000:0000") == "::1"
    assert dc._connect_host("[::]") == "::1"
    # Concrete addresses and hostnames pass through untouched.
    assert dc._connect_host("127.0.0.1") == "127.0.0.1"
    assert dc._connect_host("192.168.1.10") == "192.168.1.10"
    assert dc._connect_host("localhost") == "localhost"


def test_health_check_dials_loopback_for_wildcard_bind(server):
    # The server listens on 127.0.0.1, but the controller is told the bind host is
    # 0.0.0.0 (as `start --host 0.0.0.0` would). The healthcheck must still succeed
    # by normalising 0.0.0.0 → 127.0.0.1 before connecting (regression: Windows
    # reported started-unverified/healthy:False for a dashboard that was serving).
    port = server
    assert dc.port_listening("0.0.0.0", port) is True
    assert dc.health_ok("0.0.0.0", port) is True
    st = dc.status("0.0.0.0", port)
    assert st["listening"] and st["healthy"]


def test_build_start_cmd():
    cmd = dc.build_start_cmd("127.0.0.1", 5151)
    assert cmd[0] == sys.executable
    assert "--port" in cmd and "5151" in cmd
    assert str(dc.APP) in cmd
    assert dc.build_start_cmd("0.0.0.0", 1, extra=["--admin"])[-1] == "--admin"


def test_stop_terminates_recorded_process(tmp_path, monkeypatch):
    monkeypatch.setattr(dc, "PIDFILE", tmp_path / "d.pid")
    monkeypatch.setattr(dc, "STATEFILE", tmp_path / "d.json")  # don't touch the real state
    proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    dc.write_pid(proc.pid)
    assert dc.pid_alive(proc.pid)
    res = dc.stop(timeout=15)
    assert res["result"] == "stopped"
    assert not dc.pid_alive(proc.pid)
    proc.wait(timeout=5)


def test_stop_not_running(tmp_path, monkeypatch):
    monkeypatch.setattr(dc, "PIDFILE", tmp_path / "none.pid")
    monkeypatch.setattr(dc, "STATEFILE", tmp_path / "none.json")
    res = dc.stop()
    assert res["result"] == "not-running"


def test_state_roundtrip(tmp_path):
    sf = tmp_path / "dashboard.json"
    assert dc.read_state(sf) is None
    dc.write_state("0.0.0.0", 5151, sf)
    assert dc.read_state(sf) == {"host": "0.0.0.0", "port": 5151}
    dc.clear_state(sf)
    assert dc.read_state(sf) is None


def test_read_state_garbage(tmp_path):
    sf = tmp_path / "dashboard.json"
    sf.write_text("{not json", encoding="utf-8")
    assert dc.read_state(sf) is None
    sf.write_text('{"host": "x"}', encoding="utf-8")  # missing port
    assert dc.read_state(sf) is None


def test_resolve_restart_target_reuses_saved_host(tmp_path, monkeypatch):
    monkeypatch.setattr(dc, "STATEFILE", tmp_path / "dashboard.json")
    # No state yet → defaults.
    assert dc.resolve_restart_target(None, None) == (dc.DEFAULT_HOST, dc.DEFAULT_PORT)
    # A LAN bind was last started → a no-arg restart reuses it (the footgun fix).
    dc.write_state("0.0.0.0", 5252, dc.STATEFILE)
    assert dc.resolve_restart_target(None, None) == ("0.0.0.0", 5252)
    # An explicit --host overrides the saved one.
    assert dc.resolve_restart_target("127.0.0.1", None) == ("127.0.0.1", 5252)


def test_status_url_is_clickable_for_wildcard_bind(server):
    # A 0.0.0.0 bind must surface a clickable loopback URL, not http://0.0.0.0:port.
    st = dc.status("0.0.0.0", server)
    assert st["bind_host"] == "0.0.0.0"
    assert st["url"] == f"http://127.0.0.1:{server}"


def test_default_host_env_override():
    # AWB_DASHBOARD_HOST lets an operator default to a LAN bind on their own machine without
    # changing the shipped default. Checked in a subprocess so the env is isolated (no reload).
    probe = (f"import sys; sys.path.insert(0, r'{ROOT}'); "
             "import ops.dashboard_ctl as d; print(d.DEFAULT_HOST)")
    on = subprocess.run([sys.executable, "-c", probe],
                        env={**os.environ, "AWB_DASHBOARD_HOST": "0.0.0.0"},
                        capture_output=True, text=True)
    assert on.stdout.strip() == "0.0.0.0"
    off = {k: v for k, v in os.environ.items() if k != "AWB_DASHBOARD_HOST"}
    default = subprocess.run([sys.executable, "-c", probe], env=off, capture_output=True, text=True)
    assert default.stdout.strip() == "127.0.0.1"  # ships localhost-only
