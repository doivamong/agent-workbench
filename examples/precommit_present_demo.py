#!/usr/bin/env python3
"""Demo: the recovery-first gate wrapper (tools/precommit_present.py).

Shows the two things that matter: a passing gate passes through silently (exit 0, no note),
and a failing gate keeps its exact non-zero code AND gets a plain-language recovery note —
the wrapper never turns red into green. Stdlib-only; runs in well under a second.

    python examples/precommit_present_demo.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import precommit_present as pp  # noqa: E402

_PY = sys.executable


def _run(label: str, exit_code: int) -> int:
    print(f"\n=== {label} (wrapping a gate that exits {exit_code}) ===")
    rc = pp.main(["--", _PY, "-c", f"import sys; sys.exit({exit_code})"])
    print(f"  -> wrapper returned {rc}")
    return rc


def main() -> int:
    green = _run("green gate", 0)
    red = _run("red gate", 1)
    closed = pp.main([])  # no command at all -> must fail CLOSED
    print(f"\n=== empty command (must fail closed) ===\n  -> wrapper returned {closed}")

    ok = (green == 0) and (red == 1) and (closed == pp.WRAPPER_ERROR != 0)
    print("\nAll behaviours correct." if ok else "\nUNEXPECTED: a behaviour did not match.")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
