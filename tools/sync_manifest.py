#!/usr/bin/env python3
"""sync_manifest.py — a drift gate for the file *set* under source-of-truth dirs.

When you add a skill, a hook, a tool, or a rule, dependent artifacts have to move with it:
the registry gets a row, the README counts tick, `settings.json` wires the hook. It is easy to
add the file and forget the rest — and most of those slips have no guard today (`skill_lint`
covers the skills↔registry pair only). This tool is the deterministic backstop: it snapshots
the *set of tracked files* under a few roots into a JSON manifest, and `--check` fails when that
set drifts from the snapshot (a file was added or removed) so you are forced to acknowledge it.

Why the file SET and not content hashes: gating CI on every file's hash would turn every ordinary
content edit red until you regenerate — pure ceremony. The signal that actually requires updating
dependent docs/wiring is **a file appearing or disappearing**, so that is what the exit code gates.
Line and byte counts are recorded as a cheap change *hint* (reported as informational `changed`,
never gated) — deliberately not a cryptographic hash, both because the gate doesn't need one and
so the manifest stays free of high-entropy tokens the leak scanner would (rightly) flag.

    python tools/sync_manifest.py --check            # exit 1 if the file set drifted
    python tools/sync_manifest.py --write            # regenerate the manifest (after adding/removing a file)
    python tools/sync_manifest.py --check --manifest .claude/manifest.json --root .

Pairs with the `sync_guard.py` PostToolUse hook, which nudges you toward `--check` the moment a
new file lands in a watched dir. See docs/guard-mechanisms.md: the hook is the bypassable seatbelt,
this tool (in CI/pre-commit) is the deterministic gate with history.

Does NOT: judge whether the dependent docs are actually *correct* — only that the file set matches
the snapshot. It does not detect a file that was edited (by design), nor reconcile a rename (that
reads as one removal + one addition). Stdlib only.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if sys.stdout is not None and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    except Exception:
        pass

# Roots whose file SET, when it changes, usually means a dependent doc/registry/wiring must change
# too. Relative to --root. Tune for your project.
DEFAULT_ROOTS = (".claude/skills", ".claude/hooks", ".claude/rules", ".claude/agents", "tools", "scripts", "ui")
DEFAULT_MANIFEST = ".claude/manifest.json"
SCAN_SUFFIXES = {".py", ".md"}
SKIP_PARTS = {"__pycache__", ".pytest_cache", "references"}


def _category(rel_path: str) -> str:
    """First two path segments (e.g. ``.claude/skills``) — the bucket a file belongs to."""
    parts = rel_path.split("/")
    return "/".join(parts[:2]) if parts[0] == ".claude" else parts[0]


def build_manifest(root: Path, roots: tuple[str, ...] = DEFAULT_ROOTS,
                   suffixes: set[str] | None = None) -> dict:
    """Snapshot the tracked file set under `roots`: {path: {category, lines, bytes}}.

    Pure (filesystem in, dict out) so it is unit-testable. Paths are POSIX-relative to `root`
    and the entries are insertion-sorted, so the JSON is stable across machines and OSes.
    `lines`/`bytes` are a cheap change hint, not a hash — see the module docstring.
    """
    suffixes = suffixes or SCAN_SUFFIXES
    files: dict[str, dict] = {}
    for r in roots:
        base = root / r
        if not base.is_dir():
            continue
        for p in sorted(base.rglob("*")):
            if p.is_dir() or any(part in SKIP_PARTS for part in p.parts):
                continue
            if p.suffix not in suffixes:
                continue
            rel = p.relative_to(root).as_posix()
            try:
                data = p.read_bytes()
            except OSError:
                continue
            files[rel] = {
                "category": _category(rel),
                "lines": data.count(b"\n") + 1,
                "bytes": len(data),
            }
    return {"roots": list(roots), "files": dict(sorted(files.items()))}


def _size(entry: dict) -> tuple[int, int]:
    return (entry.get("lines", -1), entry.get("bytes", -1))


def diff_manifest(stored: dict, current: dict) -> tuple[list[str], list[str], list[str]]:
    """(added, removed, changed) paths. Only added/removed are gated; changed is informational."""
    old, new = stored.get("files", {}), current.get("files", {})
    added = sorted(set(new) - set(old))
    removed = sorted(set(old) - set(new))
    changed = sorted(p for p in (set(old) & set(new)) if _size(old[p]) != _size(new[p]))
    return added, removed, changed


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Snapshot/check the file set under source-of-truth dirs.")
    ap.add_argument("--root", type=Path, default=Path("."), help="project root (default: .)")
    ap.add_argument("--manifest", type=Path, default=None,
                    help=f"manifest path (default: <root>/{DEFAULT_MANIFEST})")
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="exit 1 if the file set drifted (default mode)")
    mode.add_argument("--write", action="store_true", help="regenerate the manifest and exit 0")
    args = ap.parse_args(argv)

    manifest_path = args.manifest or (args.root / DEFAULT_MANIFEST)
    current = build_manifest(args.root)

    if args.write:
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(json.dumps(current, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"Wrote manifest: {len(current['files'])} file(s) -> {manifest_path}")
        return 0

    # default + --check: compare against the stored manifest.
    if not manifest_path.exists():
        print(f"No manifest at {manifest_path}. Run: python tools/sync_manifest.py --write")
        return 1
    try:
        stored = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"Could not read manifest {manifest_path}: {exc}")
        return 1

    added, removed, changed = diff_manifest(stored, current)
    for p in added:
        print(f"[drift] ADDED   {p} — add its registry row / README count / hook wiring, then --write")
    for p in removed:
        print(f"[drift] REMOVED {p} — remove its dependent rows/wiring, then --write")
    for p in changed:
        print(f"[info]  changed {p} (content only — not gated)")

    if added or removed:
        print(f"\nFile-set drift: {len(added)} added, {len(removed)} removed. "
              "Update the dependents, then `python tools/sync_manifest.py --write`.")
        return 1
    print(f"Manifest in sync ({len(current['files'])} files; {len(changed)} content-only change(s)).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
