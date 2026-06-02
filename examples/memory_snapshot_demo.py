#!/usr/bin/env python3
"""Demo: snapshot a memory dir, damage it, then restore — see tools/memory_snapshot.py.

Runs entirely in a throwaway temp dir; touches nothing real. Run it:

    python examples/memory_snapshot_demo.py
"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import memory_snapshot as ms  # noqa: E402


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        mem = Path(tmp) / "memory"
        mem.mkdir()
        (mem / "MEMORY.md").write_text("- [[prefs]] user likes terse output\n", encoding="utf-8")
        (mem / "prefs.md").write_text("the original, correct fact\n", encoding="utf-8")

        print("1. memory before:")
        print("   prefs.md =", (mem / "prefs.md").read_text(encoding="utf-8").strip())

        snap = ms.snapshot_memory(mem, label="before-edit")
        print(f"\n2. snapshot taken: {snap.name}")

        # Simulate a bad automated edit + a brand-new memory written afterwards.
        (mem / "prefs.md").write_text("CORRUPTED by a bad bulk edit\n", encoding="utf-8")
        (mem / "new.md").write_text("a memory created AFTER the snapshot\n", encoding="utf-8")
        print("\n3. damage done:")
        print("   prefs.md =", (mem / "prefs.md").read_text(encoding="utf-8").strip())

        # Dry-run first (the safe default), then apply.
        print("\n4. restore --latest (dry-run):")
        restored, preserved = ms.restore_snapshot(mem, snap, apply=False)
        print("   would restore:", restored, "| would preserve newer:", preserved)

        print("\n5. restore --latest --apply:")
        ms.restore_snapshot(mem, snap, apply=True)
        print("   prefs.md =", (mem / "prefs.md").read_text(encoding="utf-8").strip())
        print("   new.md still present? ", (mem / "new.md").exists(), "(additive restore keeps it)")

    print("\nDone — bad edit rolled back, the later memory was not lost.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
