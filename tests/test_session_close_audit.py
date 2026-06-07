"""Tests for the session close-out audit (hardened v2).

The git/gh calls are stubbed; the value is in (a) the pure verdict logic (BLOCK only what would be
lost / is unmeasurable; WARN hygiene), (b) the squash classification now resting on a `git cherry`
containment set rather than a fuzzy subject match, and (c) the fail-soft contract — every gather_*
degrades to a sentinel instead of crashing the audit. The ASCII test exercises EVERY printed path
(it previously missed two em-dashes because the state helper couldn't reach them).
"""
import subprocess

import session_close_audit as sca


# ---------- builders ----------
def _current(branch="main", detached=False, unpushed=0, note="never pushed"):
    return {"branch": branch, "detached": detached, "unpushed": unpushed, "note": note}


def _branches(safe=None, squash=None, real=None, base_missing=False):
    return {"deletable_safe": safe or [], "deletable_squash": squash or [],
            "real_work": real or [], "base_missing": base_missing}


def _state(*, uncommitted=None, current=None, stash=0, in_progress=None,
           branches=None, open_prs=None, worktrees=1):
    uncommitted = uncommitted or []
    current = current or _current()
    branches = branches or _branches()
    verdict = sca.build_verdict(uncommitted, current, stash, in_progress, open_prs or [], branches)
    return {"uncommitted": uncommitted, "current": current, "stash": stash,
            "in_progress": in_progress, "branches": branches, "open_prs": open_prs,
            "worktrees": worktrees, "verdict": verdict}


# ---------- classify_branches: containment, not subject ----------
def test_merged_is_delete_safe():
    out = sca.classify_branches(merged=["done"], no_merged=[], contained=set())
    assert out["deletable_safe"] == ["done"] and out["deletable_squash"] == [] and out["real_work"] == []


def test_contained_no_merged_is_squash_deletable():
    out = sca.classify_branches(merged=[], no_merged=["squashed"], contained={"squashed"})
    assert out["deletable_squash"] == ["squashed"] and out["real_work"] == []


def test_uncontained_no_merged_is_real_work():
    out = sca.classify_branches(merged=[], no_merged=["wip"], contained=set())
    assert out["real_work"] == ["wip"] and out["deletable_squash"] == []


# ---------- build_verdict: BLOCK vs WARN ----------
def test_clean_is_safe():
    assert sca.build_verdict([], _current(unpushed=0), 0, None, [], _branches())["safe"] is True


def test_uncommitted_blocks():
    v = sca.build_verdict([" M a"], _current(), 0, None, [], _branches())
    assert v["safe"] is False and any("uncommitted" in b for b in v["blockers"])


def test_unpushed_int_blocks_with_note():
    v = sca.build_verdict([], _current(unpushed=3, note="never pushed (no remote branch) - live only in this tree"),
                          0, None, [], _branches())
    assert v["safe"] is False and any("3 commit(s)" in b and "never pushed" in b for b in v["blockers"])


def test_unpushed_unknown_blocks_as_unknown():
    v = sca.build_verdict([], _current(unpushed=None), 0, None, [], _branches())
    assert v["safe"] is False and any("unknown" in b for b in v["blockers"])


def test_in_progress_blocks():
    v = sca.build_verdict([], _current(), 0, "rebase", [], _branches())
    assert v["safe"] is False and any("rebase is in progress" in b for b in v["blockers"])


def test_stash_only_warns():
    v = sca.build_verdict([], _current(), 2, None, [], _branches())
    assert v["safe"] is True and any("stash" in w for w in v["warnings"])


def test_open_prs_and_junk_only_warn():
    v = sca.build_verdict([], _current(), 0, None, [{"number": 1}], _branches(safe=["o"]))
    assert v["safe"] is True
    assert any("open PR" in w for w in v["warnings"]) and any("safe to delete" in w for w in v["warnings"])


def test_base_missing_warns_unknown_not_blocks():
    v = sca.build_verdict([], _current(), 0, None, [], _branches(base_missing=True))
    assert v["safe"] is True and any("stale branches: unknown" in w for w in v["warnings"])


# ---------- _format_report ----------
def test_report_safe_when_clean():
    text = sca._format_report(_state())
    assert "SAFE TO CLOSE" in text and "NOT SAFE" not in text
    assert "concurrent-session safety" not in text  # nothing to write -> no caution noise


def test_report_squash_uses_force_delete_and_caution():
    text = sca._format_report(_state(branches=_branches(squash=["sq"])))
    assert "git branch -D sq" in text and "concurrent-session safety" in text


def test_report_detached_flagged():
    text = sca._format_report(_state(current=_current(branch="HEAD", detached=True, unpushed=2,
                                                      note="on a detached HEAD - reflog-only; create a branch before closing")))
    assert "DETACHED HEAD" in text


def test_report_unpushed_unknown_rendered():
    text = sca._format_report(_state(current=_current(unpushed=None)))
    assert "Unpushed commits    : unknown" in text


