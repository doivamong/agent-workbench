#!/usr/bin/env python3
"""lan_setup.py — one-step setup to reach the read-only dashboard from another device.

Makes the dashboard default to a LAN bind (``0.0.0.0``) — then a bare ``python ui/web/app.py``
or a no-arg ``restart_all`` binds the LAN with no extra flag, e.g. to view it from a phone on
the same Wi-Fi. It sets things on two levels so it works immediately AND permanently:

  * the ``AWB_DASHBOARD_HOST`` env var (the *default*, for new shells / a fresh ``start``), and
  * the persisted ``.ops/dashboard.json`` start-state that ``restart`` reuses (so the very next
    restart binds the LAN even before the env var has propagated to a logged-in shell).

    python ops/lan_setup.py status      # current default, what restart will bind, LAN URL(s)
    python ops/lan_setup.py enable       # default to a LAN bind (env + start-state)
    python ops/lan_setup.py disable      # back to localhost-only
    python ops/lan_setup.py firewall      # create the inbound rule (Windows; needs admin)
    python ops/lan_setup.py enable --dry-run   # show what it would do, change nothing

Stdlib only. The shipped default stays ``127.0.0.1``; only your machine, configured here, defaults
to a LAN bind. A ``0.0.0.0`` bind is allowed (the read-only dashboard on your LAN); a public /
Internet-routable bind is REFUSED at the chokepoint (see ``ui/bind_policy.py``). ``/admin`` is NOT
refused on a LAN bind — once you set an admin password it is reachable over the LAN, and because
this is plain HTTP that password travels in cleartext. The firewall (scoped to your LOCAL SUBNET)
is the real access control; for access from a domain, front it with a reverse proxy / Cloudflare
Tunnel rather than widening the bind.
"""
from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
from pathlib import Path

if sys.stdout is not None and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    except Exception:
        pass

# The engine that owns the pidfile/start-state. Import via the repo root so it is the SAME
# module object whether this runs as a script or is imported as ops.lan_setup (one state file).
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import ops.dashboard_ctl as dctl  # noqa: E402

_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)  # Windows: ẩn cửa sổ console; non-Windows: 0 (no-op)

ENV_VAR = "AWB_DASHBOARD_HOST"
LAN_VALUE = "0.0.0.0"
LOCAL_VALUE = "127.0.0.1"
DEFAULT_PORT = 5151


def lan_ipv4s() -> list[str]:
    """The machine's non-loopback IPv4 address(es) — what a phone on the LAN would dial."""
    ips: set[str] = set()
    try:  # primary egress IP: connecting a UDP socket picks the outbound interface (no packet sent)
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(("10.255.255.255", 1))
            ips.add(s.getsockname()[0])
        finally:
            s.close()
    except OSError:
        pass
    try:
        for ip in socket.gethostbyname_ex(socket.gethostname())[2]:
            ips.add(ip)
    except OSError:
        pass
    return sorted(i for i in ips if not i.startswith("127."))


def phone_urls(port: int = DEFAULT_PORT) -> list[str]:
    return [f"http://{ip}:{port}" for ip in lan_ipv4s()]


def firewall_command(port: int = DEFAULT_PORT) -> str:
    """The exact (admin) command to allow inbound TCP ``port`` from the LOCAL SUBNET only.
    Printed for the manual path; ``firewall`` / lan_on.bat run it for you (elevated)."""
    if sys.platform == "win32":
        return ('powershell -Command "New-NetFirewallRule -DisplayName '
                f"'AWB dashboard {port} LAN' -Direction Inbound -Protocol TCP -LocalPort {port} "
                "-Action Allow -Profile Private -RemoteAddress LocalSubnet\"")
    return f"sudo ufw allow proto tcp from 192.168.0.0/16 to any port {port}  # adjust to your subnet"


def _set_env(value: str, dry: bool) -> str:
    """Persist the env var for FUTURE processes. Windows: ``setx`` (new shells only — re-open the
    terminal / log out-in). POSIX: not auto-edited (profiles vary) — the caller prints the line."""
    if dry:
        return f"would set {ENV_VAR}={value}"
    if sys.platform == "win32":
        r = subprocess.run(["setx", ENV_VAR, value], capture_output=True, text=True,
                           creationflags=_NO_WINDOW)
        return (f"set {ENV_VAR}={value} (new shells only — re-open the terminal / log out-in)"
                if r.returncode == 0 else f"setx failed: {r.stderr.strip() or r.stdout.strip()}")
    return f"add to your shell profile (not auto-edited):  export {ENV_VAR}={value}"


