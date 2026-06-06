#!/usr/bin/env python3
"""dashboard_ctl.py — start / stop / restart / status for the ui/web dashboard.

A small, cross-platform process controller for the kit's opt-in Flask dashboard
(``ui/web/app.py``, default port 5151). It manages the dashboard as a *detached*
background process recorded in a pidfile, and reports liveness three ways — the
recorded PID, whether something is listening on the port, and an HTTP healthcheck.

    python ops/dashboard_ctl.py status            # is it up + healthy?
    python ops/dashboard_ctl.py start              # launch detached, wait until healthy
    python ops/dashboard_ctl.py stop               # stop the process we started
    python ops/dashboard_ctl.py restart            # stop + start
    python ops/dashboard_ctl.py start --port 5252  # a different port

Stdlib only (the *controller* needs no dependency — the dashboard it launches needs
Flask, the kit's opt-in dep). Runtime files live under the git-ignored ``.ops/``:
``.ops/dashboard.pid`` and ``.ops/dashboard.log``.

What this does NOT do (by default): it only stops/restarts the process recorded in ITS OWN
pidfile — if you started the dashboard another way (a bare ``python ui/web/app.py``), this
cannot find it, and ``stop`` is a no-op (it will say so). It does not scan the system to kill
an arbitrary process on the port, because that is too blunt to be safe by default. The opt-in
``--force`` flag IS that escape hatch: it kills whatever holds the port (related or not) so a
stale/foreign process can't block a restart — use it only when you know nothing else needs that
port. ``restart`` also clears ``__pycache__`` first so it can never serve a stale ``.pyc`` (pass
``--no-clear-cache`` to skip). It is localhost/single-developer tooling, not a service manager.
"""
from __future__ import annotations

import argparse
import ipaddress
import json
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

if sys.stdout is not None and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    except Exception:
        pass

REPO_ROOT = Path(__file__).resolve().parents[1]
APP = REPO_ROOT / "ui" / "web" / "app.py"
OPS_DIR = REPO_ROOT / ".ops"

# Single source of the bind-host policy (loopback/LAN/0.0.0.0 allowed, public IP refused). It is
# stdlib-only, so importing it here couples ops/ to nothing heavy — this controller already knows
# about ui/web (it spawns APP). Keeping ONE classifier avoids drift in a security check.
sys.path.insert(0, str(REPO_ROOT / "ui"))
import bind_policy  # noqa: E402
PIDFILE = OPS_DIR / "dashboard.pid"
LOGFILE = OPS_DIR / "dashboard.log"
STATEFILE = OPS_DIR / "dashboard.json"  # records the last-started host:port (see write_state)

# Default bind host. Ships as localhost-only (safe for every adopter); set the env var
# AWB_DASHBOARD_HOST=0.0.0.0 on your own machine to default to a LAN bind (e.g. to reach the
# read-only dashboard from a phone on the same subnet). The firewall is the real control — see
# ui/web/README.md. Over a LAN bind the /admin action surface stays inert until an admin
# password is set (login is the gate); without a password no action is reachable on any host.
HOST_ENV_VAR = "AWB_DASHBOARD_HOST"


def env_default_host() -> str:
    """The default bind host, resolved from the environment AT CALL TIME (not frozen at import).
    Reading it lazily keeps ``resolve_restart_target``/``status`` deterministic w.r.t. the current
    process env: a test that clears the var (or a shell that unsets it) sees localhost, even though
    the machine had ``AWB_DASHBOARD_HOST=0.0.0.0`` set when this module was first imported."""
    return os.environ.get(HOST_ENV_VAR) or "127.0.0.1"


# Import-time snapshot, used only for function default-arg values and CLI help text. The live
# resolution path (resolve_restart_target) calls env_default_host() so it is never frozen.
DEFAULT_HOST = env_default_host()
DEFAULT_PORT = 5151


def _ops_dir() -> Path:
    OPS_DIR.mkdir(parents=True, exist_ok=True)
    return OPS_DIR


