# `ops/` — operating the workbench repo

> Cross-platform, **stdlib-only** tools for working *on this repo* — controlling the
> opt-in dashboard, packaging a release, and snapshotting the working tree. These operate
> on the workbench itself; they are **not** part of `install.py`'s payload and are **not**
> counted among the kit's "standalone tools" (those are the reusable analysis tools in
> [`tools/`](../tools/)).

Each tool is a CLI **and** a callable API — the opt-in [`ui/web`](../ui/web/) admin layer
reuses the same functions, so there is exactly one implementation behind both the terminal
and the (future) web buttons.

Runtime artifacts live under the git-ignored `.ops/` (pidfile, log, snapshots, release zips).

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
python examples/ops_demo.py     # snapshot↔restore + pack→verify→tamper, on throwaway data
```
