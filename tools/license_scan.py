#!/usr/bin/env python3
"""license_scan.py — a tiny, dependency-free license/attribution tripwire.

Before you vendor a snippet, copy a file, or adopt a dependency, run this over it. It greps for the
textual markers that say "this came from somewhere with terms" — OSS license names, copyright lines,
"adapted from / derived from" attributions, non-commercial / proprietary notices — and flags each
with what it implies for reuse. The point is to break the "I'll just copy this, it's probably fine"
reflex *before* third-party code lands in your repo under the wrong assumption.

It is a **tripwire, not a license scanner**: it reads MARKERS, not meaning. It does NOT identify the
true license (that's an SPDX-detector / a human job), and — the expensive blind spot — it cannot see
code that was *copied with no marker at all*. **A clean result is not proof of original authorship**;
it means only that no marker was found. Always verify provenance by eye for anything you didn't write.

This kit learned that the hard way: a marker list once silently passed an Apache-2.0-derived file
because it had no pattern for "Apache" — a coverage blind spot. The markers below are only ever as
good as the list, which is exactly why the honest limit above is load-bearing, not boilerplate. See
the companion rule [`.claude/rules/measurement-honesty.md`](../.claude/rules/measurement-honesty.md):
a green check is not a gate.

Usage:
    python tools/license_scan.py path/to/file.py        # one file
    python tools/license_scan.py vendor/                 # a directory tree
    python tools/license_scan.py . --fail-on-find        # CI gate (non-zero on any marker)
    python tools/license_scan.py vendor/ --quiet         # print only the flagged file paths

Exit code is non-zero when markers are found AND --fail-on-find is set.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

if sys.stdout is not None and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    except Exception:
        pass

# (label, compiled regex, what a hit implies for REUSE). Ordered strongest-restriction first.
# Markers are textual: a hit means "verify before reuse", never a definitive classification. Some
# false positives are expected and acceptable — over-flagging is the safe direction for a tripwire.
MARKERS: list[tuple[str, re.Pattern[str], str]] = [
    ("proprietary / all-rights-reserved",
     re.compile(r"all rights reserved|proprietary|confidential|do not redistribute|no[\s-]?redistribut", re.I),
     "do NOT copy without explicit written permission"),
    ("commercial / paid license",
     re.compile(r"commercial license|paid license|license required|\bEULA\b", re.I),
     "review the commercial terms before any reuse"),
    ("non-commercial (CC BY-NC / similar)",
     re.compile(r"cc[\s_-]?by[\s_-]?nc|creative\s+commons|non[\s-]?commercial", re.I),
     "cannot ship in a commercial product — re-implement first-principles or drop"),
    ("copyleft (GPL / AGPL / LGPL / MPL / EPL)",
     re.compile(r"\bagpl|\blgpl|\bgpl|mozilla public|eclipse public|\bMPL\b", re.I),
     "viral — may force your whole project's license; check compatibility before vendoring"),
    ("permissive OSS (MIT / Apache / BSD / ISC / zlib)",
     re.compile(r"\bMIT\b|\bapache\b|\bBSD\b|\bISC\b|\bzlib\b|\bunlicense\b", re.I),
     "reuse OK, but keep the license + attribution notice (e.g. a NOTICES file)"),
    ("SPDX license tag",
     re.compile(r"SPDX-License-Identifier", re.I),
     "read the declared identifier and honor it"),
    ("third-party copyright",
     re.compile(r"copyright\s+(?:\(c\)|©|\d{4}|[A-Z])", re.I),
     "someone holds rights — verify the owner and the license"),
    ("attribution / provenance phrase",
     re.compile(r"adapted from|derived from|ported from|\bport of\b|forked from|borrowed from|"
                r"lifted from|salvag(?:e|ed)|vendored from|copied from", re.I),
     "traces to an upstream source — find it and check its license"),
]

DEFAULT_SKIP_DIRS = {".git", "__pycache__", ".venv", "node_modules", ".pytest_cache",
                     ".mypy_cache", ".porting"}
TEXT_SUFFIXES = {".py", ".md", ".txt", ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg",
                 ".sh", ".js", ".ts", ".tsx", ".jsx", ".html", ".css", ".rst", ".go",
                 ".rs", ".java", ".c", ".h", ".cpp", ".rb"}


def scan_text(text: str) -> list[tuple[str, int, str, str]]:
    """Return (label, line_number, excerpt, implication) for each marker found.

    At most one hit per marker (the first), so a file with many copyright lines reports the marker
    once rather than flooding the output."""
    hits: list[tuple[str, int, str, str]] = []
    lines = text.splitlines()
    for label, rx, implies in MARKERS:
        for i, line in enumerate(lines, 1):
            if rx.search(line):
                hits.append((label, i, line.strip()[:120], implies))
                break
    return hits


def iter_files(root: Path):
    """Yield scannable text files under root (or root itself if it is a file)."""
    if root.is_file():
        yield root
        return
    for p in sorted(root.rglob("*")):
        if (p.is_file() and p.suffix.lower() in TEXT_SUFFIXES
                and not any(part in DEFAULT_SKIP_DIRS for part in p.parts)):
            yield p


def scan_path(root: Path) -> dict[Path, list[tuple[str, int, str, str]]]:
    """Scan a file or directory; return {file: hits} only for files with at least one marker."""
    out: dict[Path, list[tuple[str, int, str, str]]] = {}
    for f in iter_files(root):
        try:
            text = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        hits = scan_text(text)
        if hits:
            out[f] = hits
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Heuristic license/attribution marker tripwire (NOT a license determination).")
    ap.add_argument("path", help="File or directory to scan.")
    ap.add_argument("--quiet", action="store_true", help="Print only the flagged file paths.")
    ap.add_argument("--fail-on-find", action="store_true",
                    help="Exit non-zero if any marker is found (use as a CI gate).")
    args = ap.parse_args(argv)

    root = Path(args.path)
    if not root.exists():
        print(f"ERROR: no such path: {root}", file=sys.stderr)
        return 2

    results = scan_path(root)
    total = sum(len(v) for v in results.values())

    for f in sorted(results):
        if args.quiet:
            print(f)
            continue
        print(f"\n{f}")
        for label, lineno, excerpt, implies in results[f]:
            print(f"  [{label}] line {lineno}: {excerpt!r}")
            print(f"      -> {implies}")

    print(f"\n{total} marker(s) across {len(results)} file(s). Heuristic only — a clean result is "
          "NOT proof of original authorship; verify provenance by eye.", file=sys.stderr)

    if total and args.fail_on_find:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
