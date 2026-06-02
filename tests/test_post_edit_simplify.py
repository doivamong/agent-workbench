"""Tests for the post-edit-simplify PostToolUse hook.

Two layers:
  - unit tests on the pure ``register_edit`` / ``load_session`` state transitions
    (threshold, cooldown, distinct-file dedup, TTL reset) — no I/O.
  - end-to-end subprocess runs of the hook script over its real stdin/stdout JSON
    contract, with the session state redirected to a tmp file so nothing touches
    the developer's ~/.claude.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

from post_edit_simplify import (
    load_session,
    new_session,
    register_edit,
    save_session,
)

HOOK = Path(__file__).resolve().parents[1] / ".claude" / "hooks" / "scripts" / "post_edit_simplify.py"

T0 = 1_000_000.0  # an arbitrary fixed "now" so tests don't depend on the wall clock


# --- pure state transition --------------------------------------------------

def test_edit_count_increments():
    s = new_session(T0)
    register_edit(s, "a.py", T0, threshold=5)
    register_edit(s, "b.py", T0, threshold=5)
    assert s["edit_count"] == 2


def test_distinct_files_tracked_once():
    s = new_session(T0)
    register_edit(s, "a.py", T0, threshold=5)
    register_edit(s, "a.py", T0, threshold=5)  # same file again
    register_edit(s, "b.py", T0, threshold=5)
    assert s["modified_files"] == ["a.py", "b.py"]
    assert s["edit_count"] == 3


def test_no_reminder_below_threshold():
    s = new_session(T0)
    out = [register_edit(s, f"f{i}.py", T0, threshold=5) for i in range(4)]
    assert out == [None, None, None, None]


def test_reminder_fires_at_threshold():
    s = new_session(T0)
    msg = None
    for i in range(5):
        msg = register_edit(s, f"f{i}.py", T0, threshold=5)
    assert msg is not None
    assert "5 edits" in msg and "5 file(s)" in msg


def test_first_reminder_fires_on_a_relative_clock():
    # Regression: with a small/relative time base the first reminder must still fire
    # at the threshold (it must not be gated by the cooldown against last_reminder=0).
    s = new_session(0.0)
    msg = None
    for i in range(5):
        msg = register_edit(s, f"f{i}.py", float(i), threshold=5, cooldown=600)
    assert msg is not None


def test_cooldown_suppresses_immediate_repeat():
    s = new_session(T0)
    for i in range(5):
        register_edit(s, f"f{i}.py", T0, threshold=5, cooldown=600)
    # the 6th edit happens 10s later — well within the cooldown
    again = register_edit(s, "f6.py", T0 + 10, threshold=5, cooldown=600)
    assert again is None


def test_reminder_refires_after_cooldown():
    s = new_session(T0)
    for i in range(5):
        register_edit(s, f"f{i}.py", T0, threshold=5, cooldown=600)
    # past the cooldown -> a fresh reminder is due again
    again = register_edit(s, "f6.py", T0 + 601, threshold=5, cooldown=600)
    assert again is not None


def test_session_resets_after_ttl(tmp_path, monkeypatch):
    state = tmp_path / "session.json"
    monkeypatch.setenv("POST_EDIT_SIMPLIFY_STATE", str(state))
    stale = new_session(T0)
    stale["edit_count"] = 99
    save_session(stale)
    # load far in the future (> 2h TTL) -> a zeroed session
    fresh = load_session(T0 + 3 * 60 * 60)
    assert fresh["edit_count"] == 0


def test_session_kept_within_ttl(tmp_path, monkeypatch):
    state = tmp_path / "session.json"
    monkeypatch.setenv("POST_EDIT_SIMPLIFY_STATE", str(state))
    s = new_session(T0)
    s["edit_count"] = 3
    save_session(s)
    again = load_session(T0 + 60)  # one minute later, within TTL
    assert again["edit_count"] == 3


def test_load_session_fresh_when_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("POST_EDIT_SIMPLIFY_STATE", str(tmp_path / "nope.json"))
    s = load_session(T0)
    assert s == new_session(T0)


# --- end-to-end over the real stdin/stdout contract -------------------------

def _run_hook(payload: dict, *, state: Path, env_extra: dict | None = None) -> dict:
    env = dict(os.environ, POST_EDIT_SIMPLIFY_STATE=str(state))
    if env_extra:
        env.update(env_extra)
    proc = subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=env,
    )
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout or "{}")


def test_e2e_single_edit_no_reminder(tmp_path):
    out = _run_hook({"tool_name": "Edit", "tool_input": {"file_path": "a.py"}},
                    state=tmp_path / "s.json")
    assert out == {}


def test_e2e_reminder_after_threshold(tmp_path):
    state = tmp_path / "s.json"
    out = {}
    for i in range(5):
        out = _run_hook({"tool_name": "Write", "tool_input": {"file_path": f"f{i}.py"}},
                        state=state)
    ctx = out["hookSpecificOutput"]["additionalContext"]
    assert "Simplify reminder" in ctx
    assert out["hookSpecificOutput"]["hookEventName"] == "PostToolUse"


def test_e2e_ignores_non_edit_tools(tmp_path):
    state = tmp_path / "s.json"
    out = _run_hook({"tool_name": "Bash", "tool_input": {"command": "ls"}}, state=state)
    assert out == {}
    # a non-edit tool must not create or advance the session
    assert not state.exists()


def test_e2e_disable_switch(tmp_path):
    state = tmp_path / "s.json"
    out = _run_hook({"tool_name": "Edit", "tool_input": {"file_path": "a.py"}},
                    state=state, env_extra={"POST_EDIT_SIMPLIFY": "0"})
    assert out == {}


def test_e2e_threshold_env_override(tmp_path):
    # threshold of 1 -> the very first edit triggers a reminder
    out = _run_hook({"tool_name": "Edit", "tool_input": {"file_path": "a.py"}},
                    state=tmp_path / "s.json", env_extra={"POST_EDIT_SIMPLIFY_THRESHOLD": "1"})
    assert "Simplify reminder" in out["hookSpecificOutput"]["additionalContext"]


def test_e2e_malformed_stdin_is_safe(tmp_path):
    proc = subprocess.run(
        [sys.executable, str(HOOK)],
        input="not json",
        capture_output=True,
        text=True,
        env=dict(os.environ, POST_EDIT_SIMPLIFY_STATE=str(tmp_path / "s.json")),
    )
    assert proc.returncode == 0
    assert json.loads(proc.stdout or "{}") == {}
