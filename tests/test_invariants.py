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


def test_default_suffixes_skip_non_python(tmp_path):
    # a TODO without owner in a .yaml is ignored by default (.py only)
    (tmp_path / "c.yaml").write_text("# TODO: wire this up\n", encoding="utf-8")
    assert invariants.run(tmp_path, invariants.SAMPLE_INVARIANTS) == []


def test_suffixes_extends_to_other_filetypes(tmp_path):
    (tmp_path / "c.yaml").write_text("# TODO: wire this up\n", encoding="utf-8")
    found = invariants.run(tmp_path, invariants.SAMPLE_INVARIANTS, suffixes={".yaml"})
    assert any(v.invariant == "todo-needs-owner" for v in found)


def test_user_defined_invariant_runs_through_public_api(tmp_path):
    # The framework's whole point: a project defines its OWN rule with line_regex +
    # Invariant and runs it the same way as the built-ins. Pin that contract.
    my_rule = invariants.Invariant(
        id="no-bare-except",
        description="No bare except:.",
        check=invariants.line_regex("no-bare-except", r"^\s*except\s*:", "Bare except swallows errors."),
    )
    (tmp_path / "m.py").write_text("try:\n    x()\nexcept:\n    pass\n", encoding="utf-8")
    found = invariants.run(tmp_path, [my_rule])
    assert [v.invariant for v in found] == ["no-bare-except"]


def test_inv_ignore_marker_suppresses(tmp_path):
    # An `inv: ignore` comment opts a line out (the mechanism the sample demo relies on).
    rule = invariants.Invariant(
        id="no-bare-except",
        description="No bare except:.",
        check=invariants.line_regex("no-bare-except", r"^\s*except\s*:", "msg"),
    )
    (tmp_path / "m.py").write_text("try:\n    x()\nexcept:  # inv: ignore\n    pass\n", encoding="utf-8")
    assert invariants.run(tmp_path, [rule]) == []


# --- config_nested_access (the deterministic config-guard check) ---

def test_config_flat_access_flags_one_level_get():
    chk = invariants.config_nested_access("box", {"inner"})
    found = chk("m.py", 'x = cfg.get("inner")\n')
    assert len(found) == 1 and found[0].invariant == "config-flat-access"


def test_config_two_level_access_not_flagged():
    chk = invariants.config_nested_access("box", {"inner"})
    assert chk("m.py", 'x = cfg.get("box", {}).get("inner")\n') == []


def test_config_flat_access_respects_inv_ignore():
    chk = invariants.config_nested_access("box", {"inner"})
    assert chk("m.py", 'x = cfg.get("inner")  # inv: ignore\n') == []


def test_config_unrelated_key_not_flagged():
    chk = invariants.config_nested_access("box", {"inner"})
    assert chk("m.py", 'x = cfg.get("something_else")\n') == []


def test_config_empty_nested_keys_is_noop():
    chk = invariants.config_nested_access("box", set())
    assert chk("m.py", 'x = cfg.get("inner")\n') == []


def test_sample_config_invariant_catches_placeholder_trap(tmp_path):
    # The shipped SAMPLE invariant uses placeholder parent="config_section"/key="inner_value".
    (tmp_path / "flat.py").write_text('v = cfg.get("inner_value")\n', encoding="utf-8")  # inv: ignore
    (tmp_path / "ok.py").write_text('v = cfg.get("config_section", {}).get("inner_value")\n', encoding="utf-8")
    found = invariants.run(tmp_path, invariants.SAMPLE_INVARIANTS)
    config_hits = {v.path for v in found if v.invariant == "config-flat-access"}
    assert config_hits == {"flat.py"}  # flat access flagged, correct two-level form not
