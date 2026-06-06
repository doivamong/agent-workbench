"""Tests for the concurrent-session guard core (.claude/hooks/lib/session_lock.py).

Covers the lock write/read round-trip, malformed-lock fail-open, the warn decision
(different live pid warns, same pid / same session / dead pid stay quiet), stale reclaim,
and release-only-if-ours. The suite-wide GIT_* isolation in conftest.py applies (these tests
touch no real git, but inherit the safe env)."""
import json

import session_lock


NOW = "2026-06-06T12:00:00+00:00"


# --- write / read round-trip -------------------------------------------------

def test_write_then_read_round_trips(tmp_path):
    p = tmp_path / "lock.json"
    data = {"pid": 4321, "started_at": NOW, "session_id": "abc"}
    session_lock.write_lock(p, data)
    assert session_lock.read_lock(p) == data


def test_read_missing_lock_is_none(tmp_path):
    assert session_lock.read_lock(tmp_path / "nope.json") is None


def test_read_malformed_lock_is_none(tmp_path):
    p = tmp_path / "lock.json"
    p.write_text("{ this is not json", encoding="utf-8")
    assert session_lock.read_lock(p) is None


def test_read_non_object_json_is_none(tmp_path):
    # A JSON array is valid JSON but not a lock object -> treated as absent, never crashes.
    p = tmp_path / "lock.json"
    p.write_text("[1, 2, 3]", encoding="utf-8")
    assert session_lock.read_lock(p) is None


# --- pid_is_alive: never raises, fails open ----------------------------------

def test_pid_is_alive_self_is_true():
    import os
    assert session_lock.pid_is_alive(os.getpid()) is True


def test_pid_is_alive_rejects_bad_input():
    assert session_lock.pid_is_alive(0) is False
    assert session_lock.pid_is_alive(-1) is False
    assert session_lock.pid_is_alive(None) is False
    assert session_lock.pid_is_alive("123") is False
    assert session_lock.pid_is_alive(True) is False  # bool is not a valid pid


# --- assess: the warn decision -----------------------------------------------

def test_no_existing_lock_no_warning(tmp_path):
    warning, new_lock = session_lock.assess(None, 100, "me", NOW, alive_fn=lambda p: True)
    assert warning is None
    assert new_lock == {"pid": 100, "started_at": NOW, "session_id": "me"}


def test_different_live_pid_warns():
    existing = {"pid": 999, "started_at": "2026-06-06T11:00:00+00:00", "session_id": "other"}
    warning, new_lock = session_lock.assess(existing, 100, "me", NOW, alive_fn=lambda p: True)
    assert warning is not None
    assert "999" in warning and "git worktree" in warning
    assert new_lock["pid"] == 100  # we still refresh the lock to point at us


def test_same_pid_no_warn():
    existing = {"pid": 100, "started_at": NOW, "session_id": "other"}
    warning, _ = session_lock.assess(existing, 100, "me", NOW, alive_fn=lambda p: True)
    assert warning is None


def test_same_session_id_no_warn_even_if_pid_differs():
    # Resume/clear/compact re-fires SessionStart; same session_id must not self-alarm.
    existing = {"pid": 999, "started_at": NOW, "session_id": "me"}
    warning, _ = session_lock.assess(existing, 100, "me", NOW, alive_fn=lambda p: True)
    assert warning is None


def test_dead_pid_is_reclaimed_silently():
    existing = {"pid": 999, "started_at": NOW, "session_id": "other"}
    warning, new_lock = session_lock.assess(existing, 100, "me", NOW, alive_fn=lambda p: False)
    assert warning is None
    assert new_lock["pid"] == 100  # stale lock reclaimed


def test_malformed_existing_pid_no_warn():
    # A lock whose pid isn't an int must not crash assess; degrade to no-warning.
    existing = {"pid": "not-a-pid", "started_at": NOW, "session_id": "other"}
    warning, _ = session_lock.assess(existing, 100, "me", NOW, alive_fn=lambda p: True)
    assert warning is None


# --- end-to-end: read a stale lock from disk, reclaim, warn ------------------

def test_stale_disk_lock_reclaimed_end_to_end(tmp_path):
    p = tmp_path / "lock.json"
    session_lock.write_lock(p, {"pid": 999, "started_at": NOW, "session_id": "old"})
    warning, new_lock = session_lock.assess(
        session_lock.read_lock(p), 100, "me", NOW, alive_fn=lambda p: False
    )
    assert warning is None
    session_lock.write_lock(p, new_lock)
    assert json.loads(p.read_text(encoding="utf-8"))["pid"] == 100


# --- release_lock: only removes our own lock ---------------------------------

def test_release_removes_own_lock_by_session_id(tmp_path):
    p = tmp_path / "lock.json"
    session_lock.write_lock(p, {"pid": 100, "started_at": NOW, "session_id": "me"})
    assert session_lock.release_lock(p, 100, "me") is True
    assert not p.exists()


def test_release_leaves_other_session_lock(tmp_path):
    p = tmp_path / "lock.json"
    session_lock.write_lock(p, {"pid": 999, "started_at": NOW, "session_id": "other"})
    assert session_lock.release_lock(p, 100, "me") is False
    assert p.exists()  # not ours — left intact so its warning signal survives


def test_release_matches_by_pid_when_no_session_id(tmp_path):
    p = tmp_path / "lock.json"
    session_lock.write_lock(p, {"pid": 100, "started_at": NOW, "session_id": ""})
    assert session_lock.release_lock(p, 100, "") is True
    assert not p.exists()


def test_release_missing_lock_is_noop(tmp_path):
    assert session_lock.release_lock(tmp_path / "nope.json", 100, "me") is False
