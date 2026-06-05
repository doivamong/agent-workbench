#!/usr/bin/env python3
"""ui/web/app.py — opt-in web dashboard for the kit's own state.

This is the kit's FIRST runtime dependency (Flask + Jinja2), and it is **isolated
here on purpose**: the core (``tools/``, ``scripts/``, ``.claude/hooks/``,
``ui/kit_status/``) stays stdlib-only. This file does not add a dependency to any of
them — it only *reuses* ``ui/kit_status/generator.gather()`` as its single data source,
so there is exactly one place that collects kit state.

Run it (after ``pip install -r ui/web/requirements.txt``):

    python ui/web/app.py                 # serves http://127.0.0.1:5151 (read-only)
    python -m ui.web.app                 # same, as a module (from the repo root)
    python ui/web/app.py --project /path/to/another/awb/project
    python ui/web/app.py --admin         # ALSO mount the opt-in /admin action surface

Offline by design: Chart.js and all CSS/JS are vendored under ``ui/web/static/``;
the served page makes no external network request, so it renders with the network off.

``/`` is **always read-only**. The action surface (restart / snapshot / pack / verify /
guarded tree-restore) lives under ``/admin`` and is mounted ONLY with ``--admin`` (default
OFF → ``/admin*`` is 404). See ``ui/web/admin.py`` for the guards and the honest limit.

Honesty (load-bearing — see ``.claude/rules/measurement-honesty.md``): telemetry has
three states — *not-wired* / *wired-but-empty* / *measured*. A skill is shown as
``chưa đo`` (not measured), **never "dead"**, unless the logger is wired AND the log has
data. The timeseries chart renders only when measured; otherwise the page shows an honest
empty state — never a "pretty zero" implying data that was not collected.

What this does NOT do: it does not auto-refresh (re-load the page to re-snapshot), does not
run the heavy gates, and does not re-implement data collection — that lives once in
``generator.gather()``.
"""
from __future__ import annotations

import argparse
import json
import os
import secrets
import sys
from pathlib import Path

# Reuse the stdlib generator as the ONE data source. It lives in the sibling
# ui/kit_status/ package; put it on the path and import gather(). We do NOT
# re-implement collection here (handover dead-end: "reuse generator.gather()").
HERE = Path(__file__).resolve().parent
# Put this dir on the path too, so the lazy ``import admin`` in create_app() resolves even
# under ``python -m ui.web.app --admin`` (where only cwd, not this dir, is on sys.path).
sys.path.insert(0, str(HERE))
_KIT_STATUS = HERE.parent / "kit_status"
sys.path.insert(0, str(_KIT_STATUS))
import generator as ksr  # noqa: E402

try:
    from flask import Flask, current_app, render_template, request
except ModuleNotFoundError as exc:  # fail loud with the fix, not a bare ImportError
    raise SystemExit(
        "ui/web/ needs Flask (the kit's only runtime dependency, isolated here).\n"
        "Install it:  pip install -r ui/web/requirements.txt\n"
        f"(original error: {exc})"
    )

# The kit repo root — default project to inspect is the kit itself, so running this
# inside the kit shows the kit's own state. Overridable via CLAUDE_PROJECT_DIR / --project.
_REPO_ROOT = HERE.parent.parent


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
        # Any 0-fire skill (guard or not) makes the measured-state caveat relevant — a guard's
        # "tự gọi" badge needs explaining even when `dead` (non-guard zeros) is 0.
        "n_zero": sum(1 for s in ctx["skills"] if s["fired"] == 0) if measured else 0,
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
    """gather() + build_view for the configured project — shared by the page and fragments.

    Reads config off ``current_app`` (not a module global) so the factory can serve more
    than one app (e.g. a read-only app and an admin app) without their config bleeding."""
    cfg = current_app.config
    days = _parse_days(days_raw, int(cfg.get("DAYS", 14)))
    tier = tier_raw if tier_raw in ALL_TIERS else "all"
    proj = Path(cfg.get("PROJECT", _project_dir()))
    ctx = ksr.gather(proj, days, gates_json=None, run_gates=False)
    return build_view(ctx, days, tier)


