#!/usr/bin/env python3
"""Demo: parse a staged requirements diff and show the deploy reminder.

Uses a canned diff so it runs anywhere (no git state needed). Run it:

    python examples/requirements_diff_demo.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import check_requirements_diff as rd  # noqa: E402

SAMPLE_DIFF = """--- a/requirements.txt
+++ b/requirements.txt
@@ -1,1 +1,3 @@
 flask
+numpy>=1.24
+ollama
"""


def main() -> int:
    added = rd.parse_added_packages(SAMPLE_DIFF)
    print("Parsed new dependencies:", added)
    print()
    if added:
        print(rd.render_warning(added, "requirements.txt"))
    print("\n(exit 0 — this is a reminder, it never blocks a commit)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
