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


def test_engine_actions_run_via_subprocess_arglist(tmp_path, monkeypatch):
    # D4: every engine ACTION runs through _run_engine as an arg-list subprocess (process
    # isolation; exit/stderr surfaced), never in-process and never a shell string. Spy on the
    # seam and assert snapshot drives the tree_snapshot CLI with --root, as a list of strings.
    calls = []

    def spy(script, cli_args):
        calls.append((script, cli_args))
        return 0, {"path": str(tmp_path / "fake.zip")}, ""

    monkeypatch.setattr(webadmin, "_run_engine", spy)
    app = _admin_app(tmp_path / "r")
    r = app.test_client().post("/admin/action/snapshot", data={"csrf": _token(app)})
    assert r.status_code == 200
    assert len(calls) == 1
    script, cli_args = calls[0]
    assert script.name == "tree_snapshot.py"
    assert isinstance(cli_args, list) and all(isinstance(a, str) for a in cli_args)
    assert "--root" in cli_args and "snapshot" in cli_args


def test_engine_subprocess_error_is_surfaced_not_swallowed(tmp_path, monkeypatch):
    # guard #9: a non-zero engine exit + stderr is shown, not silently swallowed.
    monkeypatch.setattr(webadmin, "_run_engine",
                        lambda s, a: (1, None, "boom: engine failed"))
    app = _admin_app(tmp_path / "r")
    r = app.test_client().post("/admin/action/pack", data={"csrf": _token(app)})
    assert r.status_code == 500
    assert "boom: engine failed" in r.get_data(as_text=True)


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


# --------------------------------------------------------------------------- #
# Phase A — auth (token/password login so /admin can be opened over LAN)
# --------------------------------------------------------------------------- #
# B1 — password hashing: stdlib pbkdf2, salted, constant-time verify, never plaintext.
def test_password_hash_roundtrips_and_rejects_wrong():
    h = webadmin.hash_password("correct horse battery staple")
    assert webadmin.verify_password("correct horse battery staple", h) is True
    assert webadmin.verify_password("wrong", h) is False


def test_password_hash_is_salted_and_never_plaintext():
    h1 = webadmin.hash_password("hunter2")
    h2 = webadmin.hash_password("hunter2")
    assert "hunter2" not in h1          # the stored form never contains the password
    assert h1 != h2                     # a random salt makes each hash unique
    assert webadmin.verify_password("hunter2", h2)  # ...yet both still verify


def test_verify_password_tolerates_garbage_stored_value():
    # A malformed/empty stored hash must verify False, not raise — defensive at the boundary.
    for bad in ("", "not-a-hash", "pbkdf2_sha256$x$y", "$$$"):
        assert webadmin.verify_password("anything", bad) is False


def _auth_app(ops_root: Path | None = None, *, password: str = "s3cret-pw",
              host: str = "127.0.0.1", port: int = 5151):
    """An /admin app with auth CONFIGURED (a password hash) — so login is required."""
    app = webapp.create_app(admin=True, host=host, port=port,
                            admin_password_hash=webadmin.hash_password(password))
    app.config.update(TESTING=True)
    if ops_root is not None:
        ops_root.mkdir(parents=True, exist_ok=True)
        app.config["OPS_ROOT"] = str(ops_root)
    return app


# B2 — when a password is configured, every /admin path requires a logged-in session.
def test_auth_unauthenticated_get_admin_redirects_to_login(tmp_path):
    app = _auth_app(tmp_path / "r")
    r = app.test_client().get("/admin")
    assert r.status_code == 302
    assert "/admin/login" in r.headers["Location"]


def test_auth_unauthenticated_action_is_401_even_with_valid_csrf(tmp_path):
    app = _auth_app(tmp_path / "r")
    # A valid CSRF token is NOT a substitute for a login session.
    r = app.test_client().post("/admin/action/snapshot", data={"csrf": _token(app)})
    assert r.status_code == 401


