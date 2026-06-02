#!/usr/bin/env python3
"""check_requirements_diff.py — warn (never block) when a commit adds a new dependency.

A new line in `requirements.txt` doesn't fail at commit time — it fails later, at import,
wherever the dependency wasn't installed (CI image, a prod venv, a teammate's machine). This
is a pre-commit *seatbelt*: it reads the staged diff of the requirements file, and if the
commit adds package(s), it prints a one-line reminder to install them where the code runs.
It exits 0 either way — adding a dep you'll install on the next deploy is legitimate, so this
never blocks the commit.

Usage (as a pre-commit hook, which passes changed files as args):
    python tools/check_requirements_diff.py [files...]
    python tools/check_requirements_diff.py --file requirements/prod.txt

Kill switch: REQUIREMENTS_DIFF_GUARD=0 disables it. Stdlib only.
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

DEFAULT_REQUIREMENTS = "requirements.txt"
# A real package line: "+numpy>=1.24", "+django==4.2", "+ollama". NOT "+++ header",
# "+# comment", or "+   " (whitespace). The leading + is the diff add-marker.
PACKAGE_LINE_RE = re.compile(r"^\+([A-Za-z0-9_][A-Za-z0-9_.\-]*)\s*([<>=!~].*)?$")


def get_staged_diff(file_path: str, cwd: Path | None = None) -> str:
    """Return `git diff --cached -U0` for file_path, or '' on any failure / non-repo."""
    try:
        r = subprocess.run(
            ["git", "diff", "--cached", "--unified=0", "--", file_path],
            capture_output=True, text=True, cwd=cwd or Path.cwd(), timeout=10,
        )
        return r.stdout if r.returncode == 0 else ""
    except (subprocess.SubprocessError, OSError):
        return ""


def parse_added_packages(diff: str) -> list[str]:
    """Package names added in a unified diff (skips the +++ header, comments, blank lines)."""
    added: list[str] = []
    for line in diff.splitlines():
        if line.startswith("+++") or not line.startswith("+"):
            continue
        body = line[1:].strip()
        if not body or body.startswith("#"):
            continue
        m = PACKAGE_LINE_RE.match(line)
        if m:
            added.append(m.group(1))
    return added


def render_warning(added: list[str], req_file: str) -> str:
    """The reminder text for a set of newly added packages (pure, for tests/demo)."""
    bar = "=" * 70
    lines = [bar, f"WARN: {req_file} adds {len(added)} new dependency(ies):"]
    lines += [f"  + {pkg}" for pkg in added]
    lines += [
        "",
        "Remember to install them everywhere this code runs — CI images, any prod/served",
        "virtualenv, teammates' environments. A dependency that isn't installed fails at",
        "import time (not at commit time), often long after this change lands.",
        "",
        "This is a reminder, not a blocker. Disable with REQUIREMENTS_DIFF_GUARD=0.",
        bar,
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Warn (never block) when a commit adds a dependency.")
    ap.add_argument("files", nargs="*", help="changed files (a pre-commit hook passes these)")
    ap.add_argument("--file", default=DEFAULT_REQUIREMENTS, help=f"requirements file (default: {DEFAULT_REQUIREMENTS})")
    args = ap.parse_args(argv)

    if os.environ.get("REQUIREMENTS_DIFF_GUARD") == "0":
        return 0

    req = args.file
    # If the hook told us which files changed, only act when the requirements file is among them.
    if args.files and not any(req in p for p in args.files):
        return 0

    added = parse_added_packages(get_staged_diff(req))
    if added:
        print(render_warning(added, req))
    return 0  # WARN only — never blocks


if __name__ == "__main__":
    raise SystemExit(main())
