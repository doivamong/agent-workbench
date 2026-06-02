#!/usr/bin/env python3
"""
Hook: PreToolUse (Bash)
Block dangerous shell commands before execution.
Especially important when using Bypass permissions mode on mobile.

Git destructive patterns use regex word-boundary (NOT substring) to:
  - avoid false positives (`git checkout .gitignore` is not blocked)
  - avoid allowlist substring shadowing (old bug: `git push origin --force`
    and `git reset --hard HEAD~N` slipped through because they matched
    allowlist entries `git push origin` / `git reset --hard HEAD`).
    WHITELIST removed — regex matches only genuinely destructive forms.
"""
import sys
import json
import os
import re
from pathlib import Path

# IMPORTANT — scope and honesty:
# This catches *common, obvious* destructive forms (the accidental footgun and the
# blatant one-liner). It is NOT a security boundary: a determined operator can evade
# any string-level matcher (base64, variable indirection, here-docs, eval). Treat it
# as a seatbelt, not a vault. See README "Status & honesty".
#
# Matching is done on a whitespace-normalized, lowercased command, so extra spaces and
# casing ("rm  -rf  /", "RM -RF /") do not slip through.

# Regex patterns matched on the normalized command.
DANGEROUS_REGEX = [
    # --- SQL ---
    (r"\bdrop\s+(?:table|database)\b", "DROP TABLE/DATABASE"),
    (r"\btruncate\s+(?:table\s+)?[`\"']?\w", "TRUNCATE — deletes all rows"),
    (r"\bdelete\s+from\s+[`\"']?\w+[`\"']?\s*(?:;|$)", "DELETE FROM with no WHERE — deletes all rows"),
    # --- filesystem (non-rm) ---
    (r"\bfind\b[^|;&]*\s-delete\b", "find -delete — bulk delete"),
    (r"\bfind\b[^|;&]*-exec\s+rm\b", "find -exec rm — bulk delete"),
    (r"\bdd\b[^|;&]*\bof=/dev/", "dd writing to a raw device"),
    (r"\bmkfs(?:\.\w+)?\b", "mkfs — formats a filesystem"),
    (r"\bchmod\s+-[a-z]*r[a-z]*\s+0?[0-7]{3,4}\b", "Recursive chmod (mass permission change)"),
    (r"\bchown\s+-[a-z]*r[a-z]*\b[^|;&]*\s/\s*$", "Recursive chown on /"),
    (r"\btruncate\b[^|;&]*(?:-s\s*0\b|--size[ =]0\b)", "truncate -s 0 — empties a file"),
    (r">\s*/dev/(?:sd|hd|nvme|disk|mmcblk)", "Redirect to a raw block device"),
    # Content-less truncating redirect: '> file' / ': > file' at command start or after a
    # separator (empties/clobbers a file). Deliberately NOT matched when a command produces
    # the output ('echo x > f', 'cat > f') — those are normal writes, not truncation.
    (r"(?:^|[;&|]\s*):?\s*>\s*[^\s>&|]", "Truncating redirect (> file) — empties/overwrites a file"),
    (r":\s*\(\s*\)\s*\{\s*:\s*\|\s*:", "Fork bomb"),
    # --- Windows ---
    (r"\brmdir\s+/s\b", "Windows recursive directory delete"),
    (r"\bdel\s+/[a-z]*[fqs]", "Windows force delete"),
    (r"\bformat\s+[a-z]:", "Windows format drive"),
    # --- git destructive (flag-order tolerant after normalization) ---
    (r"\bgit\s+push\b[^&|;]*(?:--force\b|--force-with-lease\b|\s-f\b)", "Force push — rewrites remote history"),
    (r"\bgit\s+reset\s+--hard\s+(?:head[~^]|origin/|upstream/|[0-9a-f]{7,40}\b)", "git reset --hard — loses commits"),
    (r"\bgit\s+checkout\s+(?:--\s+)?\.(?:\s|$)", "git checkout . — discards uncommitted changes"),
    (r"\bgit\s+restore\s+(?:--\s+)?\.(?:\s|$)", "git restore . — discards uncommitted changes"),
    (r"\bgit\s+clean\s+-[a-z]*f", "git clean -f — deletes untracked files"),
]

_COMPILED_REGEX = [(re.compile(rx), reason) for rx, reason in DANGEROUS_REGEX]

# Paths that make a recursive delete catastrophic.
_RM_DANGER_TARGETS = {"/", "~", "$home", "${home}", "*", ".", "./", "..", "/*", "~/*"}


def _normalize(command):
    """Lowercase + collapse runs of whitespace, so spacing/casing tricks don't evade."""
    return re.sub(r"\s+", " ", command.strip().lower())


