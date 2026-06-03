"""Tests for tools/memory_sync.py — the leak-gated, fail-closed public-memory sync."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import memory_sync as ms  # noqa: E402
from leak_scan import GENERIC_PATTERNS  # noqa: E402

PATTERNS = list(GENERIC_PATTERNS)


def _fact(dir_: Path, name: str, *, visibility: str | None, body: str = "A generic, leak-free fact.",
          extra_meta: str = "") -> Path:
    """Write a memory fact with optional visibility + extra metadata lines."""
    vis = f"\n  visibility: {visibility}" if visibility else ""
    p = dir_ / f"{name}.md"
    p.write_text(
        f"---\nname: {name}\ndescription: one line.\nmetadata:\n  type: feedback{vis}{extra_meta}\n---\n\n{body}\n",
        encoding="utf-8",
    )
    return p


def _src_tgt(tmp_path: Path) -> tuple[Path, Path]:
    src = tmp_path / "src"; tgt = tmp_path / "tgt"
    src.mkdir(); tgt.mkdir()
    return src, tgt


def test_public_fact_is_synced_and_stripped(tmp_path):
    src, tgt = _src_tgt(tmp_path)
    _fact(src, "alpha", visibility="public", extra_meta="\n  node_type: memory\n  originSessionId: abc-123")
    assert ms.main(["--source", str(src), "--target", str(tgt), "--write"]) == 0
    out = (tgt / "alpha.md")
    assert out.exists()
    text = out.read_text(encoding="utf-8")
    # the per-machine / governance keys are dropped from the published copy
    assert "originSessionId" not in text
    assert "node_type" not in text
    assert "visibility" not in text
    assert "type: feedback" in text  # the meaningful frontmatter survives


def test_unmarked_fact_is_excluded_fail_closed(tmp_path):
    src, tgt = _src_tgt(tmp_path)
    _fact(src, "beta", visibility=None)          # no visibility at all
    ms.main(["--source", str(src), "--target", str(tgt), "--write"])
    assert not (tgt / "beta.md").exists()         # never published by accident


def test_private_fact_is_excluded(tmp_path):
    src, tgt = _src_tgt(tmp_path)
    _fact(src, "gamma", visibility="private")
    ms.main(["--source", str(src), "--target", str(tgt), "--write"])
    assert not (tgt / "gamma.md").exists()


def test_already_published_fact_syncs_without_a_tag(tmp_path):
    src, tgt = _src_tgt(tmp_path)
    _fact(src, "delta", visibility=None, body="Updated body.")   # untagged in source
    (tgt / "delta.md").write_text("---\nname: delta\ndescription: x.\nmetadata:\n  type: feedback\n---\n\nOld body.\n",
                                  encoding="utf-8")                # but already in target
    ms.main(["--source", str(src), "--target", str(tgt), "--write"])
    assert "Updated body." in (tgt / "delta.md").read_text(encoding="utf-8")   # kept in sync


def test_leak_fact_is_excluded_even_if_public(tmp_path):
    src, tgt = _src_tgt(tmp_path)
    # a real-looking AWS key trips a HARD leak pattern; visibility:public must NOT override the gate
    _fact(src, "epsilon", visibility="public", body="key AKIAIOSFODNN7EXAMPLE here")  # leak-scan: ignore[aws_access_key]
    ms.main(["--source", str(src), "--target", str(tgt), "--write"])
    assert not (tgt / "epsilon.md").exists()      # the leak gate wins over the opt-in


def test_dry_run_writes_nothing(tmp_path):
    src, tgt = _src_tgt(tmp_path)
    _fact(src, "zeta", visibility="public")
    assert ms.main(["--source", str(src), "--target", str(tgt), "--check"]) == 0
    assert not (tgt / "zeta.md").exists()          # --check is read-only
    # default (no mode flag) is also a dry-run
    ms.main(["--source", str(src), "--target", str(tgt)])
    assert not (tgt / "zeta.md").exists()


def test_index_and_readme_are_never_synced(tmp_path):
    src, tgt = _src_tgt(tmp_path)
    (src / "MEMORY.md").write_text("# index\n", encoding="utf-8")
    (src / "README.md").write_text("# readme\n", encoding="utf-8")
    _fact(src, "eta", visibility="public")
    ms.main(["--source", str(src), "--target", str(tgt), "--write"])
    assert not (tgt / "MEMORY.md").exists()
    assert not (tgt / "README.md").exists()
    assert (tgt / "eta.md").exists()


def test_orphan_in_target_is_reported_not_deleted(tmp_path, capsys):
    src, tgt = _src_tgt(tmp_path)
    (tgt / "theta.md").write_text("---\nname: theta\ndescription: x.\nmetadata:\n  type: feedback\n---\n\nbody\n",
                                  encoding="utf-8")     # in target, no source backing it
    # theta is "already published" so it would re-sync only if present in source; here it is not
    ms.main(["--source", str(src), "--target", str(tgt), "--write"])
    assert (tgt / "theta.md").exists()                  # NOT auto-deleted
    assert "theta.md" in capsys.readouterr().out        # but surfaced as an orphan


def test_missing_source_dir_errors(tmp_path):
    assert ms.main(["--source", str(tmp_path / "nope"), "--target", str(tmp_path), "--check"]) == 2
