import json
import subprocess
import sys
from pathlib import Path

import pytest

import affected_tests

_MODULE = Path(affected_tests.__file__)


def _run_cli(*args, stdin=None):
    proc = subprocess.run(
        [sys.executable, str(_MODULE), *args],
        input=stdin, capture_output=True, text=True,
    )
    assert proc.returncode == 0, proc.stderr
    return proc.stdout


def test_cli_json_output_for_explicit_file():
    out = _run_cli("tools/leak_scan.py", "--json")
    data = json.loads(out)
    assert data["full_suite"] is False
    assert "tests/test_leak_scan.py" in data["tests"]


def test_cli_full_suite_trigger_json():
    data = json.loads(_run_cli("conftest.py", "--json"))
    assert data["full_suite"] is True


def test_cli_no_input_is_noop():
    assert _run_cli("--quiet").strip() == ""


def test_cli_stdin_input():
    data = json.loads(_run_cli("--stdin", "--json", stdin="tools/leak_scan.py\n"))
    assert "tests/test_leak_scan.py" in data["tests"]


def test_is_test_file():
    assert affected_tests._is_test_file("tests/test_foo.py")
    assert not affected_tests._is_test_file("src/foo.py")
    assert not affected_tests._is_test_file("tests/conftest.py")


def test_full_suite_trigger_returns_run_all():
    assert affected_tests.affected(["conftest.py"]) == [affected_tests.RUN_ALL_MARKER]


def test_non_python_change_is_noop():
    assert affected_tests.affected(["docs/readme.md"]) == []


# --- B1: non-.py classification happens BEFORE the .py filter --------------------------

@pytest.mark.parametrize("artifact", [
    "ui/web/templates/admin.html.jinja",   # template a test renders
    "ops/web/page.html",                    # ops-side template
    ".claude/skills/awb-review/SKILL.md",   # skill definition (skill-lint / -usage tests)
    ".claude/skills/skill-registry.md",     # skill registry
    ".claude/manifest.json",                # file-set manifest
    "known_violations.json",                # invariant baseline
    ".claude/settings.json",                # hook control-plane
])
def test_high_blast_nonpy_runs_full_suite(artifact):
    # Regression for B1: each used to select [] because the .py filter dropped it first.
    assert affected_tests.affected([artifact]) == [affected_tests.RUN_ALL_MARKER]


def test_unknown_nonpy_runs_full_suite_failsafe():
    # requirements.txt carries no import edge and is not a doc → conservative full run.
    assert affected_tests.affected(["requirements.txt"]) == [affected_tests.RUN_ALL_MARKER]


def test_mixed_doc_and_code_selects_only_code():
    # a .md alongside a .py: the doc is skipped, the .py drives selection (not RUN_ALL).
    result = affected_tests.affected(["docs/x.md", "tools/leak_scan.py"])
    assert affected_tests.RUN_ALL_MARKER not in result
    assert "tests/test_leak_scan.py" in result


def test_dropped_dead_triggers_no_longer_listed():
    # pyproject.toml / setup.cfg removed from FULL_SUITE_TRIGGERS (they don't exist here);
    # a pyproject.toml change now runs full via the unknown-non-.py fail-safe instead.
    assert "pyproject.toml" not in affected_tests.FULL_SUITE_TRIGGERS
    assert affected_tests.affected(["pyproject.toml"]) == [affected_tests.RUN_ALL_MARKER]


# --- --run mode (the pre-commit entry) -------------------------------------------------

def test_run_mode_skips_pytest_when_nothing_affected():
    # _run_pytest([]) must exit 0 without spawning pytest.
    assert affected_tests._run_pytest([]) == 0


def test_run_mode_builds_full_command_for_run_all(monkeypatch):
    captured = {}

    def fake_call(cmd, **k):
        captured["cmd"] = cmd
        return 0

    monkeypatch.setattr(affected_tests.subprocess, "call", fake_call)
    rc = affected_tests._run_pytest([affected_tests.RUN_ALL_MARKER])
    assert rc == 0
    assert "-n" in captured["cmd"] and "auto" in captured["cmd"]
    assert not any(str(c).startswith("tests/") for c in captured["cmd"])  # no file pinned


def test_run_mode_appends_selected_files(monkeypatch):
    captured = {}

    def fake_call(cmd, **k):
        captured["cmd"] = cmd
        return 0

    monkeypatch.setattr(affected_tests.subprocess, "call", fake_call)
    affected_tests._run_pytest(["tests/test_leak_scan.py"])
    assert "tests/test_leak_scan.py" in captured["cmd"]


def test_force_full_returns_run_all():
    assert affected_tests.affected(["src/anything.py"], force_full=True) == [
        affected_tests.RUN_ALL_MARKER
    ]


def test_module_exposes_cli_entrypoint():
    assert hasattr(affected_tests, "main")


def test_module_to_path_resolves_via_scan_dirs():
    """A bare module name resolves to its file under a SCAN_DIR (flat-layout support).

    Regression guard: this previously returned None for ``leak_scan`` because resolution
    only tried the repo root, leaving the import graph empty on this repo's layout.
    """
    resolved = affected_tests._module_to_path("leak_scan")
    assert resolved is not None
    assert resolved.as_posix().endswith("tools/leak_scan.py")


def test_import_graph_has_edges():
    """The forward graph must actually resolve edges on this repo (graph selection active)."""
    forward = affected_tests.build_import_graph(force=True)
    assert any(forward.values()), "import graph is empty — graph-based selection inactive"


def test_graph_selects_transitive_importer(monkeypatch):
    """A 2-hop reverse-dependency chain selects the importing test via BFS, not name-match.

    test_app -> service -> db ; changing db.py must surface tests/test_app.py purely
    through the reverse import graph (no test_db.py exists, so name-matching can't help).
    """
    fake_forward = {
        "tests/test_app.py": ["src/service.py"],
        "src/service.py": ["src/db.py"],
        "src/db.py": [],
    }
    monkeypatch.setattr(affected_tests, "build_import_graph", lambda *a, **k: fake_forward)
    result = affected_tests.affected(["src/db.py"])
    assert "tests/test_app.py" in result


def test_files_hash_distinguishes_same_second_edits(tmp_path):
    """Content-based cache key must differ for different contents, even at the same mtime."""
    import os

    f = tmp_path / "mod.py"
    f.write_text("x = 1\n", encoding="utf-8")
    os.utime(f, (1_700_000_000, 1_700_000_000))
    h1 = affected_tests._files_hash([f])
    f.write_text("x = 2\n", encoding="utf-8")
    os.utime(f, (1_700_000_000, 1_700_000_000))  # force identical mtime
    h2 = affected_tests._files_hash([f])
    assert h1 != h2
