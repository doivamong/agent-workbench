#!/usr/bin/env python3
"""memory_budget.py — the single source of truth for the MEMORY.md load budget.

Claude Code (v2.1.59+) auto-loads only the first 200 lines OR ~25 KB of MEMORY.md each session;
entries past whichever limit comes first silently truncate out of recall. Both the audit
(memory_audit.py) and the recall doctor (memory_recall_doctor.py) gate against these numbers, so
they live here once — they drifted apart once already (24576 -> 25600) when each tool kept its own
copy. Import them; never re-declare them. Stdlib only; pure constants, nothing executes.
"""
from __future__ import annotations

INDEX_MAX_BYTES = 25_600  # ~25 KB: the session-start load truncates near here (size, not lines)
INDEX_MAX_LINES = 200     # ...or the first 200 lines of MEMORY.md, whichever comes first
