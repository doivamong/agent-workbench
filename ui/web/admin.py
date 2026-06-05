#!/usr/bin/env python3
"""ui/web/admin.py — the /admin action surface (Flask blueprint).

**Always mounted** by ``app.create_app`` (full Approach A), but **login is the gate**: with
**no password configured the surface is inert** — every action is 403 on any host, ``GET
/admin`` redirects to a login page that cannot create a session. Setting a password (the env
``AWB_ADMIN_PASSWORD``/``_HASH`` at startup, or a web change-password later) is what *enables*
it; login then unlocks it. This supersedes the old ``--admin`` flag gate (a flag authenticates
nobody, a login does). It turns the Phase-1 ops engine (``ops/dashboard_ctl.py``,
``ops/tree_snapshot.py``, ``ops/release_pack.py``) into web buttons — restart, snapshot, pack,
verify, and a guarded tree-restore — **reusing those callable APIs**, never re-implementing them.

The guards (the design was stress-tested to GO only with all of these):
  * **Inert without a password** — no password ⇒ no login is possible ⇒ every action is 403 on
    any host. Login (not a flag, not the host) is the gate.
  * **Login required** — with a password set, every path except the login endpoint needs a
    logged-in session (pbkdf2 hash, constant-time verify, lockout, idle timeout); a valid CSRF
    token is NOT a substitute for login.
  * **CSRF** — every mutation is POST-only and must carry the per-process token
    (``secrets.token_urlsafe`` minted in create_app), checked with ``hmac.compare_digest``
    before any side effect. GETs never mutate.
  * **Server-enumerated targets** — the restore/verify target is chosen by name from a list
    THIS server produced (snapshots / releases dirs); a client-supplied path is rejected.
    Subprocess calls are arg lists, never a shell string.
  * **Guarded restore** — dry-run preview produces a plan-hash; the apply re-validates that
    hash (TOCTOU: aborts if the tree moved), takes an auto-backup first, and refuses a dirty
    tree unless ``allow_dirty``.
  * **Audited** — every action (and every blocked request) appends a JSON line to
    ``.ops/ops.log``; subprocess errors are surfaced, not swallowed.

HONEST LIMIT (documented on purpose): this is **plain HTTP** — once a password is set, the
password and the session cookie travel in **cleartext** over the LAN and can be sniffed by
anyone on the network path. The password stops a casual bystander, **not** a network attacker.
Only enable it on a **trusted** network, never Internet-facing (TLS is out of scope for Phase A).

DESIGN — engine actions run via SUBPROCESS (handover decision D4). Every engine *action*
(snapshot · pack · verify · restore preview & apply) runs as ``subprocess python
ops/<tool>.py … --json`` through ``_run_engine`` — an **arg list, never a shell string** —
so the destructive logic is isolated from the Flask process, reuses the exact CLI
dry-run/confirm semantics, and surfaces the subprocess exit code + stderr (guard #9). The
Phase-1 CLIs gained ``--root`` / ``--snap-dir`` / ``--rel-dir`` so the subprocess can target
the configured ``OPS_ROOT`` (which also makes the 4 Critical guards testable on a temp tree).
Only *read-only* status — enumerating snapshots/releases for the dropdowns and the dirty-tree
check — imports the API directly, as D4 permits. The self-restart is its own *detached*
subprocess (it must outlive the dying process).
"""
from __future__ import annotations

import hmac
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from flask import (Blueprint, abort, current_app, redirect, render_template,
                   request, session)

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
import passwords                     # noqa: E402  — shared stdlib hashing (no Flask), see passwords.py
import ops.autostart as autos      # noqa: E402  — read-only status; enable/disable may need admin
import ops.dashboard_ctl as dctl   # noqa: E402  — reused engine (process control)
import ops.lan_setup as lans       # noqa: E402  — read-only status; enable/disable (setx, no admin)
import ops.release_pack as rpack   # noqa: E402  — read-only enumeration (list_releases)
import ops.tree_snapshot as tsnap  # noqa: E402  — read-only enumeration (list_snapshots) + is_git_repo

# Engine CLIs driven as subprocesses for every ACTION (D4). Read-only enumeration uses the
# imported APIs above; writes go through these scripts.
_TS = REPO_ROOT / "ops" / "tree_snapshot.py"
_RP = REPO_ROOT / "ops" / "release_pack.py"
_LAN = REPO_ROOT / "ops" / "lan_setup.py"
_AS = REPO_ROOT / "ops" / "autostart.py"


