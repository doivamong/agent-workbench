#!/usr/bin/env python3
"""Demo: the read-only pre-push 4-point check (tools/pre_push_check.py).

Builds a throwaway git repo in a temp dir, then runs the four checks against it — first a
clean feature branch (all PASS), then a branch that commits a private handovers/ file (the
'clean' point FAILs). Nothing here touches your real repo. Stdlib-only.

    python examples/pre_push_check_demo.py
"""
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import pre_push_check as ppc  # noqa: E402


def _git(repo, *args):
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True)


def _make_repo(root: Path) -> Path:
    _git(root, "init", "-b", "main")
    _git(root, "config", "user.email", "demo@example.com")
    _git(root, "config", "user.name", "demo")
    _git(root, "remote", "add", "origin", "https://github.com/example/agent-workbench")
    (root / "a.py").write_text("x = 1\n", encoding="utf-8")
    _git(root, "add", "a.py")
    _git(root, "commit", "-m", "base")
    return root


def _report(repo, label):
    print(f"\n=== {label} ===")
    for name, ok, detail in ppc.run_checks(repo, "origin", "main", None):
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}: {detail}")


def main() -> int:
    with tempfile.TemporaryDirectory() as d:
        repo = _make_repo(Path(d))
        # clean feature branch -> all four should pass
        _git(repo, "checkout", "-b", "feature")
        (repo / "b.py").write_text("y = 2\n", encoding="utf-8")
        _git(repo, "add", "b.py")
        _git(repo, "commit", "-m", "clean change")
        _report(repo, "clean feature branch (expect 4 PASS)")

        # add a private file -> the 'clean' point should FAIL
        (repo / "handovers").mkdir()
        (repo / "handovers" / "note.md").write_text("private\n", encoding="utf-8")
        _git(repo, "add", "handovers/note.md")
        _git(repo, "commit", "-m", "oops private file")
        _report(repo, "after committing handovers/note.md (expect 'clean' FAIL)")
    print("\nDemo complete — the checker flagged the private file without touching any real repo.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
