#!/usr/bin/env python3
"""skill_lint.py — keep the skill registry and the SKILL.md files in sync.

The registry (.claude/skills/skill-registry.md) is the single grep-able index of
every skill; each skill also has its own SKILL.md. They drift: a skill gets added
without a registry row, or a row outlives its folder. This tool flags that, against
a skills directory:

  ERROR  - a skill folder (has SKILL.md) with no row in the registry
  ERROR  - a real (non-placeholder) registry row with no matching skill folder
  ERROR  - a SKILL.md missing its frontmatter 'name' or 'description'
  WARN   - a SKILL.md whose frontmatter 'name' differs from its folder name

Usage:
    python tools/skill_lint.py [skills_dir]        # default: .claude/skills
Exit code is non-zero when any ERROR is found.

Does NOT: judge whether a skill's trigger wording is *good*, or whether two skills
truly overlap — that is the human's call in the registry's Do-NOT-trigger column.
It checks registry/folder/frontmatter consistency only. Stdlib only.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REGISTRY = "skill-registry.md"
# Registry rows for unwritten skills are intentionally italicised placeholders
# (e.g. `_your-config-guard_`); they have no folder yet, so don't demand one.
_ROW_NAME_RE = re.compile(r"^\|\s*`?_?([A-Za-z0-9][\w-]*)_?`?\s*\|")
_PLACEHOLDER_RE = re.compile(r"^\|\s*[_*]")


def registry_names(registry_text: str) -> set[str]:
    """Real (non-placeholder) skill names listed in the registry table."""
    names: set[str] = set()
    for line in registry_text.splitlines():
        if not line.startswith("|") or _PLACEHOLDER_RE.match(line):
            continue
        m = _ROW_NAME_RE.match(line)
        if m and m.group(1).lower() not in ("skill",):  # skip the header row
            names.add(m.group(1))
    return names


def _frontmatter_field(text: str, field: str) -> str | None:
    m = re.search(rf"(?m)^{field}:\s*(.*)$", text)
    return m.group(1).strip() if m else None


def lint(skills_dir: Path) -> list[tuple[str, str, str]]:
    out: list[tuple[str, str, str]] = []
    registry = skills_dir / REGISTRY
    reg_names = registry_names(registry.read_text(encoding="utf-8", errors="replace")) \
        if registry.exists() else set()
    if not registry.exists():
        out.append(("error", REGISTRY, "no skill-registry.md found"))

    folder_names: set[str] = set()
    for skill_md in sorted(skills_dir.glob("*/SKILL.md")):
        folder = skill_md.parent.name
        folder_names.add(folder)
        text = skill_md.read_text(encoding="utf-8", errors="replace")
        name = _frontmatter_field(text, "name")
        if not name:
            out.append(("error", f"{folder}/SKILL.md", "frontmatter missing 'name'"))
        elif name != folder:
            out.append(("warn", f"{folder}/SKILL.md", f"frontmatter name {name!r} != folder {folder!r}"))
        if not _frontmatter_field(text, "description"):
            out.append(("error", f"{folder}/SKILL.md", "frontmatter missing 'description'"))
        if folder not in reg_names:
            out.append(("error", folder, "skill folder has no row in skill-registry.md"))

    for name in sorted(reg_names - folder_names):
        out.append(("error", REGISTRY, f"registry row '{name}' has no matching skill folder"))
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Lint skills against the registry.")
    ap.add_argument("skills_dir", nargs="?", type=Path, default=Path(".claude/skills"),
                    help="Path to the skills directory (default: .claude/skills)")
    args = ap.parse_args(argv)

    if not args.skills_dir.is_dir():
        print(f"Not a directory: {args.skills_dir}", file=sys.stderr)
        return 2

    findings = lint(args.skills_dir)
    for sev, name, msg in findings:
        print(f"[{sev}] {name}: {msg}")
    errors = sum(1 for sev, _, _ in findings if sev == "error")
    warns = len(findings) - errors
    print(f"\n{errors} error(s), {warns} warning(s).")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
