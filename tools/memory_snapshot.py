#!/usr/bin/env python3
"""memory_snapshot.py — snapshot / list / restore a file-based memory directory.

The memory store (see ``docs/memory-governance.md``) lives OUTSIDE git, so ``git checkout``
cannot undo a bad edit. The one safety net is an explicit snapshot taken *before* any
mutation. This is that net: a manual CLI you run yourself — **never wire it to a hook or
cron** (an unattended mutator with no rollback is exactly the failure this guards against;
see the honest lessons in the governance doc).

Operations:
  snapshot   copy every top-level file of the memory dir into ``<dir>/.snapshots/<ts>/``,
             then rotate so only the newest --keep snapshots remain
  list       show available snapshots, oldest first
  restore    copy a snapshot's files back over the memory dir. ADDITIVE: it never deletes
             files created after the snapshot — it only restores what the snapshot holds,
             so a memory written later is preserved, not lost. Dry-run unless --apply.
             With --apply it first snapshots the CURRENT state (label ``pre-restore``) so a
             wrong restore is reversible too — restore is itself a mutation, and snapshot-
             before-mutate applies to it. ``--latest`` always skips those ``pre-restore``
             backups (else the next ``restore --latest`` would re-apply the state you just
             discarded); reach one explicitly with ``--from`` to undo a bad restore.

Only top-level files are captured (``-maxdepth 1``): ``.snapshots/`` and any backup
subdirectories are skipped, so snapshots never nest inside snapshots.

Kill switch: set ``AGENT_MEMORY_AUTOMATION=0`` to make the one destructive op
(``restore --apply``) refuse to touch files without editing code. Read-only ops (list,
snapshot, dry-run restore) are never blocked.

Stdlib only.
"""
from __future__ import annotations

import argparse
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

KILL_SWITCH_ENV = "AGENT_MEMORY_AUTOMATION"
SNAPSHOT_DIRNAME = ".snapshots"
DEFAULT_KEEP = 10
# Label for the snapshot ``restore --apply`` takes of the CURRENT state before overwriting it,
# so a wrong restore is itself reversible. ``--latest`` skips these (see resolve_snapshot) — else
# the next ``restore --latest`` would pick this backup of the just-discarded state and re-apply it.
PRE_RESTORE_LABEL = "pre-restore"

# Windows pythonw.exe can hand us a non-UTF stdout; keep prints from crashing.
# (When a second tool needs this, lift it into a shared util — see PORT_CATALOG "W1-util".)
if sys.stdout is not None and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    except Exception:
        pass


def automation_disabled() -> bool:
    """True when the kill switch (``AGENT_MEMORY_AUTOMATION=0``) is set."""
    return os.environ.get(KILL_SWITCH_ENV) == "0"


def iter_top_level_files(memory_dir: Path) -> list[Path]:
    """Every regular file directly in ``memory_dir`` (``-maxdepth 1``); subdirs are skipped."""
    return sorted((p for p in memory_dir.iterdir() if p.is_file()), key=lambda p: p.name)


def _snapshot_root(memory_dir: Path) -> Path:
    return memory_dir / SNAPSHOT_DIRNAME


def list_snapshots(memory_dir: Path) -> list[Path]:
    """Snapshot dirs, oldest first (fixed-width timestamp names, so sort == chronological)."""
    root = _snapshot_root(memory_dir)
    if not root.is_dir():
        return []
    return sorted((d for d in root.iterdir() if d.is_dir()), key=lambda d: d.name)


def _rotate(memory_dir: Path, keep: int) -> list[str]:
    """Keep the newest ``keep`` snapshots, delete older ones. Returns removed names."""
    removed: list[str] = []
    if keep < 0:
        return removed
    snaps = list_snapshots(memory_dir)
    for old in snaps[: max(0, len(snaps) - keep)]:
        shutil.rmtree(old)
        removed.append(old.name)
    return removed


def snapshot_memory(memory_dir: Path, keep: int = DEFAULT_KEEP, label: str | None = None) -> Path:
    """Copy top-level files into ``<dir>/.snapshots/<timestamp>[_label]/``, rotate, return the new dir."""
    root = _snapshot_root(memory_dir)
    root.mkdir(exist_ok=True)
    ts = datetime.now(tz=timezone.utc).strftime("%Y%m%dT%H%M%S_%f") + "Z"
    base = f"{ts}_{label}" if label else ts
    dest = root / base
    # Defend against two snapshots landing in the same microsecond.
    n = 1
    while dest.exists():
        dest = root / f"{base}_{n}"
        n += 1
    dest.mkdir()
    for f in iter_top_level_files(memory_dir):
        shutil.copy2(f, dest / f.name)
    _rotate(memory_dir, keep)
    return dest


