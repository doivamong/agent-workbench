#!/usr/bin/env python3
"""invariants.py — a tiny framework for "rules that must never break".

The idea: a long-lived codebase accumulates rules an AI agent (or a tired human)
keeps re-breaking — "never hardcode an absolute path", "never use raw SQL for X",
"config keys are always two levels deep". Instead of hoping code review catches
them, codify each rule as a fast, greppable check and run it as a pre-commit/CI
gate. Fast (line scans, no imports of project code) so it can run on every commit.

This file is the *framework* + a few illustrative invariants. Replace the sample
invariants in `SAMPLE_INVARIANTS` with your own.

Usage:
    python tools/invariants.py <dir>
    python tools/invariants.py <dir> --allow known_violations.json   # grandfather legacy
    python tools/invariants.py <dir> --update-allow known_violations.json  # snapshot current

Exit code is non-zero when a NEW violation (not in the allow-list) is found.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

# --------------------------------------------------------------------------- #
# Core types
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Violation:
    invariant: str
    path: str
    line: int
    message: str

    def key(self) -> str:
        """Stable identity for allow-listing (path + invariant + message,
        deliberately NOT the line number so edits above don't churn it)."""
        raw = f"{self.path}::{self.invariant}::{self.message}"
        return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]


# A check receives (relative_path, file_text) and yields Violations.
CheckFn = Callable[[str, str], "list[Violation]"]


@dataclass(frozen=True)
class Invariant:
    id: str
    description: str
    check: CheckFn
    severity: str = "error"  # "error" | "warn"


# --------------------------------------------------------------------------- #
# Helpers for writing line-based checks concisely
# --------------------------------------------------------------------------- #


def line_regex(invariant_id: str, pattern: str, message: str) -> CheckFn:
    """Build a check that flags every line matching `pattern`."""
    rx = re.compile(pattern)

    def _check(path: str, text: str) -> list[Violation]:
        out: list[Violation] = []
        for i, line in enumerate(text.splitlines(), 1):
            if "inv: ignore" in line:
                continue  # explicit opt-out for intentional samples (like noqa)
            if rx.search(line):
                out.append(Violation(invariant_id, path, i, message))
        return out

    return _check


def config_nested_access(parent: str, nested_keys: set[str], accessor: str = "get") -> CheckFn:
    """Flag reading a *nested* config key at the top level — the silent-None trap.

    The deterministic half of the config-access guard (see the awb-config-guard skill).
    A key that lives under `parent` must be read two levels deep — ``cfg.get(parent, {}).get(key)``.
    Read flat — ``cfg.get(key)`` — it returns ``None`` silently, and the crash surfaces far away
    downstream as an ``AttributeError`` on ``None``. A bypassable skill can *remind* you of this;
    only an always-run check can *guarantee* it never ships, which is why it lives here.

    Heuristic: flag a line that accesses one of `nested_keys` via ``.<accessor>("key")`` while the
    `parent` container is not named as a quoted key (``"parent"``) on that same line — the correct
    two-level form spells the parent out, so it is not flagged. Matching the *quoted* parent (not a
    bare substring) avoids a false pass when the parent's name happens to be a substring of the key.
    A line scan, so it can still miss multi-line access — annotate a deliberate exception with
    ``inv: ignore``.
    """
    key_alt = "|".join(re.escape(k) for k in sorted(nested_keys))
    rx = re.compile(rf'\.{re.escape(accessor)}\(\s*["\'](?:{key_alt})["\']') if nested_keys else None
    parent_tokens = (f'"{parent}"', f"'{parent}'")

    def _check(path: str, text: str) -> list[Violation]:
        out: list[Violation] = []
        if rx is None:
            return out
        for i, line in enumerate(text.splitlines(), 1):
            if "inv: ignore" in line:
                continue
            if rx.search(line) and not any(tok in line for tok in parent_tokens):
                out.append(Violation(
                    "config-flat-access", path, i,
                    f"Nested config key read flat — use .{accessor}('{parent}', {{}}).{accessor}('...'). "
                    "Flat access returns None silently.",
                ))
        return out

    return _check


# --------------------------------------------------------------------------- #
# Sample invariants — REPLACE THESE with your project's real rules
# --------------------------------------------------------------------------- #

