# `ui/web/` — opt-in web dashboard

> An interactive, **localhost-only** dashboard that visualizes the kit's own state
> (skills + tiers, telemetry, tools, hooks, memory budget). It is the **first and only
> runtime dependency** in the whole kit — and it is **isolated here on purpose**. The core
> (`tools/`, `scripts/`, `.claude/hooks/`, `ui/kit_status/`) stays **stdlib-only**; nothing
> here is installed or imported unless you choose to run this dashboard.

## Why this exists (and what it is *not*)

The stdlib report at [`ui/kit_status/`](../kit_status/) already renders the same data as a
self-contained, offline HTML file with **zero dependencies**. This web layer adds *interactive
charts* (Chart.js) and *in-place controls* (HTMX — change the day window, refresh, filter
skills by tier without a full reload) on top of the **same single data source** — it does
**not** re-implement data collection. If you don't want a dependency, use `ui/kit_status/`;
both are honest about the same three telemetry states.

- **Not** auto-refreshing / a daemon — refresh is **manual** (a button re-reads the disk); there
  is no polling, websocket, or background process.
- **Not** remote/multi-user — localhost, single developer, no auth.
- **Not** force-shipped — `ui/web/` is opt-in: not in `install.py`'s `COPY_MAP`, not a
  manifest root. Removing `ui/web/` breaks nothing in the core or the `ui/kit_status` report.

## Run it

```sh
pip install -r ui/web/requirements.txt     # Flask + Jinja2 — the kit's only runtime deps
python ui/web/app.py                        # → http://127.0.0.1:5000
# or, as a module from the repo root:
python -m ui.web.app
# inspect a different AWB project:
python ui/web/app.py --project /path/to/another/project
```

Flags: `--host`, `--port`, `--days` (telemetry window, default 14), `--project`, `--debug`.

## Offline by design

Chart.js and all CSS/JS are **vendored** under [`static/`](static/) — there is no CDN and
the served page makes **no external network request**, so it renders with the network off.

- **Chart.js v4.4.1**, UMD build, vendored at [`static/chart.min.js`](static/chart.min.js).
  Source: `https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js` (MIT licence).
  Obtaining it was a one-time fetch; re-vendoring is the only time the network is touched.
  The trailing `//# sourceMappingURL` comment was stripped so devtools never fetches the map.
- **htmx v2.0.3**, vendored at [`static/htmx.min.js`](static/htmx.min.js).
  Source: `https://cdn.jsdelivr.net/npm/htmx.org@2.0.3/dist/htmx.min.js` (0BSD / MIT licence).
  Drives the in-place controls by fetching server-rendered HTML fragments (same-origin only).

## Dynamic controls (HTMX)

The controls fetch **server-rendered fragments** (no client-side data logic, no JSON API) so
the honesty model lives in exactly one place — Jinja templates fed by `build_view()`:

- **Cửa sổ (day window)** `7 / 14 / 30 ngày` → `GET /fragment?days=N&tier=…` swaps the whole
  data region (`#dyn`); Chart.js re-initialises on `htmx:afterSwap` (old chart destroyed first).
- **Làm mới (refresh)** → re-reads the project from disk and swaps `#dyn`.
- **Lọc loại (tier filter)** → `GET /fragment/skills?tier=…` swaps **only** the skills table
  (`#skills-region`), so the charts are not redrawn. Filtering is a view concern: the headline
  counts and the tier doughnut always reflect the full set.

The day window is whitelisted to `{7, 14, 30}`; a garbage `?days=` falls back to the default
rather than reaching `gather()`. Fragments are partials (no `<html>`), same-origin, offline.

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
