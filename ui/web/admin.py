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
import urllib.parse
from datetime import datetime
from pathlib import Path

from flask import Blueprint, abort, current_app, render_template, request

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
import ops.dashboard_ctl as dctl   # noqa: E402  — reused engine (process control)
import ops.release_pack as rpack   # noqa: E402  — read-only enumeration (list_releases)
import ops.tree_snapshot as tsnap  # noqa: E402  — read-only enumeration (list_snapshots) + is_git_repo

# Engine CLIs driven as subprocesses for every ACTION (D4). Read-only enumeration uses the
# imported APIs above; writes go through these scripts.
_TS = REPO_ROOT / "ops" / "tree_snapshot.py"
_RP = REPO_ROOT / "ops" / "release_pack.py"

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
