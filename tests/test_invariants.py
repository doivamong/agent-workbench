import invariants


def test_detects_bare_print(tmp_path):
    (tmp_path / "m.py").write_text("print('x')\n", encoding="utf-8")
    found = invariants.run(tmp_path, invariants.SAMPLE_INVARIANTS)
    assert any(v.invariant == "no-print-in-lib" for v in found)


def test_detects_absolute_path(tmp_path):
    (tmp_path / "m.py").write_text("P = '/home/alice/data'\n", encoding="utf-8")  # leak-scan: ignore  inv: ignore
    found = invariants.run(tmp_path, invariants.SAMPLE_INVARIANTS)
    assert any(v.invariant == "no-absolute-path" for v in found)


def test_clean_file_has_no_violations(tmp_path):
    (tmp_path / "m.py").write_text(
        "import logging\nlog = logging.getLogger(__name__)\n", encoding="utf-8"
    )
    assert invariants.run(tmp_path, invariants.SAMPLE_INVARIANTS) == []


def test_violation_key_is_stable_across_line_moves():
    from invariants import Violation

    a = Violation("inv", "a.py", 3, "msg")
    b = Violation("inv", "a.py", 99, "msg")  # same file/inv/msg, different line
    assert a.key() == b.key()


def test_todo_with_owner_not_flagged(tmp_path):
    (tmp_path / "m.py").write_text("# TODO(alice): do it\n", encoding="utf-8")
    found = invariants.run(tmp_path, invariants.SAMPLE_INVARIANTS)
    assert not any(v.invariant == "todo-needs-owner" for v in found)
