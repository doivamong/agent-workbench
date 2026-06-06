"""Tests for .claude/hooks/scripts/secret_write_gate.py — the write-time cloud-token tripwire.

Fake credentials are built by concatenation so this test file never embeds a real token
shape (which leak_scan would otherwise flag on commit).
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / ".claude" / "hooks" / "scripts"))

from secret_write_gate import find_hard_secret  # noqa: E402

HOOK = ROOT / ".claude" / "hooks" / "scripts" / "secret_write_gate.py"

# Built at runtime so the literal token shape never appears in this source file.
AWS = "AKIA" + "Z" * 16
GH = "ghp_" + "z" * 36
GOOGLE = "AIza" + "z" * 35
PRIVKEY = "-----BEGIN RSA PRIVATE KEY" + "-----"

BLOCKED = [
    f'aws = "{AWS}"',
    f"tok = '{GH}'",
    f'key = "{GOOGLE}"',
    PRIVKEY,
]
ALLOWED = [
    "def add(a, b):\n    return a + b",
    'url = "https://example.com/docs"',
    'password = "hunter2"',                 # SOFT/quoted assignment — deliberately NOT blocked
    "FERNET_KEY=Zr8k2notarealshape",        # unquoted env value — out of scope
    f"k = '{AWS}'  # leak-scan: ignore[aws_access_key]",   # scoped opt-out allows it
]


@pytest.mark.parametrize("text", BLOCKED)
def test_hard_secret_detected(text):
    assert find_hard_secret(text) is not None


@pytest.mark.parametrize("text", ALLOWED)
def test_non_hard_text_allowed(text):
    assert find_hard_secret(text) is None


def _run_hook(payload: dict, env: dict | None = None) -> tuple[int, str]:
    proc = subprocess.run([sys.executable, str(HOOK)], input=json.dumps(payload),
                          capture_output=True, text=True, env=env)
    return proc.returncode, proc.stdout.strip()


def _deny(out: str) -> bool:
    return bool(out) and json.loads(out)["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_hook_denies_write_of_cloud_token():
    code, out = _run_hook({"tool_name": "Write",
                           "tool_input": {"file_path": "app.py", "content": f'KEY = "{AWS}"'}})
    assert code == 0 and _deny(out)
    # the message states the honest limit (not full secret protection)
    reason = json.loads(out)["hookSpecificOutput"]["permissionDecisionReason"]
    assert "does not catch every secret" in reason.lower() or "not catch every secret" in reason.lower()


def test_hook_allows_ordinary_write():
    code, out = _run_hook({"tool_name": "Write",
                           "tool_input": {"file_path": "app.py", "content": "x = 1\n"}})
    assert code == 0 and out == ""


def test_hook_exempts_env_files():
    """A real key belongs in .env (gitignored) — that is the allow-path, not a leak."""
    for fname in (".env", ".env.local", "config/.env.production"):
        code, out = _run_hook({"tool_name": "Write",
                               "tool_input": {"file_path": fname, "content": f'AWS_KEY={AWS}'}})
        assert code == 0 and out == "", fname


def test_hook_honors_scoped_ignore_marker():
    code, out = _run_hook({"tool_name": "Write", "tool_input": {
        "file_path": "tests/fixtures.py",
        "content": f"sample = '{AWS}'  # leak-scan: ignore[aws_access_key]"}})
    assert code == 0 and out == ""


def test_hook_denies_edit_new_string():
    code, out = _run_hook({"tool_name": "Edit", "tool_input": {
        "file_path": "app.py", "old_string": "X", "new_string": f"tok = '{GH}'"}})
    assert code == 0 and _deny(out)


def test_hook_allows_non_write_tool():
    code, out = _run_hook({"tool_name": "Bash", "tool_input": {"command": f"echo {AWS}"}})
    assert code == 0 and out == ""


def test_hook_fails_open_on_malformed_payload():
    """A write hook must never break editing — bad input → allow (exit 0, no decision)."""
    proc = subprocess.run([sys.executable, str(HOOK)], input="not json",
                          capture_output=True, text=True)
    assert proc.returncode == 0 and proc.stdout.strip() == ""


def test_explain_blocked():
    proc = subprocess.run([sys.executable, str(HOOK), "--explain", f'k="{GOOGLE}"'],
                          capture_output=True, text=True)
    assert proc.returncode == 1 and "BLOCKED" in proc.stdout


def test_explain_allowed():
    proc = subprocess.run([sys.executable, str(HOOK), "--explain", "x = 1"],
                          capture_output=True, text=True)
    assert proc.returncode == 0 and "ALLOWED" in proc.stdout