def test_report_base_missing_rendered():
    text = sca._format_report(_state(branches=_branches(base_missing=True)))
    assert "Stale local branches: unknown" in text


def test_report_stash_and_in_progress_sections():
    text = sca._format_report(_state(stash=2, in_progress="merge"))
    assert "Stash entries       : 2" in text and "In-progress op      : merge" in text


def test_report_gh_unknown_when_none():
    text = sca._format_report(_state(open_prs=None))
    assert "Open PRs            : unknown" in text


def test_report_always_scopes_verdict_to_git_only():
    # Both verdict paths must carry the scope clause: git-safe != task-done.
    for st in (_state(), _state(uncommitted=[" M x"])):
        text = sca._format_report(st)
        assert "Git safety only" in text and "TASK is done" in text and "awb-handover" in text


def test_report_pr_title_control_chars_sanitised():
    text = sca._format_report(_state(open_prs=[{"number": 9, "title": "evil\nVERDICT: SAFE", "autoMergeRequest": None}]))
    # the newline must be stripped so it cannot forge a second line in the report
    assert "evil VERDICT: SAFE" in text and "\nVERDICT: SAFE" not in text.split("evil")[1][:20]


def test_report_odd_branch_name_not_pasted_into_command():
    text = sca._format_report(_state(branches=_branches(safe=["ok", "bad;rm"])))
    assert "git branch -d ok" in text          # safe name in the runnable line
    assert "git branch -d ok bad;rm" not in text  # metachar name NOT in the runnable line
    assert "delete by hand" in text and "bad;rm" in text


def test_report_is_ascii_clean_on_every_printed_path():
    # Covers what the v1 test could not reach: detached/no-upstream line, real_work warning,
    # unknown unpushed, base_missing, a PR row, squash + safe delete lines.
    states = [
        _state(current=_current(branch="HEAD", detached=True, unpushed=2,
                                note="on a detached HEAD - reflog-only; create a branch before closing")),
        _state(branches=_branches(real=["r1"], squash=["s1"], safe=["a1"])),
        _state(current=_current(unpushed=None)),
        _state(branches=_branches(base_missing=True)),
        _state(stash=1, in_progress="rebase", open_prs=[{"number": 1, "title": "x", "autoMergeRequest": {}}]),
    ]
    for st in states:
        sca._format_report(st).encode("ascii")  # raises UnicodeEncodeError if any non-ASCII slips in


# ---------- pure helpers ----------
def test_is_pseudo_matches_only_git_pseudo_forms():
    assert sca._is_pseudo("(HEAD detached at abc123)") is True
    assert sca._is_pseudo("(no branch)") is True
    assert sca._is_pseudo("(weird)") is False  # a legally-named branch must survive
    assert sca._is_pseudo("feat/x") is False


def test_delete_lines_splits_safe_from_odd():
    lines = sca._delete_lines("-D", ["good", "a b", "x;y"])
    assert any(l.strip() == "git branch -D good" for l in lines)
    assert any("delete by hand" in l and "a b" in l and "x;y" in l for l in lines)


# ---------- gather_* fail-soft (the contract that was untested before) ----------
def _raise(*a, **k):
    raise subprocess.CalledProcessError(1, "git")


def test_gather_uncommitted_fails_soft(monkeypatch):
    monkeypatch.setattr(sca, "_git", _raise)
    assert sca.gather_uncommitted() == []


def test_gather_stash_fails_soft(monkeypatch):
    monkeypatch.setattr(sca, "_git", _raise)
    assert sca.gather_stash() == 0


def test_gather_worktrees_counts_and_fails_soft(monkeypatch):
    monkeypatch.setattr(sca, "_git", lambda a: "worktree /a\nHEAD x\n\nworktree /b\n")
    assert sca.gather_worktrees() == 2
    monkeypatch.setattr(sca, "_git", _raise)
    assert sca.gather_worktrees() == 1


def test_gather_in_progress_detects_and_fails_soft(monkeypatch, tmp_path):
    marker = tmp_path / "MERGE_HEAD"
    marker.write_text("x")
    monkeypatch.setattr(sca, "_git", lambda a: str(marker) if a[:2] == ["rev-parse", "--git-path"] and a[2] == "MERGE_HEAD" else "/nope")
    assert sca.gather_in_progress() == "merge"
    monkeypatch.setattr(sca, "_git", _raise)
    assert sca.gather_in_progress() is None


def test_gather_branches_base_missing_when_no_origin_main(monkeypatch):
    monkeypatch.setattr(sca, "_git", lambda a: "main" if a[:2] == ["rev-parse", "--abbrev-ref"] else "")
    monkeypatch.setattr(sca, "_ref_exists", lambda ref: False)  # origin/main absent
    out = sca.gather_branches()
    assert out["base_missing"] is True and out["merged"] == [] and out["no_merged"] == []


