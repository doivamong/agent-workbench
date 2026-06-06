"""Tests for install.py's interpreter-robust wiring + the --doctor verifier.

Covers: the snippet builder (default byte-identical, interpreter substitution), the
interpreter resolver (printed-version probe, fallback), interpreter-independent merge
dedup + install/uninstall symmetry across interpreters, and run_doctor (deny-proof on
STDOUT not return code, FAIL paths, read-only, self-guard exemption, honesty wording).

Everything runs against a tmp project so nothing escapes the sandbox.
"""
import json
import shutil
import subprocess

import pytest

import install
import uninstall

requires_git = pytest.mark.skipif(shutil.which("git") is None, reason="git not installed")


def _git(tmp_path, *args):
    subprocess.run(["git", *args], cwd=tmp_path, capture_output=True, text=True, check=True)


def _wired_commands(settings: dict) -> list[str]:
    return [h["command"]
            for groups in settings.get("hooks", {}).values()
            for g in groups
            for h in g.get("hooks", [])
            if "command" in h]


# --------------------------------------------------------------------------- #
# S1: snippet builder
# --------------------------------------------------------------------------- #
def test_default_snippet_is_byte_identical_python():
    """f13 pin: the default build must reproduce the historical 'python' commands exactly,
    so existing settings/uninstall round-trips and tests don't shift under the refactor."""
    expected = [
        'python "$CLAUDE_PROJECT_DIR/.claude/hooks/scripts/block_dangerous.py"',
        'python "$CLAUDE_PROJECT_DIR/.claude/hooks/prompt-refiner-inject.py"',
        'python "$CLAUDE_PROJECT_DIR/.claude/hooks/scripts/post_edit_simplify.py"',
        'python "$CLAUDE_PROJECT_DIR/.claude/hooks/scripts/context_tracker.py"',
        'python "$CLAUDE_PROJECT_DIR/.claude/hooks/scripts/precompact_backup.py"',
        'python "$CLAUDE_PROJECT_DIR/.claude/hooks/scripts/compact_restore.py"',
        'python "$CLAUDE_PROJECT_DIR/.claude/hooks/scripts/session_start.py"',
        'python "$CLAUDE_PROJECT_DIR/.claude/hooks/scripts/skill_routing_inject.py"',
        'python "$CLAUDE_PROJECT_DIR/.claude/hooks/scripts/session_end.py"',
    ]
    assert install.settings_commands(install.SETTINGS_SNIPPET) == expected
    assert install.SETTINGS_SNIPPET == install.build_settings_snippet("python")


def test_snippet_substitutes_interpreter():
    cmds = install.settings_commands(install.build_settings_snippet("py"))
    assert cmds and all(c.startswith('py "$CLAUDE_PROJECT_DIR/') for c in cmds)


# --------------------------------------------------------------------------- #
# S2: interpreter resolver + dedup-by-script-path + symmetry
# --------------------------------------------------------------------------- #
def _completed(stdout, rc=0):
    return subprocess.CompletedProcess(["x"], rc, stdout=stdout, stderr="")


def test_interpreter_ok_requires_printed_version(monkeypatch):
    monkeypatch.setattr(install.subprocess, "run", lambda *a, **k: _completed("AWBPY 3 11\n"))
    assert install._interpreter_ok("any")
    # Store-alias banner: rc 0 but no sentinel printed → rejected.
    monkeypatch.setattr(install.subprocess, "run", lambda *a, **k: _completed("Try the Store\n"))
    assert not install._interpreter_ok("any")
    # too old
    monkeypatch.setattr(install.subprocess, "run", lambda *a, **k: _completed("AWBPY 3 9\n"))
    assert not install._interpreter_ok("any")
    # non-zero rc
    monkeypatch.setattr(install.subprocess, "run", lambda *a, **k: _completed("AWBPY 3 11\n", rc=9))
    assert not install._interpreter_ok("any")


