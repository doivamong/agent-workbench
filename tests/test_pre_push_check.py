"""Tests for the read-only pre-push 4-point check.

Uses real throwaway git repos (conftest's _isolate_git_env keeps each child git scoped to its
own cwd, so this is safe). The leak scan is the one heavy check, so it is stubbed except for a
single real-clean integration test. Fake paths use Z:/code/proj_x (never a real home path).
"""
import subprocess
import sys
from pathlib import Path

import pytest

import pre_push_check as ppc

_REMOTE = "https://github.com/example/agent-workbench"


def _git(repo, *args):
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True)


@pytest.fixture
def repo(tmp_path):
    r = tmp_path / "repo"
    r.mkdir()
    _git(r, "init", "-b", "main")
    _git(r, "config", "user.email", "t@example.com")
    _git(r, "config", "user.name", "t")
    _git(r, "remote", "add", "origin", _REMOTE)
    (r / "a.py").write_text("x = 1\n", encoding="utf-8")
    _git(r, "add", "a.py")
    _git(r, "commit", "-m", "base")
    return r


def _feature(repo, *, path="b.py", body="y = 2\n"):
    _git(repo, "checkout", "-b", "feature")
    f = repo / path
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(body, encoding="utf-8")
    _git(repo, "add", path)
    _git(repo, "commit", "-m", "feature change")


# --- point 1: remote ------------------------------------------------------------------

def test_remote_ok(repo):
    ok, _ = ppc.check_remote(repo, "origin", None)
    assert ok


def test_remote_substr_mismatch_fails(repo):
    ok, msg = ppc.check_remote(repo, "origin", "Z:/code/proj_x")
    assert not ok and "does not contain" in msg


def test_remote_missing_fails_closed(repo):
    # A non-existent remote makes git error -> CheckError (fail closed), not a silent pass.
    with pytest.raises(ppc.CheckError):
        ppc.check_remote(repo, "nope", None)


# --- point 2: commits -----------------------------------------------------------------

def test_commits_ok_on_feature(repo):
    _feature(repo)
    ok, msg = ppc.check_commits(repo, "main")
    assert ok and "1 commit" in msg


def test_commits_on_main_fails(repo):
    ok, msg = ppc.check_commits(repo, "main")
    assert not ok and "main" in msg


def test_commits_none_ahead_fails(repo):
    _git(repo, "checkout", "-b", "feature")  # no new commit
    ok, msg = ppc.check_commits(repo, "main")
    assert not ok and "nothing to push" in msg


# --- point 3: gate (leak scan) --------------------------------------------------------

def test_gate_fails_when_leak_scan_reds(repo, monkeypatch):
    monkeypatch.setattr(ppc, "_run_leak_scan", lambda r: (1, "found a secret"))
    ok, msg = ppc.check_gate(repo)
    assert not ok and "FAILED" in msg


def test_gate_passes_on_clean_repo_real_scan(repo):
    # Integration: the real leak scanner on a clean repo exits 0.
    _feature(repo)
    ok, _ = ppc.check_gate(repo)
    assert ok


# --- point 4: outgoing clean ----------------------------------------------------------

def test_outgoing_clean_ok(repo):
    _feature(repo)
    ok, _ = ppc.check_outgoing_clean(repo, "main")
    assert ok


def test_outgoing_private_path_fails(repo):
    _feature(repo, path="handovers/secret.md", body="private\n")
    ok, msg = ppc.check_outgoing_clean(repo, "main")
    assert not ok and "handovers/secret.md" in msg


# --- main: exit codes -----------------------------------------------------------------

def test_main_all_pass_returns_zero(repo, monkeypatch):
    _feature(repo)
    monkeypatch.setattr(ppc, "_run_leak_scan", lambda r: (0, "clean"))
    rc = ppc.main(["--repo", str(repo), "--base", "main"])
    assert rc == 0


def test_main_reports_fail_returns_one(repo, monkeypatch):
    # On main with nothing ahead -> the commits point fails -> exit 1 (not 0, not a crash).
    monkeypatch.setattr(ppc, "_run_leak_scan", lambda r: (0, "clean"))
    rc = ppc.main(["--repo", str(repo), "--base", "main"])
    assert rc == 1


def test_main_internal_error_fails_closed(tmp_path):
    # Pointing at a non-repo dir makes git error -> fail CLOSED with a non-zero, non-1 code.
    not_a_repo = tmp_path / "Z_code_proj_x"
    not_a_repo.mkdir()
    rc = ppc.main(["--repo", str(not_a_repo), "--base", "main"])
    assert rc == 2
