"""Drift-guard: Vietnamese mirror docs must be re-synced when their EN source changes.

Two layers (the second covers a gap in the first):

  A. Fingerprint marker. Each VI mirror carries an HTML comment
     ``<!-- en-sha256: <64-hex> -->``. This test recomputes the sha256 of the EN source
     (newline-normalized, so the fingerprint is stable across CRLF on Windows and LF on CI) and
     fails if the marker is missing, malformed, or stale. Any change to EN — prose, a bullet, a
     number — flips the hash, so the marker can only be made green again by editing the VI file
     and bumping it. This forces the "EN changed, go look at the translation" moment that nothing
     enforced before.

  B. Structural parity. For pairs whose VI deliberately mirrors EN section-for-section, assert the
     same number of ``##``/``###`` headings and the same bullet count *per section*. This gives a
     localized "section <X> has N bullets in EN but M in VI" diagnostic — it is what catches a
     bullet added to EN but not the translation (the failure that motivated this test). It is
     skipped for pairs whose VI is an abridged summary by design (``README.vi``), where a
     section/bullet mismatch is intended, not drift.

Honest limit (PHILOSOPHY tenet 3, self-applied): layer A proves the marker was bumped, and layer
B proves the *skeleton* matches — neither proves the translation is *faithful*. A bumped hash
sitting on a bad translation still passes. The semantic check ("did the meaning carry over, was a
caveat dropped") lives in the awb-review skill, not here.

Companion: ``test_vi_getting_started.py`` gates the byte-identical command blocks; this file gates
the fingerprint and the prose skeleton. The two are complementary.
"""
import hashlib
import re
from collections import namedtuple
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

Pair = namedtuple("Pair", "en vi parity")

# Add a new (EN, VI) mirror here and it is gated automatically.
#   parity=True  -> VI mirrors EN section-for-section (layers A and B both apply)
#   parity=False -> VI is an abridged translation by design (only layer A applies)
VI_PAIRS = [
    Pair("PHILOSOPHY.md",           "docs/PHILOSOPHY.vi.md",       True),
    Pair("README.md",               "docs/README.vi.md",          False),
    Pair("docs/getting-started.md", "docs/getting-started.vi.md", True),
]

_MARKER_RE = re.compile(r"en-sha256:\s*([0-9a-f]{64})")


def _norm(text: str) -> str:
    """Normalize newlines so the fingerprint is stable across CRLF (Windows) and LF (CI)."""
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _en_sha256(en_rel: str) -> str:
    raw = (ROOT / en_rel).read_text(encoding="utf-8")
    return hashlib.sha256(_norm(raw).encode("utf-8")).hexdigest()


def _section_bullets(text: str) -> list:
    """Bullet count per ``## `` section (index 0 = preamble before the first section)."""
    sections = re.split(r"(?m)^## ", _norm(text))
    return [len(re.findall(r"(?m)^[ \t]*- ", s)) for s in sections]


def _heading_counts(text: str) -> tuple:
    t = _norm(text)
    return (len(re.findall(r"(?m)^## ", t)), len(re.findall(r"(?m)^### ", t)))


def _id(pair):
    return pair.vi


@pytest.mark.parametrize("pair", VI_PAIRS, ids=_id)
def test_vi_marker_matches_en(pair):
    vi_path = ROOT / pair.vi
    assert vi_path.exists(), f"{pair.vi} is missing."
    expected = _en_sha256(pair.en)
    m = _MARKER_RE.search(_norm(vi_path.read_text(encoding="utf-8")))
    assert m, (
        f"{pair.vi} has no valid `<!-- en-sha256: <hex> -->` marker. After syncing the "
        f"translation to {pair.en}, add this line near the top:\n"
        f"    <!-- en-sha256: {expected} -->"
    )
    assert m.group(1) == expected, (
        f"{pair.vi} is stale: its en-sha256 marker no longer matches {pair.en} (the EN source "
        f"changed since the translation was last reconciled). Re-sync the translation, then "
        f"update the marker to:\n"
        f"    <!-- en-sha256: {expected} -->\n"
        f"(If the structure changed, the parity test below names the section that drifted.)"
    )


@pytest.mark.parametrize("pair", [p for p in VI_PAIRS if p.parity], ids=_id)
def test_vi_structure_parallel(pair):
    en_text = (ROOT / pair.en).read_text(encoding="utf-8")
    vi_text = (ROOT / pair.vi).read_text(encoding="utf-8")
    assert _heading_counts(vi_text) == _heading_counts(en_text), (
        f"{pair.vi} heading structure drifted from {pair.en}: EN has {_heading_counts(en_text)} "
        f"(##, ###), VI has {_heading_counts(vi_text)}. A section was added or dropped in one but "
        "not the other."
    )
    en_b, vi_b = _section_bullets(en_text), _section_bullets(vi_text)
    assert vi_b == en_b, (
        f"{pair.vi} bullet structure drifted from {pair.en} — a bullet was added/removed in one "
        f"but not the other:\n"
        f"  EN bullets per section: {en_b}\n"
        f"  VI bullets per section: {vi_b}\n"
        "Find the section index whose counts differ and sync the translation."
    )
