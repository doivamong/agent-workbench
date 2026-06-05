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
- **Not** multi-user — the read-only `/` has no auth (run it localhost, or firewall-gate a LAN
  bind). The opt-in `/admin` surface *can* require a password, which is what lets it open over a
  trusted LAN (see *Password auth* below).
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
AirPlay), `--days` (telemetry window, default 14), `--project`, `--admin` (opt-in action
surface — see below), `--debug`.

## Exposing to a LAN (`--host 0.0.0.0`) — the firewall is the control, not the app

The default bind is `127.0.0.1` (localhost only). Binding to `0.0.0.0` to reach the dashboard
from another device **exposes the read-only page — your skills, telemetry, tools, and memory
budget — to every host on the subnet, with no authentication.** The app does **not** protect
that data; it is read-only by design, but it is not access-controlled. **The actual control is
your OS firewall** — restrict the port to the local subnet (e.g. a `LocalSubnet`-scoped rule),
or don't bind `0.0.0.0` at all. (The opt-in `/admin` *action* surface is separate: it refuses a
`0.0.0.0` bind outright — see below — so a LAN bind never exposes the destructive buttons; only
the read-only data is on the wire **unless you set an admin password** — see *Password auth*.) Note: `ops/dashboard_ctl.py restart` reuses the last-started
host, so a LAN bind survives a no-arg restart (it won't silently revert to localhost).

**Defaulting to a LAN bind (e.g. to view the dashboard from a phone on the same Wi-Fi):** set the
environment variable `AWB_DASHBOARD_HOST=0.0.0.0` on your machine. The shipped default stays
`127.0.0.1` (safe for everyone) — only your machine, with the env var set, defaults to a LAN bind,
so a bare `python ui/web/app.py` or a double-click of `restart_all.bat` binds the LAN with no extra
flag. `/admin` still refuses `0.0.0.0` (run it with `--host 127.0.0.1`), and the firewall is still
the real control. On Windows set it once with `setx AWB_DASHBOARD_HOST 0.0.0.0` (re-open the shell
after), or per-session `set AWB_DASHBOARD_HOST=0.0.0.0`.

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

## Opt-in `/admin` action surface (`--admin`)

`/` is **always read-only**. With `--admin`, the dashboard *also* mounts an action surface at
`/admin` ([`admin.py`](admin.py)) that turns the Phase-1 [`ops/`](../../ops/) engine into web
buttons — **restart**, **snapshot the tree**, **pack a release**, **verify** a release, a
**guarded tree-restore**, plus a **System / LAN** panel (**LAN default on/off**, **open the
firewall**, **autostart on/off**, with the phone URLs and the elevated commands shown). Every
*action* runs the Phase-1 CLI as a **subprocess** (an arg list,
never a shell string — process isolation; the exit code + stderr are surfaced); only read-only
enumeration for the dropdowns imports the APIs directly. Without the flag the blueprint is never
registered, so every `/admin*` path is a plain **404**.

The guards (the design was stress-tested to GO only with all of them):

- **Opt-in, default-off** — no `--admin` → `/admin*` is 404 and no CSRF token is minted.
- **CSRF** — every mutation is POST-only and must carry the per-process `secrets.token_urlsafe`
  token (in a hidden field or `X-CSRF-Token`), checked with `hmac.compare_digest` *before* any
  side effect. GETs never mutate.
- **Host / Origin allowlist** — *without a password* every admin request must arrive on a
  localhost `Host` (and, if present, the bound port); a cross-origin `Origin`/`Referer` is refused.
  *With a password* login is the gate, so a LAN `Host` is allowed (a `SameSite=Strict` session
  cookie + CSRF cover what the host allowlist used to). `--admin` refuses to start under `--debug`
  (the Werkzeug debugger is a remote console), and refuses a `0.0.0.0` bind **unless** an admin
  password is configured.
- **Server-enumerated targets** — the restore/verify target is chosen *by name* from a list this
  server produced (the snapshots / releases dirs); a client-supplied path is rejected. Subprocess
  calls are arg lists, never a shell string.
- **Guarded restore** — dry-run preview → `plan-hash` → apply re-validates that hash (**TOCTOU**:
  aborts with no write if the tree moved), takes an **auto-backup** first, and refuses a dirty
  tree unless `allow_dirty`.
- **Detached self-restart**, and **every action audited** to `.ops/ops.log` (subprocess errors
  surfaced, not swallowed).

### Password auth — open `/admin` over a LAN (Phase A)

By default `/admin` is **localhost-only with no login** (the host allowlist is the only gate). To
reach it from another device (e.g. a phone on the same Wi-Fi) you must set an **admin password**;
that is the only thing that lets `--admin` accept a `0.0.0.0` bind:

```sh
export AWB_ADMIN_PASSWORD='your-strong-passphrase'   # plaintext, hashed at startup
python ui/web/app.py --admin --host 0.0.0.0          # now allowed; without the password it refuses
```

Prefer not to put the plaintext in your environment? Pre-compute the hash and pass it instead —
the plaintext then never touches the env or the process list:

```sh
export AWB_ADMIN_PASSWORD_HASH="$(python -c 'import sys; sys.path.insert(0,"ui/web"); import admin; print(admin.hash_password("your-strong-passphrase"))')"
```

How it works: the password is stored only as a salted **pbkdf2-sha256** hash and compared with
`hmac.compare_digest`; login mints a session cookie (`HttpOnly` + `SameSite=Strict`) that expires
after an idle window; repeated wrong passwords **lock out** the source IP; every login / logout is
audited to `.ops/ops.log`. The CSRF token and the guarded-restore flow still apply on top.

**Changing the password from the web:** once logged in, the **Đổi mật khẩu admin** panel on
`/admin` (POST `/admin/password`, needs the correct old password + a new one ≥8 chars) persists
the new hash to `.ops/admin.hash` (gitignored, never committed). That stored hash **takes
precedence over the env password** and takes effect immediately — no restart. The env var stays
the *bootstrap* secret (its value is simply ignored once a web password is set), so **keep
`AWB_ADMIN_PASSWORD` set** — if you delete it and restart with a `0.0.0.0` bind, startup refuses
the LAN bind because it checks the env at boot. The new password is still **cleartext on HTTP/LAN**
in transit (same honest limit below).

**Honest limit (documented on purpose):**
- *No-password (localhost) mode:* admin **trusts every local process that can reach the bound
  port** — any such process can read the CSRF token from the served page. Opt-in, default-off, and
  **not for shared machines**.
- *Password (LAN) mode:* this is **plain HTTP** — the password and session cookie travel in
  **cleartext** and can be sniffed by anyone on the network path. The password stops a casual
  bystander, **not** a network attacker. Only enable it on a **trusted** LAN; **never** expose it to
  the Internet. (TLS is deliberately out of scope for Phase A — a documented trade-off, not an
  oversight.)

Try it offline (no port opened): `python examples/ops_web_admin_demo.py`.

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
