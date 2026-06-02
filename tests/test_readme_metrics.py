"""Guard against README metric drift.

The README advertises a test count in a few places. That number is hand-maintained,
so it silently goes stale every time a test is added (it drifted 37 -> 60 -> 75 -> ...
across earlier rounds). This test pins the advertised number to reality: it collects the
suite via `pytest --co` and asserts every "N tests" figure in the README matches.

If this fails, update the count in README.md (metrics row, Quickstart comment, footer).
"""
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _collected_test_count() -> int:
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "--co", "-q", "tests"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    m = re.search(r"(\d+)\s+tests?\s+collected", proc.stdout)
    assert m, f"could not parse pytest collection summary:\n{proc.stdout[-800:]}"
    return int(m.group(1))


def test_readme_advertised_test_count_matches_reality():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    advertised = {int(n) for n in re.findall(r"\b(\d+)\s+tests\b", readme)}
    advertised |= {int(n) for n in re.findall(r"\|\s*Tests\s*\|\s*\*\*(\d+)\*\*", readme)}
    assert advertised, "no test-count metric found in README.md"
    actual = _collected_test_count()
    assert advertised == {actual}, (
        f"README advertises test counts {sorted(advertised)} but pytest collects {actual}. "
        "Update the count in README.md (metrics row, Quickstart comment, and footer)."
    )
