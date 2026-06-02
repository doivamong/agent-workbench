#!/usr/bin/env python3
"""PostToolUse hook — nudge to manage context as a session grows long.

Counts every tool call (and, separately, edits) per project. At a few thresholds it
injects a one-line reminder: free the context window with /compact, or save a handover
so the session can be resumed cleanly. A cooldown throttles repeats and the count resets
after a TTL. This is the "you're getting deep, checkpoint now" half of session
preservation — the backups (precompact_backup) catch you if you don't.

State: a small JSON file under ~/.claude/.state (override with CONTEXT_TRACKER_STATE),
keyed by project directory so two repos don't share a counter.

Kill switches (environment variables):
- CONTEXT_TRACKER=0          — disable the hook entirely
- CONTEXT_TRACKER_STATE=<p>  — relocate the state file (used by tests)

Protocol: stdin JSON (tool_name, cwd) -> stdout JSON -> exit 0. Never blocks.
"""
import json
import os
import sys
import time
from pathlib import Path

SESSION_TTL = 4 * 60 * 60     # a session older than this resets to zero
MESSAGE_COOLDOWN = 5 * 60     # seconds between two reminders
# Thresholds are tunable starting points, not measured truths.
EDIT_WARN = 40
EDIT_REPEAT = 20
TOOL_CHECKPOINT = 100
TOOL_CRITICAL = 200


def _state_file() -> Path:
    override = os.environ.get("CONTEXT_TRACKER_STATE")
    if override:
        return Path(override)
    return Path.home() / ".claude" / ".state" / "context_tracker.json"


def new_state(now: float) -> dict:
    return {"start_time": now, "tool_count": 0, "edit_count": 0, "last_message": 0}


def load_state(cwd: str, now: float) -> dict:
    """Per-project state, starting fresh if missing, corrupt, or older than the TTL.

    Takes ``now`` rather than calling the clock so the TTL reset is unit-testable.
    """
    try:
        all_data = json.loads(_state_file().read_text(encoding="utf-8"))
        project = all_data.get(cwd, {})
        if now - project.get("start_time", 0) < SESSION_TTL:
            project.setdefault("start_time", now)
            project.setdefault("tool_count", 0)
            project.setdefault("edit_count", 0)
            project.setdefault("last_message", 0)
            return project
    except Exception:
        pass
    return new_state(now)


def save_state(cwd: str, state: dict) -> None:
    """Persist per-project state. Fails open — state I/O must never break the hook."""
    try:
        path = _state_file()
        all_data: dict = {}
        if path.exists():
            try:
                all_data = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                all_data = {}
        all_data[cwd] = state
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(all_data, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


def register_tool(state: dict, tool_name: str, now: float, *,
                  cooldown: float = MESSAGE_COOLDOWN) -> str | None:
    """Record one tool call in ``state`` (mutated in place); return a reminder if one is due.

    Pure state transition, separated from main() so thresholds/cooldown are unit-testable.
    """
    state["tool_count"] = state.get("tool_count", 0) + 1
    if tool_name in ("Edit", "Write"):
        state["edit_count"] = state.get("edit_count", 0) + 1

    ec, tc = state["edit_count"], state["tool_count"]
    message = ""
    if ec == EDIT_WARN or (ec > EDIT_WARN and ec % EDIT_REPEAT == 0):
        message = f"{ec} edits this session — consider /compact to free up the context window."
    elif TOOL_CHECKPOINT <= tc < TOOL_CHECKPOINT + 10:
        message = f"{tc} tool calls — consider saving a handover so the session can resume cleanly."
    elif TOOL_CRITICAL <= tc < TOOL_CRITICAL + 10:
        message = f"{tc} tool calls — context is getting large; consider /compact or saving a handover."

    if not message:
        return None
    last = state.get("last_message", 0)
    if last and (now - last) < cooldown:
        return None
    state["last_message"] = now
    return message


# Fail-open wrapper from the sibling lib/ directory.
sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))
from stdio_utf8 import ensure_utf8_io  # noqa: E402
from hook_logger import hook_main  # noqa: E402

# UTF-8, pythonw-safe stdout/stdin before any output (shared lib/stdio_utf8.py).
ensure_utf8_io()


@hook_main("context-tracker")
def main() -> None:
    if os.environ.get("CONTEXT_TRACKER", "1") == "0":
        print(json.dumps({}))
        sys.exit(0)

    try:
        event = json.load(sys.stdin)
    except Exception:
        print(json.dumps({}))
        sys.exit(0)

    cwd = event.get("cwd") or os.getcwd()
    now = time.time()
    state = load_state(cwd, now)
    message = register_tool(state, event.get("tool_name", ""), now)
    save_state(cwd, state)

    output: dict = {}
    if message:
        output = {"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": message}}
    print(json.dumps(output, ensure_ascii=False))
    sys.exit(0)


if __name__ == "__main__":
    main()
