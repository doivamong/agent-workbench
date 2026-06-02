"""Tests for tools/check_context_budget.py."""
import json
from pathlib import Path

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


# --- budget caps (Wave 0: give the audit teeth) ---

def _skill_comps(n, tokens=100):
    return [cb.Component(kind="skill", name=f"s{i}", path=Path("x"), tokens=tokens) for i in range(n)]


def test_check_caps_flags_too_many_skills():
    comps = _skill_comps(5)
    assert cb.check_caps(comps, max_skills=3, max_skill_tokens=None)      # 5 > 3 → breach
    assert cb.check_caps(comps, max_skills=5, max_skill_tokens=None) == []  # 5 == 5 → ok


def test_check_caps_flags_skill_tokens():
    comps = _skill_comps(1, tokens=500)
    assert cb.check_caps(comps, max_skills=None, max_skill_tokens=400)       # 500 > 400 → breach
    assert cb.check_caps(comps, max_skills=None, max_skill_tokens=600) == []  # 500 < 600 → ok


def test_check_caps_ignores_non_skill_components():
    comps = [cb.Component(kind="rule", name="r", path=Path("x"), tokens=9999)]
    assert cb.check_caps(comps, max_skills=0, max_skill_tokens=0) == []  # no skills → no breach


def test_main_exits_1_when_skill_cap_exceeded(tmp_path):
    _project(tmp_path)  # one skill
    assert cb.main(["--root", str(tmp_path), "--max-skills", "0"]) == 1


def test_main_exits_0_when_under_cap(tmp_path):
    _project(tmp_path)
    assert cb.main(["--root", str(tmp_path), "--max-skills", "10", "--max-skill-tokens", "100000"]) == 0
