"""Structural checks for shipped sub-agents in .claude/agents/."""
import re
from pathlib import Path

AGENTS_DIR = Path(__file__).resolve().parents[1] / ".claude" / "agents"


def _frontmatter(text: str) -> dict:
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.DOTALL)
    assert m, "no YAML frontmatter"
    fm = {}
    for line in m.group(1).splitlines():
        if ":" in line and not line[0].isspace():
            k, v = line.split(":", 1)
            fm[k.strip()] = v.strip()
    return fm


def test_silent_failure_hunter_exists():
    assert (AGENTS_DIR / "silent-failure-hunter.md").is_file()


def test_agent_frontmatter_name_matches_filename():
    for agent in AGENTS_DIR.glob("*.md"):
        fm = _frontmatter(agent.read_text(encoding="utf-8"))
        assert fm.get("name") == agent.stem, f"{agent.name}: name != filename"
        assert fm.get("description"), f"{agent.name}: missing description"


def test_agent_description_stays_tight():
    # The description loads on every Task() routing decision — keep it short
    # (check_context_budget flags > 50 words as critical).
    for agent in AGENTS_DIR.glob("*.md"):
        fm = _frontmatter(agent.read_text(encoding="utf-8"))
        words = len(re.findall(r"\S+", fm["description"]))
        assert words <= 50, f"{agent.name}: description is {words} words (keep <= 50)"


def test_adapted_agent_carries_attribution():
    text = (AGENTS_DIR / "silent-failure-hunter.md").read_text(encoding="utf-8")
    assert "Apache-2.0" in text and "Anthropic" in text, "adapted agent must attribute its source"


def test_sub_agents_doc_references_the_agent():
    doc = (AGENTS_DIR.parent.parent / "docs" / "sub-agents.md").read_text(encoding="utf-8")
    assert "silent-failure-hunter" in doc
