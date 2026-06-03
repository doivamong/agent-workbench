#!/usr/bin/env python3
"""memory_sync.py — copy the PUBLIC-SAFE subset of a memory dir into a target, leak-gated.

You keep a full, private memory (the per-project store, or a private backup repo); only
*some* of those facts are safe to publish into a public repo's ``memory/``. Doing that by
hand is error-prone, and the expensive mistake is one-directional: a machine path, a
private identifier, or an internal note leaked into a public commit. This tool makes the
filter mechanical and **fail-closed**.

A source fact is synced into the target only when BOTH hold:

  1. **leak-clean** — ``leak_scan.scan_file`` (generic patterns + an ``--entropy`` sweep,
     plus an optional project ``--denylist``) finds nothing; and
  2. **opted in** — its frontmatter declares ``metadata.visibility: public``, OR a file of
     the same name already exists in the target (an already-published fact keeps syncing
     without re-tagging).

Everything else is excluded and reported with a reason. The default for an *unmarked* new
fact is therefore **private**: a fact can never reach the public target by accident — it
must declare ``visibility: public`` (or already be there). On copy, the per-machine /
per-session / source-side governance keys (``node_type``, ``originSessionId``,
``visibility``) are dropped so the published fact is clean.

    python tools/memory_sync.py --source <private-mem> --target memory --check   # dry-run report
    python tools/memory_sync.py --source <private-mem> --target memory --write   # apply
    python tools/memory_sync.py --source <private-mem> --target memory --denylist private.txt --write

Does **NOT**: commit, push, or manage the ``MEMORY.md`` index — that stays human-curated
(the tool syncs fact *files*; review the diff and update the index yourself). The leak gate
is a *tripwire*, not a guarantee — it shares ``leak_scan``'s limits (line-based, heuristic).
**Manual-run only**: never wire it to a hook or cron, the same way ``memory_snapshot.py`` is
manual-only — an unattended mutator that *publishes* has no undo.

Stdlib-only. Reuses ``leak_scan.scan_file`` and ``memory_audit.parse_frontmatter`` rather
than re-deriving them (see ``.claude/rules/defer-discipline.md``).
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# Reuse the kit's pieces (do not re-derive the parser or the scanner).
sys.path.insert(0, str(Path(__file__).resolve().parent))
from leak_scan import GENERIC_PATTERNS, load_denylist, scan_file  # noqa: E402
from memory_audit import parse_frontmatter  # noqa: E402

# The index and its readme are managed by hand, never synced as facts.
INDEX_AND_DOCS = {"MEMORY.md", "README.md"}
# Frontmatter keys that are per-machine / per-session / source-side governance — never published.
STRIP_KEYS = ("node_type", "originSessionId", "visibility")
_STRIP_RE = re.compile(r"\s*(?:" + "|".join(STRIP_KEYS) + r")\s*:", re.IGNORECASE)


def visibility(fm: dict | None) -> str:
    """A fact's declared visibility, defaulting to ``private`` (fail-closed)."""
    if not fm:
        return "private"
    meta = fm.get("metadata") if isinstance(fm.get("metadata"), dict) else {}
    raw = (meta.get("visibility") or fm.get("visibility") or "").strip().lower()
    return raw or "private"


def strip_private_keys(text: str) -> str:
    """Drop per-machine / per-session / governance frontmatter lines for the public copy."""
    kept = [ln for ln in text.splitlines() if not _STRIP_RE.match(ln)]
    return "\n".join(kept).rstrip() + "\n"


def plan(source: Path, target: Path, patterns) -> dict:
    """Compute the sync plan over ``source``'s facts.

    Eligible := leak-clean AND (visibility == ``public`` OR a same-named file already in
    ``target``). Returns ``{"included": [(name, public_content, reason)],
    "excluded": [(name, reason)], "orphans": [name]}`` where *orphans* are facts present in
    the target that no eligible source fact backs (a human decides whether to remove them).
    """
    existing = ({p.name for p in target.glob("*.md")} - INDEX_AND_DOCS) if target.is_dir() else set()
    included: list[tuple[str, str, str]] = []
    excluded: list[tuple[str, str]] = []
    for p in sorted(source.glob("*.md")):
        if p.name in INDEX_AND_DOCS:
            continue
        leaks = scan_file(p, patterns, entropy=True)
        if leaks:
            kinds = ",".join(sorted({name for _, name, _ in leaks}))
            excluded.append((p.name, f"LEAK [{kinds}]"))
            continue
        text = p.read_text(encoding="utf-8")
        vis = visibility(parse_frontmatter(text))
        if vis == "public":
            included.append((p.name, strip_private_keys(text), "visibility: public"))
        elif p.name in existing:
            included.append((p.name, strip_private_keys(text), "already published"))
        else:
            excluded.append((p.name, "private (no `visibility: public`)"))
    inc = {n for n, _, _ in included}
    orphans = sorted(existing - inc)
    return {"included": included, "excluded": excluded, "orphans": orphans}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Sync the public-safe subset of a memory dir into a target, leak-gated.")
    ap.add_argument("--source", type=Path, required=True, help="The private/full memory dir to sync FROM")
    ap.add_argument("--target", type=Path, required=True, help="The public memory dir to sync INTO")
    ap.add_argument("--denylist", type=Path,
                    help="Project-specific terms/regexes for the leak gate (gitignored)")
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true",
                      help="Dry-run: report the plan, write nothing (the default)")
    mode.add_argument("--write", action="store_true", help="Apply: write eligible facts into --target")
    args = ap.parse_args(argv)

    if not args.source.is_dir():
        print(f"error: --source {args.source} is not a directory", file=sys.stderr)
        return 2

    patterns = list(GENERIC_PATTERNS)
    if args.denylist and args.denylist.exists():
        patterns += load_denylist(args.denylist)

    p = plan(args.source, args.target, patterns)
    for name, _, why in p["included"]:
        print(f"  + {name}  ({why})")
    for name, why in p["excluded"]:
        print(f"  - {name}  ({why})")
    for name in p["orphans"]:
        print(f"  ? {name}  (in target, no eligible source — review / remove by hand)")

    if args.write:
        args.target.mkdir(parents=True, exist_ok=True)
        for name, content, _ in p["included"]:
            (args.target / name).write_text(content, encoding="utf-8")
        print(f"\nwrote {len(p['included'])} fact(s) to {args.target}; "
              f"{len(p['excluded'])} excluded. Review the diff before you commit.")
    else:
        print(f"\n[dry-run] {len(p['included'])} would sync, {len(p['excluded'])} excluded, "
              f"{len(p['orphans'])} orphan(s). Re-run with --write to apply.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
