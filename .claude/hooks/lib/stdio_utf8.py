"""stdio_utf8.py — make a hook's standard streams UTF-8 and pythonw-safe.

Claude Code hooks talk JSON over stdin/stdout. Two Windows realities bite if you don't
prepare the streams first:

- The default console encoding is often cp1252, so the moment a hook prints a non-ASCII
  character (a smart quote, an arrow, an emoji inside injected context) it raises
  ``UnicodeEncodeError`` and the hook crashes.
- Under ``pythonw.exe`` there is no console, so ``sys.stdout`` / ``sys.stdin`` can be
  ``None`` — and ``None`` has no ``.reconfigure``.

``ensure_utf8_io()`` switches the streams to UTF-8 when they support it and quietly does
nothing when they don't (``None`` under pythonw, or a stream without ``reconfigure`` on an
older Python). It is the single shared copy of an idiom that used to sit, duplicated, at
the top of every hook — import it instead of repeating the four lines.

Honest limit: this only fixes ENCODING. It does not create a console where pythonw removed
one; if a stream is ``None`` the hook's output simply has nowhere to go — that is the
caller's contract to handle, not this helper's.
"""
import sys


def ensure_utf8_io() -> None:
    """Reconfigure stdout and stdin to UTF-8 where the streams support it; a no-op otherwise.

    Idempotent and safe to call unconditionally at hook start-up: a missing or ``None``
    stream (pythonw) or a stream without ``reconfigure`` (older Python) is skipped rather
    than raising.
    """
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stdin, "reconfigure"):
        sys.stdin.reconfigure(encoding="utf-8")
