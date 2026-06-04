#!/usr/bin/env python3
"""Runnable demo for the ops/ toolkit (dashboard_ctl, tree_snapshot, release_pack).

Exercises the three repo-operation tools on throwaway data — no server is started, no
port is opened, the live tree is never touched:

  1. tree_snapshot : snapshot a tiny fake tree → modify it → restore it back (round-trip,
     including the dry-run plan hash + TOCTOU-guarded apply).
  2. release_pack  : pack the real kit payload into a temp zip → verify it (clean) →
     tamper a byte → verify again (now reports the mismatch).
  3. dashboard_ctl : report status against a port nobody is serving (honestly "down")
     and show the exact launch command it would use.

    python examples/ops_demo.py
"""
from __future__ import annotations

import socket
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import ops.dashboard_ctl as dc  # noqa: E402
import ops.release_pack as rp  # noqa: E402
import ops.tree_snapshot as ts  # noqa: E402


def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port  # bound then released → nothing is listening on it now


def demo_tree_snapshot(tmp: Path) -> None:
    print("== tree_snapshot: snapshot → modify → restore ==")
    fake = tmp / "fake_repo"
    (fake / "src").mkdir(parents=True)
    (fake / "src" / "app.py").write_text("print('v1')\n", encoding="utf-8")
    snaps = tmp / "snaps"

    z = ts.snapshot(fake, label="demo", snap_dir=snaps)
    print(f"  snapshot taken: {z.name}")

    (fake / "src" / "app.py").write_text("print('BROKEN')\n", encoding="utf-8")
    plan = ts.plan_restore(z, fake)
    print(f"  after edit, dry-run plan: modify={plan['will_modify']} hash={plan['plan_hash'][:12]}…")

    res = ts.apply_restore(z, plan["plan_hash"], fake, auto_backup=True, snap_dir=snaps)
    restored = (fake / "src" / "app.py").read_text(encoding="utf-8").strip()
    print(f"  restored → {restored!r}  (auto-backup: {Path(res['backup']).name})")


def demo_release_pack(tmp: Path) -> None:
    print("\n== release_pack: pack → verify → tamper → verify ==")
    z = rp.pack(rel_dir=tmp, ver="demo")
    print(f"  packed {len(rp.payload_files())} payload files → {z.name}")
    print(f"  verify (intact): {'clean' if not rp.verify(z) else 'PROBLEMS'}")

    tampered = tmp / "tampered.zip"
    with zipfile.ZipFile(z) as zin, zipfile.ZipFile(tampered, "w") as zout:
        for item in zin.infolist():
            data = zin.read(item.filename)
            if item.filename.endswith("secrets_guard.py"):
                data += b"\n# tampered\n"
            zout.writestr(item, data)
    problems = rp.verify(tampered)
    print(f"  verify (tampered): {problems[0] if problems else 'clean?!'}")


def demo_dashboard_status() -> None:
    print("\n== dashboard_ctl: status on a dead port ==")
    port = _free_port()
    st = dc.status("127.0.0.1", port)
    print(f"  status :5{port % 1000:03d}… → listening={st['listening']} healthy={st['healthy']}")
    print(f"  would launch: {' '.join(dc.build_start_cmd('127.0.0.1', 5151)[1:])}")


def main() -> int:
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        demo_tree_snapshot(tmp)
        demo_release_pack(tmp)
    demo_dashboard_status()
    print("\nAll three ops tools exercised on throwaway data — no server, no live writes.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
