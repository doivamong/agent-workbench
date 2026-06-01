#!/usr/bin/env python3
"""UserPromptSubmit hook — inject instruction prompting Claude to run the prompt-refiner skill.

Trigger: Every user prompt submission
Logic: If prompt >10 words + not a slash command + not "raw:" prefix + not already structured
       + no dedupe hit → inject additionalContext instructing Claude to invoke the
       prompt-refiner skill.

Features:
- Injection deduplication (scope_key = sha1(session + cwd + prompt[:100]), TTL 10min)
- Usage JSONL metrics logging (~/.claude/.logs/prompt-refiner-metrics.jsonl, rotate at 5MB)

Kill switches (environment variables):
- PROMPT_REFINER_HOOK_LOGGING=0  — skip crash log (shared across all hooks)
- PROMPT_REFINER_DEDUPE=0        — disable dedupe, inject on every qualifying prompt
- PROMPT_REFINER_METRICS=0       — disable JSONL metrics write
- PROMPT_REFINER_JSON=0          — fall back to plain text output (canary from v1)

Protocol: stdin JSON (prompt field) → stdout text → exit 0
"""

import hashlib
import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stdin, "reconfigure"):
    sys.stdin.reconfigure(encoding="utf-8")

# ─── Skip patterns ──────────────────────────────────────────────────────────
STRUCTURED_PATTERNS = [
    r"^\d+\.\s",          # numbered list "1. do X"
    r"^[-*]\s",           # bullet list "- do X"
    r"```",               # code block
    r"file:\s*\S+\.py",   # explicit file reference
]

# Slash command prefixes that bypass the refiner
SLASH_PREFIXES = ("/<project>-", "/ck:", "/commit", "/help", "/clear", "/compact",
                  "/checkpoint", "/wrap-up", "/spawn", "/mode",
                  "/context", "/tasks", "/loop", "/schedule")

# ─── Paths & thresholds ──────────────────────────────────────────────────────
_METRICS_FILE = Path.home() / ".claude" / ".logs" / "prompt-refiner-metrics.jsonl"
_METRICS_MAX_BYTES = 5 * 1024 * 1024  # rotate at 5MB
_DEDUPE_FILE = Path.home() / ".claude" / ".state" / "prompt_refiner_dedupe.json"
_DEDUPE_TTL_SEC = 600   # 10 minutes
_DEDUPE_MAX_ENTRIES = 200  # prune when state grows beyond this


def is_structured(prompt: str) -> bool:
    """Return True if prompt already has clear structure (≥2 pattern signals)."""
    matches = sum(1 for p in STRUCTURED_PATTERNS if re.search(p, prompt, re.MULTILINE))
    return matches >= 2


def _scope_key(session_id: str, cwd: str, prompt: str) -> str:
    """Compute dedupe key — same session+cwd+prompt-prefix maps to the same key."""
    raw = f"{session_id}|{cwd}|{prompt[:100]}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def _log_metric(action: str, word_count: int = 0, extra: dict | None = None) -> None:
    """Append a JSONL metric entry. Fail-open. Respects PROMPT_REFINER_METRICS=0."""
    if os.environ.get("PROMPT_REFINER_METRICS", "1") == "0":
        return
    try:
        _METRICS_FILE.parent.mkdir(parents=True, exist_ok=True)
        # Rotate if over size threshold (best-effort)
        if _METRICS_FILE.exists() and _METRICS_FILE.stat().st_size > _METRICS_MAX_BYTES:
            rotated = _METRICS_FILE.with_suffix(".jsonl.1")
            if rotated.exists():
                rotated.unlink()
            _METRICS_FILE.rename(rotated)
        entry = {
            "ts": datetime.now().isoformat(timespec="seconds"),
            "action": action,
            "word_count": word_count,
        }
        if extra:
            entry.update(extra)
        with _METRICS_FILE.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass  # never block on metrics failure


def _should_inject_dedupe(scope_key: str) -> bool:
    """Return True if injection is allowed (not recently injected for this scope_key).

    Fail-open: any exception → return True (allow inject).
    Respects PROMPT_REFINER_DEDUPE=0 → always return True.
    """
    if os.environ.get("PROMPT_REFINER_DEDUPE", "1") == "0":
        return True
    try:
        if not _DEDUPE_FILE.exists():
            return True
        state = json.loads(_DEDUPE_FILE.read_text(encoding="utf-8"))
        last_ts = state.get(scope_key, 0)
        now = time.time()
        return (now - last_ts) > _DEDUPE_TTL_SEC
    except Exception:
        return True  # fail-open


