#!/usr/bin/env python3
"""PreCompact hook — back up the transcript before the context is compacted.

Fires on auto-compact (context full) or a manual /compact. Copies the transcript JSONL
into .claude/handovers/ and writes a `.last_compact` signal file that compact_restore.py
reads on the next SessionStart to re-inject a handover excerpt. This is Layer 1 of the
session-preservation design (see docs/session-preservation.md): a safety net that fires
even when you forget to save, so a compaction never silently drops the working context.

Kill switch:
- PRECOMPACT_BACKUP=0   — disable (no backup, no signal)

Protocol: stdin JSON (transcript_path, trigger, cwd) -> stdout JSON -> exit 0. Backs up
silently; never blocks. Keeps the newest 5 transcript backups.
"""
import json
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stdin, "reconfigure"):
    sys.stdin.reconfigure(encoding="utf-8")

# Shared helpers + fail-open wrapper from the sibling lib/ directory.
sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))
from handover_utils import cleanup_old_files, get_handovers_dir  # noqa: E402
from hook_logger import hook_main  # noqa: E402


@hook_main("precompact-backup")
def main() -> None:
    if os.environ.get("PRECOMPACT_BACKUP", "1") == "0":
        print(json.dumps({}))
        sys.exit(0)

    try:
        event = json.load(sys.stdin)
    except Exception:
        event = {}

    transcript_path = event.get("transcript_path", "")
    trigger = event.get("trigger", "unknown")
    cwd = event.get("cwd") or os.environ.get("CLAUDE_PROJECT_DIR") or str(Path.home())

    handovers_dir = get_handovers_dir(cwd)

    backup_path = ""
    if transcript_path and Path(transcript_path).exists():
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        dest = handovers_dir / f"transcript_{trigger}_{ts}.jsonl"
        try:
            shutil.copy2(transcript_path, dest)
            backup_path = str(dest)
        except OSError:
            pass
        cleanup_old_files(handovers_dir, "transcript_*.jsonl", keep=5)

    signal = {
        "timestamp": datetime.now().isoformat(),
        "trigger": trigger,
        "transcript_backup": backup_path,
    }
    try:
        (handovers_dir / ".last_compact").write_text(
            json.dumps(signal, ensure_ascii=False), encoding="utf-8"
        )
    except OSError:
        pass

    print(json.dumps({}))  # silent backup — no additionalContext
    sys.exit(0)


if __name__ == "__main__":
    main()
