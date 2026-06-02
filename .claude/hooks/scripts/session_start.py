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
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stdin, "reconfigure"):
    sys.stdin.reconfigure(encoding="utf-8")

sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))
from hook_logger import hook_main  # noqa: E402

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

    context = build_primer_context(Path(cwd) / PRIMER_REL)
    output: dict = {}
    if context:
        output = {"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": context}}
    print(json.dumps(output, ensure_ascii=False))
    sys.exit(0)


if __name__ == "__main__":
    main()
