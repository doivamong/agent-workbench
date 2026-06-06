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
    python install.py /path/to/your/project --doctor           # verify the wired hooks actually run

The hooks are wired with a per-machine interpreter (``python``/``py``/``python3``, resolved at
install time) so a bare ``python`` that doesn't resolve on Windows isn't silently wired as a
no-op. After installing, ``--doctor`` proves each guard runs and that dangerous-command blocking
is actually ON — it FAILS LOUD if a guard is silently off.

It writes an installer-manifest (``.claude/installer-manifest.json``, git-ignored in the
target) recording what it copied, so ``uninstall.py`` can cleanly reverse the install —
keeping any file you edited. Run ``python uninstall.py /path/to/your/project`` (dry-run by
default; ``--yes`` to apply).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
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

# The hooks the installer wires, as (script path relative to the target project,
# optional matcher). One source of truth for build_settings_snippet — the interpreter
# token is substituted per-machine by _resolve_hook_interpreter (so a bare `python`
# that doesn't resolve on Windows isn't silently wired as a no-op).
_HOOK_WIRING = [
    ("PreToolUse", ".claude/hooks/scripts/block_dangerous.py", "Bash"),
    ("UserPromptSubmit", ".claude/hooks/prompt-refiner-inject.py", None),
    ("PostToolUse", ".claude/hooks/scripts/post_edit_simplify.py", "Edit|Write"),
    ("PostToolUse", ".claude/hooks/scripts/context_tracker.py", None),
    ("PreCompact", ".claude/hooks/scripts/precompact_backup.py", None),
    ("SessionStart", ".claude/hooks/scripts/compact_restore.py", "compact"),
    ("SessionStart", ".claude/hooks/scripts/session_start.py", "startup|resume|clear"),
    # skill_routing_inject: no matcher → every SessionStart; derived from the (also-copied)
    # skill-registry.md and fails open if missing, so it's safe to wire for any adopter.
    ("SessionStart", ".claude/hooks/scripts/skill_routing_inject.py", None),
    ("SessionEnd", ".claude/hooks/scripts/session_end.py", None),
]


def hook_command(interp: str, rel: str) -> str:
    """The wired command string for one hook: ``<interp> "$CLAUDE_PROJECT_DIR/<rel>"``.

    ``interp`` is a launcher token (``python``/``py``/``python3``) or a quoted absolute
    path. ``$CLAUDE_PROJECT_DIR`` is expanded by Claude Code's shell at hook time."""
    return f'{interp} "$CLAUDE_PROJECT_DIR/{rel}"'


def build_settings_snippet(interp: str = "python") -> dict:
    """Build the settings.json ``hooks`` block, prefixing every command with ``interp``.

    The default ``"python"`` reproduces the historical snippet byte-for-byte (so a machine
    where ``python`` resolves sees no change). _resolve_hook_interpreter picks a working
    token per-machine; the SAME built snippet must feed both the settings merge and the
    manifest's hooks_added (see install path), or uninstall.py's strip-set diverges.
    """
    hooks: dict = {}
    for event, rel, matcher in _HOOK_WIRING:
        entry = {"type": "command", "command": hook_command(interp, rel), "timeout": 10}
        group = {"hooks": [entry]}
        if matcher is not None:
            group = {"matcher": matcher, "hooks": [entry]}
        hooks.setdefault(event, []).append(group)
    return {"hooks": hooks}


SETTINGS_SNIPPET = build_settings_snippet("python")

# Candidate launcher tokens, in preference order. A NAME (not an absolute path) is
# preferred so a possibly-committed settings.json stays portable and machine-path-free.
_INTERPRETER_CANDIDATES = ["python", "py", "python3"]
_PROBE = "import sys; print('AWBPY', sys.version_info[0], sys.version_info[1])"


def _probe_interpreter(argv: list[str]) -> bool:
    """True if ``argv`` launches and reports Python >= 3.10. Never hangs or raises.

    Requires the probe to PRINT its sentinel: a Windows Store-alias stub can exit 0 with
    only a banner, so exit code alone is not trusted. A timeout / OSError → not OK. Runs
    ``-c`` (no project side effects), so it is safe to use as the doctor's launch check.
    """
    try:
        proc = subprocess.run(list(argv) + ["-c", _PROBE], capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=5)
    except (OSError, subprocess.TimeoutExpired, ValueError):
        return False
    if proc.returncode != 0:
        return False
    for line in (proc.stdout or "").splitlines():
        parts = line.split()
        if len(parts) == 3 and parts[0] == "AWBPY":
            try:
                return (int(parts[1]), int(parts[2])) >= (3, 10)
            except ValueError:
                return False
    return False


