#!/usr/bin/env python3
"""doctor.py — verify the wired agent-workbench guards actually RUN on this machine.

This is the SAME verification `install.py --doctor` performs, factored into a self-contained
module so it can travel **into an adopter project**: `install.py` copies `tools/doctor.py`
(COPY_MAP group `tools`) into the project, so after installing you can re-check your guards
from inside your own repo with:

    python tools/doctor.py            # check the current project (default '.')
    python tools/doctor.py /path/to/project

without going back to the kit folder. `install.py` imports `run_doctor` (and the helpers
below) FROM this module, so there is a single source of truth for the logic — and this file
must stay **stdlib-only and standalone** (in an adopter it runs alone, with no `install.py`
beside it). That is also why `SETTINGS_REL` is re-declared here instead of imported from
`install.py`: a copied-in file cannot depend on the kit; `install.py` keeps its own copy and
a test asserts the two never drift.

What it proves (and what it does NOT):
  - PROVEN  — the guard was actually exercised here and behaved correctly (today only
              `block_dangerous.py`: it really denied a dangerous command and allowed a safe one).
  - INSTALLED — the script is wired and its interpreter runs, but its behaviour was not tested.
  - It is READ-ONLY: it writes nothing into the project (no settings, no __pycache__).
  - It proves the scripts run on THIS machine — NOT that a live Claude Code session has loaded
    them. Restart Claude Code after installing/re-wiring. It FAILS LOUD: it is the verifier,
    not a fail-open guard.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

# Print UTF-8 safely even on a legacy Windows console (cp1252/cp437) or when stdout is
# redirected — otherwise a non-ASCII character in our output raises UnicodeEncodeError.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Re-declared standalone (see module docstring): a copied-in adopter file cannot import
# install.py. install.py keeps its own SETTINGS_REL; test_doctor_standalone asserts parity.
SETTINGS_REL = ".claude/settings.json"

# A probe that must PRINT its sentinel: a Windows Store-alias stub can exit 0 with only a
# banner, so exit code alone is not trusted.
_PROBE = "import sys; print('AWBPY', sys.version_info[0], sys.version_info[1])"

# Named so tests can assert the honesty wording by reference. block_dangerous is a seatbelt,
# not a vault; the doctor proves the script RUNS here, not that a live Claude Code session
# has loaded it.
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
    ap = argparse.ArgumentParser(
        description="Verify the wired agent-workbench guards actually run here (read-only). "
                    "Run it from inside the project the kit was installed into.")
    ap.add_argument("target", type=Path, nargs="?", default=Path("."),
                    help="Path to the project to check (default: the current directory).")
    args = ap.parse_args(argv)
    project = args.target.resolve()
    if not project.is_dir():
        print(f"Target is not a directory: {project}", file=sys.stderr)
        return 1
    return run_doctor(project)


if __name__ == "__main__":
    raise SystemExit(main())
