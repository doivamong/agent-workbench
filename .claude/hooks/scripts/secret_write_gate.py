#!/usr/bin/env python3
"""
Hook: PreToolUse (Write | Edit | MultiEdit | NotebookEdit)
Stop the agent from writing a near-certain CLOUD CREDENTIAL into a file that could be
committed and leaked. A non-programmer driving the agent can't tell that a hardcoded
``AKIA…`` / ``ghp_…`` / ``AIza…`` is a catastrophic, costly leak — this catches the
worst, most unambiguous cases before they land on disk.

SCOPE AND HONESTY (measured, not assumed):
  * It denies ONLY leak_scan's HARD_PATTERNS — the high-confidence token shapes
    (private-key blocks, AWS / GitHub / Google / Slack / Telegram keys). On a real
    13.9k-file project these produced ZERO false positives on agent-written files, which
    is why they are safe to BLOCK. The softer detectors (a quoted ``api_key = "…"``
    assignment, ``sk-…`` keys) false-positive on test fixtures, so they are NOT blocked
    here — that is deliberate.
  * It is a TRIPWIRE for *pasted cloud tokens*, NOT full secret protection. It does not
    catch plain passwords, framework SECRET/FERNET keys, database URLs, or unquoted
    ``KEY=value`` env entries — on the same project it caught none of those. Do not read a
    silent pass as "no secrets here".
  * Allow-paths (none is a way to defeat a guard — each is the *correct* action):
      - a **gitignored** target is exempt: the gate exists to stop a secret being *committed*,
        and a gitignored file can't be (measured: on a scraper project every high-confidence
        hit was in a gitignored cache of scraped third-party pages, never a committable file);
      - writing to a ``.env`` / ``.env.*`` file is exempt (the right home for a real key);
      - a ``# leak-scan: ignore[<name>]`` marker on the line lets a known placeholder /
        intentional fixture through.

Fail-open: if anything goes wrong (leak_scan unavailable, odd payload), the write is
ALLOWED — a write hook must never break the user's editing, and this is a tripwire, not a
boundary.
"""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

# --- locate and import leak_scan (the SINGLE source of the detectors) --------------------
# Prefer the project the hook is wired into ($CLAUDE_PROJECT_DIR); fall back to this repo
# layout (.claude/hooks/scripts/ -> repo root). If it can't be imported, the gate fails open.
_leak_scan = None
for _base in (os.environ.get("CLAUDE_PROJECT_DIR"), Path(__file__).resolve().parents[3]):
    if not _base:
        continue
    _tools = Path(_base) / "tools"
    if (_tools / "leak_scan.py").is_file():
        sys.path.insert(0, str(_tools))
        try:
            import leak_scan as _leak_scan  # type: ignore
        except Exception:  # noqa: BLE001 — a broken import must not break writing
            _leak_scan = None
        break

# Friendly names for the deny message (keyed by leak_scan detector name).
_LABELS = {
    "private_key_block": "private key",
    "aws_access_key": "AWS access key",
    "telegram_bot_token": "Telegram bot token",
    "slack_token": "Slack token",
    "github_token": "GitHub token",
    "github_pat": "GitHub personal access token",
    "google_api_key": "Google API key",
}

# Files that are the CORRECT, gitignored home for a real secret — never gated.
_ENV_FILE_RE = re.compile(r"(^|[\\/])\.env(\.[^\\/]*)?$", re.IGNORECASE)