def clear_pycache(root: Path = REPO_ROOT) -> int:
    """Remove every ``__pycache__`` directory under ``root`` so a restart cannot serve a stale
    ``.pyc`` (the cause of a zombie dashboard answering with old code after the source changed).
    Returns the count removed. Best-effort: a directory still locked by a live process is skipped,
    never fatal — call it AFTER the old process is stopped so its ``.pyc`` locks are released.

    VCS / virtualenv / dependency / runtime trees are pruned (both for speed and so a dependency's
    own cache is never touched); only the project's own source caches are cleared."""
    removed = 0
    for dirpath, dirnames, _files in os.walk(root):
        # Prune dirs we never want to descend into: dotdirs (.git, .venv, .ops, .pytest_cache…)
        # and vendored deps. __pycache__ has no leading dot, so it survives this filter and is
        # handled below. Source trees (ui/, tools/, ops/, …) are kept.
        dirnames[:] = [d for d in dirnames
                       if not d.startswith(".") and d not in {"venv", "node_modules"}]
        if "__pycache__" in dirnames:
            try:
                shutil.rmtree(Path(dirpath) / "__pycache__")
                removed += 1
            except OSError:
                pass  # locked / permission — a cache dir is never worth failing the restart over
            dirnames.remove("__pycache__")  # don't descend into the dir we just removed
    return removed


