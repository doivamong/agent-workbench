#!/usr/bin/env python3
"""Runnable demo for .claude/hooks/scripts/secret_write_gate.py.

Runs the write-time secret classifier against a mix of safe text and pasted cloud
credentials, and prints the verdict. This is the logic a PreToolUse Write|Edit hook uses
to stop a near-certain cloud key from being written into a committable file. It denies ONLY
high-confidence token shapes (leak_scan HARD_PATTERNS, measured 0 false positives on a real
project) — it is a tripwire for pasted cloud tokens, not full secret protection. Stdlib only.

    python examples/secret_write_gate_demo.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / ".claude" / "hooks" / "scripts"))

from secret_write_gate import find_hard_secret  # noqa: E402

SAMPLES = [
    # (text, expected_blocked)
    ("def add(a, b):\n    return a + b\n", False),                    # ordinary code
    ('API_DOCS = "https://example.com/docs"\n', False),              # a URL, not a key
    ('password = "hunter2"\n', False),                               # SOFT/quoted — NOT blocked here
    ("FERNET_KEY=Zr8k2...not-a-real-shape\n", False),                # env value — out of scope
    ('aws_key = "AKIA' + "A" * 16 + '"\n', True),                    # AWS access key shape
    ("token = 'ghp_" + "a" * 36 + "'\n", True),                      # GitHub token shape
    ("KEY = 'AIza" + "b" * 35 + "'\n", True),                        # Google API key shape
    ("-----BEGIN RSA PRIVATE KEY" + "-----\n", True),                # private key block (split so this file doesn't self-flag)
    # a scoped opt-out lets a known fixture through
    ("k = 'AKIA" + "C" * 16 + "'  # leak-scan: ignore[aws_access_key]\n", False),
]


def main() -> int:
    print(f"{'BLOCKED?':<9} {'EXPECTED':<9} SAMPLE")
    print("-" * 64)
    ok = True
    for text, expected in SAMPLES:
        hit = find_hard_secret(text)
        blocked = hit is not None
        mark = "OK" if blocked == expected else "MISMATCH"
        if blocked != expected:
            ok = False
        reason = f"   -> {hit[0]}" if hit else ""
        sample = text.splitlines()[0][:42]
        print(f"{str(blocked):<9} {str(expected):<9} {sample}{reason}  [{mark}]")

    print("\nAll classifications correct." if ok else "\nSome classifications were wrong!")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