def _system_status() -> dict:
    """Read-only system view for the /admin panel: the LAN bind default + the autostart task
    state, sourced from the lan_setup / autostart status APIs (imported directly, like the
    snapshot/release enumeration — no mutation). Each is defensive: a status call that raises
    (e.g. schtasks missing on POSIX) degrades to an error marker rather than 500-ing the page."""
    try:
        lan = lans.status(current_app.config.get("PORT", 5151))
    except Exception as exc:  # noqa: BLE001 — a status probe must never break the page
        lan = {"error": str(exc)}
    try:
        autostart = autos.status()
    except Exception as exc:  # noqa: BLE001
        autostart = {"error": str(exc)}
    return {"lan": lan, "autostart": autostart}

admin_bp = Blueprint("admin", __name__, template_folder="templates")


# --------------------------------------------------------------------------- #
# Config-derived paths (overridable in tests via app.config["OPS_ROOT"])
# --------------------------------------------------------------------------- #
def _ops_root() -> Path:
    return Path(current_app.config.get("OPS_ROOT", REPO_ROOT))


def _snap_dir() -> Path:
    return _ops_root() / ".ops" / "snapshots"


def _rel_dir() -> Path:
    return _ops_root() / ".ops" / "releases"


def _audit_path() -> Path:
    return _ops_root() / ".ops" / "ops.log"


# --------------------------------------------------------------------------- #
# Audit — every action and every blocked request lands here
# --------------------------------------------------------------------------- #
def _audit(action: str, result: str, **fields) -> None:
    rec = {"time": datetime.now().isoformat(timespec="seconds"),
           "action": action, "result": result,
           "remote": request.remote_addr, **fields}
    path = _audit_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")


# --------------------------------------------------------------------------- #
# Password hashing (Phase A auth) — re-exported from the shared stdlib module so the
# offline set_password.py CLI and this web route hash identically. See passwords.py for
# the format / constant-time-verify rationale.
# --------------------------------------------------------------------------- #
hash_password = passwords.hash_password
verify_password = passwords.verify_password


# --------------------------------------------------------------------------- #
# Guards (before_request) — login gate (full Approach A) + CSRF
# --------------------------------------------------------------------------- #
def _pw_store_path() -> Path:
    """Where a web-changed password hash persists. Under .ops/ (gitignored, never committed)."""
    return _ops_root() / ".ops" / "admin.hash"


def _read_pw_store() -> str:
    """The persisted password hash, or '' if none. A web change-password writes here; this read
    is at REQUEST time so a change takes effect immediately, no restart needed."""
    p = _pw_store_path()
    try:
        return p.read_text(encoding="utf-8").strip() if p.is_file() else ""
    except OSError:
        return ""


def _effective_password_hash() -> str:
    """The hash login checks against: the persisted (web-set) hash wins; otherwise the
    bootstrap hash from the env (config['ADMIN_PASSWORD_HASH'])."""
    return _read_pw_store() or current_app.config.get("ADMIN_PASSWORD_HASH", "")


def _auth_enabled() -> bool:
    return bool(_effective_password_hash())


# An authenticated session is only valid for _IDLE_SECONDS after login; past that it must
# re-authenticate (overridable per-app via config["ADMIN_IDLE_SECONDS"], e.g. in tests).
_IDLE_SECONDS = 3600


def _is_authed() -> bool:
    if session.get("authed") is not True:
        return False
    login_at = session.get("login_at")
    try:
        elapsed = (datetime.now() - datetime.fromisoformat(login_at)).total_seconds()
    except (ValueError, TypeError):
        return False
    return elapsed < current_app.config.get("ADMIN_IDLE_SECONDS", _IDLE_SECONDS)


# Brute-force lockout: per-source-IP failure counter held in app.config (per-process, so a
# restart clears it; per-app, so tests stay isolated). After _MAX_LOGIN_FAILS failures a
# source is refused for _LOCKOUT_SECONDS — even with the correct password.
_MAX_LOGIN_FAILS = 5
_LOCKOUT_SECONDS = 300


def _login_failures() -> dict:
    return current_app.config.setdefault("LOGIN_FAILURES", {})


