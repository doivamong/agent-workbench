"""Tests for tools/kit_status_report.py — the kit-status HTML generator.

The load-bearing behaviour under test is HONESTY: when telemetry is not wired the
report must say skills are "chưa đo" (not measured), never "dead", and must not
invent gate results. Plus: the output is self-contained (no external network) and
HTML-escapes untrusted names.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ui" / "kit_status"))

import generator as ksr  # noqa: E402


def _make_project(tmp: Path, skills: dict[str, str], *, wired: bool = False,
                  memory: bool = True) -> Path:
    """Build a minimal AWB project tree. skills = {name: tier}."""
    sk = tmp / ".claude" / "skills"
    sk.mkdir(parents=True)
    rows = ["| name | tier | fires | not |", "|---|---|---|---|"]
    for name, tier in skills.items():
        (sk / name).mkdir()
        (sk / name / "SKILL.md").write_text(f"# {name}\n", encoding="utf-8")
        rows.append(f"| {name} | {tier} | x | y |")
    (sk / "skill-registry.md").write_text("\n".join(rows), encoding="utf-8")

    settings = {"hooks": {"UserPromptSubmit": [{"hooks": [
        {"type": "command", "command": "python .../prompt-refiner-inject.py"}]}]}}
    if wired:
        settings["hooks"]["UserPromptSubmit"][0]["hooks"].append(
            {"type": "command", "command": "python .../skill_usage_logger.py"})
    (tmp / ".claude").mkdir(exist_ok=True)
    (tmp / ".claude" / "settings.json").write_text(json.dumps(settings), encoding="utf-8")

    (tmp / "tools").mkdir()
    (tmp / "tools" / "leak_scan.py").write_text("# tool\n", encoding="utf-8")

    if memory:
        mem = tmp / "memory"
        mem.mkdir()
        (mem / "MEMORY.md").write_text("# index\n- [[fact-a]] real\n- [[ghost]] dangling\n",
                                       encoding="utf-8")
        (mem / "fact-a.md").write_text("a", encoding="utf-8")
    return tmp


def _render(proj: Path, days: int = 14, gates_json: str | None = None) -> str:
    return ksr.render(ksr.gather(proj, days, gates_json))


def test_renders_complete_and_self_contained(tmp_path):
    proj = _make_project(tmp_path, {"awb-review": "guard", "awb-tdd": "workflow"})
    html = _render(proj)
    assert html.rstrip().endswith("</html>")
    assert "<body" in html
    # no leftover template placeholders
    import re
    assert not re.search(r"\$[a-z_]{3,}", html)
    # self-contained: no external network references
    assert "http://" not in html and "https://" not in html.replace('xmlns="http', "")
    assert "<script src" not in html and "@import" not in html and "cdn" not in html.lower()


def test_honest_when_telemetry_not_wired(tmp_path):
    proj = _make_project(tmp_path, {"awb-review": "guard", "awb-tdd": "workflow"}, wired=False)
    html = _render(proj)
    assert "Telemetry chưa bật" in html          # the honesty banner
    assert "chưa đo" in html                       # skills marked not-measured
    assert "ứng viên chết" not in html             # NEVER call a skill dead when unmeasured


def test_dead_candidate_only_when_wired_and_zero(tmp_path):
    proj = _make_project(tmp_path, {"awb-review": "guard", "awb-tdd": "workflow"}, wired=True)
    log = proj / ".claude" / ".logs"
    log.mkdir(parents=True)
    now = datetime.now().isoformat(timespec="seconds")
    # awb-review fired; awb-tdd never did
    (log / "skill_usage.jsonl").write_text(
        json.dumps({"time": now, "skill": "awb-review", "signal": "invoke"}) + "\n",
        encoding="utf-8")
    html = _render(proj)
    assert "Telemetry chưa bật" not in html        # wired -> no banner
    assert "ứng viên chết" in html                 # awb-tdd, wired + 0 fires
    assert "sống" in html                          # awb-review fired


def test_wired_but_empty_log_is_not_dead(tmp_path):
    # The logger is configured, but no telemetry has been collected yet. Every skill is
    # 0 fires — but that is "chưa đo", NOT "ứng viên chết" (measurement-honesty trap #1).
    proj = _make_project(tmp_path, {"awb-review": "guard", "awb-tdd": "workflow"}, wired=True)
    # no .claude/.logs/skill_usage.jsonl created -> empty
    html = _render(proj)
    assert "ứng viên chết" not in html
    assert "chưa đo" in html
    assert "chưa có dữ liệu" in html               # the "wired but no data" banner


def test_gates_not_invented(tmp_path):
    proj = _make_project(tmp_path, {"awb-review": "guard"})
    html = _render(proj)
    assert "chưa chạy" in html
    # with explicit gate results it shows them
    gj = tmp_path / "g.json"
    gj.write_text(json.dumps({"leak_scan": True, "pytest": True}), encoding="utf-8")
    html2 = _render(proj, gates_json=str(gj))
    assert "2/2 PASS" in html2


def test_html_escaped(tmp_path):
    # Untrusted strings reach the markup via build() (names, tiers, branch...).
    # Filesystem dir names can't hold '<', so inject at the render layer instead.
    proj = _make_project(tmp_path, {"awb-review": "guard"})
    ctx = ksr.gather(proj, 14, None)
    ctx["skills"].append({"name": "awb-<script>", "tier": "guard", "fired": 0})
    frags = ksr.build(ctx)
    assert "<script>" not in frags["skills"]      # raw injection not emitted
    assert "&lt;script&gt;" in frags["skills"]     # escaped form is


def test_memory_health_reads_real_index(tmp_path):
    proj = _make_project(tmp_path, {"awb-review": "guard"}, memory=True)
    mh = ksr.memory_health(proj)
    assert mh["present"] is True
    assert mh["facts"] == 1
    assert mh["dangling"] == 1   # [[ghost]] has no file


def test_run_gates_skips_absent_tools(tmp_path):
    proj = _make_project(tmp_path, {"awb-review": "guard"})
    res = ksr.run_readonly_gates(proj)
    assert isinstance(res, dict)
    assert "invariants" not in res          # tool absent in fixture -> skipped, not failed
    # gather with run_gates must not crash and must still render
    html = ksr.render(ksr.gather(proj, 14, None, run_gates=True))
    assert html.rstrip().endswith("</html>")


def test_non_numeric_kpi_is_muted_not_a_giant_number(tmp_path):
    proj = _make_project(tmp_path, {"awb-review": "guard"})  # telemetry not wired
    frags = ksr.build(ksr.gather(proj, 14, None))
    # "chưa đo" must not be rendered with the big display-number class
    assert "kit-num--display" not in frags["hero"].split("chưa đo")[0][-80:]
    assert ksr._kpi_display("chưa đo") == ksr._kpi_display("chưa chạy").replace("chưa chạy", "chưa đo")
    assert "kit-num--display" in ksr._kpi_display(42, "lần")


@pytest.mark.parametrize("val,expected", [(5, "5"), (5.9, "5,9"), (10.0, "10"), (0.0, "0")])
def test_vn_num(val, expected):
    assert ksr._vn_num(val) == expected


def test_json_flag_emits_gather_data(tmp_path, capsys):
    # The --json seam ui/web/ consumes: valid JSON of gather()'s dict, no HTML written.
    proj = _make_project(tmp_path, {"awb-review": "guard", "awb-tdd": "workflow"})
    out_html = tmp_path / "should-not-exist.html"
    rc = ksr.main(["--project", str(proj), "--output", str(out_html), "--json"])
    assert rc == 0
    assert not out_html.exists()                       # --json skips HTML
    data = json.loads(capsys.readouterr().out)         # must be valid JSON
    # stable top-level keys ui/web/ relies on
    for key in ("skills", "wired", "daily", "labels", "total", "dead_candidates",
                "tools_present", "tools_missing", "events", "n_hooks", "mem",
                "gates", "branch", "commit", "today", "days"):
        assert key in data, f"missing key: {key}"
    assert {s["name"] for s in data["skills"]} == {"awb-review", "awb-tdd"}
    assert data["wired"] is False                       # telemetry not wired in fixture
