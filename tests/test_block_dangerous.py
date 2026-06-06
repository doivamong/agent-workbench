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


def _deny_reason(payload_or_text) -> str:
    """Run the hook and return the permissionDecisionReason of its deny decision."""
    kwargs = {"capture_output": True, "text": True}
    if isinstance(payload_or_text, str):
        kwargs["input"] = payload_or_text          # malformed -> parse-fail deny path
    else:
        kwargs["input"] = json.dumps(payload_or_text)
    proc = subprocess.run([sys.executable, str(HOOK)], **kwargs)
    out = json.loads(proc.stdout.strip())
    return out["hookSpecificOutput"]["permissionDecisionReason"]


# Both user-facing deny paths: the pattern-match deny and the parse-fail (fail-closed) deny.
DENY_PATHS = [
    {"tool_name": "Bash", "tool_input": {"command": "rm -rf /"}},  # match path
    "this is not json",                                            # parse-fail path
]
# Bypass *incantations* a non-programmer must never be taught. These phrases never appear in a
# legitimate danger reason label (so this stays decoupled from the {reason} text — note "force"
# is deliberately NOT here: it is part of honest reason labels like "Force push").
BYPASS_PHRASES = ["outside the agent", "manually", "--no-verify", "bypass", "override"]


@pytest.mark.parametrize("payload", DENY_PATHS)
def test_deny_message_is_recovery_first(payload):
    """Every deny message must keep the honest seatbelt-limit clause and offer a recovery a
    non-programmer can act on, WITHOUT teaching a way to bypass the guard. This test fails if a
    future edit drops the limit clause or reintroduces a bypass incantation (spec opt-3)."""
    reason = _deny_reason(payload).lower()
    # honest limit kept
    assert "not a security boundary" in reason
    # an actionable, non-bypass recovery is offered
    assert "ask me" in reason
    # no bypass incantation
    for phrase in BYPASS_PHRASES:
        assert phrase not in reason, f"deny message must not teach a bypass: {phrase!r}"


# --- project-defined (data-driven) patterns ---------------------------------

import os

from block_dangerous import load_extra_patterns


def _write_patterns(tmp_path, data) -> dict:
    pf = tmp_path / "dangerous-patterns.json"
    pf.write_text(json.dumps(data), encoding="utf-8")
    return dict(os.environ, BLOCK_DANGEROUS_PATTERNS=str(pf))


def test_extra_patterns_extend_check_command(tmp_path, monkeypatch):
    pf = tmp_path / "p.json"
    pf.write_text(json.dumps([{"pattern": r"\breset_db\b", "reason": "wipes the dev database"}]),
                  encoding="utf-8")
    monkeypatch.setenv("BLOCK_DANGEROUS_PATTERNS", str(pf))
    extra = load_extra_patterns()
    assert check_command("reset_db --yes", extra=extra)[1] == "wipes the dev database"
    # built-in safe command still passes with the extra rules loaded
    assert check_command("git status", extra=extra) is None


def test_malformed_patterns_file_fails_open(tmp_path, monkeypatch):
    pf = tmp_path / "bad.json"
    pf.write_text("{not valid json", encoding="utf-8")
    monkeypatch.setenv("BLOCK_DANGEROUS_PATTERNS", str(pf))
    assert load_extra_patterns() == []  # no crash, no rules


def test_hook_blocks_project_pattern_via_env(tmp_path):
    env = _write_patterns(tmp_path, [{"pattern": r"\bnuke_prod\b", "reason": "prod wipe"}])
    proc = subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps({"tool_name": "Bash", "tool_input": {"command": "nuke_prod now"}}),
        capture_output=True, text=True, env=env,
    )
    assert proc.returncode == 0
    decision = json.loads(proc.stdout.strip())["hookSpecificOutput"]["permissionDecision"]
    assert decision == "deny"


# --- --explain audit mode ----------------------------------------------------

def test_explain_reports_blocked():
    proc = subprocess.run([sys.executable, str(HOOK), "--explain", "rm -rf /"],
                          capture_output=True, text=True)
    assert proc.returncode == 1
    assert "BLOCKED" in proc.stdout


def test_explain_reports_allowed():
    proc = subprocess.run([sys.executable, str(HOOK), "--explain", "git status"],
                          capture_output=True, text=True)
    assert proc.returncode == 0
    assert "ALLOWED" in proc.stdout
