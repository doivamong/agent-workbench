#!/usr/bin/env python3
"""PostToolUse hook — nudge a simplicity pass after a burst of edits.

Trigger: Edit or Write tool calls.
Logic:   Count edits and the distinct files touched within a session window. Once the
         edit count crosses a threshold, inject a one-line reminder to do a
         simplification pass (dead code, unused imports, over-long functions, DRY).
         A cooldown throttles repeats and the session resets after a TTL, so a long
         session gets the occasional nudge, never a stream of them.

State:   a small JSON file under ~/.claude/.state (override with POST_EDIT_SIMPLIFY_STATE).

Kill switches (environment variables):
- POST_EDIT_SIMPLIFY=0             — disable the hook entirely (never remind)
- POST_EDIT_SIMPLIFY_THRESHOLD=N   — edits before the first reminder (default 5)
- POST_EDIT_SIMPLIFY_STATE=<path>  — relocate the session state file (used by tests)

Protocol: stdin JSON (tool_name, tool_input) -> stdout JSON -> exit 0 (always allow).
This hook never blocks an action; it only adds advisory context.

Design influence: the "remind to simplify after N edits" idea comes from claudekit
(MIT); this is an independent, stdlib-only reimplementation — see THIRD_PARTY_NOTICES.md.
"""
import json
import os
import sys
import time
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stdin, "reconfigure"):
    sys.stdin.reconfigure(encoding="utf-8")

EDIT_THRESHOLD = 5
REMINDER_COOLDOWN = 10 * 60   # seconds between two reminders
SESSION_TTL = 2 * 60 * 60     # a session older than this resets to zero


def _state_file() -> Path:
    override = os.environ.get("POST_EDIT_SIMPLIFY_STATE")
    if override:
        return Path(override)
    return Path.home() / ".claude" / ".state" / "post_edit_simplify_session.json"


def _threshold() -> int:
    try:
        return max(1, int(os.environ.get("POST_EDIT_SIMPLIFY_THRESHOLD", EDIT_THRESHOLD)))
    except (TypeError, ValueError):
        return EDIT_THRESHOLD


def new_session(now: float) -> dict:
    """A zeroed session anchored at ``now``."""
    return {"start_time": now, "edit_count": 0, "modified_files": [], "last_reminder": 0}


def load_session(now: float) -> dict:
    """Load session state, starting fresh if it is missing, corrupt, or older than the TTL.

    Takes ``now`` rather than calling the clock itself so the TTL reset is unit-testable.
    """
    try:
        data = json.loads(_state_file().read_text(encoding="utf-8"))
        if now - data.get("start_time", 0) < SESSION_TTL:
            data.setdefault("start_time", now)
            data.setdefault("edit_count", 0)
            data.setdefault("modified_files", [])
            data.setdefault("last_reminder", 0)
            return data
    except Exception:
        pass
    return new_session(now)


def save_session(session: dict) -> None:
    """Persist session state. State I/O must never break the hook, so it fails open."""
    try:
        path = _state_file()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(session, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


def register_edit(session: dict, file_path: str, now: float, *,
                  threshold: int = EDIT_THRESHOLD,
                  cooldown: float = REMINDER_COOLDOWN) -> str | None:
    """Record one edit in ``session`` (mutated in place); return a reminder if one is due.

    Pure state transition, separated from main() so the threshold/cooldown/dedup logic
    is unit-testable without stdin or the filesystem.
    """
    session["edit_count"] = session.get("edit_count", 0) + 1
    if file_path:
        files = session.setdefault("modified_files", [])
        if file_path not in files:
            files.append(file_path)

    # The cooldown only applies once a reminder has actually been sent; treat a
    # last_reminder of 0 as "never reminded" so the first nudge fires at the
    # threshold regardless of the time base (real clock vs. a relative one in tests).
    last = session.get("last_reminder", 0)
    cooled_down = last == 0 or (now - last) > cooldown
    if not (session["edit_count"] >= threshold and cooled_down):
        return None

    session["last_reminder"] = now
    n_files = len(session.get("modified_files", []))
    return (
        f"[Simplify reminder] {n_files} file(s) changed "
        f"({session['edit_count']} edits) this session. Consider a simplification pass "
        f"before moving on: dead code, unused imports, over-long functions, DRY violations."
    )


# Hook logger — fail-open wrapper from the shared lib directory (sibling of scripts/).
from pathlib import Path as _HookLoggerPath
sys.path.insert(0, str(_HookLoggerPath(__file__).parent.parent / "lib"))
from hook_logger import hook_main  # noqa: E402


@hook_main("post-edit-simplify")
def main() -> None:
    if os.environ.get("POST_EDIT_SIMPLIFY", "1") == "0":
        print(json.dumps({}))
        sys.exit(0)

    try:
        event = json.load(sys.stdin)
    except Exception:
        print(json.dumps({}))
        sys.exit(0)

    if event.get("tool_name") not in ("Edit", "Write"):
        print(json.dumps({}))
        sys.exit(0)

    now = time.time()
    session = load_session(now)
    file_path = (event.get("tool_input") or {}).get("file_path", "")
    reminder = register_edit(session, file_path, now, threshold=_threshold())
    save_session(session)

    output: dict = {}
    if reminder:
        output = {
            "hookSpecificOutput": {
                "hookEventName": "PostToolUse",
                "additionalContext": reminder,
            }
        }
    print(json.dumps(output, ensure_ascii=False))
    sys.exit(0)


if __name__ == "__main__":
    main()
