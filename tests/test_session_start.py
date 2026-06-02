"""Tests for the SessionStart primer-injection hook (.claude/hooks/scripts/session_start.py)."""
import session_start


def test_missing_primer_injects_nothing(tmp_path):
    assert session_start.build_primer_context(tmp_path / ".claude" / "session-primer.md") is None


def test_empty_primer_injects_nothing(tmp_path):
    p = tmp_path / "session-primer.md"
    p.write_text("   \n\n", encoding="utf-8")
    assert session_start.build_primer_context(p) is None


def test_present_primer_is_returned(tmp_path):
    p = tmp_path / "session-primer.md"
    p.write_text("Check the skill registry before non-trivial work.\n", encoding="utf-8")
    out = session_start.build_primer_context(p)
    assert out is not None and "skill registry" in out


def test_oversize_primer_is_truncated(tmp_path):
    p = tmp_path / "session-primer.md"
    p.write_text("x" * 5000, encoding="utf-8")
    out = session_start.build_primer_context(p, max_chars=100)
    assert out is not None
    assert len(out) < 5000
    assert "truncated" in out


def test_shipped_primer_is_within_budget():
    # The default primer this repo ships must itself be short (it loads every session).
    from pathlib import Path
    primer = Path(__file__).resolve().parents[1] / ".claude" / "session-primer.md"
    out = session_start.build_primer_context(primer)
    assert out is not None
    assert len(out) <= session_start.MAX_PRIMER_CHARS
