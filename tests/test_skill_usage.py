"""Skill-usage telemetry: the logger (UserPromptSubmit hook) + the report aggregator.

The logger records a PROXY — skill names appearing in prompts — so the contract under test is
modest but exact: it distinguishes an explicit `/invoke` from a bare `mention`, never logs a
name that isn't there, discovers skills dynamically, stores a digest (not the prompt text),
and — being a hook — never breaks a prompt (fail-open). The aggregator must window, roll up,
flag dormant skills, and survive a malformed log line.
"""
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import skill_usage_logger as logger
import skill_usage_report as report

ROOT = Path(__file__).resolve().parents[1]
LOGGER_HOOK = ROOT / ".claude" / "hooks" / "scripts" / "skill_usage_logger.py"


def _skills(base: Path, *names: str) -> Path:
    d = base / ".claude" / "skills"
    for n in names:
        (d / n).mkdir(parents=True)
        (d / n / "SKILL.md").write_text("# x\n", encoding="utf-8")
    return d


# ---- logger: pure functions -------------------------------------------------

def test_discover_skill_names_needs_skill_md(tmp_path):
    d = _skills(tmp_path, "example-debug")
    (d / "no-skill-md").mkdir()  # a directory without SKILL.md is not a skill
    assert logger.discover_skill_names(d) == ["example-debug"]


def test_discover_skill_names_longest_first(tmp_path):
    d = _skills(tmp_path, "review", "example-review")
    assert logger.discover_skill_names(d) == ["example-review", "review"]


def test_discover_missing_dir_is_empty(tmp_path):
    assert logger.discover_skill_names(tmp_path / "nope") == []


def test_find_signals_invoke_vs_mention():
    names = ["example-review", "example-debug"]
    assert logger.find_signals("please /example-review this", names) == [("example-review", "invoke")]
    assert logger.find_signals("use example-debug now", names) == [("example-debug", "mention")]


def test_find_signals_word_boundary_no_false_match():
    # the common word "review" must NOT match the skill "example-review"
    assert logger.find_signals("review my code", ["example-review"]) == []


def test_find_signals_each_skill_once_at_strongest():
    out = logger.find_signals("/example-debug and example-debug again", ["example-debug"])
    assert out == [("example-debug", "invoke")]


# ---- logger: as a subprocess (the real hook contract) -----------------------

def _run_logger(stdin: str, env_extra: dict) -> subprocess.CompletedProcess:
    env = dict(os.environ, HOME=os.environ.get("TEMP", "/tmp"), **env_extra)
    return subprocess.run([sys.executable, str(LOGGER_HOOK)], input=stdin,
                          capture_output=True, text=True, env=env)


def test_logger_writes_one_line_per_signal_and_no_prompt_text(tmp_path):
    _skills(tmp_path, "example-debug")
    log = tmp_path / "u.jsonl"
    proc = _run_logger(json.dumps({"prompt": "run /example-debug now", "session_id": "abc"}),
                       {"CLAUDE_PROJECT_DIR": str(tmp_path), "SKILL_USAGE_LOG_PATH": str(log)})
    assert proc.returncode == 0, proc.stderr
    raw = log.read_text(encoding="utf-8")
    lines = [json.loads(x) for x in raw.splitlines() if x.strip()]
    assert len(lines) == 1
    assert lines[0]["skill"] == "example-debug"
    assert lines[0]["signal"] == "invoke"
    assert len(lines[0]["prompt"]) == 8          # an 8-char digest, not the text
    assert "run /example-debug now" not in raw   # the prompt text is never stored


def test_logger_kill_switch(tmp_path):
    _skills(tmp_path, "example-debug")
    log = tmp_path / "u.jsonl"
    proc = _run_logger(json.dumps({"prompt": "/example-debug"}),
                       {"CLAUDE_PROJECT_DIR": str(tmp_path), "SKILL_USAGE_LOG_PATH": str(log),
                        "SKILL_USAGE_LOG": "0"})
    assert proc.returncode == 0
    assert not log.exists()


