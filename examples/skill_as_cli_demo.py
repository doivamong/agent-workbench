#!/usr/bin/env python3
"""Reference example: invoke a skill's playbook OUTSIDE Claude Code.

A SKILL.md is just frontmatter + a Markdown playbook. Any agent (Cursor, Copilot,
a plain LLM call) can run the same methodology if you hand it that playbook as
context. This demo extracts the body of a skill and prints it the way you'd pipe
it into another tool — e.g. `python examples/skill_as_cli_demo.py awb-review`.

This is a BLUEPRINT, deliberately ~30 lines: it shows the seam (strip frontmatter,
emit the playbook), not a full multi-tool runner. See docs/skills-as-cli.md.
"""
from __future__ import annotations

import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")  # playbooks contain non-ASCII (em-dashes, etc.)

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / ".claude" / "skills"


def playbook(skill_md: Path) -> str:
    """Return the SKILL.md body with its YAML frontmatter stripped."""
    text = skill_md.read_text(encoding="utf-8")
    lines = text.splitlines()
    if lines and lines[0].strip() == "---":
        close = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), 0)
        lines = lines[close + 1:]
    return "\n".join(lines).strip()


def main() -> int:
    name = sys.argv[1] if len(sys.argv) > 1 else "awb-review"
    skill_md = SKILLS / name / "SKILL.md"
    if not skill_md.is_file():
        avail = ", ".join(sorted(p.name for p in SKILLS.glob("*/") if (p / "SKILL.md").exists()))
        print(f"No such skill: {name}. Available: {avail}", file=sys.stderr)
        return 1
    print(f"# Playbook for '{name}' (pipe this into any agent as context)\n")
    print(playbook(skill_md))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
