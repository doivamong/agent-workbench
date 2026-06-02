"""Drift-guard for the canonical PHILOSOPHY.md.

The philosophy used to be restated in ~six files with no single source of truth, so the tenets
could drift apart the way the README test count once did (37 -> 60 -> 75). PHILOSOPHY.md is now
canonical; this test keeps it that way, modeled on ``test_readme_metrics.py``.

It is a PYTEST, not an ``invariants.py`` check, on purpose: invariants.py only scans ``.py``
files, so it cannot see these Markdown docs.

What it checks (structural, casing/whitespace-stable):
  1. PHILOSOPHY.md exists and still carries the motto, the four tenet names, and the
     "what would betray this" review section.
  2. Every satellite that quotes the philosophy links back to PHILOSOPHY.md — so a fresh-context
     edit that drops the pointer fails CI.
  3. The distinctive tenet sentences live ONLY in PHILOSOPHY.md (de-duplication). This is the
     load-bearing assertion: it makes "added the link but kept the restated paragraph" — i.e.
     quietly growing a sixth copy — a red build, which checking link-presence alone would miss.

Honest limit (tenet 3, self-applied): this verifies the *structure* of single-sourcing is
intact. It cannot verify the *spirit* was honored — that a guard wasn't oversold, that
SHIPS-vs-BLUEPRINT wasn't blurred. That semantic check lives in the example-review skill.
"""
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CANON = ROOT / "PHILOSOPHY.md"

# Files that quote the philosophy and must defer to the canon (link back, never restate).
SATELLITES = ["README.md", "CLAUDE.md", "AGENTS.md", "CONTRIBUTING.md", "docs/SECURITY.md"]

MOTTO = "best-fit, honest about limits, not gospel"
TENET_NAMES = [
    "Liberation",
    "Utility over metrics",
    "Honesty about limits is the ethical core",
    "Dual, co-equal beneficiary",
]
# Distinctive one-per-tenet sentences that must appear ONLY in PHILOSOPHY.md.
TENET_SENTENCES = [
    "distill the method, never bulk-transfer the source",
    "Don't add features to look bigger",
    "an oversold guard causes the very stumble it should prevent",
    "a droppable day-1 starter framework",
]


def _norm(text: str) -> str:
    """Collapse all whitespace so matches survive Markdown line-wrapping and casing of spaces."""
    return re.sub(r"\s+", " ", text)


def _read(rel: str) -> str:
    return _norm((ROOT / rel).read_text(encoding="utf-8"))


def test_canon_exists():
    assert CANON.exists(), "PHILOSOPHY.md (the canonical philosophy) is missing from the repo root."


def test_canon_has_motto():
    assert MOTTO in _read("PHILOSOPHY.md"), (
        f"PHILOSOPHY.md no longer contains the canonical motto '{MOTTO}'. "
        "If the wording moved on purpose, update it here and in the satellites that quote it."
    )


@pytest.mark.parametrize("name", TENET_NAMES)
def test_canon_has_tenet(name):
    assert name in _read("PHILOSOPHY.md"), (
        f"PHILOSOPHY.md is missing the tenet '{name}'. The four tenets are load-bearing; "
        "don't drop one. If the philosophy genuinely moved, change it here (the canon)."
    )


def test_canon_has_betrayal_checklist():
    assert "What would betray this" in _read("PHILOSOPHY.md"), (
        "PHILOSOPHY.md lost its 'What would betray this' review checklist — the section that "
        "turns honesty-about-limits into something a reviewer can run against a diff."
    )


@pytest.mark.parametrize("rel", SATELLITES)
def test_satellite_links_back(rel):
    assert "PHILOSOPHY.md" in _read(rel), (
        f"{rel} quotes the philosophy but no longer links to PHILOSOPHY.md. Restore the link — "
        "satellites must defer to the canon, not float free."
    )


@pytest.mark.parametrize("sentence", TENET_SENTENCES)
def test_tenet_sentence_is_single_sourced(sentence):
    assert _norm(sentence) in _read("PHILOSOPHY.md"), (
        f"The canonical sentence '{sentence}' vanished from PHILOSOPHY.md."
    )
    duplicated = [rel for rel in SATELLITES if _norm(sentence) in _read(rel)]
    assert not duplicated, (
        f"The canonical tenet sentence '{sentence}' was copied into {duplicated}. "
        "Satellites must quote+link, not restate the tenets — delete the duplicated prose and "
        "leave a link to PHILOSOPHY.md, or this becomes another drifting copy."
    )
