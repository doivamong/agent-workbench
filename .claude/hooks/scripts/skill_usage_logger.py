#!/usr/bin/env python3
"""UserPromptSubmit hook — record which skills a prompt reaches for (OPT-IN telemetry).

Appends one JSONL line per skill a prompt names, so `tools/skill_usage_report.py` can later
show which skills actually fire and which are dead weight. Two signal strengths are recorded:

  - "invoke"  — the prompt contains `/<skill>` (an explicit slash invocation; high confidence)
  - "mention" — the prompt contains the bare skill name (LOW confidence; a name in passing is
                NOT a use — this is exactly the proxy the report warns about)

Skill names are DISCOVERED at runtime from `.claude/skills/*/SKILL.md` (folder name == skill
name) — nothing is hardcoded, so it tracks whatever skills the project actually ships.

**Opt-in by design.** This hook is shipped but NOT wired by default. Enable it by adding it to
the `UserPromptSubmit` chain in `.claude/settings.json` (see README). Telemetry should be a
deliberate choice, not something that starts the moment you install the kit.

Privacy: the prompt text is never stored — only an 8-char digest (to de-dup repeated prompts)
and an 8-char session digest. The log is project-local and gitignored.

Kill switches (environment variables):
- SKILL_USAGE_LOG=0          — disable even if wired
- SKILL_USAGE_LOG_PATH=<p>   — relocate the log file (used by tests)

Protocol: stdin JSON (prompt, session_id?, cwd?) -> stdout empty -> exit 0. Never blocks.
"""
import hashlib
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))
from stdio_utf8 import ensure_utf8_io  # noqa: E402
from hook_logger import hook_main  # noqa: E402

# UTF-8, pythonw-safe stdout/stdin before any output (shared lib/stdio_utf8.py).
ensure_utf8_io()

LOG_MAX_BYTES = 5 * 1024 * 1024  # rotate past this; keep one .1 backup


def _project_dir() -> Path:
    return Path(os.environ.get("CLAUDE_PROJECT_DIR", "."))


def _log_path() -> Path:
    override = os.environ.get("SKILL_USAGE_LOG_PATH")
    if override:
        return Path(override)
    return _project_dir() / ".claude" / ".logs" / "skill_usage.jsonl"


def discover_skill_names(skills_dir: Path) -> list[str]:
    """Skill names = subdirectories of `.claude/skills/` that contain a SKILL.md.

    Returned longest-first so a longer name is tested before a shorter one it contains."""
    if not skills_dir.is_dir():
        return []
    names = [d.name for d in skills_dir.iterdir() if d.is_dir() and (d / "SKILL.md").is_file()]
    return sorted(names, key=len, reverse=True)


def find_signals(prompt: str, skill_names: list[str]) -> list[tuple[str, str]]:
    """Return (skill, signal) pairs found in the prompt, each skill at its strongest signal.

    'invoke' when the prompt has `/<skill>` (a real slash command, not a path); otherwise
    'mention' for the bare name. Matching is case-insensitive and word-bounded so a common
    word like 'review' does not match the skill 'awb-review'."""
    low = prompt.lower()
    found: list[tuple[str, str]] = []
    for name in skill_names:
        n = re.escape(name.lower())
        if re.search(r"(?<![\w/])/" + n + r"\b", low):
            found.append((name, "invoke"))
        elif re.search(r"\b" + n + r"\b", low):
            found.append((name, "mention"))
    return found


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", "ignore")).hexdigest()[:8]


def _rotate(log: Path) -> None:
    """Move the log aside once it grows past the cap; keep exactly one backup. Fail-open."""
    try:
        if log.exists() and log.stat().st_size > LOG_MAX_BYTES:
            backup = log.with_suffix(".jsonl.1")
            if backup.exists():
                backup.unlink()
            log.rename(backup)
    except Exception:
        pass


@hook_main("skill-usage-logger")
def main() -> None:
    if os.environ.get("SKILL_USAGE_LOG", "1") == "0":
        sys.exit(0)
    try:
        event = json.load(sys.stdin)
    except Exception:
        sys.exit(0)  # unparseable stdin -> log nothing, never block

    prompt = event.get("prompt") or event.get("user_prompt") or ""
    if not prompt.strip():
        sys.exit(0)

    skills = discover_skill_names(_project_dir() / ".claude" / "skills")
    signals = find_signals(prompt, skills)
    if not signals:
        sys.exit(0)

    now = datetime.now().isoformat(timespec="seconds")
    prompt_digest = _digest(prompt)
    session_digest = _digest(str(event.get("session_id") or event.get("cwd") or os.getcwd()))
    log = _log_path()
    try:
        log.parent.mkdir(parents=True, exist_ok=True)
        _rotate(log)
        with log.open("a", encoding="utf-8") as f:
            for skill, signal in signals:
                f.write(json.dumps(
                    {"time": now, "skill": skill, "signal": signal,
                     "prompt": prompt_digest, "session": session_digest},
                    ensure_ascii=False) + "\n")
    except Exception:
        pass  # telemetry must never break a prompt


if __name__ == "__main__":
    main()