def test_interpreter_ok_survives_timeout_and_missing(monkeypatch):
    def boom(*a, **k):
        raise subprocess.TimeoutExpired(cmd="x", timeout=5)
    monkeypatch.setattr(install.subprocess, "run", boom)
    assert not install._interpreter_ok("any")

    def missing(*a, **k):
        raise OSError("no such file")
    monkeypatch.setattr(install.subprocess, "run", missing)
    assert not install._interpreter_ok("any")


def test_resolver_prefers_first_working_name(monkeypatch):
    monkeypatch.setattr(install, "_interpreter_ok", lambda t: t == "py")
    token, warn = install._resolve_hook_interpreter()
    assert token == "py"
    assert warn is None


def test_resolver_falls_back_to_sys_executable_with_warning(monkeypatch):
    monkeypatch.setattr(install, "_interpreter_ok", lambda t: False)
    token, warn = install._resolve_hook_interpreter()
    assert install.sys.executable in token
    assert warn and "machine-specific" in warn


def test_hook_script_key_is_interpreter_independent():
    base = '"$CLAUDE_PROJECT_DIR/.claude/hooks/scripts/block_dangerous.py"'
    a = install._hook_script_key(f"python {base}")
    b = install._hook_script_key(f"py {base}")
    c = install._hook_script_key(f'"Z:\\no such\\python.exe" {base}')
    assert a == b == c == ".claude/hooks/scripts/block_dangerous.py"


def test_merge_dedup_replaces_in_place_across_interpreters():
    once = install._merge_settings({}, install.build_settings_snippet("python"))
    twice = install._merge_settings(once, install.build_settings_snippet("py"))
    cmds = _wired_commands(twice)
    bd = [c for c in cmds if "block_dangerous.py" in c]
    assert len(bd) == 1 and bd[0].startswith("py ")  # replaced in place, not duplicated


def test_reinstall_changed_interpreter_no_duplicate(tmp_path, monkeypatch):
    monkeypatch.setattr(install, "_resolve_hook_interpreter", lambda: ("python", None))
    install.main([str(tmp_path), "--merge-settings"])
    monkeypatch.setattr(install, "_resolve_hook_interpreter", lambda: ("py", None))
    install.main([str(tmp_path), "--merge-settings"])
    settings = json.loads((tmp_path / install.SETTINGS_REL).read_text(encoding="utf-8"))
    bd = [c for c in _wired_commands(settings) if "block_dangerous.py" in c]
    assert len(bd) == 1 and bd[0].startswith("py ")


@requires_git
def test_cross_interpreter_install_uninstall_git_clean(tmp_path, monkeypatch):
    """f1: a non-default interpreter must keep manifest == merged commands so uninstall
    strips everything and leaves a clean tree."""
    _git(tmp_path, "init")
    _git(tmp_path, "config", "user.email", "x@example.com")
    _git(tmp_path, "config", "user.name", "x")
    monkeypatch.setattr(install, "_resolve_hook_interpreter", lambda: ("py", None))
    install.main([str(tmp_path), "--merge-settings"])
    manifest = json.loads((tmp_path / install.MANIFEST_REL).read_text(encoding="utf-8"))
    assert set(manifest["settings"]["hooks_added"]) == set(
        install.settings_commands(install.build_settings_snippet("py")))
    uninstall.main([str(tmp_path), "--yes"])
    r = subprocess.run(["git", "status", "--porcelain"], cwd=tmp_path,
                       capture_output=True, text=True)
    assert r.stdout.strip() == "", r.stdout


