import affected_tests


def test_is_test_file():
    assert affected_tests._is_test_file("tests/test_foo.py")
    assert not affected_tests._is_test_file("src/foo.py")
    assert not affected_tests._is_test_file("tests/conftest.py")


def test_full_suite_trigger_returns_run_all():
    assert affected_tests.affected(["conftest.py"]) == [affected_tests.RUN_ALL_MARKER]


def test_non_python_change_is_noop():
    assert affected_tests.affected(["docs/readme.md"]) == []


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
