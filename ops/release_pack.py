#!/usr/bin/env python3
"""release_pack.py — package the installable kit into a verifiable release zip.

Builds a timestamped/versioned zip of exactly what ``install.py`` would deploy (its
``COPY_MAP`` is the single source of truth — this never maintains a second file list),
with an embedded sha256 manifest so a release can be integrity-checked later or
unpacked into a target directory.

    python ops/release_pack.py pack                 # build .ops/releases/awb-kit-<ver>.zip
    python ops/release_pack.py list                 # existing release zips
    python ops/release_pack.py verify <zip>         # recompute every sha vs the manifest
    python ops/release_pack.py restore <zip> <dir>  # DRY-RUN unpack into <dir>
    python ops/release_pack.py restore <zip> <dir> --yes   # actually unpack

Stdlib only. ``<ver>`` comes from ``git describe`` when available, else a timestamp.

What this does NOT do: it packages the *kit payload* (the COPY_MAP groups), NOT the whole
repo (tests, examples, .git are not shipped) — use ``tree_snapshot.py`` for a full-tree
backup. The sha256 manifest proves **integrity** (the bytes are intact / unmodified), not
**authenticity** (it is not signed — it cannot prove who built it). Restore is dry-run by
default and writes into the directory you name; it does not touch the live kit.
"""
from __future__ import annotations

import argparse
import hashlib
import json
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
REL_DIR = OPS_DIR / "releases"
MANIFEST_NAME = "RELEASE_MANIFEST.json"

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
import install  # noqa: E402  — the kit's installer; COPY_MAP is the payload's single source of truth


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def payload_files() -> list[tuple[Path, str]]:
    """(absolute source path, archive name) for every file install.py would copy.
    Expands COPY_MAP directories exactly as install._copy does (skipping __pycache__),
    so the release contains precisely the installable payload — no drift."""
    out: list[tuple[Path, str]] = []
    for src_rel, dst_rel, _group in install.COPY_MAP:
        src = install.KIT / src_rel
        if src.is_dir():
            for f in sorted(src.rglob("*")):
                if f.is_dir() or "__pycache__" in f.parts:
                    continue
                arc = (Path(dst_rel) / f.relative_to(src)).as_posix()
                out.append((f, arc))
        elif src.is_file():
            out.append((src, Path(dst_rel).as_posix()))
    return out


def version() -> str:
    """git describe (tags/commit, marked --dirty), else a timestamp."""
    try:
        r = subprocess.run(["git", "describe", "--tags", "--always", "--dirty"],
                           cwd=str(REPO_ROOT), capture_output=True, text=True,
                           creationflags=_NO_WINDOW)
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip()
    except OSError:
        pass
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def pack(out: Path | None = None, ver: str | None = None,
         rel_dir: Path = REL_DIR) -> Path:
    """Build the release zip with an embedded sha256 manifest. Returns the zip path."""
    ver = ver or version()
    rel_dir.mkdir(parents=True, exist_ok=True)
    out = out or rel_dir / f"awb-kit-{ver}.zip"
    files = payload_files()
    manifest = {
        "kit": "agent-workbench",
        "version": ver,
        "created": datetime.now().strftime("%Y%m%d-%H%M%S"),
        "files": {},
    }
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        for src, arc in files:
            data = src.read_bytes()
            zf.writestr(arc, data)
            manifest["files"][arc] = _sha256(data)
        zf.writestr(MANIFEST_NAME, json.dumps(manifest, ensure_ascii=False, indent=2))
    return out


