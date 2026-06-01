"""hook_logger.py — fail-open wrapper + crash logging for Claude Code hooks.

A hook must NEVER break the user's session. `hook_main()` guarantees that: if the
wrapped hook raises, the error is appended to a JSONL crash log and the process
exits 0 (fail-open) so the host action proceeds as if the hook were absent.

Intentional `sys.exit(code)` calls inside a hook pass through unchanged — only
unexpected exceptions are swallowed.

Env:
    HOOK_LOGGING=0   disable crash logging (fail-open behavior still applies)
    HOOK_LOG_DIR=... override the log directory (default: ~/.claude/.logs)

This is an original, dependency-free implementation.
"""
from __future__ import annotations

import functools
import json
import os
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, TypeVar

F = TypeVar("F", bound=Callable[..., object])


def _log_dir() -> Path:
    return Path(os.environ.get("HOOK_LOG_DIR", Path.home() / ".claude" / ".logs"))


def _log_crash(name: str, exc: BaseException) -> None:
    """Append a crash record. Logging must itself never raise."""
    if os.environ.get("HOOK_LOGGING") == "0":
        return
    try:
        d = _log_dir()
        d.mkdir(parents=True, exist_ok=True)
        record = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "hook": name,
            "error": repr(exc),
            "traceback": traceback.format_exc(),
        }
        with (d / "hook-crashes.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:
        pass  # never let logging break the hook


def hook_main(name: str) -> "Callable[[F], F]":
    """Decorator: wrap a hook entry point with fail-open + crash logging.

    Usage:
        @hook_main("my-hook")
        def main():
            ...        # raise freely; the session is protected
    """

    def decorator(fn: F) -> F:
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            try:
                return fn(*args, **kwargs)
            except SystemExit:
                raise  # intentional exit codes are honored
            except BaseException as exc:  # noqa: BLE001 — fail-open is the point
                _log_crash(name, exc)
                sys.exit(0)

        return wrapper  # type: ignore[return-value]

    return decorator
