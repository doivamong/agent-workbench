#!/usr/bin/env python3
"""SessionStart[startup|resume|clear] hook — inject a small project primer each session.

CLAUDE.md is loaded every session, but the skill catalog, the registry, and other
project conventions are NOT — so the agent can start a fresh session without
remembering the skill system exists. This hook injects the contents of a project-authored
primer file (``.claude/session-primer.md``) into context at session start, so a short,
stable pointer ("you have skills; here's the registry; pick by the trigger markers") is
present from turn one.

It is deliberately minimal and opt-in:
- It injects a *file you control*; edit it to change what every session sees, or delete it
  to inject nothing. The hook ships; the policy lives in the primer.
- Keep the primer SHORT. Whatever is here is paid for in every session's context budget —
  this competes with CLAUDE.md, it doesn't replace it. If a line belongs in always-loaded
  core, put it in CLAUDE.md instead; use the primer for pointers that aren't worth the
  permanent CLAUDE.md cost.
- It does NOT fire on `compact` (that source is handled by compact_restore.py, which
  re-injects the handover instead).

Kill switch:
- SESSION_PRIMER=0   — disable (never inject)

Protocol: stdin JSON (cwd) -> stdout JSON (hookSpecificOutput.additionalContext) -> exit 0.
Fail-open: any error degrades to an empty injection, never a broken session.
"""
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))
from stdio_utf8 import ensure_utf8_io  # noqa: E402
from session_breadcrumb import breadcrumb_path, format_note, read_breadcrumb  # noqa: E402
from hook_logger import hook_main  # noqa: E402

# UTF-8, pythonw-safe stdout/stdin before any output (shared lib/stdio_utf8.py).
ensure_utf8_io()

PRIMER_REL = Path(".claude") / "session-primer.md"
# A primer longer than this is almost certainly content that belongs in CLAUDE.md or a
# skill, not in every-session injected context. Truncate (don't fail) so the budget stays bounded.
MAX_PRIMER_CHARS = 2000


def build_primer_context(primer_path: Path, max_chars: int = MAX_PRIMER_CHARS) -> str | None:
    """Return the primer text to inject, or None if there's nothing to inject.

    Pure (filesystem in, string out) so it is unit-testable without stdin. Returns None
    for a missing or empty primer; truncates an over-long one to keep the injected context
    bounded (the cap is a budget guard, not a hard rule)."""
    if not primer_path.exists():
        return None
    try:
        text = primer_path.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    if not text:
        return None
    if len(text) > max_chars:
        text = text[:max_chars].rstrip() + "\n\n[primer truncated — keep .claude/session-primer.md short]"
    return text


@hook_main("session-start")
def main() -> None:
    if os.environ.get("SESSION_PRIMER", "1") == "0":
        print(json.dumps({}))
        sys.exit(0)

    try:
        event = json.load(sys.stdin)
    except Exception:
        event = {}
    cwd = event.get("cwd") or os.environ.get("CLAUDE_PROJECT_DIR") or str(Path.home())

    # Inject the project primer, then a one-line "where I left off" breadcrumb (if a recent one
    # was written by session_end.py). Either may be absent; inject whatever we have.
    parts = []
    primer = build_primer_context(Path(cwd) / PRIMER_REL)
    if primer:
        parts.append(primer)
    note = format_note(read_breadcrumb(breadcrumb_path(cwd)), datetime.now(timezone.utc))
    if note:
        parts.append(note)

    output: dict = {}
    if parts:
        output = {"hookSpecificOutput": {"hookEventName": "SessionStart",
                                         "additionalContext": "\n\n".join(parts)}}
    print(json.dumps(output, ensure_ascii=False))
    sys.exit(0)


if __name__ == "__main__":
    main()
