"""Tests for ops/lan_setup.py — stdlib only. Never mutates the real machine env / firewall:
env changes are exercised via --dry-run, and status via a monkeypatched os.environ."""
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


def test_status_reflects_env(monkeypatch):
    monkeypatch.delenv(ls.ENV_VAR, raising=False)
    st = ls.status()
    assert st["current"] is None and st["resolved_bind"] == "127.0.0.1"
    assert st["lan_default"] is False and st["lan_urls"] == []

    monkeypatch.setenv(ls.ENV_VAR, "0.0.0.0")
    st = ls.status()
    assert st["current"] == "0.0.0.0" and st["lan_default"] is True


def test_enable_dry_run_does_not_mutate(monkeypatch):
    monkeypatch.delenv(ls.ENV_VAR, raising=False)
    res = ls.enable(dry=True)
    assert res["action"] == "enable"
    assert "would set" in res["env"]  # dry-run never calls setx / edits anything
    assert "5151" in res["firewall_command"]
    # The real process env is untouched by a dry-run.
    import os
    assert os.environ.get(ls.ENV_VAR) is None


def test_main_dry_run_exit_zero(capsys):
    assert ls.main(["enable", "--dry-run", "--json"]) == 0
    assert ls.main(["status"]) == 0
    assert ls.main(["disable", "--dry-run"]) == 0
