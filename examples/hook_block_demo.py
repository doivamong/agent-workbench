#!/usr/bin/env python3
"""Runnable demo for .claude/hooks/scripts/block_dangerous.py.

Runs the danger classifier against a mix of safe and destructive commands and
prints the verdict. This is the logic a PreToolUse hook uses to block dangerous
shell commands before they execute. Stdlib only.

    python examples/hook_block_demo.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / ".claude" / "hooks" / "scripts"))

from block_dangerous import check_command  # noqa: E402

SAMPLES = [
    # (command, expected_blocked)
    ("git status", False),
    ("git push origin main", False),
    ("git checkout -- file.py", False),
    ("pytest tests/", False),
    ("git push origin main --force", True),
    ("git reset --hard HEAD~3", True),
    ("git clean -fd", True),
    ("rm -rf /", True),
    ("DROP TABLE users;", True),
]


def main() -> int:
    print(f"{'BLOCKED?':<9} {'EXPECTED':<9} COMMAND")
    print("-" * 60)
    ok = True
    for cmd, expected in SAMPLES:
        hit = check_command(cmd)
        blocked = hit is not None
        mark = "OK" if blocked == expected else "MISMATCH"
        if blocked != expected:
            ok = False
        reason = f"   -> {hit[1]}" if hit else ""
        print(f"{str(blocked):<9} {str(expected):<9} {cmd}{reason}  [{mark}]")

    print("\nAll classifications correct." if ok else "\nSome classifications were wrong!")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
