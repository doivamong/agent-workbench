#!/usr/bin/env python3
"""Runnable demo for the in-adopter `tools/doctor.py`.

`install.py --doctor` only verifies guards from the kit folder. But `install.py` copies
`tools/doctor.py` INTO the project, so once the kit is installed you can re-check your guards
from inside your own repo — `python tools/doctor.py` — without going back to the kit. This
demo imports `doctor` DIRECTLY (never `install`) to prove that standalone path works: it is
exactly what runs in an adopter project that has no `install.py` beside it.

    python examples/doctor_demo.py
"""
from __future__ import annotations

import contextlib
import io
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))            # for install (sets up a throwaway project)
sys.path.insert(0, str(ROOT / "tools"))  # for doctor — the SAME path an adopter's tools/ has

import doctor  # noqa: E402
import install  # noqa: E402  (only to create the demo project; doctor never imports it)


def _quiet(fn, *args):
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*args)


def main() -> int:
    with tempfile.TemporaryDirectory() as d:
        project = Path(d) / "demo_project"
        project.mkdir()
        print(f"Installing the kit into a throwaway project: {project}\n")
        _quiet(install.main, [str(project), "--merge-settings"])

        print("=== In-adopter verify: run the doctor that was COPIED into the project ===")
        print("(calling doctor.run_doctor directly — no install.py involved, as in a real adopter)\n")
        rc = doctor.run_doctor(project)
        print(f"\n(doctor exit code: {rc} — 0 means every wired guard passed)")

        print("\nThe point: the verifier travels with the kit. After installing, a user can ask "
              "'are my guards still on?' from inside their own project — no kit folder needed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