def create_app(admin: bool = False, *, host: str = "127.0.0.1", port: int = 5151,
               debug: bool = False) -> "Flask":
    """Build the Flask app. ``/`` and the read-only fragments are always present; the
    ``/admin`` action surface is mounted ONLY when ``admin=True``.

    Refuses to mount admin under ``--debug`` (Werkzeug's debugger is an RCE console) or a
    wildcard bind (``0.0.0.0`` exposes the token-readable surface to the whole network) —
    admin is a localhost-only, single-developer convenience (see ui/web/admin.py)."""
    if admin and host in ("0.0.0.0", "::"):
        raise ValueError("--admin refuses a wildcard bind; admin is localhost-only "
                         f"(got --host {host}). Bind 127.0.0.1.")
    if admin and debug:
        raise ValueError("--admin refuses --debug: the Werkzeug debugger is a remote code "
                         "console. Run admin without --debug.")

    app = Flask(__name__)
    app.config["DAYS"] = 14
    app.config["PROJECT"] = _project_dir()
    app.config["ADMIN"] = bool(admin)

    @app.context_processor
    def _inject_admin_flag() -> dict:
        # Templates show the /admin nav link only when the surface is actually mounted.
        return {"admin_enabled": bool(current_app.config.get("ADMIN"))}

    @app.route("/health")
    def health():
        """Cheap liveness probe (no gather()) — used by ops/dashboard_ctl.py's healthcheck."""
        return "ok", 200

    @app.route("/")
    def dashboard():
        return render_template("dashboard.html.jinja", **_view())

    @app.route("/fragment")
    def fragment_body():
        """The whole dynamic region — HTMX-swapped on day change / refresh."""
        return render_template("_body.html.jinja",
                               **_view(request.args.get("days"), request.args.get("tier")))

    @app.route("/fragment/skills")
    def fragment_skills():
        """Just the skills table — HTMX-swapped on tier filter, so charts aren't redrawn."""
        return render_template("_skills.html.jinja",
                               **_view(request.args.get("days"), request.args.get("tier")))

    if admin:
        # Mint a per-process CSRF secret and record the bound host/port for the allowlist.
        # Imported lazily so the read-only app never pulls in the ops engine.
        import admin as _admin  # noqa: PLC0415 — local import keeps read-only path dep-free
        app.config["ADMIN_TOKEN"] = secrets.token_urlsafe(32)
        app.config["HOST"] = host
        app.config["PORT"] = int(port)
        app.config["OPS_ROOT"] = str(_REPO_ROOT)
        app.register_blueprint(_admin.admin_bp, url_prefix="/admin")

    return app


# Module-level read-only app — what `python ui/web/app.py` (no --admin) and the existing
# tests use. The admin app is a SEPARATE instance built in main(), so the default-off app
# can never accidentally carry admin routes.
app = create_app()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Opt-in web dashboard for the kit's own state.")
    ap.add_argument("--host", default="127.0.0.1", help="bind host (default: 127.0.0.1, localhost-only)")
    ap.add_argument("--port", type=int, default=5151,
                    help="bind port (default: 5151 — 5000 collides with common dev servers / macOS AirPlay)")
    ap.add_argument("--days", type=int, default=14, help="telemetry window in days (default: 14)")
    ap.add_argument("--project", help="project root to inspect (default: $CLAUDE_PROJECT_DIR or the kit repo)")
    ap.add_argument("--admin", action="store_true",
                    help="mount the opt-in /admin action surface (localhost-only; default OFF)")
    ap.add_argument("--debug", action="store_true", help="Flask debug mode (dev only; incompatible with --admin)")
    args = ap.parse_args(argv)

    # Fail fast and loud at the CLI boundary (create_app re-checks as defence in depth).
    if args.admin and args.debug:
        raise SystemExit("refusing: --admin is incompatible with --debug (RCE debugger).")
    if args.admin and args.host in ("0.0.0.0", "::"):
        raise SystemExit("refusing: --admin must bind 127.0.0.1 (localhost-only), not "
                         f"{args.host}.")

    built = create_app(admin=args.admin, host=args.host, port=args.port, debug=args.debug)
    built.config["DAYS"] = args.days
    built.config["PROJECT"] = (Path(args.project).resolve() if args.project else _project_dir())

    if args.admin:
        # Record our own PID so ops/dashboard_ctl.py (and the /admin restart button, which
        # spawns it) can find and restart THIS process even if launched directly.
        import admin as _admin  # noqa: PLC0415
        _admin.record_own_pid()
        print("⚠  /admin is MOUNTED. It trusts every local process that can reach the port "
              "(it can read the CSRF token). Opt-in, default-off, not for shared machines.",
              file=sys.stderr)

    print(f"Agent Workbench dashboard → http://{args.host}:{args.port}  "
          f"(project: {built.config['PROJECT']}{', /admin ON' if args.admin else ''})",
          file=sys.stderr)
    built.run(host=args.host, port=args.port, debug=args.debug)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