def _is_locked(ip: str) -> bool:
    rec = _login_failures().get(ip)
    if not rec or rec[0] < _MAX_LOGIN_FAILS:
        return False
    if (datetime.now() - rec[1]).total_seconds() >= _LOCKOUT_SECONDS:
        _login_failures().pop(ip, None)  # window elapsed → reset
        return False
    return True


def _record_login_failure(ip: str) -> None:
    count, first = _login_failures().get(ip, (0, datetime.now()))
    _login_failures()[ip] = (count + 1, first)


@admin_bp.before_request
def _enforce_guards():
    effective = _effective_password_hash()
    # NO PASSWORD ⇒ admin is INERT (full Approach A). There is no login (you cannot
    # authenticate against an empty hash) and no action runs — on ANY host. The ONLY thing
    # that renders is the login page itself (GET), which shows the "set AWB_ADMIN_PASSWORD and
    # restart" bootstrap notice. This is the load-bearing guarantee: login is the gate, and
    # with no password there is no gate to pass, so every mutation is refused (even with a
    # valid CSRF token — the 403 below fires before the CSRF check is ever reached).
    if not effective:
        if request.endpoint == "admin.login" and request.method in ("GET", "HEAD"):
            return  # let the login page render the bootstrap notice
        _audit("guard", "blocked-no-password", path=request.path)
        if request.method in ("GET", "HEAD"):
            return redirect("/admin/login")
        abort(403)
    # PASSWORD SET ⇒ login is the gate. Every admin path except the login endpoint needs a
    # logged-in session; a valid CSRF token is NOT a substitute for login. The host is NOT
    # checked — a wildcard bind serves arbitrary LAN hosts we can't enumerate, and
    # SameSite=Strict + the session cookie + CSRF cover what the old host-allowlist used to (a
    # cross-site/DNS-rebind request carries no session cookie, so it 401s here).
    if request.endpoint != "admin.login" and not _is_authed():
        _audit("guard", "blocked-unauthenticated", path=request.path)
        if request.method in ("GET", "HEAD"):
            return redirect("/admin/login")
        abort(401)
    # Cross-origin CSRF defence on every mutation: the per-process token, constant-time compared.
    if request.method not in ("GET", "HEAD", "OPTIONS"):
        token = request.form.get("csrf") or request.headers.get("X-CSRF-Token") or ""
        want = current_app.config.get("ADMIN_TOKEN") or ""
        if not want or not hmac.compare_digest(str(token), str(want)):
            _audit("guard", "blocked-csrf", path=request.path)
            abort(403)


# --------------------------------------------------------------------------- #
# Target resolution — never trust a client path
# --------------------------------------------------------------------------- #
def _resolve_in_dir(name: str, directory: Path) -> Path | None:
    """Map a client-supplied basename to a real file in ``directory`` — but only one this
    server would have enumerated. Rejects path separators, ``..``, and anything that doesn't
    resolve to a file sitting directly inside ``directory``. Returns None on any rejection."""
    if not name or "/" in name or "\\" in name or name in (".", ".."):
        return None
    candidate = directory / name
    if not candidate.is_file():
        return None
    try:
        if candidate.resolve().parent != directory.resolve():
            return None
    except OSError:
        return None
    return candidate


def _tree_dirty(root: Path) -> bool:
    """True if the git working tree has uncommitted changes. Outside a git repo we can't
    tell, so we don't block (return False). GIT_* is stripped so a leaked worktree GIT_DIR
    can't redirect the check at the wrong repo."""
    if not tsnap.is_git_repo(root):
        return False
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    r = subprocess.run(["git", "status", "--porcelain"], cwd=str(root),
                       env=env, capture_output=True, text=True)
    return bool(r.stdout.strip())


# --------------------------------------------------------------------------- #
# Self-restart — a DETACHED spawn (seam; monkeypatched in tests)
# --------------------------------------------------------------------------- #
def record_own_pid() -> None:
    """Record THIS process's PID in ops/dashboard_ctl's pidfile, so ``dashboard_ctl
    restart/stop`` — and the detached restarter spawned below — can find and replace us
    even when the dashboard was launched directly (``python ui/web/app.py``)."""
    dctl.write_pid(os.getpid())


