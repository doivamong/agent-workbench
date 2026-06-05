"""Tests for ui/web/ admin layer — the opt-in /admin action surface (Phase 2).

These mirror tests/test_ui_web.py's OPT-IN pattern exactly: a guarded import (never
``importorskip``) keeps every item COLLECTED so tools/readme_metrics.py sees a stable
count dev (Flask present) vs CI (Flask absent); the tests are skipped at run time when
Flask is missing, so the core suite still passes with zero third-party deps.

The load-bearing properties under test are the 9 guards the design was stress-tested on.
The four CRITICAL guards (called out below) are the ones that, if they regress, turn an
opt-in dev convenience into a remote-code-execution surface:

  C1  admin is OFF by default — no --admin → /admin* is 404 and no token is minted.
  C2  CSRF — POST mutations need the per-process token (hmac.compare_digest); GET never mutates.
  C3  Host/Origin allowlist — a foreign Host/Origin is refused; --debug / 0.0.0.0 can't enable admin.
  C4  Restore TOCTOU — a stale plan-hash aborts the apply with NO write; the target is chosen
      from a server-enumerated allowlist, never a client-supplied path.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

# OPT-IN guard — identical rationale to tests/test_ui_web.py (keep items collected for the
# readme_metrics count; skip at run time when Flask is absent).
try:
    import flask  # noqa: F401
    sys.path.insert(0, str(ROOT / "ui" / "web"))
    import app as webapp
    import admin as webadmin
    _HAS_FLASK = True
except ImportError:
    webapp = None
    webadmin = None
    _HAS_FLASK = False

pytestmark = pytest.mark.skipif(
    not _HAS_FLASK, reason="ui/web/ is opt-in; install ui/web/requirements.txt (Flask) to run")


@pytest.fixture(autouse=True)
def _clean_git_env(monkeypatch):
    """Strip inherited GIT_* from the env for every test.

    Defends against the worktree GIT_DIR-leak trap: when the suite runs from a commit hook
    in a linked worktree, GIT_DIR points at the worktree's .git, and tree_snapshot's git
    subprocesses (run with cwd=<temp repo>) would otherwise honour GIT_DIR and read the
    WRONG repo — and the tests' own ``git init/commit`` would corrupt the shared config.
    Deleting these from the process env makes every child git auto-discover from its cwd.
    """
    for k in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE"):
        monkeypatch.delenv(k, raising=False)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _admin_app(ops_root: Path | None = None, *, host: str = "127.0.0.1", port: int = 5151):
    app = webapp.create_app(admin=True, host=host, port=port)
    app.config.update(TESTING=True)
    if ops_root is not None:
        ops_root.mkdir(parents=True, exist_ok=True)
        app.config["OPS_ROOT"] = str(ops_root)
    return app


def _token(app) -> str:
    return app.config["ADMIN_TOKEN"]


def _git(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    return subprocess.run(["git", *args], cwd=str(cwd), env=env,
                          capture_output=True, text=True, check=True)


def _git_repo(tmp: Path) -> Path:
    repo = tmp / "repo"
    (repo / "src").mkdir(parents=True)
    (repo / "src" / "a.py").write_text("print('v1')\n", encoding="utf-8")
    _git(["init", "-q"], repo)
    _git(["add", "-A"], repo)
    _git(["-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "init"], repo)
    return repo


def _snap_dir(repo: Path) -> Path:
    return repo / ".ops" / "snapshots"


def _take_snapshot(repo: Path, label: str = "s"):
    import ops.tree_snapshot as ts
    return ts.snapshot(repo, label=label, snap_dir=_snap_dir(repo))


def _plan_hash_from(html: str) -> str | None:
    m = re.search(r'name="plan_hash"\s+value="([0-9a-f]{64})"', html)
    return m.group(1) if m else None


def _make_project(tmp: Path) -> Path:
    """Minimal AWB project so the read-only views' gather() succeeds."""
    proj = tmp / "proj"
    sk = proj / ".claude" / "skills"
    sk.mkdir(parents=True)
    (sk / "awb-review").mkdir()
    (sk / "awb-review" / "SKILL.md").write_text("# awb-review\n", encoding="utf-8")
    (sk / "skill-registry.md").write_text(
        "| name | tier | f | n |\n|---|---|---|---|\n| awb-review | guard | x | y |\n",
        encoding="utf-8")
    (proj / ".claude" / "settings.json").write_text(
        '{"hooks": {}}', encoding="utf-8")
    (proj / "tools").mkdir()
    (proj / "tools" / "leak_scan.py").write_text("# tool\n", encoding="utf-8")
    return proj


