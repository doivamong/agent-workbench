"""Tests for ui/web/ admin layer — the /admin action surface (full Approach A: login is the gate).

These mirror tests/test_ui_web.py's OPT-IN pattern exactly: a guarded import (never
``importorskip``) keeps every item COLLECTED so tools/readme_metrics.py sees a stable
count dev (Flask present) vs CI (Flask absent); the tests are skipped at run time when
Flask is missing, so the core suite still passes with zero third-party deps.

The four CRITICAL guards (called out below) are the ones that, if they regress, turn admin
into a remote-code-execution surface:

  C1  /admin is ALWAYS mounted, but NO password ⇒ admin is INERT — every action is 403 on any
      host (even with a valid CSRF token), login is impossible, GET /admin → the login page.
  C2  CSRF — POST mutations need the per-process token (hmac.compare_digest); GET never mutates.
  C3  --debug refused outright (admin always mounted); a LAN bind is allowed (inert without a
      password) — login, not the host, is the gate once a password is set.
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


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
# A password the migrated action tests configure so /admin is ENABLED — under full Approach A
# login is the gate, and no-password admin is inert (that contract is the C1 tests above). ≥8
# chars so it passes the change-password floor too.
_ADMIN_PW = "test-admin-pw"  # leak-scan: ignore


def _admin_app(ops_root: Path | None = None, *, host: str = "127.0.0.1", port: int = 5151,
               password: str = _ADMIN_PW):
    """An /admin app with a password CONFIGURED, so admin is enabled and login is required.
    The action tests drive it through _authed_client() (a logged-in client)."""
    app = webapp.create_app(host=host, port=port,
                            admin_password_hash=webadmin.hash_password(password))
    app.config.update(TESTING=True)
    if ops_root is not None:
        ops_root.mkdir(parents=True, exist_ok=True)
        app.config["OPS_ROOT"] = str(ops_root)
    return app


def _token(app) -> str:
    return app.config["ADMIN_TOKEN"]


def _authed_client(app, *, password: str = _ADMIN_PW):
    """A test client that has logged in, so it can reach the (now login-gated) admin actions."""
    c = app.test_client()
    r = c.post("/admin/login", data={"csrf": _token(app), "password": password})
    assert r.status_code in (200, 302), "login failed in _authed_client"
    return c


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
# C1 (full Approach A) — /admin is ALWAYS mounted; NO PASSWORD ⇒ admin is INERT.
#
# The load-bearing security contract this whole change exists to provide: login (not a flag,
# not the host) is the gate. With no password configured you cannot authenticate against an
# empty hash, so every admin mutation is refused on ANY host — even with a valid CSRF token.
# --------------------------------------------------------------------------- #
def _no_password_app(ops_root: Path | None = None, *, host: str = "127.0.0.1", port: int = 5151):
    """An /admin app with NO password configured — admin is mounted but inert."""
    app = webapp.create_app(host=host, port=port)  # no admin_password_hash → inert admin
    app.config.update(TESTING=True)
    if ops_root is not None:
        ops_root.mkdir(parents=True, exist_ok=True)
        app.config["OPS_ROOT"] = str(ops_root)
    return app


def test_C1_no_password_admin_action_is_403_on_any_host_even_with_valid_csrf(tmp_path):
    """THE load-bearing test. No password + a VALID CSRF token + a POST action → 403 on BOTH
    localhost and a LAN Host. The 403 is the INERT gate (no login possible), not the CSRF
    check — which is why the token is valid and it still fails. No snapshot is written."""
    repo = tmp_path / "r"
    app = _no_password_app(repo, host="0.0.0.0")
    token = _token(app)  # the token IS minted (admin is always mounted) — yet useless here
    for host in ("127.0.0.1:5151", "192.168.1.50:5151"):
        r = app.test_client().post("/admin/action/snapshot",
                                   data={"csrf": token}, headers={"Host": host})
        assert r.status_code == 403, host
    snaps = repo / ".ops" / "snapshots"
    assert not (snaps.exists() and list(snaps.glob("*.zip")))  # no mutation reached the engine


def test_C1_no_password_get_admin_redirects_to_login(tmp_path):
    app = _no_password_app(tmp_path / "r")
    r = app.test_client().get("/admin")
    assert r.status_code == 302
    assert "/admin/login" in r.headers["Location"]


def test_C1_no_password_login_is_impossible(tmp_path):
    """POST /admin/login with any password cannot create a session (nothing to verify against)."""
    app = _no_password_app(tmp_path / "r")
    c = app.test_client()
    r = c.post("/admin/login", data={"csrf": _token(app), "password": "anything-at-all"})
    assert r.status_code in (401, 403)               # refused — no session minted
    assert c.get("/admin").status_code == 302        # ...still bounced to login
    with c.session_transaction() as sess:
        assert sess.get("authed") is not True


def test_C1_no_password_login_page_shows_bootstrap_notice_not_a_setup_form(tmp_path):
    """GET /admin/login renders (the only thing that does when inert) and names the bootstrap
    path — set AWB_ADMIN_PASSWORD and restart — NOT an in-page password-setting form."""
    app = _no_password_app(tmp_path / "r")
    html = app.test_client().get("/admin/login").get_data(as_text=True)
    assert "AWB_ADMIN_PASSWORD" in html              # the bootstrap env var is named
    assert 'name="password"' not in html             # no setup/login field while inert


def test_C1_admin_always_mounted_token_minted(tmp_path):
    # /admin is mounted with no flag and no password; a per-process CSRF token is always minted.
    a = _no_password_app(tmp_path / "a")
    b = _no_password_app(tmp_path / "b")
    assert _token(a) and len(_token(a)) >= 32
    assert _token(a) != _token(b)  # per-process secret, not a shared constant


# --------------------------------------------------------------------------- #
# C2 — CSRF
# --------------------------------------------------------------------------- #
# CSRF is checked in PASSWORD mode (login is the gate, then CSRF on each mutation). A
# logged-in client without a valid token is still refused — a session is NOT a CSRF substitute.
def test_C2_post_without_token_is_403(tmp_path):
    app = _admin_app(tmp_path / "r")
    r = _authed_client(app).post("/admin/action/snapshot")
    assert r.status_code == 403


def test_C2_post_with_wrong_token_is_403(tmp_path):
    app = _admin_app(tmp_path / "r")
    r = _authed_client(app).post("/admin/action/snapshot", data={"csrf": "not-the-token"})
    assert r.status_code == 403


def test_C2_post_with_correct_token_succeeds(tmp_path):
    app = _admin_app(tmp_path / "r")
    r = _authed_client(app).post("/admin/action/snapshot", data={"csrf": _token(app)})
    assert r.status_code == 200


def test_C2_token_also_accepted_via_header(tmp_path):
    app = _admin_app(tmp_path / "r")
    r = _authed_client(app).post("/admin/action/snapshot",
                                 headers={"X-CSRF-Token": _token(app)})
    assert r.status_code == 200


def test_C2_get_on_action_route_never_mutates(tmp_path):
    repo = tmp_path / "r"
    app = _admin_app(repo)
    snaps = _snap_dir(repo)
    before = sorted(snaps.glob("*.zip")) if snaps.exists() else []
    r = _authed_client(app).get("/admin/action/snapshot")
    assert r.status_code in (404, 405)  # POST-only — GET is not even routed to the action
    after = sorted(snaps.glob("*.zip")) if snaps.exists() else []
    assert before == after  # no snapshot written by a GET


# --------------------------------------------------------------------------- #
# C3 — --debug refused outright; a LAN bind is allowed (admin is inert without a password)
#
# Under full Approach A login is the gate, not the host: SameSite=Strict + the session cookie
# + CSRF cover what the old host-allowlist did, and a wildcard bind serves LAN hosts we can't
# enumerate. So a foreign Host with a logged-in session is served (covered by the B-series LAN
# test). What MUST stay refused is --debug (the Werkzeug debugger is an RCE console), which now
# applies unconditionally since admin is always mounted.
# --------------------------------------------------------------------------- #
def test_C3_debug_refused_outright(tmp_path):
    with pytest.raises(ValueError):
        webapp.create_app(debug=True)            # admin is always mounted → debugger refused
    # A LAN bind is NO LONGER refused — admin is inert without a password; login is the gate.
    app = webapp.create_app(host="0.0.0.0")
    assert "ADMIN_TOKEN" in app.config           # built without raising


def test_C3_cli_refuses_debug(tmp_path):
    with pytest.raises(SystemExit):
        webapp.main(["--debug"])


def test_C3b_public_bind_refused_but_lan_allowed():
    """opt-2: create_app refuses a public/Internet-routable bind (cleartext HTTP must not face
    the Internet), while loopback / private-LAN / 0.0.0.0 stay allowed (the sanctioned modes)."""
    with pytest.raises(ValueError):
        webapp.create_app(host="8.8.8.8")        # a public address → refused
    for ok in ("127.0.0.1", "0.0.0.0", "192.168.1.50", "10.0.0.5"):
        assert "ADMIN_TOKEN" in webapp.create_app(host=ok).config  # built without raising


def test_C3b_cli_refuses_public_bind():
    with pytest.raises(SystemExit):
        webapp.main(["--host", "8.8.8.8"])        # a public IP → clean SystemExit, no traceback


# --------------------------------------------------------------------------- #
# Audit-log writability — boot-time fail-closed (the chosen T3 model A).
#
# _audit() appends a JSON line to .ops/ops.log for every action AND every blocked request,
# with NO try/except on purpose (an audit log must fail loud, never silently). But a write
# that raises *inside a request* would (C1) turn a clean 401/403 refusal into a 500, and (C2)
# could drop a destructive action's audit line AFTER the action already ran. The fix verifies
# .ops/ writability ONCE, at create_app, and refuses to start if it can't write — so:
#   * C1 (auth not masked): unreachable at runtime — the server never serves a request against
#     an unwritable .ops/, so no 401/403 can ever degrade to a 500.
#   * C2 (destructive audit never silently lost): the destructive path never runs against an
#     unwritable log, and the boot failure is loud (a raised RuntimeError), never swallowed.
# --------------------------------------------------------------------------- #
def test_unwritable_ops_dir_refused_at_startup(tmp_path):
    """An unwritable .ops/ must fail create_app LOUD, not boot a server that 500s an auth
    refusal or silently drops a destructive-action audit line. Trigger portably (incl. Windows)
    by placing a *file* where .ops/ must be a dir, so the mkdir + probe-write fails."""
    (tmp_path / ".ops").write_text("not a directory", encoding="utf-8")  # blocks .ops/ mkdir
    with pytest.raises(RuntimeError) as exc:
        webapp.create_app(ops_root=str(tmp_path))
    msg = str(exc.value).lower()
    assert "audit" in msg and "writable" in msg          # an actionable, audit-specific message
    assert str(tmp_path) in str(exc.value)               # names the offending root


def test_writable_ops_dir_builds(tmp_path):
    """The boot-time assert is not over-eager: a writable ops_root builds normally and the
    config reflects the injected root (the new param is purely additive)."""
    app = webapp.create_app(ops_root=str(tmp_path))
    assert "ADMIN_TOKEN" in app.config                   # built without raising
    assert app.config["OPS_ROOT"] == str(tmp_path)
    assert (tmp_path / ".ops").is_dir()                  # the probe created/validated .ops/


def test_admin_page_reachability_badge_reflects_real_bind(tmp_path):
    """opt-2 UI honesty: the /admin page shows a badge driven by the REAL bind host — 'reachable
    on LAN' for a 0.0.0.0 bind, 'this machine only' for loopback.

    Uses an isolated ops_root: without it, _effective_password_hash() reads the REAL repo
    .ops/admin.hash (a web-set password persists there, gitignored) and that overrides the test's
    configured password — so login fails on any machine that has one, while a fresh CI checkout
    (no .ops/admin.hash) stays green. The other admin tests isolate the same way."""
    lan = _admin_app(tmp_path / "lan", host="0.0.0.0")
    lan_html = _authed_client(lan).get("/admin?lang=en").get_data(as_text=True)
    assert "reachable on LAN" in lan_html
    loc = _admin_app(tmp_path / "loc", host="127.0.0.1")
    local_html = _authed_client(loc).get("/admin?lang=en").get_data(as_text=True)
    assert "this machine only" in local_html


# --------------------------------------------------------------------------- #
# C4 — Restore TOCTOU + server-enumerated targets
# --------------------------------------------------------------------------- #
def test_C4_restore_preview_returns_plan_hash(tmp_path):
    repo = _git_repo(tmp_path)
    z = _take_snapshot(repo)
    app = _admin_app(repo)
    r = _authed_client(app).post("/admin/restore/preview",
                                 data={"csrf": _token(app), "snapshot": z.name})
    assert r.status_code == 200
    assert _plan_hash_from(r.get_data(as_text=True)) is not None


def test_C4_restore_apply_with_stale_hash_aborts_no_write(tmp_path):
    repo = _git_repo(tmp_path)
    z = _take_snapshot(repo)
    app = _admin_app(repo)
    c = _authed_client(app)
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
    c = _authed_client(app)
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
    c = _authed_client(app)
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
    r = _authed_client(app).post("/admin/action/snapshot", data={"csrf": _token(app)})
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
    r = _authed_client(app).post("/admin/action/pack", data={"csrf": _token(app)})
    assert r.status_code == 500
    assert "boom: engine failed" in r.get_data(as_text=True)


def test_restart_is_a_detached_spawn(tmp_path, monkeypatch):
    seen = {}

    def fake_launch(host, port):
        seen["host"], seen["port"] = host, port
        return 4242  # pretend pid; do NOT actually spawn

    monkeypatch.setattr(webadmin, "_launch_restart", fake_launch)
    app = _admin_app(tmp_path / "r", host="127.0.0.1", port=5151)
    r = _authed_client(app).post("/admin/action/restart", data={"csrf": _token(app)})
    assert r.status_code in (200, 202)
    assert seen == {"host": "127.0.0.1", "port": 5151}


def test_every_action_is_audited(tmp_path):
    repo = tmp_path / "r"
    app = _admin_app(repo)
    _authed_client(app).post("/admin/action/snapshot", data={"csrf": _token(app)})
    log = repo / ".ops" / "ops.log"
    assert log.exists()
    rec = json.loads(log.read_text(encoding="utf-8").strip().splitlines()[-1])
    assert rec["action"] == "snapshot" and "time" in rec and "result" in rec


def test_restore_refuses_dirty_tree_without_allow_dirty(tmp_path):
    repo = _git_repo(tmp_path)
    z = _take_snapshot(repo)
    app = _admin_app(repo)
    c = _authed_client(app)
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
    c = _authed_client(app)
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
    r = _authed_client(app).post("/admin/action/verify",
                                 data={"csrf": _token(app), "release": "../escape.zip"})
    assert r.status_code == 400


def test_admin_page_renders_and_is_offline(tmp_path):
    app = _admin_app(tmp_path / "r")
    html = _authed_client(app).get("/admin").get_data(as_text=True)
    assert "<form" in html
    assert 'class="btn' in html                      # buttons reuse the >=44px .btn
    assert _token(app) in html                        # CSRF token embedded for the forms
    assert not re.search(r'(?:src|href)="https?://', html)  # offline — no external refs
    assert "cdn" not in html.lower()


def test_readonly_root_always_shows_login_link_with_password(tmp_path):
    # Friction removed: the read-only / ALWAYS offers a way into admin (the login link),
    # whether or not a password is configured. Here a password IS set.
    proj = _make_project(tmp_path)
    app = _admin_app(tmp_path / "r")
    app.config["PROJECT"] = proj
    r = app.test_client().get("/")
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert 'href="/admin/login"' in html
    assert "Đăng nhập admin" in html


def test_readonly_root_shows_login_link_even_without_password(tmp_path):
    # The link is present even with NO password (admin inert) — clicking it lands on the
    # bootstrap notice, so there is always a discoverable path to enabling admin.
    proj = _make_project(tmp_path)
    app = webapp.create_app()
    app.config.update(TESTING=True, PROJECT=proj)
    html = app.test_client().get("/").get_data(as_text=True)
    assert 'href="/admin/login"' in html
    assert "Đăng nhập admin" in html


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
    html = _authed_client(app).get("/admin").get_data(as_text=True)
    assert "admin.js" in html


def test_restart_result_carries_reconnect_marker(tmp_path, monkeypatch):
    monkeypatch.setattr(webadmin, "_launch_restart", lambda host, port: 4242)
    app = _admin_app(tmp_path / "r", host="127.0.0.1", port=5151)
    r = _authed_client(app).post("/admin/action/restart", data={"csrf": _token(app)})
    assert r.status_code in (200, 202)
    assert 'data-restart="1"' in r.get_data(as_text=True)  # admin.js keys off this to poll/reload


def test_destructive_restore_has_confirm_dialog(tmp_path):
    repo = _git_repo(tmp_path)
    z = _take_snapshot(repo)
    app = _admin_app(repo)
    preview = _authed_client(app).post(
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
    app = webapp.create_app(host=host, port=port,
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


# B6 — a LAN (wildcard) bind always builds (full Approach A): with no password admin is inert,
# with a password login is the gate. Once auth is on, a request arriving with a LAN Host passes
# the (now relaxed) host gate — login, not the host, is the real gate.
def test_lan_bind_builds_with_and_without_password(tmp_path):
    inert = webapp.create_app(host="0.0.0.0")                    # no password → inert, not refused
    assert "ADMIN_TOKEN" in inert.config
    enabled = webapp.create_app(host="0.0.0.0",
                                admin_password_hash=webadmin.hash_password("lan-bind-pw"))
    assert "ADMIN_TOKEN" in enabled.config                       # both build without raising


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


# B7 — full Approach A replaces the old no-password back-compat: with NO password admin is
# inert on EVERY host (there is no localhost convenience mode any more). A GET bounces to the
# login page; an action POST is refused even with a valid CSRF token. (The localhost and LAN
# cases of the load-bearing contract are the C1 tests above; this pins the no-action guarantee.)
def test_no_password_admin_is_inert_no_localhost_convenience(tmp_path):
    app = _no_password_app(tmp_path / "r")           # localhost bind, no password
    c = app.test_client()
    assert c.get("/admin").status_code == 302         # bounced to login (not a 200 page)
    assert c.post("/admin/action/snapshot",
                  data={"csrf": _token(app)}).status_code == 403   # action refused (inert)


# Wiring — main()/env resolves the admin password; a LAN bind needs it.
def test_resolve_admin_password_hash_from_env(monkeypatch):
    monkeypatch.delenv("AWB_ADMIN_PASSWORD", raising=False)
    monkeypatch.delenv("AWB_ADMIN_PASSWORD_HASH", raising=False)
    assert webapp._resolve_admin_password_hash() == ""                 # neither set → no auth
    monkeypatch.setenv("AWB_ADMIN_PASSWORD", "from-plain")
    assert webadmin.verify_password("from-plain", webapp._resolve_admin_password_hash())
    monkeypatch.setenv("AWB_ADMIN_PASSWORD_HASH", "pre-computed-wins")
    assert webapp._resolve_admin_password_hash() == "pre-computed-wins"  # explicit hash wins


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
    html = _authed_client(_admin_app(tmp_path / "r")).get("/admin").get_data(as_text=True)
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
    r = _authed_client(app).post("/admin/action/lan-enable", data={"csrf": _token(app)})
    assert r.status_code == 200
    script, cli_args = calls[-1]
    assert script.name == "lan_setup.py"
    assert "enable" in cli_args and "--json" in cli_args


def test_lan_disable_runs_lan_setup_disable(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(webadmin, "_run_engine",
                        lambda s, a: (calls.append((s, a)) or (0, {"action": "disable"}, "")))
    app = _admin_app(tmp_path / "r")
    r = _authed_client(app).post("/admin/action/lan-disable", data={"csrf": _token(app)})
    assert r.status_code == 200
    assert calls[0][0].name == "lan_setup.py" and "disable" in calls[0][1]


def test_lan_action_requires_csrf(tmp_path):
    app = _admin_app(tmp_path / "r")
    # Logged in but no CSRF token → still 403 (a session is not a CSRF substitute).
    assert _authed_client(app).post("/admin/action/lan-enable").status_code == 403


# BB3 — firewall + autostart actions run the engines; an elevation failure is surfaced
# honestly (the page tells you to run the self-elevating .bat), not silently swallowed.
def test_firewall_open_runs_engine(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(webadmin, "_run_engine",
                        lambda s, a: (calls.append((s, a)) or (0, {"result": "opened"}, "")))
    app = _admin_app(tmp_path / "r")
    r = _authed_client(app).post("/admin/action/firewall-open", data={"csrf": _token(app)})
    assert r.status_code == 200
    assert calls[0][0].name == "lan_setup.py" and "firewall" in calls[0][1]


def test_firewall_needs_admin_is_surfaced_not_swallowed(tmp_path, monkeypatch):
    monkeypatch.setattr(webadmin, "_run_engine",
                        lambda s, a: (0, {"result": "failed", "detail": "needs administrator",
                                          "command": "powershell New-NetFirewallRule"}, ""))
    app = _admin_app(tmp_path / "r")
    body = _authed_client(app).post("/admin/action/firewall-open",
                                    data={"csrf": _token(app)}).get_data(as_text=True)
    assert "lan_on.bat" in body or "admin" in body.lower()      # tells the user how to elevate


def test_autostart_enable_runs_engine(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(webadmin, "_run_engine",
                        lambda s, a: (calls.append((s, a)) or (0, {"result": "enabled"}, "")))
    app = _admin_app(tmp_path / "r")
    r = _authed_client(app).post("/admin/action/autostart-enable", data={"csrf": _token(app)})
    assert r.status_code == 200
    assert calls[0][0].name == "autostart.py" and "enable" in calls[0][1]


def test_autostart_disable_runs_engine(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(webadmin, "_run_engine",
                        lambda s, a: (calls.append((s, a)) or (0, {"result": "removed"}, "")))
    app = _admin_app(tmp_path / "r")
    r = _authed_client(app).post("/admin/action/autostart-disable", data={"csrf": _token(app)})
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


# --------------------------------------------------------------------------- #
# Bilingual EN/VI — /admin is localized too (VI default, EN via ?lang= + cookie).
# Server-rendered result messages come from admin.py via i18n.admin_msg(lang).
# --------------------------------------------------------------------------- #
def test_login_page_localized_vi_default_en_on_query(tmp_path):
    app = _no_password_app(tmp_path / "r")
    vi = app.test_client().get("/admin/login").get_data(as_text=True)
    assert '<html lang="vi">' in vi and "Chưa bật admin" in vi
    en = app.test_client().get("/admin/login?lang=en").get_data(as_text=True)
    assert '<html lang="en">' in en and "Admin not enabled" in en
    assert "AWB_ADMIN_PASSWORD" in en                  # bootstrap notice, not a setup form
    assert 'name="password"' not in en                 # still NO password field (C1 contract)


def test_admin_page_renders_english(tmp_path):
    app = _admin_app(tmp_path / "r")
    html = _authed_client(app).get("/admin?lang=en").get_data(as_text=True)
    assert '<html lang="en">' in html
    assert "Kit control" in html and "Restart" in html and "Change admin password" in html
    assert "Điều khiển kit" not in html                # no VI leak


def test_admin_result_message_localized_english(tmp_path):
    # A server-rendered result message follows ?lang. Wrong old password → EN "Denied".
    app = _admin_app(tmp_path / "r")
    c = _authed_client(app)
    r = c.post("/admin/password?lang=en",
               data={"csrf": _token(app), "old": "wrong-old-pw", "new": "another-strong-pw"})
    assert r.status_code == 400
    body = r.get_data(as_text=True)
    assert "Denied" in body and "old password is incorrect" in body
    assert "Mật khẩu" not in body                      # no VI leak in the message
