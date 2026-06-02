#!/usr/bin/env python3
"""SessionStart[compact] hook — re-inject a handover excerpt right after a compaction.

Layer 2 of the session-preservation design (see docs/session-preservation.md). When a
session restarts after auto-compact or /compact, this reads the `.last_compact` signal
that precompact_backup.py wrote; if it is recent, it injects the top of the newest
HANDOVER_*.md back into context so the agent resumes with the goal/decisions/next-steps
instead of a blank slate.

Kill switch:
- COMPACT_RESTORE=0   — disable (never inject)

Protocol: stdin JSON (cwd) -> stdout JSON (hookSpecificOutput.additionalContext) -> exit 0.
"""
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stdin, "reconfigure"):
    sys.stdin.reconfigure(encoding="utf-8")

sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))
from hook_logger import hook_main  # noqa: E402

MAX_EXCERPT_LINES = 50
SIGNAL_MAX_AGE = 300  # seconds — only inject if the compaction was very recent


def _signal_age_seconds(signal: dict, now: datetime) -> float:
    """Seconds since the signal timestamp; a huge number if it is missing/unparseable."""
    try:
        ts = datetime.fromisoformat(signal["timestamp"]).replace(tzinfo=timezone.utc)
        return (now - ts).total_seconds()
    except Exception:
        return SIGNAL_MAX_AGE + 1


def build_recovery_context(handovers_dir: Path, now: datetime,
                           max_age: int = SIGNAL_MAX_AGE,
                           max_lines: int = MAX_EXCERPT_LINES) -> str | None:
    """Return the post-compact context to inject, or None if nothing recent applies.

    Pure-ish (filesystem in, string out) so it is unit-testable without stdin.
    """
    signal_file = handovers_dir / ".last_compact"
    if not signal_file.exists():
        return None
    try:
        signal = json.loads(signal_file.read_text(encoding="utf-8"))
    except Exception:
        return None
    if _signal_age_seconds(signal, now) > max_age:
        return None
    handovers = sorted(handovers_dir.glob("HANDOVER_*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not handovers:
        return None
    try:
        excerpt = "\n".join(handovers[0].read_text(encoding="utf-8").splitlines()[:max_lines])
    except Exception:
        return None
    return (
        "[POST-COMPACT RECOVERY] The session was just compacted. Handover from before "
        f"compaction:\n\n{excerpt}\n\nRead the full handover at {handovers[0]} to restore "
        "complete context."
    )


@hook_main("compact-restore")
def main() -> None:
    if os.environ.get("COMPACT_RESTORE", "1") == "0":
        print(json.dumps({}))
        sys.exit(0)

    try:
        event = json.load(sys.stdin)
    except Exception:
        event = {}
    cwd = event.get("cwd") or os.environ.get("CLAUDE_PROJECT_DIR") or str(Path.home())

    context = build_recovery_context(Path(cwd) / ".claude" / "handovers", datetime.now(timezone.utc))
    output: dict = {}
    if context:
        output = {"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": context}}
    print(json.dumps(output, ensure_ascii=False))
    sys.exit(0)


if __name__ == "__main__":
    main()