# B3 — login: the login page is reachable unauthenticated; the right password opens a
# session that unlocks /admin; a wrong password is refused and audited.
def test_auth_login_page_reachable_unauthenticated(tmp_path):
    app = _auth_app(tmp_path / "r")
    r = app.test_client().get("/admin/login")
    assert r.status_code == 200
    assert "<form" in r.get_data(as_text=True)
    assert _token(app) in r.get_data(as_text=True)  # CSRF token embedded for the login POST


def test_auth_login_correct_password_unlocks_admin(tmp_path):
    app = _auth_app(tmp_path / "r", password="open-sesame")  # leak-scan: ignore
    c = app.test_client()
    r = c.post("/admin/login", data={"csrf": _token(app), "password": "open-sesame"})
    assert r.status_code in (200, 302)
    assert c.get("/admin").status_code == 200                       # page now reachable
    assert c.post("/admin/action/snapshot",
                  data={"csrf": _token(app)}).status_code == 200     # ...and actions work


def test_auth_login_wrong_password_refused_and_audited(tmp_path):
    repo = tmp_path / "r"
    app = _auth_app(repo, password="right-one")  # leak-scan: ignore
    c = app.test_client()
    r = c.post("/admin/login", data={"csrf": _token(app), "password": "WRONG"})
    assert r.status_code == 401
    assert c.get("/admin").status_code == 302                       # still locked out
    recs = [json.loads(ln) for ln in
            (repo / ".ops" / "ops.log").read_text(encoding="utf-8").splitlines()]
    assert any(r["action"] == "login" and r["result"] == "failed" for r in recs)


# B4 — lockout: after enough failed attempts the source is temporarily refused, so even the
# CORRECT password can't get in (brute-force guard).
def test_auth_lockout_refuses_even_correct_password(tmp_path):
    repo = tmp_path / "r"
    app = _auth_app(repo, password="right-one")  # leak-scan: ignore
    c = app.test_client()
    for _ in range(6):  # exhaust the attempt budget
        c.post("/admin/login", data={"csrf": _token(app), "password": "nope"})
    r = c.post("/admin/login", data={"csrf": _token(app), "password": "right-one"})
    assert r.status_code == 429                         # locked out despite correct password
    assert c.get("/admin").status_code == 302           # still not authenticated
    recs = [json.loads(ln) for ln in
            (repo / ".ops" / "ops.log").read_text(encoding="utf-8").splitlines()]
    assert any(r["action"] == "login" and r["result"] == "locked-out" for r in recs)


# B5 — the session cookie is hardened, and an idle session expires (forces re-login).
def test_auth_session_cookie_is_httponly_and_samesite_strict(tmp_path):
    app = _auth_app(tmp_path / "r", password="pw")
    c = app.test_client()
    r = c.post("/admin/login", data={"csrf": _token(app), "password": "pw"})
    set_cookie = r.headers.get("Set-Cookie", "")
    assert "HttpOnly" in set_cookie
    assert "SameSite=Strict" in set_cookie


def test_auth_idle_session_expires_and_requires_relogin(tmp_path):
    app = _auth_app(tmp_path / "r", password="pw")
    c = app.test_client()
    c.post("/admin/login", data={"csrf": _token(app), "password": "pw"})
    assert c.get("/admin").status_code == 200            # freshly logged in
    with c.session_transaction() as sess:                # forge an old login time
        sess["login_at"] = "2000-01-01T00:00:00"
    assert c.get("/admin").status_code == 302            # idle past timeout → back to login


# B6 — a LAN (wildcard) bind under --admin is refused WITHOUT auth but allowed WITH it; once
# auth is on, a request arriving with a LAN Host passes the host gate (login is the real gate).
def test_auth_lan_bind_refused_without_password_allowed_with(tmp_path):
    with pytest.raises(ValueError):
        webapp.create_app(admin=True, host="0.0.0.0")            # no auth → refused
    app = webapp.create_app(admin=True, host="0.0.0.0",
                            admin_password_hash=webadmin.hash_password("pw"))
    assert app.config["ADMIN"] is True                          # built without raising


