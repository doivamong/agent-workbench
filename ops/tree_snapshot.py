#!/usr/bin/env python3
"""tree_snapshot.py — zip / list / restore the working tree as a dev safety net.

A quick, gitignore-respecting snapshot of the repo before a risky operation, and a
guarded restore back. Snapshots are plain zips under the git-ignored ``.ops/snapshots/``;
each embeds a manifest (file list + sha256 + git commit) so a restore can be previewed
and verified before it touches anything.

    python ops/tree_snapshot.py snapshot                  # zip the tree now
    python ops/tree_snapshot.py snapshot --label pre-x    # ...with a label in the name
    python ops/tree_snapshot.py list                      # existing snapshots
    python ops/tree_snapshot.py restore <zip>             # DRY-RUN: preview + print confirm hash
    python ops/tree_snapshot.py restore <zip> --confirm <hash> --yes   # actually apply

Stdlib only. The file set is exactly ``git ls-files --cached --others --exclude-standard``
(tracked + untracked-but-not-ignored, excluding .git) so it honours .gitignore precisely.

What this does NOT do: restore is an *overlay* — it writes the files in the zip; it does
NOT delete files that exist now but aren't in the snapshot (deleting on restore is too
easy to get catastrophically wrong). Restore is **dry-run by default**; applying needs the
plan hash from the dry-run (so a tree that changed since the preview is refused — see the
TOCTOU guard) plus ``--yes``. Outside a git repo it falls back to a coarser os.walk that
cannot read .gitignore — it warns when it does.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import zipfile
from datetime import datetime
from pathlib import Path

if sys.stdout is not None and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    except Exception:
        pass

_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)  # Windows: ẩn cửa sổ console; non-Windows: 0 (no-op)

REPO_ROOT = Path(__file__).resolve().parents[1]
OPS_DIR = REPO_ROOT / ".ops"
SNAP_DIR = OPS_DIR / "snapshots"
MANIFEST_NAME = ".tree_snapshot_manifest.json"

# Directories the os.walk fallback always skips (the git path skips via exclude-standard).
_FALLBACK_SKIP = {".git", "__pycache__", ".ops", ".pytest_cache", ".venv", "node_modules"}


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def is_git_repo(root: Path) -> bool:
    try:
        r = subprocess.run(["git", "rev-parse", "--is-inside-work-tree"],
                           cwd=str(root), capture_output=True, text=True,
                           creationflags=_NO_WINDOW)
        return r.returncode == 0 and r.stdout.strip() == "true"
    except (OSError, FileNotFoundError):
        return False


def _git_commit(root: Path) -> str | None:
    try:
        r = subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                           cwd=str(root), capture_output=True, text=True,
                           creationflags=_NO_WINDOW)
        return r.stdout.strip() if r.returncode == 0 else None
    except OSError:
        return None


def repo_files(root: Path = REPO_ROOT) -> tuple[list[str], bool]:
    """(sorted relative POSIX paths, used_git). Tracked + untracked-not-ignored via
    git; coarse os.walk fallback (used_git=False) when not a git repo."""
    if is_git_repo(root):
        r = subprocess.run(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
            cwd=str(root), capture_output=True, text=True, creationflags=_NO_WINDOW)
        if r.returncode == 0:
            files = [p for p in r.stdout.split("\0") if p]
            return sorted(set(files)), True
    out: list[str] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in _FALLBACK_SKIP]
        for fn in filenames:
            rel = (Path(dirpath) / fn).relative_to(root).as_posix()
            out.append(rel)
    return sorted(set(out)), False


def snapshot(root: Path = REPO_ROOT, label: str | None = None,
             snap_dir: Path = SNAP_DIR) -> Path:
    """Zip the current tree into snap_dir; embed a manifest. Returns the zip path."""
    snap_dir.mkdir(parents=True, exist_ok=True)
    files, used_git = repo_files(root)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    safe_label = "".join(c for c in (label or "") if c.isalnum() or c in "-_")
    name = f"tree-{stamp}{('-' + safe_label) if safe_label else ''}.zip"
    out = snap_dir / name
    manifest = {
        "kind": "tree-snapshot",
        "created": stamp,
        "root": root.name,
        "used_git": used_git,
        "git_commit": _git_commit(root),
        "files": {},
    }
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        for rel in files:
            src = root / rel
            try:
                data = src.read_bytes()
            except OSError:
                continue  # vanished between listing and read — skip, don't abort
            zf.writestr(rel, data)
            manifest["files"][rel] = _sha256(data)
        zf.writestr(MANIFEST_NAME, json.dumps(manifest, ensure_ascii=False, indent=2))
    return out


def list_snapshots(snap_dir: Path = SNAP_DIR) -> list[dict]:
    if not snap_dir.is_dir():
        return []
    out = []
    for z in sorted(snap_dir.glob("*.zip")):
        st = z.stat()
        out.append({"name": z.name, "path": str(z), "size": st.st_size,
                    "mtime": datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M:%S")})
    return out


def _safe_members(zf: zipfile.ZipFile, root: Path) -> list[str]:
    """Zip-slip guard: every member must resolve to a path INSIDE root. Returns the
    real file members (excluding the manifest); raises ValueError on any escape."""
    root_res = root.resolve()
    members = []
    for name in zf.namelist():
        if name == MANIFEST_NAME or name.endswith("/"):
            continue
        target = (root / name).resolve()
        if root_res != target and root_res not in target.parents:
            raise ValueError(f"unsafe path in snapshot (zip-slip): {name!r}")
        members.append(name)
    return members


def plan_restore(zip_path: Path, root: Path = REPO_ROOT) -> dict:
    """Preview a restore without writing anything. Classifies each member as create /
    modify / unchanged and returns a ``plan_hash`` that the apply step must echo back —
    so if the tree changes between preview and apply, the apply is refused (TOCTOU)."""
    with zipfile.ZipFile(zip_path) as zf:
        members = _safe_members(zf, root)
        create, modify, unchanged = [], [], []
        rows = []
        for name in sorted(members):
            new_sha = _sha256(zf.read(name))
            cur = root / name
            if not cur.exists():
                action = "create"; create.append(name)
            else:
                cur_sha = _sha256(cur.read_bytes())
                if cur_sha == new_sha:
                    action = "unchanged"; unchanged.append(name)
                else:
                    action = "modify"; modify.append(name)
            rows.append((name, action, new_sha))
    plan_hash = _sha256(
        "\n".join(f"{n}\t{a}\t{s}" for n, a, s in rows).encode("utf-8"))
    return {
        "zip": str(zip_path),
        "files_total": len(rows),
        "will_create": create,
        "will_modify": modify,
        "unchanged": unchanged,
        "plan_hash": plan_hash,
    }


def apply_restore(zip_path: Path, confirm_hash: str, root: Path = REPO_ROOT,
                  auto_backup: bool = True, snap_dir: Path = SNAP_DIR) -> dict:
    """Apply a previously-previewed restore. Recomputes the plan and refuses if its
    hash no longer matches ``confirm_hash`` (the tree moved under us). Takes an
    auto-backup of the current tree first, by default."""
    plan = plan_restore(zip_path, root)
    if plan["plan_hash"] != confirm_hash:
        return {"action": "restore", "result": "aborted-stale",
                "reason": "tree changed since preview; re-run dry-run for a fresh hash",
                "expected": confirm_hash, "actual": plan["plan_hash"]}
    backup = str(snapshot(root, label="pre-restore", snap_dir=snap_dir)) if auto_backup else None
    written = []
    with zipfile.ZipFile(zip_path) as zf:
        for name in _safe_members(zf, root):
            target = root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(zf.read(name))
            written.append(name)
    return {"action": "restore", "result": "restored", "backup": backup,
            "written": len(written), "files": written}


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def _emit(obj: dict, as_json: bool) -> None:
    if as_json:
        print(json.dumps(obj, ensure_ascii=False))
    else:
        for k, v in obj.items():
            if isinstance(v, list) and len(v) > 8:
                print(f"  {k}: [{len(v)} items]")
            else:
                print(f"  {k}: {v}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Snapshot / list / restore the working tree.")
    sub = ap.add_subparsers(dest="command", required=True)
    sp = sub.add_parser("snapshot", help="zip the tree now")
    sp.add_argument("--label", help="label embedded in the snapshot filename")
    sub.add_parser("list", help="list existing snapshots")
    rp = sub.add_parser("restore", help="preview (dry-run) or apply a restore")
    rp.add_argument("zip", type=Path, help="snapshot zip to restore from")
    rp.add_argument("--confirm", help="plan hash from the dry-run (required to apply)")
    rp.add_argument("--yes", action="store_true", help="apply (with --confirm)")
    rp.add_argument("--no-backup", action="store_true", help="skip the pre-restore auto-backup")
    # --root / --snap-dir let a caller (e.g. the ui/web /admin subprocess) point the snapshot &
    # restore at a tree other than this repo — pass them BEFORE the subcommand. Default: this repo.
    ap.add_argument("--root", type=Path, default=REPO_ROOT,
                    help="tree to snapshot / restore into (default: this repo)")
    ap.add_argument("--snap-dir", type=Path, default=None,
                    help="snapshot store (default: <root>/.ops/snapshots)")
    ap.add_argument("--json", action="store_true", help="emit JSON")
    args, _ = ap.parse_known_args(argv)
    as_json = "--json" in (argv if argv is not None else sys.argv[1:])
    root = args.root
    snap_dir = args.snap_dir or (root / ".ops" / "snapshots")

    if args.command == "snapshot":
        out = snapshot(root, args.label, snap_dir=snap_dir)
        _emit({"action": "snapshot", "result": "created", "path": str(out)}, as_json)
        return 0
    if args.command == "list":
        snaps = list_snapshots(snap_dir)
        _emit({"snapshots": snaps, "count": len(snaps)}, as_json)
        return 0
    # restore
    if not args.zip.is_file():
        print(f"no such snapshot: {args.zip}", file=sys.stderr)
        return 2
    if not (args.confirm and args.yes):
        plan = plan_restore(args.zip, root)
        _emit({**plan, "note": "DRY-RUN. To apply: "
               f"--confirm {plan['plan_hash']} --yes"}, as_json)
        return 0
    result = apply_restore(args.zip, args.confirm, root,
                           auto_backup=not args.no_backup, snap_dir=snap_dir)
    _emit(result, as_json)
    return 0 if result.get("result") == "restored" else 1


if __name__ == "__main__":
    raise SystemExit(main())
