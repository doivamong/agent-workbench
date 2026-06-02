#!/usr/bin/env python3
"""SessionStart hook — inject a compact, tier-ordered skill routing map every session.

Pairs with the `example-using-skills` meta-skill (the routing *method*). This hook supplies
the *data*: it reads `.claude/skills/skill-registry.md` — the single source of truth — and prints
a short "skill → fires when → does NOT fire when" map, ordered by tier (Workflow > Guard > Feature
> Audit), so the agent starts every session already knowing what is available and when each fires.
The map is derived, never hardcoded: add a registry row and it shows up here automatically.

Because this loads into *every* session, the output is kept deliberately compact — that is the
cost lever. Placeholder rows (the italic `_your-thing_` entries) are skipped.

Kill switch:
- SKILL_ROUTING_INJECT=0   — disable (never inject)

Protocol: stdin JSON (cwd) -> stdout JSON (hookSpecificOutput.additionalContext) -> exit 0.
"""
import json
import os
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stdin, "reconfigure"):
    sys.stdin.reconfigure(encoding="utf-8")

sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))
from hook_logger import hook_main  # noqa: E402

# Tier precedence for the routing map (lower index = higher priority). Tiers outside this list
# (e.g. `meta`, or a project's custom tier) are rendered after these, in first-seen order.
TIER_ORDER = ("workflow", "guard", "feature", "audit")
# A markdown table separator row (e.g. ``|----|----|``): only dashes, colons, spaces, pipes.
_SEPARATOR_RE = re.compile(r"^[\s|:-]+$")
# An italic placeholder row whose first cell starts with `_` or `*` (an unwritten skill).
_PLACEHOLDER_RE = re.compile(r"^\|\s*[_*]")


def _cells(row: str) -> list[str]:
    """Split a markdown table row on '|' into trimmed cells (drops the outer empties)."""
    return [c.strip() for c in row.strip().strip("|").split("|")]


def parse_registry_rows(registry_text: str) -> list[dict]:
    """Real (non-placeholder) skill rows from the registry table.

    Each dict has: name, tier (lowercased), fires, not_when. The registry table is
    ``| Skill | Tier | Fires when | Does NOT fire when |``; the header and separator rows
    and any italic ``_placeholder_`` rows are skipped. Pure (text in, list out) so it is
    unit-testable without stdin or the filesystem.
    """
    rows: list[dict] = []
    for line in registry_text.splitlines():
        if not line.startswith("|") or _SEPARATOR_RE.match(line) or _PLACEHOLDER_RE.match(line):
            continue
        cells = _cells(line)
        if len(cells) < 4:
            continue
        name = cells[0].strip("`").strip()
        if not name or name.lower() == "skill":  # header row
            continue
        rows.append({
            "name": name,
            "tier": cells[1].strip("`").strip().lower(),
            "fires": cells[2].strip(),
            "not_when": cells[3].strip(),
        })
    return rows


def build_routing_map(registry_text: str) -> str | None:
    """A compact, tier-ordered routing map, or None if the registry lists no real skills."""
    rows = parse_registry_rows(registry_text)
    if not rows:
        return None

    # Order tiers: the known precedence first, then any leftover tier in first-seen order.
    seen_extra: list[str] = []
    for r in rows:
        if r["tier"] not in TIER_ORDER and r["tier"] not in seen_extra:
            seen_extra.append(r["tier"])
    tier_sequence = list(TIER_ORDER) + seen_extra

    out: list[str] = [
        "[SKILL ROUTING — auto] If a skill might apply (even ~1% chance), invoke it. Tie-break: "
        "Workflow>Guard>Feature>Audit; match the OBJECT not the verb; domain-specific beats "
        "general; if unsure, ask. Source of truth: .claude/skills/skill-registry.md "
        "(see example-using-skills for the full protocol).",
    ]
    for tier in tier_sequence:
        group = [r for r in rows if r["tier"] == tier]
        if not group:
            continue
        out.append("")
        out.append(f"{tier}:")
        for r in group:
            out.append(f"• {r['name']} — fires: {r['fires']} | not: {r['not_when']}")
    return "\n".join(out)


def build_routing_context(skills_dir: Path) -> str | None:
    """Read skill-registry.md under `skills_dir` and return the map to inject, or None.

    Returns None (no injection) when the registry is missing, unreadable, or lists no real
    skills — fail-open, so a session never breaks on a malformed registry.
    """
    registry = skills_dir / "skill-registry.md"
    if not registry.exists():
        return None
    try:
        text = registry.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    return build_routing_map(text)


@hook_main("skill-routing-inject")
def main() -> None:
    if os.environ.get("SKILL_ROUTING_INJECT", "1") == "0":
        print(json.dumps({}))
        sys.exit(0)

    try:
        event = json.load(sys.stdin)
    except Exception:
        event = {}
    cwd = event.get("cwd") or os.environ.get("CLAUDE_PROJECT_DIR") or str(Path.home())

    context = build_routing_context(Path(cwd) / ".claude" / "skills")
    output: dict = {}
    if context:
        output = {"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": context}}
    print(json.dumps(output, ensure_ascii=False))
    sys.exit(0)


if __name__ == "__main__":
    main()
