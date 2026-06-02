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

from tools.invariants import Invariant, SAMPLE_INVARIANTS, line_regex, run  # noqa: E402


def main() -> int:
    bad_source = (
        "import logging\n"
        "\n"
        "DATA_DIR = '/home/alice/project/data'  # absolute path -> violation\n"  # leak-scan: ignore  inv: ignore (intentional sample)
        "\n"
        "def handle():\n"
        "    print('debugging')        # bare print -> warn\n"
        "    # TODO: make this configurable   <- no owner -> warn\n"
        "    try:\n"
        "        return DATA_DIR\n"
        "    except:                    # bare except -> custom-rule violation\n"
        "        return None\n"
    )

    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        (root / "sample_module.py").write_text(bad_source, encoding="utf-8")

        # Part 1: the rules the tool ships with.
        violations = run(root, SAMPLE_INVARIANTS)
        print(f"[built-in rules] scanned a 1-file sample project; found {len(violations)} violation(s):\n")
        for v in violations:
            print(f"  {v.path}:{v.line}  ({v.invariant})  {v.message}")

        # Part 2: the actual point of the framework — write YOUR OWN rule. A few lines of
        # line_regex codify a project convention the agent keeps re-breaking, and it runs
        # at the same speed as the built-ins. (This one mirrors the repo's silent-failure
        # theme: a bare `except:` swallows everything.)
        my_rules = [
            Invariant(
                id="no-bare-except",
                description="Catch a specific exception, never a bare except:.",
                check=line_regex(
                    "no-bare-except",
                    r"^\s*except\s*:",
                    "Bare 'except:' swallows every error - name the exception you handle.",
                ),
            ),
        ]
        custom = run(root, my_rules)
        print(f"\n[your own rule] the same scan with one custom invariant; found {len(custom)} violation(s):\n")
        for v in custom:
            print(f"  {v.path}:{v.line}  ({v.invariant})  {v.message}")

        print(
            "\nThis is the gate: in CI you'd run "
            "`python tools/invariants.py <dir> --allow known_violations.json` and fail "
            "the build on any NEW violation while grandfathering existing ones. The built-in "
            "rules are just a starting set - the framework exists so you add your own (Part 2)."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
