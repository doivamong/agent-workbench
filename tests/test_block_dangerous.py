import json
import subprocess
import sys
from pathlib import Path

import pytest

from block_dangerous import check_command

HOOK = Path(__file__).resolve().parents[1] / ".claude" / "hooks" / "scripts" / "block_dangerous.py"

SAFE = [
    "git status",
    "git push origin main",
    "git checkout -- file.py",
    "git checkout .gitignore",
    "pytest tests/",
    "rm build/tmp.o",
]
DANGEROUS = [
    "git push origin main --force",
    "git push -f",
    "git reset --hard HEAD~3",
    "git clean -fd",
    "rm -rf /",
    "DROP TABLE users;",
    "TRUNCATE logs",
]


@pytest.mark.parametrize("cmd", SAFE)
def test_safe_commands_pass(cmd):
    assert check_command(cmd) is None


@pytest.mark.parametrize("cmd", DANGEROUS)
def test_dangerous_commands_caught(cmd):
    assert check_command(cmd) is not None


def _run_hook(payload: dict) -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
    )
    return proc.returncode, proc.stdout.strip()


def test_hook_denies_dangerous_via_stdin():
    code, out = _run_hook({"tool_name": "Bash", "tool_input": {"command": "rm -rf /"}})
    assert code == 0
    decision = json.loads(out)["hookSpecificOutput"]["permissionDecision"]
    assert decision == "deny"


def test_hook_allows_safe_via_stdin():
    code, out = _run_hook({"tool_name": "Bash", "tool_input": {"command": "git status"}})
    assert code == 0
    assert out == ""  # no decision -> default flow continues
