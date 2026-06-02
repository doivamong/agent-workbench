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


# --- block-scalar parser + structural-convention checks (N5) ---

_SKILL_BLOCK = """---
name: alpha
description: >
  WHAT: does a thing.
  USE WHEN: the user asks for a thing.
  DO NOT TRIGGER: when they ask for a different thing.
tier: guard
---
body
"""


def test_parse_frontmatter_reads_block_scalar():
    fields = skill_lint.parse_frontmatter(_SKILL_BLOCK)
    assert fields is not None
    assert fields["name"] == "alpha"
    # The block body is folded into one string, so its markers are visible.
    assert "USE WHEN" in fields["description"]
    assert "DO NOT TRIGGER" in fields["description"]


def test_parse_frontmatter_none_without_fence():
    assert skill_lint.parse_frontmatter("name: alpha\ndescription: x\n") is None


def test_block_scalar_skill_is_clean(tmp_path):
    _skills(tmp_path, _REGISTRY, {"alpha": _SKILL_BLOCK})
    findings = skill_lint.lint(tmp_path)
    assert [f for f in findings if f[0] == "error"] == []
    # A well-formed block-scalar description must not warn about missing markers.
    assert not any("marker" in msg for _, _, msg in findings)


def test_missing_markers_warn(tmp_path):
    # _SKILL has a bare 'description: does a thing' — no USE WHEN / DO NOT TRIGGER.
    _skills(tmp_path, _REGISTRY, {"alpha": _SKILL})
    msgs = [msg for sev, _, msg in skill_lint.lint(tmp_path) if sev == "warn"]
    assert any("USE WHEN" in m for m in msgs)
    assert any("DO NOT TRIGGER" in m for m in msgs)


def test_malformed_frontmatter_is_error(tmp_path):
    _skills(tmp_path, _REGISTRY, {"alpha": "no frontmatter here\n"})
    assert any(sev == "error" and "frontmatter" in msg
               for sev, _, msg in skill_lint.lint(tmp_path))


def test_oversize_skill_warns(tmp_path):
    big = _SKILL_BLOCK + ("\nfiller line" * (skill_lint.MAX_SKILL_LINES + 5))
    _skills(tmp_path, _REGISTRY, {"alpha": big})
    assert any(sev == "warn" and "lines" in msg
               for sev, _, msg in skill_lint.lint(tmp_path))


# --- description-quality checks (C1) ---

def test_reserved_name_token_warns(tmp_path):
    reg = _REGISTRY.replace("`alpha`", "`claude-helper`")
    skill = _SKILL_BLOCK.replace("name: alpha", "name: claude-helper")
    _skills(tmp_path, reg, {"claude-helper": skill})
    assert any(sev == "warn" and "reserved token" in msg
               for sev, _, msg in skill_lint.lint(tmp_path))


def test_angle_brackets_in_description_warn(tmp_path):
    skill = _SKILL_BLOCK.replace("does a thing.", "does a thing for <users>.")
    _skills(tmp_path, _REGISTRY, {"alpha": skill})
    assert any(sev == "warn" and "angle brackets" in msg
               for sev, _, msg in skill_lint.lint(tmp_path))


def test_too_short_description_warns(tmp_path):
    # _SKILL has a 12-char 'does a thing' description — under DESC_MIN_CHARS.
    _skills(tmp_path, _REGISTRY, {"alpha": _SKILL})
    assert any(sev == "warn" and "chars" in msg for sev, _, msg in skill_lint.lint(tmp_path))


def test_too_long_description_warns(tmp_path):
    long_desc = "USE WHEN x. DO NOT TRIGGER y. " + ("padding " * 200)
    skill = f"---\nname: alpha\ndescription: {long_desc}\ntier: guard\n---\nbody\n"
    _skills(tmp_path, _REGISTRY, {"alpha": skill})
    assert any(sev == "warn" and "chars" in msg for sev, _, msg in skill_lint.lint(tmp_path))


def test_band_length_description_is_clean(tmp_path):
    # _SKILL_BLOCK's description is well within the band and has no angle brackets.
    _skills(tmp_path, _REGISTRY, {"alpha": _SKILL_BLOCK})
    msgs = [msg for _, _, msg in skill_lint.lint(tmp_path)]
    assert not any("chars" in m or "angle brackets" in m or "reserved token" in m for m in msgs)
