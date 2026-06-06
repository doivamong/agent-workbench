#!/usr/bin/env python3
"""Demo: the auto-merge silent-fail surfacer (tools/automerge_status.py).

Runs the pure classifier on three synthetic PRs — a healthy queued one, a STUCK one
(auto-merge on but a check failed → never merges), and a plain open one — so you can see
how the reporter distinguishes "waiting" from "silently stuck" without needing live GitHub
state. Stdlib-only.

    python examples/automerge_status_demo.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import automerge_status as ams  # noqa: E402

PRS = [
    {"number": 1, "title": "queued, checks pending", "url": "https://github.com/o/r/pull/1",
     "headRefName": "feat/a", "autoMergeRequest": {"mergeMethod": "SQUASH"},
     "statusCheckRollup": [{"name": "test", "status": "IN_PROGRESS", "conclusion": None}]},
    {"number": 2, "title": "queued but a check failed", "url": "https://github.com/o/r/pull/2",
     "headRefName": "feat/b", "autoMergeRequest": {"mergeMethod": "SQUASH"},
     "statusCheckRollup": [{"name": "ui-web", "conclusion": "FAILURE"}]},
    {"number": 3, "title": "plain open PR", "url": "https://github.com/o/r/pull/3",
     "headRefName": "feat/c", "autoMergeRequest": None, "statusCheckRollup": []},
]


def main() -> int:
    stuck = 0
    for pr in PRS:
        status = ams.classify(pr)
        stuck += status["state"] == "STUCK"
        print(ams._format(pr, status))
        print()
    expected_stuck = 1  # only PR #2
    ok = stuck == expected_stuck
    print(f"Detected {stuck} stuck PR(s) (expected {expected_stuck}).")
    print("Classifier behaves as expected." if ok else "UNEXPECTED classification.")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
