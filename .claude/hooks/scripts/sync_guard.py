#!/usr/bin/env python3
"""PostToolUse hook — nudge a manifest/docs sync when a NEW file lands in a watched dir.

Adding a skill, a hook, a tool, or a rule usually means a dependent artifact must move too
(a registry row, a README count, `settings.json` wiring). This hook fires on a Write whose
target is a *new* file under a watched source-of-truth dir, and reminds you to run the
manifest drift check + update the dependents. It stays quiet on edits to existing files —
it distinguishes "new" from "edit" by checking whether the path is already in the committed
`.claude/manifest.json`, so ordinary content edits never trip it.

It is the bypassable seatbelt; `tools/sync_manifest.py --check` (in CI/pre-commit) is the
deterministic gate with history. See docs/guard-mechanisms.md. This hook is advisory only —
it never blocks the write.

Kill switch:
- SYNC_GUARD=0   — disable (never remind)

Protocol: stdin JSON (tool_name, tool_input, cwd) -> stdout JSON -> exit 0 (always allow).
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

# Kept in sync with tools/sync_manifest.py (re-declared so the hook stays self-contained —
# it runs with only .claude/hooks/lib on sys.path, not tools/).
WATCHED_ROOTS = (".claude/skills", ".claude/hooks", ".claude/rules", "tools", "scripts")
SCAN_SUFFIXES = {".py", ".md"}
MANIFEST_REL = ".claude/manifest.json"


def _manifest_paths(cwd: Path) -> set[str]:
    """The set of file paths recorded in the committed manifest (empty if none/unreadable)."""
    mf = cwd / MANIFEST_REL
    if not mf.exists():
        return set()
    try:
        return set(json.loads(mf.read_text(encoding="utf-8")).get("files", {}))
    except (OSError, json.JSONDecodeError):
        return set()


def reminder_for_write(file_path: str, cwd: Path, known_paths: set[str]) -> str | None:
    """Advisory string if `file_path` is a NEW watched-dir file, else None.

    Pure (inputs in, optional string out) so it is unit-testable without stdin. `known_paths`
    is the manifest's recorded set; a path already there is an edit (silent), a path missing
    from it is a new file (nudge).
    """
    if not file_path:
        return None
    try:
        rel = Path(file_path).resolve().relative_to(cwd.resolve()).as_posix()
    except (ValueError, OSError):
        return None
    if not any(rel == r or rel.startswith(r + "/") for r in WATCHED_ROOTS):
        return None
    if Path(rel).suffix not in SCAN_SUFFIXES:
        return None
    if rel in known_paths:
        return None  # already tracked -> this was an edit, stay quiet
    return (
        f"[sync-guard] New file in a watched dir: {rel}. Update its dependents (registry row / "
        "README counts / settings.json wiring), then run `python tools/sync_manifest.py --write`. "
        "Verify with `python tools/sync_manifest.py --check`."
    )


@hook_main("sync-guard")
def main() -> None:
    if os.environ.get("SYNC_GUARD", "1") == "0":
        print(json.dumps({}))
        sys.exit(0)

    try:
        event = json.load(sys.stdin)
    except Exception:
        print(json.dumps({}))
        sys.exit(0)

    if event.get("tool_name") != "Write":
        print(json.dumps({}))
        sys.exit(0)

    cwd = Path(event.get("cwd") or os.environ.get("CLAUDE_PROJECT_DIR") or ".")
    file_path = (event.get("tool_input") or {}).get("file_path", "")
    reminder = reminder_for_write(file_path, cwd, _manifest_paths(cwd))

    output: dict = {}
    if reminder:
        output = {"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": reminder}}
    print(json.dumps(output, ensure_ascii=False))
    sys.exit(0)


if __name__ == "__main__":
    main()
