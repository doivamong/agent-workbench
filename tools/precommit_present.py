#!/usr/bin/env python3
"""Recovery-first wrapper for a pre-commit gate (stdlib-only).

Wraps a gate command, runs it, and re-emits its exit code **unchanged**. The only thing it
adds is a short, plain-language note — printed **only when the gate fails** — so a refused
commit reads as "here is what to do" instead of a raw traceback. This matters for the kit's
target user: someone driving the agent in natural language, for whom a wall of pytest output
is noise, not a signal.

What it must never do (and is tested for):

  * Turn a red gate green. A passing gate (exit 0) passes through untouched and silently; a
    failing gate keeps its exact non-zero code. The note is presentation, never a verdict.
  * Fail OPEN. If the wrapper itself cannot run the gate (bad command, launch error, no
    command at all), it exits NON-ZERO — it refuses the commit rather than letting it through
    on a wrapper bug. (This is why it is deliberately NOT wrapped in hook_logger.hook_main,
    which exits 0 on an unhandled exception — that would convert a wrapper crash into a green
    commit.)

Usage in .pre-commit-config.yaml:

    entry: python tools/precommit_present.py -- python tools/affected_tests.py --diff --run

Everything after ``--`` (or all args if ``--`` is omitted) is the gate command.
"""
import subprocess
import sys

# Exit code for an internal wrapper failure — distinct, non-zero, so it is never confused
# with the gate's own codes and never mistaken for success (fail CLOSED).
WRAPPER_ERROR = 3


def _recovery_note(cmd: list[str]) -> str:
    """A short, plain-language note shown only when the wrapped gate fails."""
    return (
        "\n"
        "----------------------------------------------------------------------\n"
        "A commit gate stopped this commit. This is a guard doing its job, not\n"
        "your mistake. You do not need to read the output above line by line.\n"
        "  - Ask the agent to fix the cause (say \"the commit was refused\").\n"
        "  - Nothing was committed; your changes are safe and still staged.\n"
        f"  - Gate that failed: {' '.join(cmd)}\n"
        "----------------------------------------------------------------------\n"
    )


def main(argv: list[str]) -> int:
    """Run the gate in ``argv`` (after an optional leading ``--``); return its exit code.

    Returns WRAPPER_ERROR (non-zero) if there is no command or the gate cannot be launched.
    """
    cmd = argv[1:] if argv and argv[0] == "--" else list(argv)
    if not cmd:
        sys.stderr.write("precommit_present: no gate command given (nothing to run).\n")
        return WRAPPER_ERROR

    try:
        rc = subprocess.call(cmd)
    except Exception as exc:  # noqa: BLE001 — any launch failure must fail CLOSED, not open
        sys.stderr.write(
            f"precommit_present: could not run the gate {cmd!r}: {exc}\n"
            "Refusing the commit (the wrapper failed; it will not pass a commit through "
            "on its own error).\n"
        )
        return WRAPPER_ERROR

    if rc != 0:
        sys.stderr.write(_recovery_note(cmd))
    return rc


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
