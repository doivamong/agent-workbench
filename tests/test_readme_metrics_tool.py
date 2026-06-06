"""tools/readme_metrics.py — generate / gate the README 'At a glance' counts.

The tool makes the five advertised numbers deterministic from the tree so two branches stop
conflicting on hand-typed counts. These tests pin the compute (from a fixture tree), the staleness
check, and the in-place rewrite (including the three test-count mirrors)."""
import readme_metrics as rm


def _make_tree(tmp_path):
    (tmp_path / "examples").mkdir()
    for n in ("a", "b", "c"):
        (tmp_path / "examples" / f"{n}.py").write_text("x=1\n", encoding="utf-8")
    (tmp_path / "tools").mkdir()
    for n in ("t1", "t2"):
        (tmp_path / "tools" / f"{n}.py").write_text("x=1\n", encoding="utf-8")
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "secrets_guard.py").write_text("x=1\n", encoding="utf-8")
    skills = tmp_path / ".claude" / "skills"
    for n in ("s1", "s2", "s3", "s4"):
        (skills / n).mkdir(parents=True)
        (skills / n / "SKILL.md").write_text("# x\n", encoding="utf-8")
    return tmp_path


def test_compute_static_counts(tmp_path):
    c = rm.compute_static(_make_tree(tmp_path))
    assert c == {"deps": 0, "demos": 3, "tools": 3, "skills": 4}  # 2 tools/ files + secrets_guard


def test_compute_static_without_secrets_guard(tmp_path):
    t = _make_tree(tmp_path)
    (t / "scripts" / "secrets_guard.py").unlink()
    assert rm.compute_static(t)["tools"] == 2


README_FIXTURE = """\
| Reusable core dependencies | **0** (stdlib-only) |
| Tests | **99**, green in CI (...) |
| Runnable demos | **99** (`examples/`) |
| Skills | **99** (...) |
| Standalone tools | **99** (`a`, `b`) |

python -m pytest -q                 # 99 tests

**Agent Workbench** · stdlib-only core · 99 tests · MIT
"""

COUNTS = {"deps": 0, "tests": 353, "demos": 14, "tools": 12, "skills": 15}


def test_find_mismatches_flags_all_stale():
    keys = [k for k, _, _ in rm.find_mismatches(COUNTS, README_FIXTURE)]
    assert keys.count("tests") == 3        # metrics row + Quickstart comment + footer
    assert "demos" in keys and "tools" in keys and "skills" in keys
    assert "deps" not in keys              # already 0 -> not stale


def test_rewrite_fixes_all_numbers():
    out = rm.rewrite(COUNTS, README_FIXTURE)
    assert rm.find_mismatches(COUNTS, out) == []
    assert "Tests | **353**" in out
    assert "# 353 tests" in out
    assert "353 tests · MIT" in out
    assert "Runnable demos | **14**" in out
    assert "Standalone tools | **12**" in out
    assert "(`a`, `b`)" in out             # the hand-maintained list is left untouched


def test_rewrite_idempotent():
    once = rm.rewrite(COUNTS, README_FIXTURE)
    assert rm.rewrite(COUNTS, once) == once


def test_main_check_flags_stale(tmp_path, monkeypatch):
    readme = tmp_path / "README.md"
    readme.write_text(README_FIXTURE, encoding="utf-8")
    monkeypatch.setattr(rm, "compute", lambda root=rm.ROOT: COUNTS)
    assert rm.main(["--check", "--readme", str(readme)]) == 1


def test_main_write_then_check_clean(tmp_path, monkeypatch):
    readme = tmp_path / "README.md"
    readme.write_text(README_FIXTURE, encoding="utf-8")
    monkeypatch.setattr(rm, "compute", lambda root=rm.ROOT: COUNTS)
    assert rm.main(["--write", "--readme", str(readme)]) == 0
    assert rm.main(["--check", "--readme", str(readme)]) == 0


# --- Vietnamese mirror (docs/README.vi.md) --------------------------------------------------

VI_FIXTURE = """\
| Phụ thuộc của lõi tái dùng | **0** (chỉ stdlib) |
| Tests | **99**, xanh trong CI (...) |
| Demo chạy được | **99** (`examples/`) |
| Skills | **99** (...) |
| Tool độc lập | **99** (...) |

python -m pytest -q                 # 99 tests

**Agent Workbench** · lõi chỉ stdlib · 99 tests · MIT
"""


def test_vi_find_mismatches_flags_all_stale():
    keys = [k for k, _, _ in rm.find_mismatches(COUNTS, VI_FIXTURE, rm.VI_PATTERNS)]
    assert keys.count("tests") == 3        # metrics row + Quickstart comment + footer
    assert "demos" in keys and "tools" in keys and "skills" in keys
    assert "deps" not in keys              # already 0 -> not stale


def test_vi_rewrite_fixes_all_numbers():
    out = rm.rewrite(COUNTS, VI_FIXTURE, rm.VI_PATTERNS)
    assert rm.find_mismatches(COUNTS, out, rm.VI_PATTERNS) == []
    assert "Tests | **353**" in out
    assert "# 353 tests" in out
    assert "353 tests · MIT" in out
    assert "Demo chạy được | **14**" in out
    assert "Tool độc lập | **12**" in out


def test_main_default_gates_both_en_and_vi(tmp_path, monkeypatch):
    """The default run (no --readme) must catch staleness in the VI mirror, not just EN —
    the coverage gap that let docs/README.vi.md's counts rot."""
    (tmp_path / "README.md").write_text(README_FIXTURE, encoding="utf-8")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "README.vi.md").write_text(VI_FIXTURE, encoding="utf-8")
    monkeypatch.setattr(rm, "ROOT", tmp_path)
    monkeypatch.setattr(rm, "compute", lambda root=tmp_path: COUNTS)
    assert rm.main(["--check"]) == 1       # both files stale -> red
    assert rm.main(["--write"]) == 0
    assert rm.main(["--check"]) == 0       # both reconciled -> green
