#!/usr/bin/env python3
"""ui/web/app.py — opt-in web dashboard for the kit's own state.

This is the kit's FIRST runtime dependency (Flask + Jinja2), and it is **isolated
here on purpose**: the core (``tools/``, ``scripts/``, ``.claude/hooks/``,
``ui/kit_status/``) stays stdlib-only. This file does not add a dependency to any of
them — it only *reuses* ``ui/kit_status/generator.gather()`` as its single data source,
so there is exactly one place that collects kit state.

Run it (after ``pip install -r ui/web/requirements.txt``):

    python ui/web/app.py                 # serves http://127.0.0.1:5000
    python -m ui.web.app                 # same, as a module (from the repo root)
    python ui/web/app.py --project /path/to/another/awb/project

Offline by design: Chart.js and all CSS/JS are vendored under ``ui/web/static/``;
the served page makes no external network request, so it renders with the network off.

Honesty (load-bearing — see ``.claude/rules/measurement-honesty.md``): telemetry has
three states — *not-wired* / *wired-but-empty* / *measured*. A skill is shown as
``chưa đo`` (not measured), **never "dead"**, unless the logger is wired AND the log has
data. The timeseries chart renders only when measured; otherwise the page shows an honest
empty state — never a "pretty zero" implying data that was not collected.

What this does NOT do: it does not auto-refresh (re-load the page to re-snapshot), does not
run the heavy gates, is localhost/single-dev only (no auth, no remote serving), and does not
re-implement data collection — that lives once in ``generator.gather()``.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

# Reuse the stdlib generator as the ONE data source. It lives in the sibling
# ui/kit_status/ package; put it on the path and import gather(). We do NOT
# re-implement collection here (handover dead-end: "reuse generator.gather()").
HERE = Path(__file__).resolve().parent
_KIT_STATUS = HERE.parent / "kit_status"
sys.path.insert(0, str(_KIT_STATUS))
import generator as ksr  # noqa: E402

try:
    from flask import Flask, render_template, request
except ModuleNotFoundError as exc:  # fail loud with the fix, not a bare ImportError
    raise SystemExit(
        "ui/web/ needs Flask (the kit's only runtime dependency, isolated here).\n"
        "Install it:  pip install -r ui/web/requirements.txt\n"
        f"(original error: {exc})"
    )

# The kit repo root — default project to inspect is the kit itself, so running this
# inside the kit shows the kit's own state. Overridable via CLAUDE_PROJECT_DIR / --project.
_REPO_ROOT = HERE.parent.parent

app = Flask(__name__)


def _project_dir() -> Path:
    return Path(os.environ.get("CLAUDE_PROJECT_DIR", str(_REPO_ROOT))).resolve()


# Vietnamese tier labels (match the kit_status report's vocabulary).
TIER_VI = {
    "workflow": "quy trình",
    "guard": "bảo vệ",
    "feature": "tính năng",
    "audit": "kiểm toán",
    "meta": "điều phối",
}
# Tier accent colors — same palette as ui/kit_status/template.html (--cat-*).
TIER_COLOR = {
    "workflow": "#5B8DC9",
    "guard": "#CC2929",
    "feature": "#3FB37F",
    "audit": "#D6A14B",
    "meta": "#9B7FD4",
}

# Selectable telemetry windows (the only day values the dashboard offers / accepts).
DAY_OPTIONS = [7, 14, 30]
# Tier filter values. "all" plus the five real tiers; ALL_TIERS is the validation set.
TIERS_FOR_FILTER = [{"value": "all", "label": "Tất cả"}] + [
    {"value": t, "label": TIER_VI[t]} for t in ("workflow", "guard", "feature", "audit", "meta")]
ALL_TIERS = {t["value"] for t in TIERS_FOR_FILTER}


def build_view(ctx: dict, days: int, tier: str = "all") -> dict:
    """Shape gather()'s raw dict into what the template + charts need.

    Adds nothing the data doesn't support — every derived value is computed from ctx.
    The ``measured`` flag is the honesty gate: configured AND has data. ``tier`` filters
    only the SKILLS TABLE (a view concern) — counts, the dead tally, and the tier doughnut
    always reflect the full set, so filtering never distorts the honest totals."""
    measured = bool(ctx["wired"]) and ctx["total"] > 0
    if tier not in ALL_TIERS:
        tier = "all"
    skills_table = ([s for s in ctx["skills"] if s["tier"] == tier]
                    if tier != "all" else ctx["skills"])

    # Tier distribution is a STATIC property of the skills (not telemetry), so it is
    # always honest to show — independent of whether telemetry was measured.
    tier_counts: dict[str, int] = {}
    for s in ctx["skills"]:
        tier_counts[s["tier"]] = tier_counts.get(s["tier"], 0) + 1
    tiers = sorted(tier_counts, key=lambda t: (-tier_counts[t], t))
    tier_dist = [
        {"tier": t, "label": TIER_VI.get(t, t), "count": tier_counts[t],
         "color": TIER_COLOR.get(t, "#5B8DC9")}
        for t in tiers
    ]

    mem = ctx["mem"]
    mem_pct = round(mem["used"] / mem["budget"] * 100) if mem.get("present") else None

    # Data handed to Chart.js. Only includes the timeseries when measured — the JS
    # never draws the line chart for an empty/not-wired log (no pretty zero).
    chart_data = {
        "measured": measured,
        "timeseries": {"labels": ctx["labels"], "values": ctx["daily"]} if measured else None,
        "tiers": {
            "labels": [t["label"] for t in tier_dist],
            "values": [t["count"] for t in tier_dist],
            "colors": [t["color"] for t in tier_dist],
        },
    }

    return {
        "ctx": ctx,
        "days": days,
        "day_options": DAY_OPTIONS,
        "tiers_for_filter": TIERS_FOR_FILTER,
        "active_tier": tier,
        "measured": measured,
        "tier_dist": tier_dist,
        "mem_pct": mem_pct,
        "n_skills": len(ctx["skills"]),
        "skills_table": skills_table,
        "dead": ctx["dead_candidates"],
        "n_tools_full": len(ctx["tools_present"]) + len(ctx["tools_missing"]),
        # Embedded as <script type="application/json">. Escape '<' so a skill name like
        # "</script>" can never break out of the tag (defence-in-depth; names are kit-local).
        "chart_json": json.dumps(chart_data, ensure_ascii=False).replace("<", "\\u003c"),
    }


def _parse_days(raw: str | None, default: int) -> int:
    """Whitelist the day window to DAY_OPTIONS — an out-of-range/garbage query never
    reaches gather() (which would otherwise build an arbitrarily long series)."""
    try:
        v = int(raw)
    except (TypeError, ValueError):
        return default
    return v if v in DAY_OPTIONS else default


def _view(days_raw: str | None = None, tier_raw: str | None = None) -> dict:
    """gather() + build_view for the configured project — shared by the page and fragments."""
    days = _parse_days(days_raw, int(app.config.get("DAYS", 14)))
    tier = tier_raw if tier_raw in ALL_TIERS else "all"
    proj = Path(app.config.get("PROJECT", _project_dir()))
    ctx = ksr.gather(proj, days, gates_json=None, run_gates=False)
    return build_view(ctx, days, tier)


@app.route("/")
def dashboard():
    return render_template("dashboard.html.jinja", **_view())


@app.route("/fragment")
def fragment_body():
    """The whole dynamic region (banner + KPIs + grid) — HTMX-swapped on day change / refresh."""
    return render_template("_body.html.jinja",
                           **_view(request.args.get("days"), request.args.get("tier")))


@app.route("/fragment/skills")
def fragment_skills():
    """Just the skills table — HTMX-swapped on tier filter, so the charts are not redrawn."""
    return render_template("_skills.html.jinja",
                           **_view(request.args.get("days"), request.args.get("tier")))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Opt-in web dashboard for the kit's own state.")
    ap.add_argument("--host", default="127.0.0.1", help="bind host (default: 127.0.0.1, localhost-only)")
    ap.add_argument("--port", type=int, default=5000, help="bind port (default: 5000)")
    ap.add_argument("--days", type=int, default=14, help="telemetry window in days (default: 14)")
    ap.add_argument("--project", help="project root to inspect (default: $CLAUDE_PROJECT_DIR or the kit repo)")
    ap.add_argument("--debug", action="store_true", help="Flask debug mode (dev only)")
    args = ap.parse_args(argv)

    app.config["DAYS"] = args.days
    app.config["PROJECT"] = (Path(args.project).resolve() if args.project else _project_dir())
    print(f"Agent Workbench dashboard → http://{args.host}:{args.port}  "
          f"(project: {app.config['PROJECT']})", file=sys.stderr)
    app.run(host=args.host, port=args.port, debug=args.debug)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
