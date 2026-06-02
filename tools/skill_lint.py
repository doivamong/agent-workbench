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
  WARN   - a skill name containing a reserved token ('claude'/'anthropic') — naming a
           skill after the assistant/vendor reads as an impersonation/injection smell
  WARN   - a description with raw angle brackets (`<`/`>`) — it lands verbatim in the
           always-loaded system listing, where stray markup is an injection/noise risk
  WARN   - a description outside a sane length band (too thin to route on / so long it
           bloats the always-loaded listing)
  WARN   - a SKILL.md longer than MAX_SKILL_LINES (push detail into references/)
  WARN   - a relative markdown link in a SKILL.md whose target file doesn't exist
           (a reference deleted/renamed out from under the link)

Usage:
    python tools/skill_lint.py [skills_dir]        # default: .claude/skills
Exit code is non-zero when any ERROR is found (WARN alone does not fail).

Does NOT: judge whether the trigger *wording* is good, or whether two skills truly
overlap — that is the human's call in the registry's Do-NOT-trigger column. It checks
registry/folder consistency and the *presence* of the structural conventions only.
Stdlib only.

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
# A skill name should never impersonate the assistant/vendor (smells like an
# injection or a confused scope). Substring match, case-insensitive.
RESERVED_NAME_TOKENS = ("claude", "anthropic")
# The description is concatenated into the always-loaded skill listing. Too short =
# nothing to route on; too long = it bloats every session's context. Soft band (WARN).
DESC_MIN_CHARS = 30
DESC_MAX_CHARS = 1200
# Registry rows for unwritten skills are intentionally italicised placeholders
# (e.g. `_your-config-guard_`); they have no folder yet, so don't demand one.
_ROW_NAME_RE = re.compile(r"^\|\s*`?_?([A-Za-z0-9][\w-]*)_?`?\s*\|")
_PLACEHOLDER_RE = re.compile(r"^\|\s*[_*]")
_FIELD_RE = re.compile(r"^([A-Za-z_][\w-]*)\s*:\s*(.*)$")
_BLOCK_SCALAR_HEADS = {"|", ">", "|+", "|-", ">+", ">-"}
# Markdown inline link target: the bit inside ](...). Used to find local file links
# whose target no longer exists (a SKILL.md pointing at a deleted references/ file).
_MD_LINK_RE = re.compile(r"\]\(([^)]+)\)")


def dangling_links(skill_md: Path, text: str) -> list[str]:
    """Relative file links in ``text`` whose target doesn't exist (resolved from the
    SKILL.md's own folder). Skips external URLs, mailto:, and pure ``#anchor`` links —
    only local paths are checked, since those are the ones a refactor silently breaks."""
    missing: list[str] = []
    for raw in _MD_LINK_RE.findall(text):
        target = raw.strip().split()[0]  # drop an optional "title" after the path
        target = target.split("#", 1)[0]  # drop a #fragment
        if not target or "://" in target or target.startswith(("#", "mailto:", "tel:")):
            continue
        if not (skill_md.parent / target).exists():
            missing.append(target)
    return missing


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
        loc = f"{folder}/SKILL.md"

        n_lines = text.count("\n") + 1
        if n_lines > MAX_SKILL_LINES:
            out.append(("warn", loc, f"{n_lines} lines (>{MAX_SKILL_LINES}) — move detail into references/"))

        for missing in dangling_links(skill_md, text):
            out.append(("warn", loc, f"link target not found: {missing!r}"))

        fields = parse_frontmatter(text)
        if fields is None:
            out.append(("error", loc, "no/malformed YAML frontmatter (need a '---' fenced block)"))
        else:
            name = fields.get("name", "").strip()
            if not name:
                out.append(("error", loc, "frontmatter missing 'name'"))
            elif name != folder:
                out.append(("warn", loc, f"frontmatter name {name!r} != folder {folder!r}"))
            bad_tok = next((t for t in RESERVED_NAME_TOKENS if t in name.lower()), None)
            if bad_tok:
                out.append(("warn", loc, f"name contains reserved token {bad_tok!r} "
                                         "(don't name a skill after the assistant/vendor)"))

            desc = fields.get("description", "").strip()
            if not desc:
                out.append(("error", loc, "frontmatter missing 'description'"))
            else:
                upper = desc.upper()
                if "USE WHEN" not in upper:
                    out.append(("warn", loc, "description has no 'USE WHEN' marker (when should it fire?)"))
                if "DO NOT TRIGGER" not in upper:
                    out.append(("warn", loc, "description has no 'DO NOT TRIGGER' marker (when should it not?)"))
                if "<" in desc or ">" in desc:
                    out.append(("warn", loc, "description contains raw angle brackets (<>) — "
                                             "they land verbatim in the system skill listing"))
                if not (DESC_MIN_CHARS <= len(desc) <= DESC_MAX_CHARS):
                    out.append(("warn", loc, f"description is {len(desc)} chars "
                                             f"(outside {DESC_MIN_CHARS}-{DESC_MAX_CHARS}; "
                                             "too thin to route on, or bloats the listing)"))

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
