"""Tests for the session close-out audit.

The git/gh calls are stubbed; the value is in the pure logic — does it (a) tell work that would be
LOST on close (uncommitted / unpushed) from already-on-server hygiene, and (b) recognise a
squash-merged branch (whose subject is in main but tip is not an ancestor) as safe to delete rather
than as real unmerged work?
"""
import session_close_audit as sca


# ----- classify_branches: the squash-merge trap -----
def test_merged_branch_is_delete_safe():
    out = sca.classify_branches(
        merged=["feat/done"], no_merged=[], remote_gone=set(),
        main_subjects=set(), branch_subject={},
    )
    assert out["deletable_safe"] == ["feat/done"]
    assert out["deletable_squash"] == [] and out["real_work"] == []


def test_squash_merged_branch_is_deletable_not_real_work():
    # Subject is in main (with the PR-number suffix squash appends) AND the remote is gone.
    out = sca.classify_branches(
        merged=[], no_merged=["docs/onboarding"], remote_gone={"docs/onboarding"},
        main_subjects={"docs: smooth onboarding (#101)"},
        branch_subject={"docs/onboarding": "docs: smooth onboarding"},
    )
    assert out["deletable_squash"] == ["docs/onboarding"]
    assert out["real_work"] == []


def test_unmerged_with_live_remote_is_real_work():
    # Same subject match, but the remote branch still exists -> may be in flight, treat as real work.
    out = sca.classify_branches(
        merged=[], no_merged=["feat/wip"], remote_gone=set(),
        main_subjects={"feat: wip (#9)"}, branch_subject={"feat/wip": "feat: wip"},
    )
    assert out["real_work"] == ["feat/wip"] and out["deletable_squash"] == []


def test_unmerged_subject_not_in_main_is_real_work():
    out = sca.classify_branches(
        merged=[], no_merged=["feat/new"], remote_gone={"feat/new"},
        main_subjects={"something else"}, branch_subject={"feat/new": "feat: brand new work"},
    )
    assert out["real_work"] == ["feat/new"] and out["deletable_squash"] == []


# ----- build_verdict: BLOCK only what would be LOST -----
def test_clean_tree_is_safe():
    branches = {"deletable_safe": [], "deletable_squash": [], "real_work": []}
    v = sca.build_verdict(uncommitted=[], unpushed=0, tracked=True, open_prs=[], branches=branches)
    assert v["safe"] is True and v["blockers"] == []


def test_uncommitted_blocks():
    branches = {"deletable_safe": [], "deletable_squash": [], "real_work": []}
    v = sca.build_verdict(uncommitted=[" M a.py"], unpushed=0, tracked=True, open_prs=[], branches=branches)
    assert v["safe"] is False and any("uncommitted" in b for b in v["blockers"])


def test_unpushed_blocks_and_notes_missing_upstream():
    branches = {"deletable_safe": [], "deletable_squash": [], "real_work": []}
    v = sca.build_verdict(uncommitted=[], unpushed=3, tracked=False, open_prs=[], branches=branches)
    assert v["safe"] is False
    assert any("not on any remote" in b and "no upstream" in b for b in v["blockers"])


def test_open_prs_and_junk_branches_only_warn():
    branches = {"deletable_safe": ["old1"], "deletable_squash": ["old2"], "real_work": []}
    v = sca.build_verdict(
        uncommitted=[], unpushed=0, tracked=True,
        open_prs=[{"number": 5, "title": "x"}], branches=branches,
    )
    assert v["safe"] is True  # already on the server -> not a blocker
    assert any("open PR" in w for w in v["warnings"])
    assert any("safe to delete" in w for w in v["warnings"])


# ----- _format_report + main -----
def _state(*, safe=True, unpushed=0, prs=None, squash=None, worktrees=1):
    branches = {"deletable_safe": [], "deletable_squash": squash or [], "real_work": []}
    verdict = sca.build_verdict([" M x"] if not safe else [], unpushed, True, prs or [], branches)
    return {
        "uncommitted": [" M x"] if not safe else [],
        "current": {"branch": "main", "upstream": "origin/main", "tracked": True, "unpushed": unpushed},
        "branches": branches,
        "open_prs": prs,
        "worktrees": worktrees,
        "verdict": verdict,
    }


