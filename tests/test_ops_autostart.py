"""Tests for ops/autostart.py — stdlib only. Never registers/removes a real Scheduled Task:
the command builders are pure, and enable/disable are exercised via --dry-run."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import ops.autostart as au  # noqa: E402


def test_run_command_launches_dashboard_ctl_start():
    cmd = au.run_command()
    assert "dashboard_ctl.py" in cmd and cmd.rstrip().endswith("start")
    assert cmd.count('"') >= 2  # the interpreter + script paths are quoted (spaces-safe)


def test_schtasks_args_are_onlogon_and_forced():
    args = au.schtasks_create_args()
    assert args[0] == "schtasks" and "/Create" in args
    assert args[args.index("/SC") + 1] == "ONLOGON"
    assert "/F" in args  # idempotent overwrite
    assert args[args.index("/TN") + 1] == au.TASK_NAME


def test_systemd_unit_is_a_user_service():
    unit = au.systemd_unit()
    assert "[Service]" in unit and "ExecStart=" in unit and "dashboard_ctl.py" in unit


def test_enable_dry_run_changes_nothing():
    res = au.enable(dry=True)
    if sys.platform == "win32":
        assert res["result"] == "dry-run"
        assert "schtasks" in res["command"] and "ONLOGON" in res["command"]
    else:
        assert res["result"] == "manual" and "ExecStart=" in res["systemd_unit"]


def test_disable_dry_run_changes_nothing():
    res = au.disable(dry=True)
    if sys.platform == "win32":
        assert res["result"] == "dry-run" and "/Delete" in res["command"]
    else:
        assert res["result"] == "manual"


def test_status_returns_a_dict():
    st = au.status()  # read-only (schtasks /Query on Windows; a hint on POSIX)
    assert st["action"] == "status"
    if sys.platform == "win32":
        assert isinstance(st["registered"], bool)


def test_main_dry_run_exit_zero():
    assert au.main(["enable", "--dry-run", "--json"]) == 0
    assert au.main(["disable", "--dry-run"]) == 0
    assert au.main(["status"]) == 0
