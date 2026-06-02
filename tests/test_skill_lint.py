"""Tests for tools/skill_lint.py."""
import skill_lint

_REGISTRY = """# Skill Registry

| Skill | Tier | Fires when | Does NOT fire when |
|-------|------|------------|--------------------|
| `alpha` | guard | x | y |
| _your-placeholder_ | guard | x | y |
"""

_SKILL = """---
name: alpha
description: does a thing
tier: guard
---
body
"""


def _skills(tmp_path, registry: str, skills: dict) -> None:
    (tmp_path / "skill-registry.md").write_text(registry, encoding="utf-8")
    for folder, body in skills.items():
        d = tmp_path / folder
        d.mkdir()
        (d / "SKILL.md").write_text(body, encoding="utf-8")


def test_registry_names_skips_header_and_placeholder():
    assert skill_lint.registry_names(_REGISTRY) == {"alpha"}


def test_clean_skills_have_no_errors(tmp_path):
    _skills(tmp_path, _REGISTRY, {"alpha": _SKILL})
    assert [f for f in skill_lint.lint(tmp_path) if f[0] == "error"] == []


def test_folder_without_registry_row_is_error(tmp_path):
    _skills(tmp_path, _REGISTRY, {"alpha": _SKILL, "beta": _SKILL.replace("alpha", "beta")})
    assert any(sev == "error" and "no row" in msg for sev, _, msg in skill_lint.lint(tmp_path))


def test_registry_row_without_folder_is_error(tmp_path):
    reg = _REGISTRY + "| `ghost` | guard | x | y |\n"
    _skills(tmp_path, reg, {"alpha": _SKILL})
    assert any(sev == "error" and "no matching skill folder" in msg
               for sev, _, msg in skill_lint.lint(tmp_path))


def test_name_mismatch_is_warning(tmp_path):
    _skills(tmp_path, _REGISTRY, {"alpha": _SKILL.replace("name: alpha", "name: different")})
    findings = skill_lint.lint(tmp_path)
    assert any(sev == "warn" and "!=" in msg for sev, _, msg in findings)


def test_main_exit_code(tmp_path):
    _skills(tmp_path, _REGISTRY, {"alpha": _SKILL})
    assert skill_lint.main([str(tmp_path)]) == 0
