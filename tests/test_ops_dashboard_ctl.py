"""Tests for ops/dashboard_ctl.py — stdlib only (no Flask). The healthcheck is
exercised against a throwaway http.server; stop() against a dummy child process."""
import os
import socket
import subprocess
import sys
import threading
import time
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
    assert dc.build_start_cmd("0.0.0.0", 1, extra=["--days", "7"])[-1] == "7"


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


def test_restart_reports_not_restarted_when_port_held_by_foreign_process(monkeypatch):
    # The bug behind "restart_all.bat doesn't work": stop() no-ops on a stale/dead pidfile (or
    # is denied against an elevated server), so the port stays held and start() returns
    # "already-running". The old restart() had no top-level "result" → main() exited 0 on a
    # silent no-op. It must now report "not-restarted" (a failure) with an actionable hint.
    monkeypatch.setattr(dc, "stop", lambda timeout=10.0: {"action": "stop", "result": "not-running"})
    monkeypatch.setattr(dc, "port_listening", lambda h, p, timeout=0.5: True)
    monkeypatch.setattr(dc, "start",
                        lambda *a, **k: {"action": "start", "result": "already-running", "healthy": True})
    res = dc.restart("127.0.0.1", 5151)
    assert res["result"] == "not-restarted"
    assert res.get("hint")  # the caller is told WHY (stale pidfile / elevated server), not left guessing


def test_restart_reports_restarted_on_fresh_start(monkeypatch):
    # The happy path: stop succeeds, the port frees, start launches a fresh process → "restarted".
    monkeypatch.setattr(dc, "stop", lambda timeout=10.0: {"action": "stop", "result": "stopped", "pid": 1})
    monkeypatch.setattr(dc, "port_listening", lambda h, p, timeout=0.5: False)
    monkeypatch.setattr(dc, "start",
                        lambda *a, **k: {"action": "start", "result": "started", "healthy": True, "pid": 2})
    res = dc.restart("127.0.0.1", 5151)
    assert res["result"] == "restarted"
    assert "hint" not in res


def test_restart_propagates_started_unverified(monkeypatch):
    monkeypatch.setattr(dc, "stop", lambda timeout=10.0: {"action": "stop", "result": "stopped", "pid": 1})
    monkeypatch.setattr(dc, "port_listening", lambda h, p, timeout=0.5: False)
    monkeypatch.setattr(dc, "start",
                        lambda *a, **k: {"action": "start", "result": "started-unverified", "healthy": False})
    assert dc.restart("127.0.0.1", 5151)["result"] == "started-unverified"


def test_terminate_surfaces_access_denied_reason(monkeypatch):
    # A taskkill denied because the target runs elevated must come back as an actionable reason,
    # not be swallowed (the root cause of restart_all.bat silently failing on an elevated server).
    monkeypatch.setattr(dc.sys, "platform", "win32")

    class _CP:  # a fake taskkill that was denied
        returncode = 1
        stdout = ""
        stderr = ("ERROR: The process with PID 1 (child process of PID 2) could not be "
                  "terminated.\nReason: Access is denied.")

    monkeypatch.setattr(dc.subprocess, "run", lambda *a, **k: _CP())
    monkeypatch.setattr(dc, "pid_alive", lambda pid: True)  # elevated → never dies for us
    gone, reason = dc._terminate(1234, timeout=0.3)
    assert gone is False
    assert reason and "administrator" in reason.lower()


def test_stop_threads_terminate_hint(tmp_path, monkeypatch):
    monkeypatch.setattr(dc, "PIDFILE", tmp_path / "d.pid")
    monkeypatch.setattr(dc, "STATEFILE", tmp_path / "d.json")
    dc.write_pid(999_999)
    monkeypatch.setattr(dc, "pid_alive", lambda pid: True)  # appears alive
    monkeypatch.setattr(dc, "_terminate", lambda pid, timeout=10.0: (False, "run as Administrator"))
    res = dc.stop()
    assert res["result"] == "stop-failed"
    assert res["hint"] == "run as Administrator"


# --- __pycache__ clearing on restart (fresh-code guarantee) -------------------------------

def test_clear_pycache_removes_source_caches_and_skips_deps(tmp_path):
    # Project source caches are wiped; dependency / VCS / runtime trees (dotdirs, venv,
    # node_modules) are pruned so we never delete a dependency's own cache.
    (tmp_path / "pkg" / "__pycache__").mkdir(parents=True)
    (tmp_path / "pkg" / "__pycache__" / "m.cpython-310.pyc").write_bytes(b"x")
    (tmp_path / "ui" / "web" / "__pycache__").mkdir(parents=True)
    (tmp_path / ".venv" / "lib" / "__pycache__").mkdir(parents=True)   # must be skipped (dotdir)
    (tmp_path / "node_modules" / "__pycache__").mkdir(parents=True)    # must be skipped (deps)
    removed = dc.clear_pycache(tmp_path)
    assert removed == 2
    assert not (tmp_path / "pkg" / "__pycache__").exists()
    assert not (tmp_path / "ui" / "web" / "__pycache__").exists()
    assert (tmp_path / ".venv" / "lib" / "__pycache__").exists()
    assert (tmp_path / "node_modules" / "__pycache__").exists()


def test_clear_pycache_tolerates_locked_dir(tmp_path, monkeypatch):
    # A cache dir still locked by a live process must be skipped, never fail the restart.
    (tmp_path / "a" / "__pycache__").mkdir(parents=True)
    monkeypatch.setattr(dc.shutil, "rmtree",
                        lambda *a, **k: (_ for _ in ()).throw(PermissionError("locked")))
    assert dc.clear_pycache(tmp_path) == 0  # swallowed, returns a count, doesn't raise