# --------------------------------------------------------------------------- #
# C1 — admin is OFF by default
# --------------------------------------------------------------------------- #
def test_C1_admin_disabled_by_default_is_404(tmp_path):
    app = webapp.create_app()  # no admin=True
    app.config.update(TESTING=True)
    c = app.test_client()
    for path in ("/admin", "/admin/action/snapshot", "/admin/action/restart",
                 "/admin/restore/preview", "/admin/restore/apply"):
        assert c.get(path).status_code == 404, path
        assert c.post(path).status_code == 404, path


def test_C1_no_token_minted_when_admin_off(tmp_path):
    app = webapp.create_app()
    assert "ADMIN_TOKEN" not in app.config
    assert app.config.get("ADMIN") is not True


def test_C1_token_minted_and_per_process_when_admin_on(tmp_path):
    a = _admin_app(tmp_path / "a")
    b = _admin_app(tmp_path / "b")
    assert _token(a) and len(_token(a)) >= 32
    assert _token(a) != _token(b)  # per-process secret, not a shared constant


# --------------------------------------------------------------------------- #
# C2 — CSRF
# --------------------------------------------------------------------------- #
def test_C2_post_without_token_is_403(tmp_path):
    app = _admin_app(tmp_path / "r")
    r = app.test_client().post("/admin/action/snapshot")
    assert r.status_code == 403


def test_C2_post_with_wrong_token_is_403(tmp_path):
    app = _admin_app(tmp_path / "r")
    r = app.test_client().post("/admin/action/snapshot", data={"csrf": "not-the-token"})
    assert r.status_code == 403


def test_C2_post_with_correct_token_succeeds(tmp_path):
    app = _admin_app(tmp_path / "r")
    r = app.test_client().post("/admin/action/snapshot", data={"csrf": _token(app)})
    assert r.status_code == 200


def test_C2_token_also_accepted_via_header(tmp_path):
    app = _admin_app(tmp_path / "r")
    r = app.test_client().post("/admin/action/snapshot",
                               headers={"X-CSRF-Token": _token(app)})
    assert r.status_code == 200


def test_C2_get_on_action_route_never_mutates(tmp_path):
    repo = tmp_path / "r"
    app = _admin_app(repo)
    snaps = _snap_dir(repo)
    before = sorted(snaps.glob("*.zip")) if snaps.exists() else []
    r = app.test_client().get("/admin/action/snapshot")
    assert r.status_code in (404, 405)  # POST-only — GET is not even routed to the action
    after = sorted(snaps.glob("*.zip")) if snaps.exists() else []
    assert before == after  # no snapshot written by a GET


# --------------------------------------------------------------------------- #
# C3 — Host / Origin allowlist + refuse debug / 0.0.0.0
# --------------------------------------------------------------------------- #
def test_C3_foreign_host_is_403(tmp_path):
    app = _admin_app(tmp_path / "r")
    r = app.test_client().post("/admin/action/snapshot",
                               data={"csrf": _token(app)}, headers={"Host": "evil.example"})
    assert r.status_code == 403


def test_C3_foreign_origin_is_403(tmp_path):
    app = _admin_app(tmp_path / "r")
    r = app.test_client().post("/admin/action/snapshot",
                               data={"csrf": _token(app)},
                               headers={"Origin": "http://evil.example"})
    assert r.status_code == 403


def test_C3_localhost_origin_allowed(tmp_path):
    app = _admin_app(tmp_path / "r", port=5151)
    r = app.test_client().post("/admin/action/snapshot",
                               data={"csrf": _token(app)},
                               headers={"Origin": "http://127.0.0.1:5151"})
    assert r.status_code == 200


def test_C3_debug_and_bind_all_refused_under_admin(tmp_path):
    with pytest.raises(ValueError):
        webapp.create_app(admin=True, host="0.0.0.0")
    with pytest.raises(ValueError):
        webapp.create_app(admin=True, debug=True)


def test_C3_cli_refuses_admin_with_debug(tmp_path):
    with pytest.raises(SystemExit):
        webapp.main(["--admin", "--debug"])
    with pytest.raises(SystemExit):
        webapp.main(["--admin", "--host", "0.0.0.0"])