def resolve_snapshot(memory_dir: Path, ref: str | None, latest: bool) -> Path:
    """Find a snapshot by ``--latest`` or by ``--from <ref>`` (full name or unambiguous prefix)."""
    snaps = list_snapshots(memory_dir)
    if not snaps:
        raise FileNotFoundError(f"no snapshots in {_snapshot_root(memory_dir)}")
    if latest:
        # Skip auto pre-restore backups: --latest means the latest snapshot YOU took, never the
        # one restore made of the state it overwrote (picking that would re-apply discarded state).
        # A pre-restore backup is still reachable explicitly via --from to undo a bad restore.
        user_snaps = [s for s in snaps if PRE_RESTORE_LABEL not in s.name]
        if not user_snaps:
            raise FileNotFoundError(
                f"only pre-restore snapshots in {_snapshot_root(memory_dir)}; "
                "pass --from <name> to restore one explicitly")
        return user_snaps[-1]
    if not ref:
        raise FileNotFoundError("need --latest or --from <snapshot>")
    exact = [s for s in snaps if s.name == ref]
    if exact:
        return exact[0]
    prefix = [s for s in snaps if s.name.startswith(ref)]
    if len(prefix) == 1:
        return prefix[0]
    if len(prefix) > 1:
        raise FileNotFoundError(f"ref {ref!r} matches {len(prefix)} snapshots — be more specific")
    raise FileNotFoundError(f"no snapshot matches {ref!r}")


def restore_snapshot(memory_dir: Path, snapshot_dir: Path, apply: bool = False) -> tuple[list[str], list[str]]:
    """Copy a snapshot's files back over ``memory_dir``. Additive — never deletes newer files.

    Returns ``(restored, preserved)``: ``restored`` = files the snapshot holds (overwritten
    when ``apply`` is True); ``preserved`` = files now in ``memory_dir`` that the snapshot does
    not contain (left untouched). With ``apply=False`` nothing is written.
    """
    snap_files = [p for p in snapshot_dir.iterdir() if p.is_file()]
    snap_names = {p.name for p in snap_files}
    current = {p.name for p in iter_top_level_files(memory_dir)}
    preserved = sorted(current - snap_names)
    restored: list[str] = []
    for f in snap_files:
        if apply:
            shutil.copy2(f, memory_dir / f.name)
        restored.append(f.name)
    return sorted(restored), preserved


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Snapshot / list / restore a file-based memory directory.")
    ap.add_argument("--dir", type=Path, default=Path("memory"), help="memory directory (default: memory)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_snap = sub.add_parser("snapshot", help="copy top-level files into .snapshots/ before mutating")
    p_snap.add_argument("--keep", type=int, default=DEFAULT_KEEP, help=f"snapshots to retain (default: {DEFAULT_KEEP})")
    p_snap.add_argument("--label", default=None, help="optional suffix on the snapshot name")

    sub.add_parser("list", help="list snapshots, oldest first")

    p_rest = sub.add_parser("restore", help="restore from a snapshot (dry-run unless --apply)")
    pick = p_rest.add_mutually_exclusive_group(required=True)
    pick.add_argument("--latest", action="store_true", help="restore the newest snapshot")
    pick.add_argument("--from", dest="ref", default=None, help="snapshot name or unambiguous prefix")
    p_rest.add_argument("--apply", action="store_true", help="actually overwrite (default: preview only)")

    args = ap.parse_args(argv)
    memory_dir: Path = args.dir
    if not memory_dir.is_dir():
        print(f"not a directory: {memory_dir}", file=sys.stderr)
        return 2

    if args.cmd == "snapshot":
        dest = snapshot_memory(memory_dir, keep=args.keep, label=args.label)
        print(f"snapshot: {dest.name}  ({len(iter_top_level_files(memory_dir))} file(s))")
        return 0

    if args.cmd == "list":
        snaps = list_snapshots(memory_dir)
        if not snaps:
            print("(no snapshots)")
        for s in snaps:
            print(s.name)
        return 0

    # restore
    try:
        snap = resolve_snapshot(memory_dir, args.ref, args.latest)
    except FileNotFoundError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    if args.apply and automation_disabled():
        print(f"KILL SWITCH: {KILL_SWITCH_ENV}=0 -> restore --apply refuses to write. Nothing touched.")
        return 0
    if args.apply:
        # Snapshot the current state before overwriting it, so a wrong restore is reversible too
        # (this is itself a mutation; honor snapshot-before-mutate). Comes AFTER the kill switch.
        pre = snapshot_memory(memory_dir, label=PRE_RESTORE_LABEL)
        print(f"pre-restore snapshot: {pre.name}")
    restored, preserved = restore_snapshot(memory_dir, snap, apply=args.apply)
    mode = "RESTORED" if args.apply else "DRY-RUN (pass --apply to write)"
    print(f"{mode} from {snap.name}: {len(restored)} file(s)")
    for name in restored:
        print(f"  <- {name}")
    if preserved:
        print(f"preserved (newer than snapshot, untouched): {len(preserved)}")
        for name in preserved:
            print(f"  =  {name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