def test_auth_lan_host_passes_host_gate_when_auth_enabled(tmp_path):
    app = _auth_app(tmp_path / "r", host="0.0.0.0", port=5151)
    c = app.test_client()
    lan = {"Host": "192.168.1.50:5151"}
    # A LAN Host is NOT a blocked-host 403 — it bounces to login (auth is the gate, not the host).
    r = c.get("/admin", headers=lan)
    assert r.status_code == 302 and "/admin/login" in r.headers["Location"]
    # Log in over the LAN host, then the LAN request is served.
    c.post("/admin/login", data={"csrf": _token(app), "password": "s3cret-pw"}, headers=lan)
    assert c.get("/admin", headers=lan).status_code == 200


def test_no_auth_admin_still_blocks_foreign_host(tmp_path):
    # Back-compat: without a password, the localhost host-allowlist is still the gate.
    app = _admin_app(tmp_path / "r")
    r = app.test_client().get("/admin", headers={"Host": "192.168.1.50:5151"})
    assert r.status_code == 403


# B7 — back-compat: localhost admin WITHOUT a password needs no login at all.
def test_no_auth_admin_needs_no_login(tmp_path):
    app = _admin_app(tmp_path / "r")
    c = app.test_client()
    assert c.get("/admin").status_code == 200                          # no login redirect
    assert c.post("/admin/action/snapshot",
                  data={"csrf": _token(app)}).status_code == 200


# Wiring — main()/env resolves the admin password; a LAN bind needs it.
def test_resolve_admin_password_hash_from_env(monkeypatch):
    monkeypatch.delenv("AWB_ADMIN_PASSWORD", raising=False)
    monkeypatch.delenv("AWB_ADMIN_PASSWORD_HASH", raising=False)
    assert webapp._resolve_admin_password_hash() == ""                 # neither set → no auth
    monkeypatch.setenv("AWB_ADMIN_PASSWORD", "from-plain")
    assert webadmin.verify_password("from-plain", webapp._resolve_admin_password_hash())
    monkeypatch.setenv("AWB_ADMIN_PASSWORD_HASH", "pre-computed-wins")
    assert webapp._resolve_admin_password_hash() == "pre-computed-wins"  # explicit hash wins


def test_cli_admin_lan_refused_without_password(monkeypatch):
    monkeypatch.delenv("AWB_ADMIN_PASSWORD", raising=False)
    monkeypatch.delenv("AWB_ADMIN_PASSWORD_HASH", raising=False)
    with pytest.raises(SystemExit):
        webapp.main(["--admin", "--host", "0.0.0.0"])


def test_auth_logout_clears_session(tmp_path):
    app = _auth_app(tmp_path / "r", password="pw")
    c = app.test_client()
    c.post("/admin/login", data={"csrf": _token(app), "password": "pw"})
    assert c.get("/admin").status_code == 200
    c.post("/admin/logout", data={"csrf": _token(app)})
    assert c.get("/admin").status_code == 302   # session cleared → bounced back to login


# --------------------------------------------------------------------------- #
# Phase B — lan_setup / autostart on /admin (system panel + web-safe toggles)
# --------------------------------------------------------------------------- #
# BB1 — the /admin page shows a read-only System panel sourced from the lan_setup /
# autostart status APIs (monkeypatched here so the test is hermetic + fast).
def test_admin_page_shows_system_panel(tmp_path, monkeypatch):
    monkeypatch.setattr(webadmin.lans, "status", lambda port=5151: {
        "effective_bind": "0.0.0.0", "lan_default": True,
        "lan_urls": ["http://192.168.1.50:5151"],
        "firewall_command": "powershell -Command New-NetFirewallRule-AWB"})
    monkeypatch.setattr(webadmin.autos, "status", lambda: {"registered": True, "runs": "x"})
    html = _admin_app(tmp_path / "r").test_client().get("/admin").get_data(as_text=True)
    assert "192.168.1.50:5151" in html                 # phone URL surfaced
    assert "New-NetFirewallRule-AWB" in html           # firewall command shown (run elevated)
    assert "đã bật" in html                             # autostart registered state shown
    for url in ("/admin/action/lan-enable", "/admin/action/lan-disable",
                "/admin/action/firewall-open", "/admin/action/autostart-enable",
                "/admin/action/autostart-disable"):
        assert url in html                              # each action button is wired


