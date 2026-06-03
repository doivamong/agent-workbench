"""Tests for tools/memory_recall_doctor.py."""
from pathlib import Path

import memory_recall_doctor as doc


def _fact(name: str) -> str:
    return f"---\nname: {name}\ndescription: a fact.\nmetadata:\n  type: feedback\n---\n\nbody\n"


def _seed(d: Path, facts: int, index_body: str = "# Memory Index\n\n") -> Path:
    d.mkdir(parents=True, exist_ok=True)
    (d / "MEMORY.md").write_text(index_body, encoding="utf-8")
    for i in range(facts):
        (d / f"feedback_{i}.md").write_text(_fact(f"feedback-{i}"), encoding="utf-8")
    return d


def test_mangle_cwd_matches_harness_form():
    # Z:/code/proj_x/sub -> Z--code-proj-x-sub (separators, ':' and '_' all become '-')
    assert doc.mangle_cwd(Path("Z:/code/proj_x/sub")) == "Z--code-proj-x-sub"


def test_missing_live_dir_is_advisory_not_red(tmp_path, capsys):
    # The never-false-RED case: a non-existent live dir must NOT fail, and must say how to fix it.
    template = _seed(tmp_path / "repo_memory", facts=2)
    missing = tmp_path / "nope"
    rc = doc.main(["--dir", str(missing), "--template", str(template), "--project", str(tmp_path)])
    out = capsys.readouterr().out
    assert rc == 0                       # advisory, never red on a missing dir
    assert "NOT found" in out
    assert "pass --dir" in out
    assert str(missing) in out           # prints the path it actually checked


def test_over_budget_index_goes_red(tmp_path, capsys):
    # make-it-go-red: a located live index over the byte budget exits non-zero.
    live = tmp_path / "live"
    live.mkdir()
    (live / "MEMORY.md").write_text("# Memory Index\n\n" + ("x" * 26000), encoding="utf-8")
    rc = doc.main(["--dir", str(live), "--template", str(tmp_path / "repo_memory")])
    out = capsys.readouterr().out
    assert rc == 1
    assert "RED" in out and "OVER budget" in out


def test_healthy_index_is_ok(tmp_path, capsys):
    live = _seed(tmp_path / "live", facts=1)
    rc = doc.main(["--dir", str(live), "--template", str(tmp_path / "repo_memory")])
    out = capsys.readouterr().out
    assert rc == 0
    assert "OK:" in out


def test_template_more_than_live_notes_mismatch(tmp_path, capsys):
    # The core "you curated the wrong dir" signal: template has facts, live has none.
    template = _seed(tmp_path / "repo_memory", facts=3)
    live = _seed(tmp_path / "live", facts=0)
    rc = doc.main(["--dir", str(live), "--template", str(template)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "more facts" in out and "not being recalled" in out


def test_explicit_dir_wins_over_derivation(tmp_path):
    live = _seed(tmp_path / "live", facts=1)
    path, how = doc.resolve_live_dir(tmp_path, live)
    assert path == live
    assert how == "--dir"


def test_autoMemoryDirectory_used_when_no_explicit_dir(tmp_path):
    auto = _seed(tmp_path / "auto", facts=1)
    claude = tmp_path / ".claude"
    claude.mkdir()
    (claude / "settings.json").write_text(
        '{"autoMemoryDirectory": "' + str(auto).replace("\\", "/") + '"}', encoding="utf-8")
    path, how = doc.resolve_live_dir(tmp_path, None)
    assert path == auto
    assert "autoMemoryDirectory" in how
