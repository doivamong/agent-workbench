#!/usr/bin/env python3
"""
Hook: PreToolUse (Bash)
Block dangerous shell commands before execution.
Especially important when using Bypass permissions mode on mobile.

Git destructive patterns use regex word-boundary (NOT substring) to:
  - avoid false positives (`git checkout .gitignore` is not blocked)
  - avoid allowlist substring shadowing (old bug: `git push origin --force`
    and `git reset --hard HEAD~N` slipped through because they matched
    allowlist entries `git push origin` / `git reset --hard HEAD`).
    WHITELIST removed — regex matches only genuinely destructive forms.
"""
import sys
import json
import re

# Substring patterns — DB / filesystem / config (substring match is sufficient)
DANGEROUS_PATTERNS = [
    # DB operations
    ("DROP TABLE", "Drop DB table"),
    ("DROP DATABASE", "Drop database"),
    ("DELETE FROM users", "Delete all users"),
    ("DELETE FROM items", "Delete all items"),
    ("TRUNCATE", "Delete all rows in table"),
    # File system
    ("rm -rf /", "Delete root"),
    ("rm -rf ~", "Delete home dir"),
    ("rmdir /s /q C:", "Windows: delete C drive"),
    # Config destructive
    ("del config.json", "Delete config file"),
    ("rm config.json", "Delete config file"),
    ("rm *.db", "Delete databases"),
]

# Regex patterns — git destructive. All regexes are IGNORECASE, searched on the command.
# SAFE commands still pass through (regex only matches destructive forms):
#   git push origin main | git reset --hard HEAD | git reset --hard |
#   git checkout main | git checkout -- file.py | git checkout .gitignore |
#   git restore --staged . | git clean -n
DANGEROUS_REGEX = [
    (r"\bgit\s+push\b[^&|;]*(?:--force|\s-f\b)",
     "Force push — rewrites remote history"),
    (r"\bgit\s+reset\s+--hard\s+HEAD[~^]",
     "Reset --hard HEAD~/^ — loses commits"),
    (r"\bgit\s+reset\s+--hard\s+(?:origin|upstream)/",
     "Reset --hard to remote — loses local commits"),
    (r"\bgit\s+reset\s+--hard\s+[0-9a-f]{7,40}\b",
     "Reset --hard to SHA — loses commits"),
    (r"\bgit\s+checkout\s+(?:--\s+)?\.(?:\s|$)",
     "Checkout . — discards all uncommitted changes (IRREVERSIBLE)"),
    (r"\bgit\s+restore\s+(?:--\s+)?\.(?:\s|$)",
     "Restore . — discards all uncommitted changes (IRREVERSIBLE)"),
    (r"\bgit\s+clean\s+-[a-z]*f",
     "Clean -f — deletes untracked files (IRREVERSIBLE)"),
]

_COMPILED_REGEX = [(re.compile(rx, re.IGNORECASE), reason)
                   for rx, reason in DANGEROUS_REGEX]


def check_command(command):
    """Return (pattern, reason) if command is dangerous; None if safe.

    Separated from main() to allow direct unit testing without changing hook behavior.
    """
    lower = command.lower()
    for pattern, reason in DANGEROUS_PATTERNS:
        if pattern.lower() in lower:
            return pattern, reason
    for rx, reason in _COMPILED_REGEX:
        if rx.search(command):
            return rx.pattern, reason
    return None


# Hook logger — imports hook_main from the shared lib directory
from pathlib import Path as _HookLoggerPath
sys.path.insert(0, str(_HookLoggerPath(__file__).parent.parent / "lib"))
from hook_logger import hook_main  # noqa: E402


@hook_main("block_dangerous")
def main():
    try:
        input_data = json.loads(sys.argv[1]) if len(sys.argv) > 1 else {}
    except (json.JSONDecodeError, IndexError):
        sys.exit(0)

    command = input_data.get("command", "").strip()
    if not command:
        sys.exit(0)

    hit = check_command(command)
    if hit:
        pattern, reason = hit
        print(json.dumps({
            "decision": "block",
            "reason": (
                f"Dangerous command blocked: `{pattern}`\n"
                f"Reason: {reason}\n"
                f"Command: {command[:100]}\n"
                f"-> Confirm manually if this action is truly required."
            )
        }))
        return

    sys.exit(0)


if __name__ == "__main__":
    main()