# --------------------------------------------------------------------------- #
# C4 — Restore TOCTOU + server-enumerated targets
# --------------------------------------------------------------------------- #
def test_C4_restore_preview_returns_plan_hash(tmp_path):
    repo = _git_repo(tmp_path)
    z = _take_snapshot(repo)
    app = _admin_app(repo)
    r = app.test_client().post("/admin/restore/preview",
                               data={"csrf": _token(app), "snapshot": z.name})
    assert r.status_code == 200
    assert _plan_hash_from(r.get_data(as_text=True)) is not None


def test_C4_restore_apply_with_stale_hash_aborts_no_write(tmp_path):
    repo = _git_repo(tmp_path)
    z = _take_snapshot(repo)
    app = _admin_app(repo)
    c = app.test_client()
    preview = c.post("/admin/restore/preview",
                     data={"csrf": _token(app), "snapshot": z.name}).get_data(as_text=True)
    stale_hash = _plan_hash_from(preview)

    # Mutate a snapshot member AFTER the preview → the recomputed plan hash will differ.
    (repo / "src" / "a.py").write_text("print('CHANGED')\n", encoding="utf-8")
    r = c.post("/admin/restore/apply",
               data={"csrf": _token(app), "snapshot": z.name,
                     "plan_hash": stale_hash, "allow_dirty": "on"})
    body = r.get_data(as_text=True)
    assert "aborted-stale" in body or "lệch" in body or "thay đổi" in body
    # The load-bearing assertion: the file the engine WOULD have rewritten is untouched.
    assert (repo / "src" / "a.py").read_text(encoding="utf-8") == "print('CHANGED')\n"


def test_C4_restore_rejects_target_not_in_allowlist(tmp_path):
    repo = _git_repo(tmp_path)
    _take_snapshot(repo)
    app = _admin_app(repo)
    c = app.test_client()
    # Critical #1: path traversal AND shell-metachar injection names are both refused — only a
    # server-enumerated id is accepted (the metachars never reach a shell; subprocess is arg-list).
    for bad in ("../../../etc/passwd", "nope.zip", "..\\..\\win.zip", "sub/dir.zip",
                "a;rm -rf.zip", "a|b.zip", "$(whoami).zip"):
        r = c.post("/admin/restore/preview", data={"csrf": _token(app), "snapshot": bad})
        assert r.status_code == 400, bad


def test_C4_restore_apply_happy_path_round_trips(tmp_path):
    repo = _git_repo(tmp_path)
    z = _take_snapshot(repo)
    app = _admin_app(repo)
    c = app.test_client()
    # break the file, then restore it
    (repo / "src" / "a.py").write_text("print('BROKEN')\n", encoding="utf-8")
    preview = c.post("/admin/restore/preview",
                     data={"csrf": _token(app), "snapshot": z.name}).get_data(as_text=True)
    h = _plan_hash_from(preview)
    r = c.post("/admin/restore/apply",
               data={"csrf": _token(app), "snapshot": z.name,
                     "plan_hash": h, "allow_dirty": "on"})
    assert r.status_code == 200
    assert (repo / "src" / "a.py").read_text(encoding="utf-8") == "print('v1')\n"  # restored


# --------------------------------------------------------------------------- #
# Supporting guards
# --------------------------------------------------------------------------- #
def test_admin_source_never_uses_shell_true():
    src = (ROOT / "ui" / "web" / "admin.py").read_text(encoding="utf-8")
    assert "shell=True" not in src  # subprocess arg lists only, never a shell string


def test_restart_is_a_detached_spawn(tmp_path, monkeypatch):
    seen = {}

    def fake_launch(host, port):
        seen["host"], seen["port"] = host, port
        return 4242  # pretend pid; do NOT actually spawn

    monkeypatch.setattr(webadmin, "_launch_restart", fake_launch)
    app = _admin_app(tmp_path / "r", host="127.0.0.1", port=5151)
    r = app.test_client().post("/admin/action/restart", data={"csrf": _token(app)})
    assert r.status_code in (200, 202)
    assert seen == {"host": "127.0.0.1", "port": 5151}


def test_every_action_is_audited(tmp_path):
    repo = tmp_path / "r"
    app = _admin_app(repo)
    app.test_client().post("/admin/action/snapshot", data={"csrf": _token(app)})
    log = repo / ".ops" / "ops.log"
    assert log.exists()
    rec = json.loads(log.read_text(encoding="utf-8").strip().splitlines()[-1])
    assert rec["action"] == "snapshot" and "time" in rec and "result" in rec


