#!/usr/bin/env python3
"""leak_scan.py — a tiny, dependency-free secret/identifier leak scanner.

Two jobs:

1. Catch *generic* leaks that should never be in a public repo: private keys,
   cloud credentials, bot tokens, absolute home paths, real-looking emails.
2. Catch *project-specific* identifiers via an optional, gitignored deny-list
   file (one term/regex per line). This is how you verify a "domain-stripped"
   export without baking your private vocabulary into the public tool itself.

It is a line-based *tripwire*, not a vault: pass --entropy for an extra (opt-in,
higher-false-positive) pass that flags high-entropy base64/hex tokens a keyword
scan would miss — useful for a deeper sweep before publishing.

Opt-out: a trailing `# leak-scan: ignore` silences soft/heuristic detectors on that
line. High-confidence secrets (private keys, AWS/Slack/Telegram tokens) are NOT
silenced by a bare marker — those require a named opt-out (`# leak-scan: ignore[aws_access_key]`)
so a real credential can never be hidden by an accidental or blanket comment.

Usage:
    python tools/leak_scan.py .                       # generic patterns only
    python tools/leak_scan.py . --denylist private.txt
    python tools/leak_scan.py src/ --denylist db.txt --fail-on-find
    python tools/leak_scan.py . --entropy --fail-on-find   # + high-entropy sweep

Exit code is non-zero when findings exist and --fail-on-find is set (CI gate).
"""
from __future__ import annotations

import argparse
import math
import re
import string
import sys
from collections import Counter
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

# High-confidence "real secret" detectors. A *bare* `leak-scan: ignore` must NOT be
# able to silence these — there is no legitimate reason to commit a real one with a
# blanket opt-out. Suppressing one requires naming it explicitly, e.g.
# `# leak-scan: ignore[aws_access_key]`, which is a conscious, greppable, reviewable
# act (used only for intentional test fixtures). This closes the hole where any line
# could hide an AWS key / private key behind a trailing comment.
HARD_PATTERNS = frozenset({
    "private_key_block", "aws_access_key", "telegram_bot_token", "slack_token",
})

# Inline opt-out: "leak-scan: ignore" (bare) or "leak-scan: ignore[name1,name2]" (scoped).
_IGNORE_RE = re.compile(r"leak-scan:\s*ignore(?:\[([^\]]*)\])?")

# Cross-line secret assignment: a keyword and its quoted value separated by
# newlines/parentheses, e.g. `api_key = (\n  "abc12345"\n)`. The per-line scan
# (generic_api_key_assign) cannot see this; --multiline catches it. Soft detector.
_MULTILINE_ASSIGN_RE = re.compile(
    r"(?i)\b(?:api[_-]?key|secret[_-]?key|access[_-]?token|password|passwd|pwd)\b"
    r"\s*[:=]\s*[\(\[]?\s*['\"][^'\"\n]{8,}['\"]"  # value itself stays on one line; only the gap may wrap
)

DEFAULT_SKIP_DIRS = {".git", "__pycache__", ".venv", "node_modules", ".pytest_cache",
                     ".mypy_cache", ".porting"}
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


def _parse_ignore(line: str) -> tuple[bool, set[str]]:
    """Parse an inline opt-out comment.

    Returns ``(suppress_soft, named)`` where:
      - "# leak-scan: ignore"            -> (True, set())       silence soft detectors
      - "# leak-scan: ignore[a, b]"      -> (False, {"a","b"})  silence only the named ones
      - (no marker)                      -> (False, set())
    A bare marker never silences a HARD_PATTERNS detector; a scoped marker can, but only
    when it names it explicitly.
    """
    m = _IGNORE_RE.search(line)
    if not m:
        return False, set()
    scoped = m.group(1)
    if scoped is not None:
        return False, {n.strip() for n in scoped.split(",") if n.strip()}
    return True, set()


def _suppressed(name: str, suppress_soft: bool, named: set[str]) -> bool:
    """Decide whether a finding of detector ``name`` is silenced by the line's opt-out."""
    explicit = name in named or any(name.startswith(n) for n in named)
    if name in HARD_PATTERNS:
        return explicit  # hard secrets: only a named opt-out can silence them
    return suppress_soft or explicit


def _multiline_findings(text: str) -> list[tuple[int, str, str]]:
    """Flag secret assignments whose quoted value sits on a later line than the
    keyword — the cross-line blind spot the per-line scan cannot see."""
    out: list[tuple[int, str, str]] = []
    lines = text.splitlines()
    for m in _MULTILINE_ASSIGN_RE.finditer(text):
        frag = m.group(0)
        if "\n" not in frag:
            continue  # same-line case is already covered by generic_api_key_assign
        start_line = text.count("\n", 0, m.start()) + 1
        end_line = text.count("\n", 0, m.end()) + 1
        # honor an opt-out on any line the assignment spans
        if any(_suppressed("multiline_secret_assign", *_parse_ignore(lines[i - 1]))
               for i in range(start_line, end_line + 1)):
            continue
        out.append((start_line, "multiline_secret_assign", _redact(" ".join(frag.split()))))
    return out


