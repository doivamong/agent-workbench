"""Cross-hook integration: every shipped hook honors the Claude Code contract.

Individual behavior is tested per hook; this file is the consolidated guarantee
that ALL of them, run as real subprocesses over stdin/stdout, share the same
safety envelope — no hook ever crashes the session (fail-open exit 0), and the
one security gate fails CLOSED (deny) on an unparseable payload.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

HOOKS_DIR = Path(__file__).resolve().parents[1] / ".claude" / "hooks"
ALL_HOOKS = [
    HOOKS_DIR / "scripts" / "block_dangerous.py",
    HOOKS_DIR / "scripts" / "post_edit_simplify.py",
    HOOKS_DIR / "scripts" / "precompact_backup.py",
    HOOKS_DIR / "scripts" / "compact_restore.py",
    HOOKS_DIR / "scripts" / "context_tracker.py",
    HOOKS_DIR / "prompt-refiner-inject.py",
]


def _run(hook: Path, stdin: str, env_extra=None):
    env = dict(os.environ, HOME=os.environ.get("TEMP", "/tmp"))
    if env_extra:
        env.update(env_extra)
    return subprocess.run([sys.executable, str(hook)], input=stdin,
                          capture_output=True, text=True, env=env)


import pytest


@pytest.mark.parametrize("hook", ALL_HOOKS, ids=lambda p: p.name)
def test_every_hook_fails_open_on_garbage(hook, tmp_path):
    # malformed stdin must never crash (exit 0) and must emit valid JSON or nothing
    proc = _run(hook, "this is not json{{{",
                env_extra={"HOME": str(tmp_path), "USERPROFILE": str(tmp_path),
                           "POST_EDIT_SIMPLIFY_STATE": str(tmp_path / "s.json")})
    assert proc.returncode == 0, proc.stderr
    if proc.stdout.strip():
        json.loads(proc.stdout)  # whatever it prints must be parseable


@pytest.mark.parametrize("hook", ALL_HOOKS, ids=lambda p: p.name)
def test_every_hook_survives_empty_stdin(hook, tmp_path):
    proc = _run(hook, "",
                env_extra={"HOME": str(tmp_path), "USERPROFILE": str(tmp_path),
                           "POST_EDIT_SIMPLIFY_STATE": str(tmp_path / "s.json")})
    assert proc.returncode == 0, proc.stderr


def test_only_block_dangerous_denies_on_malformed():
    # the security gate is the one that must fail CLOSED on garbage
    proc = _run(ALL_HOOKS[0], "not json")
    decision = json.loads(proc.stdout)["hookSpecificOutput"]["permissionDecision"]
    assert decision == "deny"
