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