def _launch_restart(host: str, port: int) -> int:
    """Spawn a DETACHED ``dashboard_ctl restart`` and return its PID. Detached so it
    outlives this process's imminent death (it stops us via the pidfile, then starts fresh).
    Arg list, never a shell string. Tests monkeypatch this — it never really restarts there."""
    (_ops_root() / ".ops").mkdir(parents=True, exist_ok=True)
    cmd = [sys.executable, str(Path(dctl.__file__)), "restart",
           "--host", host, "--port", str(port)]
    logf = open(_ops_root() / ".ops" / "restart.log", "ab")  # noqa: SIM115 — handed to child
    kwargs: dict = {"stdout": logf, "stderr": logf, "stdin": subprocess.DEVNULL,
                    "cwd": str(REPO_ROOT)}
    if sys.platform == "win32":
        kwargs["creationflags"] = 0x00000008 | 0x00000200  # DETACHED_PROCESS | NEW_GROUP
    else:
        kwargs["start_new_session"] = True
    return subprocess.Popen(cmd, **kwargs).pid


# --------------------------------------------------------------------------- #
# Engine actions — run as subprocesses (D4): arg list, never a shell string
# --------------------------------------------------------------------------- #
def _run_engine(script: Path, cli_args: list[str]) -> tuple[int, dict | None, str]:
    """Run an ops CLI as a subprocess and return ``(returncode, parsed_json|None, stderr_tail)``.

    Arg list (never a shell string), ``cwd=REPO_ROOT`` so the CLI's ``import install`` resolves,
    GIT_* stripped so a leaked worktree GIT_DIR can't redirect the engine's own git calls. The
    last stdout line is parsed as the JSON result; the exit code + stderr are surfaced, never
    swallowed (guard #9)."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    proc = subprocess.run([sys.executable, str(script), *cli_args],
                          cwd=str(REPO_ROOT), env=env, capture_output=True, text=True)
    data: dict | None = None
    out = (proc.stdout or "").strip()
    if out:
        try:
            data = json.loads(out.splitlines()[-1])
        except (ValueError, IndexError):
            data = None
    return proc.returncode, data, (proc.stderr or "").strip()[-500:]


def _root_args() -> list[str]:
    return ["--root", str(_ops_root()), "--snap-dir", str(_snap_dir())]


# --------------------------------------------------------------------------- #
# Rendering helpers
# --------------------------------------------------------------------------- #
def _result(action: str, title: str, message: str, *, ok: bool = True,
            detail: list[str] | None = None, poll_health: bool = False):
    # poll_health stamps a data-restart marker so admin.js knows to poll /health and reload
    # once the freshly-spawned dashboard answers again.
    return render_template("_admin_result.html.jinja",
                           action=action, title=title, message=message, ok=ok,
                           detail=detail, poll_health=poll_health)


def _token() -> str:
    return current_app.config.get("ADMIN_TOKEN", "")


# --------------------------------------------------------------------------- #
# Routes
# --------------------------------------------------------------------------- #
@admin_bp.route("/login", methods=["GET", "POST"])
def login():
    """Password login (Phase A). GET renders the form (reachable unauthenticated, carries the
    CSRF token); POST verifies the password against the configured pbkdf2 hash with a
    constant-time compare. Success mints an authenticated session; failure is audited.

    With NO password configured this route is only reachable as a GET (the inert guard 403s a
    POST before it gets here); the page then shows the bootstrap notice instead of a form."""
    no_password = not _effective_password_hash()
    if request.method == "POST":
        ip = request.remote_addr or "?"
        if _is_locked(ip):
            _audit("login", "locked-out")
            return render_template("admin_login.html.jinja", token=_token(), no_password=no_password,
                                   error="Tạm khoá do nhập sai quá nhiều lần. Thử lại sau."), 429
        stored = _effective_password_hash()
        if stored and verify_password(request.form.get("password", ""), stored):
            _login_failures().pop(ip, None)  # clear the counter on success
            session.clear()
            session["authed"] = True
            session["login_at"] = datetime.now().isoformat(timespec="seconds")
            _audit("login", "ok")
            return redirect("/admin")
        _record_login_failure(ip)
        _audit("login", "failed")
        return render_template("admin_login.html.jinja", token=_token(), no_password=no_password,
                               error="Sai mật khẩu."), 401
    return render_template("admin_login.html.jinja", token=_token(), no_password=no_password,
                           error=None)


@admin_bp.route("/logout", methods=["POST"])
def logout():
    session.clear()
    _audit("logout", "ok")
    return redirect("/admin/login")


_MIN_PASSWORD_LEN = passwords.MIN_PASSWORD_LEN


@admin_bp.route("/password", methods=["POST"])
def change_password():
    """Change the admin password from the web. Requires an authenticated session (enforced by
    before_request), a correct OLD password (constant-time), and a NEW password of at least
    _MIN_PASSWORD_LEN chars. On success the new pbkdf2 hash is persisted to .ops/admin.hash,
    which then takes precedence over the env password — no restart needed. The plaintext is
    never stored; on HTTP/LAN it still travels in cleartext (documented honest limit)."""
    old = request.form.get("old", "")
    new = request.form.get("new", "")
    if not verify_password(old, _effective_password_hash()):
        _audit("password-change", "wrong-old")
        return _result("password", "Bị từ chối", "Mật khẩu cũ không đúng.", ok=False), 400
    if len(new) < _MIN_PASSWORD_LEN:
        _audit("password-change", "too-short")
        return _result("password", "Bị từ chối",
                       f"Mật khẩu mới phải tối thiểu {_MIN_PASSWORD_LEN} ký tự.", ok=False), 400
    store = _pw_store_path()
    store.parent.mkdir(parents=True, exist_ok=True)
    store.write_text(hash_password(new), encoding="utf-8")
    _audit("password-change", "ok")
    return _result("password", "Đã đổi mật khẩu",
                   "Mật khẩu admin đã đổi. Các đăng nhập mới dùng mật khẩu này.", ok=True), 200


@admin_bp.route("/", methods=["GET"], strict_slashes=False)
def admin_page():
    """The action surface itself. Read-only GET: it only enumerates existing snapshots /
    releases for the dropdowns — it performs no action (those are POST-only)."""
    return render_template(
        "admin.html.jinja",
        token=_token(),
        snapshots=tsnap.list_snapshots(_snap_dir()),
        releases=rpack.list_releases(_rel_dir()),
        host=current_app.config.get("HOST", "127.0.0.1"),
        port=current_app.config.get("PORT", 5151),
        dirty=_tree_dirty(_ops_root()),
        auth_enabled=_auth_enabled(),
        system=_system_status(),
    )


@admin_bp.route("/action/restart", methods=["POST"])
def action_restart():
    host = current_app.config.get("HOST", "127.0.0.1")
    port = int(current_app.config.get("PORT", 5151))
    try:
        pid = _launch_restart(host, port)
    except OSError as exc:  # surface the spawn failure, don't swallow it
        _audit("restart", "error", error=str(exc))
        return _result("restart", "Lỗi", f"Không khởi động lại được: {exc}", ok=False), 500
    _audit("restart", "spawned", helper_pid=pid, host=host, port=port)
    return _result("restart", "Đang khởi động lại",
                   f"Đã sinh tiến trình khởi động lại tách rời (PID {pid}). "
                   "Trang sẽ tự kết nối lại khi dashboard sống lại.",
                   ok=True, poll_health=True), 202


@admin_bp.route("/action/snapshot", methods=["POST"])
def action_snapshot():
    rc, data, err = _run_engine(_TS, [*_root_args(), "--json", "snapshot", "--label", "admin"])
    if rc != 0 or not data:
        _audit("snapshot", "error", rc=rc, stderr=err)
        return _result("snapshot", "Lỗi", f"Chụp ảnh thất bại (mã {rc}). {err}", ok=False), 500
    name = Path(data.get("path", "")).name
    _audit("snapshot", "created", name=name, rc=rc)
    return _result("snapshot", "Đã chụp ảnh cây làm việc",
                   f"Ảnh chụp đã lưu: {name}", ok=True), 200


@admin_bp.route("/action/pack", methods=["POST"])
def action_pack():
    rc, data, err = _run_engine(_RP, ["--rel-dir", str(_rel_dir()), "--json", "pack"])
    if rc != 0 or not data:
        _audit("pack", "error", rc=rc, stderr=err)
        return _result("pack", "Lỗi", f"Đóng gói thất bại (mã {rc}). {err}", ok=False), 500
    name = Path(data.get("path", "")).name
    _audit("pack", "created", name=name, files=data.get("files"), rc=rc)
    return _result("pack", "Đã đóng gói bản phát hành",
                   f"Bản phát hành: {name} ({data.get('files')} tệp payload).", ok=True), 200


@admin_bp.route("/action/verify", methods=["POST"])
def action_verify():
    name = request.form.get("release", "")
    path = _resolve_in_dir(name, _rel_dir())
    if path is None:
        _audit("verify", "rejected-target", target=name)
        abort(400)
    # verify exits 0 clean / 1 on problems — so judge by the JSON, not the exit code; a None
    # payload (couldn't parse output) is the real failure.
    rc, data, err = _run_engine(_RP, ["--json", "verify", str(path)])
    if data is None:
        _audit("verify", "error", rc=rc, stderr=err, name=name)
        return _result("verify", "Lỗi", f"Kiểm tra thất bại (mã {rc}). {err}", ok=False), 500
    problems = data.get("problems") or []
    _audit("verify", data.get("result"), name=name, problems=problems)
    if not problems:
        return _result("verify", "Kiểm tra toàn vẹn",
                       f"Bản phát hành {name} nguyên vẹn — mọi sha256 khớp manifest.",
                       ok=True), 200
    return _result("verify", "Phát hiện vấn đề toàn vẹn",
                   f"{len(problems)} vấn đề trong {name}.", ok=False, detail=problems), 200


def _lan_action(cmd: str):
    """Run ``lan_setup.py <enable|disable>`` — sets AWB_DASHBOARD_HOST via setx (no admin
    needed) and applies the start-state. Surfaces the engine's result + the phone URLs."""
    port = int(current_app.config.get("PORT", 5151))
    rc, data, err = _run_engine(_LAN, [cmd, "--port", str(port), "--json"])
    if rc != 0 or not data:
        _audit(f"lan-{cmd}", "error", rc=rc, stderr=err)
        return _result("lan", "Lỗi", f"Lệnh LAN thất bại (mã {rc}). {err}", ok=False), 500
    _audit(f"lan-{cmd}", data.get("action", cmd))
    urls = data.get("lan_urls") or []
    if cmd == "enable":
        msg = "Đã bật mặc định LAN. Khởi động lại dashboard để áp dụng."
        if urls:
            msg += " Mở từ điện thoại: " + ", ".join(urls)
    else:
        msg = "Đã tắt mặc định LAN — quay về localhost-only."
    return _result("lan", "LAN " + ("BẬT" if cmd == "enable" else "TẮT"), msg, ok=True), 200