# --------------------------------------------------------------------------- #
# Pidfile
# --------------------------------------------------------------------------- #
def read_pid(pidfile: Path | None = None) -> int | None:
    """The recorded PID, or None if the file is missing/empty/garbage (fail soft —
    a corrupt pidfile means 'we don't know of a process', not a crash). Resolves the
    default at call time so tests can repoint the module PIDFILE."""
    pidfile = pidfile or PIDFILE
    try:
        return int(pidfile.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return None


def write_pid(pid: int, pidfile: Path | None = None) -> None:
    pidfile = pidfile or PIDFILE
    pidfile.parent.mkdir(parents=True, exist_ok=True)
    pidfile.write_text(str(pid), encoding="utf-8")


def clear_pid(pidfile: Path | None = None) -> None:
    pidfile = pidfile or PIDFILE
    try:
        pidfile.unlink()
    except FileNotFoundError:
        pass


# --------------------------------------------------------------------------- #
# Start-state (host:port the dashboard was last launched on)
# --------------------------------------------------------------------------- #
def write_state(host: str, port: int, statefile: Path | None = None) -> None:
    """Record the host:port the dashboard was last started on, so ``restart`` can reuse
    it — a LAN bind (``--host 0.0.0.0``) then survives a no-arg ``restart`` (e.g. a
    double-click of restart_all) instead of silently reverting to localhost."""
    statefile = statefile or STATEFILE
    statefile.parent.mkdir(parents=True, exist_ok=True)
    statefile.write_text(json.dumps({"host": host, "port": port}), encoding="utf-8")


def read_state(statefile: Path | None = None) -> dict | None:
    """The recorded ``{host, port}``, or None if absent/garbage (fail soft)."""
    statefile = statefile or STATEFILE
    try:
        data = json.loads(statefile.read_text(encoding="utf-8"))
        if isinstance(data, dict) and "host" in data and "port" in data:
            return {"host": str(data["host"]), "port": int(data["port"])}
    except (OSError, ValueError, TypeError):
        pass
    return None


def clear_state(statefile: Path | None = None) -> None:
    statefile = statefile or STATEFILE
    try:
        statefile.unlink()
    except FileNotFoundError:
        pass


def resolve_restart_target(host: str | None, port: int | None) -> tuple[str, int]:
    """Resolve the host:port a ``restart``/``status`` should use: an explicit value wins;
    otherwise reuse what the dashboard was last started on (so a LAN bind survives a
    no-arg restart); otherwise the defaults. This is the fix for 'restart silently
    reverts a LAN bind to localhost'."""
    saved = read_state() or {}
    return (host if host is not None else saved.get("host", env_default_host()),
            port if port is not None else saved.get("port", DEFAULT_PORT))


def _url(host: str, port: int) -> str:
    """A clickable URL: a wildcard bind (``0.0.0.0``/``::``) is shown on loopback, and an
    IPv6 literal is bracketed — so the URL connects on Windows (see ``_connect_host``)."""
    dial = _connect_host(host)
    netloc = f"[{dial}]" if ":" in dial else dial
    return f"http://{netloc}:{port}"


# --------------------------------------------------------------------------- #
# Liveness — three independent signals
# --------------------------------------------------------------------------- #
def _connect_host(host: str) -> str:
    """Map a wildcard *bind* address to a routable *connect* address.

    Binding to ``0.0.0.0`` (or IPv6 ``::``) means "all interfaces", but those
    unspecified addresses are not valid *connect* destinations on every OS:
    Linux silently treats ``0.0.0.0`` as localhost, but Windows rejects the
    connection, so a healthcheck that dials the bind host false-reports the
    dashboard as down (see memory: dashboard-ctl-0000-healthcheck-false-negative).
    Dial the matching loopback (``127.0.0.1`` / ``::1``) instead. A concrete
    address or a hostname is returned unchanged."""
    try:
        addr = ipaddress.ip_address(host.strip().strip("[]"))
    except ValueError:
        return host  # hostname or non-literal — dial as given
    if addr.is_unspecified:
        return "::1" if addr.version == 6 else "127.0.0.1"
    return host


def pid_alive(pid: int | None) -> bool:
    """True if a process with this PID currently exists. Cross-platform: ctypes
    OpenProcess on Windows, signal-0 probe on POSIX. None → False."""
    if not pid or pid <= 0:
        return False
    if sys.platform == "win32":
        import ctypes
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        STILL_ACTIVE = 259
        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not handle:
            return False
        try:
            code = ctypes.c_ulong()
            if not kernel32.GetExitCodeProcess(handle, ctypes.byref(code)):
                return False
            return code.value == STILL_ACTIVE
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True  # exists, owned by someone else
    return True


def port_listening(host: str, port: int, timeout: float = 0.5) -> bool:
    """True if a TCP connection to host:port succeeds (something is accepting).
    A wildcard bind host (``0.0.0.0``/``::``) is dialled on loopback — see
    ``_connect_host``."""
    try:
        with socket.create_connection((_connect_host(host), port), timeout=timeout):
            return True
    except OSError:
        return False


def health_ok(host: str, port: int, timeout: float = 1.0) -> bool:
    """True if the dashboard answers a 2xx. Tries /health first (cheap, added for
    exactly this), falls back to / so it still works against an older dashboard.
    A wildcard bind host (``0.0.0.0``/``::``) is dialled on loopback — see
    ``_connect_host``."""
    dial = _connect_host(host)
    netloc = f"[{dial}]" if ":" in dial else dial  # bracket IPv6 literals for the URL
    for path in ("/health", "/"):
        try:
            req = urllib.request.Request(f"http://{netloc}:{port}{path}", method="GET")
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                if 200 <= resp.status < 300:
                    return True
        except urllib.error.HTTPError as e:
            if path == "/health" and e.code == 404:
                continue  # old dashboard with no /health — try /
        except (urllib.error.URLError, OSError):
            return False
    return False


def status(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> dict:
    """Compose the three signals into one honest picture."""
    pid = read_pid()
    listening = port_listening(host, port)
    return {
        "pid": pid,
        "pid_alive": pid_alive(pid),
        "listening": listening,
        "healthy": health_ok(host, port) if listening else False,
        "bind_host": host,
        "url": _url(host, port),  # clickable: a 0.0.0.0 bind is shown on loopback
    }


# --------------------------------------------------------------------------- #
# Lifecycle
# --------------------------------------------------------------------------- #
def build_start_cmd(host: str, port: int, app: Path = APP,
                    extra: list[str] | None = None) -> list[str]:
    """The exact argv used to launch the dashboard — pure, so it can be unit-tested
    and reused by the web self-restart path (which must carry the same flags)."""
    cmd = [sys.executable, str(app), "--host", host, "--port", str(port)]
    if extra:
        cmd += extra
    return cmd


def _spawn_detached(cmd: list[str], log: Path) -> int:
    """Launch cmd as a detached background process writing to ``log``; return its PID.
    Detached so it outlives this controller invocation (Windows: no console + new
    group; POSIX: new session)."""
    _ops_dir()
    logf = open(log, "ab")  # noqa: SIM115 — handed to the child; closed when it exits
    kwargs: dict = {"stdout": logf, "stderr": logf, "stdin": subprocess.DEVNULL,
                    "cwd": str(REPO_ROOT)}
    if sys.platform == "win32":
        DETACHED_PROCESS = 0x00000008
        CREATE_NEW_PROCESS_GROUP = 0x00000200
        kwargs["creationflags"] = DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True
    proc = subprocess.Popen(cmd, **kwargs)
    return proc.pid


def wait_healthy(host: str, port: int, timeout: float = 20.0,
                 interval: float = 0.4) -> bool:
    """Poll until the dashboard answers healthy or the deadline passes."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if health_ok(host, port):
            return True
        time.sleep(interval)
    return False


def start(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT, *, app: Path = APP,
          extra: list[str] | None = None, wait: bool = True,
          timeout: float = 20.0) -> dict:
    """Launch the dashboard if it isn't already up. Idempotent: if something is
    already listening, report it rather than starting a second one.

    Refuses a public/Internet-routable bind host BEFORE spawning, so the operator gets a clean
    reason instead of a server that comes up exposing cleartext HTTP. Loopback / LAN / 0.0.0.0
    are allowed; see ui/bind_policy.py. (app.create_app re-checks as defence in depth.)"""
    if bind_policy.is_public_bind_host(host):
        return {"action": "start", "result": "refused-public-bind",
                "bind_host": host, "reason": bind_policy.public_bind_refusal(host)}
    if port_listening(host, port):
        return {"action": "start", "result": "already-running",
                "healthy": health_ok(host, port), "url": _url(host, port)}
    pid = _spawn_detached(build_start_cmd(host, port, app, extra), LOGFILE)
    write_pid(pid)
    write_state(host, port)  # so a no-arg restart reuses this host:port (LAN bind survives)
    healthy = wait_healthy(host, port, timeout) if wait else False
    return {"action": "start", "result": "started" if healthy else "started-unverified",
            "pid": pid, "healthy": healthy, "bind_host": host, "log": str(LOGFILE),
            "url": _url(host, port)}


def _reap(pid: int) -> None:
    """Reap a terminated child (POSIX) so it doesn't linger as a zombie that
    ``os.kill(pid, 0)`` still reports as alive. No-op on Windows, and a no-op when
    ``pid`` isn't our child (the real detached dashboard, reparented to init — killing
    it is reaped by init, so there is nothing here to reap)."""
    if sys.platform == "win32":
        return
    try:
        os.waitpid(pid, os.WNOHANG)
    except (ChildProcessError, OSError):
        pass  # not our child, or already reaped


def _terminate(pid: int, timeout: float = 10.0) -> tuple[bool, str | None]:
    """Stop a process by PID, cross-platform. Returns ``(gone, reason)`` — ``gone`` is True
    if the process is no longer alive afterwards; ``reason`` is an actionable diagnostic when
    it could NOT be killed (else None). The reason matters: a taskkill that is denied because
    the target runs at a higher integrity level (a dashboard launched from an elevated shell)
    is otherwise swallowed, leaving the caller with a bare 'stop-failed' and no clue why a
    plain double-click of restart_all.bat can't restart it."""
    reason: str | None = None
    if sys.platform == "win32":
        proc = subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"],
                              capture_output=True, text=True)
        if proc.returncode != 0:
            err = (proc.stderr or proc.stdout or "").strip()
            if "access is denied" in err.lower():
                reason = ("taskkill was denied (Access is denied): the process runs at a higher "
                          "integrity level — it was launched elevated. Run restart_all.bat / "
                          "dashboard_ctl as Administrator to restart it.")
            elif err:
                reason = f"taskkill failed: {err}"
    else:
        import signal
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            return True, None
        except PermissionError as exc:
            reason = f"SIGTERM denied (process owned by another user?): {exc}"
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            _reap(pid)
            if not pid_alive(pid):
                return True, None
            time.sleep(0.2)
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            return True, None
        except PermissionError as exc:
            reason = f"SIGKILL denied (process owned by another user?): {exc}"
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        _reap(pid)
        if not pid_alive(pid):
            return True, None
        time.sleep(0.2)
    gone = not pid_alive(pid)
    return gone, (None if gone else reason)


