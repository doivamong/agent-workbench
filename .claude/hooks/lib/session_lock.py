"""session_lock.py — per-worktree session lock: write, read, liveness, the warn decision.

`concurrent_session_guard.py` (SessionStart) writes a small lock recording the live agent
process for *this* checkout; the next session that starts in the same checkout reads it and,
if a DIFFERENT session is still alive, surfaces a warning. `session_end.py` removes the lock
on teardown. The path, schema, liveness check, and warn rule live here so the writer, the
reader, and the cleanup can never drift apart.

Why this matters: two agent/Claude sessions on one checkout race the shared git index/HEAD —
a commit hook in a linked worktree can leak `GIT_DIR` and flip `core.bare` / overwrite
`user.*` in the SHARED `.git/config`. The rule "one session per working tree" is in CLAUDE.md;
this is the seatbelt that *notices* when it's broken.

HONEST LIMITS — this is a SEATBELT, not a lock. It CANNOT prevent a second session, only
warn after one has already attached. It does NOT:
  * serialize or block anything — `assess()` only ever returns advisory text;
  * guarantee detection — the recorded pid is the guard's PARENT process (the agent/CLI that
    spawned the hook). If your platform spawns hooks through an intermediate shell, that pid
    may be transient, so by the next session it reads as dead and the check degrades to
    FAIL-OPEN: no warning. It fails toward silence (a missed warning), never a false alarm;
  * detect a session on a DIFFERENT checkout — the lock is per-worktree by design (that's the
    safe case; separate `git worktree`s are the remedy we point users to).

Stdlib only (kit golden rule #2). The liveness check is cross-platform and never raises.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

# Env override used by tests/examples to relocate the lock off the real `.claude/.logs/`.
_PATH_ENV = "SESSION_LOCK_PATH"
_LOCK_REL = Path(".claude") / ".logs" / "session_lock.json"


def lock_path(cwd) -> Path:
    """Where the per-worktree lock lives (project-local, gitignored). `SESSION_LOCK_PATH` overrides."""
    override = os.environ.get(_PATH_ENV)
    if override:
        return Path(override)
    return Path(cwd) / _LOCK_REL


def write_lock(path: Path, data: dict) -> None:
    """Persist the lock, creating the parent dir. The caller handles failures (fail-open)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def read_lock(path) -> "dict | None":
    """Load the lock, or None if missing / unreadable / malformed.

    Returns None for anything that isn't a JSON object so a corrupt or hand-edited lock can
    never crash the guard (a malformed lock degrades to "no existing session" → no warning)."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def pid_is_alive(pid) -> bool:
    """Best-effort, cross-platform, stdlib-only liveness check. NEVER raises; FAILS OPEN.

    "Fails open" means: on any uncertainty (can't query, odd error, bad input) it returns
    False — assume-not-alive — so a flaky check produces a missed warning, never a false alarm.
    """
    if not isinstance(pid, int) or isinstance(pid, bool) or pid <= 0:
        return False
    if os.name == "nt":
        return _alive_windows(pid)
    return _alive_posix(pid)


def _alive_posix(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False              # no such process
    except PermissionError:
        return True               # exists, owned by another user
    except OSError:
        return False              # fail open: uncertain -> not alive -> no false alarm
    return True


def _alive_windows(pid: int) -> bool:
    # NOTE: do NOT use os.kill(pid, 0) on Windows — for a non-CTRL signal it calls
    # TerminateProcess and would KILL the process. Query a handle via ctypes (stdlib) instead;
    # no `tasklist` subprocess. Any failure -> fail open (assume dead).
    try:
        import ctypes
        from ctypes import wintypes

        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        STILL_ACTIVE = 259
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not handle:
            return False          # can't open (gone, or access-denied) -> assume dead
        try:
            code = wintypes.DWORD()
            if not kernel32.GetExitCodeProcess(handle, ctypes.byref(code)):
                return False
            return code.value == STILL_ACTIVE
        finally:
            kernel32.CloseHandle(handle)
    except Exception:
        return False              # fail open


def format_warning(existing: dict) -> str:
    """The advisory text shown to the new session when a different live session holds the lock."""
    pid = existing.get("pid", "?")
    started = existing.get("started_at", "?")
    return (
        f"⚠ Another session (pid {pid}, started {started}) appears active in this worktree — "
        "running two sessions on one checkout races the git index/HEAD and can corrupt shared "
        "state (a commit hook can leak GIT_DIR and flip core.bare / overwrite user.* in the "
        "shared .git/config). Use a separate `git worktree` per session. "
        "(Advisory only — this guard warns, it does not block.)"
    )


def assess(existing, my_pid, my_session_id, now_iso, alive_fn=pid_is_alive):
    """Pure decision: given the existing lock (or None), return (warning_or_none, new_lock).

    `new_lock` is what THIS session should write (always — start refreshes the lock to point at
    us). `warning` is advisory text, or None. We warn only when the existing lock names a
    DIFFERENT session that is STILL ALIVE:

      * same `session_id` as ours  -> our own session re-firing (resume/clear/compact) -> quiet;
      * different pid, still alive  -> a genuine second session -> WARN;
      * dead pid / missing / malformed -> stale, silently reclaimed -> quiet.

    `alive_fn` is injected so tests can drive the decision without real processes.
    """
    new_lock = {"pid": my_pid, "started_at": now_iso, "session_id": my_session_id}
    if not existing:
        return None, new_lock

    other_sid = existing.get("session_id")
    if my_session_id and other_sid and other_sid == my_session_id:
        return None, new_lock     # same session re-firing — never warn

    other_pid = existing.get("pid")
    if isinstance(other_pid, int) and not isinstance(other_pid, bool) \
            and other_pid != my_pid and alive_fn(other_pid):
        return format_warning(existing), new_lock
    return None, new_lock


def release_lock(path, my_pid, my_session_id) -> bool:
    """Remove the lock on session end, but only if it is OURS.

    Match by `session_id` when both sides have one (robust across pid quirks), else by pid. A
    lock owned by another live session is left untouched so we never delete its warning signal.
    Returns True if a lock was removed. Never raises (best-effort teardown)."""
    try:
        existing = read_lock(path)
        if not existing:
            return False
        owned = False
        other_sid = existing.get("session_id")
        if my_session_id and other_sid:
            owned = other_sid == my_session_id
        else:
            owned = existing.get("pid") == my_pid
        if owned:
            Path(path).unlink()
            return True
    except Exception:
        pass
    return False
