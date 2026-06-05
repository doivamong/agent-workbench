#!/usr/bin/env python3
"""ui/web/admin.py — the opt-in /admin action surface (Flask blueprint).

Mounted ONLY by ``app.create_app(admin=True)`` (i.e. ``python ui/web/app.py --admin``);
without the flag this blueprint is never registered, so every ``/admin*`` path is a plain
404. It turns the Phase-1 ops engine (``ops/dashboard_ctl.py``, ``ops/tree_snapshot.py``,
``ops/release_pack.py``) into web buttons — restart, snapshot, pack, verify, and a guarded
tree-restore — **reusing those callable APIs**, never re-implementing them.

The guards (the design was stress-tested to GO only with all of these):
  * **Opt-in, default-off** — no ``--admin`` → these routes don't exist.
  * **CSRF** — every mutation is POST-only and must carry the per-process token
    (``secrets.token_urlsafe`` minted in create_app), checked with ``hmac.compare_digest``
    before any side effect. GETs never mutate.
  * **Host / Origin allowlist** — every admin request must arrive with a localhost Host (and,
    if present, the bound port); a cross-origin ``Origin``/``Referer`` is refused.
  * **Server-enumerated targets** — the restore/verify target is chosen by name from a list
    THIS server produced (snapshots / releases dirs); a client-supplied path is rejected.
    Subprocess calls are arg lists, never a shell string.
  * **Guarded restore** — dry-run preview produces a plan-hash; the apply re-validates that
    hash (TOCTOU: aborts if the tree moved), takes an auto-backup first, and refuses a dirty
    tree unless ``allow_dirty``.
  * **Audited** — every action (and every blocked request) appends a JSON line to
    ``.ops/ops.log``; subprocess errors are surfaced, not swallowed.

HONEST LIMIT (documented on purpose): admin mode **trusts every local process that can
reach the bound port** — any such process can read the CSRF token from the served page.
It is opt-in, default-off, localhost-only, and **not for shared machines**. The CSRF/Origin
checks stop a cross-origin *browser* from forging requests; they do NOT stop a local
attacker who can already talk to the port.

DESIGN NOTE — in-process vs. subprocess (re: handover decision D4). The handover's D4 asked
for destructive ops to run via ``subprocess python ops/<tool>.py …`` (process isolation +
kill-ability). This module instead reuses the engine's **callable API in-process**, a
deliberate, documented deviation taken on ROI grounds:
  * Every data-safety guard the restore needs — TOCTOU plan-hash re-validation, auto-backup,
    dirty-tree refusal, zip-slip, the server-enumerated allowlist — lives IN that API and
    holds identically in-process; subprocess would add process isolation, which a restore
    (a *data* risk, not a stability one) does not need.
  * The Phase-1 CLIs hard-code ``REPO_ROOT`` and expose no ``--root``, so a subprocess could
    only ever target the real repo — untestable on a temp tree, where the in-process API
    (``root=``/``snap_dir=`` params) lets the 4 Critical guards be tested as real round-trips.
  * Subprocess would re-introduce the cross-platform reap/zombie surface the handover itself
    flags as a CI-only trap (``dashboard_ctl._reap``).
``threaded=True`` (set in app.main) recovers the one practical benefit subprocess offered —
a slow action not blocking the page. Only the self-restart genuinely needs a *detached*
subprocess (it must outlive the dying process); that one IS spawned, never in-process.
"""
from __future__ import annotations

import hmac
import json
import os
import subprocess
import sys
import urllib.parse
from datetime import datetime
from pathlib import Path

from flask import Blueprint, abort, current_app, render_template, request

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
import ops.dashboard_ctl as dctl   # noqa: E402  — reused engine (process control)
import ops.release_pack as rpack   # noqa: E402  — reused engine (release zips)
import ops.tree_snapshot as tsnap  # noqa: E402  — reused engine (tree snapshot/restore)

admin_bp = Blueprint("admin", __name__, template_folder="templates")