def _interpreter_ok(token: str) -> bool:
    """True if the launcher ``token`` runs Python >= 3.10 (resolver candidate check)."""
    return _probe_interpreter([token])


def _resolve_hook_interpreter() -> tuple[str, str | None]:
    """Pick the interpreter token to prefix wired hook commands with on THIS machine.

    Returns (token, warning). Prefers a launcher NAME that actually runs Python >= 3.10
    so a bare ``python`` that resolves to nothing (Windows Store alias / py-only box) is
    not silently wired as a no-op guard. Only if no name works does it fall back to the
    absolute ``sys.executable`` (quoted), with a warning that the path is machine-specific.

    Honest limit: this probes the INSTALLER's PATH, which is usually but not always the
    PATH Claude Code's hook process sees — run ``install.py <project> --doctor`` afterwards
    to confirm the wired command actually runs.
    """
    for token in _INTERPRETER_CANDIDATES:
        if _interpreter_ok(token):
            return token, None
    exe = sys.executable
    quoted = f'"{exe}"' if " " in exe else exe
    warn = ("none of python/py/python3 resolved to Python >= 3.10 on PATH; wiring hooks "
            f"with the absolute interpreter path {exe}. This path is machine-specific — "
            "re-run install if Python moves, and prefer not to commit this settings.json.")
    return quoted, warn

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


def _hook_script_key(command: str | None) -> str | None:
    """Identity of a wired hook, independent of the interpreter token.

    A hook command is ``<interp> "$CLAUDE_PROJECT_DIR/<rel>"``; the script <rel> is the
    identity. Keying on this (not the whole command) means re-installing with a different
    interpreter (``python`` → ``py``) REPLACES the command in place instead of wiring a
    duplicate hook that would fire twice per event.
    """
    if not command:
        return command
    m = re.search(r'\$CLAUDE_PROJECT_DIR/([^"\s]+)', command)
    return m.group(1) if m else command


def _merge_settings(existing: dict, snippet: dict) -> dict:
    """Deep-merge the snippet's ``hooks`` block into an existing settings dict.

    Idempotent and interpreter-stable: a hook is identified by its script path
    (_hook_script_key), so re-running the installer — even with a different interpreter
    token — updates the command in place rather than duplicating it. Other keys in
    ``existing`` are preserved.
    """
    result = json.loads(json.dumps(existing))  # deep copy, never mutate the input
    hooks = result.setdefault("hooks", {})
    for event, groups in snippet.get("hooks", {}).items():
        existing_groups = hooks.setdefault(event, [])
        # Index existing hooks by script identity so a re-install replaces in place.
        existing_by_key: dict = {}
        for g in existing_groups:
            for h in g.get("hooks", []):
                existing_by_key.setdefault(_hook_script_key(h.get("command")), h)
        for group in groups:
            unmatched = []
            for h in group.get("hooks", []):
                key = _hook_script_key(h.get("command"))
                if key in existing_by_key:
                    # Already wired (any interpreter) → update the command in place.
                    existing_by_key[key]["command"] = h.get("command")
                else:
                    unmatched.append(h)
            if unmatched:
                new_group = dict(group)
                new_group["hooks"] = unmatched
                existing_groups.append(new_group)
    return result