def _pids_on_port(port: int) -> set[int]:
    """Best-effort: the PIDs with a LISTENING socket on ``port``, via the OS's own tooling so
    no third-party dependency (psutil) is needed. Windows parses ``netstat -ano``; POSIX uses
    ``lsof``. Returns an empty set if the tool is absent or its output can't be parsed — the
    ``--force`` path then simply finds nothing to kill rather than crashing."""
    pids: set[int] = set()
    try:
        if sys.platform == "win32":
            out = subprocess.run(["netstat", "-ano"], capture_output=True, text=True).stdout
            for line in out.splitlines():
                parts = line.split()
                # Columns: Proto  Local  Foreign  State  PID
                if len(parts) >= 5 and parts[0].upper() == "TCP" and parts[3].upper() == "LISTENING":
                    if parts[1].rsplit(":", 1)[-1] == str(port):  # local-address port matches
                        try:
                            pids.add(int(parts[-1]))
                        except ValueError:
                            pass
        else:
            out = subprocess.run(["lsof", "-nP", f"-iTCP:{port}", "-sTCP:LISTEN", "-t"],
                                 capture_output=True, text=True).stdout
            for tok in out.split():
                try:
                    pids.add(int(tok))
                except ValueError:
                    pass
    except (OSError, subprocess.SubprocessError):
        pass  # tooling missing — best-effort, the caller treats an empty set as "found nothing"
    pids.discard(0)
    return pids


