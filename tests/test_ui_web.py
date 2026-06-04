"""Tests for ui/web/ — the opt-in Flask dashboard.

These are OPT-IN: the whole module skips if Flask is not installed, so the core test
suite still passes with zero third-party deps. The load-bearing properties under test:

  - the dashboard renders (200) from generator.gather() data,
  - it is OFFLINE — the served HTML has no external network refs (Chart.js vendored), and
  - it preserves the kit's HONESTY model: telemetry not-wired / wired-but-empty shows
    "chưa đo", never "ứng viên chết" (dead); a fired skill shows "sống".
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

# ui/web/ is OPT-IN: its only dependency is Flask. We deliberately do NOT use
# `pytest.importorskip` at module level, because that drops these tests from
# `pytest --co` entirely when Flask is absent — and tools/readme_metrics.py counts
# COLLECTED tests, so the advertised README count would differ between a dev machine
# (Flask present → 9 collected) and CI (Flask absent → 0 collected), failing the gate.
# Instead: import Flask guardedly so the module ALWAYS imports cleanly, then mark every
# test skipif-no-Flask. The items stay COLLECTED (stable count) but are skipped at run
# time, so the core suite still passes with zero third-party deps installed.
try:
    import flask  # noqa: F401
    sys.path.insert(0, str(ROOT / "ui" / "web"))
    import app as webapp
    _HAS_FLASK = True
except ImportError:
    webapp = None
    _HAS_FLASK = False

pytestmark = pytest.mark.skipif(
    not _HAS_FLASK, reason="ui/web/ is opt-in; install ui/web/requirements.txt (Flask) to run")


def _make_project(tmp: Path, skills: dict[str, str], *, wired: bool = False,
                  fired: dict[str, int] | None = None, memory: bool = True) -> Path:
    """Minimal AWB project tree. skills = {name: tier}; fired = {name: count}."""
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
    (tmp / ".claude" / "settings.json").write_text(json.dumps(settings), encoding="utf-8")

    (tmp / "tools").mkdir()
    (tmp / "tools" / "leak_scan.py").write_text("# tool\n", encoding="utf-8")

    if fired:
        log = tmp / ".claude" / ".logs"
        log.mkdir(parents=True)
        now = datetime.now().isoformat(timespec="seconds")
        lines = [json.dumps({"time": now, "skill": n, "signal": "invoke"})
                 for n, c in fired.items() for _ in range(c)]
        (log / "skill_usage.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")

    if memory:
        mem = tmp / "memory"
        mem.mkdir()
        (mem / "MEMORY.md").write_text("# index\n- [[fact-a]] real\n", encoding="utf-8")
        (mem / "fact-a.md").write_text("a", encoding="utf-8")
    return tmp


def _client(proj: Path, days: int = 14):
    webapp.app.config.update(TESTING=True, DAYS=days, PROJECT=proj)
    return webapp.app.test_client()


def _render(proj: Path, days: int = 14) -> str:
    r = _client(proj, days).get("/")
    assert r.status_code == 200
    return r.get_data(as_text=True)


def test_route_renders_200_and_complete(tmp_path):
    proj = _make_project(tmp_path, {"awb-review": "guard", "awb-tdd": "workflow"})
    html = _render(proj)
    assert html.rstrip().endswith("</html>")
    assert "<body" in html
    assert 'id="chart-data"' in html          # chart payload embedded, not fetched


def test_offline_no_external_refs(tmp_path):
    # The headline offline contract: no external src/href, no CDN, Chart.js vendored.
    proj = _make_project(tmp_path, {"awb-review": "guard"})
    html = _render(proj)
    assert not re.search(r'(?:src|href)="https?://', html)
    assert "cdn" not in html.lower()
    assert "chart.min.js" in html             # vendored, served from /static/


def test_static_chart_js_is_vendored_and_served(tmp_path):
    proj = _make_project(tmp_path, {"awb-review": "guard"})
    r = _client(proj).get("/static/chart.min.js")
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    assert "Chart.js v4.4.1" in body          # the pinned vendored version
    assert "sourceMappingURL" not in body     # stripped → no devtools map fetch


def test_honest_when_telemetry_not_wired(tmp_path):
    proj = _make_project(tmp_path, {"awb-review": "guard", "awb-tdd": "workflow"}, wired=False)
    html = _render(proj)
    assert "Telemetry chưa bật" in html
    assert "chưa đo" in html
    assert "ứng viên chết" not in html        # NEVER dead when unmeasured
    # no timeseries canvas when not measured (no pretty zero)
    assert 'id="chart-timeseries"' not in html


def test_wired_but_empty_log_is_not_dead(tmp_path):
    proj = _make_project(tmp_path, {"awb-review": "guard"}, wired=True)  # no log file
    html = _render(proj)
    assert "ứng viên chết" not in html
    assert "chưa đo" in html
    assert "chưa có dữ liệu" in html          # the wired-but-empty banner


def test_measured_shows_chart_and_dead_candidate(tmp_path):
    proj = _make_project(tmp_path, {"awb-review": "guard", "awb-tdd": "workflow"},
                         wired=True, fired={"awb-review": 3})
    html = _render(proj)
    assert "Telemetry chưa bật" not in html
    assert 'id="chart-timeseries"' in html    # measured → real chart canvas
    assert "ứng viên chết" in html            # awb-tdd: wired + 0 fires
    assert "sống" in html                      # awb-review fired
    # the embedded payload says measured + carries the timeseries
    payload = json.loads(re.search(
        r'<script id="chart-data" type="application/json">(.*?)</script>', html, re.S).group(1))
    assert payload["measured"] is True
    assert payload["timeseries"]["values"]    # non-empty series


def test_tier_distribution_always_present(tmp_path):
    # Tier distribution is a static property of the skill set → honest even unmeasured.
    proj = _make_project(tmp_path, {"awb-review": "guard", "awb-tdd": "workflow"}, wired=False)
    html = _render(proj)
    assert 'id="chart-tiers"' in html
    payload = json.loads(re.search(
        r'<script id="chart-data" type="application/json">(.*?)</script>', html, re.S).group(1))
    assert sum(payload["tiers"]["values"]) == 2


def test_reduced_motion_guard_in_css(tmp_path):
    proj = _make_project(tmp_path, {"awb-review": "guard"})
    css = _client(proj).get("/static/dashboard.css").get_data(as_text=True)
    assert "prefers-reduced-motion: reduce" in css


def test_payload_cannot_break_out_of_json_script_tag(tmp_path):
    # Defence-in-depth: any '<' that reaches the embedded <script type="application/json">
    # must be escaped so a value can't close the tag early. Tier labels flow into the
    # payload, so an exotic tier name with '<' exercises the escape.
    ctx = {
        "skills": [{"name": "a", "tier": "g</script>x", "fired": 0}],
        "wired": False, "daily": [], "labels": [], "total": 0, "dead_candidates": 0,
        "tools_present": [], "tools_missing": [], "events": [], "n_hooks": 0,
        "mem": {"present": False}, "gates": {}, "branch": "x", "commit": "y",
        "today": "01/01/2026", "days": 14,
    }
    view = webapp.build_view(ctx, 14)
    assert "</script>" not in view["chart_json"]   # tag cannot be closed early
    assert "\\u003c" in view["chart_json"]          # '<' escaped to <