def _apply_settings_merge(project: Path, dry: bool, snippet: dict = SETTINGS_SNIPPET) -> list[str]:
    """Merge ``snippet`` into the project's .claude/settings.json. Fail-soft.

    ``snippet`` MUST be the same resolved snippet recorded in the manifest's hooks_added
    (see the install path), or uninstall.py's strip-set won't match what was written.
    """
    settings = project / ".claude" / "settings.json"
    existing: dict = {}
    if settings.exists():
        try:
            existing = json.loads(settings.read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            return [f"  could not read {settings} ({e}); printing the snippet instead."]
    merged = _merge_settings(existing, snippet)
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


# --------------------------------------------------------------------------- #
# Doctor: prove the wired guards actually RUN on this machine (opt-1)
# --------------------------------------------------------------------------- #
# Named so tests can assert the honesty wording by reference. block_dangerous is a
# seatbelt, not a vault; the doctor proves the script RUNS here, not that a live Claude
# Code session has loaded it.
DOCTOR_BLOCK_LIMIT = ("catches common destructive commands, NOT a security boundary — "
                      "a determined command can still evade it")
DOCTOR_RESTART_NOTE = (
    "This proves the hook scripts run on THIS machine. It does NOT prove your running "
    "Claude Code session has loaded them — if you just installed or re-wired, restart "
    "Claude Code (or start a new session) so the hooks take effect. The installer's PATH "
    "may also differ from Claude Code's.")
DOCTOR_LEGEND = (
    "PROVEN = the guard was run here and behaved correctly; INSTALLED = the script is "
    "wired and its interpreter runs, but its behaviour was not exercised.")

_DANGER_PAYLOAD = json.dumps({"tool_name": "Bash", "tool_input": {"command": "rm -rf /"}})
_SAFE_PAYLOAD = json.dumps({"tool_name": "Bash", "tool_input": {"command": "echo hi"}})


def _interp_argv(interp: str) -> list[str]:
    """Split an interpreter token into argv. A quoted absolute path → one arg; a bare
    launcher name (python/py/python3) → one arg. We control the snippet format, so this
    stays deterministic — no shlex, which would mangle Windows backslashes."""
    interp = interp.strip()
    if len(interp) >= 2 and interp[0] == '"' and interp[-1] == '"':
        return [interp[1:-1]]
    return interp.split()


def _parse_hook_command(command: str, project: Path):
    """Split a wired hook command into (interp_argv, rel, script_path), or None.

    The command is ``<interp> "$CLAUDE_PROJECT_DIR/<rel>"``. The doctor runs the script
    directly, so NO shell expands ``$CLAUDE_PROJECT_DIR`` — we substitute it here (in
    Python), and build the path with pathlib from the project root + the posix relpath.
    """
    m = re.search(r'"?\$CLAUDE_PROJECT_DIR/([^"\s]+)"?\s*$', command.strip())
    if not m:
        return None
    rel = m.group(1)
    interp = command[:m.start()].strip()
    if not interp:
        return None
    return _interp_argv(interp), rel, project / rel


def _run_hook(interp_argv, script_path, payload, env):
    """Run a hook script with ``payload`` on stdin; return (stdout, launched). Never
    raises or hangs. launched=False only when the interpreter binary can't be started."""
    try:
        proc = subprocess.run(interp_argv + [str(script_path)],
                              input=payload, capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=10, env=env)
        return proc.stdout, True
    except (OSError, subprocess.TimeoutExpired, ValueError):
        return "", False


def _is_deny(stdout: str) -> bool:
    """True iff stdout is the PreToolUse deny JSON. block_dangerous exits 0 for BOTH deny
    and safe, so the decision lives in stdout, never the return code; a safe command prints
    nothing, so empty/unparseable stdout is 'no deny'."""
    stdout = (stdout or "").strip()
    if not stdout:
        return False
    try:
        obj = json.loads(stdout)
    except ValueError:
        return False
    return obj.get("hookSpecificOutput", {}).get("permissionDecision") == "deny"


def _doctor_env(project: Path, tmpdir: str) -> dict:
    """Child env for hook probes: point CLAUDE_PROJECT_DIR at the project (the scripts read
    it via os.environ), silence crash logging, and neutralise any project dangerous-patterns
    file so a project rule can't make the safe-payload check flap."""
    empty = Path(tmpdir) / "empty-patterns.json"
    empty.write_text("[]", encoding="utf-8")
    # PYTHONDONTWRITEBYTECODE: running block_dangerous imports hook_logger from the project,
    # which would otherwise drop __pycache__ into the project tree — keep the doctor read-only.
    return {**os.environ, "CLAUDE_PROJECT_DIR": str(project),
            "HOOK_LOGGING": "0", "BLOCK_DANGEROUS_PATTERNS": str(empty),
            "PYTHONDONTWRITEBYTECODE": "1"}


def _is_abs_interp(interp_argv) -> bool:
    return bool(interp_argv) and (interp_argv[0].endswith(".exe")
                                  or "/" in interp_argv[0] or "\\" in interp_argv[0])


def run_doctor(project: Path) -> int:
    """Verify the wired agent-workbench hooks actually run here. Read-only (writes nothing
    into the project). Returns 0 if every check passed, non-zero otherwise — it FAILS LOUD,
    because it is the verifier, not a fail-open guard."""
    settings_path = project / SETTINGS_REL
    print(f"Doctor — checking agent-workbench guards in {project}\n")
    if not settings_path.is_file():
        print("  FAIL: no .claude/settings.json — the hooks are not wired.")
        print("  Fix: run  python install.py <project> --merge-settings")
        return 1
    try:
        settings = json.loads(settings_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        print(f"  FAIL: cannot read {settings_path} ({e}).")
        return 1
    commands = [h.get("command")
                for groups in (settings.get("hooks") or {}).values()
                for g in groups
                for h in g.get("hooks", [])
                if h.get("command")]
    kit_cmds = [c for c in commands if "$CLAUDE_PROJECT_DIR" in c and "/.claude/hooks/" in c]
    if not kit_cmds:
        print("  FAIL: no agent-workbench hooks are wired in settings.json.")
        print("  Fix: run  python install.py <project> --merge-settings")
        return 1

    failures = 0
    with tempfile.TemporaryDirectory() as tmp:
        env = _doctor_env(project, tmp)
        for cmd in kit_cmds:
            parsed = _parse_hook_command(cmd, project)
            if parsed is None:
                print(f"  FAIL: cannot parse a wired command: {cmd}")
                failures += 1
                continue
            interp_argv, rel, script_path = parsed
            name = Path(rel).name
            if not script_path.is_file():
                print(f"  FAIL [{name}]: the wired script is missing at {rel}.")
                print("        Fix: re-run install (the hook file was not copied).")
                failures += 1
                continue
            # Probe the interpreter with `-c` (no side effects) rather than running the
            # hook script itself — most hooks write telemetry/state, so running them would
            # make the doctor non-read-only. The silent-off landmine is the interpreter
            # token not resolving, which this catches without firing the hook.
            if not _probe_interpreter(interp_argv):
                print(f"  FAIL [{name}]: the interpreter '{' '.join(interp_argv)}' did not "
                      "run — this guard is silently OFF on this machine.")
                print("        Fix: run  python install.py <project> --merge-settings  "
                      "(it re-detects a working Python).")
                failures += 1
                continue
            abs_note = "  (absolute interpreter path — machine-specific)" if _is_abs_interp(interp_argv) else ""
            if name == "block_dangerous.py":
                d_out, _ = _run_hook(interp_argv, script_path, _DANGER_PAYLOAD, env)
                s_out, _ = _run_hook(interp_argv, script_path, _SAFE_PAYLOAD, env)
                if _is_deny(d_out) and not _is_deny(s_out):
                    print(f"  PROVEN [{name}]: dangerous-command block is ON — "
                          f"{DOCTOR_BLOCK_LIMIT}.{abs_note}")
                else:
                    print(f"  FAIL [{name}]: did not block a known-dangerous command (or "
                          "blocked a safe one) — the seatbelt is not working.")
                    failures += 1
            else:
                print(f"  INSTALLED [{name}]: wired and its interpreter runs.{abs_note}")

    print(f"\n  {DOCTOR_LEGEND}")
    print(f"  NOTE: {DOCTOR_RESTART_NOTE}")
    if failures:
        print(f"\nDoctor: {failures} guard(s) FAILED — they are not protecting you yet. "
              "See the fixes above.")
        return 1
    print("\nDoctor: all wired guards passed.")
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
    ap.add_argument("--doctor", action="store_true",
                    help="Verify the wired hooks actually run on this machine (read-only), then exit. "
                         "Proves dangerous-command blocking is ON and the hook interpreter resolves.")
    args = ap.parse_args(argv)

    project = args.target.resolve()
    if not project.is_dir():
        print(f"Target is not a directory: {project}", file=sys.stderr)
        return 1
    # --doctor is a read-only diagnostic, so it is exempt from the install-into-itself
    # guard: `python install.py . --doctor` is a valid way to verify this repo's own wiring.
    if args.doctor:
        return run_doctor(project)
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
        # Resolve a working interpreter ONCE and build the snippet from it, so the merge
        # and the manifest's hooks_added record the exact same command strings (uninstall
        # symmetry), and the wired command actually runs on this machine.
        interp, interp_warn = _resolve_hook_interpreter()
        snippet = build_settings_snippet(interp)
        if interp_warn:
            print(f"  WARN {interp_warn}")
        if args.merge_settings:
            settings_created = not (project / SETTINGS_REL).exists()
            print("\nActivating hooks (--merge-settings):")
            for line in _apply_settings_merge(project, args.dry_run, snippet):
                print(line)
            settings_info = {"created": settings_created, "hooks_added": settings_commands(snippet)}
        else:
            print("\nNext step - activate the hooks. Merge this into your")
            print(f"  {project / '.claude' / 'settings.json'}")
            print("  (or re-run with --merge-settings to do this automatically)\n")
            print(json.dumps(snippet, indent=2))
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
