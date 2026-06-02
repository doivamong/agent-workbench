"""Tests for tools/check_context_budget.py."""
import json

import check_context_budget as cb


def _project(tmp_path):
    (tmp_path / "CLAUDE.md").write_text("# Title\nmentions the foo skill here\n", encoding="utf-8")
    sk = tmp_path / ".claude" / "skills" / "foo"
    sk.mkdir(parents=True)
    (sk / "SKILL.md").write_text("---\nname: foo\ndescription: does foo\n---\nbody\n", encoding="utf-8")
    refs = sk / "references"
    refs.mkdir()
    (refs / "big.md").write_text("word " * 200, encoding="utf-8")
    rules = tmp_path / ".claude" / "rules"
    rules.mkdir(parents=True)
    (rules / "bar.md").write_text("a rule body\n", encoding="utf-8")
    return tmp_path


def test_count_tokens_is_word_heuristic():
    assert cb.count_tokens("one two three") == int(3 * cb.TOKENS_PER_WORD)


def test_collect_finds_each_kind(tmp_path):
    kinds = {c.kind for c in cb.collect(_project(tmp_path))}
    assert {"skill", "rule", "claudemd"} <= kinds


def test_skill_body_and_references_counted_separately(tmp_path):
    foo = next(c for c in cb.collect(_project(tmp_path)) if c.kind == "skill")
    assert foo.tokens > 0       # session-start body
    assert foo.ref_tokens > 0   # references/ counted as on-demand
    assert foo.ref_lines >= 1


def test_bucket_is_always_when_named_in_claudemd(tmp_path):
    foo = next(c for c in cb.collect(_project(tmp_path)) if c.name == "foo")
    assert foo.bucket == "always"  # CLAUDE.md mentions "foo"


def test_critical_agent_description_yields_exit_1(tmp_path):
    _project(tmp_path)
    agents = tmp_path / ".claude" / "agents"
    agents.mkdir(parents=True)
    long_desc = "word " * 60  # > agent_desc_critical
    (agents / "baz.md").write_text(f"---\nname: baz\ndescription: {long_desc}\n---\nbody\n", encoding="utf-8")
    assert cb.main(["--root", str(tmp_path)]) == 1


def test_json_output_lists_components(tmp_path, capsys):
    _project(tmp_path)
    rc = cb.main(["--root", str(tmp_path), "--json"])
    data = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert any(c["kind"] == "skill" for c in data)