def force_free_port(host: str, port: int, timeout: float = 10.0) -> dict:
    """Kill EVERY process with a listening socket on ``port`` — the opt-in ``--force`` escape
    hatch for a port the pidfile path can't clear (a stale pidfile, or a server started outside
    this controller). Blunt by design: it kills whatever holds the port, related or not, which
    is exactly why it is never the default. Returns the per-PID outcome and whether the port is
    free afterwards (it waits briefly for the socket to be released so a follow-on start sees it
    free)."""
    killed: list[int] = []
    failed: list[dict] = []
    for pid in sorted(_pids_on_port(port)):
        gone, reason = _terminate(pid, timeout)
        if gone:
            killed.append(pid)
        else:
            failed.append({"pid": pid, "hint": reason})
    deadline = time.monotonic() + 3.0  # let the OS release the socket before we report/Start
    while port_listening(host, port) and time.monotonic() < deadline:
        time.sleep(0.2)
    return {"action": "force-free-port", "port": port, "killed": killed,
            "failed": failed, "freed": not port_listening(host, port)}


def stop(timeout: float = 10.0) -> dict:
    """Stop the process recorded in our pidfile. A no-op (honestly reported) if we
    have no live PID on record — we never hunt-and-kill by port (use ``--force`` for that)."""
    pid = read_pid()
    if not pid_alive(pid):
        clear_pid()
        clear_state()
        return {"action": "stop", "result": "not-running"}
    gone, reason = _terminate(pid, timeout)  # type: ignore[arg-type]
    if gone:
        clear_pid()
        clear_state()
    res = {"action": "stop", "result": "stopped" if gone else "stop-failed", "pid": pid}
    if not gone and reason:
        res["hint"] = reason  # why it couldn't be stopped (e.g. needs elevation) — never swallow it
    return res


