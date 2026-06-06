"""Acceptance tests for the recovery-first gate wrapper.

These are the gate, not nice-to-haves: the wrapper's whole reason to exist is that it must
never convert a red gate to green. So we prove (a) a passing gate passes through silently,
(b) a failing gate keeps its exact non-zero code AND gets the note, (c) a malformed / weird
invocation fails CLOSED, and (d) an unlaunchable gate (internal error) fails CLOSED.
"""
import sys

import precommit_present as pp

_PY = sys.executable


def _exit(code: int) -> list[str]:
    return [_PY, "-c", f"import sys; sys.exit({code})"]


def test_success_passes_through_silently(capsys):
    rc = pp.main(["--", *_exit(0)])
    assert rc == 0
    assert "commit gate" not in capsys.readouterr().err  # no note on the green path


def test_failure_reemits_code_and_adds_note(capsys):
    rc = pp.main(["--", *_exit(1)])
    assert rc == 1
    assert "A commit gate stopped this commit" in capsys.readouterr().err


def test_arbitrary_nonzero_is_preserved(capsys):
    # The gate's exact code passes through — the wrapper is presentation, not a verdict.
    rc = pp.main(["--", *_exit(7)])
    assert rc == 7


def test_works_without_double_dash_separator(capsys):
    assert pp.main(_exit(0)) == 0
    assert pp.main(_exit(2)) == 2


def test_empty_command_fails_closed(capsys):
    # Weird shape: no gate to run → must refuse (non-zero), never silently pass.
    rc = pp.main([])
    assert rc == pp.WRAPPER_ERROR != 0
    assert "no gate command" in capsys.readouterr().err


def test_only_double_dash_fails_closed():
    assert pp.main(["--"]) == pp.WRAPPER_ERROR != 0


def test_unlaunchable_gate_fails_closed(capsys):
    # Internal error: the gate binary does not exist → subprocess raises → fail CLOSED.
    rc = pp.main(["--", "this_binary_does_not_exist_zzz_42", "--flag"])
    assert rc == pp.WRAPPER_ERROR != 0
    assert "could not run the gate" in capsys.readouterr().err


def test_note_names_the_failing_gate(capsys):
    pp.main(["--", *_exit(1)])
    err = capsys.readouterr().err
    assert "Gate that failed" in err and "-c" in err
