"""Tests for the auto-merge silent-fail surfacer (B5).

The gh call is stubbed; the value is in the pure classification — does it tell a STUCK PR
(auto-merge on + a failed check, which never merges) apart from a normal queued PR (waiting
on pending checks)?
"""
import automerge_status as ams


def _pr(*, number=1, auto=False, checks=None):
    return {
        "number": number,
        "title": "x",
        "url": f"https://github.com/o/r/pull/{number}",
        "headRefName": "feat/x",
        "mergeStateStatus": "BLOCKED",
        "autoMergeRequest": {"mergeMethod": "SQUASH"} if auto else None,
        "statusCheckRollup": checks or [],
    }


def test_queued_with_failed_check_is_stuck():
    pr = _pr(auto=True, checks=[{"name": "ui-web", "conclusion": "FAILURE"}])
    status = ams.classify(pr)
    assert status["state"] == "STUCK"
    assert "ui-web" in status["reason"]


def test_queued_with_only_pending_is_not_stuck():
    pr = _pr(auto=True, checks=[{"name": "test", "status": "IN_PROGRESS", "conclusion": None}])
    assert ams.classify(pr)["state"] == "queued"


def test_failing_without_automerge_is_failing_not_stuck():
    pr = _pr(auto=False, checks=[{"name": "lint", "conclusion": "FAILURE"}])
    assert ams.classify(pr)["state"] == "failing"


def test_clean_open_pr():
    pr = _pr(auto=False, checks=[{"name": "lint", "conclusion": "SUCCESS"}])
    assert ams.classify(pr)["state"] == "open"


def test_status_state_field_is_honoured():
    # Legacy "status" contexts use {context, state} rather than {name, conclusion}.
    pr = _pr(auto=True, checks=[{"context": "legacy-ci", "state": "FAILURE"}])
    status = ams.classify(pr)
    assert status["state"] == "STUCK" and "legacy-ci" in status["reason"]


def test_format_includes_recheck_command():
    pr = _pr(number=42)
    text = ams._format(pr, ams.classify(pr))
    assert "gh pr checks 42" in text and "gh run list --branch feat/x" in text


def test_main_reports_and_exit_code_on_stuck(monkeypatch, capsys):
    monkeypatch.setattr(ams, "_fetch_open_prs",
                        lambda: [_pr(number=7, auto=True, checks=[{"name": "ui-web", "conclusion": "FAILURE"}])])
    rc = ams.main(["--exit-code"])
    out = capsys.readouterr().out
    assert "STUCK" in out and "#7" in out
    assert rc == 1  # --exit-code + a stuck PR -> non-zero alert


def test_main_no_exit_code_stays_zero_even_when_stuck(monkeypatch, capsys):
    monkeypatch.setattr(ams, "_fetch_open_prs",
                        lambda: [_pr(auto=True, checks=[{"name": "ui-web", "conclusion": "FAILURE"}])])
    assert ams.main([]) == 0  # reporting only, without --exit-code


def test_main_handles_no_open_prs(monkeypatch, capsys):
    monkeypatch.setattr(ams, "_fetch_open_prs", lambda: [])
    assert ams.main([]) == 0
    assert "No open PRs" in capsys.readouterr().out
