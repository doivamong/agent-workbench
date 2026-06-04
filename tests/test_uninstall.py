"""Tests for uninstall.py — the inverse of install.py.

The load-bearing guarantees: (1) after install→uninstall on a fresh git repo the working
tree is clean (the headline acceptance), (2) a file the user edited since install is KEPT,
not deleted, (3) a missing manifest fails loud instead of pattern-deleting, (4) dry-run is
the default and changes nothing, (5) settings.json is reverted precisely (user hooks kept).
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

import install
import uninstall
from uninstall import revert_settings


def _git(args, cwd):
    return subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True)


def _has_git() -> bool:
    return shutil.which("git") is not None


# --- revert_settings (pure, the inverse of install._merge_settings) ---------

def test_revert_removes_only_installer_commands():
    merged = install._merge_settings({}, install.SETTINGS_SNIPPET)
    reverted = revert_settings(merged, set(install.settings_commands()))
    assert reverted == {}                       # everything the installer added is gone


def test_revert_preserves_user_hooks():
    user_cmd = "python my_own_hook.py"
    existing = {"model": "x", "hooks": {"PreToolUse": [
        {"matcher": "Bash", "hooks": [{"type": "command", "command": user_cmd}]}]}}
    merged = install._merge_settings(existing, install.SETTINGS_SNIPPET)
    reverted = revert_settings(merged, set(install.settings_commands()))
    assert reverted["model"] == "x"             # unrelated key preserved
    cmds = [h["command"] for g in reverted["hooks"]["PreToolUse"] for h in g["hooks"]]
    assert cmds == [user_cmd]                    # the user's own hook survives
    assert reverted == existing                  # exact round-trip back to the original


# --- plan_files classification ---------------------------------------------

def test_plan_files_keeps_modified(tmp_path):
    install.main([str(tmp_path), "--select", "tools"])
    manifest = json.loads((tmp_path / install.MANIFEST_REL).read_text(encoding="utf-8"))
    # edit one installed file so its sha no longer matches the manifest
    edited = tmp_path / "tools" / "leak_scan.py"
    edited.write_text("# I changed this\n", encoding="utf-8")
    remove, keep, gone = uninstall.plan_files(tmp_path, manifest)
    assert "tools/leak_scan.py" in keep
    assert "tools/leak_scan.py" not in remove


# --- dry run (default) ------------------------------------------------------

def test_dry_run_is_default_and_changes_nothing(tmp_path, capsys):
    install.main([str(tmp_path), "--select", "tools"])
    before = sorted(p.name for p in (tmp_path / "tools").iterdir())
    rc = uninstall.main([str(tmp_path)])          # no --yes → dry run
    out = capsys.readouterr().out
    assert rc == 0
    assert "would remove" in out
    assert (tmp_path / "tools" / "leak_scan.py").is_file()   # nothing deleted
    assert sorted(p.name for p in (tmp_path / "tools").iterdir()) == before


# --- missing manifest fails loud -------------------------------------------

def test_missing_manifest_fails_loud(tmp_path, capsys):
    rc = uninstall.main([str(tmp_path), "--yes"])
    err = capsys.readouterr().err
    assert rc == 1
    assert "No installer-manifest" in err
    assert "never pattern-deletes blindly" in err


# --- keep modified on apply -------------------------------------------------

def test_apply_keeps_modified_file(tmp_path):
    install.main([str(tmp_path), "--select", "tools"])
    edited = tmp_path / "tools" / "leak_scan.py"
    edited.write_text("# mine now\n", encoding="utf-8")
    uninstall.main([str(tmp_path), "--yes"])
    assert edited.is_file()                                   # user edit kept
    assert edited.read_text(encoding="utf-8") == "# mine now\n"
    # an untouched installed file from the same group is gone
    assert not (tmp_path / "tools" / "invariants.py").exists()


# --- settings revert leaves a backup when settings pre-existed --------------

def test_revert_preexisting_settings_leaves_bak(tmp_path):
    claude = tmp_path / ".claude"
    claude.mkdir()
    user_cmd = "python user_hook.py"
    (claude / "settings.json").write_text(json.dumps(
        {"hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [
            {"type": "command", "command": user_cmd}]}]}}), encoding="utf-8")
    install.main([str(tmp_path), "--select", "hooks", "--merge-settings"])
    uninstall.main([str(tmp_path), "--yes"])
    # settings.json kept (pre-existing) with the user hook, kit hooks stripped
    data = json.loads((claude / "settings.json").read_text(encoding="utf-8"))
    cmds = [h["command"] for g in data["hooks"]["PreToolUse"] for h in g["hooks"]]
    assert cmds == [user_cmd]
    assert (claude / "settings.json.bak").is_file()          # backup left


# --- headline acceptance: git clean after install -> uninstall --------------

@pytest.mark.skipif(not _has_git(), reason="git not available")
def test_git_clean_after_install_then_uninstall(tmp_path):
    _git(["init"], tmp_path)
    _git(["config", "user.email", "t@t.com"], tmp_path)  # leak-scan: ignore (test fixture, not a real address)
    _git(["config", "user.name", "t"], tmp_path)
    (tmp_path / "README.md").write_text("# project\n", encoding="utf-8")
    _git(["add", "-A"], tmp_path)
    _git(["commit", "-m", "initial"], tmp_path)

    install.main([str(tmp_path), "--merge-settings"])
    dirty = _git(["status", "--porcelain"], tmp_path).stdout
    assert dirty.strip(), "install should have added files (sanity)"

    uninstall.main([str(tmp_path), "--yes"])
    clean = _git(["status", "--porcelain"], tmp_path).stdout
    assert clean.strip() == "", f"working tree not clean after uninstall:\n{clean}"
