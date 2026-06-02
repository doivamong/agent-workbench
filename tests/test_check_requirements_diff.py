"""Tests for tools/check_requirements_diff.py."""
import check_requirements_diff as rd

_DIFF = """diff --git a/requirements.txt b/requirements.txt
--- a/requirements.txt
+++ b/requirements.txt
@@ -1,2 +1,4 @@
 flask
+numpy>=1.24
+# a comment line, not a package
+ollama
-oldpkg==1.0
+
"""


def test_parses_added_packages_only():
    assert rd.parse_added_packages(_DIFF) == ["numpy", "ollama"]


def test_ignores_header_context_removed_and_blank():
    # +++ header, context ' flask', removed '-oldpkg', '+# comment', '+   ' all excluded
    added = rd.parse_added_packages(_DIFF)
    assert "flask" not in added and "oldpkg" not in added
    assert all(not p.startswith("#") for p in added)


def test_empty_diff_yields_nothing():
    assert rd.parse_added_packages("") == []


def test_render_warning_lists_each_package():
    out = rd.render_warning(["numpy", "ollama"], "requirements.txt")
    assert "numpy" in out and "ollama" in out
    assert "2 new dependency" in out
    assert "not a blocker" in out  # honest: it never blocks


def test_kill_switch_silences(monkeypatch, capsys):
    monkeypatch.setenv("REQUIREMENTS_DIFF_GUARD", "0")
    assert rd.main(["requirements.txt"]) == 0
    assert capsys.readouterr().out == ""


def test_noop_when_requirements_not_in_changed_files(capsys):
    # a pre-commit run touching only other files must do nothing (and never block)
    assert rd.main(["src/app.py", "README.md"]) == 0
    assert capsys.readouterr().out == ""
