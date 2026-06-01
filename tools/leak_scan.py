#!/usr/bin/env python3
"""leak_scan.py — a tiny, dependency-free secret/identifier leak scanner.

Two jobs:

1. Catch *generic* leaks that should never be in a public repo: private keys,
   cloud credentials, bot tokens, absolute home paths, real-looking emails.
2. Catch *project-specific* identifiers via an optional, gitignored deny-list
   file (one term/regex per line). This is how you verify a "domain-stripped"
   export without baking your private vocabulary into the public tool itself.

Usage:
    python tools/leak_scan.py .                       # generic patterns only
    python tools/leak_scan.py . --denylist private.txt
    python tools/leak_scan.py src/ --denylist db.txt --fail-on-find

Exit code is non-zero when findings exist and --fail-on-find is set (CI gate).
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# Generic patterns: (name, compiled regex). Tuned for low false-negative on the
# things that actually hurt; some false positives are acceptable for a gate.
GENERIC_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("private_key_block", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |PGP )?PRIVATE KEY-----")),
    ("aws_access_key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("generic_api_key_assign", re.compile(r"(?i)\b(?:api[_-]?key|secret[_-]?key|access[_-]?token|password|passwd|pwd)\b\s*[:=]\s*['\"][^'\"]{8,}['\"]")),
    ("telegram_bot_token", re.compile(r"\b\d{8,10}:[A-Za-z0-9_-]{35}\b")),
    ("slack_token", re.compile(r"\bxox[baprs]-[0-9A-Za-z-]{10,}\b")),
    ("windows_user_path", re.compile(r"[A-Za-z]:\\Users\\[^\\\s'\"]+")),
    ("unix_home_path", re.compile(r"/home/[A-Za-z0-9._-]+|/Users/[A-Za-z0-9._-]+")),
    ("email_address", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")),
]

# Emails that are fine in a public repo (examples, noreply, placeholders).
EMAIL_ALLOW = re.compile(r"@(?:example\.(?:com|org|net)|test\.|localhost|noreply\.)", re.I)

DEFAULT_SKIP_DIRS = {".git", "__pycache__", ".venv", "node_modules", ".pytest_cache", ".mypy_cache"}
TEXT_SUFFIXES = {".py", ".md", ".txt", ".json", ".yaml", ".yml", ".toml", ".ini",
                 ".cfg", ".sh", ".bat", ".js", ".ts", ".html", ".css", ".rst"}


def load_denylist(path: Path) -> list[tuple[str, re.Pattern[str]]]:
    out: list[tuple[str, re.Pattern[str]]] = []
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        try:
            out.append((f"denylist:{line}", re.compile(line, re.I)))
        except re.error:
            # Treat as a literal term if it isn't a valid regex.
            out.append((f"denylist:{line}", re.compile(re.escape(line), re.I)))
    return out


def iter_text_files(root: Path):
    for p in root.rglob("*"):
        if p.is_dir():
            continue
        if any(part in DEFAULT_SKIP_DIRS for part in p.parts):
            continue
        if p.suffix.lower() in TEXT_SUFFIXES or p.suffix == "":
            yield p


def scan_file(path: Path, patterns: list[tuple[str, re.Pattern[str]]]) -> list[tuple[int, str, str]]:
    findings: list[tuple[int, str, str]] = []
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return findings
    for lineno, line in enumerate(text.splitlines(), 1):
        if "leak-scan: ignore" in line:
            continue  # explicit opt-out for intentional samples (like noqa)
        for name, pat in patterns:
            m = pat.search(line)
            if not m:
                continue
            if name == "email_address" and EMAIL_ALLOW.search(m.group(0)):
                continue
            # Redact the matched value in output — never echo the secret itself.
            findings.append((lineno, name, _redact(m.group(0))))
    return findings


def _redact(s: str) -> str:
    if len(s) <= 6:
        return s[0] + "***"
    return s[:3] + "***" + s[-2:]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Scan a tree for leaked secrets/identifiers.")
    ap.add_argument("root", type=Path, help="Directory or file to scan")
    ap.add_argument("--denylist", type=Path, help="Extra project-specific terms/regexes (gitignored)")
    ap.add_argument("--fail-on-find", action="store_true", help="Exit non-zero if any finding")
    args = ap.parse_args(argv)

    patterns = list(GENERIC_PATTERNS)
    if args.denylist:
        patterns += load_denylist(args.denylist)

    root = args.root
    files = [root] if root.is_file() else list(iter_text_files(root))

    total = 0
    for f in files:
        for lineno, name, redacted in scan_file(f, patterns):
            total += 1
            print(f"{f}:{lineno}: [{name}] {redacted}")

    print(f"\n{total} finding(s) across {len(files)} file(s).")
    if total and args.fail_on_find:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
