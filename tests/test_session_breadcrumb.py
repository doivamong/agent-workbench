"""N12-C: the cross-session breadcrumb (session_end writes, session_start surfaces).

A breadcrumb is a one-line "where I left off", not a handover: session_end records git state at
session end; session_start reads a FRESH one and injects a single line. The contract under test:
the writer and reader agree on path + schema, stale breadcrumbs do not resurface, and neither
hook ever breaks a session (fail-open).
"""
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import session_breadcrumb as sb

ROOT = Path(__file__).resolve().parents[1]
SESSION_END = ROOT / ".claude" / "hooks" / "scripts" / "session_end.py"
SESSION_START = ROOT / ".claude" / "hooks" / "scripts" / "session_start.py"


# --- lib: session_breadcrumb (pure) ---

def test_breadcrumb_path_env_override(tmp_path, monkeypatch):
    p = tmp_path / "bc.json"
    monkeypatch.setenv("SESSION_BREADCRUMB_PATH", str(p))
    assert sb.breadcrumb_path("/whatever") == p


def test_breadcrumb_default_path_is_project_local(monkeypatch):
    monkeypatch.delenv("SESSION_BREADCRUMB_PATH", raising=False)
    assert sb.breadcrumb_path("/proj") == Path("/proj") / ".claude" / ".logs" / "last_session.json"


def test_write_read_roundtrip(tmp_path):
    p = tmp_path / "deep" / "bc.json"      # parent dir does not exist yet
    data = {"branch": "main", "commit": "abc x", "uncommitted": 2, "ended_at": "2026-06-03T00:00:00+00:00"}
    sb.write_breadcrumb(p, data)
    assert sb.read_breadcrumb(p) == data


def test_read_missing_is_none(tmp_path):
    assert sb.read_breadcrumb(tmp_path / "nope.json") is None


def test_format_note_fresh(tmp_path):
    now = datetime(2026, 6, 3, 12, 0, tzinfo=timezone.utc)
    data = {"ended_at": (now - timedelta(hours=2)).isoformat(), "branch": "feat/x",
            "commit": "abc123 do thing", "uncommitted": 3}
    note = sb.format_note(data, now)
    assert "Last session (2h ago)" in note
    assert "`feat/x`" in note
    assert "3 uncommitted" in note


def test_format_note_stale_returns_none():
    now = datetime(2026, 6, 3, tzinfo=timezone.utc)
    data = {"ended_at": (now - timedelta(days=10)).isoformat(), "branch": "x", "commit": "y"}
    assert sb.format_note(data, now) is None


def test_format_note_empty_returns_none():
    now = datetime(2026, 6, 3, tzinfo=timezone.utc)
    assert sb.format_note(None, now) is None
    assert sb.format_note({}, now) is None


def test_format_note_clean_tree_omits_dirty_part():
    now = datetime(2026, 6, 3, tzinfo=timezone.utc)
    data = {"ended_at": now.isoformat(), "branch": "main", "commit": "abc", "uncommitted": 0}
    assert "uncommitted" not in sb.format_note(data, now)


def test_format_note_truncates_long_commit():
    now = datetime(2026, 6, 3, tzinfo=timezone.utc)
    data = {"ended_at": now.isoformat(), "branch": "m", "commit": "x" * 200, "uncommitted": 0}
    note = sb.format_note(data, now)
    assert "…" in note and len(note) < 120


# --- session_end hook (subprocess) ---

def _run(hook: Path, stdin: str, env_extra: dict) -> subprocess.CompletedProcess:
    env = dict(os.environ, HOME=os.environ.get("TEMP", "/tmp"), **env_extra)
    return subprocess.run([sys.executable, str(hook)], input=stdin,
                          capture_output=True, text=True, env=env)


def test_session_end_writes_breadcrumb(tmp_path):
    bc = tmp_path / "bc.json"
    # cwd = a non-git tmp dir, so git fields come back empty but the breadcrumb still writes
    proc = _run(SESSION_END, json.dumps({"cwd": str(tmp_path)}), {"SESSION_BREADCRUMB_PATH": str(bc)})
    assert proc.returncode == 0, proc.stderr
    data = json.loads(bc.read_text(encoding="utf-8"))
    assert set(data) >= {"ended_at", "branch", "commit", "uncommitted"}


def test_session_end_kill_switch(tmp_path):
    bc = tmp_path / "bc.json"
    proc = _run(SESSION_END, json.dumps({"cwd": str(tmp_path)}),
                {"SESSION_BREADCRUMB_PATH": str(bc), "SESSION_BREADCRUMB": "0"})
    assert proc.returncode == 0
    assert not bc.exists()


def test_session_end_fails_open_on_garbage(tmp_path):
    bc = tmp_path / "bc.json"
    proc = _run(SESSION_END, "not json{{{", {"SESSION_BREADCRUMB_PATH": str(bc)})
    assert proc.returncode == 0       # never blocks teardown


# --- session_start surfaces the breadcrumb ---

def test_session_start_injects_breadcrumb_note(tmp_path):
    bc = tmp_path / "bc.json"
    now = datetime.now(timezone.utc)
    sb.write_breadcrumb(bc, {"ended_at": now.isoformat(timespec="seconds"),
                             "branch": "feat/demo", "commit": "abc123 x", "uncommitted": 1})
    proc = _run(SESSION_START, json.dumps({"source": "startup", "cwd": str(tmp_path)}),
                {"SESSION_BREADCRUMB_PATH": str(bc)})
    assert proc.returncode == 0, proc.stderr
    ctx = json.loads(proc.stdout)["hookSpecificOutput"]["additionalContext"]
    assert "Last session" in ctx and "`feat/demo`" in ctx


def test_session_start_no_breadcrumb_no_note(tmp_path):
    # no breadcrumb file and no primer -> empty injection, still exit 0
    proc = _run(SESSION_START, json.dumps({"source": "startup", "cwd": str(tmp_path)}),
                {"SESSION_BREADCRUMB_PATH": str(tmp_path / "absent.json")})
    assert proc.returncode == 0
    assert json.loads(proc.stdout) == {}
