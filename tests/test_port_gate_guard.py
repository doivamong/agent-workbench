"""Guard: the private porting gate must keep scanning what actually ships, not what's ignored.

Backstory (so this never regresses): `leak_scan` once scanned git-ignored files too, so a
machine path inside a git-ignored scratch handover false-failed the whole port gate. The fix
was `leak_scan --respect-gitignore` (test-locked in test_leak_scan.py) *wired into the gate*.
That wiring lives in `.porting/port_gate.py`, which is gitignored private infra with no test of
its own — so if a future edit drops the flag, the false-fail returns silently. This pins it.

It is intentionally tolerant of the public checkout: `.porting/` does not ship, so when the
gate file is absent the test SKIPS (it still collects, keeping the README test count identical
in the private and public trees). It asserts only the presence of the flag — it never echoes
the file's contents, so nothing private leaks into this shipped test.
"""
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PORT_GATE = ROOT / ".porting" / "port_gate.py"


def test_port_gate_passes_respect_gitignore():
    if not PORT_GATE.exists():
        pytest.skip("private porting infra (.porting/port_gate.py) not present in this checkout")
    src = PORT_GATE.read_text(encoding="utf-8")
    assert "--respect-gitignore" in src, (
        "port_gate.py no longer passes --respect-gitignore to leak_scan. Without it the gate "
        "re-scans git-ignored private files (handovers, caches) and false-fails on identifiers "
        "that never ship. Restore the flag in the leak_scan command."
    )