def restart(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT, *, app: Path = APP,
            extra: list[str] | None = None, timeout: float = 20.0,
            force: bool = False, clear_cache: bool = True) -> dict:
    """Stop the recorded process (if any) and start a fresh one.

    ``clear_cache`` (default on) wipes ``__pycache__`` between stop and start so the fresh
    process can't import a stale ``.pyc``. ``force`` (opt-in) escalates when the port is still
    held by something the pidfile path couldn't stop: it kills whatever holds the port (see
    ``force_free_port``) instead of giving up with 'not-restarted'."""
    # Refuse a public bind BEFORE stopping the running server — otherwise we'd tear the live
    # dashboard down for a restart that start() will then refuse, AND the top-level result must
    # say 'refused' (not fall through to 'restarted'): a guard that fired must never report success.
    if bind_policy.is_public_bind_host(host):
        return {"action": "restart", "result": "refused-public-bind",
                "bind_host": host, "reason": bind_policy.public_bind_refusal(host)}
    stop_res = stop()
    # If the port is still held (e.g. started outside our pidfile), don't pile a second
    # process on top — report so the caller can act (see memory: restart-didnt-work).
    force_res: dict | None = None
    if port_listening(host, port):
        if force:
            force_res = force_free_port(host, port, timeout)
        time.sleep(0.5)
    # Clear the bytecode cache now that the old process is gone (its .pyc locks are released),
    # before the fresh one imports anything — guarantees it runs the current source.
    pycache_cleared = clear_pycache() if clear_cache else 0
    start_res = start(host, port, app=app, extra=extra, wait=True, timeout=timeout)
    # Derive an HONEST top-level result. A restart only *succeeds* when we launched a fresh
    # process. If start() found the port already held, we did NOT restart — something we
    # couldn't stop still serves: a stale pidfile pointing at a dead PID, or (the usual cause
    # on Windows) a dashboard launched ELEVATED that a non-elevated taskkill can't reach. That
    # used to exit 0 on a silent no-op; surface it so restart_all.bat reports the failure.
    sres = start_res.get("result")
    if sres == "already-running":
        hint = stop_res.get("hint") or (
            "the port is still held by a process this controller did not start — likely a "
            "stale pidfile or a dashboard launched elevated. Stop that process, or re-run with "
            "--force (and as Administrator if it is elevated); the running server was NOT replaced.")
        out = {"action": "restart", "result": "not-restarted", "stop": stop_res,
               "start": start_res, "hint": hint}
    elif sres == "started-unverified":
        out = {"action": "restart", "result": "started-unverified", "stop": stop_res, "start": start_res}
    else:
        out = {"action": "restart", "result": "restarted", "stop": stop_res, "start": start_res}
    out["pycache_cleared"] = pycache_cleared
    if force_res is not None:
        out["force"] = force_res
    return out


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Start/stop/restart/status the ui/web dashboard.")
    ap.add_argument("command", choices=["status", "start", "stop", "restart"])
    ap.add_argument("--host", default=None,
                    help=f"bind host (default: {DEFAULT_HOST}; restart/status reuse the "
                         "last-started host unless you pass this)")
    ap.add_argument("--port", type=int, default=None, help=f"port (default: {DEFAULT_PORT})")
    ap.add_argument("--timeout", type=float, default=20.0, help="seconds to wait for healthy on start")
    ap.add_argument("--force", action="store_true",
                    help="stop/restart: kill ANY process holding the port, not just our pidfile's "
                         "— blunt; use when a stale or foreign process blocks the restart")
    ap.add_argument("--no-clear-cache", action="store_true",
                    help="restart: skip the default __pycache__ wipe (kept only if you have a reason)")
    ap.add_argument("--json", action="store_true", help="emit the result as JSON")
    args = ap.parse_args(argv)

    if args.command == "start":
        # An explicit launch defaults to SAFE localhost — never auto-expose on a bare start.
        result = start(args.host or DEFAULT_HOST, args.port or DEFAULT_PORT, timeout=args.timeout)
    elif args.command == "status":
        host, port = resolve_restart_target(args.host, args.port)
        result = status(host, port)
    elif args.command == "stop":
        result = stop()
        if args.force:  # also clear any process still holding the port (not just our pidfile's)
            host, port = resolve_restart_target(args.host, args.port)
            force_res = force_free_port(host, port)
            result = {"action": "stop", "result": "stopped" if force_res["freed"] else "stop-failed",
                      "pidfile_stop": result, "force": force_res}
    else:  # restart — reuse the last-started host:port (so a LAN bind survives) unless overridden
        host, port = resolve_restart_target(args.host, args.port)
        result = restart(host, port, timeout=args.timeout,
                         force=args.force, clear_cache=not args.no_clear_cache)

    if args.json:
        print(json.dumps(result, ensure_ascii=False))
    else:
        for k, v in result.items():
            print(f"  {k}: {v}")
    # Exit non-zero when the outcome is a failure the caller should notice.
    failed = result.get("result") in {"stop-failed", "started-unverified", "not-restarted",
                                      "refused-public-bind"} or (
        args.command == "status" and not result.get("healthy"))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