def test_restore_refuses_dirty_tree_without_allow_dirty(tmp_path):
    repo = _git_repo(tmp_path)
    z = _take_snapshot(repo)
    app = _admin_app(repo)
    c = app.test_client()
    h = _plan_hash_from(c.post("/admin/restore/preview",
                               data={"csrf": _token(app), "snapshot": z.name}).get_data(as_text=True))
    # Make the tree dirty WITHOUT touching a snapshot member (an untracked file) so the
    # refusal is the dirty guard, not the TOCTOU guard.
    (repo / "untracked.txt").write_text("dirty\n", encoding="utf-8")
    r = c.post("/admin/restore/apply",
               data={"csrf": _token(app), "snapshot": z.name, "plan_hash": h})  # no allow_dirty
    body = r.get_data(as_text=True)
    assert "chưa commit" in body or "dirty" in body or "allow_dirty" in body
    assert (repo / "src" / "a.py").read_text(encoding="utf-8") == "print('v1')\n"  # untouched


def test_pack_then_verify_through_admin(tmp_path):
    # pack builds a real release zip from install.COPY_MAP into OPS_ROOT/.ops/releases,
    # then verify reports it clean. Exercises the server-enumerated release allowlist.
    repo = tmp_path / "r"
    app = _admin_app(repo)
    c = app.test_client()
    rp = c.post("/admin/action/pack", data={"csrf": _token(app)})
    assert rp.status_code == 200
    rels = sorted((repo / ".ops" / "releases").glob("*.zip"))
    assert rels, "pack should have written a release zip"
    rv = c.post("/admin/action/verify",
                data={"csrf": _token(app), "release": rels[0].name})
    assert rv.status_code == 200
    assert "clean" in rv.get_data(as_text=True) or "nguyên vẹn" in rv.get_data(as_text=True)


def test_verify_rejects_release_not_in_allowlist(tmp_path):
    repo = tmp_path / "r"
    app = _admin_app(repo)
    r = app.test_client().post("/admin/action/verify",
                               data={"csrf": _token(app), "release": "../escape.zip"})
    assert r.status_code == 400


def test_admin_page_renders_and_is_offline(tmp_path):
    app = _admin_app(tmp_path / "r")
    html = app.test_client().get("/admin").get_data(as_text=True)
    assert "<form" in html
    assert 'class="btn' in html                      # buttons reuse the >=44px .btn
    assert _token(app) in html                        # CSRF token embedded for the forms
    assert not re.search(r'(?:src|href)="https?://', html)  # offline — no external refs
    assert "cdn" not in html.lower()


def test_readonly_root_still_works_with_admin_enabled(tmp_path):
    proj = _make_project(tmp_path)
    app = _admin_app(tmp_path / "r")
    app.config["PROJECT"] = proj
    r = app.test_client().get("/")
    assert r.status_code == 200
    assert 'href="/admin"' in r.get_data(as_text=True)  # admin link surfaced only when on


def test_readonly_root_has_no_admin_link_when_off(tmp_path):
    proj = _make_project(tmp_path)
    app = webapp.create_app()
    app.config.update(TESTING=True, PROJECT=proj)
    html = app.test_client().get("/").get_data(as_text=True)
    assert 'href="/admin"' not in html


# --- admin.js (restart -> poll /health -> reload) + confirm dialogs ----------
def test_admin_js_is_served_and_offline(tmp_path):
    app = _admin_app(tmp_path / "r")
    r = app.test_client().get("/static/admin.js")
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    assert "/health" in body                    # it polls the liveness probe
    assert "location.reload" in body            # ...and reloads when healthy again
    assert not re.search(r"https?://", body)    # offline, no external fetch


def test_admin_page_loads_admin_js(tmp_path):
    app = _admin_app(tmp_path / "r")
    html = app.test_client().get("/admin").get_data(as_text=True)
    assert "admin.js" in html


def test_restart_result_carries_reconnect_marker(tmp_path, monkeypatch):
    monkeypatch.setattr(webadmin, "_launch_restart", lambda host, port: 4242)
    app = _admin_app(tmp_path / "r", host="127.0.0.1", port=5151)
    r = app.test_client().post("/admin/action/restart", data={"csrf": _token(app)})
    assert r.status_code in (200, 202)
    assert 'data-restart="1"' in r.get_data(as_text=True)  # admin.js keys off this to poll/reload


def test_destructive_restore_has_confirm_dialog(tmp_path):
    repo = _git_repo(tmp_path)
    z = _take_snapshot(repo)
    app = _admin_app(repo)
    preview = app.test_client().post(
        "/admin/restore/preview",
        data={"csrf": _token(app), "snapshot": z.name}).get_data(as_text=True)
    assert "hx-confirm" in preview  # the apply button confirms before overwriting files
