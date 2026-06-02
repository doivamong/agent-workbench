#!/usr/bin/env python3
"""readme_metrics.py — generate (and gate) the README "At a glance" counts.

The metrics block advertises five numbers — dependencies, tests, demos, tools, skills. They are
easy to let rot, and a magnet for merge conflicts when two branches both bump them by hand. This
computes each from the tree and either checks the README matches (``--check``, a CI gate) or
rewrites the numbers in place (``--write``), so reconciling counts after a merge is a deterministic
``--write`` instead of manual arithmetic.

    python tools/readme_metrics.py --check     # exit 1 if any advertised number is stale (CI gate)
    python tools/readme_metrics.py --write      # rewrite the numbers from the tree, in place
    python tools/readme_metrics.py              # print the computed counts (dry)

What it computes:
  - dependencies : 0 — the reusable core is stdlib-only (a fixed claim, surfaced for completeness)
  - tests        : the ``pytest --co -q`` collected count
  - demos        : ``*.py`` under ``examples/``
  - tools        : ``*.py`` under ``tools/`` + ``scripts/secrets_guard.py``
  - skills       : ``SKILL.md`` files under ``.claude/skills/*/``

Honest limit: it gates the NUMBERS, not the prose around them — the tool/skill *lists* and the
skill tier breakdown stay hand-maintained (generating those would churn ordering and couple this
to the registry format). It also cannot judge whether a number *should* have changed — only that
the README matches the tree right now. Stdlib only.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

if sys.stdout is not None and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    except Exception:
        pass

ROOT = Path(__file__).resolve().parents[1]

# (metric key, regex). The number is group 2, flanked by group 1 (prefix) and group 3 (suffix) so
# --write can substitute just the digits. `tests` appears three times (metrics row, Quickstart
# comment, footer) — all three are kept in lockstep.
PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("deps",   re.compile(r"(\| Reusable core dependencies \| \*\*)(\d+)(\*\*)")),
    ("tests",  re.compile(r"(\| Tests \| \*\*)(\d+)(\*\*)")),
    ("demos",  re.compile(r"(\| Runnable demos \| \*\*)(\d+)(\*\*)")),
    ("skills", re.compile(r"(\| Example skills \| \*\*)(\d+)(\*\*)")),
    ("tools",  re.compile(r"(\| Standalone tools \| \*\*)(\d+)(\*\*)")),
    ("tests",  re.compile(r"(python -m pytest -q\s+# )(\d+)( tests)")),
    ("tests",  re.compile(r"(stdlib-only core · )(\d+)( tests · MIT)")),
]


def count_tests(root: Path = ROOT) -> int:
    proc = subprocess.run([sys.executable, "-m", "pytest", "--co", "-q", "tests"],
                          cwd=root, capture_output=True, text=True)
    m = re.search(r"(\d+)\s+tests?\s+collected", proc.stdout)
    if not m:
        raise RuntimeError(f"could not parse the pytest collection summary:\n{proc.stdout[-500:]}")
    return int(m.group(1))


def compute_static(root: Path = ROOT) -> dict[str, int]:
    """The counts that come from the file tree alone (no pytest run) — easy to unit-test."""
    tools = len(list((root / "tools").glob("*.py")))
    if (root / "scripts" / "secrets_guard.py").is_file():
        tools += 1  # secrets_guard lives in scripts/ but is counted as a standalone tool
    return {
        "deps": 0,
        "demos": len(list((root / "examples").glob("*.py"))),
        "tools": tools,
        "skills": len(list((root / ".claude" / "skills").glob("*/SKILL.md"))),
    }


def compute(root: Path = ROOT) -> dict[str, int]:
    return {**compute_static(root), "tests": count_tests(root)}


def find_mismatches(counts: dict[str, int], text: str) -> list[tuple[str, int, int]]:
    """Return (metric, found_in_readme, expected) for every advertised number that is stale."""
    bad: list[tuple[str, int, int]] = []
    for key, rx in PATTERNS:
        for m in rx.finditer(text):
            found = int(m.group(2))
            if found != counts[key]:
                bad.append((key, found, counts[key]))
    return bad


def rewrite(counts: dict[str, int], text: str) -> str:
    for key, rx in PATTERNS:
        text = rx.sub(lambda m: f"{m.group(1)}{counts[key]}{m.group(3)}", text)
    return text


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Generate / gate the README 'At a glance' counts.")
    ap.add_argument("--check", action="store_true", help="exit 1 if any advertised number is stale")
    ap.add_argument("--write", action="store_true", help="rewrite the numbers in README.md from the tree")
    ap.add_argument("--readme", default=str(ROOT / "README.md"), help="path to README.md")
    args = ap.parse_args(argv)

    counts = compute()
    if not (args.check or args.write):
        print("computed counts: " + " · ".join(f"{k}={v}" for k, v in counts.items()))
        return 0

    readme = Path(args.readme)
    text = readme.read_text(encoding="utf-8")

    if args.write:
        new = rewrite(counts, text)
        if new != text:
            readme.write_text(new, encoding="utf-8")
            print(f"updated README counts: " + " · ".join(f"{k}={v}" for k, v in counts.items()))
        else:
            print("README counts already current.")
        return 0

    # --check
    bad = find_mismatches(counts, text)
    if not bad:
        print("README counts match the tree.")
        return 0
    print("README counts are STALE (run `python tools/readme_metrics.py --write`):", file=sys.stderr)
    for key, found, expected in bad:
        print(f"  {key}: README says {found}, tree has {expected}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