def _is_gitignored(file_path: str) -> bool:
    """True if git would ignore ``file_path`` — meaning it can't be committed, so a secret in it
    can't leak via the repo. Runs ``git check-ignore`` (works on a not-yet-created path too).
    Any error / not-a-repo / git-missing → False, i.e. gate normally: when we can't prove the
    file is uncommittable, prefer to flag. Only ever called on a (rare) high-confidence match."""
    root = os.environ.get("CLAUDE_PROJECT_DIR")
    parent = Path(str(file_path)).parent
    cwd = root or (str(parent) if parent.exists() else None)
    try:
        r = subprocess.run(["git", "check-ignore", "-q", "--", str(file_path)],
                           cwd=cwd, capture_output=True, timeout=5)
        return r.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def _written_text(tool_name: str, tool_input: dict) -> str:
    """The text the tool is about to write, across the write-family tools."""
    if tool_name == "Write":
        return tool_input.get("content") or ""
    if tool_name == "Edit":
        return tool_input.get("new_string") or ""
    if tool_name == "MultiEdit":
        return "\n".join(e.get("new_string") or "" for e in (tool_input.get("edits") or []))
    if tool_name == "NotebookEdit":
        return tool_input.get("new_source") or ""
    return ""


def find_hard_secret(text: str):
    """Return (detector_name, line_no) for the first HARD_PATTERNS hit in ``text`` that is
    not silenced by a scoped ``leak-scan: ignore[name]`` marker on its line; else None.
    Reuses leak_scan's own patterns so a security check never drifts from the scanner."""
    if _leak_scan is None:
        return None
    hard = [(name, rx) for name, rx in _leak_scan.GENERIC_PATTERNS
            if name in _leak_scan.HARD_PATTERNS]
    for lineno, line in enumerate(text.splitlines(), 1):
        _bare, named = _leak_scan._parse_ignore(line)  # honor a scoped opt-out only
        for name, rx in hard:
            if rx.search(line) and name not in named:
                return name, lineno
    return None


def _emit_deny(reason: str) -> None:
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }))


# Hook logger — shared fail-open wrapper (imports from the sibling lib dir).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))
from hook_logger import hook_main  # noqa: E402


@hook_main("secret_write_gate")
def main():
    try:
        event = json.load(sys.stdin)
    except Exception:
        sys.exit(0)  # can't parse → don't block the write (tripwire, fail-open)

    tool_name = event.get("tool_name") or ""
    if tool_name not in ("Write", "Edit", "MultiEdit", "NotebookEdit"):
        sys.exit(0)

    tool_input = event.get("tool_input") or {}
    file_path = tool_input.get("file_path") or tool_input.get("notebook_path") or ""
    if _ENV_FILE_RE.search(str(file_path)):
        sys.exit(0)  # a real key belongs in .env — that is the allow-path, not a leak

    hit = find_hard_secret(_written_text(tool_name, tool_input))
    if hit:
        if _is_gitignored(str(file_path)):
            sys.exit(0)  # uncommittable (e.g. a scrape cache) → can't leak via the repo
        name, lineno = hit
        label = _LABELS.get(name, "credential")
        where = Path(str(file_path)).name or "this file"
        _emit_deny(
            f"That looks like a real {label} (line {lineno}), and writing it into "
            f"'{where}' risks committing it where it can be seen publicly — a leaked cloud "
            f"key like this is the costly kind. If it IS your real secret, put it in a .env "
            f"file instead (that's gitignored, so it won't be committed). If it's only a "
            f"placeholder or an intentional test fixture, add '# leak-scan: ignore[{name}]' "
            f"on that line. (This catches pasted cloud tokens — it does NOT catch every "
            f"secret, e.g. plain passwords or .env values, so a silent pass is not a "
            f"guarantee.)"
        )
        return

    sys.exit(0)  # no high-confidence secret → allow the write


def _explain(text: str) -> int:
    """Audit mode for adopters: show whether some text would be blocked, without acting as a
    hook. Run: python secret_write_gate.py --explain "<text>"."""
    hit = find_hard_secret(text)
    if hit:
        name, lineno = hit
        print(f"BLOCKED: high-confidence {_LABELS.get(name, name)} on line {lineno} ({name})")
        return 1
    print("ALLOWED: no high-confidence cloud-token pattern matched.")
    return 0


if __name__ == "__main__":
    if "--explain" in sys.argv:
        rest = [a for a in sys.argv[1:] if a != "--explain"]
        raise SystemExit(_explain(rest[0] if rest else ""))
    main()
