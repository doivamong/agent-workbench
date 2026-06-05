#!/usr/bin/env python3
"""lan_setup.py — one-step setup to reach the read-only dashboard from another device.

Sets the ``AWB_DASHBOARD_HOST`` environment variable so the dashboard defaults to a LAN bind
(``0.0.0.0``) — then a bare ``python ui/web/app.py`` or a no-arg ``restart_all`` binds the LAN
with no extra flag, e.g. to view it from a phone on the same Wi-Fi. It also prints your LAN
URL(s) and the exact firewall command to open the port.

    python ops/lan_setup.py status      # current env value, resolved bind, LAN URL(s)
    python ops/lan_setup.py enable       # default to a LAN bind (sets the env var)
    python ops/lan_setup.py disable      # back to localhost-only
    python ops/lan_setup.py enable --dry-run   # show what it would do, change nothing

Stdlib only. **It does NOT open your firewall** — opening an inbound port is a deliberate
security action, so this PRINTS the exact command for you to run once as administrator instead
of doing it silently. The shipped default stays ``127.0.0.1``; only your machine, with the env
var set, defaults to a LAN bind. The ``/admin`` action surface still refuses a ``0.0.0.0`` bind
regardless — only the read-only data is ever on the wire. The firewall (scoped to your local
subnet) is the real access control, not the app.
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
    """The exact (admin) command to allow inbound TCP ``port`` from the LOCAL SUBNET only —
    printed for you to run once, never run automatically."""
    if sys.platform == "win32":
        return ('powershell -Command "New-NetFirewallRule -DisplayName '
                f"'AWB dashboard {port} LAN' -Direction Inbound -Protocol TCP -LocalPort {port} "
                "-Action Allow -Profile Private -RemoteAddress LocalSubnet\"")
    return f"sudo ufw allow proto tcp from 192.168.0.0/16 to any port {port}  # adjust to your subnet"


def _set_env(value: str, dry: bool) -> str:
    """Persist the env var for future processes. Windows: ``setx`` (new shells only — re-open
    the terminal / log out-in for a double-click to pick it up). POSIX: not auto-edited (shell
    profiles vary) — the caller prints the export line to add yourself."""
    if dry:
        return f"would set {ENV_VAR}={value}"
    if sys.platform == "win32":
        r = subprocess.run(["setx", ENV_VAR, value], capture_output=True, text=True)
        return (f"set {ENV_VAR}={value} (new shells only — re-open the terminal / log out-in)"
                if r.returncode == 0 else f"setx failed: {r.stderr.strip() or r.stdout.strip()}")
    return (f"add to your shell profile (not auto-edited):  export {ENV_VAR}={value}")


def status(port: int = DEFAULT_PORT) -> dict:
    current = os.environ.get(ENV_VAR)
    resolved = current or LOCAL_VALUE
    return {
        "env_var": ENV_VAR,
        "current": current,  # None if unset (→ ships localhost)
        "resolved_bind": resolved,
        "lan_default": resolved == LAN_VALUE,
        "lan_urls": phone_urls(port) if resolved == LAN_VALUE else [],
        "firewall_command": firewall_command(port),
    }


def enable(port: int = DEFAULT_PORT, dry: bool = False) -> dict:
    return {"action": "enable", "env": _set_env(LAN_VALUE, dry),
            "lan_urls": phone_urls(port),
            "firewall_command": firewall_command(port),
            "note": "Run the firewall command ONCE as administrator, then re-open your terminal "
                    "(or log out/in) so a double-click picks up the env var. /admin stays localhost-only."}


def disable(dry: bool = False) -> dict:
    return {"action": "disable", "env": _set_env(LOCAL_VALUE, dry),
            "note": "Back to localhost-only. You may also remove the firewall rule: "
                    + (f"powershell -Command \"Remove-NetFirewallRule -DisplayName 'AWB dashboard "
                       f"{DEFAULT_PORT} LAN'\"" if sys.platform == "win32" else "via your firewall tool")}


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
    ap = argparse.ArgumentParser(description="Default the dashboard to a LAN bind (env + firewall hint).")
    ap.add_argument("command", choices=["status", "enable", "disable"])
    ap.add_argument("--port", type=int, default=DEFAULT_PORT, help=f"dashboard port (default: {DEFAULT_PORT})")
    ap.add_argument("--dry-run", action="store_true", help="show what would change, change nothing")
    ap.add_argument("--json", action="store_true", help="emit the result as JSON")
    args = ap.parse_args(argv)

    if args.command == "status":
        result = status(args.port)
    elif args.command == "enable":
        result = enable(args.port, dry=args.dry_run)
    else:
        result = disable(dry=args.dry_run)
    _emit(result, args.json)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
