#!/usr/bin/env python3
"""SessionStart hook — WARN when a second session attaches to a busy working tree.

CLAUDE.md says "one session per working tree", but the rule is documented, not enforced:
two agent/Claude sessions on one checkout race the shared git index/HEAD, and a commit hook in
a linked worktree can leak GIT_DIR and flip core.bare / overwrite user.* in the SHARED
.git/config. This hook is the seatbelt that *notices* the violation.

On start it writes/refreshes a per-worktree lock (`.claude/.logs/session_lock.json`, gitignored)
recording {pid, started_at, session_id}. The recorded pid is the guard's PARENT process — the
agent/CLI that spawned this hook, which lives for the session — NOT this short-lived hook's own
pid. Before refreshing, it reads any existing lock: if that lock names a DIFFERENT session whose
pid is STILL ALIVE, it injects a warning into the session. A stale lock (dead pid) is silently
reclaimed. `session_end.py` removes the lock on teardown.

HONEST LIMIT — a SEATBELT, not a lock: it cannot PREVENT a second session, only warn after one
has attached, and it fails toward silence (a missed warning), never a false alarm. The full
limits live in lib/session_lock.py. Advisory only: it NEVER blocks, NEVER exits non-zero.

Kill switch:
- SESSION_LOCK_GUARD=0   — disable (write nothing, warn nothing)

Protocol: stdin JSON (cwd?, session_id?) -> stdout JSON (hookSpecificOutput.additionalContext)
-> exit 0. Fail-open via hook_logger: any crash logs + exits clean, never a broken session.
"""
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))
from stdio_utf8 import ensure_utf8_io  # noqa: E402
from session_lock import assess, lock_path, read_lock, write_lock  # noqa: E402
from hook_logger import hook_main  # noqa: E402

# UTF-8, pythonw-safe stdout/stdin before any output (shared lib/stdio_utf8.py).
ensure_utf8_io()


@hook_main("concurrent-session-guard")
def main() -> None:
    if os.environ.get("SESSION_LOCK_GUARD", "1") == "0":
        print(json.dumps({}))
        sys.exit(0)

    try:
        event = json.load(sys.stdin)
    except Exception:
        event = {}
    cwd = event.get("cwd") or os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    session_id = event.get("session_id") or ""

    # The long-lived process is the one that SPAWNED this hook (the agent/CLI), not this hook.
    my_pid = os.getppid()
    now_iso = datetime.now(timezone.utc).isoformat(timespec="seconds")

    path = lock_path(cwd)
    warning, new_lock = assess(read_lock(path), my_pid, session_id, now_iso)
    try:
        write_lock(path, new_lock)
    except Exception:
        pass  # refreshing the lock is best-effort; never disrupt session start

    output: dict = {}
    if warning:
        output = {"hookSpecificOutput": {"hookEventName": "SessionStart",
                                         "additionalContext": warning}}
    print(json.dumps(output, ensure_ascii=False))
    sys.exit(0)


if __name__ == "__main__":
    main()
