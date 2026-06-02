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

KIT = Path(__file__).resolve().parent

# (source relative to kit, destination relative to target project)
COPY_MAP = [
    (".claude/hooks", ".claude/hooks"),
    (".claude/skills", ".claude/skills"),
    (".claude/rules", ".claude/rules"),
    ("tools/leak_scan.py", "tools/leak_scan.py"),
    ("tools/invariants.py", "tools/invariants.py"),
    ("tools/affected_tests.py", "tools/affected_tests.py"),
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
    }
}

GIT_PRE_COMMIT = """#!/bin/sh
# Installed by agent-workbench. Blocks commits that leak secrets/identifiers.
python tools/leak_scan.py . --fail-on-find || {
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


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Install the kit into a project.")
    ap.add_argument("target", type=Path, help="Path to your project root")
    ap.add_argument("--force", action="store_true", help="Overwrite existing files")
    ap.add_argument("--dry-run", action="store_true", help="Show what would happen")
    ap.add_argument("--with-git-hook", action="store_true", help="Install a git pre-commit leak gate")
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

    print("\nNext step — activate the hooks. Merge this into your")
    print(f"  {project / '.claude' / 'settings.json'}\n")
    print(json.dumps(SETTINGS_SNIPPET, indent=2))
    print("\nThen open the project in Claude Code. Dangerous Bash commands will be")
    print("blocked and vague prompts will be flagged. See .claude/skills/README.md to")
    print("start using the skill system, and memory/README.md for the memory system.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
