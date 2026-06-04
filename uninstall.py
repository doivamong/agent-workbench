#!/usr/bin/env python3
"""uninstall.py — cleanly remove what install.py put into a target project.

Symmetric to ``install.py``: it reads the **installer-manifest** that install wrote into
the target (``.claude/installer-manifest.json``) and reverses exactly that — the copied
files, the hook commands merged into ``settings.json``, and the ``.gitignore`` lines it
added. The headline guarantee: after ``install.py <p> --merge-settings`` then
``uninstall.py <p> --yes`` on a fresh project, ``git status`` is clean.

Safety model (stdlib only):
  - **Dry-run by default.** It prints what *would* change and touches nothing until you
    pass ``--yes`` (alias ``--apply``).
  - **Keeps user-modified files.** Each manifest entry records the kit's canonical sha256.
    A file whose current bytes still match is removed; one you edited (sha mismatch) is
    KEPT with a warning — uninstall never deletes your work.
  - **Reverts settings precisely.** It removes only the hook *command strings* install
    added (recorded in the manifest), preserving any hooks you added yourself. If install
    *created* settings.json and nothing else lives in it after the revert, the file is
    removed; otherwise the revert is written and the prior content is saved to
    ``settings.json.bak``.
  - **Fails loud on a missing manifest.** With no manifest it refuses to guess — it never
    pattern-deletes blindly (that could eat files the kit never installed).

Usage:
    python uninstall.py /path/to/project            # dry run (default) — shows the plan
    python uninstall.py /path/to/project --yes       # actually remove
    python uninstall.py /path/to/project --apply     # same as --yes
"""
from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path

# Reuse install.py's single sources of truth (sha256, the manifest/settings paths) so the
# two stay symmetric — uninstall is the exact inverse, not a re-derivation.
KIT = Path(__file__).resolve().parent
sys.path.insert(0, str(KIT))
import install  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def revert_settings(existing: dict, commands: set[str]) -> dict:
    """Remove hooks whose ``command`` is in ``commands``; drop emptied groups/events.

    The exact inverse of install._merge_settings: a group that contained only installer
    commands is dropped wholesale (its matcher too); a hook you added survives; an event
    with no groups left is removed, as is an empty top-level ``hooks`` key.
    """
    result = copy.deepcopy(existing)
    hooks = result.get("hooks")
    if not isinstance(hooks, dict):
        return result
    for event in list(hooks):
        new_groups = []
        for group in hooks[event]:
            kept = [h for h in group.get("hooks", []) if h.get("command") not in commands]
            if kept:
                ng = dict(group)
                ng["hooks"] = kept
                new_groups.append(ng)
        if new_groups:
            hooks[event] = new_groups
        else:
            del hooks[event]
    if not hooks:
        result.pop("hooks", None)
    return result


def plan_files(project: Path, manifest: dict) -> tuple[list[str], list[str], list[str]]:
    """Classify each manifest file as (remove, keep_modified, already_gone).

    remove        — present and bytes still match the kit's recorded sha256.
    keep_modified — present but edited since install (sha mismatch) → never deleted.
    already_gone  — not on disk (nothing to do).
    """
    remove, keep, gone = [], [], []
    for rel, meta in sorted(manifest.get("files", {}).items()):
        path = project / rel
        if not path.exists():
            gone.append(rel)
        elif install.sha256(path) == meta.get("sha256"):
            remove.append(rel)
        else:
            keep.append(rel)
    return remove, keep, gone


