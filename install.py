#!/usr/bin/env python3
"""install.py — drop this kit's tooling into an existing project.

Copies the reusable pieces (hooks, skills, rules, tools, secrets_guard, the memory
scaffold) into a target project and prints the exact settings.json snippet you need
to activate the hooks. Optionally installs a git pre-commit hook that runs the leak
scanner. Stdlib only; safe to re-run (won't overwrite unless you pass --force).

Usage:
    python install.py /path/to/your/project
    python install.py /path/to/your/project --with-git-hook
    python install.py /path/to/your/project --dry-run
    python install.py /path/to/your/project --force            # overwrite existing files
    python install.py /path/to/your/project --select hooks,skills  # only these groups (+deps)
    python install.py /path/to/your/project --list             # groups available / installed
    python install.py /path/to/your/project --coverage         # installed-vs-available counts

It writes an installer-manifest (``.claude/installer-manifest.json``, git-ignored in the
target) recording what it copied, so ``uninstall.py`` can cleanly reverse the install —
keeping any file you edited. Run ``python uninstall.py /path/to/your/project`` (dry-run by
default; ``--yes`` to apply).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

# Print UTF-8 safely even on a legacy Windows console (cp1252/cp437) or when stdout
# is redirected — otherwise a non-ASCII character in our output raises
# UnicodeEncodeError and aborts the install. Same idiom as the hooks use.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

KIT = Path(__file__).resolve().parent

# (source relative to kit, destination relative to target project, GROUP)
# The group is the unit of `--select`: you install/uninstall by group, not by file.
COPY_MAP = [
    (".claude/hooks", ".claude/hooks", "hooks"),
    (".claude/session-primer.md", ".claude/session-primer.md", "hooks"),
    (".claude/skills", ".claude/skills", "skills"),
    (".claude/rules", ".claude/rules", "rules"),
    (".claude/agents", ".claude/agents", "agents"),
    ("tools/leak_scan.py", "tools/leak_scan.py", "tools"),
    ("tools/license_scan.py", "tools/license_scan.py", "tools"),
    ("tools/invariants.py", "tools/invariants.py", "tools"),
    ("tools/affected_tests.py", "tools/affected_tests.py", "tools"),
    ("tools/memory_audit.py", "tools/memory_audit.py", "tools"),
    ("tools/memory_recall_doctor.py", "tools/memory_recall_doctor.py", "tools"),
    ("tools/skill_lint.py", "tools/skill_lint.py", "tools"),
    ("tools/skill_usage_report.py", "tools/skill_usage_report.py", "tools"),
    ("scripts/secrets_guard.py", "scripts/secrets_guard.py", "tools"),
    ("memory", "memory", "memory"),
]

# The selectable groups, in install order. Source of truth for --select / --list.
GROUPS = ["hooks", "skills", "rules", "agents", "tools", "memory"]

# Soft dependencies: selecting a group auto-selects what it needs to be useful.
# hooks→skills: skill_routing_inject.py fails open without the skills, but its routing
# map is empty — so installing the hooks without the skills ships a no-op. Pulling skills
# in keeps a --select install functional (handover C1: "a hook that needs a skill
# auto-selects it"). Kept minimal and accurate; not every hook needs every group.
DEPENDENCIES = {"hooks": {"skills"}}

# The installer-manifest records exactly what was installed (path + sha256 + group), so
# uninstall.py can remove precisely that and KEEP user-modified files. It lives in the
# TARGET project (not the kit) to avoid a dual-location trap, and is git-ignored there
# (it is machine-specific bookkeeping, not source).
MANIFEST_REL = ".claude/installer-manifest.json"
MANIFEST_SCHEMA = 1
SETTINGS_REL = ".claude/settings.json"
SETTINGS_BAK_REL = ".claude/settings.json.bak"

SETTINGS_SNIPPET = {
    "hooks": {
        "PreToolUse": [
            {
                "matcher": "Bash",
                "hooks": [
                    {
                        "type": "command",
                        "command": 'python "$CLAUDE_PROJECT_DIR/.claude/hooks/scripts/block_dangerous.py"',
                        "timeout": 10,
                    }
                ],
            }
        ],
        "UserPromptSubmit": [
            {
                "hooks": [
                    {
                        "type": "command",
                        "command": 'python "$CLAUDE_PROJECT_DIR/.claude/hooks/prompt-refiner-inject.py"',
                        "timeout": 10,
                    }
                ]
            }
        ],
        "PostToolUse": [
            {
                "matcher": "Edit|Write",
                "hooks": [
                    {
                        "type": "command",
                        "command": 'python "$CLAUDE_PROJECT_DIR/.claude/hooks/scripts/post_edit_simplify.py"',
                        "timeout": 10,
                    }
                ],
            },
            {
                "hooks": [
                    {
                        "type": "command",
                        "command": 'python "$CLAUDE_PROJECT_DIR/.claude/hooks/scripts/context_tracker.py"',
                        "timeout": 10,
                    }
                ]
            },
        ],
        "PreCompact": [
            {
                "hooks": [
                    {
                        "type": "command",
                        "command": 'python "$CLAUDE_PROJECT_DIR/.claude/hooks/scripts/precompact_backup.py"',
                        "timeout": 10,
                    }
                ]
            }
        ],
        "SessionStart": [
            {
                "matcher": "compact",
                "hooks": [
                    {
                        "type": "command",
                        "command": 'python "$CLAUDE_PROJECT_DIR/.claude/hooks/scripts/compact_restore.py"',
                        "timeout": 10,
                    }
                ],
            },
            {
                "matcher": "startup|resume|clear",
                "hooks": [
                    {
                        "type": "command",
                        "command": 'python "$CLAUDE_PROJECT_DIR/.claude/hooks/scripts/session_start.py"',
                        "timeout": 10,
                    }
                ],
            },
            {
                # No matcher: runs on every SessionStart so the agent gets the skill
                # routing map each session. Derived from the (also-copied) skill-registry.md
                # and fails open if it's missing, so it's safe to wire for any adopter.
                "hooks": [
                    {
                        "type": "command",
                        "command": 'python "$CLAUDE_PROJECT_DIR/.claude/hooks/scripts/skill_routing_inject.py"',
                        "timeout": 10,
                    }
                ]
            },
        ],
        "SessionEnd": [
            {
                "hooks": [
                    {
                        "type": "command",
                        "command": 'python "$CLAUDE_PROJECT_DIR/.claude/hooks/scripts/session_end.py"',
                        "timeout": 10,
                    }
                ],
            }
        ],
    }
}

GIT_PRE_COMMIT = """#!/bin/sh
# Installed by agent-workbench. Blocks commits that leak secrets/identifiers.
# --respect-gitignore skips git-ignored local files that never ship (matches CI / .pre-commit-config).
if command -v python3 >/dev/null 2>&1; then PY=python3; else PY=python; fi
"$PY" tools/leak_scan.py . --entropy --fail-on-find --respect-gitignore || {
    echo "leak_scan found a potential secret/identifier. Fix it or add '# leak-scan: ignore'." >&2
    exit 1
}
"""


def _copy(src: Path, dst: Path, force: bool, dry: bool) -> list[str]:
    actions: list[str] = []
    if src.is_dir():
        for f in src.rglob("*"):
            if f.is_dir() or "__pycache__" in f.parts:
                continue
            rel = f.relative_to(src)
            target = dst / rel
            actions += _copy_file(f, target, force, dry)
    else:
        actions += _copy_file(src, dst, force, dry)
    return actions


def _copy_file(src: Path, target: Path, force: bool, dry: bool) -> list[str]:
    if target.exists() and not force:
        return [f"  skip (exists): {target}"]
    if dry:
        return [f"  would copy: {target}"]
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, target)
    return [f"  copied: {target}"]


def _install_git_hook(project: Path, dry: bool) -> str:
    git_dir = project / ".git"
    if not git_dir.is_dir():
        return "  (no .git found — skipped git pre-commit hook)"
    hook = git_dir / "hooks" / "pre-commit"
    if dry:
        return f"  would write git hook: {hook}"
    hook.parent.mkdir(parents=True, exist_ok=True)
    hook.write_text(GIT_PRE_COMMIT, encoding="utf-8")
    try:
        hook.chmod(0o755)
    except OSError:
        pass
    return f"  wrote git pre-commit hook: {hook}"


def _merge_settings(existing: dict, snippet: dict) -> dict:
    """Deep-merge the snippet's ``hooks`` block into an existing settings dict.

    Idempotent: a hook is identified by its ``command`` string, so re-running the
    installer never duplicates an entry. Other keys in ``existing`` are preserved.
    """
    result = json.loads(json.dumps(existing))  # deep copy, never mutate the input
    hooks = result.setdefault("hooks", {})
    for event, groups in snippet.get("hooks", {}).items():
        existing_groups = hooks.setdefault(event, [])
        existing_cmds = {
            h.get("command")
            for g in existing_groups
            for h in g.get("hooks", [])
        }
        for group in groups:
            group_cmds = {h.get("command") for h in group.get("hooks", [])}
            if group_cmds & existing_cmds:
                continue  # already wired — skip so the merge stays idempotent
            existing_groups.append(group)
    return result


def _apply_settings_merge(project: Path, dry: bool) -> list[str]:
    """Merge SETTINGS_SNIPPET into the project's .claude/settings.json. Fail-soft."""
    settings = project / ".claude" / "settings.json"
    existing: dict = {}
    if settings.exists():
        try:
            existing = json.loads(settings.read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            return [f"  could not read {settings} ({e}); printing the snippet instead."]
    merged = _merge_settings(existing, SETTINGS_SNIPPET)
    if merged == existing:
        return [f"  already wired: {settings} (no change)"]
    if dry:
        return [f"  would merge hooks into: {settings}"]
    settings.parent.mkdir(parents=True, exist_ok=True)
    settings.write_text(json.dumps(merged, indent=2) + "\n", encoding="utf-8")
    return [f"  merged hooks into: {settings}"]


# --------------------------------------------------------------------------- #
# C1 lifecycle: group selection, manifest, gitignore
# --------------------------------------------------------------------------- #
def sha256(path: Path) -> str:
    """Hex sha256 of a file's bytes — the identity uninstall uses to tell an
    untouched installed file (safe to remove) from a user-modified one (keep)."""
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def settings_commands(snippet: dict = SETTINGS_SNIPPET) -> list[str]:
    """Every hook ``command`` string the installer would add — the exact set
    uninstall.py reverts from settings.json (symmetric to ``_merge_settings``)."""
    return [h.get("command")
            for groups in snippet.get("hooks", {}).values()
            for g in groups
            for h in g.get("hooks", [])
            if h.get("command")]


def resolve_groups(selected: list[str] | None) -> list[str]:
    """Expand a --select list to include soft dependencies, in GROUPS order.

    None (no --select) means ALL groups — backward-compatible default. An unknown
    group name raises ValueError so a typo fails loud instead of silently installing
    nothing.
    """
    if selected is None:
        return list(GROUPS)
    want = set()
    for name in selected:
        name = name.strip()
        if not name:
            continue
        if name not in GROUPS:
            raise ValueError(f"unknown group {name!r}; choose from: {', '.join(GROUPS)}")
        want.add(name)
        want |= DEPENDENCIES.get(name, set())
    return [g for g in GROUPS if g in want]


def copy_entries_for(groups: list[str]) -> list[tuple[str, str, str]]:
    """COPY_MAP entries whose group is in ``groups``."""
    chosen = set(groups)
    return [(s, d, g) for (s, d, g) in COPY_MAP if g in chosen]


def installed_files(manifest: dict) -> set[str]:
    return set(manifest.get("files", {}))


def _write_manifest(project: Path, files: dict[str, dict], groups: list[str],
                    settings_info: dict, gitignore_info: dict, dry: bool) -> list[str]:
    """Write/merge the installer-manifest into the TARGET project. Unions with any
    existing manifest so installing groups incrementally accumulates one truthful record."""
    path = project / MANIFEST_REL
    existing: dict = {}
    if path.is_file():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            existing = {}
    merged_files = {**existing.get("files", {}), **files}
    merged_groups = sorted(set(existing.get("groups", [])) | set(groups))
    # settings/gitignore: keep the FIRST recorded create-state (that's the one uninstall
    # must reverse); union the added command/line lists.
    prev_settings = existing.get("settings", {})
    prev_gitignore = existing.get("gitignore", {})
    manifest = {
        "schema": MANIFEST_SCHEMA,
        "kit": "agent-workbench",
        "groups": merged_groups,
        "files": dict(sorted(merged_files.items())),
        "settings": {
            "created": prev_settings.get("created", settings_info.get("created", False)),
            "hooks_added": sorted(set(prev_settings.get("hooks_added", []))
                                  | set(settings_info.get("hooks_added", []))),
        },
        "gitignore": {
            "created": prev_gitignore.get("created", gitignore_info.get("created", False)),
            "lines_added": sorted(set(prev_gitignore.get("lines_added", []))
                                  | set(gitignore_info.get("lines_added", []))),
        },
    }
    if dry:
        return [f"  would write manifest: {path} ({len(merged_files)} file(s))"]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return [f"  wrote manifest: {path} ({len(merged_files)} file(s))"]


def _ensure_gitignore(project: Path, lines: list[str], dry: bool) -> dict:
    """Ensure each line is present in the target .gitignore. Returns the info dict
    {created, lines_added} so the manifest can record exactly what to reverse."""
    path = project / ".gitignore"
    created = not path.exists()
    current = "" if created else path.read_text(encoding="utf-8")
    have = set(current.splitlines())
    to_add = [ln for ln in lines if ln not in have]
    info = {"created": created, "lines_added": to_add}
    if not to_add or dry:
        return info
    block = ""
    if current and not current.endswith("\n"):
        block += "\n"
    if created or not current.strip():
        block += "# agent-workbench installer bookkeeping (machine-specific)\n"
    block += "\n".join(to_add) + "\n"
    path.write_text(current + block, encoding="utf-8")
    return info


def _kit_file_shas(src: Path, dst_rel: str) -> list[tuple[str, str]]:
    """For a COPY_MAP source, yield (target-relative POSIX path, sha256 of the kit source).

    This is the kit's *canonical* content for each installed file — uninstall compares the
    live file against it to decide remove (matches) vs keep (user-modified)."""
    out: list[tuple[str, str]] = []
    if src.is_dir():
        for f in sorted(src.rglob("*")):
            if f.is_dir() or "__pycache__" in f.parts:
                continue
            rel = (Path(dst_rel) / f.relative_to(src)).as_posix()
            out.append((rel, sha256(f)))
    elif src.is_file():
        out.append((Path(dst_rel).as_posix(), sha256(src)))
    return out


def _report(project: Path, manifest: dict, *, coverage: bool) -> int:
    """--list / --coverage: show available groups and what is installed in the target."""
    installed_groups = set(manifest.get("groups", []))
    installed = installed_files(manifest)
    avail_by_group: dict[str, int] = {g: 0 for g in GROUPS}
    for src_rel, dst_rel, group in COPY_MAP:
        for _ in _kit_file_shas(KIT / src_rel, dst_rel):
            avail_by_group[group] += 1
    if coverage:
        n_files_installed = len(installed)
        n_files_avail = sum(avail_by_group.values())
        print(f"Coverage for {project}:")
        print(f"  groups: {len(installed_groups & set(GROUPS))}/{len(GROUPS)} installed")
        print(f"  files:  {n_files_installed}/{n_files_avail} tracked in the installer-manifest")
        if not manifest:
            print("  (no installer-manifest found — nothing installed by this kit, or installed "
                  "before manifests existed)")
        return 0
    print(f"Available groups (installed into {project} marked ✓):")
    for g in GROUPS:
        mark = "✓" if g in installed_groups else " "
        dep = f"  (pulls in: {', '.join(sorted(DEPENDENCIES[g]))})" if g in DEPENDENCIES else ""
        print(f"  [{mark}] {g:<8} {avail_by_group[g]:>2} file(s){dep}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Install the kit into a project.")
    ap.add_argument("target", type=Path, help="Path to your project root")
    ap.add_argument("--force", action="store_true", help="Overwrite existing files")
    ap.add_argument("--dry-run", action="store_true", help="Show what would happen")
    ap.add_argument("--with-git-hook", action="store_true", help="Install a git pre-commit leak gate")
    ap.add_argument(
        "--merge-settings",
        action="store_true",
        help="Merge the hooks block into .claude/settings.json automatically (idempotent), "
             "instead of just printing the snippet for you to paste.",
    )
    ap.add_argument(
        "--select", metavar="GROUPS",
        help=f"Comma-separated groups to install (default: all). Groups: {', '.join(GROUPS)}. "
             "Dependencies are pulled in automatically (e.g. hooks → skills).",
    )
    ap.add_argument("--list", action="store_true",
                    help="List the available groups and what is already installed in the target, then exit.")
    ap.add_argument("--coverage", action="store_true",
                    help="Report installed-vs-available groups/files for the target, then exit.")
    args = ap.parse_args(argv)

    project = args.target.resolve()
    if not project.is_dir():
        print(f"Target is not a directory: {project}", file=sys.stderr)
        return 1
    if project == KIT:
        print("Refusing to install the kit into itself.", file=sys.stderr)
        return 1

    # Read any existing manifest once — both --list/--coverage and the install path use it.
    manifest_path = project / MANIFEST_REL
    existing_manifest: dict = {}
    if manifest_path.is_file():
        try:
            existing_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            existing_manifest = {}

    if args.list or args.coverage:
        return _report(project, existing_manifest, coverage=args.coverage)

    # Resolve which groups to install (None → all; deps auto-added). Fail loud on a typo.
    try:
        groups = resolve_groups(args.select.split(",") if args.select else None)
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    if args.select:
        print(f"Selected groups (with dependencies): {', '.join(groups)}\n")

    print(f"Installing kit into: {project}{'  (dry run)' if args.dry_run else ''}\n")
    manifest_files: dict[str, dict] = {}
    for src_rel, dst_rel, group in copy_entries_for(groups):
        src = KIT / src_rel
        if not src.exists():
            print(f"  WARN missing in kit: {src_rel}")
            continue
        print(f"{src_rel} -> {dst_rel}  [{group}]")
        for line in _copy(src, project / dst_rel, args.force, args.dry_run):
            print(line)
        # Record the kit's canonical content (source sha) so uninstall can tell an
        # untouched installed file from a user-modified one, regardless of copy/skip.
        for rel, digest in _kit_file_shas(src, dst_rel):
            manifest_files[rel] = {"sha256": digest, "group": group}

    if args.with_git_hook:
        print("\ngit pre-commit hook:")
        print(_install_git_hook(project, args.dry_run))
        if (project / ".pre-commit-config.yaml").exists():
            print("  NOTE: this project uses the pre-commit framework. Running "
                  "'pre-commit install' will overwrite this raw hook; wire the leak "
                  "scan into .pre-commit-config.yaml instead (see this kit's).")

    # Settings only make sense when the hooks they point at are installed.
    settings_info = {"created": False, "hooks_added": []}
    if "hooks" in groups:
        if args.merge_settings:
            settings_created = not (project / SETTINGS_REL).exists()
            print("\nActivating hooks (--merge-settings):")
            for line in _apply_settings_merge(project, args.dry_run):
                print(line)
            settings_info = {"created": settings_created, "hooks_added": settings_commands()}
        else:
            print("\nNext step - activate the hooks. Merge this into your")
            print(f"  {project / '.claude' / 'settings.json'}")
            print("  (or re-run with --merge-settings to do this automatically)\n")
            print(json.dumps(SETTINGS_SNIPPET, indent=2))
    elif args.merge_settings:
        print("\n  (skipped --merge-settings: the 'hooks' group was not selected)")

    # Record what was installed so uninstall.py can reverse exactly this — and git-ignore
    # the machine-specific manifest in the target.
    if manifest_files:
        gitignore_info = _ensure_gitignore(project, [MANIFEST_REL], args.dry_run)
        print("\nInstaller bookkeeping:")
        for line in _write_manifest(project, manifest_files, groups,
                                    settings_info, gitignore_info, args.dry_run):
            print(line)

    print("\nThen open the project in Claude Code. Dangerous Bash commands will be")
    print("blocked and vague prompts will be flagged. See .claude/skills/README.md to")
    print("start using the skill system, and memory/README.md for the memory system.")
    print("\nMEMORY: the copied memory/ holds EXAMPLE facts (a reference template) - replace them")
    print("with your own. Claude Code (v2.1.59+) auto-loads MEMORY.md from a per-project path")
    print("(~/.claude/projects/<id>/memory/), NOT this repo's memory/ - so curate facts there (or")
    print("point autoMemoryDirectory at it). Run 'python tools/memory_recall_doctor.py' to verify.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
