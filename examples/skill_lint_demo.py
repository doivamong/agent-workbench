#!/usr/bin/env python3
"""Runnable demo for tools/skill_lint.py.

Builds a throwaway skills/ directory where one skill is in sync, one folder is
missing from the registry, and one registry row has no folder — then lints it.

    python examples/skill_lint_demo.py
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.skill_lint import lint  # noqa: E402

_REGISTRY = """# Skill Registry

| Skill | Tier | Fires when | Does NOT fire when |
|-------|------|------------|--------------------|
| `in-sync` | guard | x | y |
| `ghost-row` | guard | x | y |
| _your-placeholder_ | guard | x | y |
"""

_SKILL = "---\nname: {name}\ndescription: does a thing\ntier: guard\n---\nbody\n"


def main() -> int:
    with tempfile.TemporaryDirectory() as d:
        skills = Path(d)
        (skills / "skill-registry.md").write_text(_REGISTRY, encoding="utf-8")
        for folder in ("in-sync", "unregistered"):
            sd = skills / folder
            sd.mkdir()
            (sd / "SKILL.md").write_text(_SKILL.format(name=folder), encoding="utf-8")

        findings = lint(skills)
        print(f"Linted 2 skill folders against a 2-row registry; {len(findings)} finding(s):\n")
        for sev, name, msg in findings:
            print(f"  [{sev}] {name}: {msg}")
        print(
            "\n'unregistered' has no registry row and 'ghost-row' has no folder -> both ERROR. "
            "The italic placeholder row is ignored on purpose."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
