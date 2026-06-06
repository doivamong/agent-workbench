#!/usr/bin/env python3
"""Runnable demo for `install.py --doctor`.

Installs the kit into a throwaway project, proves the dangerous-command guard is actually ON
with --doctor, then breaks the wired interpreter to show the doctor FAIL LOUD — the case a
non-programmer could never spot on their own (a wired-but-dead hook).

    python examples/install_doctor_demo.py
"""
from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import install  # noqa: E402


def _quiet(fn, *args):
    """Run fn, swallowing its (verbose) stdout, so the demo focuses on the doctor."""
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*args)


def main() -> int:
    with tempfile.TemporaryDirectory() as d:
        project = Path(d) / "demo_project"
        project.mkdir()
        print(f"Installing the kit into a throwaway project: {project}\n")
        _quiet(install.main, [str(project), "--merge-settings"])

        print("=== 1) Healthy install — doctor should PROVE the guard is ON ===")
        rc_ok = install.main([str(project), "--doctor"])
        print(f"\n(doctor exit code: {rc_ok} — 0 means every wired guard passed)\n")

        print("=== 2) Break the wired interpreter — doctor should FAIL LOUD ===")
        settings_path = project / install.SETTINGS_REL
        data = json.loads(settings_path.read_text(encoding="utf-8"))
        for group in data["hooks"]["PreToolUse"]:
            for hook in group["hooks"]:
                if "block_dangerous.py" in hook["command"]:
                    hook["command"] = ('awb_no_such_python '
                                       '"$CLAUDE_PROJECT_DIR/.claude/hooks/scripts/block_dangerous.py"')
        settings_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        rc_bad = install.main([str(project), "--doctor"])
        print(f"\n(doctor exit code: {rc_bad} — non-zero: a guard is silently OFF)")

        print("\nThe point: a non-programmer can't tell a wired-but-dead hook from a live one. "
              "--doctor proves protection is real, and fails loud the moment it isn't.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
