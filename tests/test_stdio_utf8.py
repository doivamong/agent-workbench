"""ensure_utf8_io() — the shared stdio guard every hook calls at start-up.

It must switch the standard streams to UTF-8 when it can and, crucially, never raise:
under pythonw the streams can be ``None``, and on an older Python they may lack
``reconfigure``. A stdio tweak that crashed would defeat the fail-open contract of the
hooks that depend on it.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / ".claude" / "hooks" / "lib"))
from stdio_utf8 import ensure_utf8_io  # noqa: E402


class _FakeStream:
    """A stand-in stream that records every reconfigure(encoding=...) it receives."""

    def __init__(self):
        self.calls = []

    def reconfigure(self, *, encoding=None):
        self.calls.append(encoding)


def test_reconfigures_both_streams_to_utf8(monkeypatch):
    out, inp = _FakeStream(), _FakeStream()
    monkeypatch.setattr(sys, "stdout", out)
    monkeypatch.setattr(sys, "stdin", inp)
    ensure_utf8_io()
    assert out.calls == ["utf-8"]
    assert inp.calls == ["utf-8"]


def test_no_crash_when_streams_are_none(monkeypatch):
    # pythonw.exe: no console, so sys.stdout / sys.stdin are None
    monkeypatch.setattr(sys, "stdout", None)
    monkeypatch.setattr(sys, "stdin", None)
    ensure_utf8_io()  # must not raise


def test_no_crash_when_stream_lacks_reconfigure(monkeypatch):
    # an older Python (or a redirected non-stream) whose streams have no reconfigure
    monkeypatch.setattr(sys, "stdout", object())
    monkeypatch.setattr(sys, "stdin", object())
    ensure_utf8_io()  # must not raise


def test_idempotent(monkeypatch):
    out, inp = _FakeStream(), _FakeStream()
    monkeypatch.setattr(sys, "stdout", out)
    monkeypatch.setattr(sys, "stdin", inp)
    ensure_utf8_io()
    ensure_utf8_io()
    assert out.calls == ["utf-8", "utf-8"]
    assert inp.calls == ["utf-8", "utf-8"]