def _update_dedupe_state(scope_key: str) -> None:
    """Mark scope_key as recently injected. Prune old entries. Fail-open."""
    if os.environ.get("PROMPT_REFINER_DEDUPE", "1") == "0":
        return
    try:
        _DEDUPE_FILE.parent.mkdir(parents=True, exist_ok=True)
        state: dict = {}
        if _DEDUPE_FILE.exists():
            try:
                state = json.loads(_DEDUPE_FILE.read_text(encoding="utf-8"))
            except Exception:
                state = {}
        now = time.time()
        # Prune entries older than TTL
        state = {k: v for k, v in state.items() if (now - v) < _DEDUPE_TTL_SEC}
        state[scope_key] = now
        # Hard cap — keep only the most recent MAX_ENTRIES
        if len(state) > _DEDUPE_MAX_ENTRIES:
            state = dict(
                sorted(state.items(), key=lambda kv: kv[1], reverse=True)[:_DEDUPE_MAX_ENTRIES]
            )
        _DEDUPE_FILE.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass  # never block on dedupe failure


# ─── Hook logger ─────────────────────────────────────────────────────────────
# Requires hook_logger.py in the same hooks/lib/ directory.
# hook_main() wraps the entry point with fail-open error handling and crash logging.
sys.path.insert(0, str(Path(__file__).parent / "lib"))
from hook_logger import hook_main  # noqa: E402


@hook_main("prompt-refiner-inject")
def main() -> None:
    try:
        stdin_data = json.load(sys.stdin)
    except Exception:
        _log_metric("skip-empty")
        sys.exit(0)

    prompt = stdin_data.get("prompt", "") or stdin_data.get("user_prompt", "")
    if not prompt:
        _log_metric("skip-empty")
        sys.exit(0)

    prompt_stripped = prompt.strip()
    word_count = len(prompt_stripped.split())

    # Skip: slash commands
    if any(prompt_stripped.lower().startswith(p) for p in SLASH_PREFIXES):
        _log_metric("skip-slash", word_count)
        sys.exit(0)

    # Skip: "raw:" prefix — explicit user bypass
    if prompt_stripped.lower().startswith("raw:"):
        _log_metric("skip-raw", word_count)
        sys.exit(0)

    # Skip: ≤10 words
    if word_count <= 10:
        _log_metric("skip-short", word_count)
        sys.exit(0)

    # Skip: already structured prompt
    if is_structured(prompt_stripped):
        _log_metric("skip-structured", word_count)
        sys.exit(0)

    # Dedupe: skip if the same prompt was recently injected for this session+cwd
    session_id = stdin_data.get("session_id", "") or os.environ.get("CLAUDE_SESSION_ID", "")
    cwd = stdin_data.get("cwd", "") or os.getcwd()
    scope_key = _scope_key(session_id, cwd, prompt_stripped)

    if not _should_inject_dedupe(scope_key):
        _log_metric("skip-dedupe", word_count, {"scope_key": scope_key})
        sys.exit(0)

    # Build injection instruction
    instruction = (
        "[PROMPT REFINER] Prompt >10 words detected. "
        "MUST invoke the prompt-refiner skill BEFORE executing. "
        "Analyse the prompt — if ambiguous, show an optimised version and ask the user to confirm. "
        "If the prompt is already clear (specific scope, file paths, expected outcome) "
        "→ skip the refiner and execute directly."
    )

    # Uniform JSON additionalContext output format.
    # Set PROMPT_REFINER_JSON=0 to fall back to plain text if JSON breaks Claude Code parsing.
    if os.environ.get("PROMPT_REFINER_JSON", "1") == "1":
        output = {
            "continue": True,
            "hookSpecificOutput": {
                "hookEventName": "UserPromptSubmit",
                "additionalContext": instruction,
            },
        }
        print(json.dumps(output, ensure_ascii=False))
    else:
        print(instruction)

    # Record metrics and update dedupe state
    _log_metric("inject", word_count, {"scope_key": scope_key})
    _update_dedupe_state(scope_key)

    sys.exit(0)


if __name__ == "__main__":
    main()