# Only these hostnames may reach /admin. urlsplit strips the brackets from "[::1]".
_ALLOWED_HOSTNAMES = {"127.0.0.1", "localhost", "::1"}


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
# Guards (before_request) — Host/Origin allowlist + CSRF
# --------------------------------------------------------------------------- #
def _host_allowed(value: str, *, match_port: bool) -> bool:
    """True if ``value`` (a Host header or an Origin/Referer URL) names a localhost host —
    and, when ``match_port`` and the value carries a port, that port is the one we bound."""
    if not value:
        return False
    try:
        parts = urllib.parse.urlsplit(value if "://" in value else "//" + value)
    except ValueError:
        return False
    if parts.hostname not in _ALLOWED_HOSTNAMES:
        return False
    try:
        port = parts.port
    except ValueError:
        return False
    want = current_app.config.get("PORT")
    if match_port and port is not None and want and port != int(want):
        return False
    return True


@admin_bp.before_request
def _enforce_guards():
    # Host allowlist applies to EVERY admin request (incl. GET) — DNS-rebind / wrong-vhost.
    if not _host_allowed(request.host, match_port=True):
        _audit("guard", "blocked-host", host=request.host, path=request.path)
        abort(403)
    if request.method not in ("GET", "HEAD", "OPTIONS"):
        # Cross-origin browser CSRF — defence in depth (hostname is the security-relevant bit).
        origin = request.headers.get("Origin") or request.headers.get("Referer")
        if origin and not _host_allowed(origin, match_port=False):
            _audit("guard", "blocked-origin", origin=origin, path=request.path)
            abort(403)
        # The real gate: the per-process CSRF token, constant-time compared.
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
    even when the dashboard was launched directly (``python ui/web/app.py --admin``)."""
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
    try:
        z = tsnap.snapshot(_ops_root(), label="admin", snap_dir=_snap_dir())
    except OSError as exc:
        _audit("snapshot", "error", error=str(exc))
        return _result("snapshot", "Lỗi", f"Không chụp được ảnh cây: {exc}", ok=False), 500
    _audit("snapshot", "created", path=str(z), name=z.name)
    return _result("snapshot", "Đã chụp ảnh cây làm việc",
                   f"Ảnh chụp đã lưu: {z.name}", ok=True), 200


@admin_bp.route("/action/pack", methods=["POST"])
def action_pack():
    try:
        z = rpack.pack(rel_dir=_rel_dir())
        n = len(rpack.payload_files())
    except (OSError, ValueError) as exc:
        _audit("pack", "error", error=str(exc))
        return _result("pack", "Lỗi", f"Không đóng gói được bản phát hành: {exc}", ok=False), 500
    _audit("pack", "created", path=str(z), name=z.name, files=n)
    return _result("pack", "Đã đóng gói bản phát hành",
                   f"Bản phát hành: {z.name} ({n} tệp payload).", ok=True), 200


@admin_bp.route("/action/verify", methods=["POST"])
def action_verify():
    name = request.form.get("release", "")
    path = _resolve_in_dir(name, _rel_dir())
    if path is None:
        _audit("verify", "rejected-target", target=name)
        abort(400)
    problems = rpack.verify(path)
    _audit("verify", "clean" if not problems else "problems", name=name, problems=problems)
    if not problems:
        return _result("verify", "Kiểm tra toàn vẹn",
                       f"Bản phát hành {name} nguyên vẹn — mọi sha256 khớp manifest.",
                       ok=True), 200
    return _result("verify", "Phát hiện vấn đề toàn vẹn",
                   f"{len(problems)} vấn đề trong {name}.", ok=False, detail=problems), 200


@admin_bp.route("/restore/preview", methods=["POST"])
def restore_preview():
    name = request.form.get("snapshot", "")
    path = _resolve_in_dir(name, _snap_dir())
    if path is None:
        _audit("restore-preview", "rejected-target", target=name)
        abort(400)
    plan = tsnap.plan_restore(path, _ops_root())
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
    root = _ops_root()

    if _tree_dirty(root) and not allow_dirty:
        _audit("restore-apply", "refused-dirty", name=name)
        return _result("restore", "Bị từ chối — cây chưa commit",
                       "Cây làm việc có thay đổi chưa commit. Commit/stash trước, hoặc tick "
                       "“allow_dirty” để ghi đè có chủ đích.", ok=False), 409

    # apply_restore re-validates the plan-hash (TOCTOU) and auto-backs-up before writing.
    res = tsnap.apply_restore(path, confirm_hash, root=root,
                              auto_backup=True, snap_dir=_snap_dir())
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
