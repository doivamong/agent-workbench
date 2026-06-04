"""Drift-guard: the Vietnamese getting-started's command blocks must stay byte-identical to EN.

``docs/getting-started.vi.md`` duplicates the EN guide's runnable command blocks — the
highest-drift content (a command that changes in one file but not the other silently misleads a
reader). The design rule is "copy, never re-translate the load-bearing bytes; translate only the
prose." This test enforces that rule instead of trusting it: it extracts every ```bash fenced
block from the VI file and asserts each is byte-identical to a block in the EN file. If the EN
guide's commands change and the VI copy isn't re-synced, CI fails — the same way
``readme_metrics.py --check`` gates the README's numbers.

Honest limit: this gates the *code blocks*, not the surrounding Vietnamese prose (which is
hand-maintained and free to differ — that's the point of a translation).
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EN = ROOT / "docs" / "getting-started.md"
VI = ROOT / "docs" / "getting-started.vi.md"


def _bash_blocks(text: str) -> list[str]:
    return re.findall(r"```bash\n(.*?)\n```", text, re.DOTALL)


def test_vi_getting_started_bash_blocks_match_en():
    assert VI.exists(), "docs/getting-started.vi.md is missing."
    en_blocks = _bash_blocks(EN.read_text(encoding="utf-8"))
    vi_blocks = _bash_blocks(VI.read_text(encoding="utf-8"))
    assert vi_blocks, "no ```bash blocks found in docs/getting-started.vi.md"
    drifted = [b for b in vi_blocks if b not in en_blocks]
    assert not drifted, (
        "These command blocks in getting-started.vi.md are not byte-identical to any block in the "
        "EN getting-started.md. Re-copy them verbatim (translate only the surrounding prose):\n\n"
        + "\n--- drifted block ---\n".join(drifted)
    )
