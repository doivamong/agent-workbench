"""Tests for ops/lan_setup.py — stdlib only. Never mutates the real machine env / firewall /
start-state: setx is exercised only via --dry-run, state writes go to a monkeypatched STATEFILE,
and the firewall is exercised via --dry-run."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import ops.lan_setup as ls  # noqa: E402


def test_lan_ipv4s_returns_non_loopback_list():
    ips = ls.lan_ipv4s()
    assert isinstance(ips, list)
    assert all(isinstance(i, str) and not i.startswith("127.") for i in ips)


def test_firewall_command_names_the_port_and_subnet():
    cmd = ls.firewall_command(5151)
    assert "5151" in cmd
    if sys.platform == "win32":
        assert "New-NetFirewallRule" in cmd and "LocalSubnet" in cmd
    else:
        assert "ufw" in cmd


def test_phone_urls_built_from_lan_ips():
    urls = ls.phone_urls(5151)
    assert all(u.startswith("http://") and u.endswith(":5151") for u in urls)
    assert len(urls) == len(ls.lan_ipv4s())


def test_apply_state_writes_the_next_restart_target(tmp_path, monkeypatch):
    # _apply_state persists the host so the NEXT restart binds it (the fix for 'env set but
    # restart still localhost'). Patch the engine's STATEFILE so the real one is untouched.
    monkeypatch.setattr(ls.dctl, "STATEFILE", tmp_path / "dashboard.json")
    assert "would set" in ls._apply_state("0.0.0.0", 5151, dry=True)
    assert ls.dctl.read_state(ls.dctl.STATEFILE) is None  # dry-run wrote nothing
    ls._apply_state("0.0.0.0", 5151, dry=False)
    assert ls.dctl.read_state(ls.dctl.STATEFILE) == {"host": "0.0.0.0", "port": 5151}


def test_status_reflects_the_effective_bind(tmp_path, monkeypatch):
    monkeypatch.setattr(ls.dctl, "STATEFILE", tmp_path / "dashboard.json")
    monkeypatch.delenv(ls.ENV_VAR, raising=False)
    st = ls.status()
    assert st["effective_bind"] == "127.0.0.1" and st["lan_default"] is False and st["lan_urls"] == []
    # Once a LAN bind is persisted, status truthfully reports what restart will bind.
    ls.dctl.write_state("0.0.0.0", 5151, ls.dctl.STATEFILE)
    st = ls.status()
    assert st["effective_bind"] == "0.0.0.0" and st["lan_default"] is True


def test_enable_dry_run_does_not_mutate(tmp_path, monkeypatch):
    monkeypatch.setattr(ls.dctl, "STATEFILE", tmp_path / "dashboard.json")
    monkeypatch.delenv(ls.ENV_VAR, raising=False)
    res = ls.enable(dry=True)
    assert "would set" in res["env"] and "would set" in res["state"]
    assert "5151" in res["firewall_command"]
    import os
    assert os.environ.get(ls.ENV_VAR) is None  # no setx
    assert ls.dctl.read_state(ls.dctl.STATEFILE) is None  # no state write


def test_firewall_dry_run_prints_not_runs():
    res = ls.open_firewall(dry=True)
    assert res["result"] == "dry-run" and "5151" in res["command"]


def test_main_dry_run_exit_zero(capsys):
    assert ls.main(["enable", "--dry-run", "--json"]) == 0
    assert ls.main(["status"]) == 0
    assert ls.main(["disable", "--dry-run"]) == 0
    assert ls.main(["firewall", "--dry-run"]) == 0