def _is_dangerous_rm(norm):
    """Flag-order-agnostic detector: rm with recursive AND force, or recursive on a
    broad target. Catches 'rm -rf /', 'rm -fr /', 'rm -r -f .', 'rm -rf $HOME', etc."""
    if not re.search(r"\brm\b", norm):
        return False
    has_r = has_f = False
    targets = []
    for tok in norm.split():
        if tok == "rm":
            continue
        if tok == "--recursive":
            has_r = True
        elif tok == "--force":
            has_f = True
        elif tok.startswith("-") and not tok.startswith("--"):
            if "r" in tok[1:]:
                has_r = True
            if "f" in tok[1:]:
                has_f = True
        elif not tok.startswith("-"):
            targets.append(tok)
    if has_r and has_f:
        return True
    if has_r and any(t in _RM_DANGER_TARGETS or t.startswith(("/", "~", "$home")) for t in targets):
        return True
    return False


def _patterns_file():
    """Locate an optional project patterns file, or None. Env override wins."""
    env = os.environ.get("BLOCK_DANGEROUS_PATTERNS")
    if env:
        return Path(env)
    base = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    return Path(base) / ".claude" / "dangerous-patterns.json"


def load_extra_patterns():
    """Load project-defined (regex, reason) rules from .claude/dangerous-patterns.json.

    Lets a project extend the seatbelt without forking this hook (mirrors how
    leak_scan takes a project denylist). JSON shape: a list of objects with a
    "pattern" (regex, matched on the normalized command) and an optional "reason".
    Fail-open: a missing or malformed file yields no extra rules, never a crash.
    """
    path = _patterns_file()
    if not path or not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        out = []
        for item in data:
            out.append((re.compile(item["pattern"]),
                        item.get("reason", "project-defined dangerous pattern")))
        return out
    except (OSError, ValueError, re.error, KeyError, TypeError):
        return []  # a broken patterns file must not break the hook


def check_command(command, extra=None):
    """Return (matched, reason) if the command looks destructive; None if it looks safe.

    Separated from main() so it can be unit-tested directly. Operates on a normalized
    form so spacing/casing variants are treated identically. ``extra`` is an optional
    list of (compiled_regex, reason) from a project patterns file.
    """
    norm = _normalize(command)
    if _is_dangerous_rm(norm):
        return "rm -r -f", "Recursive force delete"
    for rx, reason in _COMPILED_REGEX + list(extra or []):
        if rx.search(norm):
            return rx.pattern, reason
    return None


# Hook logger — imports hook_main from the shared lib directory
from pathlib import Path as _HookLoggerPath
sys.path.insert(0, str(_HookLoggerPath(__file__).parent.parent / "lib"))
from hook_logger import hook_main  # noqa: E402


def _emit_deny(reason):
    """Emit the documented PreToolUse deny decision with a human-readable reason."""
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }))


@hook_main("block_dangerous")
def main():
    # Claude Code delivers the hook payload as JSON on stdin.
    try:
        event = json.load(sys.stdin)
    except Exception:
        # Fail CLOSED: an unparseable payload means we cannot confirm the command is
        # safe, so we deny by default rather than silently letting it through. A
        # security guardrail must not become a no-op on malformed input.
        _emit_deny(
            "block_dangerous could not parse the tool payload, so it cannot verify "
            "the command is safe. Denying by default (fail-closed). If this is a "
            "false positive, run the command manually outside the agent."
        )
        return

    # Only act on Bash commands (settings.json matcher should already scope this).
    if event.get("tool_name") not in (None, "", "Bash"):
        sys.exit(0)

    command = (event.get("tool_input") or {}).get("command", "").strip()
    if not command:
        sys.exit(0)

    hit = check_command(command, extra=load_extra_patterns())
    if hit:
        _pattern, reason = hit
        _emit_deny(
            f"Blocked a dangerous command ({reason}). "
            f"Run it manually outside the agent if this is genuinely intended."
        )
        return

    sys.exit(0)  # safe -> no decision, default flow continues


def _explain(command):
    """Audit mode for adopters: show whether a command would be blocked and why,
    without acting as a hook. Run: python block_dangerous.py --explain "<cmd>"."""
    hit = check_command(command, extra=load_extra_patterns())
    if hit:
        pattern, reason = hit
        print(f"BLOCKED: {reason}")
        print(f"  matched rule: {pattern}")
        return 1
    print("ALLOWED: no dangerous pattern matched.")
    return 0


if __name__ == "__main__":
    if "--explain" in sys.argv:
        rest = [a for a in sys.argv[1:] if a != "--explain"]
        raise SystemExit(_explain(rest[0] if rest else ""))
    main()