SAMPLE_INVARIANTS: list[Invariant] = [
    Invariant(
        id="no-absolute-path",
        description="Source must not contain machine-specific absolute paths.",
        check=line_regex(
            "no-absolute-path",
            r"(?:[A-Za-z]:\\Users\\|/home/[A-Za-z0-9._-]+/|/Users/[A-Za-z0-9._-]+/)",
            "Hardcoded absolute path - use a config value or relative path.",
        ),
    ),
    Invariant(
        id="todo-needs-owner",
        description="Every TODO/FIXME must name an owner so it isn't orphaned.",
        severity="warn",
        check=line_regex(
            "todo-needs-owner",
            r"(?i)\b(?:TODO|FIXME)\b(?!\s*\([^)]+\))",
            "TODO/FIXME without an owner - write TODO(name): ...",
        ),
    ),
    Invariant(
        id="no-print-in-lib",
        description="Library code should log, not print (demo rule).",
        severity="warn",
        check=line_regex(
            "no-print-in-lib",
            r"^\s*print\(",
            "Bare print() in library code - use logging.",
        ),
    ),
    Invariant(
        id="config-flat-access",
        description="A nested config key must be read two levels deep, never flat (silent-None trap).",
        # error, not warn: the whole point of reclassifying this guard out of a bypassable skill is
        # that the silent-None bug must ALWAYS be caught. Fires on nothing in this repo — the sample
        # parent/keys below are placeholders; replace them with your project's real config shape.
        check=config_nested_access(
            parent="config_section",       # REPLACE: your container key (e.g. the schema/contract block)
            nested_keys={"inner_value"},   # REPLACE: the keys that live *under* that container
        ),
    ),
]

# --------------------------------------------------------------------------- #
# Runner
# --------------------------------------------------------------------------- #

SKIP_DIRS = {".git", "__pycache__", ".venv", "node_modules", ".pytest_cache"}
SCAN_SUFFIXES = {".py"}


def iter_files(root: Path, suffixes: set[str] | None = None):
    suffixes = suffixes or SCAN_SUFFIXES
    for p in root.rglob("*"):
        if p.is_dir() or any(part in SKIP_DIRS for part in p.parts):
            continue
        if p.suffix in suffixes:
            yield p


def run(root: Path, invariants: list[Invariant], suffixes: set[str] | None = None) -> list[Violation]:
    found: list[Violation] = []
    for f in iter_files(root, suffixes):
        try:
            text = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        rel = str(f.relative_to(root)).replace("\\", "/")
        for inv in invariants:
            found.extend(inv.check(rel, text))
    return found


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Run codebase invariants.")
    ap.add_argument("root", type=Path)
    ap.add_argument("--allow", type=Path, help="JSON allow-list of grandfathered violation keys")
    ap.add_argument("--update-allow", type=Path, help="Write current violations to this allow-list and exit 0")
    ap.add_argument("--suffixes", help="Comma-separated file extensions to scan (default: .py). "
                                       "e.g. --suffixes .py,.yaml,.sh to cover non-Python files too")
    args = ap.parse_args(argv)

    suffixes = None
    if args.suffixes:
        suffixes = {s if s.startswith(".") else f".{s}" for s in args.suffixes.split(",") if s.strip()}

    violations = run(args.root, SAMPLE_INVARIANTS, suffixes)

    if args.update_allow:
        keys = sorted({v.key() for v in violations})
        args.update_allow.write_text(json.dumps(keys, indent=2), encoding="utf-8")
        print(f"Wrote {len(keys)} grandfathered key(s) to {args.update_allow}.")
        return 0

    allowed: set[str] = set()
    if args.allow and args.allow.exists():
        allowed = set(json.loads(args.allow.read_text(encoding="utf-8")))

    new = [v for v in violations if v.key() not in allowed]
    by_sev = {inv.id: inv.severity for inv in SAMPLE_INVARIANTS}

    for v in new:
        sev = by_sev.get(v.invariant, "error")
        print(f"[{sev}] {v.path}:{v.line}: ({v.invariant}) {v.message}")

    errors = [v for v in new if by_sev.get(v.invariant) == "error"]
    print(f"\n{len(new)} new violation(s) ({len(errors)} error, {len(new) - len(errors)} warn); "
          f"{len(allowed)} grandfathered.")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