def test_restart_clears_pycache_by_default_and_opt_out(monkeypatch):
    seen: dict = {}
    monkeypatch.setattr(dc, "stop", lambda timeout=10.0: {"action": "stop", "result": "stopped", "pid": 1})
    monkeypatch.setattr(dc, "port_listening", lambda h, p, timeout=0.5: False)
    monkeypatch.setattr(dc, "clear_pycache", lambda root=dc.REPO_ROOT: seen.setdefault("n", 7))
    monkeypatch.setattr(dc, "start",
                        lambda *a, **k: {"action": "start", "result": "started", "healthy": True, "pid": 2})
    res = dc.restart("127.0.0.1", 5151)
    assert res["pycache_cleared"] == 7 and seen.get("n") == 7  # cleared by default
    seen.clear()
    res2 = dc.restart("127.0.0.1", 5151, clear_cache=False)
    assert res2["pycache_cleared"] == 0 and "n" not in seen   # opt-out skips the wipe entirely


# --- --force kill-by-port (opt-in escape hatch) ---------------------------------------------

def test_force_free_port_kills_foreign_listener(tmp_path):
    # End-to-end: a foreign process holds a port; force_free_port enumerates and kills it.
    # Skips when the OS lacks netstat/lsof to enumerate owners (best-effort by design).
    port = _free_port()
    code = ("import socket,time;s=socket.socket();"
            "s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1);"
            f"s.bind(('127.0.0.1',{port}));s.listen(5);time.sleep(30)")
    proc = subprocess.Popen([sys.executable, "-c", code])
    try:
        for _ in range(50):
            if dc.port_listening("127.0.0.1", port):
                break
            time.sleep(0.1)
        assert dc.port_listening("127.0.0.1", port), "the foreign listener never came up"
        if proc.pid not in dc._pids_on_port(port):
            pytest.skip("no netstat/lsof to enumerate port owners on this host")
        res = dc.force_free_port("127.0.0.1", port, timeout=10)
        assert proc.pid in res["killed"]
        assert res["freed"] is True
        proc.wait(timeout=5)
    finally:
        if proc.poll() is None:
            proc.kill()


def test_restart_force_invokes_force_free_port(monkeypatch):
    # When the port is held and --force is set, restart escalates via force_free_port.
    called: dict = {}
    monkeypatch.setattr(dc, "stop", lambda timeout=10.0: {"action": "stop", "result": "not-running"})
    monkeypatch.setattr(dc, "port_listening", lambda h, p, timeout=0.5: True)
    monkeypatch.setattr(dc, "clear_pycache", lambda root=dc.REPO_ROOT: 0)
    monkeypatch.setattr(dc, "force_free_port",
                        lambda h, p, t=10.0: called.setdefault("f", {"freed": True, "killed": [123], "failed": []}))
    monkeypatch.setattr(dc, "start",
                        lambda *a, **k: {"action": "start", "result": "started", "healthy": True, "pid": 9})
    res = dc.restart("127.0.0.1", 5151, force=True)
    assert "f" in called                    # force path was taken
    assert res["force"]["killed"] == [123]
    assert res["result"] == "restarted"


def test_restart_without_force_does_not_touch_port(monkeypatch):
    # The default must NOT hunt-and-kill by port — force_free_port is never called.
    monkeypatch.setattr(dc, "stop", lambda timeout=10.0: {"action": "stop", "result": "not-running"})
    monkeypatch.setattr(dc, "port_listening", lambda h, p, timeout=0.5: True)
    monkeypatch.setattr(dc, "clear_pycache", lambda root=dc.REPO_ROOT: 0)
    boom = lambda *a, **k: pytest.fail("force_free_port must not run without --force")
    monkeypatch.setattr(dc, "force_free_port", boom)
    monkeypatch.setattr(dc, "start",
                        lambda *a, **k: {"action": "start", "result": "already-running", "healthy": True})
    res = dc.restart("127.0.0.1", 5151)  # force defaults False
    assert res["result"] == "not-restarted"
    assert "force" not in res


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


def test_start_refuses_public_bind_without_spawning():
    """opt-2: start() refuses a public/Internet-routable host BEFORE spawning a server, so the
    operator gets a clean reason instead of a process exposing cleartext HTTP."""
    res = dc.start("8.8.8.8", _free_port(), wait=False)
    assert res["result"] == "refused-public-bind"
    assert "pid" not in res                      # nothing was launched
    assert "cleartext" in res["reason"].lower()


def test_restart_refuses_public_bind_without_touching_server():
    """opt-2: restart() must refuse a public host BEFORE stop() — otherwise it tears the live
    server down for a doomed restart — and the top-level result must say 'refused', never fall
    through to 'restarted' (a guard that fired reporting success is the kit's worst failure)."""
    res = dc.restart("8.8.8.8", _free_port())
    assert res["result"] == "refused-public-bind"
    assert res["action"] == "restart"
    assert "stop" not in res                          # the running server was not touched
    assert "cleartext" in res["reason"].lower()


def test_start_allows_lan_and_loopback_hosts(monkeypatch):
    """The sanctioned modes must pass the public-bind pre-flight. We stub port_listening to True
    so start() short-circuits to 'already-running' WITHOUT spawning a real server — the point is
    only that the guard did not refuse these hosts."""
    monkeypatch.setattr(dc, "port_listening", lambda host, port: True)
    monkeypatch.setattr(dc, "health_ok", lambda host, port: True)
    for ok in ("127.0.0.1", "0.0.0.0", "192.168.1.50"):
        res = dc.start(ok, 5151, wait=False)
        assert res["result"] == "already-running", ok   # passed the guard, no spawn
