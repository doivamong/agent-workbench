"""tools/doctor.py — the verifier factored out of install.py so it can run STANDALONE
inside an adopter project (it is copied in via COPY_MAP). These tests import ``doctor``
directly (never through ``install``) to prove it stands alone, and cover the contract that
matters for a non-programmer who can't read the output: deny-proof keys on STDOUT (not exit
code), the doctor is read-only, and it FAILS LOUD on every silent-off landmine.

``test_install_doctor.py`` separately proves ``install.py --doctor`` still works (regression),
since install.py now imports run_doctor from here.
"""
import json

import doctor
import install


# --------------------------------------------------------------------------- #
# Standalone happy path + CLI
# --------------------------------------------------------------------------- #
def test_doctor_standalone_passes_after_install(tmp_path, capsys):
    install.main([str(tmp_path), "--merge-settings"])
    capsys.readouterr()
    rc = doctor.run_doctor(tmp_path)
    out = capsys.readouterr().out
    assert rc == 0
    assert "PROVEN [block_dangerous.py]" in out
    assert doctor.DOCTOR_BLOCK_LIMIT in out
    assert doctor.DOCTOR_RESTART_NOTE in out
    assert doctor.DOCTOR_LEGEND in out


def test_doctor_cli_main_returns_run_doctor_code(tmp_path):
    install.main([str(tmp_path), "--merge-settings"])
    assert doctor.main([str(tmp_path)]) == 0          # wired → pass
    assert doctor.main([str(tmp_path / "nope")]) == 1  # not a dir → fail


def test_doctor_cli_defaults_to_cwd(tmp_path, monkeypatch):
    """`python tools/doctor.py` with no arg checks the current directory — the in-adopter
    invocation a non-programmer will actually type."""
    install.main([str(tmp_path), "--merge-settings"])
    monkeypatch.chdir(tmp_path)
    assert doctor.main([]) == 0


# --------------------------------------------------------------------------- #
# The load-bearing contract: deny decision lives in STDOUT, never the exit code
# --------------------------------------------------------------------------- #
def test_is_deny_keys_on_stdout_permission_decision():
    deny = json.dumps({"hookSpecificOutput": {"permissionDecision": "deny"}})
    allow = json.dumps({"hookSpecificOutput": {"permissionDecision": "allow"}})
    assert doctor._is_deny(deny) is True
    assert doctor._is_deny(allow) is False
    assert doctor._is_deny("") is False            # safe command prints nothing
    assert doctor._is_deny("not json") is False    # unparseable → not a deny
    assert doctor._is_deny(None) is False


# --------------------------------------------------------------------------- #
# FAIL-LOUD landmines (each must return non-zero, not a silent pass)
# --------------------------------------------------------------------------- #
def test_doctor_fails_without_settings(tmp_path, capsys):
    assert doctor.run_doctor(tmp_path) == 1
    assert "not wired" in capsys.readouterr().out


def test_doctor_fails_when_no_kit_hooks(tmp_path, capsys):
    (tmp_path / ".claude").mkdir()
    (tmp_path / doctor.SETTINGS_REL).write_text('{"hooks": {}}', encoding="utf-8")
    assert doctor.run_doctor(tmp_path) == 1
    assert "no agent-workbench hooks" in capsys.readouterr().out


def test_doctor_fails_on_bogus_interpreter(tmp_path, capsys):
    install.main([str(tmp_path), "--merge-settings"])
    sp = tmp_path / doctor.SETTINGS_REL
    data = json.loads(sp.read_text(encoding="utf-8"))
    for g in data["hooks"]["PreToolUse"]:
        for h in g["hooks"]:
            if "block_dangerous.py" in h["command"]:
                h["command"] = ('awb_no_such_interp_xyz '
                                '"$CLAUDE_PROJECT_DIR/.claude/hooks/scripts/block_dangerous.py"')
    sp.write_text(json.dumps(data), encoding="utf-8")
    capsys.readouterr()
    assert doctor.run_doctor(tmp_path) == 1
    assert "silently OFF" in capsys.readouterr().out


def test_doctor_fails_when_block_dangerous_script_missing(tmp_path, capsys):
    install.main([str(tmp_path), "--merge-settings"])
    (tmp_path / ".claude/hooks/scripts/block_dangerous.py").unlink()
    capsys.readouterr()
    assert doctor.run_doctor(tmp_path) == 1
    assert "missing" in capsys.readouterr().out


# --------------------------------------------------------------------------- #
# Read-only: the doctor writes NOTHING into the project (no settings, no __pycache__)
# --------------------------------------------------------------------------- #
def test_doctor_is_read_only(tmp_path):
    install.main([str(tmp_path), "--merge-settings"])
    before = {p for p in tmp_path.rglob("*") if p.is_file()}
    doctor.run_doctor(tmp_path)
    after = {p for p in tmp_path.rglob("*") if p.is_file()}
    assert before == after
    assert not list(tmp_path.rglob("__pycache__"))


# --------------------------------------------------------------------------- #
# Drift guard: the standalone SETTINGS_REL must equal install.py's (see doctor docstring)
# --------------------------------------------------------------------------- #
def test_settings_rel_parity_with_install():
    assert doctor.SETTINGS_REL == install.SETTINGS_REL == ".claude/settings.json"
