"""Tests for tools/sync_manifest.py and the sync_guard PostToolUse hook."""
import json
import subprocess
import sys
from pathlib import Path

import sync_guard as sg
from tools.sync_manifest import build_manifest, diff_manifest
from tools import sync_manifest as sm


def _seed(root: Path) -> None:
    (root / "tools").mkdir(parents=True)
    (root / ".claude" / "skills" / "ex").mkdir(parents=True)
    (root / "tools" / "a.py").write_text("print(1)\n", encoding="utf-8")
    (root / ".claude" / "skills" / "ex" / "SKILL.md").write_text("# x\n", encoding="utf-8")


# --- build_manifest ---

def test_build_manifest_records_set_and_metadata(tmp_path):
    _seed(tmp_path)
    mf = build_manifest(tmp_path)
    assert set(mf["files"]) == {"tools/a.py", ".claude/skills/ex/SKILL.md"}
    a = mf["files"]["tools/a.py"]
    # bytes == real on-disk size (line-ending-agnostic: write_text may emit \r\n on Windows).
    assert a["category"] == "tools" and a["lines"] == 2
    assert a["bytes"] == (tmp_path / "tools" / "a.py").stat().st_size
    assert mf["files"][".claude/skills/ex/SKILL.md"]["category"] == ".claude/skills"


def test_build_manifest_skips_references_and_pycache(tmp_path):
    _seed(tmp_path)
    (tmp_path / ".claude" / "skills" / "ex" / "references").mkdir()
    (tmp_path / ".claude" / "skills" / "ex" / "references" / "deep.md").write_text("x", encoding="utf-8")
    (tmp_path / "tools" / "__pycache__").mkdir()
    (tmp_path / "tools" / "__pycache__" / "a.pyc").write_text("x", encoding="utf-8")
    paths = set(build_manifest(tmp_path)["files"])
    assert not any("references" in p or "__pycache__" in p for p in paths)


# --- diff_manifest: only added/removed are gated; changed is informational ---

def test_diff_classifies_added_removed_changed(tmp_path):
    _seed(tmp_path)
    before = build_manifest(tmp_path)
    (tmp_path / "tools" / "b.py").write_text("print(2)\n", encoding="utf-8")   # add
    (tmp_path / ".claude" / "skills" / "ex" / "SKILL.md").unlink()             # remove
    (tmp_path / "tools" / "a.py").write_text("print(11)\n", encoding="utf-8")  # edit
    added, removed, changed = diff_manifest(before, build_manifest(tmp_path))
    assert added == ["tools/b.py"]
    assert removed == [".claude/skills/ex/SKILL.md"]
    assert changed == ["tools/a.py"]


# --- CLI main(): --write then --check round-trips; a new file makes --check exit 1 ---

def test_cli_write_then_check_in_sync(tmp_path):
    _seed(tmp_path)
    mpath = tmp_path / ".claude" / "manifest.json"
    assert sm.main(["--root", str(tmp_path), "--manifest", str(mpath), "--write"]) == 0
    assert mpath.exists()
    assert sm.main(["--root", str(tmp_path), "--manifest", str(mpath), "--check"]) == 0


def test_cli_check_fails_on_added_file(tmp_path):
    _seed(tmp_path)
    mpath = tmp_path / ".claude" / "manifest.json"
    sm.main(["--root", str(tmp_path), "--manifest", str(mpath), "--write"])
    (tmp_path / "tools" / "new_tool.py").write_text("print(3)\n", encoding="utf-8")
    assert sm.main(["--root", str(tmp_path), "--manifest", str(mpath), "--check"]) == 1


def test_cli_check_passes_on_content_only_edit(tmp_path):
    _seed(tmp_path)
    mpath = tmp_path / ".claude" / "manifest.json"
    sm.main(["--root", str(tmp_path), "--manifest", str(mpath), "--write"])
    (tmp_path / "tools" / "a.py").write_text("print(999)\n", encoding="utf-8")  # edit only
    assert sm.main(["--root", str(tmp_path), "--manifest", str(mpath), "--check"]) == 0


def test_cli_check_without_manifest_fails(tmp_path):
    _seed(tmp_path)
    assert sm.main(["--root", str(tmp_path), "--manifest", str(tmp_path / "none.json"), "--check"]) == 1


# --- sync_guard.reminder_for_write ---

def test_guard_reminds_on_new_watched_file(tmp_path):
    known = {"tools/a.py"}
    msg = sg.reminder_for_write(str(tmp_path / "tools" / "b.py"), tmp_path, known)
    assert msg is not None and "tools/b.py" in msg and "sync_manifest.py" in msg


def test_guard_silent_on_existing_file(tmp_path):
    known = {"tools/a.py"}
    assert sg.reminder_for_write(str(tmp_path / "tools" / "a.py"), tmp_path, known) is None


def test_guard_silent_outside_watched_roots(tmp_path):
    assert sg.reminder_for_write(str(tmp_path / "docs" / "x.md"), tmp_path, set()) is None


def test_guard_silent_on_unscanned_suffix(tmp_path):
    assert sg.reminder_for_write(str(tmp_path / "tools" / "data.json"), tmp_path, set()) is None


# --- sync_guard end-to-end stdin/stdout contract (subprocess) ---

def _run_guard(event: dict, env_extra: dict | None = None) -> dict:
    import os
    env = {**os.environ, **(env_extra or {})}
    proc = subprocess.run(
        [sys.executable, sg.__file__],
        input=json.dumps(event), capture_output=True, text=True, env=env,
    )
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


def test_guard_e2e_injects_for_new_file(tmp_path):
    _seed(tmp_path)
    sm.main(["--root", str(tmp_path), "--manifest", str(tmp_path / ".claude" / "manifest.json"), "--write"])
    event = {"tool_name": "Write", "cwd": str(tmp_path),
             "tool_input": {"file_path": str(tmp_path / "tools" / "brand_new.py")}}
    out = _run_guard(event)
    assert "brand_new.py" in out["hookSpecificOutput"]["additionalContext"]


def test_guard_e2e_silent_for_non_write(tmp_path):
    out = _run_guard({"tool_name": "Edit", "cwd": str(tmp_path),
                      "tool_input": {"file_path": str(tmp_path / "tools" / "x.py")}})
    assert out == {}


def test_guard_e2e_kill_switch(tmp_path):
    _seed(tmp_path)
    event = {"tool_name": "Write", "cwd": str(tmp_path),
             "tool_input": {"file_path": str(tmp_path / "tools" / "brand_new.py")}}
    assert _run_guard(event, {"SYNC_GUARD": "0"}) == {}
