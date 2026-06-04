# `ui/web/` — opt-in web dashboard

> An interactive, **localhost-only** dashboard that visualizes the kit's own state
> (skills + tiers, telemetry, tools, hooks, memory budget). It is the **first and only
> runtime dependency** in the whole kit — and it is **isolated here on purpose**. The core
> (`tools/`, `scripts/`, `.claude/hooks/`, `ui/kit_status/`) stays **stdlib-only**; nothing
> here is installed or imported unless you choose to run this dashboard.

## Why this exists (and what it is *not*)

The stdlib report at [`ui/kit_status/`](../kit_status/) already renders the same data as a
self-contained, offline HTML file with **zero dependencies**. This web layer adds *interactive
charts* (Chart.js) on top of the **same single data source** — it does **not** re-implement
data collection. If you don't want a dependency, use `ui/kit_status/`; both are honest about
the same three telemetry states.

- **Not** auto-refreshing / a daemon — it's an on-demand snapshot; reload to re-snapshot.
- **Not** remote/multi-user — localhost, single developer, no auth.
- **Not** force-shipped — `ui/web/` is opt-in: not in `install.py`'s `COPY_MAP`, not a
  manifest root. Removing `ui/web/` breaks nothing in the core or the `ui/kit_status` report.

## Run it

```sh
pip install -r ui/web/requirements.txt     # Flask + Jinja2 — the kit's only runtime deps
python ui/web/app.py                        # → http://127.0.0.1:5151
# or, as a module from the repo root:
python -m ui.web.app
# inspect a different AWB project:
python ui/web/app.py --project /path/to/another/project
```

Flags: `--host`, `--port` (default **5151**; 5000 collides with common dev servers / macOS
AirPlay), `--days` (telemetry window, default 14), `--project`, `--debug`.

## Offline by design

Chart.js and all CSS/JS are **vendored** under [`static/`](static/) — there is no CDN and
the served page makes **no external network request**, so it renders with the network off.

- **Chart.js v4.4.1**, UMD build, vendored at [`static/chart.min.js`](static/chart.min.js).
  Source: `https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js` (MIT licence).
  Obtaining it was a one-time fetch; re-vendoring is the only time the network is touched.
  The trailing `//# sourceMappingURL` comment was stripped so devtools never fetches the map.

## Honesty (load-bearing)

Telemetry has three states — *not-wired* / *wired-but-empty* / *measured* (see
[`.claude/rules/measurement-honesty.md`](../../.claude/rules/measurement-honesty.md)). A skill
is shown **`chưa đo`** (not measured), **never "chết" (dead)**, unless `skill_usage_logger` is
wired **and** the log has data. The activation timeseries chart renders **only when measured**;
otherwise the page shows an honest empty state — never a "pretty zero" implying uncollected data.
The tier-distribution doughnut is a *static* property of the skill set, so it is always shown.

## UI bar

Held to the same discipline as the rest of the kit's UI: semantic design tokens (shared with
`ui/kit_status/template.html`), every transition wrapped in `@media (prefers-reduced-motion:
reduce)` (Chart.js animation is disabled when reduced too), AA-contrast badges (no invisible
white-on-light status chips), ≥44px targets, all UI text in **Vietnamese with diacritics**, and
no AI-fingerprint tells (data-first layout, no centered hero, no generic three-equal-card grid).

## What this does NOT do

- It does not run the heavy gates (pytest) — the dashboard is a read-only snapshot.
- It does not collect data itself — that lives once in `ui/kit_status/generator.gather()`.
- It does not persist anything; every request re-reads the project from disk.
