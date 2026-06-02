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
    # near-misses that must NOT be flagged (guards against over-blocking)
    "rm -f stale.lock",          # force but not recursive, specific target
    "ls -lrf",                   # not rm
    'find . -name "*.py"',       # find without -delete/-exec rm
    "chmod 644 file.txt",        # not recursive 777
    "delete from users where id = 1",  # has WHERE
    "truncate -s 1M sparse.img", # grows a file; not the empty-it form, and not SQL
    # writes that produce output are normal, not destructive truncation
    "echo done > status.txt",    # command writes to a file
    "cat > config.json",         # heredoc-style write (agents do this constantly)
    "cat src.txt > dst.txt",     # copy/overwrite via command output
    "ls >> build.log",           # append, not truncate
]
DANGEROUS = [
    "git push origin main --force",
    "git push -f",
    "git reset --hard HEAD~3",
    "git clean -fd",
    "rm -rf /",
    "DROP TABLE users;",
    "TRUNCATE logs",
    # --- adversarial: evasion attempts that earlier slipped through ---
    "rm  -rf  /",                # extra whitespace
    "rm -fr /",                  # reordered flags
    "rm -r -f .",                # split flags
    "RM -RF /",                  # uppercase
    "rm -rf $HOME",              # variable target
    "DROP   TABLE users",        # extra whitespace in SQL
    "find / -delete",            # bulk delete, no rm
    "find . -exec rm {} +",      # delete via find -exec
    "dd if=/dev/zero of=/dev/sda",  # raw device write
    "mkfs.ext4 /dev/sda1",       # format filesystem
    ":(){ :|:& };:",             # fork bomb
    "chmod -R 777 /",            # recursive perms
    "delete from users;",        # DELETE without WHERE
    "truncate -s 0 prod.db",     # coreutils truncate that empties a file
    "> config.json",             # content-less truncating redirect
    ": > prod.db",               # : > file idiom — empties a file
    "echo hi; > important.log",  # truncating redirect after a separator
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


def test_hook_fails_closed_on_malformed_payload():
    """An unparseable payload must DENY (fail-closed), not silently allow."""
    proc = subprocess.run(
        [sys.executable, str(HOOK)],
        input="this is not json",
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0
    decision = json.loads(proc.stdout.strip())["hookSpecificOutput"]["permissionDecision"]
    assert decision == "deny"