# --------------------------------------------------------------------------- #
# S3: run_doctor
# --------------------------------------------------------------------------- #
def test_doctor_passes_after_install(tmp_path, capsys):
    install.main([str(tmp_path), "--merge-settings"])
    capsys.readouterr()
    rc = install.main([str(tmp_path), "--doctor"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "PROVEN [block_dangerous.py]" in out
    assert install.DOCTOR_BLOCK_LIMIT in out
    assert install.DOCTOR_RESTART_NOTE in out
    assert install.DOCTOR_LEGEND in out


def test_doctor_fails_without_settings(tmp_path, capsys):
    rc = install.main([str(tmp_path), "--doctor"])
    assert rc == 1
    assert "not wired" in capsys.readouterr().out


def test_doctor_fails_when_no_kit_hooks(tmp_path, capsys):
    (tmp_path / ".claude").mkdir()
    (tmp_path / install.SETTINGS_REL).write_text('{"hooks": {}}', encoding="utf-8")
    rc = install.main([str(tmp_path), "--doctor"])
    assert rc == 1
    assert "no agent-workbench hooks" in capsys.readouterr().out


def test_doctor_fails_on_bogus_interpreter(tmp_path, capsys):
    """The silent-off landmine: a wired interpreter that doesn't run must FAIL loud."""
    install.main([str(tmp_path), "--merge-settings"])
    sp = tmp_path / install.SETTINGS_REL
    data = json.loads(sp.read_text(encoding="utf-8"))
    for g in data["hooks"]["PreToolUse"]:
        for h in g["hooks"]:
            if "block_dangerous.py" in h["command"]:
                h["command"] = ('awb_no_such_interp_xyz '
                                '"$CLAUDE_PROJECT_DIR/.claude/hooks/scripts/block_dangerous.py"')
    sp.write_text(json.dumps(data), encoding="utf-8")
    capsys.readouterr()
    rc = install.main([str(tmp_path), "--doctor"])
    out = capsys.readouterr().out
    assert rc == 1
    assert "silently OFF" in out


def test_doctor_fails_when_block_dangerous_script_missing(tmp_path, capsys):
    install.main([str(tmp_path), "--merge-settings"])
    (tmp_path / ".claude/hooks/scripts/block_dangerous.py").unlink()
    capsys.readouterr()
    rc = install.main([str(tmp_path), "--doctor"])
    out = capsys.readouterr().out
    assert rc == 1
    assert "missing" in out


def test_doctor_is_read_only(tmp_path):
    install.main([str(tmp_path), "--merge-settings"])
    before = {p for p in tmp_path.rglob("*") if p.is_file()}
    install.main([str(tmp_path), "--doctor"])
    after = {p for p in tmp_path.rglob("*") if p.is_file()}
    assert before == after  # doctor writes nothing into the project


def test_doctor_exempt_from_self_install_guard(capsys):
    """`install.py . --doctor` must run the read-only check, not the install refusal."""
    rc = install.main([str(install.KIT), "--doctor"])
    captured = capsys.readouterr()
    assert "Refusing to install the kit into itself" not in captured.err
    assert "Doctor" in captured.out
    assert rc == 0


# --------------------------------------------------------------------------- #
# f5: command parsing (var expansion in Python, no shell, no backslash mangle)
# --------------------------------------------------------------------------- #
def test_parse_hook_command_handles_space_in_project_path(tmp_path):
    proj = tmp_path / "a b"
    proj.mkdir()
    cmd = 'python "$CLAUDE_PROJECT_DIR/.claude/hooks/scripts/block_dangerous.py"'
    argv, rel, path = install._parse_hook_command(cmd, proj)
    assert argv == ["python"]
    assert rel == ".claude/hooks/scripts/block_dangerous.py"
    assert path == proj / ".claude" / "hooks" / "scripts" / "block_dangerous.py"


def test_parse_hook_command_handles_quoted_abs_interpreter(tmp_path):
    cmd = '"Z:\\no such\\python.exe" "$CLAUDE_PROJECT_DIR/.claude/hooks/scripts/x.py"'
    argv, rel, path = install._parse_hook_command(cmd, tmp_path)
    assert argv == ["Z:\\no such\\python.exe"]
    assert rel == ".claude/hooks/scripts/x.py"


def test_interp_argv_forms():
    assert install._interp_argv("py") == ["py"]
    assert install._interp_argv('"Z:\\no such\\python.exe"') == ["Z:\\no such\\python.exe"]
