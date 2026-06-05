"""Tests for ui/web/ — the opt-in Flask dashboard.

These are OPT-IN: the whole module skips if Flask is not installed, so the core test
suite still passes with zero third-party deps. The load-bearing properties under test:

  - the dashboard renders (200) from generator.gather() data,
  - it is OFFLINE — the served HTML has no external network refs (Chart.js vendored), and
  - it preserves the kit's HONESTY model: telemetry not-wired / wired-but-empty shows
    "chưa đo", never "ứng viên chết" (dead); a wired 0-fire skill shows "chưa ai gọi
    tên" (un-named, not dead) — or "tự gọi" for a guard; a named skill shows "đã gọi tên".
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


def test_measured_shows_chart_and_named_signal(tmp_path):
    # awb-review (guard) fired; awb-output-guard (guard) and awb-tdd (workflow) did not.
    proj = _make_project(
        tmp_path,
        {"awb-review": "guard", "awb-output-guard": "guard", "awb-tdd": "workflow"},
        wired=True, fired={"awb-review": 3})
    html = _render(proj)
    assert "Telemetry chưa bật" not in html
    assert 'id="chart-timeseries"' in html    # measured → real chart canvas
    assert "ứng viên chết" not in html        # the old death verdict is gone kit-wide
    assert "chưa ai gọi tên" in html          # awb-tdd: non-guard, 0 fires
    assert "tự gọi" in html                   # awb-output-guard: guard 0-fire, neutral badge
    assert "Đang đo theo tên trong prompt" in html   # measured-state caveat present
    assert "đã gọi tên" in html                # awb-review fired (was named)
    # the embedded payload says measured + carries the timeseries
    payload = json.loads(re.search(
        r'<script id="chart-data" type="application/json">(.*?)</script>', html, re.S).group(1))
    assert payload["measured"] is True
    assert payload["timeseries"]["values"]    # non-empty series


def test_caveat_shows_when_only_guard_is_zero(tmp_path):
    # Edge mirror of the static test: the only 0-fire is a guard → dead==0, but the
    # "tự gọi" badge still renders, so the caveat must be gated on n_zero (any zero), not
    # on dead. Catches a regression to `{% elif measured and dead %}` in _body.html.jinja.
    proj = _make_project(tmp_path, {"awb-review": "guard", "awb-output-guard": "guard"},
                         wired=True, fired={"awb-review": 3})
    html = _render(proj)
    assert "tự gọi" in html
    assert "Đang đo theo tên trong prompt" in html


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


# --- HTMX dynamic layer: vendored htmx, fragment routes, tier filter --------

def test_htmx_is_vendored_and_served(tmp_path):
    proj = _make_project(tmp_path, {"awb-review": "guard"})
    r = _client(proj).get("/static/htmx.min.js")
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    assert 'version:"2.0.3' in body          # the pinned vendored version
    assert "sourceMappingURL" not in body    # no devtools map fetch


def test_page_wires_htmx_controls(tmp_path):
    proj = _make_project(tmp_path, {"awb-review": "guard", "awb-tdd": "workflow"})
    html = _render(proj)
    assert "htmx.min.js" in html             # script loaded (vendored, offline)
    assert 'id="dyn"' in html                # the swap target
    assert 'name="days"' in html and 'hx-get="/fragment"' in html
    assert 'name="tier"' in html and 'hx-get="/fragment/skills"' in html
    # no external refs anywhere on the page
    assert not re.search(r'(?:src|href)="https?://', html)


def test_fragment_is_a_partial_not_a_full_page(tmp_path):
    proj = _make_project(tmp_path, {"awb-review": "guard"})
    r = _client(proj).get("/fragment?days=7&tier=all")
    assert r.status_code == 200
    frag = r.get_data(as_text=True)
    assert "<html" not in frag and "<body" not in frag   # a fragment, not a page
    assert 'id="chart-data"' in frag                      # carries fresh chart data
    assert "· 7 ngày" in frag                             # honours the requested window


def test_day_window_is_whitelisted(tmp_path):
    # An out-of-range/garbage window falls back to the default — never reaches gather().
    proj = _make_project(tmp_path, {"awb-review": "guard"})
    c = _client(proj, days=14)
    assert c.get("/fragment?days=9999").status_code == 200
    assert c.get("/fragment?days=abc").status_code == 200
    assert "· 14 ngày" in c.get("/fragment?days=9999").get_data(as_text=True)


def test_skills_fragment_filters_by_tier(tmp_path):
    proj = _make_project(tmp_path, {"awb-review": "guard", "awb-tdd": "workflow",
                                    "awb-cook": "workflow"})
    r = _client(proj).get("/fragment/skills?days=14&tier=guard")
    assert r.status_code == 200
    table = r.get_data(as_text=True)
    assert table.lstrip().startswith("<table")           # table fragment only
    assert "awb-review" in table                          # the guard skill
    assert "awb-tdd" not in table and "awb-cook" not in table  # workflow skills filtered out


def test_tier_filter_does_not_distort_totals(tmp_path):
    # Filtering the table must not change the headline skill count (a view concern only).
    proj = _make_project(tmp_path, {"awb-review": "guard", "awb-tdd": "workflow"})
    body = _client(proj).get("/fragment?tier=guard").get_data(as_text=True)
    assert '>2</span>&nbsp;skill' in body or "2</span>&nbsp;skill" in body  # still counts all 2


def test_fragments_preserve_honesty(tmp_path):
    proj = _make_project(tmp_path, {"awb-review": "guard"}, wired=False)
    frag = _client(proj).get("/fragment").get_data(as_text=True)
    assert "chưa đo" in frag
    assert "ứng viên chết" not in frag
    skills = _client(proj).get("/fragment/skills").get_data(as_text=True)
    assert "chưa đo" in skills and "ứng viên chết" not in skills


def test_fragments_have_no_external_refs(tmp_path):
    proj = _make_project(tmp_path, {"awb-review": "guard"}, wired=True, fired={"awb-review": 2})
    for path in ("/fragment", "/fragment/skills"):
        frag = _client(proj).get(path).get_data(as_text=True)
        assert not re.search(r'(?:src|href)="https?://', frag)
        assert "cdn" not in frag.lower()
