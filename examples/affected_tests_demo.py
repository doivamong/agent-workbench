#!/usr/bin/env python3
"""Runnable demo for tools/affected_tests.py.

Builds a throwaway 5-file project with a real import chain, points the selector at
it, and shows which tests a change pulls in — including a test caught *transitively*
through the reverse import graph (not by name). No external deps, no ITF graph.

    python examples/affected_tests_demo.py
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import tools.affected_tests as at  # noqa: E402

# A tiny project: api -> service -> db, with two tests. Note test_api does NOT import
# db directly — the only way changing db can select it is through the reverse graph.
FILES = {
    "src/db.py": "VALUE = 1\n",
    "src/service.py": "import db\n\ndef serve():\n    return db.VALUE\n",
    "src/api.py": "import service\n\ndef handle():\n    return service.serve()\n",
    "tests/test_db.py": "import db\n\ndef test_value():\n    assert db.VALUE == 1\n",
    "tests/test_api.py": "import api\n\ndef test_handle():\n    assert api.handle() == 1\n",
}


def main() -> int:
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        for rel, body in FILES.items():
            p = root / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(body, encoding="utf-8")

        # Point the selector's module-level roots at the throwaway project.
        at.ROOT = root
        at.SCAN_DIRS = ("src", "tests")
        at.CACHE_DIR = root / ".cache"
        at.CACHE_FILE = root / ".cache" / "affected_tests.json"

        print("Project: api.py -> service.py -> db.py, with test_db.py and test_api.py.\n")

        for changed in ("src/db.py", "src/service.py", "tests/conftest.py"):
            result = at.affected([changed])
            if at.RUN_ALL_MARKER in result:
                shown = "FULL SUITE (high blast radius)"
            else:
                shown = ", ".join(result) or "(none)"
            print(f"  change {changed:<20} -> run: {shown}")

        print(
            "\nNote: changing db.py selects test_api.py too — there's no test_db_api name\n"
            "match; it's found purely by walking the reverse import graph (test_api -> api\n"
            "-> service -> db). conftest.py changes trip the full-suite fallback."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
