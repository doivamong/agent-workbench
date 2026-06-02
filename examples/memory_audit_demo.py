#!/usr/bin/env python3
"""Runnable demo for tools/memory_audit.py.

Builds a throwaway memory/ directory with one healthy fact, one orphan (not in the
index), and one dangling index link, then runs the auditor and prints what it caught.

    python examples/memory_audit_demo.py
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.memory_audit import audit  # noqa: E402

_FACT = """---
name: feedback-small-commits
description: Prefer small, reviewable commits.
metadata:
  type: feedback
---

Keep commits small. Related: [[user-style]]
"""


def main() -> int:
    with tempfile.TemporaryDirectory() as d:
        mem = Path(d)
        (mem / "MEMORY.md").write_text(
            "# Memory Index\n\n"
            "- [feedback_small_commits.md](feedback_small_commits.md) - small commits\n"
            "- [gone.md](gone.md) - this file does not exist\n",
            encoding="utf-8",
        )
        (mem / "feedback_small_commits.md").write_text(_FACT, encoding="utf-8")
        (mem / "project_orphan.md").write_text(
            "---\nname: project-orphan\ndescription: not linked from the index.\n"
            "metadata:\n  type: project\n---\n\nAn orphan fact.\n",
            encoding="utf-8",
        )

        findings = audit(mem)
        print(f"Audited a 2-fact sample memory; {len(findings)} finding(s):\n")
        for sev, name, msg in findings:
            print(f"  [{sev}] {name}: {msg}")
        print(
            "\nThe dangling index link is an ERROR (fix the index); the orphan and the "
            "unresolved [[wiki-link]] are WARNINGs you triage by hand."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
