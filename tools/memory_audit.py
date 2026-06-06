#!/usr/bin/env python3
"""memory_audit.py — a hygiene check for the file-based memory system.

The memory model (see memory/README.md) is governed by human discipline: an index
(MEMORY.md) gates recall, each fact lives in its own file with frontmatter, and
wiki-links cross-reference facts. Nothing enforces any of that — so it silently
rots. This tool is the missing tripwire. It flags, against a memory/ directory:

  ERROR  - a fact file with missing/invalid frontmatter (name, description, type)
  ERROR  - an index line pointing at a file that does not exist (dangling link)
  WARN   - a fact using a flat top-level 'type:' (canonical is nested metadata.type)
  WARN   - a fact whose name does not match its filename under kebab/underscore folding
  WARN   - a [[wiki-link]] that resolves to no known memory name
  WARN   - a fact file not referenced from the index (orphan / cold storage)
  WARN   - the index over its line-count OR byte-size budget, or in the early margin nearing it
  WARN   - an index entry over the per-line char budget, or facts over a total-KB budget
  WARN   - two facts whose descriptions look near-duplicate (detect-only; you decide to merge)

Usage:
    python tools/memory_audit.py [memory_dir]                       # default: ./memory
    python tools/memory_audit.py [memory_dir] --promotion-readiness  # + opt-in group report
Exit code is non-zero when any ERROR is found (WARN alone exits 0). The opt-in, default-OFF
--promotion-readiness flag adds a read-only report that buckets facts by an optional
metadata.group field (NEVER by name); it changes neither the exit code nor the default audit
output. See docs/memory-governance.md §4.

Does NOT: judge whether a memory is *true*, *current*, or *useful* — staleness is a
human call (a fact can name a file that was later deleted). It checks structure and
referential integrity only, not semantics. Stdlib only.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

try:  # tools/ on sys.path: a direct script run, or the test suite (see tests/conftest.py)
    from memory_budget import INDEX_MAX_BYTES, INDEX_MAX_LINES  # shared load budget — never re-declare
except ModuleNotFoundError:  # imported as a package, e.g. `from tools.memory_audit import ...` in a demo
    from tools.memory_budget import INDEX_MAX_BYTES, INDEX_MAX_LINES

VALID_TYPES = {"user", "feedback", "project", "reference"}
INDEX_NAME = "MEMORY.md"
SKIP = {INDEX_NAME, "README.md"}
# INDEX_MAX_BYTES / INDEX_MAX_LINES come from memory_budget (shared with memory_recall_doctor, so the
# two can never drift). The rest are tunable starting points, not measured truths — adjust per project.
INDEX_LINE_MAX_CHARS = 200   # a single index entry this long bloats recall (distinct from line COUNT)
INDEX_SOFT_RATIO = 0.8       # early-margin: WARN once the index reaches this fraction of the byte
                             # budget — a margin to act BEFORE the 100% truncation boundary, derived
                             # from the imported INDEX_MAX_BYTES (never a re-declared budget)
TOTAL_FACTS_MAX_KB = 128     # total on-disk size of all fact files (on-demand, but a bloat signal)
NEAR_DUP_JACCARD = 0.7       # description token overlap above which two facts look like duplicates
WIKILINK_RE = re.compile(r"\[\[([^\]]+)\]\]")


def _desc_tokens(description: str) -> set[str]:
    """Lowercased word tokens of a description, for similarity comparison."""
    return set(re.findall(r"[a-z0-9]+", description.lower()))


def _jaccard(a: set[str], b: set[str]) -> float:
    """Jaccard similarity of two token sets (0.0 when either is empty)."""
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def parse_frontmatter(text: str) -> dict | None:
    """Minimal frontmatter parser for the kit's fixed format (no YAML dependency)."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    close = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
    if close is None:
        return None
    fm: dict = {"metadata": {}}
    in_meta = False
    for line in lines[1:close]:
        if not line.strip():
            continue
        indented = line[0] in (" ", "\t")
        if indented and in_meta and ":" in line:
            k, v = line.strip().split(":", 1)
            fm["metadata"][k.strip()] = v.strip()
            continue
        if ":" in line:
            k, v = line.split(":", 1)
            key = k.strip()
            if key == "metadata":
                in_meta = True
                continue
            in_meta = False
            fm[key] = v.strip()
    return fm


