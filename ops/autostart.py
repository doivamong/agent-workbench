#!/usr/bin/env python3
"""autostart.py — start the dashboard automatically at logon (so it's there after a reboot).

Registers an OS auto-start entry that launches the dashboard when you log in. The dashboard then
binds whatever ``AWB_DASHBOARD_HOST`` defaults to (a LAN bind if you ran ``lan_setup.py enable``),
so a phone on the LAN can reach it without you starting anything by hand.

    python ops/autostart.py status      # is the logon entry registered?
    python ops/autostart.py enable        # register it
    python ops/autostart.py disable       # remove it
    python ops/autostart.py enable --dry-run    # show the command, change nothing

Stdlib only. **Windows:** a Scheduled Task (``schtasks``) triggered ``ONLOGON`` that runs
``dashboard_ctl start`` hidden via ``pythonw.exe``. Creating it may need administrator rights —
``win/autostart_on.bat`` self-elevates via UAC. **POSIX:** prints a ready-to-paste systemd
*user* service (auto-creating one is too distro-specific to do safely).

Security: this makes the dashboard come up on every logon — if it defaults to a LAN bind, it is
reachable on your subnet at every boot. The firewall (LocalSubnet) is the real control. A LAN /
``0.0.0.0`` bind is allowed but a public bind is refused (``ui/bind_policy.py``); ``/admin`` is NOT
refused on a LAN bind, so if you have set an admin password it is reachable on the subnet at every
boot and its password travels in cleartext over plain HTTP — keep it on a trusted LAN, or front it
with a reverse proxy / Cloudflare Tunnel for domain access.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

if sys.stdout is not None and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    except Exception:
        pass

_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)  # Windows: ẩn cửa sổ console; non-Windows: 0 (no-op)

TASK_NAME = "AWB Dashboard (logon)"
_SCRIPT = Path(__file__).resolve().parent / "dashboard_ctl.py"


def _launcher() -> str:
    """Prefer pythonw.exe (no console window flashes at logon); fall back to the interpreter."""
    exe = Path(sys.executable)
    if sys.platform == "win32":
        pyw = exe.with_name("pythonw.exe")
        return str(pyw if pyw.exists() else exe)
    return str(exe)


def run_command() -> str:
    """The command the logon entry runs: launch the dashboard via dashboard_ctl (so it records
    the pidfile/state and health-checks, exactly like a manual ``start``)."""
    return f'"{_launcher()}" "{_SCRIPT}" start'


def schtasks_create_args() -> list[str]:
    return ["schtasks", "/Create", "/TN", TASK_NAME, "/TR", run_command(),
            "/SC", "ONLOGON", "/RL", "LIMITED", "/F"]


def systemd_unit() -> str:
    return ("[Unit]\nDescription=Agent Workbench dashboard\n\n[Service]\n"
            f"ExecStart={_launcher()} {_SCRIPT} start\nRestart=on-failure\n\n"
            "[Install]\nWantedBy=default.target\n"
            "# Save as ~/.config/systemd/user/awb-dashboard.service, then:\n"
            "#   systemctl --user enable --now awb-dashboard.service")


def enable(dry: bool = False) -> dict:
    if sys.platform != "win32":
        return {"action": "enable", "result": "manual", "systemd_unit": systemd_unit()}
    if dry:
        return {"action": "enable", "result": "dry-run", "command": " ".join(schtasks_create_args())}
    r = subprocess.run(schtasks_create_args(), capture_output=True, text=True,
                       creationflags=_NO_WINDOW)
    ok = r.returncode == 0
    return {"action": "enable", "result": "enabled" if ok else "failed",
            "detail": (r.stdout or r.stderr).strip() or ("ok" if ok else "access denied"),
            "note": "Runs `dashboard_ctl start` at logon (hidden). It binds whatever "
                    "AWB_DASHBOARD_HOST defaults to. If this said access-denied, run it elevated "
                    "(win/autostart_on.bat self-elevates via UAC)."}


def disable(dry: bool = False) -> dict:
    if sys.platform != "win32":
        return {"action": "disable", "result": "manual",
                "hint": "systemctl --user disable --now awb-dashboard.service"}
    args = ["schtasks", "/Delete", "/TN", TASK_NAME, "/F"]
    if dry:
        return {"action": "disable", "result": "dry-run", "command": " ".join(args)}
    r = subprocess.run(args, capture_output=True, text=True, creationflags=_NO_WINDOW)
    ok = r.returncode == 0
    return {"action": "disable", "result": "removed" if ok else "not-found",
            "detail": (r.stdout or r.stderr).strip()}


def status() -> dict:
    if sys.platform != "win32":
        return {"action": "status", "platform": "posix",
                "hint": "check: systemctl --user status awb-dashboard.service"}
    r = subprocess.run(["schtasks", "/Query", "/TN", TASK_NAME], capture_output=True, text=True,
                       creationflags=_NO_WINDOW)
    return {"action": "status", "task": TASK_NAME, "registered": r.returncode == 0,
            "runs": run_command()}


def _emit(obj: dict, as_json: bool) -> None:
    if as_json:
        print(json.dumps(obj, ensure_ascii=False))
        return
    for k, v in obj.items():
        print(f"  {k}: {v}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Auto-start the dashboard at logon (Scheduled Task).")
    ap.add_argument("command", choices=["status", "enable", "disable"])
    ap.add_argument("--dry-run", action="store_true", help="show what would change, change nothing")
    ap.add_argument("--json", action="store_true", help="emit the result as JSON")
    args = ap.parse_args(argv)

    result = {"status": status, "enable": lambda: enable(args.dry_run),
              "disable": lambda: disable(args.dry_run)}[args.command]()
    _emit(result, args.json)
    return 1 if result.get("result") == "failed" else 0


if __name__ == "__main__":
    raise SystemExit(main())