def _prune_empty_dirs(project: Path, removed: list[str]) -> list[Path]:
    """Remove now-empty ancestor dirs of removed files (deepest first), never the project
    root and never a dir that still holds files. Returns the dirs removed."""
    dirs: set[Path] = set()
    for rel in removed:
        p = (project / rel).parent
        while p != project and project in p.parents:
            dirs.add(p)
            p = p.parent
    pruned = []
    for d in sorted(dirs, key=lambda p: len(p.parts), reverse=True):
        try:
            if d.is_dir() and not any(d.iterdir()):
                d.rmdir()
                pruned.append(d)
        except OSError:
            pass
    return pruned


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Remove what install.py installed (dry-run by default).")
    ap.add_argument("target", type=Path, help="Path to the project to clean")
    ap.add_argument("--yes", "--apply", dest="apply", action="store_true",
                    help="Actually perform the removal (default is a dry run that changes nothing)")
    args = ap.parse_args(argv)

    project = args.target.resolve()
    if not project.is_dir():
        print(f"Target is not a directory: {project}", file=sys.stderr)
        return 1

    manifest_path = project / install.MANIFEST_REL
    if not manifest_path.is_file():
        print(f"No installer-manifest at {manifest_path}.", file=sys.stderr)
        print("Refusing to guess what to remove — uninstall never pattern-deletes blindly.",
              file=sys.stderr)
        print("If the kit was installed before manifests existed, remove its files by hand, or "
              "re-run install.py to regenerate the manifest first.", file=sys.stderr)
        return 1
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        print(f"Could not read manifest {manifest_path}: {e}", file=sys.stderr)
        return 1

    dry = not args.apply
    print(f"Uninstalling kit from: {project}{'  (dry run — pass --yes to apply)' if dry else ''}\n")

    remove, keep, gone = plan_files(project, manifest)
    for rel in remove:
        print(f"  {'would remove' if dry else 'removed'}: {rel}")
    for rel in keep:
        print(f"  KEEP (modified since install): {rel}")
    for rel in gone:
        print(f"  already gone: {rel}")

    # settings.json revert (symmetric to install --merge-settings)
    settings_meta = manifest.get("settings", {})
    commands = set(settings_meta.get("hooks_added", []))
    settings_path = project / install.SETTINGS_REL
    settings_action = None
    if commands and settings_path.is_file():
        try:
            current = json.loads(settings_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            print(f"  WARN could not read {settings_path} ({e}); leaving it untouched.")
            current = None
        if current is not None:
            reverted = revert_settings(current, commands)
            if settings_meta.get("created") and reverted in ({}, {"hooks": {}}):
                # install created settings.json and nothing else lives in it → remove it
                # wholesale (no .bak: there was no pre-existing config to protect). This is
                # what keeps `git status` clean on a fresh install→uninstall.
                settings_action = ("remove", None)
            else:
                settings_action = ("revert", reverted)
    if settings_action:
        kind, payload = settings_action
        if kind == "remove":
            print(f"  {'would remove' if dry else 'removed'}: {install.SETTINGS_REL} (installer-created)")
        else:
            print(f"  {'would revert' if dry else 'reverted'}: {install.SETTINGS_REL} "
                  f"(installer hooks stripped; backup → {install.SETTINGS_BAK_REL})")

    # .gitignore revert
    gi_meta = manifest.get("gitignore", {})
    gi_lines = set(gi_meta.get("lines_added", []))
    gi_path = project / ".gitignore"
    gi_action = None
    if gi_lines and gi_path.is_file():
        kept_lines = [ln for ln in gi_path.read_text(encoding="utf-8").splitlines()
                      if ln not in gi_lines]
        # also drop our bookkeeping comment if it is now orphaned
        kept_lines = [ln for ln in kept_lines
                      if ln.strip() != "# agent-workbench installer bookkeeping (machine-specific)"]
        if gi_meta.get("created") and not [ln for ln in kept_lines if ln.strip()]:
            gi_action = ("remove", None)
        else:
            gi_action = ("rewrite", kept_lines)
        print(f"  {'would update' if dry else 'updated'}: .gitignore "
              f"({'remove' if gi_action[0] == 'remove' else 'strip installer lines'})")

    print(f"  {'would remove' if dry else 'removed'}: {install.MANIFEST_REL}")

    if dry:
        print(f"\nDry run: {len(remove)} file(s) would be removed, {len(keep)} kept (modified). "
              "Re-run with --yes to apply.")
        return 0

    # ---- apply ----
    for rel in remove:
        try:
            (project / rel).unlink()
        except OSError as e:
            print(f"  WARN could not remove {rel}: {e}")
    if settings_action:
        kind, payload = settings_action
        if kind == "remove":
            settings_path.unlink(missing_ok=True)
        else:
            (project / install.SETTINGS_BAK_REL).write_text(
                settings_path.read_text(encoding="utf-8"), encoding="utf-8")
            settings_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    if gi_action:
        kind, payload = gi_action
        if kind == "remove":
            gi_path.unlink(missing_ok=True)
        else:
            body = "\n".join(payload).rstrip("\n")
            gi_path.write_text(body + "\n" if body else "", encoding="utf-8")
    manifest_path.unlink(missing_ok=True)
    pruned = _prune_empty_dirs(project, remove + [install.MANIFEST_REL, install.SETTINGS_REL])

    print(f"\nDone: removed {len(remove)} file(s); kept {len(keep)} modified file(s); "
          f"pruned {len(pruned)} empty dir(s).")
    if keep:
        print("Kept (edited since install) — remove by hand if you no longer want them:")
        for rel in keep:
            print(f"  {rel}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
