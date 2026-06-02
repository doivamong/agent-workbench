"""Tests for tools/memory_audit.py."""
import memory_audit

_GOOD_FACT = """---
name: feedback-thing
description: A one-line description.
metadata:
  type: feedback
---

The fact. Related: [[feedback-thing]]
"""


def _mem(tmp_path, index_body: str, files: dict) -> None:
    (tmp_path / "MEMORY.md").write_text("# Memory Index\n\n" + index_body, encoding="utf-8")
    for name, body in files.items():
        (tmp_path / name).write_text(body, encoding="utf-8")


def test_clean_memory_has_no_errors(tmp_path):
    _mem(tmp_path, "- [feedback_thing.md](feedback_thing.md) - a thing\n",
         {"feedback_thing.md": _GOOD_FACT})
    findings = memory_audit.audit(tmp_path)
    assert [f for f in findings if f[0] == "error"] == []


def test_missing_frontmatter_is_error(tmp_path):
    _mem(tmp_path, "- [bad.md](bad.md)\n", {"bad.md": "no frontmatter here\n"})
    assert any(sev == "error" and "frontmatter" in msg for sev, _, msg in memory_audit.audit(tmp_path))


def test_invalid_type_is_error(tmp_path):
    fact = _GOOD_FACT.replace("type: feedback", "type: bogus")
    _mem(tmp_path, "- [feedback_thing.md](feedback_thing.md)\n", {"feedback_thing.md": fact})
    assert any(sev == "error" and "metadata.type" in msg for sev, _, msg in memory_audit.audit(tmp_path))


def test_dangling_index_link_is_error(tmp_path):
    _mem(tmp_path, "- [gone.md](gone.md) - missing file\n", {})
    assert any(sev == "error" and "missing file" in msg for sev, _, msg in memory_audit.audit(tmp_path))


def test_orphan_fact_is_warning(tmp_path):
    _mem(tmp_path, "(empty index)\n", {"feedback_thing.md": _GOOD_FACT})
    findings = memory_audit.audit(tmp_path)
    assert any(sev == "warn" and "orphan" in msg for sev, _, msg in findings)
    assert [f for f in findings if f[0] == "error"] == []


def test_parse_frontmatter_reads_nested_type():
    fm = memory_audit.parse_frontmatter(_GOOD_FACT)
    assert fm["name"] == "feedback-thing"
    assert fm["metadata"]["type"] == "feedback"


def test_main_exit_code(tmp_path):
    _mem(tmp_path, "- [feedback_thing.md](feedback_thing.md)\n", {"feedback_thing.md": _GOOD_FACT})
    assert memory_audit.main([str(tmp_path)]) == 0
    (tmp_path / "broken.md").write_text("nope\n", encoding="utf-8")
    assert memory_audit.main([str(tmp_path)]) == 1