def _apply_state(host: str, port: int, dry: bool) -> str:
    """Update the persisted start-state so the *next* ``restart`` binds ``host`` immediately —
    this is what fixes 'set the env var but restart still binds localhost', because ``restart``
    reuses the saved host and a stale one would otherwise win over the new default."""
    if dry:
        return f"would set start-state host={host} port={port}"
    dctl.write_state(host, port)
    return f"start-state host={host} port={port} (next restart binds it)"


def status(port: int = DEFAULT_PORT) -> dict:
    env_current = os.environ.get(ENV_VAR)
    effective_host, _ = dctl.resolve_restart_target(None, None)  # what a no-arg restart will bind
    lan = effective_host == LAN_VALUE
    return {
        "env_var": ENV_VAR,
        "env_default": env_current,            # persisted default (None → ships localhost)
        "effective_bind": effective_host,      # what `restart` will actually use (start-state wins)
        "lan_default": lan,
        "lan_urls": phone_urls(port) if lan else [],
        "firewall_command": firewall_command(port),
    }


def enable(port: int = DEFAULT_PORT, dry: bool = False) -> dict:
    return {"action": "enable",
            "env": _set_env(LAN_VALUE, dry),
            "state": _apply_state(LAN_VALUE, port, dry),
            "lan_urls": phone_urls(port),
            "firewall_command": firewall_command(port),
            "note": "Next restart binds the LAN immediately. Open the firewall (run `firewall`, or "
                    "lan_on.bat does it via UAC). Re-open the terminal / log out-in so new shells "
                    "also default to LAN. /admin stays localhost-only."}


def disable(port: int = DEFAULT_PORT, dry: bool = False) -> dict:
    return {"action": "disable",
            "env": _set_env(LOCAL_VALUE, dry),
            "state": _apply_state(LOCAL_VALUE, port, dry),
            "note": "Back to localhost-only. You may also remove the firewall rule: "
                    + (f"powershell -Command \"Remove-NetFirewallRule -DisplayName 'AWB dashboard "
                       f"{port} LAN'\"" if sys.platform == "win32" else "via your firewall tool")}


def open_firewall(port: int = DEFAULT_PORT, dry: bool = False) -> dict:
    """Create the inbound LOCAL-SUBNET rule. Windows: needs admin (lan_on.bat elevates this via
    UAC); idempotent (skips if the rule already exists). POSIX: prints the command."""
    if dry or sys.platform != "win32":
        return {"action": "firewall", "result": "dry-run" if dry else "manual",
                "command": firewall_command(port)}
    rule = (f"if (-not (Get-NetFirewallRule -DisplayName 'AWB dashboard {port} LAN' "
            "-ErrorAction SilentlyContinue)) { New-NetFirewallRule -DisplayName "
            f"'AWB dashboard {port} LAN' -Direction Inbound -Protocol TCP -LocalPort {port} "
            "-Action Allow -Profile Private -RemoteAddress LocalSubnet | Out-Null }")
    r = subprocess.run(["powershell", "-NoProfile", "-Command", rule],
                       capture_output=True, text=True, creationflags=_NO_WINDOW)
    ok = r.returncode == 0
    return {"action": "firewall", "result": "opened" if ok else "failed",
            "detail": (r.stderr or r.stdout).strip() or ("ok" if ok else "needs administrator"),
            "command": firewall_command(port)}


def _emit(obj: dict, as_json: bool) -> None:
    if as_json:
        print(json.dumps(obj, ensure_ascii=False))
        return
    for k, v in obj.items():
        if isinstance(v, list):
            print(f"  {k}:")
            for item in v:
                print(f"    {item}")
        else:
            print(f"  {k}: {v}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Default the dashboard to a LAN bind (env + state + firewall).")
    ap.add_argument("command", choices=["status", "enable", "disable", "firewall"])
    ap.add_argument("--port", type=int, default=DEFAULT_PORT, help=f"dashboard port (default: {DEFAULT_PORT})")
    ap.add_argument("--dry-run", action="store_true", help="show what would change, change nothing")
    ap.add_argument("--json", action="store_true", help="emit the result as JSON")
    args = ap.parse_args(argv)

    if args.command == "status":
        result = status(args.port)
    elif args.command == "enable":
        result = enable(args.port, dry=args.dry_run)
    elif args.command == "disable":
        result = disable(args.port, dry=args.dry_run)
    else:
        result = open_firewall(args.port, dry=args.dry_run)
    _emit(result, args.json)
    return 0 if result.get("result") != "failed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
