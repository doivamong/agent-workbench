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


# --- Wave 0 additions: registry tiers, archive field, guard honesty, cross-references ---

_ARCHIVED = """---
name: beta
archived: 2026-06-03
description: >
  WHAT: an old thing. USE WHEN: never. DO NOT TRIGGER: always.
tier: guard
---
This skill is retired; it does not run anymore.
"""


def test_registry_tiers_maps_name_to_tier():
    assert skill_lint.registry_tiers(_REGISTRY) == {"alpha": "guard"}


def test_archived_skill_without_row_is_not_error(tmp_path):
    # 'beta' has no registry row, but `archived:` exempts it from the no-row error.
    _skills(tmp_path, _REGISTRY, {"alpha": _SKILL, "beta": _ARCHIVED})
    findings = skill_lint.lint(tmp_path)
    assert not any(sev == "error" and "no row" in msg for sev, _, msg in findings)
    assert any(sev == "warn" and "archived" in msg for sev, _, msg in findings)


def test_guard_without_honesty_line_warns(tmp_path):
    # _SKILL is tier guard with body 'body' — no 'does not' phrase.
    _skills(tmp_path, _REGISTRY, {"alpha": _SKILL})
    assert any(sev == "warn" and "honesty" in msg for sev, _, msg in skill_lint.lint(tmp_path))


def test_guard_with_honesty_line_is_clean(tmp_path):
    honest = _SKILL.replace("body", "It does not catch everything.")
    _skills(tmp_path, _REGISTRY, {"alpha": honest})
    assert not any("honesty" in msg for _, _, msg in skill_lint.lint(tmp_path))


def test_dangling_skill_reference_warns(tmp_path):
    # `alpha-ghost`: family 'alpha' matches the real skill, but the slug has no folder/row.
    body = _SKILL.replace("body", "see `alpha-ghost` for details")
    _skills(tmp_path, _REGISTRY, {"alpha": body})
    assert any(sev == "warn" and "alpha-ghost" in msg for sev, _, msg in skill_lint.lint(tmp_path))


def test_unrelated_hyphenated_token_does_not_warn(tmp_path):
    # 'post-edit-simplify' is a hook; family 'post' matches no skill → not flagged (precision).
    body = _SKILL.replace("body", "the `post-edit-simplify` hook runs after edits")
    _skills(tmp_path, _REGISTRY, {"alpha": body})
    assert not any("post-edit-simplify" in msg for _, _, msg in skill_lint.lint(tmp_path))
