"""handover_utils.py — shared helpers for the session-preservation hooks.

Used by precompact_backup.py (PreCompact) and compact_restore.py (SessionStart[compact]).
Stdlib only; no side effects on import.
"""
from __future__ import annotations

import time
from pathlib import Path


def get_handovers_dir(cwd: str) -> Path:
    """Return ``<cwd>/.claude/handovers``, creating it if needed."""
    d = Path(cwd) / ".claude" / "handovers"
    d.mkdir(parents=True, exist_ok=True)
    return d


def get_latest_handover(cwd: str, max_age_hours: int = 24) -> Path | None:
    """Newest ``HANDOVER_*.md``, or None if there is none or it is older than ``max_age_hours``."""
    d = get_handovers_dir(cwd)
    handovers = sorted(d.glob("HANDOVER_*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not handovers:
        return None
    newest = handovers[0]
    if time.time() - newest.stat().st_mtime > max_age_hours * 3600:
        return None
    return newest


def cleanup_old_files(directory: Path, pattern: str, keep: int = 5) -> int:
    """Delete files matching ``pattern`` in ``directory``, keeping the ``keep`` newest. Returns count removed."""
    files = sorted(directory.glob(pattern), key=lambda p: p.stat().st_mtime)
    removed = 0
    for old_file in (files[:-keep] if len(files) > keep else []):
        try:
            old_file.unlink()
            removed += 1
        except OSError:
            pass
    return removed
