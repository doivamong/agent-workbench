#!/usr/bin/env python3
"""Runnable demo for tools/memory_eval.py.

Benchmarks the kit's own reference ``memory/`` corpus: does each one-line MEMORY.md hook recall
the right fact file for a realistic query? Loads the shipped gold set via the same path the CLI
uses, then prints recall@k / precision@k / MRR for the index hooks vs the full-body baseline.

    python examples/memory_eval_demo.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.memory_eval import evaluate, format_report, load_gold  # noqa: E402


def main() -> int:
    mem_dir = ROOT / "memory"
    gold = load_gold(ROOT / "examples" / "memory_eval_gold.json")
    print(f"Benchmarking the reference corpus at {mem_dir} over {len(gold)} gold queries:\n")
    for line in format_report(evaluate(mem_dir, gold)):
        print(line)
    print("\nRead the index row as a FLOOR: bag-of-words Jaccard understates the live agent, which")
    print("reads meaning. The point is to MEASURE the index-gating discipline, not to assert it.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
