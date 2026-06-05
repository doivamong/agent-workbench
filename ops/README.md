# `ops/` — operating the workbench repo

> Cross-platform, **stdlib-only** tools for working *on this repo* — controlling the
> opt-in dashboard, packaging a release, and snapshotting the working tree. These operate
> on the workbench itself; they are **not** part of `install.py`'s payload and are **not**
> counted among the kit's "standalone tools" (those are the reusable analysis tools in
> [`tools/`](../tools/)).

Each tool is a CLI **and** a callable API. The opt-in [`ui/web`](../ui/web/) admin layer
(`python ui/web/app.py --admin`) runs the **CLIs as subprocesses** for every action (process
isolation; arg lists, never a shell) and imports the APIs only for read-only enumeration — so
there is exactly one implementation behind both the terminal and the web buttons. The
`tree_snapshot` / `release_pack` CLIs take `--root` / `--snap-dir` / `--rel-dir` so a caller can
point them at a tree other than this repo.

Runtime artifacts live under the git-ignored `.ops/` (pidfile, logs, snapshots, release zips,
and the `/admin` action audit `ops.log`).

## The three tools

### `dashboard_ctl.py` — process control for the dashboard
```sh
python ops/dashboard_ctl.py status     # is it up + healthy? (pid · listening · /health)
python ops/dashboard_ctl.py start      # launch detached, wait until healthy
python ops/dashboard_ctl.py stop       # stop the process WE started
python ops/dashboard_ctl.py restart    # stop + start
```
Windows convenience: double-click [`win/restart_all.bat`](win/restart_all.bat) (or
`win/restart_all.ps1`) — thin wrappers that call `restart`. **Honest limit:** it only
stops/restarts the process in its own `.ops/dashboard.pid`; a dashboard you started another
way is invisible to it (it never hunts-and-kills by port). Localhost/single-dev only.

`restart` reuses the host:port the dashboard was last started on (recorded in
`.ops/dashboard.json`), so a LAN bind survives a no-arg restart. To **default** to a LAN bind
(e.g. to reach the read-only page from a phone), set `AWB_DASHBOARD_HOST=0.0.0.0` — the shipped
default stays localhost; the firewall is the control; `/admin` still refuses `0.0.0.0`. See the
"Exposing to a LAN" section of [`ui/web/README.md`](../ui/web/README.md).

One-step helper: [`lan_setup.py`](lan_setup.py) (`status` / `enable` / `disable` / `firewall`).
`enable` sets the env var **and** the persisted start-state to a LAN bind (so the very next
`restart` binds the LAN immediately, before the env var even propagates to a logged-in shell) and
prints your LAN URL(s). The bare CLI prints the firewall command for you; the Windows double-click
[`win/lan_on.bat`](win/lan_on.bat) runs `enable` then **opens the firewall for you via a UAC
prompt** (the env var is set as you; only the firewall step self-elevates). `win/lan_off.bat`
reverts. `/admin` still refuses `0.0.0.0`.
```sh
python ops/lan_setup.py status      # env default · what restart will bind · LAN URL(s)
python ops/lan_setup.py enable       # default to a LAN bind (env + start-state)
```

Start at logon (so the dashboard is there after a reboot): [`autostart.py`](autostart.py)
(`status` / `enable` / `disable`). Windows registers an `ONLOGON` Scheduled Task that runs
`dashboard_ctl start` hidden via `pythonw`; POSIX prints a systemd *user* service. Double-click
[`win/autostart_on.bat`](win/autostart_on.bat) (self-elevates via UAC) / `win/autostart_off.bat`.
It binds whatever `AWB_DASHBOARD_HOST` defaults to — so combine with `lan_setup enable` for a
dashboard that comes up on the LAN every boot. **Honest limit:** that means it's reachable on your
subnet at every logon — the firewall stays the control; `/admin` still refuses `0.0.0.0`.

### `tree_snapshot.py` — a dev safety net
```sh
python ops/tree_snapshot.py snapshot              # zip the tree (respects .gitignore)
python ops/tree_snapshot.py list
python ops/tree_snapshot.py restore <zip>         # DRY-RUN: preview + print a confirm hash
python ops/tree_snapshot.py restore <zip> --confirm <hash> --yes
```
The file set is exactly `git ls-files --cached --others --exclude-standard`. **Honest
limits:** restore is an *overlay* (it writes the snapshot's files; it never deletes files
absent from the snapshot); it is **dry-run by default**, the apply needs the dry-run's plan
hash (so a tree that moved since the preview is refused) and takes an auto-backup first.
Outside a git repo it falls back to a coarser `os.walk` that cannot read `.gitignore`.

### `release_pack.py` — a verifiable release zip
```sh
python ops/release_pack.py pack                    # → .ops/releases/awb-kit-<ver>.zip
python ops/release_pack.py verify <zip>            # recompute every sha vs the manifest
python ops/release_pack.py restore <zip> <dir>     # DRY-RUN unpack (--yes to apply)
```
Packs exactly what `install.py` would deploy — its `COPY_MAP` is the single source of
truth, so the release never drifts from the installer. **Honest limit:** the sha256
manifest proves **integrity** (bytes intact), not **authenticity** (it is not signed). It
packages the kit payload, not the whole repo — use `tree_snapshot.py` for a full-tree backup.

## Try it
```sh
python examples/ops_demo.py            # snapshot↔restore + pack→verify→tamper, on throwaway data
python examples/ops_web_admin_demo.py  # the /admin guards (CSRF, TOCTOU restore) in-process, no port
```

## The `/admin` web layer — always mounted, **login is the gate**

The same three APIs back the web action surface at `/admin`. It is **always mounted**, but with
**no password configured it is inert** — every action is 403 on any host (even with a valid CSRF
token), login is impossible, and `GET /admin` redirects to a login page that names
`AWB_ADMIN_PASSWORD` as the way to enable admin. Setting a password is what enables it; **login**
(not the old `--admin` flag, which is now a no-op) is the gate. On top it adds CSRF (per-process
token + `hmac.compare_digest`), server-enumerated restore / verify targets, the plan-hash
TOCTOU-guarded restore with an auto-backup, a detached self-restart, and an audit of every action
to `.ops/ops.log`. **Honest limit:** once a password is set this is plain HTTP — the password and
session cookie travel in cleartext over a LAN; only enable it on a **trusted** network, never
Internet-facing. Details in [`ui/web/README.md`](../ui/web/README.md).