def audit(mem_dir: Path) -> list[tuple[str, str, str]]:
    """Return a list of (severity, file, message). severity in {'error','warn'}."""
    out: list[tuple[str, str, str]] = []
    index = mem_dir / INDEX_NAME
    index_text = index.read_text(encoding="utf-8", errors="replace") if index.exists() else ""
    if not index.exists():
        out.append(("error", INDEX_NAME, "no MEMORY.md index found"))

    fact_files = sorted(p for p in mem_dir.glob("*.md") if p.name not in SKIP)
    names: dict[str, str] = {}  # frontmatter name -> filename
    descs: list[tuple[str, str]] = []  # (filename, description) for near-dup detection
    total_bytes = 0

    for f in fact_files:
        raw = f.read_text(encoding="utf-8", errors="replace")
        total_bytes += len(raw.encode("utf-8"))
        fm = parse_frontmatter(raw)
        if fm is None:
            out.append(("error", f.name, "missing or malformed frontmatter block"))
            continue
        if not fm.get("name"):
            out.append(("error", f.name, "frontmatter missing 'name'"))
        else:
            names[fm["name"]] = f.name
            # Identity (advisory): the name should equal the filename stem under kebab<->underscore
            # folding (the kit's convention: name 'feedback-x' <-> file 'feedback_x.md'). Drift means
            # a [[wiki-link]] by name and the file can diverge. WARN, never ERROR — real corpora use
            # free-text names this cannot bind, and the kit cannot rename a read-only source corpus.
            if fm["name"].strip().replace("_", "-").lower() != f.stem.replace("_", "-").lower():
                out.append(("warn", f.name,
                            f"frontmatter name {fm['name']!r} does not match filename stem "
                            f"{f.stem!r} under kebab/underscore folding"))
        if not fm.get("description"):
            out.append(("error", f.name, "frontmatter missing 'description'"))
        else:
            descs.append((f.name, fm["description"]))
        # Type may be canonical nested (metadata.type) or flat top-level (type:) — the latter is the
        # shape some source corpora ship (e.g. one migrated in). Prefer nested when present so a real
        # nested error is never masked by a stray flat key; fall back to flat, and flag the flat form.
        nested_type = fm.get("metadata", {}).get("type")
        flat_type = fm.get("type")
        mtype = nested_type if nested_type is not None else flat_type
        if mtype not in VALID_TYPES:
            out.append(("error", f.name,
                        f"type {mtype!r} not in {sorted(VALID_TYPES)} (set metadata.type or top-level type)"))
        elif nested_type is None and flat_type is not None:
            out.append(("warn", f.name,
                        "uses flat top-level 'type:'; canonical form is nested 'metadata.type'"))
        if f.name not in index_text:
            out.append(("warn", f.name, "not referenced in MEMORY.md (orphan / cold storage)"))

    # dangling index links: a [foo](file.md) whose target is missing
    for target in re.findall(r"\]\(([^)]+\.md)\)", index_text):
        name = target.split("/")[-1]
        if name not in SKIP and not (mem_dir / name).exists():
            out.append(("error", INDEX_NAME, f"index links a missing file: {target}"))

    # dangling wiki-links across all facts
    for f in fact_files:
        for link in WIKILINK_RE.findall(f.read_text(encoding="utf-8", errors="replace")):
            if link not in names:
                out.append(("warn", f.name, f"[[{link}]] resolves to no known memory name"))

    index_lines = len(index_text.splitlines())
    if index_lines > INDEX_MAX_LINES:
        out.append(("warn", INDEX_NAME,
                    f"index is {index_lines} lines (> {INDEX_MAX_LINES}); it loads every session"))

    # Per-entry char budget — distinct from the line COUNT above: one overlong line bloats recall.
    # Computed first so the byte-pressure WARN below can name the over-cap entries as the lever.
    long_entries = [ln for ln in index_text.splitlines() if len(ln) > INDEX_LINE_MAX_CHARS]

    # Byte size — distinct from line count: a short index of long lines can still blow the load
    # budget. This is the truncation that silently drops later entries from recall. Graduated: a
    # hard WARN once the boundary is crossed, and ONE aggregate early-margin WARN before it, so the
    # pressure surfaces while there is still room to act — not only after recall has truncated. (Not
    # a third independent byte-check: it is the same byte gate, reported earlier; see governance §7.)
    index_bytes = len(index_text.encode("utf-8"))
    budget_pct = index_bytes / INDEX_MAX_BYTES * 100
    if index_bytes > INDEX_MAX_BYTES:
        out.append(("warn", INDEX_NAME,
                    f"index is {index_bytes / 1024:.0f} KB (> {INDEX_MAX_BYTES / 1024:.0f} KB); the "
                    "session-start load truncates near here, silently dropping later entries; "
                    "archive stale project facts to recover budget (governance section 7)"))
    elif budget_pct >= INDEX_SOFT_RATIO * 100:
        if long_entries:
            lever = (f"{len(long_entries)} over-cap "
                     f"{'entry is' if len(long_entries) == 1 else 'entries are'} the lever - "
                     "tighten those hooks (or archive a cold fact)")
        else:
            lever = "tighten the longest hooks or archive a cold fact"
        out.append(("warn", INDEX_NAME,
                    f"index is at {budget_pct:.0f}% of the {INDEX_MAX_BYTES / 1024:.0f} KB load "
                    "budget - an early margin, NOT the truncation boundary (that is 100%, where "
                    f"later entries silently drop from recall); {lever} to recover headroom now "
                    "(governance section 7)"))

    if long_entries:
        word = "entry" if len(long_entries) == 1 else "entries"
        out.append(("warn", INDEX_NAME,
                    f"{len(long_entries)} index {word} exceed {INDEX_LINE_MAX_CHARS} chars; "
                    "keep each line one terse fact"))

    total_kb = total_bytes / 1024
    if total_kb > TOTAL_FACTS_MAX_KB:
        out.append(("warn", "(total)",
                    f"fact files total {total_kb:.0f} KB (> {TOTAL_FACTS_MAX_KB} KB); "
                    "consider archiving cold facts"))

    # Near-duplicate descriptions (detect-only — a human decides whether to merge).
    token_sets = [(name, _desc_tokens(d)) for name, d in descs]
    for i in range(len(token_sets)):
        for j in range(i + 1, len(token_sets)):
            sim = _jaccard(token_sets[i][1], token_sets[j][1])
            if sim >= NEAR_DUP_JACCARD:
                out.append(("warn", token_sets[i][0],
                            f"description ~{sim * 100:.0f}% similar to {token_sets[j][0]} "
                            "(possible near-duplicate; merge, differentiate, or run the external "
                            "consolidate-memory pass; governance section 7)"))
    return out


