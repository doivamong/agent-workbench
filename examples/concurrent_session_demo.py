#!/usr/bin/env python3
"""Runnable demo for .claude/hooks/scripts/concurrent_session_guard.py.

Drives the guard's decision core (lib/session_lock.py) against synthetic locks and prints
whether each would warn a newly-starting session. This is the logic a SessionStart hook uses
to NOTICE a second agent/Claude session attaching to one checkout (which races the shared git
index/HEAD). It is a seatbelt — it warns, it cannot block. Stdlib only.

    python examples/concurrent_session_demo.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / ".claude" / "hooks" / "lib"))

from session_lock import assess, read_lock, release_lock, write_lock  # noqa: E402

NOW = "2026-06-06T12:00:00+00:00"
MY_PID, MY_SID = 100, "this-session"

# (label, existing-lock-or-None, is-the-other-pid-alive?, expect_warning)
SCENARIOS = [
    ("fresh checkout (no lock)", None, False, False),
    ("another LIVE session here", {"pid": 999, "started_at": NOW, "session_id": "other"}, True, True),
    ("stale lock (dead pid)", {"pid": 999, "started_at": NOW, "session_id": "old"}, False, False),
    ("our own session re-firing", {"pid": 999, "started_at": NOW, "session_id": MY_SID}, True, False),
    ("malformed pid in lock", {"pid": "?!", "started_at": NOW, "session_id": "other"}, True, False),
]


def main() -> int:
    print(f"{'WARN?':<6} {'EXPECT':<7} SCENARIO")
    print("-" * 60)
    ok = True
    for label, existing, alive, expect in SCENARIOS:
        warning, _new = assess(existing, MY_PID, MY_SID, NOW, alive_fn=lambda _p, a=alive: a)
        warned = warning is not None
        mark = "OK" if warned == expect else "MISMATCH"
        if warned != expect:
            ok = False
        print(f"{str(warned):<6} {str(expect):<7} {label}  [{mark}]")

    # Show the round-trip the real hooks use: write our lock, then SessionEnd releases it.
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        lock = Path(d) / "session_lock.json"
        write_lock(lock, {"pid": MY_PID, "started_at": NOW, "session_id": MY_SID})
        print(f"\nwrote lock     -> {read_lock(lock)}")
        removed = release_lock(lock, MY_PID, MY_SID)
        print(f"released (ours) -> removed={removed}, exists={lock.exists()}")

    print("\nAll scenarios behaved as expected." if ok else "\nSome scenarios were wrong!")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
