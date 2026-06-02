"""Tests for tools/memory_snapshot.py."""
import memory_snapshot as ms


def _mem(tmp_path, files: dict) -> object:
    d = tmp_path / "memory"
    d.mkdir()
    for name, body in files.items():
        (d / name).write_text(body, encoding="utf-8")
    return d


def test_snapshot_captures_only_top_level_files(tmp_path):
    d = _mem(tmp_path, {"MEMORY.md": "index", "a.md": "A"})
    (d / "sub").mkdir()
    (d / "sub" / "nested.md").write_text("nested", encoding="utf-8")
    snap = ms.snapshot_memory(d)
    names = {p.name for p in snap.iterdir()}
    assert names == {"MEMORY.md", "a.md"}  # subdir not captured


def test_snapshot_restore_roundtrip(tmp_path):
    d = _mem(tmp_path, {"a.md": "original"})
    ms.snapshot_memory(d)
    (d / "a.md").write_text("DAMAGED", encoding="utf-8")
    snap = ms.resolve_snapshot(d, ref=None, latest=True)
    restored, preserved = ms.restore_snapshot(d, snap, apply=True)
    assert restored == ["a.md"]
    assert (d / "a.md").read_text(encoding="utf-8") == "original"


def test_restore_is_additive_keeps_newer_files(tmp_path):
    d = _mem(tmp_path, {"a.md": "A"})
    ms.snapshot_memory(d)
    (d / "b.md").write_text("created later", encoding="utf-8")  # newer than snapshot
    snap = ms.resolve_snapshot(d, ref=None, latest=True)
    restored, preserved = ms.restore_snapshot(d, snap, apply=True)
    assert restored == ["a.md"]
    assert preserved == ["b.md"]
    assert (d / "b.md").exists()  # not deleted


def test_dry_run_writes_nothing(tmp_path):
    d = _mem(tmp_path, {"a.md": "original"})
    ms.snapshot_memory(d)
    (d / "a.md").write_text("DAMAGED", encoding="utf-8")
    snap = ms.resolve_snapshot(d, ref=None, latest=True)
    ms.restore_snapshot(d, snap, apply=False)
    assert (d / "a.md").read_text(encoding="utf-8") == "DAMAGED"  # untouched


def test_rotate_keeps_only_n(tmp_path):
    d = _mem(tmp_path, {"a.md": "A"})
    for label in ("x1", "x2", "x3"):
        ms.snapshot_memory(d, keep=2, label=label)
    assert len(ms.list_snapshots(d)) == 2


def test_resolve_ambiguous_prefix_raises(tmp_path):
    d = _mem(tmp_path, {"a.md": "A"})
    s1 = ms.snapshot_memory(d, label="dup")
    s2 = ms.snapshot_memory(d, label="dup2")
    # Both share the date prefix; a too-short ref must be rejected, not guessed.
    common = s1.name[:9]
    if s2.name.startswith(common):
        import pytest
        with pytest.raises(FileNotFoundError):
            ms.resolve_snapshot(d, ref=common, latest=False)


def test_kill_switch_blocks_apply(tmp_path, monkeypatch):
    d = _mem(tmp_path, {"a.md": "original"})
    ms.snapshot_memory(d)
    (d / "a.md").write_text("DAMAGED", encoding="utf-8")
    monkeypatch.setenv(ms.KILL_SWITCH_ENV, "0")
    rc = ms.main(["--dir", str(d), "restore", "--latest", "--apply"])
    assert rc == 0
    assert (d / "a.md").read_text(encoding="utf-8") == "DAMAGED"  # refused to write


def test_main_snapshot_then_list(tmp_path):
    d = _mem(tmp_path, {"a.md": "A"})
    assert ms.main(["--dir", str(d), "snapshot"]) == 0
    assert ms.main(["--dir", str(d), "list"]) == 0
