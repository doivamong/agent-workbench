#!/usr/bin/env python3
"""Surface auto-merge PRs that are silently stuck (stdlib + the `gh` CLI, read-only).

The silent failure this guards (blocker B5): you enqueue a PR with `gh pr merge --auto`, walk
away trusting GitHub to merge it when green — but if a *late* required check goes red, the PR
just sits open, un-merged, with nobody watching. This reporter makes that state loud.

Run it after enqueuing an auto-merge, and again on your next ship, to answer one question in
plain language: "is any queued PR stuck, and why?" It mutates nothing — it only reads `gh`.

  python tools/automerge_status.py            # report all open PRs
  python tools/automerge_status.py --exit-code # also exit 1 if any queued PR is STUCK

A PR is **STUCK** when auto-merge is enabled but a required check has FAILED: GitHub will
never merge it, so it needs a human/agent. A PR that is merely waiting on pending checks is
**queued** (normal), not stuck.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys

# gh check-run conclusions that mean "this will not turn green on its own".
_FAILED = {"FAILURE", "CANCELLED", "TIMED_OUT", "ACTION_REQUIRED", "STARTUP_FAILURE", "STALE"}

_FIELDS = "number,title,url,headRefName,mergeStateStatus,autoMergeRequest,statusCheckRollup"


def _fetch_open_prs() -> list[dict]:
    """Return open PRs as gh JSON dicts. Isolated so tests can stub it."""
    out = subprocess.check_output(
        ["gh", "pr", "list", "--state", "open", "--json", _FIELDS],
        encoding="utf-8",
    )
    return json.loads(out)


def _failed_checks(pr: dict) -> list[str]:
    """Names of checks on the PR whose conclusion is a hard failure."""
    failed = []
    for c in pr.get("statusCheckRollup") or []:
        # gh normalises check-runs (status/conclusion) and statuses (state) differently.
        verdict = (c.get("conclusion") or c.get("state") or "").upper()
        if verdict in _FAILED:
            failed.append(c.get("name") or c.get("context") or "<unnamed check>")
    return failed


def classify(pr: dict) -> dict:
    """Pure: turn a gh PR dict into a status verdict. No I/O — unit-testable."""
    queued = pr.get("autoMergeRequest") is not None
    failed = _failed_checks(pr)
    if queued and failed:
        state, reason = "STUCK", f"auto-merge is on but {len(failed)} check(s) failed: {', '.join(failed)}"
    elif queued:
        state, reason = "queued", "auto-merge on; waiting for required checks to pass"
    elif failed:
        state, reason = "failing", f"{len(failed)} check(s) failed (no auto-merge set): {', '.join(failed)}"
    else:
        state, reason = "open", "open; no auto-merge enabled"
    return {"state": state, "reason": reason, "failed_checks": failed}


def _format(pr: dict, status: dict) -> str:
    num, headref = pr.get("number"), pr.get("headRefName", "?")
    lines = [
        f"PR #{num} [{status['state']}] {pr.get('title', '')}".rstrip(),
        f"    {status['reason']}",
        f"    {pr.get('url', '')}",
        f"    recheck: gh pr checks {num}    |    gh run list --branch {headref}",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--exit-code", action="store_true",
                        help="exit 1 if any queued PR is STUCK (for use as an alert/CI signal)")
    args = parser.parse_args(argv)

    try:
        prs = _fetch_open_prs()
    except FileNotFoundError:
        sys.stderr.write("automerge_status: the `gh` CLI is not installed — cannot read PR state.\n")
        return 2
    except subprocess.CalledProcessError as exc:
        sys.stderr.write(f"automerge_status: `gh pr list` failed ({exc}).\n")
        return 2

    if not prs:
        print("No open PRs.")
        return 0

    stuck = 0
    for pr in prs:
        status = classify(pr)
        if status["state"] == "STUCK":
            stuck += 1
        print(_format(pr, status))
        print()

    if stuck:
        print(f"WARNING: {stuck} queued PR(s) STUCK — auto-merge will not complete until the "
              "failed check(s) are fixed. They are open right now, not merged.")
    return 1 if (args.exit_code and stuck) else 0


if __name__ == "__main__":
    sys.exit(main())
