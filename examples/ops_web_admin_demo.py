#!/usr/bin/env python3
"""Runnable demo for the ui/web /admin action surface (full Approach A — login is the gate).

Drives the admin layer entirely through Flask's in-process test client — **no port is
opened, no server is detached, the live tree is never touched**. It demonstrates the load-
bearing guards on throwaway data in a temp git repo:

  1. inert (no password): /admin is ALWAYS mounted but with no password it is inert — a POST
     action with a VALID CSRF token is 403 on any host, GET /admin redirects to a login page
     you cannot pass (it names AWB_ADMIN_PASSWORD as the way to enable admin).
  2. login          : set a password → GET /admin/login is a form → POST the password → session.
  3. CSRF           : a POST without the per-process token is refused (403); with it, 200.
  4. snapshot       : an authorised POST snapshots the temp tree → .ops/snapshots/.
  5. guarded restore: break a file → preview (dry-run plan-hash) → apply (auto-backup +
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

import admin as webadmin  # noqa: E402
import app as webapp  # noqa: E402
import ops.tree_snapshot as ts  # noqa: E402

_DEMO_PW = "demo-admin-pw"  # leak-scan: ignore — throwaway demo password (≥8 chars)


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

    print("== inert: /admin always mounted, but with NO password it is inert ==")
    ro = webapp.create_app(host="0.0.0.0")  # even a LAN bind: still inert without a password
    ro.config.update(TESTING=True)
    roc = ro.test_client()
    valid_token = ro.config["ADMIN_TOKEN"]  # a real token IS minted (admin always mounted) …
    blocked = roc.post("/admin/action/snapshot",
                       data={"csrf": valid_token}, headers={"Host": "192.168.1.50:5151"})
    print(f"  POST action w/ VALID token on a LAN host → {blocked.status_code} (inert; not the CSRF check)")
    print(f"  GET /admin → {roc.get('/admin').status_code} (redirect to login)")
    login_html = roc.get("/admin/login").get_data(as_text=True)
    names_env = "AWB_ADMIN_PASSWORD" in login_html
    no_setup_form = 'name="password"' not in login_html
    print(f"  login page names AWB_ADMIN_PASSWORD: {names_env}  (no setup form: {no_setup_form})")

    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        repo = _make_repo(tmp)
        # Set a password → /admin is ENABLED; login is the gate.
        app = webapp.create_app(host="127.0.0.1", port=5151,
                                admin_password_hash=webadmin.hash_password(_DEMO_PW))
        app.config.update(TESTING=True, OPS_ROOT=str(repo))
        c = app.test_client()
        token = app.config["ADMIN_TOKEN"]

        print("\n== login: the password opens a session that unlocks /admin ==")
        print(f"  POST /admin/login (right password) → "
              f"{c.post('/admin/login', data={'csrf': token, 'password': _DEMO_PW}).status_code}")
        print(f"  GET /admin (now logged in) → {c.get('/admin').status_code}")

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
