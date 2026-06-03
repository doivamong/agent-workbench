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


# --- code-review regression tests (PR #8 follow-up) ---

def test_mangle_cwd_dotted_path_doubles_the_dash():
    # A '.claude' worktree path: the harness maps EVERY non-alphanumeric to '-', so '/.' -> '--'.
    assert doc.mangle_cwd(Path("Z:/code/.claude/wt/x")) == "Z--code--claude-wt-x"


def test_non_object_settings_falls_through_to_derived(tmp_path):
    claude = tmp_path / ".claude"
    claude.mkdir()
    (claude / "settings.json").write_text("[1, 2, 3]", encoding="utf-8")  # valid JSON, not an object
    _path, how = doc.resolve_live_dir(tmp_path, None)
    assert how.startswith("derived")  # did not crash; fell through to derivation


def test_non_string_autoMemoryDirectory_falls_through(tmp_path):
    claude = tmp_path / ".claude"
    claude.mkdir()
    (claude / "settings.json").write_text('{"autoMemoryDirectory": 123}', encoding="utf-8")
    _path, how = doc.resolve_live_dir(tmp_path, None)
    assert how.startswith("derived")


def test_derived_branch_wires_mangle_cwd(tmp_path):
    project = tmp_path / "proj"
    project.mkdir()
    path, how = doc.resolve_live_dir(project, None)
    assert how.startswith("derived")
    assert doc.mangle_cwd(project) in str(path) and path.name == "memory"


def test_derived_missing_dir_is_advisory(tmp_path, capsys):
    # No --dir, no settings: derive a path that won't exist -> advisory exit 0, never a false RED.
    project = tmp_path / "proj"
    project.mkdir()
    rc = doc.main(["--project", str(project), "--template", str(_seed(tmp_path / "repo", facts=1))])
    out = capsys.readouterr().out
    assert rc == 0
    assert "derived" in out and "NOT found" in out


def test_no_memory_md_in_live_dir_is_advisory(tmp_path, capsys):
    live = tmp_path / "live"
    live.mkdir()  # exists but has no MEMORY.md -> exercises the 'nothing auto-loads' branch
    rc = doc.main(["--dir", str(live), "--template", str(tmp_path / "repo")])
    out = capsys.readouterr().out
    assert rc == 0
    assert "nothing auto-loads" in out


def test_over_line_count_index_goes_red(tmp_path, capsys):
    live = tmp_path / "live"
    live.mkdir()
    (live / "MEMORY.md").write_text("\n".join(f"- l{i}" for i in range(205)) + "\n", encoding="utf-8")
    rc = doc.main(["--dir", str(live), "--template", str(tmp_path / "repo")])
    out = capsys.readouterr().out
    assert rc == 1  # the line-count clause of the RED trips even though total bytes are tiny
    assert "RED" in out and "lines" in out


def test_doctor_output_is_ascii_safe(tmp_path):
    # Every emitted line must encode as ASCII (a stray non-ASCII char crashes a legacy console).
    live = tmp_path / "live"
    live.mkdir()  # no MEMORY.md -> exercises the line that previously held an em-dash
    report, _ = doc.doctor(tmp_path, live, tmp_path / "repo")
    for line in report:
        line.encode("ascii")  # raises UnicodeEncodeError if any non-ASCII slipped in
