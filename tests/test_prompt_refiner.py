"""Tests for the prompt-refiner-inject UserPromptSubmit hook.

This hook runs on *every* user prompt yet was previously untested. Two layers,
mirroring test_post_edit_simplify:
  - unit tests on the pure decision helpers (loaded via importlib because the
    module name has hyphens), with dedupe/metrics state redirected to a tmp dir.
  - end-to-end subprocess runs over the real stdin -> stdout JSON contract, with
    HOME/USERPROFILE pointed at a tmp dir so nothing touches the real ~/.claude.
"""
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

HOOK = Path(__file__).resolve().parents[1] / ".claude" / "hooks" / "prompt-refiner-inject.py"

VAGUE = "please go and refactor the whole authentication thing and also fix the tests somehow"


def _load_module(tmp_path):
    """Import the hyphen-named hook module and redirect its state files to tmp."""
    spec = importlib.util.spec_from_file_location("prompt_refiner_inject", HOOK)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod._DEDUPE_FILE = tmp_path / "dedupe.json"
    mod._METRICS_FILE = tmp_path / "metrics.jsonl"
    return mod


# --- pure decision helpers --------------------------------------------------

def test_is_structured_detects_lists_and_code(tmp_path):
    mod = _load_module(tmp_path)
    structured = "1. first do this\n2. then that\n```\ncode\n```"
    assert mod.is_structured(structured) is True
    assert mod.is_structured("just a flowing sentence with no structure at all") is False


def test_scope_key_is_stable_and_prefix_scoped(tmp_path):
    mod = _load_module(tmp_path)
    k1 = mod._scope_key("sess", "/cwd", "a long prompt about things " * 5)
    k2 = mod._scope_key("sess", "/cwd", "a long prompt about things " * 5 + " EXTRA TAIL")
    # only the first 100 chars feed the key, so a differing tail collapses to the same key
    assert k1 == k2
    assert k1 != mod._scope_key("other", "/cwd", "a long prompt about things " * 5)


def test_dedupe_blocks_within_ttl(tmp_path):
    mod = _load_module(tmp_path)
    key = "abc123"
    assert mod._should_inject_dedupe(key) is True  # first time: allowed
    mod._update_dedupe_state(key)
    assert mod._should_inject_dedupe(key) is False  # immediately after: suppressed


# --- end-to-end over the real stdin/stdout contract -------------------------

def _run_hook(payload: dict, tmp_path: Path, env_extra: dict | None = None) -> str:
    env = dict(os.environ, HOME=str(tmp_path), USERPROFILE=str(tmp_path))
    if env_extra:
        env.update(env_extra)
    proc = subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps(payload),
        capture_output=True, text=True, env=env,
    )
    assert proc.returncode == 0, proc.stderr
    return proc.stdout


def _injected(stdout: str) -> bool:
    if not stdout.strip():
        return False
    out = json.loads(stdout)
    return "PROMPT REFINER" in out["hookSpecificOutput"]["additionalContext"]


def test_e2e_vague_prompt_injects(tmp_path):
    assert _injected(_run_hook({"prompt": VAGUE}, tmp_path)) is True


def test_e2e_short_prompt_skipped(tmp_path):
    assert _run_hook({"prompt": "fix the bug"}, tmp_path).strip() == ""


def test_e2e_slash_command_skipped(tmp_path):
    assert _run_hook({"prompt": "/commit some long message that exceeds the word threshold easily here"},
                     tmp_path).strip() == ""


def test_e2e_raw_prefix_bypasses(tmp_path):
    assert _run_hook({"prompt": "raw: " + VAGUE}, tmp_path).strip() == ""


def test_e2e_structured_prompt_skipped(tmp_path):
    structured = "1. refactor the auth module thoroughly\n2. then update all of the failing tests\n- and document it"
    assert _run_hook({"prompt": structured}, tmp_path).strip() == ""


def test_e2e_dedupe_suppresses_second_identical_prompt(tmp_path):
    payload = {"prompt": VAGUE, "session_id": "s1", "cwd": "/proj"}
    assert _injected(_run_hook(payload, tmp_path)) is True
    assert _run_hook(payload, tmp_path).strip() == ""  # second identical submission: deduped


def test_e2e_malformed_stdin_is_safe(tmp_path):
    proc = subprocess.run(
        [sys.executable, str(HOOK)],
        input="not json", capture_output=True, text=True,
        env=dict(os.environ, HOME=str(tmp_path), USERPROFILE=str(tmp_path)),
    )
    assert proc.returncode == 0
    assert proc.stdout.strip() == ""
