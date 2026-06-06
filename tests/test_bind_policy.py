"""Tests for ui/bind_policy.py — the shared bind-host classifier + Internet-facing-bind refusal.

Stdlib-only (the module imports only ``ipaddress``), so these always run — no Flask skip.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ui"))

import bind_policy  # noqa: E402


# (host, expected scope)
SCOPES = [
    # localhost — this machine only
    ("127.0.0.1", "localhost"),
    ("::1", "localhost"),
    # lan — all-interfaces (0.0.0.0/::) + private + link-local
    ("0.0.0.0", "lan"),
    ("::", "lan"),
    ("192.168.1.10", "lan"),
    ("10.1.2.3", "lan"),
    ("172.16.5.5", "lan"),
    ("169.254.1.1", "lan"),       # link-local
    ("fd00::1", "lan"),           # IPv6 ULA (private)
    # public — globally routable; the thing opt-2 refuses. (Documentation ranges like
    # 203.0.113.0/24 are is_private=True in stdlib ipaddress, so they classify as 'lan', not
    # 'public' — use genuinely routable addresses here.)
    ("8.8.8.8", "public"),
    ("1.1.1.1", "public"),
    ("2606:4700:4700::1111", "public"),  # public IPv6
    # hostname — non-literal, unclassifiable here (treated as non-public)
    ("dashboard.local", "hostname"),
    ("example.com", "hostname"),
]


def test_bind_scope_classification():
    for host, expected in SCOPES:
        assert bind_policy.bind_scope(host) == expected, host


def test_is_public_only_true_for_public():
    for host, expected in SCOPES:
        assert bind_policy.is_public_bind_host(host) is (expected == "public"), host


def test_lan_and_loopback_are_not_public():
    # the sanctioned modes (LAN-mobile + localhost) must never be refused
    for host in ("127.0.0.1", "0.0.0.0", "192.168.0.42", "::1", "::"):
        assert not bind_policy.is_public_bind_host(host)


def test_refusal_message_names_risk_and_safe_path_without_teaching_a_bypass():
    msg = bind_policy.public_bind_refusal("8.8.8.8").lower()
    assert "8.8.8.8" in msg                            # names the offending host
    assert "cleartext" in msg                          # states the real risk
    # points at the safe path the owner actually wants (reverse proxy / Cloudflare Tunnel)
    assert "reverse proxy" in msg or "tunnel" in msg
    # must not teach a way to switch the guard off
    for bypass in ("--force", "disable", "override", "ignore"):
        assert bypass not in msg
