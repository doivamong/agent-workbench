"""session_breadcrumb.py — the one-line "where I left off" note, shared writer + reader.

`session_end.py` writes a breadcrumb when a session ends; `session_start.py` reads it at the
next start and injects a single line, so a fresh session opens with "last time: branch X, at
commit Y, N uncommitted files" instead of nothing. The path, schema, and freshness rule live
here so the writer and the reader can never drift apart.

Honest limit: this is a breadcrumb, not a handover. It records the git state at session END
(which can be stale if you changed things outside the agent) and carries no goal/decisions/
next-steps. For real continuity, write a HANDOVER (see docs/session-preservation.md).
"""
import json
import os
from datetime import datetime
from pathlib import Path

MAX_AGE_SECONDS = 7 * 24 * 3600  # older than a week -> stale, don't resurface
_MAX_COMMIT_CHARS = 60           # keep the injected line short


def breadcrumb_path(cwd) -> Path:
    """Where the breadcrumb lives (project-local, gitignored). `SESSION_BREADCRUMB_PATH` overrides."""
    override = os.environ.get("SESSION_BREADCRUMB_PATH")
    if override:
        return Path(override)
    return Path(cwd) / ".claude" / ".logs" / "last_session.json"


def write_breadcrumb(path: Path, data: dict) -> None:
    """Persist the breadcrumb, creating the parent dir. The caller handles failures (fail-open)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def read_breadcrumb(path) -> "dict | None":
    """Load the breadcrumb, or None if missing/unreadable."""
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return None


def format_note(data, now: datetime) -> "str | None":
    """A one-line continuity note from a breadcrumb, or None if absent/stale/empty.

    Returns None for a breadcrumb older than MAX_AGE_SECONDS so a week-old session does not
    resurface as if it were yesterday. `now` and the stored timestamp must share tz-awareness."""
    if not data:
        return None
    when = "earlier"
    ended = data.get("ended_at")
    if ended:
        try:
            age = (now - datetime.fromisoformat(ended)).total_seconds()
            if age > MAX_AGE_SECONDS:
                return None
            when = _humanize(age)
        except (ValueError, TypeError):
            pass
    branch = data.get("branch") or "?"
    commit = data.get("commit") or "?"
    if len(commit) > _MAX_COMMIT_CHARS:
        commit = commit[:_MAX_COMMIT_CHARS].rstrip() + "…"
    dirty = data.get("uncommitted") or 0
    dirty_part = f", {dirty} uncommitted file(s)" if dirty else ""
    return f"Last session ({when}): branch `{branch}`, at `{commit}`{dirty_part}."


def _humanize(seconds: float) -> str:
    if seconds < 3600:
        return f"{int(seconds // 60)}m ago"
    if seconds < 24 * 3600:
        return f"{int(seconds // 3600)}h ago"
    return f"{int(seconds // 86400)}d ago"
