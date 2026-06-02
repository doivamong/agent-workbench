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


# --- near-dup / size-budget checks (N2) ---

def _fact(name: str, desc: str, typ: str = "feedback") -> str:
    return f"---\nname: {name}\ndescription: {desc}\nmetadata:\n  type: {typ}\n---\n\nbody\n"


def test_near_duplicate_descriptions_warn(tmp_path):
    same = "deploy the staging server every friday afternoon"
    _mem(tmp_path, "- [a.md](a.md)\n- [b.md](b.md)\n",
         {"a.md": _fact("alpha", same), "b.md": _fact("beta", same)})
    findings = memory_audit.audit(tmp_path)
    assert any(sev == "warn" and "near-duplicate" in msg for sev, _, msg in findings)
    assert [f for f in findings if f[0] == "error"] == []  # detect-only, never an error


def test_distinct_descriptions_no_near_dup(tmp_path):
    _mem(tmp_path, "- [a.md](a.md)\n- [b.md](b.md)\n",
         {"a.md": _fact("alpha", "cats sleep all day long"),
          "b.md": _fact("beta", "quarterly financial reports are due")})
    assert not any("near-duplicate" in msg for _, _, msg in memory_audit.audit(tmp_path))


def test_oversized_index_entry_warn(tmp_path):
    long_line = "- [a.md](a.md) - " + "x" * 250
    _mem(tmp_path, long_line + "\n", {"a.md": _fact("alpha", "a short description")})
    assert any(sev == "warn" and "chars" in msg for sev, _, msg in memory_audit.audit(tmp_path))


def test_total_kb_budget_warn(tmp_path, monkeypatch):
    monkeypatch.setattr(memory_audit, "TOTAL_FACTS_MAX_KB", 0)  # force the budget to bite
    _mem(tmp_path, "- [a.md](a.md)\n", {"a.md": _fact("alpha", "a short description")})
    assert any(sev == "warn" and "KB" in msg for sev, _, msg in memory_audit.audit(tmp_path))