@admin_bp.route("/action/lan-enable", methods=["POST"])
def action_lan_enable():
    return _lan_action("enable")


@admin_bp.route("/action/lan-disable", methods=["POST"])
def action_lan_disable():
    return _lan_action("disable")


@admin_bp.route("/action/firewall-open", methods=["POST"])
def action_firewall_open():
    """Open the inbound LAN firewall rule. This NEEDS admin; a non-elevated dashboard can't
    do it, so a failure is surfaced honestly (run the command elevated / the self-elevating
    win/lan_on.bat) rather than pretending it worked."""
    port = int(current_app.config.get("PORT", 5151))
    rc, data, err = _run_engine(_LAN, ["firewall", "--port", str(port), "--json"])
    if data is None:
        _audit("firewall", "error", rc=rc, stderr=err)
        return _result("firewall", "Lỗi", f"Mở firewall thất bại (mã {rc}). {err}", ok=False), 500
    result = data.get("result")
    _audit("firewall", result)
    ok = result == "opened"
    msg = {
        "opened": "Đã mở cổng inbound cho LAN (chỉ local subnet).",
        "failed": "Không mở được — cần quyền admin. Chạy lệnh dưới trong PowerShell "
                  "(Run as administrator), hoặc bấm đúp win/lan_on.bat (tự nâng quyền UAC).",
        "manual": "Trên hệ này hãy chạy lệnh dưới thủ công.",
        "dry-run": "(dry-run) lệnh sẽ chạy:",
    }.get(result, str(result))
    detail = [d for d in (data.get("detail"), data.get("command")) if d]
    return _result("firewall", "Firewall LAN", msg, ok=ok, detail=detail or None), 200


