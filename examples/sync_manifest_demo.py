#!/usr/bin/env python3
"""Runnable demo for tools/sync_manifest.py.

Builds a throwaway project with a couple of watched dirs, writes a manifest, then adds a
file and removes another so `--check` reports the file-set drift (added/removed) while an
in-place content edit is reported as informational only (not gated).

    python examples/sync_manifest_demo.py
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.sync_manifest import build_manifest, diff_manifest  # noqa: E402


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "tools").mkdir()
        (root / ".claude" / "skills").mkdir(parents=True)
        (root / "tools" / "alpha.py").write_text("print('a')\n", encoding="utf-8")
        (root / ".claude" / "skills" / "s.md").write_text("# skill\n", encoding="utf-8")

        snapshot = build_manifest(root)
        print(f"Snapshot: {len(snapshot['files'])} file(s) across {snapshot['roots']}")

        # Add one file, remove another, and edit a third in place.
        (root / "tools" / "beta.py").write_text("print('b')\n", encoding="utf-8")
        (root / ".claude" / "skills" / "s.md").unlink()
        (root / "tools" / "alpha.py").write_text("print('a — edited')\n", encoding="utf-8")

        added, removed, changed = diff_manifest(snapshot, build_manifest(root))
        print(f"  added (gated):   {added}")
        print(f"  removed (gated): {removed}")
        print(f"  changed (info):  {changed}")

        ok = added == ["tools/beta.py"] and removed == [".claude/skills/s.md"] and changed == ["tools/alpha.py"]
        print("\nDemo OK — set drift is gated, content edit is not." if ok else "\nDemo mismatch!")
        return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
