#!/usr/bin/env python3
"""Runnable demo for tools/memory_sync.py — the leak-gated, fail-closed public-memory sync.

Builds a throwaway "private" memory dir with three facts — one marked public and clean,
one marked public but containing a leak, and one left unmarked — then runs the sync into a
fresh target and prints what crossed the gate and what didn't. No network, no real paths.

    python examples/memory_sync_demo.py
"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import memory_sync as ms  # noqa: E402


def _fact(d: Path, name: str, body: str, visibility: str | None) -> None:
    vis = f"\n  visibility: {visibility}" if visibility else ""
    (d / f"{name}.md").write_text(
        f"---\nname: {name}\ndescription: a demo fact.\nmetadata:\n  type: feedback{vis}\n"
        f"  originSessionId: demo-session-0001\n---\n\n{body}\n",
        encoding="utf-8",
    )


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "private-memory"
        tgt = Path(tmp) / "public-memory"
        src.mkdir()
        tgt.mkdir()

        _fact(src, "use-abs-paths", "Prefer absolute paths over `cd X && cmd` for one-shot commands.",
              visibility="public")                                   # public + clean  -> sync
        _fact(src, "deploy-note", "Deploy key AKIAIOSFODNN7EXAMPLE lives in the prod env.",  # leak-scan: ignore[aws_access_key]
              visibility="public")                                   # public BUT leaks -> excluded
        _fact(src, "scratch-idea", "A half-formed idea I have not decided to share.",
              visibility=None)                                       # unmarked        -> excluded (fail-closed)

        print("=== dry-run (--check) ===")
        ms.main(["--source", str(src), "--target", str(tgt), "--check"])

        print("\n=== apply (--write) ===")
        ms.main(["--source", str(src), "--target", str(tgt), "--write"])

        published = sorted(p.name for p in tgt.glob("*.md"))
        print("\nPublished to the public target:", published)
        assert published == ["use-abs-paths.md"], published
        # the published copy is stripped of per-session frontmatter
        text = (tgt / "use-abs-paths.md").read_text(encoding="utf-8")
        assert "originSessionId" not in text and "visibility" not in text
        print("Only the public, leak-free, opted-in fact crossed the gate — and it was stripped clean.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