def verify(zip_path: Path) -> list[str]:
    """Recompute every member's sha vs the embedded manifest. Returns a list of
    problems (empty == clean): mismatches, members missing from the zip, and zip
    members absent from the manifest."""
    problems: list[str] = []
    with zipfile.ZipFile(zip_path) as zf:
        names = set(zf.namelist())
        if MANIFEST_NAME not in names:
            return [f"missing {MANIFEST_NAME} — not a release zip"]
        manifest = json.loads(zf.read(MANIFEST_NAME))
        recorded = manifest.get("files", {})
        for arc, want in recorded.items():
            if arc not in names:
                problems.append(f"missing from zip: {arc}")
                continue
            got = _sha256(zf.read(arc))
            if got != want:
                problems.append(f"sha mismatch: {arc}")
        for arc in names - {MANIFEST_NAME} - set(recorded):
            problems.append(f"not in manifest: {arc}")
    return problems


def list_releases(rel_dir: Path = REL_DIR) -> list[dict]:
    if not rel_dir.is_dir():
        return []
    out = []
    for z in sorted(rel_dir.glob("*.zip")):
        st = z.stat()
        out.append({"name": z.name, "path": str(z), "size": st.st_size,
                    "mtime": datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M:%S")})
    return out


def restore(zip_path: Path, target: Path, dry: bool = True) -> dict:
    """Unpack the release payload into ``target``. Dry-run by default. Zip-slip guarded."""
    target_res = target.resolve()
    actions: list[str] = []
    with zipfile.ZipFile(zip_path) as zf:
        for name in zf.namelist():
            if name == MANIFEST_NAME or name.endswith("/"):
                continue
            dest = (target / name).resolve()
            if target_res != dest and target_res not in dest.parents:
                raise ValueError(f"unsafe path in release (zip-slip): {name!r}")
            if dry:
                actions.append(f"would write: {name}")
            else:
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(zf.read(name))
                actions.append(f"wrote: {name}")
    return {"action": "restore", "result": "dry-run" if dry else "restored",
            "target": str(target), "count": len(actions)}


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def _emit(obj: dict, as_json: bool) -> None:
    if as_json:
        print(json.dumps(obj, ensure_ascii=False))
    else:
        for k, v in obj.items():
            print(f"  {k}: {v}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Pack / verify / restore the installable kit.")
    sub = ap.add_subparsers(dest="command", required=True)
    sub.add_parser("pack", help="build a release zip")
    sub.add_parser("list", help="list release zips")
    vp = sub.add_parser("verify", help="check a release zip's integrity")
    vp.add_argument("zip", type=Path)
    rp = sub.add_parser("restore", help="unpack a release into a directory")
    rp.add_argument("zip", type=Path)
    rp.add_argument("target", type=Path)
    rp.add_argument("--yes", action="store_true", help="actually write (default: dry-run)")
    # --rel-dir lets a caller (e.g. the ui/web /admin subprocess) choose where pack writes /
    # list reads — pass it BEFORE the subcommand. Default: this repo's .ops/releases.
    ap.add_argument("--rel-dir", type=Path, default=REL_DIR,
                    help="release store (default: <repo>/.ops/releases)")
    ap.add_argument("--json", action="store_true", help="emit JSON")
    args, _ = ap.parse_known_args(argv)
    as_json = "--json" in (argv if argv is not None else sys.argv[1:])

    if args.command == "pack":
        out = pack(rel_dir=args.rel_dir)
        _emit({"action": "pack", "result": "created", "path": str(out),
               "files": len(payload_files())}, as_json)
        return 0
    if args.command == "list":
        rels = list_releases(args.rel_dir)
        _emit({"releases": rels, "count": len(rels)}, as_json)
        return 0
    if args.command == "verify":
        if not args.zip.is_file():
            print(f"no such zip: {args.zip}", file=sys.stderr)
            return 2
        problems = verify(args.zip)
        _emit({"action": "verify", "result": "clean" if not problems else "problems",
               "problems": problems}, as_json)
        return 0 if not problems else 1
    # restore
    if not args.zip.is_file():
        print(f"no such zip: {args.zip}", file=sys.stderr)
        return 2
    result = restore(args.zip, args.target, dry=not args.yes)
    _emit(result, as_json)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
