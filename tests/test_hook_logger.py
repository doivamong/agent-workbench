"""Tests for hook_logger — the fail-open wrapper every hook relies on.

The audit flagged this as half-covered: the exception-swallowing path and the
crash-log write were untested, yet they are the whole point of the wrapper.
"""
import json

import pytest

from hook_logger import hook_main


def test_unexpected_exception_fails_open_and_logs(tmp_path, monkeypatch):
    monkeypatch.setenv("HOOK_LOG_DIR", str(tmp_path))

    @hook_main("boom-hook")
    def boom():
        raise RuntimeError("kaboom")

    with pytest.raises(SystemExit) as ei:
        boom()
    assert ei.value.code == 0  # fail-open: the session is not blocked

    log = tmp_path / "hook-crashes.jsonl"
    assert log.is_file()
    record = json.loads(log.read_text(encoding="utf-8").splitlines()[-1])
    assert record["hook"] == "boom-hook"
    assert "kaboom" in record["error"]
    assert "RuntimeError" in record["traceback"]


def test_intentional_systemexit_passes_through(tmp_path, monkeypatch):
    monkeypatch.setenv("HOOK_LOG_DIR", str(tmp_path))

    @hook_main("exiting-hook")
    def exiting():
        raise SystemExit(3)

    with pytest.raises(SystemExit) as ei:
        exiting()
    assert ei.value.code == 3  # honored, not swallowed
    assert not (tmp_path / "hook-crashes.jsonl").exists()  # and not logged as a crash


def test_logging_can_be_disabled(tmp_path, monkeypatch):
    monkeypatch.setenv("HOOK_LOG_DIR", str(tmp_path))
    monkeypatch.setenv("HOOK_LOGGING", "0")

    @hook_main("quiet-hook")
    def quiet():
        raise ValueError("shh")

    with pytest.raises(SystemExit) as ei:
        quiet()
    assert ei.value.code == 0          # still fails open
    assert not (tmp_path / "hook-crashes.jsonl").exists()  # but writes no log


def test_successful_hook_returns_value(tmp_path, monkeypatch):
    monkeypatch.setenv("HOOK_LOG_DIR", str(tmp_path))

    @hook_main("happy-hook")
    def happy():
        return "ok"

    assert happy() == "ok"
