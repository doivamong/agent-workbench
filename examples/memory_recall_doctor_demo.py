#!/usr/bin/env python3
"""Runnable demo for tools/memory_recall_doctor.py.

Simulates the trap the doctor exists to catch: facts curated in the repo TEMPLATE dir while
the live (harness-loaded) dir is empty — so the agent never recalls them.

    python examples/memory_recall_doctor_demo.py
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.memory_recall_doctor import doctor  # noqa: E402


def _fact(name: str) -> str:
    return f"---\nname: {name}\ndescription: a fact.\nmetadata:\n  type: feedback\n---\n\nbody\n"


def main() -> int:
    with tempfile.TemporaryDirectory() as d:
        base = Path(d)
        template = base / "repo_memory"
        template.mkdir()
        live = base / "live_memory"
        live.mkdir()
        # The adopter curated two facts in the repo template...
        (template / "MEMORY.md").write_text(
            "# Memory Index\n\n- [feedback_a.md](feedback_a.md) - a\n"
            "- [feedback_b.md](feedback_b.md) - b\n", encoding="utf-8")
        (template / "feedback_a.md").write_text(_fact("feedback-a"), encoding="utf-8")
        (template / "feedback_b.md").write_text(_fact("feedback-b"), encoding="utf-8")
        # ...but the live dir the harness actually loads holds only an empty index.
        (live / "MEMORY.md").write_text("# Memory Index\n\n", encoding="utf-8")

        report, code = doctor(base, live, template)
        print("\n".join(report))
        print(f"\nexit code: {code}  (0 = advisory; 1 only when a live index is over budget)")
        print("The doctor shows 2 facts sit in the template but 0 reach the agent - the "
              "wrong-directory trap.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
