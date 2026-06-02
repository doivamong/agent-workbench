#!/usr/bin/env python3
"""memory_audit.py — a hygiene check for the file-based memory system.

The memory model (see memory/README.md) is governed by human discipline: an index
(MEMORY.md) gates recall, each fact lives in its own file with frontmatter, and
wiki-links cross-reference facts. Nothing enforces any of that — so it silently
rots. This tool is the missing tripwire. It flags, against a memory/ directory:

  ERROR  - a fact file with missing/invalid frontmatter (name, description, type)
  ERROR  - an index line pointing at a file that does not exist (dangling link)
  ERROR  - a [[wiki-link]] that resolves to no known memory name
  WARN   - a fact file not referenced from the index (orphan / cold storage)
  WARN   - the index exceeding its line-count budget (it is loaded every session)
  WARN   - an index entry over the per-line char budget, or facts over a total-KB budget
  WARN   - two facts whose descriptions look near-duplicate (detect-only; you decide to merge)

Usage:
    python tools/memory_audit.py [memory_dir]      # default: ./memory
Exit code is non-zero when any ERROR is found (WARN alone exits 0).

Does NOT: judge whether a memory is *true*, *current*, or *useful* — staleness is a
human call (a fact can name a file that was later deleted). It checks structure and
referential integrity only, not semantics. Stdlib only.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

VALID_TYPES = {"user", "feedback", "project", "reference"}
INDEX_NAME = "MEMORY.md"
SKIP = {INDEX_NAME, "README.md"}
INDEX_MAX_LINES = 200  # the index is loaded every session; keep it small
# The following are tunable starting points, not measured truths — adjust per project.
INDEX_LINE_MAX_CHARS = 200   # a single index entry this long bloats recall (distinct from line COUNT)
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
        if not fm.get("description"):
            out.append(("error", f.name, "frontmatter missing 'description'"))
        else:
            descs.append((f.name, fm["description"]))
        mtype = fm.get("metadata", {}).get("type")
        if mtype not in VALID_TYPES:
            out.append(("error", f.name, f"metadata.type {mtype!r} not in {sorted(VALID_TYPES)}"))
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
    long_entries = [ln for ln in index_text.splitlines() if len(ln) > INDEX_LINE_MAX_CHARS]
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
                            "(possible near-duplicate; merge or differentiate)"))
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Audit the file-based memory for hygiene problems.")
    ap.add_argument("mem_dir", nargs="?", type=Path, default=Path("memory"),
                    help="Path to the memory directory (default: ./memory)")
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
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