def _autostart_action(cmd: str):
    """Run ``autostart.py <enable|disable>`` (schtasks). May need admin; an access-denied is
    surfaced with the self-elevating win/autostart_on.bat, not swallowed."""
    rc, data, err = _run_engine(_AS, [cmd, "--json"])
    if data is None:
        _audit(f"autostart-{cmd}", "error", rc=rc, stderr=err)
        return _result("autostart", "Lỗi", f"Lệnh autostart thất bại (mã {rc}). {err}", ok=False), 500
    result = data.get("result")
    _audit(f"autostart-{cmd}", result)
    ok = result in ("enabled", "removed")
    msg = {
        "enabled": "Đã bật tự khởi động lúc đăng nhập (chạy ẩn).",
        "removed": "Đã tắt tự khởi động.",
        "failed": "Không tạo được tác vụ — cần quyền admin. Bấm đúp "
                  "win/autostart_on.bat (tự nâng quyền UAC).",
        "not-found": "Không có tác vụ tự khởi động để xoá.",
        "manual": "Trên hệ này hãy cấu hình systemd thủ công (xem chi tiết).",
    }.get(result, str(result))
    detail = [d for d in (data.get("detail"), data.get("systemd_unit"), data.get("hint")) if d]
    return _result("autostart", "Tự khởi động", msg, ok=ok, detail=detail or None), 200


