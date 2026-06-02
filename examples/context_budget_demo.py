#!/usr/bin/env python3
"""Demo: audit this repo's own context budget — see tools/check_context_budget.py.

Runs the auditor against the workbench itself and prints the top few findings. Run it:

    python examples/context_budget_demo.py
"""
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))
import check_context_budget as cb  # noqa: E402


def main() -> int:
    components = cb.collect(REPO)
    print(cb.render_text_report(components, top_n=5, verbose=False, window=cb.DEFAULT_WINDOW))
    print("\n(token figures are a heuristic — relative magnitudes, not an exact budget)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