def scan_file(path: Path, patterns: list[tuple[str, re.Pattern[str]]],
              entropy: bool = False, multiline: bool = False) -> list[tuple[int, str, str]]:
    findings: list[tuple[int, str, str]] = []
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return findings
    if multiline:
        findings.extend(_multiline_findings(text))
    for lineno, line in enumerate(text.splitlines(), 1):
        suppress_soft, named = _parse_ignore(line)
        for name, pat in patterns:
            m = pat.search(line)
            if not m:
                continue
            if name == "email_address" and EMAIL_ALLOW.search(m.group(0)):
                continue
            if _suppressed(name, suppress_soft, named):
                continue
            # Redact the matched value in output — never echo the secret itself.
            findings.append((lineno, name, _redact(m.group(0))))
        if entropy:
            for name, redacted in _entropy_findings(line):
                if _suppressed(name, suppress_soft, named):
                    continue
                findings.append((lineno, name, redacted))
    return findings


def _redact(s: str) -> str:
    if len(s) <= 6:
        return s[0] + "***"
    return s[:3] + "***" + s[-2:]


# --- Optional high-entropy detection (opt-in via --entropy) ------------------
# Catches random-looking secrets (API keys, tokens) that don't match any keyword.
# Charsets are built from the stdlib `string` module so this file never embeds a
# high-entropy literal that would flag itself.
_ENTROPY_TOKEN_RE = re.compile(r"[A-Za-z0-9+/=_-]{20,}")
_HEX_SET = set(string.hexdigits)
_B64_SET = set(string.ascii_letters + string.digits + "+/=_-")


def _shannon_entropy(s: str) -> float:
    n = len(s)
    if n == 0:
        return 0.0
    return -sum((c / n) * math.log2(c / n) for c in Counter(s).values())


def _entropy_findings(line: str) -> list[tuple[str, str]]:
    """Flag long, high-entropy base64/hex tokens. Conservative thresholds to keep
    false positives manageable; still noisier than the keyword scan (hence opt-in)."""
    out: list[tuple[str, str]] = []
    for m in _ENTROPY_TOKEN_RE.finditer(line):
        tok = m.group(0)
        if len(tok) >= 32 and all(ch in _HEX_SET for ch in tok) and _shannon_entropy(tok) >= 3.0:
            out.append(("high_entropy_hex", _redact(tok)))
        elif len(tok) >= 20 and all(ch in _B64_SET for ch in tok) and _shannon_entropy(tok) >= 4.5:
            out.append(("high_entropy_base64", _redact(tok)))
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Scan a tree for leaked secrets/identifiers.")
    ap.add_argument("root", type=Path, help="Directory or file to scan")
    ap.add_argument("--denylist", type=Path, help="Extra project-specific terms/regexes (gitignored)")
    ap.add_argument("--fail-on-find", action="store_true", help="Exit non-zero if any finding")
    ap.add_argument("--entropy", action="store_true",
                    help="Also flag high-entropy base64/hex tokens (opt-in; noisier, good for a pre-publish sweep)")
    ap.add_argument("--multiline", action="store_true",
                    help="Also flag secret assignments whose value is on a later line than the "
                         "keyword (opt-in; catches a cross-line blind spot of the line scan)")
    ap.add_argument("--require-denylist", action="store_true",
                    help="Fail (exit 2) if --denylist is missing or has zero effective patterns. "
                         "Use in private->public port runs so the project-specific gate cannot silently no-op.")
    args = ap.parse_args(argv)

    # Fail CLOSED on the project-specific gate: in a port run a missing/empty denylist
    # must error, not silently degrade to generic-only patterns (which would yield a
    # falsely reassuring green scan on exactly the identifiers that matter most).
    denylist_patterns: list[tuple[str, re.Pattern[str]]] = []
    if args.denylist and args.denylist.exists():
        denylist_patterns = load_denylist(args.denylist)
    elif args.denylist and args.require_denylist:
        print(f"error: --denylist {args.denylist} not found (required by --require-denylist).",
              file=sys.stderr)
        return 2
    if args.require_denylist and not denylist_patterns:
        print("error: --require-denylist set but no effective denylist patterns were loaded "
              f"(file: {args.denylist}). Refusing to run with the project gate disabled.",
              file=sys.stderr)
        return 2

    patterns = list(GENERIC_PATTERNS) + denylist_patterns

    root = args.root
    files = [root] if root.is_file() else list(iter_text_files(root))

    total = 0
    for f in files:
        for lineno, name, redacted in scan_file(f, patterns, entropy=args.entropy,
                                                 multiline=args.multiline):
            total += 1
            print(f"{f}:{lineno}: [{name}] {redacted}")

    print(f"\n{total} finding(s) across {len(files)} file(s).")
    if total and args.fail_on_find:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
