#!/usr/bin/env python3
"""SessionEnd hook — drop a one-line breadcrumb of where this session left off.

When a session ends, record the git branch, the last commit, how many files were uncommitted,
and the time, to a small project-local file. The next session's SessionStart hook
(session_start.py) reads it and injects a "Last session: ..." line, so you reopen with a little
orientation instead of a blank slate. This is the lightweight, automatic complement to a
hand-written HANDOVER (see docs/session-preservation.md) — a breadcrumb, not a replay.

Kill switches (environment variables):
- SESSION_BREADCRUMB=0         — disable (write nothing)
- SESSION_BREADCRUMB_PATH=<p>  — relocate the breadcrumb file (used by tests)

Protocol: stdin JSON (cwd?, reason?) -> stdout empty -> exit 0. Side-effect only; never blocks.
"""
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))
from stdio_utf8 import ensure_utf8_io  # noqa: E402
from session_breadcrumb import breadcrumb_path, write_breadcrumb  # noqa: E402
from session_lock import lock_path, release_lock  # noqa: E402
from hook_logger import hook_main  # noqa: E402

# UTF-8, pythonw-safe stdout/stdin before any output (shared lib/stdio_utf8.py).
ensure_utf8_io()


def _git(args: "list[str]", cwd: str) -> str:
    try:
        r = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, timeout=5)
        return r.stdout.strip() if r.returncode == 0 else ""
    except Exception:
        return ""


def collect_state(cwd: str) -> dict:
    """The breadcrumb payload: git branch, last commit, uncommitted count, end time."""
    status = _git(["status", "--porcelain"], cwd)
    return {
        "ended_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "branch": _git(["branch", "--show-current"], cwd),
        "commit": _git(["log", "--oneline", "-1"], cwd),
        "uncommitted": len([ln for ln in status.splitlines() if ln.strip()]),
    }


@hook_main("session-end")
def main() -> None:
    if os.environ.get("SESSION_BREADCRUMB", "1") == "0":
        sys.exit(0)
    try:
        event = json.load(sys.stdin)
    except Exception:
        event = {}
    cwd = event.get("cwd") or os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    try:
        write_breadcrumb(breadcrumb_path(cwd), collect_state(cwd))
    except Exception:
        pass  # the breadcrumb is best-effort; never disrupt session teardown
    # Release this session's concurrent-session lock (concurrent_session_guard.py). Only removes
    # the lock if it is ours; another live session's lock is left intact. Best-effort.
    release_lock(lock_path(cwd), os.getppid(), event.get("session_id") or "")


if __name__ == "__main__":
    main()