@admin_bp.route("/action/autostart-enable", methods=["POST"])
def action_autostart_enable():
    return _autostart_action("enable")


@admin_bp.route("/action/autostart-disable", methods=["POST"])
def action_autostart_disable():
    return _autostart_action("disable")


@admin_bp.route("/restore/preview", methods=["POST"])
def restore_preview():
    name = request.form.get("snapshot", "")
    path = _resolve_in_dir(name, _snap_dir())
    if path is None:
        _audit("restore-preview", "rejected-target", target=name)
        abort(400)
    # Dry-run restore via the CLI — gives the same plan + plan_hash the apply will re-validate.
    rc, plan, err = _run_engine(_TS, [*_root_args(), "--json", "restore", str(path)])
    if rc != 0 or not plan or "plan_hash" not in plan:
        _audit("restore-preview", "error", rc=rc, stderr=err, name=name)
        return _result("restore", "Lỗi", f"Xem trước thất bại (mã {rc}). {err}", ok=False), 500
    dirty = _tree_dirty(_ops_root())
    _audit("restore-preview", "ok", name=name, plan_hash=plan["plan_hash"],
           create=len(plan["will_create"]), modify=len(plan["will_modify"]))
    return render_template("_admin_restore_plan.html.jinja",
                           token=_token(), snapshot=name, plan=plan, dirty=dirty), 200


@admin_bp.route("/restore/apply", methods=["POST"])
def restore_apply():
    name = request.form.get("snapshot", "")
    confirm_hash = request.form.get("plan_hash", "")
    allow_dirty = request.form.get("allow_dirty") == "on"
    path = _resolve_in_dir(name, _snap_dir())
    if path is None:
        _audit("restore-apply", "rejected-target", target=name)
        abort(400)

    # Dirty-tree refusal is an admin policy (the engine doesn't check it) — enforce before
    # spawning the apply.
    if _tree_dirty(_ops_root()) and not allow_dirty:
        _audit("restore-apply", "refused-dirty", name=name)
        return _result("restore", "Bị từ chối — cây chưa commit",
                       "Cây làm việc có thay đổi chưa commit. Commit/stash trước, hoặc tick "
                       "“allow_dirty” để ghi đè có chủ đích.", ok=False), 409

    # The CLI apply re-validates the plan-hash (TOCTOU) and auto-backs-up before writing.
    rc, res, err = _run_engine(
        _TS, [*_root_args(), "--json", "restore", str(path), "--confirm", confirm_hash, "--yes"])
    if res is None:
        _audit("restore-apply", "error", rc=rc, stderr=err, name=name)
        return _result("restore", "Lỗi", f"Khôi phục thất bại (mã {rc}). {err}", ok=False), 500
    _audit("restore-apply", res.get("result"), name=name,
           backup=res.get("backup"), written=res.get("written"))

    if res.get("result") == "aborted-stale":
        return _result("restore", "Bị hủy — kế hoạch đã lệch [aborted-stale]",
                       "Cây đã thay đổi kể từ lúc xem trước nên plan-hash bị lệch; không ghi "
                       "gì cả. Xem trước lại để lấy hash mới.", ok=False,
                       detail=[f"expected {res.get('expected')}", f"actual {res.get('actual')}"]), 409

    backup_name = Path(res["backup"]).name if res.get("backup") else "không có"
    return _result("restore", "Đã khôi phục",
                   f"Đã ghi {res.get('written')} tệp từ {name}. "
                   f"Tự sao lưu trước khi ghi: {backup_name}.", ok=True), 200
