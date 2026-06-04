"""Tests for install.py — the distribution mechanism a stranger hits first.

Covers the copy map, the printed settings snippet, the git pre-commit hook, and
the --merge-settings deep-merge (correctness + idempotency + preservation of
unrelated keys). Everything runs against a tmp project so nothing is written
outside the test sandbox.
"""
import json

import pytest

import install
from install import COPY_MAP, SETTINGS_SNIPPET, _merge_settings, main, resolve_groups


def test_dry_run_copies_nothing(tmp_path, capsys):
    rc = main([str(tmp_path), "--dry-run"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "would copy" in out
    # dry-run must not actually create files
    assert not (tmp_path / ".claude" / "hooks").exists()


def test_real_install_copies_core_pieces(tmp_path):
    rc = main([str(tmp_path)])
    assert rc == 0
    # a representative file from each kind of COPY_MAP entry lands in place
    assert (tmp_path / ".claude" / "hooks" / "scripts" / "block_dangerous.py").is_file()
    assert (tmp_path / "tools" / "leak_scan.py").is_file()
    assert (tmp_path / "scripts" / "secrets_guard.py").is_file()
    assert (tmp_path / "memory" / "MEMORY.md").is_file()


def test_skips_existing_without_force(tmp_path):
    main([str(tmp_path)])
    target = tmp_path / "tools" / "leak_scan.py"
    target.write_text("# locally edited\n", encoding="utf-8")
    main([str(tmp_path)])  # second run, no --force
    assert target.read_text(encoding="utf-8") == "# locally edited\n"


def test_force_overwrites(tmp_path):
    main([str(tmp_path)])
    target = tmp_path / "tools" / "leak_scan.py"
    target.write_text("# locally edited\n", encoding="utf-8")
    main([str(tmp_path), "--force"])
    assert target.read_text(encoding="utf-8") != "# locally edited\n"


def test_refuses_to_install_into_itself(capsys):
    rc = main([str(install.KIT)])
    assert rc == 1
    assert "itself" in capsys.readouterr().err


def test_refuses_non_directory_target(tmp_path, capsys):
    missing = tmp_path / "does-not-exist"
    rc = main([str(missing)])
    assert rc == 1
    assert "not a directory" in capsys.readouterr().err


def test_git_hook_skipped_without_repo(tmp_path, capsys):
    main([str(tmp_path), "--with-git-hook"])
    assert "no .git found" in capsys.readouterr().out


def test_git_hook_written_with_repo(tmp_path):
    (tmp_path / ".git").mkdir()
    main([str(tmp_path), "--with-git-hook"])
    hook = tmp_path / ".git" / "hooks" / "pre-commit"
    assert hook.is_file()
    body = hook.read_text(encoding="utf-8")
    assert "leak_scan.py" in body
    # Keep this flag in sync with CI / .pre-commit-config by hand — the assertion
    # only checks the substring is present, it does not measure parity with those
    # files. (Adopters' git-ignored local files would otherwise false-positive.)
    assert "--respect-gitignore" in body


# --- --merge-settings ------------------------------------------------------

def test_merge_into_empty_dict_adds_all_events():
    merged = _merge_settings({}, SETTINGS_SNIPPET)
    assert set(merged["hooks"]) == {"PreToolUse", "UserPromptSubmit", "PostToolUse", "PreCompact", "SessionStart", "SessionEnd"}


def test_merge_preserves_unrelated_keys_and_is_idempotent():
    existing = {"model": "claude-opus-4-8", "hooks": {"PreToolUse": [
        {"matcher": "Bash", "hooks": [{"type": "command",
         "command": SETTINGS_SNIPPET["hooks"]["PreToolUse"][0]["hooks"][0]["command"],
         "timeout": 10}]}
    ]}}
    once = _merge_settings(existing, SETTINGS_SNIPPET)
    twice = _merge_settings(once, SETTINGS_SNIPPET)
    assert once == twice                              # idempotent
    assert once["model"] == "claude-opus-4-8"         # unrelated key preserved
    assert len(once["hooks"]["PreToolUse"]) == 1      # the already-present hook is not duplicated
    assert "UserPromptSubmit" in once["hooks"]        # the missing ones are added


def test_merge_settings_flag_writes_valid_json(tmp_path):
    main([str(tmp_path), "--merge-settings"])
    settings = tmp_path / ".claude" / "settings.json"
    assert settings.is_file()
    data = json.loads(settings.read_text(encoding="utf-8"))
    assert set(data["hooks"]) == {"PreToolUse", "UserPromptSubmit", "PostToolUse", "PreCompact", "SessionStart", "SessionEnd"}


def test_merge_settings_flag_is_idempotent_on_disk(tmp_path):
    main([str(tmp_path), "--merge-settings"])
    settings = tmp_path / ".claude" / "settings.json"
    first = settings.read_text(encoding="utf-8")
    main([str(tmp_path), "--merge-settings"])
    assert settings.read_text(encoding="utf-8") == first


# --- C1: group selection (--select), dependencies, manifest, --list/--coverage ---

def test_resolve_groups_pulls_dependencies():
    # hooks needs skills to be functional → selecting hooks auto-adds skills.
    assert resolve_groups(["hooks"]) == ["hooks", "skills"]
    assert resolve_groups(["tools"]) == ["tools"]
    assert resolve_groups(None) == install.GROUPS          # default = everything


def test_resolve_groups_unknown_raises():
    with pytest.raises(ValueError):
        resolve_groups(["nope"])


def test_select_installs_only_chosen_group(tmp_path):
    main([str(tmp_path), "--select", "tools"])
    assert (tmp_path / "tools" / "leak_scan.py").is_file()   # selected
    assert not (tmp_path / ".claude" / "skills").exists()    # not selected
    assert not (tmp_path / "memory").exists()


def test_select_hooks_pulls_in_skills(tmp_path):
    main([str(tmp_path), "--select", "hooks"])
    assert (tmp_path / ".claude" / "hooks").is_dir()
    assert (tmp_path / ".claude" / "skills").is_dir()        # dependency auto-installed


def test_unknown_group_exits_nonzero(tmp_path, capsys):
    rc = main([str(tmp_path), "--select", "bogus"])
    assert rc == 2
    assert "unknown group" in capsys.readouterr().err


def test_install_writes_manifest_with_sha_and_groups(tmp_path):
    main([str(tmp_path), "--select", "tools"])
    manifest = tmp_path / ".claude" / "installer-manifest.json"
    assert manifest.is_file()
    data = json.loads(manifest.read_text(encoding="utf-8"))
    assert data["schema"] == install.MANIFEST_SCHEMA
    assert "tools" in data["groups"]
    entry = data["files"]["tools/leak_scan.py"]
    assert entry["group"] == "tools"
    assert len(entry["sha256"]) == 64                        # a real sha256 hex digest


def test_install_gitignores_the_manifest(tmp_path):
    main([str(tmp_path), "--select", "tools"])
    gitignore = (tmp_path / ".gitignore").read_text(encoding="utf-8")
    assert install.MANIFEST_REL in gitignore


def test_dry_run_writes_no_manifest(tmp_path):
    main([str(tmp_path), "--select", "tools", "--dry-run"])
    assert not (tmp_path / ".claude" / "installer-manifest.json").exists()


def test_list_reports_available_and_installed(tmp_path, capsys):
    main([str(tmp_path), "--select", "tools"])
    capsys.readouterr()
    rc = main([str(tmp_path), "--list"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "Available groups" in out
    assert "tools" in out and "skills" in out


def test_coverage_reports_counts(tmp_path, capsys):
    main([str(tmp_path), "--select", "tools"])
    capsys.readouterr()
    rc = main([str(tmp_path), "--coverage"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "groups:" in out and "files:" in out