def test_system_status_helper_merges_both_tools(tmp_path, monkeypatch):
    monkeypatch.setattr(webadmin.lans, "status", lambda port=5151: {"lan_default": False})
    monkeypatch.setattr(webadmin.autos, "status", lambda: {"registered": False})
    app = _admin_app(tmp_path / "r")
    with app.app_context():
        st = webadmin._system_status()
    assert st["lan"]["lan_default"] is False and st["autostart"]["registered"] is False


# BB2 — LAN enable/disable run lan_setup via subprocess (arg list); these need no admin.
def test_lan_enable_runs_lan_setup_enable(tmp_path, monkeypatch):
    calls = []

    def spy(script, cli_args):
        calls.append((script, cli_args))
        return 0, {"action": "enable", "lan_urls": ["http://192.168.1.50:5151"]}, ""

    monkeypatch.setattr(webadmin, "_run_engine", spy)
    app = _admin_app(tmp_path / "r")
    r = app.test_client().post("/admin/action/lan-enable", data={"csrf": _token(app)})
    assert r.status_code == 200
    script, cli_args = calls[-1]
    assert script.name == "lan_setup.py"
    assert "enable" in cli_args and "--json" in cli_args


def test_lan_disable_runs_lan_setup_disable(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(webadmin, "_run_engine",
                        lambda s, a: (calls.append((s, a)) or (0, {"action": "disable"}, "")))
    app = _admin_app(tmp_path / "r")
    r = app.test_client().post("/admin/action/lan-disable", data={"csrf": _token(app)})
    assert r.status_code == 200
    assert calls[0][0].name == "lan_setup.py" and "disable" in calls[0][1]


def test_lan_action_requires_csrf(tmp_path):
    app = _admin_app(tmp_path / "r")
    assert app.test_client().post("/admin/action/lan-enable").status_code == 403


# BB3 — firewall + autostart actions run the engines; an elevation failure is surfaced
# honestly (the page tells you to run the self-elevating .bat), not silently swallowed.
def test_firewall_open_runs_engine(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(webadmin, "_run_engine",
                        lambda s, a: (calls.append((s, a)) or (0, {"result": "opened"}, "")))
    app = _admin_app(tmp_path / "r")
    r = app.test_client().post("/admin/action/firewall-open", data={"csrf": _token(app)})
    assert r.status_code == 200
    assert calls[0][0].name == "lan_setup.py" and "firewall" in calls[0][1]


def test_firewall_needs_admin_is_surfaced_not_swallowed(tmp_path, monkeypatch):
    monkeypatch.setattr(webadmin, "_run_engine",
                        lambda s, a: (0, {"result": "failed", "detail": "needs administrator",
                                          "command": "powershell New-NetFirewallRule"}, ""))
    app = _admin_app(tmp_path / "r")
    body = app.test_client().post("/admin/action/firewall-open",
                                  data={"csrf": _token(app)}).get_data(as_text=True)
    assert "lan_on.bat" in body or "admin" in body.lower()      # tells the user how to elevate


def test_autostart_enable_runs_engine(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(webadmin, "_run_engine",
                        lambda s, a: (calls.append((s, a)) or (0, {"result": "enabled"}, "")))
    app = _admin_app(tmp_path / "r")
    r = app.test_client().post("/admin/action/autostart-enable", data={"csrf": _token(app)})
    assert r.status_code == 200
    assert calls[0][0].name == "autostart.py" and "enable" in calls[0][1]


def test_autostart_disable_runs_engine(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(webadmin, "_run_engine",
                        lambda s, a: (calls.append((s, a)) or (0, {"result": "removed"}, "")))
    app = _admin_app(tmp_path / "r")
    r = app.test_client().post("/admin/action/autostart-disable", data={"csrf": _token(app)})
    assert r.status_code == 200
    assert calls[0][0].name == "autostart.py" and "disable" in calls[0][1]


# --------------------------------------------------------------------------- #
# Phase A.1 — change the admin password from the web (persistent hash store)
# --------------------------------------------------------------------------- #
def _pw_store(ops_root: Path) -> Path:
    return ops_root / ".ops" / "admin.hash"


# CB1 — the persistent store overrides the env password (a web-set password survives restart
# and takes precedence over the bootstrap env password).
def test_pw_store_overrides_env_password(tmp_path):
    repo = tmp_path / "r"
    app = _auth_app(repo, password="env-pw")
    store = _pw_store(repo)
    store.parent.mkdir(parents=True, exist_ok=True)
    store.write_text(webadmin.hash_password("the-web-password"), encoding="utf-8")
    assert app.test_client().post(
        "/admin/login", data={"csrf": _token(app), "password": "the-web-password"}).status_code == 302
    assert app.test_client().post(
        "/admin/login", data={"csrf": _token(app), "password": "env-pw"}).status_code == 401


# CB2 — /admin/password: logged in + correct old → writes the store; new password then works.
def test_change_password_updates_store_and_takes_effect(tmp_path):
    repo = tmp_path / "r"
    app = _auth_app(repo, password="old-pass")          # leak-scan: ignore
    c = app.test_client()
    c.post("/admin/login", data={"csrf": _token(app), "password": "old-pass"})
    r = c.post("/admin/password",
               data={"csrf": _token(app), "old": "old-pass", "new": "fresh-passphrase"})
    assert r.status_code in (200, 302)
    assert _pw_store(repo).exists()
    assert app.test_client().post(
        "/admin/login", data={"csrf": _token(app), "password": "fresh-passphrase"}).status_code == 302
    assert app.test_client().post(
        "/admin/login", data={"csrf": _token(app), "password": "old-pass"}).status_code == 401


def test_change_password_wrong_old_is_refused_no_write(tmp_path):
    repo = tmp_path / "r"
    app = _auth_app(repo, password="old-pass")          # leak-scan: ignore
    c = app.test_client()
    c.post("/admin/login", data={"csrf": _token(app), "password": "old-pass"})
    r = c.post("/admin/password",
               data={"csrf": _token(app), "old": "WRONG", "new": "fresh-passphrase"})
    assert r.status_code == 400
    assert not _pw_store(repo).exists()


def test_change_password_requires_login(tmp_path):
    repo = tmp_path / "r"
    app = _auth_app(repo, password="old-pass")          # leak-scan: ignore
    r = app.test_client().post(
        "/admin/password", data={"csrf": _token(app), "old": "old-pass", "new": "fresh-passphrase"})
    assert r.status_code == 401
    assert not _pw_store(repo).exists()


def test_change_password_rejects_too_short_new(tmp_path):
    repo = tmp_path / "r"
    app = _auth_app(repo, password="old-pass")          # leak-scan: ignore
    c = app.test_client()
    c.post("/admin/login", data={"csrf": _token(app), "password": "old-pass"})
    r = c.post("/admin/password", data={"csrf": _token(app), "old": "old-pass", "new": "short"})
    assert r.status_code == 400
    assert not _pw_store(repo).exists()


# CB3 — the change-password form is on the /admin page when auth is enabled.
def test_admin_page_has_change_password_form_when_auth_on(tmp_path):
    app = _auth_app(tmp_path / "r", password="pw")
    c = app.test_client()
    c.post("/admin/login", data={"csrf": _token(app), "password": "pw"})
    assert "/admin/password" in c.get("/admin").get_data(as_text=True)
