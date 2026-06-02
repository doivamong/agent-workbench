#!/usr/bin/env python3
"""Runnable demo for tools/license_scan.py.

Drops a few throwaway files carrying different license / attribution markers into a temp directory
and runs the tripwire over them — so you can see what it flags (and what it deliberately cannot)
without pointing it at real vendored code.

    python examples/license_scan_demo.py
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.license_scan import scan_path  # noqa: E402

FILES = {
    "vendored_apache.py": '"""Helper.\n\nAdapted from acme/widgets (Apache-2.0).\n"""\nx = 1\n',
    "gpl_snippet.c": "/* Copyright (c) 2021 Someone. Licensed under the GPLv3. */\nint main(){return 0;}\n",
    "noncommercial.md": "# Dataset\n\nReleased under CC BY-NC 4.0 — non-commercial use only.\n",
    "proprietary.txt": "ACME Corp confidential. All rights reserved. Do not redistribute.\n",
    "my_own.py": '"""A file I wrote from scratch — no licence header at all."""\ndef f():\n    return 42\n',
}


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        for name, body in FILES.items():
            (root / name).write_text(body, encoding="utf-8")

        results = scan_path(root)
        for f in sorted(results):
            print(f"\n{f.name}")
            for label, lineno, excerpt, implies in results[f]:
                print(f"  [{label}] line {lineno}: {excerpt!r}")
                print(f"      -> {implies}")

        clean = [n for n in FILES if (root / n) not in results]
        print(f"\nFlagged {len(results)}/{len(FILES)} files. No marker in: {', '.join(clean)} "
              "(remember: 'no marker' is NOT proof it was written from scratch — verify by eye).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
