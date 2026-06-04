"""Tests for ops/tree_snapshot.py — stdlib only. Uses a temp dir (and a temp git
repo where git is available) so nothing touches the real working tree."""
import json
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import ops.tree_snapshot as ts  # noqa: E402

HAS_GIT = shutil.which("git") is not None


@pytest.fixture
def repo(tmp_path):
    (tmp_path / "a.txt").write_text("alpha", encoding="utf-8")
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "b.txt").write_text("bravo", encoding="utf-8")
    return tmp_path


def test_repo_files_walk_fallback_excludes_noise(repo):
    cache = repo / "__pycache__"
    cache.mkdir()
    (cache / "x.pyc").write_text("junk", encoding="utf-8")
    files, used_git = ts.repo_files(repo)
    assert "a.txt" in files and "sub/b.txt" in files
    assert not any("__pycache__" in f for f in files)
    assert used_git is False  # plain temp dir → fallback


@pytest.mark.skipif(not HAS_GIT, reason="git not available")
def test_repo_files_respects_gitignore(repo):
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True, capture_output=True)
    (repo / ".gitignore").write_text("*.log\n", encoding="utf-8")
    (repo / "ignored.log").write_text("secret", encoding="utf-8")
    files, used_git = ts.repo_files(repo)
    assert used_git is True
    assert "ignored.log" not in files
    assert "a.txt" in files and ".gitignore" in files


def test_snapshot_creates_zip_with_manifest(repo, tmp_path):
    snaps = tmp_path / "snaps"
    z = ts.snapshot(repo, label="t1", snap_dir=snaps)
    assert z.exists() and z.suffix == ".zip" and "t1" in z.name
    with zipfile.ZipFile(z) as zf:
        names = zf.namelist()
        assert "a.txt" in names and ts.MANIFEST_NAME in names
        man = json.loads(zf.read(ts.MANIFEST_NAME))
        assert "a.txt" in man["files"]


def test_plan_and_apply_restore_roundtrip(repo, tmp_path):
    snaps = tmp_path / "snaps"
    z = ts.snapshot(repo, snap_dir=snaps)
    (repo / "a.txt").write_text("CHANGED", encoding="utf-8")  # diverge from snapshot
    plan = ts.plan_restore(z, repo)
    assert "a.txt" in plan["will_modify"]

    stale = ts.apply_restore(z, "deadbeef", repo, auto_backup=False, snap_dir=snaps)
    assert stale["result"] == "aborted-stale"  # wrong hash refused (TOCTOU guard)

    res = ts.apply_restore(z, plan["plan_hash"], repo, auto_backup=True, snap_dir=snaps)
    assert res["result"] == "restored"
    assert (repo / "a.txt").read_text(encoding="utf-8") == "alpha"  # content back
    assert res["backup"] is not None  # auto-backup of the pre-restore tree taken


def test_zip_slip_member_rejected(repo, tmp_path):
    evil = tmp_path / "evil.zip"
    with zipfile.ZipFile(evil, "w") as zf:
        zf.writestr("../escape.txt", "pwned")
    with pytest.raises(ValueError):
        ts.plan_restore(evil, repo)


def test_list_snapshots(repo, tmp_path):
    snaps = tmp_path / "snaps"
    ts.snapshot(repo, label="one", snap_dir=snaps)
    listed = ts.list_snapshots(snaps)
    assert len(listed) == 1 and listed[0]["name"].endswith(".zip")
