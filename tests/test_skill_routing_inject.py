"""Tests for the skill_routing_inject SessionStart hook.

Covers the pure parse/build functions (registry text -> tier-ordered map) and the real
stdin/stdout hook contract via a subprocess, including fail-open on a missing/malformed
registry and the kill switch.
"""
import json
import subprocess
import sys
from pathlib import Path

import skill_routing_inject as sri

# A miniature registry: tiers deliberately out of precedence order, plus a placeholder row,
# a header, and a separator — the parser must keep only the real rows and the builder must
# re-order them Workflow > Guard > Feature > Audit.
SAMPLE_REGISTRY = """# Skill Registry

| Skill | Tier | Fires when (triggers) | Does NOT fire when |
|-------|------|------------------------|--------------------|
| `a-audit` | audit | "find dead code" | "this function is too long" |
| `b-guard` | guard | "review my changes" | a whole-repo audit |
| `c-workflow` | workflow | "implement X" | a one-line fix |
| `d-feature` | feature | "style the UI" | backend perf work |
| _your-config-guard_ | guard | reads config | reading config to understand it |
"""


def _skills_dir(tmp_path: Path, text: str) -> Path:
    d = tmp_path / ".claude" / "skills"
    d.mkdir(parents=True)
    (d / "skill-registry.md").write_text(text, encoding="utf-8")
    return d


# --- parse_registry_rows ---

def test_parse_keeps_only_real_rows():
    rows = sri.parse_registry_rows(SAMPLE_REGISTRY)
    names = [r["name"] for r in rows]
    assert names == ["a-audit", "b-guard", "c-workflow", "d-feature"]
    # header, separator, and the `_your-config-guard_` placeholder are all excluded.
    assert "Skill" not in names and "_your-config-guard_" not in names


def test_parse_extracts_tier_and_columns():
    rows = {r["name"]: r for r in sri.parse_registry_rows(SAMPLE_REGISTRY)}
    assert rows["c-workflow"]["tier"] == "workflow"
    assert rows["c-workflow"]["fires"] == '"implement X"'
    assert rows["c-workflow"]["not_when"] == "a one-line fix"


# --- build_routing_map ---

def test_build_map_orders_by_tier_precedence():
    out = sri.build_routing_map(SAMPLE_REGISTRY)
    assert out is not None
    # Workflow before Guard before Feature before Audit, regardless of registry order.
    order = [out.index(t + ":") for t in ("workflow", "guard", "feature", "audit")]
    assert order == sorted(order)
    # The mandate + tie-break preamble is present.
    assert "1%" in out and "OBJECT not the verb" in out
    # Every real skill and both of its trigger columns are rendered.
    assert "c-workflow — fires:" in out and "not: a one-line fix" in out


def test_build_map_places_unknown_tier_last():
    reg = SAMPLE_REGISTRY + "| `m-meta` | meta | auto-injected | as a destination |\n"
    out = sri.build_routing_map(reg)
    assert out is not None
    assert out.index("meta:") > out.index("audit:")  # custom/meta tier after the known four


def test_build_map_none_when_no_real_rows():
    only_placeholders = "# Skill Registry\n\n| Skill | Tier | Fires | Not |\n|--|--|--|--|\n| _x_ | guard | a | b |\n"
    assert sri.build_routing_map(only_placeholders) is None


# --- build_routing_context (filesystem) ---

def test_context_none_when_registry_missing(tmp_path):
    empty = tmp_path / ".claude" / "skills"
    empty.mkdir(parents=True)
    assert sri.build_routing_context(empty) is None


def test_context_none_when_registry_malformed(tmp_path):
    d = _skills_dir(tmp_path, "this file has no table at all, just prose\n")
    assert sri.build_routing_context(d) is None


def test_context_built_from_registry_file(tmp_path):
    d = _skills_dir(tmp_path, SAMPLE_REGISTRY)
    ctx = sri.build_routing_context(d)
    assert ctx is not None and "c-workflow" in ctx


# --- end-to-end stdin/stdout contract (subprocess) ---

def _run(cwd: Path, env_extra: dict | None = None) -> dict:
    import os
    env = {**os.environ, **(env_extra or {})}
    payload = json.dumps({"cwd": str(cwd)})
    proc = subprocess.run(
        [sys.executable, sri.__file__],
        input=payload, capture_output=True, text=True, env=env,
    )
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


def test_e2e_injects_additional_context(tmp_path):
    _skills_dir(tmp_path, SAMPLE_REGISTRY)
    out = _run(tmp_path)
    inj = out["hookSpecificOutput"]
    assert inj["hookEventName"] == "SessionStart"
    assert "c-workflow" in inj["additionalContext"]


def test_e2e_kill_switch_emits_nothing(tmp_path):
    _skills_dir(tmp_path, SAMPLE_REGISTRY)
    out = _run(tmp_path, {"SKILL_ROUTING_INJECT": "0"})
    assert out == {}


def test_e2e_missing_registry_is_fail_open(tmp_path):
    # No .claude/skills at all -> empty object, exit 0 (never breaks the session).
    out = _run(tmp_path)
    assert out == {}
