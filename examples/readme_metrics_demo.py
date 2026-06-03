#!/usr/bin/env python3
"""Runnable demo for tools/readme_metrics.py.

Writes a tiny README with deliberately-stale counts into a temp dir, shows the check flagging each,
then the rewrite fixing them — without touching the real README.

    python examples/readme_metrics_demo.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.readme_metrics import find_mismatches, rewrite  # noqa: E402

STALE = """\
| Reusable core dependencies | **0** (stdlib-only) |
| Tests | **1**, green in CI (...) |
| Runnable demos | **1** (`examples/`) |
| Skills | **1** (...) |
| Standalone tools | **1** (`a`) |

python -m pytest -q                 # 1 tests

**Agent Workbench** · stdlib-only core · 1 tests · MIT
"""

# Pretend the tree currently has these counts (the real tool computes them from the file tree).
COUNTS = {"deps": 0, "tests": 353, "demos": 14, "tools": 12, "skills": 15}


def main() -> int:
    print("A stale README advertises 1 everywhere. `--check` finds:")
    for key, found, expected in find_mismatches(COUNTS, STALE):
        print(f"  {key}: README says {found}, tree has {expected}")
    fixed = rewrite(COUNTS, STALE)
    remaining = find_mismatches(COUNTS, fixed)
    print(f"\nAfter `--write`, remaining mismatches: {remaining or 'none'}")
    print("(The tool/skill LISTS stay hand-maintained — it gates numbers, not prose.)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
