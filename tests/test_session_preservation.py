"""Tests for the session-preservation hooks: handover_utils, precompact_backup,
compact_restore, context_tracker."""
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import compact_restore as cr
import context_tracker as ct
import handover_utils as hu
import precompact_backup


# --- handover_utils ---

def test_get_handovers_dir_creates(tmp_path):
    d = hu.get_handovers_dir(str(tmp_path))
    assert d.is_dir() and d == tmp_path / ".claude" / "handovers"


def test_cleanup_keeps_newest_n(tmp_path):
    d = hu.get_handovers_dir(str(tmp_path))
    for i in range(8):
        f = d / f"transcript_{i}.jsonl"
        f.write_text("x", encoding="utf-8")
        os.utime(f, (i, i))  # ascending mtime
    removed = hu.cleanup_old_files(d, "transcript_*.jsonl", keep=5)
    assert removed == 3
    assert len(list(d.glob("transcript_*.jsonl"))) == 5


def test_latest_handover_skips_too_old(tmp_path):
    d = hu.get_handovers_dir(str(tmp_path))
    old = d / "HANDOVER_old.md"
    old.write_text("old", encoding="utf-8")
    os.utime(old, (time.time() - 48 * 3600,) * 2)
    assert hu.get_latest_handover(str(tmp_path), max_age_hours=24) is None


# --- compact_restore.build_recovery_context ---

def _write_signal(handovers: Path, age_seconds: float) -> None:
    ts = (datetime.now(timezone.utc) - timedelta(seconds=age_seconds)).isoformat()
    (handovers / ".last_compact").write_text(json.dumps({"timestamp": ts}), encoding="utf-8")


def test_recovery_none_without_signal(tmp_path):
    d = hu.get_handovers_dir(str(tmp_path))
    assert cr.build_recovery_context(d, datetime.now(timezone.utc)) is None


def test_recovery_none_when_signal_stale(tmp_path):
    d = hu.get_handovers_dir(str(tmp_path))
    (d / "HANDOVER_x.md").write_text("# Goal\nship it\n", encoding="utf-8")
    _write_signal(d, age_seconds=999)  # older than SIGNAL_MAX_AGE
    assert cr.build_recovery_context(d, datetime.now(timezone.utc)) is None


def test_recovery_injects_excerpt_when_recent(tmp_path):
    d = hu.get_handovers_dir(str(tmp_path))
    (d / "HANDOVER_x.md").write_text("# Goal\nship the thing\n# Next\nwrite tests\n", encoding="utf-8")
    _write_signal(d, age_seconds=10)
    ctx = cr.build_recovery_context(d, datetime.now(timezone.utc))
    assert ctx is not None
    assert "POST-COMPACT RECOVERY" in ctx
    assert "ship the thing" in ctx


# --- context_tracker.register_tool ---

def test_edit_warn_fires_at_threshold():
    state = ct.new_state(now=0.0)
    msg = None
    for _ in range(ct.EDIT_WARN):
        msg = ct.register_tool(state, "Edit", now=1.0)
    assert msg is not None and "edits this session" in msg


def test_tool_checkpoint_message():
    state = ct.new_state(now=0.0)
    msg = None
    for _ in range(ct.TOOL_CHECKPOINT):
        msg = ct.register_tool(state, "Bash", now=1.0)
    assert msg is not None and "tool calls" in msg


def test_cooldown_suppresses_repeat():
    state = ct.new_state(now=0.0)
    for _ in range(ct.EDIT_WARN):
        ct.register_tool(state, "Edit", now=1.0)
    # Next edit lands within the cooldown window -> no second message.
    extra = ct.register_tool(state, "Edit", now=2.0)
    assert extra is None


def test_load_state_resets_after_ttl(tmp_path, monkeypatch):
    monkeypatch.setenv("CONTEXT_TRACKER_STATE", str(tmp_path / "s.json"))
    ct.save_state("/proj", {"start_time": 0.0, "tool_count": 99, "edit_count": 0, "last_message": 0})
    fresh = ct.load_state("/proj", now=ct.SESSION_TTL + 1)  # well past TTL
    assert fresh["tool_count"] == 0


# --- precompact_backup end-to-end (subprocess, real stdin/stdout contract) ---

def test_precompact_backup_writes_backup_and_signal(tmp_path):
    transcript = tmp_path / "t.jsonl"
    transcript.write_text('{"role":"user"}\n', encoding="utf-8")
    payload = json.dumps({"transcript_path": str(transcript), "trigger": "manual", "cwd": str(tmp_path)})
    proc = subprocess.run(
        [sys.executable, precompact_backup.__file__],
        input=payload, capture_output=True, text=True,
    )
    assert proc.returncode == 0
    handovers = tmp_path / ".claude" / "handovers"
    assert (handovers / ".last_compact").exists()
    assert list(handovers.glob("transcript_manual_*.jsonl"))
