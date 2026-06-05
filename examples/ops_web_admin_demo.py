#!/usr/bin/env python3
"""Runnable demo for the opt-in ui/web /admin action surface (ops Phase 2).

Drives the admin layer entirely through Flask's in-process test client — **no port is
opened, no server is detached, the live tree is never touched**. It demonstrates the load-
bearing guards on throwaway data in a temp git repo:

  1. default-off    : a plain app has no /admin (404), and mints no CSRF token.
  2. CSRF           : a POST without the per-process token is refused (403); with it, 200.
  3. snapshot       : an authorised POST snapshots the temp tree → .ops/snapshots/.
  4. guarded restore: break a file → preview (dry-run plan-hash) → apply (auto-backup +
     TOCTOU re-validate) → file restored. Then a STALE plan-hash is shown to abort with no write.

    python examples/ops_web_admin_demo.py

Needs Flask (the kit's opt-in dependency): pip install -r ui/web/requirements.txt
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "ui" / "web"))

try:
    import flask  # noqa: F401
except ModuleNotFoundError:
    print("ui/web/ is opt-in — install Flask to run this demo:\n"
          "  pip install -r ui/web/requirements.txt")
    raise SystemExit(0)

import app as webapp  # noqa: E402
import ops.tree_snapshot as ts  # noqa: E402


def _git(args: list[str], cwd: Path) -> None:
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    subprocess.run(["git", *args], cwd=str(cwd), env=env, capture_output=True, text=True, check=True)


def _make_repo(tmp: Path) -> Path:
    repo = tmp / "repo"
    (repo / "src").mkdir(parents=True)
    (repo / "src" / "app.py").write_text("print('v1')\n", encoding="utf-8")
    _git(["init", "-q"], repo)
    _git(["add", "-A"], repo)
    _git(["-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "init"], repo)
    return repo


def _plan_hash(html: str) -> str:
    return re.search(r'name="plan_hash"\s+value="([0-9a-f]{64})"', html).group(1)


def main() -> int:
    for k in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE"):
        os.environ.pop(k, None)  # avoid a leaked worktree GIT_DIR redirecting our git calls

    print("== default-off: no --admin → /admin is 404, no token minted ==")
    ro = webapp.create_app()
    ro.config.update(TESTING=True)
    print(f"  GET /admin → {ro.test_client().get('/admin').status_code}   "
          f"ADMIN_TOKEN minted: {'ADMIN_TOKEN' in ro.config}")

    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        repo = _make_repo(tmp)
        app = webapp.create_app(admin=True, host="127.0.0.1", port=5151)
        app.config.update(TESTING=True, OPS_ROOT=str(repo))
        c = app.test_client()
        token = app.config["ADMIN_TOKEN"]

        print("\n== CSRF: POST needs the per-process token ==")
        print(f"  POST /admin/action/snapshot (no token)   → {c.post('/admin/action/snapshot').status_code}")
        r = c.post("/admin/action/snapshot", data={"csrf": token})
        print(f"  POST /admin/action/snapshot (with token) → {r.status_code}")
        snap = sorted((repo / ".ops" / "snapshots").glob("*.zip"))[-1]
        print(f"  snapshot written: {snap.name}")

        print("\n== guarded restore: break → preview → apply (auto-backup + TOCTOU) ==")
        (repo / "src" / "app.py").write_text("print('BROKEN')\n", encoding="utf-8")
        preview = c.post("/admin/restore/preview",
                         data={"csrf": token, "snapshot": snap.name}).get_data(as_text=True)
        h = _plan_hash(preview)
        print(f"  preview plan-hash: {h[:16]}…")
        c.post("/admin/restore/apply",
               data={"csrf": token, "snapshot": snap.name, "plan_hash": h, "allow_dirty": "on"})
        print(f"  after apply, src/app.py = {(repo / 'src' / 'app.py').read_text(encoding='utf-8').strip()!r}")

        print("\n== TOCTOU: a STALE plan-hash aborts with no write ==")
        stale = c.post("/admin/restore/preview",
                       data={"csrf": token, "snapshot": snap.name}).get_data(as_text=True)
        stale_h = _plan_hash(stale)
        (repo / "src" / "app.py").write_text("print('CHANGED-AGAIN')\n", encoding="utf-8")
        body = c.post("/admin/restore/apply",
                      data={"csrf": token, "snapshot": snap.name,
                            "plan_hash": stale_h, "allow_dirty": "on"}).get_data(as_text=True)
        aborted = "aborted-stale" in body
        print(f"  apply with stale hash → aborted-stale: {aborted}  "
              f"(file still {(repo / 'src' / 'app.py').read_text(encoding='utf-8').strip()!r})")

        log = repo / ".ops" / "ops.log"
        print(f"\n  every action audited → {log.name}: {len(log.read_text(encoding='utf-8').splitlines())} lines")

    print("\nAdmin surface driven via the in-process test client (actions run as engine "
          "subprocesses) — no port opened, no live writes.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