def test_report_says_safe_when_clean():
    text = sca._format_report(_state(safe=True))
    assert "SAFE TO CLOSE" in text and "NOT SAFE" not in text


def test_report_flags_squash_branch_with_force_delete_command():
    text = sca._format_report(_state(safe=True, squash=["docs/onboarding"]))
    assert "git branch -D docs/onboarding" in text


def test_report_handles_unknown_prs_when_gh_missing():
    text = sca._format_report(_state(safe=True, prs=None))
    assert "Open PRs            : unknown" in text


# ----- concurrent-session caution (shown only when there is a write to suggest) -----
def test_no_concurrency_caution_when_clean_and_nothing_to_do():
    # Safe + no stale branches -> nothing to clean or ship -> no caution noise.
    text = sca._format_report(_state(safe=True))
    assert "concurrent-session safety" not in text


def test_concurrency_caution_shown_when_branches_to_delete():
    text = sca._format_report(_state(safe=True, squash=["docs/onboarding"]))
    assert "concurrent-session safety" in text
    assert "git branch --show-current" in text


def test_concurrency_caution_shown_when_unsafe_needs_ship():
    text = sca._format_report(_state(safe=False, unpushed=1))
    assert "concurrent-session safety" in text


def test_report_is_ascii_clean_on_windows_consoles():
    # The report prints to cp1252 consoles; a stray em-dash mojibakes. Cover both verdict paths
    # and the branch lines so no printed string carries a non-ASCII char.
    for st in (_state(safe=True, squash=["docs/onboarding"]),
               _state(safe=False, unpushed=2, prs=[{"number": 1, "title": "x"}])):
        sca._format_report(st).encode("ascii")  # raises UnicodeEncodeError if any non-ASCII slips in


def test_concurrency_caution_flags_extra_worktrees():
    text = sca._format_report(_state(safe=False, unpushed=1, worktrees=2))
    assert "Worktrees sharing this .git: 2" in text
    assert "refs/config still SHARED" in text


def test_gather_worktrees_counts_porcelain(monkeypatch):
    monkeypatch.setattr(sca, "_git",
                        lambda args: "worktree /a\nHEAD abc\nbranch refs/heads/main\n\nworktree /b\nHEAD def\n")
    assert sca.gather_worktrees() == 2


def test_gather_worktrees_fails_soft_to_one(monkeypatch):
    def _boom(args):
        raise sca.subprocess.CalledProcessError(1, "git")
    monkeypatch.setattr(sca, "_git", _boom)
    assert sca.gather_worktrees() == 1


def test_main_reports_and_exit_code_on_unsafe(monkeypatch, capsys):
    monkeypatch.setattr(sca, "_git", lambda args: ".git" if args[:2] == ["rev-parse", "--git-dir"] else "")
    monkeypatch.setattr(sca.subprocess, "run", lambda *a, **k: None)
    monkeypatch.setattr(sca, "audit", lambda: _state(safe=False, unpushed=2))
    rc = sca.main(["--exit-code"])
    out = capsys.readouterr().out
    assert "NOT SAFE TO CLOSE" in out
    assert rc == 1


def test_main_safe_returns_zero(monkeypatch, capsys):
    monkeypatch.setattr(sca, "_git", lambda args: ".git" if args[:2] == ["rev-parse", "--git-dir"] else "")
    monkeypatch.setattr(sca.subprocess, "run", lambda *a, **k: None)
    monkeypatch.setattr(sca, "audit", lambda: _state(safe=True))
    assert sca.main(["--exit-code"]) == 0
    assert "SAFE TO CLOSE" in capsys.readouterr().out


def test_main_not_a_git_repo_returns_2(monkeypatch, capsys):
    def _boom(args):
        raise sca.subprocess.CalledProcessError(128, "git")
    monkeypatch.setattr(sca, "_git", _boom)
    assert sca.main([]) == 2
    assert "not a git repository" in capsys.readouterr().err
