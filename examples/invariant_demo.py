#!/usr/bin/env python3
"""Runnable demo for tools/invariants.py.

Creates a throwaway file containing deliberate violations, runs the invariant
runner against it, and prints what was caught. No external deps.

    python examples/invariant_demo.py
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

# Make the repo root importable when run from anywhere.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.invariants import SAMPLE_INVARIANTS, run  # noqa: E402


def main() -> int:
    bad_source = (
        "import logging\n"
        "\n"
        "DATA_DIR = '/home/alice/project/data'  # absolute path -> violation\n"  # leak-scan: ignore  inv: ignore (intentional sample)
        "\n"
        "def handle():\n"
        "    print('debugging')        # bare print -> warn\n"
        "    # TODO: make this configurable   <- no owner -> warn\n"
        "    return DATA_DIR\n"
    )

    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        (root / "sample_module.py").write_text(bad_source, encoding="utf-8")

        violations = run(root, SAMPLE_INVARIANTS)

        print(f"Scanned a 1-file sample project; found {len(violations)} violation(s):\n")
        for v in violations:
            print(f"  {v.path}:{v.line}  ({v.invariant})  {v.message}")

        print(
            "\nThis is the gate: in CI you'd run "
            "`python tools/invariants.py <dir> --allow known_violations.json` and fail "
            "the build on any NEW violation while grandfathering existing ones."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