def test_logger_no_skill_no_log(tmp_path):
    _skills(tmp_path, "example-debug")
    log = tmp_path / "u.jsonl"
    proc = _run_logger(json.dumps({"prompt": "just a normal request"}),
                       {"CLAUDE_PROJECT_DIR": str(tmp_path), "SKILL_USAGE_LOG_PATH": str(log)})
    assert proc.returncode == 0
    assert not log.exists()


def test_logger_fails_open_on_garbage(tmp_path):
    log = tmp_path / "u.jsonl"
    proc = _run_logger("not json{{{",
                       {"CLAUDE_PROJECT_DIR": str(tmp_path), "SKILL_USAGE_LOG_PATH": str(log)})
    assert proc.returncode == 0       # never blocks the prompt
    assert not log.exists()


# ---- aggregator -------------------------------------------------------------

def _entries(now: datetime) -> list[dict]:
    return [
        {"time": (now - timedelta(days=1)).isoformat(), "skill": "a", "signal": "invoke", "prompt": "p1", "session": "s1"},
        {"time": (now - timedelta(days=2)).isoformat(), "skill": "a", "signal": "mention", "prompt": "p2", "session": "s1"},
        {"time": (now - timedelta(days=20)).isoformat(), "skill": "b", "signal": "mention", "prompt": "p3", "session": "s2"},
    ]


def _write_log(tmp_path: Path, now: datetime, extra=()) -> Path:
    log = tmp_path / "log.jsonl"
    lines = [json.dumps(e) for e in _entries(now)] + list(extra)
    log.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return log


def _args(log: Path, skills: Path, **kw) -> SimpleNamespace:
    base = dict(log_path=str(log), skills_dir=str(skills), days=30, since=None, output=None, json=False)
    base.update(kw)
    return SimpleNamespace(**base)


def test_parse_log_windows_and_skips_malformed(tmp_path):
    now = datetime.now()
    log = _write_log(tmp_path, now, extra=["{garbage}", ""])
    entries, skipped = report.parse_log(log, now - timedelta(days=30))
    assert len(entries) == 3
    assert skipped == 1                       # blank line ignored, garbage counted
    narrow, _ = report.parse_log(log, now - timedelta(days=10))
    assert {e["skill"] for e in narrow} == {"a"}   # the 20-day-old "b" falls outside


def test_aggregate_counts_invoke_mention_and_trend(tmp_path):
    now = datetime.now()
    entries, _ = report.parse_log(_write_log(tmp_path, now), now - timedelta(days=30))
    stats = report.aggregate(entries, now - timedelta(days=report.RECENT_DAYS))
    assert stats["a"]["invoke"] == 1
    assert stats["a"]["mention"] == 1
    assert stats["a"]["total"] == 2
    assert stats["a"]["recent"] == 2          # both "a" entries within 7 days
    assert stats["b"]["prior"] == 1           # "b" is 20 days old -> prior slice


def test_discover_known_skills(tmp_path):
    d = _skills(tmp_path, "example-debug", "deep-research")
    assert report.discover_known_skills(d) == {"example-debug", "deep-research"}


def test_markdown_lists_dormant_and_honest_limit(tmp_path):
    now = datetime.now()
    log = _write_log(tmp_path, now)
    skills = _skills(tmp_path, "a", "deep-research")   # "a" active; deep-research dormant
    md = report.build_report(_args(log, skills), now)
    assert "`a`" in md
    assert "Dormant" in md and "deep-research" in md
    assert "Honest limit" in md


def test_json_output_shape(tmp_path):
    now = datetime.now()
    log = _write_log(tmp_path, now)
    skills = _skills(tmp_path, "a")
    out = json.loads(report.build_report(_args(log, skills, json=True), now))
    assert out["skills_seen"] == 2            # a and b both appear in the log
    assert out["per_skill"]["a"]["invoke"] == 1
    assert "b" in out["per_skill"]


def test_empty_window_message(tmp_path):
    now = datetime.now()
    log = tmp_path / "empty.jsonl"
    log.write_text("", encoding="utf-8")
    md = report.build_report(_args(log, tmp_path / "noskills"), now)
    assert "No telemetry" in md


def test_trend_marker():
    assert report._trend(3, 1) == "+2"
    assert report._trend(1, 3) == "-2"
    assert report._trend(2, 2) == "="
