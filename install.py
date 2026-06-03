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
    python install.py /path/to/your/project --force      # overwrite existing files
"""
from __future__ import annotations

import argparse
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

# (source relative to kit, destination relative to target project)
COPY_MAP = [
    (".claude/hooks", ".claude/hooks"),
    (".claude/skills", ".claude/skills"),
    (".claude/rules", ".claude/rules"),
    (".claude/session-primer.md", ".claude/session-primer.md"),
    ("tools/leak_scan.py", "tools/leak_scan.py"),
    ("tools/license_scan.py", "tools/license_scan.py"),
    ("tools/invariants.py", "tools/invariants.py"),
    ("tools/affected_tests.py", "tools/affected_tests.py"),
    ("tools/memory_audit.py", "tools/memory_audit.py"),
    ("tools/memory_recall_doctor.py", "tools/memory_recall_doctor.py"),
    ("tools/skill_lint.py", "tools/skill_lint.py"),
    ("tools/skill_usage_report.py", "tools/skill_usage_report.py"),
    ("scripts/secrets_guard.py", "scripts/secrets_guard.py"),
    ("memory", "memory"),
]

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
if command -v python3 >/dev/null 2>&1; then PY=python3; else PY=python; fi
"$PY" tools/leak_scan.py . --entropy --fail-on-find || {
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
    args = ap.parse_args(argv)

    project = args.target.resolve()
    if not project.is_dir():
        print(f"Target is not a directory: {project}", file=sys.stderr)
        return 1
    if project == KIT:
        print("Refusing to install the kit into itself.", file=sys.stderr)
        return 1

    print(f"Installing kit into: {project}{'  (dry run)' if args.dry_run else ''}\n")
    for src_rel, dst_rel in COPY_MAP:
        src = KIT / src_rel
        if not src.exists():
            print(f"  WARN missing in kit: {src_rel}")
            continue
        print(f"{src_rel} -> {dst_rel}")
        for line in _copy(src, project / dst_rel, args.force, args.dry_run):
            print(line)

    if args.with_git_hook:
        print("\ngit pre-commit hook:")
        print(_install_git_hook(project, args.dry_run))
        if (project / ".pre-commit-config.yaml").exists():
            print("  NOTE: this project uses the pre-commit framework. Running "
                  "'pre-commit install' will overwrite this raw hook; wire the leak "
                  "scan into .pre-commit-config.yaml instead (see this kit's).")

    if args.merge_settings:
        print("\nActivating hooks (--merge-settings):")
        for line in _apply_settings_merge(project, args.dry_run):
            print(line)
    else:
        print("\nNext step - activate the hooks. Merge this into your")
        print(f"  {project / '.claude' / 'settings.json'}")
        print("  (or re-run with --merge-settings to do this automatically)\n")
        print(json.dumps(SETTINGS_SNIPPET, indent=2))

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
