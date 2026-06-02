#!/usr/bin/env python3
"""skill_lint.py — keep the skill registry and the SKILL.md files in sync.

The registry (.claude/skills/skill-registry.md) is the single grep-able index of
every skill; each skill also has its own SKILL.md. They drift: a skill gets added
without a registry row, or a row outlives its folder. This tool flags that, against
a skills directory:

  ERROR  - a skill folder (has SKILL.md) with no row in the registry
  ERROR  - a real (non-placeholder) registry row with no matching skill folder
  ERROR  - a SKILL.md with no/malformed YAML frontmatter, or missing 'name'/'description'
  WARN   - a SKILL.md whose frontmatter 'name' differs from its folder name
  WARN   - a description missing a 'USE WHEN' or 'DO NOT TRIGGER' marker (the
           convention that makes a skill fire at the right time and not the wrong one)
  WARN   - a SKILL.md longer than MAX_SKILL_LINES (push detail into references/)
  WARN   - a guard-tier skill whose body states no limit (no 'does NOT …' honesty line)
  WARN   - a body that references `another-skill` slug with no folder/registry row (a
           dangling cross-reference left by a rename or archive)

A skill may be retired with an `archived: <date>` frontmatter field: it is then exempt from the
"folder has no registry row" error (so you can drop its row without deleting the folder) and is
reported as an archived WARN instead.

Usage:
    python tools/skill_lint.py [skills_dir]        # default: .claude/skills
Exit code is non-zero when any ERROR is found (WARN alone does not fail).

Does NOT: judge whether the trigger *wording* is good, or whether two skills truly overlap — that
is the human's call in the registry's Do-NOT-trigger column. The guard-honesty and cross-reference
checks are presence heuristics, not semantic guarantees: the honesty check only greps for a 'does
not' phrase (it cannot tell a real caveat from the words), and the cross-ref check only catches
backtick-wrapped kebab-case slugs whose name-family matches an existing skill (a reference written
in prose without backticks slips through). It checks registry/folder consistency and the *presence*
of the structural conventions only. Stdlib only.

The block-scalar frontmatter parser and the USE WHEN / DO NOT TRIGGER presence checks
were re-implemented in stdlib from the design of `MiniMax-AI/skills` (`validate_skills.py`,
MIT) — see THIRD_PARTY_NOTICES.md. No source was copied.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REGISTRY = "skill-registry.md"
# A SKILL.md beyond this is usually carrying detail that belongs in references/.
# Soft nudge (WARN), not a hard rule — tune per project.
MAX_SKILL_LINES = 400
# Registry rows for unwritten skills are intentionally italicised placeholders
# (e.g. `_your-config-guard_`); they have no folder yet, so don't demand one.
_ROW_NAME_RE = re.compile(r"^\|\s*`?_?([A-Za-z0-9][\w-]*)_?`?\s*\|")
_PLACEHOLDER_RE = re.compile(r"^\|\s*[_*]")
_FIELD_RE = re.compile(r"^([A-Za-z_][\w-]*)\s*:\s*(.*)$")
_BLOCK_SCALAR_HEADS = {"|", ">", "|+", "|-", ">+", ">-"}
# A guard skill should state what it does NOT do (PHILOSOPHY tenet 3). Greppable presence check.
_HONESTY_RE = re.compile(r"does\s*not|doesn't", re.IGNORECASE)
# A cross-reference to another skill: a backtick-wrapped kebab-case slug (>= 1 hyphen).
_SKILL_REF_RE = re.compile(r"`([a-z][a-z0-9]*(?:-[a-z0-9]+)+)`")


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


def registry_tiers(registry_text: str) -> dict[str, str]:
    """Map each real (non-placeholder) skill name to its tier (lowercased) from the registry."""
    tiers: dict[str, str] = {}
    for line in registry_text.splitlines():
        if not line.startswith("|") or _PLACEHOLDER_RE.match(line):
            continue
        m = _ROW_NAME_RE.match(line)
        if not m or m.group(1).lower() == "skill":
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) > 1:
            tiers[m.group(1)] = cells[1].strip("`").lower()
    return tiers


def parse_frontmatter(text: str) -> dict[str, str] | None:
    """Parse a SKILL.md's YAML frontmatter into {field: value}, or None if absent.

    Handles single-line ``key: value`` and YAML block scalars (``key: >`` / ``key: |``):
    the block body is the indented continuation, joined into one string. This is why a
    single-line regex is not enough — descriptions are written as ``description: >`` blocks,
    so their USE WHEN / DO NOT TRIGGER markers live on indented continuation lines.
    """
    s = text.lstrip("﻿")
    if not s.startswith("---"):
        return None
    lines = s.splitlines()
    end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
    if end is None:
        return None
    body = lines[1:end]
    fields: dict[str, str] = {}
    i = 0
    while i < len(body):
        line = body[i]
        if not line.strip() or line.lstrip().startswith("#"):
            i += 1
            continue
        m = _FIELD_RE.match(line)
        if not m:
            i += 1
            continue
        key, rest = m.group(1), m.group(2).strip()
        if rest in _BLOCK_SCALAR_HEADS or rest == "":
            # Collect indented continuation lines (and blanks within the block).
            block: list[str] = []
            i += 1
            while i < len(body) and (body[i][:1] in (" ", "\t") or not body[i].strip()):
                block.append(body[i].strip())
                i += 1
            fields[key] = " ".join(b for b in block if b).strip()
            continue
        fields[key] = rest.strip("\"'")
        i += 1
    return fields


def _body_after_frontmatter(text: str) -> str:
    """The SKILL.md content after the closing frontmatter '---' (or all of it if unfenced)."""
    s = text.lstrip("﻿")
    if not s.startswith("---"):
        return s
    lines = s.splitlines()
    end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
    return "\n".join(lines[end + 1:]) if end is not None else s


def lint(skills_dir: Path) -> list[tuple[str, str, str]]:
    out: list[tuple[str, str, str]] = []
    registry = skills_dir / REGISTRY
    reg_text = registry.read_text(encoding="utf-8", errors="replace") if registry.exists() else ""
    reg_names = registry_names(reg_text)
    reg_tiers = registry_tiers(reg_text)
    if not registry.exists():
        out.append(("error", REGISTRY, "no skill-registry.md found"))

    skill_mds = sorted(skills_dir.glob("*/SKILL.md"))
    folder_names = {p.parent.name for p in skill_mds}
    known = reg_names | folder_names
    families = {n.split("-", 1)[0] for n in known}  # leading segment of every known skill slug

    for skill_md in skill_mds:
        folder = skill_md.parent.name
        text = skill_md.read_text(encoding="utf-8", errors="replace")
        loc = f"{folder}/SKILL.md"
        body = _body_after_frontmatter(text)

        n_lines = text.count("\n") + 1
        if n_lines > MAX_SKILL_LINES:
            out.append(("warn", loc, f"{n_lines} lines (>{MAX_SKILL_LINES}) — move detail into references/"))

        fields = parse_frontmatter(text)
        archived = bool((fields or {}).get("archived", "").strip())
        if fields is None:
            out.append(("error", loc, "no/malformed YAML frontmatter (need a '---' fenced block)"))
        else:
            name = fields.get("name", "").strip()
            if not name:
                out.append(("error", loc, "frontmatter missing 'name'"))
            elif name != folder:
                out.append(("warn", loc, f"frontmatter name {name!r} != folder {folder!r}"))

            desc = fields.get("description", "").strip()
            if not desc:
                out.append(("error", loc, "frontmatter missing 'description'"))
            else:
                upper = desc.upper()
                if "USE WHEN" not in upper:
                    out.append(("warn", loc, "description has no 'USE WHEN' marker (when should it fire?)"))
                if "DO NOT TRIGGER" not in upper:
                    out.append(("warn", loc, "description has no 'DO NOT TRIGGER' marker (when should it not?)"))

            if archived:
                out.append(("warn", loc, f"archived ({fields['archived'].strip()}) — folder kept, registry row not required"))

            tier = (reg_tiers.get(folder) or fields.get("tier", "")).strip().lower()
            if tier == "guard" and not _HONESTY_RE.search(body):
                out.append(("warn", loc, "guard skill states no limit — add a 'does NOT …' honesty line (tenet 3)"))

        for ref in sorted(set(_SKILL_REF_RE.findall(body))):
            if ref != folder and ref not in known and ref.split("-", 1)[0] in families:
                out.append(("warn", loc, f"references `{ref}` — no such skill folder or registry row (renamed/archived?)"))

        if folder not in reg_names and not archived:
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