def promotion_readiness(mem_dir: Path) -> list[str]:
    """Read-only: bucket fact files by an optional metadata.group, report group sizes.

    Opt-in and advisory. Buckets by ``metadata.group`` ONLY — NEVER by ``name``. ``name`` is
    unique per fact, so bucketing by it yields groups of one and surfaces nothing; that is the
    exact wreck (a dedup key doubling as a unique id) documented in docs/memory-governance.md §6.
    A group's size counts FILES, not distinct sessions, so it cannot prove a lesson recurred — it
    is a readiness hint a human weighs, never an auto-trigger. Writes nothing. ASCII output.
    """
    groups: dict[str, list[str]] = {}
    for f in sorted(p for p in mem_dir.glob("*.md") if p.name not in SKIP):
        fm = parse_frontmatter(f.read_text(encoding="utf-8", errors="replace"))
        if fm is None:
            continue
        group = fm.get("metadata", {}).get("group")
        if isinstance(group, str) and group.strip():
            groups.setdefault(group.strip(), []).append(f.name)
    if not groups:
        return ["promotion grouping INACTIVE (no metadata.group present)"]
    out: list[str] = []
    for key in sorted(groups):
        out.append(f"group {key}: {len(groups[key])} member files - counts files, not distinct "
                   "sessions; cannot prove recurrence")
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Audit the file-based memory for hygiene problems.")
    ap.add_argument("mem_dir", nargs="?", type=Path, default=Path("memory"),
                    help="Path to the memory directory (default: ./memory)")
    ap.add_argument("--promotion-readiness", action="store_true",
                    help="Also print a read-only report bucketing facts by metadata.group "
                         "(opt-in, default off; never groups by name; writes nothing).")
    args = ap.parse_args(argv)

    if not args.mem_dir.is_dir():
        print(f"Not a directory: {args.mem_dir}", file=sys.stderr)
        return 2

    findings = audit(args.mem_dir)
    for sev, name, msg in findings:
        print(f"[{sev}] {name}: {msg}")
    errors = sum(1 for sev, _, _ in findings if sev == "error")
    warns = len(findings) - errors
    print(f"\n{errors} error(s), {warns} warning(s).")

    if args.promotion_readiness:
        print("\npromotion-readiness (read-only; buckets by metadata.group):")
        for line in promotion_readiness(args.mem_dir):
            print(line)

    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