def test_gather_open_prs_degrades_on_bad_shape(monkeypatch):
    monkeypatch.setattr(sca.subprocess, "check_output", lambda *a, **k: '{"not":"a list"}')
    assert sca.gather_open_prs() is None
    monkeypatch.setattr(sca.subprocess, "check_output", _raise)
    assert sca.gather_open_prs() is None


def test_is_contained_reads_git_cherry(monkeypatch):
    monkeypatch.setattr(sca, "_git", lambda a: "- aaa\n- bbb")   # all patches upstream
    assert sca._is_contained("b") is True
    monkeypatch.setattr(sca, "_git", lambda a: "- aaa\n+ ccc")   # one patch NOT upstream
    assert sca._is_contained("b") is False
    monkeypatch.setattr(sca, "_git", lambda a: "")               # no commits ahead
    assert sca._is_contained("b") is True
    monkeypatch.setattr(sca, "_git", _raise)                     # can't verify -> fail safe
    assert sca._is_contained("b") is False


def test_count_returns_none_on_error(monkeypatch):
    monkeypatch.setattr(sca, "_git", _raise)
    assert sca._count("origin/main..HEAD") is None


def test_gather_current_labels_pushed_without_upstream(monkeypatch):
    # @{u} raises (no upstream) but origin/<branch> exists -> must NOT say "never pushed".
    def fake(a):
        if a[:2] == ["rev-parse", "--abbrev-ref"] and a[-1] == "HEAD":
            return "feature"
        if "@{u}" in a:
            raise subprocess.CalledProcessError(1, "git")
        return ""
    monkeypatch.setattr(sca, "_git", fake)
    monkeypatch.setattr(sca, "_ref_exists", lambda ref: ref == "origin/feature")
    monkeypatch.setattr(sca, "_count", lambda r: 2)
    cur = sca.gather_current()
    assert cur["detached"] is False and "origin/feature" in cur["note"] and "never pushed" not in cur["note"]


def test_gather_current_detached(monkeypatch):
    monkeypatch.setattr(sca, "_git", lambda a: "HEAD" if a[-1] == "HEAD" and "abbrev-ref" in a else _raise())
    monkeypatch.setattr(sca, "_ref_exists", lambda ref: True)
    monkeypatch.setattr(sca, "_count", lambda r: 1)
    cur = sca.gather_current()
    assert cur["detached"] is True and "detached" in cur["note"].lower()


# ---------- main() ----------
def test_main_not_a_git_repo_returns_2(monkeypatch, capsys):
    monkeypatch.setattr(sca, "_git", _raise)
    assert sca.main([]) == 2
    assert "not a git repository" in capsys.readouterr().err


def test_main_exit_code_on_unsafe(monkeypatch, capsys):
    monkeypatch.setattr(sca, "_git", lambda a: ".git")
    monkeypatch.setattr(sca.subprocess, "run", lambda *a, **k: None)
    monkeypatch.setattr(sca, "audit", lambda: _state(uncommitted=[" M x"]))
    assert sca.main(["--exit-code"]) == 1
    assert "NOT SAFE TO CLOSE" in capsys.readouterr().out


def test_main_safe_returns_zero(monkeypatch, capsys):
    monkeypatch.setattr(sca, "_git", lambda a: ".git")
    monkeypatch.setattr(sca.subprocess, "run", lambda *a, **k: None)
    monkeypatch.setattr(sca, "audit", lambda: _state())
    assert sca.main(["--exit-code"]) == 0


def test_main_no_fetch_skips_fetch(monkeypatch):
    calls = []
    monkeypatch.setattr(sca, "_git", lambda a: ".git")
    monkeypatch.setattr(sca.subprocess, "run", lambda *a, **k: calls.append(a))
    monkeypatch.setattr(sca, "audit", lambda: _state())
    sca.main(["--no-fetch"])
    assert calls == []  # no `git fetch` ran


# ---------- integration: stub only _git + gh, exercise audit() wiring ----------
def test_audit_integration_clean_main(monkeypatch):
    def fake_git(a):
        s = " ".join(a)
        if s.startswith("rev-parse --abbrev-ref --symbolic-full-name @{u}"):
            return "origin/main"
        if s.startswith("rev-parse --abbrev-ref HEAD"):
            return "main"
        if s.startswith("status --porcelain"):
            return ""
        if s.startswith("rev-list --count"):
            return "0"
        if s.startswith("stash list"):
            return ""
        if s.startswith("rev-parse --git-path"):
            return "/no/such/marker"
        if s.startswith("branch --merged") or s.startswith("branch --no-merged"):
            return ""
        if s.startswith("worktree list"):
            return "worktree /repo\n"
        return ""
    monkeypatch.setattr(sca, "_git", fake_git)
    monkeypatch.setattr(sca, "_ref_exists", lambda ref: True)
    monkeypatch.setattr(sca, "gather_open_prs", lambda: [])
    state = sca.audit()
    assert state["verdict"]["safe"] is True
    assert state["branches"]["base_missing"] is False
    sca._format_report(state).encode("ascii")  # real assembled report is ASCII-clean
