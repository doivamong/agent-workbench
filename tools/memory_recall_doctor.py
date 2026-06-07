#!/usr/bin/env python3
"""memory_recall_doctor.py — does your curated memory actually reach the agent?

This kit's repo ``memory/`` is a COMMITTED REFERENCE TEMPLATE. The Claude Code harness
(v2.1.59+) auto-loads ``MEMORY.md`` (first 200 lines / ~25 KB) from a PER-PROJECT path —
``~/.claude/projects/<mangled-cwd>/memory/`` — NOT from the repo's ``./memory/``. So a fact you
curate in the repo dir is never recalled unless you also place it at the path the harness reads
(see ``docs/memory-governance.md``). This read-only doctor makes that wiring visible:

  - which directory the harness most likely loads, and whether it exists;
  - whether the live store is EMPTY — a fresh clone recalls *nothing* yet. This is surfaced
    loudly (so it is not mistaken for a green pass), but it is NOT a failure: an empty per-project
    store is the honest day-1 state, filled over time via the ``capture the lessons`` skill;
  - how many facts live there vs in the repo template (a big mismatch = curating the wrong dir),
    and how many of the live facts are ``*_example_*`` template placeholders (noise that should
    not reach recall);
  - whether the live ``MEMORY.md`` is over the ~25 KB / 200-line load budget (entries past it
    truncate silently from recall).

Live-dir resolution order: ``--dir`` > ``autoMemoryDirectory`` in ``.claude/settings.json`` >
derived ``~/.claude/projects/<mangled-cwd>/memory``. The derived path is harness-specific and
version-fragile, so it is ALWAYS stat-verified — the doctor never asserts a path it did not
stat, and never reports a missing dir as a failure (your Claude Code may simply predate v2.1.59).
NOTE: this tool only READS ``autoMemoryDirectory``; whether the harness HONORS that override for
auto-load is not verified here — so when it is the resolution source, the report says so plainly.

Exit code: 1 ONLY when a located live ``MEMORY.md`` is over budget (truncation is certain).
Every other case — missing dir, unresolved path, EMPTY store, healthy index — exits 0 (advisory):
an empty day-1 store is loud in the text but not an error.

Does NOT: read or query fact contents, follow ``[[wiki-links]]``, verify your Claude Code
version, or write anything. It is a read-only wiring trip-wire, not a recall engine. Stdlib only.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

try:  # tools/ on sys.path: a direct script run, or the test suite (see tests/conftest.py)
    from memory_budget import INDEX_MAX_BYTES, INDEX_MAX_LINES  # shared load budget — never re-declare
except ModuleNotFoundError:  # imported as a package, e.g. `from tools.memory_recall_doctor import ...`
    from tools.memory_budget import INDEX_MAX_BYTES, INDEX_MAX_LINES

INDEX_NAME = "MEMORY.md"
SKIP = {INDEX_NAME, "README.md"}


def mangle_cwd(cwd: Path) -> str:
    """Claude Code project-id mangling: every non-alphanumeric character becomes '-'.

    e.g. ``Z:/code/proj_x/sub`` -> ``Z--code-proj-x-sub``, and a ``.claude`` worktree path folds
    ``/.`` to ``--`` to match the harness's on-disk ~/.claude/projects/<id>/ dir. Harness-specific
    and version-fragile; the caller always stat-verifies the result rather than trusting it.
    """
    return re.sub(r"[^A-Za-z0-9]", "-", str(cwd))


def _auto_memory_dir(project: Path) -> "Path | None":
    """``autoMemoryDirectory`` from ``.claude/settings.json`` (``~`` expanded), if set."""
    settings = project / ".claude" / "settings.json"
    if not settings.exists():
        return None
    try:
        data = json.loads(settings.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict):          # valid JSON but not an object -> fall through
        return None
    raw = data.get("autoMemoryDirectory")
    if not isinstance(raw, str) or not raw.strip():
        return None
    return Path(raw).expanduser()


def resolve_live_dir(project: Path, explicit: "Path | None") -> "tuple[Path, str]":
    """Return (path, how_resolved). Does NOT guarantee existence — the caller stats it."""
    if explicit is not None:
        return explicit.expanduser(), "--dir"
    auto = _auto_memory_dir(project)
    if auto is not None:
        return auto, "autoMemoryDirectory (.claude/settings.json)"
    derived = Path.home() / ".claude" / "projects" / mangle_cwd(project) / "memory"
    return derived, "derived from cwd (best-effort, version-fragile)"


def _fact_count(d: Path) -> int:
    return sum(1 for p in d.glob("*.md") if p.name not in SKIP)


def _example_count(d: Path) -> int:
    """Count ``*_example_*`` template placeholders (made-up scaffold facts) living in ``d``.

    A clean, name-based signal — these files are pure noise if they reach recall. We classify
    only this; we do NOT guess which real facts are 'kit-specific' (no clean signal for that —
    guessing would be the false-confidence trap measurement-honesty.md warns against).
    """
    return sum(1 for p in d.glob("*_example_*.md") if p.name not in SKIP)


def _empty_guidance() -> "list[str]":
    """The loud, plain-language day-1-empty message — shared by the missing-dir and zero-fact
    branches so a fresh-clone user cannot read the (exit-0) advisory as a green 'memory works'."""
    return [
        "  WARN: MEMORY IS EMPTY - the agent recalls NOTHING about this project yet.",
        "        This is EXPECTED on a fresh clone: the live store is per-project and starts empty.",
        "        It fills with what your agent learns about YOUR project - to start, say",
        "        'capture the lessons' at the end of a session (the awb-lessons-capture skill).",
    ]


def doctor(project: Path, explicit_dir: "Path | None", template: Path) -> "tuple[list[str], int]":
    """Return (report_lines, exit_code). Read-only. exit 1 only on a certain over-budget index."""
    lines: "list[str]" = []
    live, how = resolve_live_dir(project, explicit_dir)
    template_facts = _fact_count(template) if template.is_dir() else 0
    lines.append(f"Live (harness-loaded) memory dir: {live}")
    lines.append(f"  resolved via: {how}")
    if how.startswith("autoMemoryDirectory"):
        lines.append("  NOTE: this tool only READS autoMemoryDirectory; whether your Claude Code HONORS")
        lines.append("        it for auto-load is NOT verified here - confirm via a real session's loaded")
        lines.append("        context, not this tool.")
    lines.append(f"Repo template dir: {template}  ({template_facts} fact file(s))")

    if not live.is_dir():
        lines.append("  STATUS: live dir NOT found at the path above.")
        lines.extend(_empty_guidance())
        lines.append("  -> Facts curated only in the repo template are never recalled by the agent.")
        lines.append("     Copy your scaffold to the live path (or set autoMemoryDirectory), then re-run.")
        lines.append("     If you expected it to exist, pass --dir <path>; your Claude Code may also "
                     "predate v2.1.59 (native auto-memory).")
        return lines, 0  # advisory, NOT a failure — could be an older harness

    live_facts = _fact_count(live)
    lines.append(f"  STATUS: live dir found, {live_facts} fact file(s).")
    if live_facts == 0:
        lines.extend(_empty_guidance())
    example_facts = _example_count(live)
    if example_facts:
        lines.append(f"  WARN: {example_facts} of these are *_example_* template placeholders - "
                     "made-up noise that should not reach recall; remove them.")
    if template_facts > live_facts:
        lines.append(f"  NOTE: the repo template holds more facts ({template_facts}) than the live dir "
                     f"({live_facts}) - if you curated facts in the repo dir, they are not being recalled.")

    index = live / INDEX_NAME
    if not index.exists():
        lines.append(f"  WARN: no {INDEX_NAME} in the live dir - nothing auto-loads each session.")
        return lines, 0
    raw = index.read_text(encoding="utf-8", errors="replace")
    nbytes, nlines = len(raw.encode("utf-8")), len(raw.splitlines())
    budget = (f"{nbytes / 1024:.1f} KB / {nlines} lines "
              f"(budget ~{INDEX_MAX_BYTES // 1024} KB / {INDEX_MAX_LINES} lines)")
    if nbytes > INDEX_MAX_BYTES or nlines > INDEX_MAX_LINES:
        lines.append(f"  RED: {INDEX_NAME} is {budget} - OVER budget; later entries truncate "
                     "silently from recall.")
        return lines, 1
    lines.append(f"  OK: {INDEX_NAME} is {budget} - within the load budget.")
    lines.append("Note: cannot verify your Claude Code version here; native auto-memory needs v2.1.59+.")
    return lines, 0


def main(argv: "list[str] | None" = None) -> int:
    ap = argparse.ArgumentParser(
        description="Check whether curated memory reaches the agent (read-only, writes nothing).")
    ap.add_argument("--dir", type=Path, default=None,
                    help="The live per-project memory dir the harness loads (overrides auto-detection).")
    ap.add_argument("--template", type=Path, default=Path("memory"),
                    help="The repo reference-template memory dir (default: ./memory).")
    ap.add_argument("--project", type=Path, default=None,
                    help="Project root used for path derivation + settings (default: cwd).")
    args = ap.parse_args(argv)
    project = (args.project or Path.cwd()).resolve()
    report, code = doctor(project, args.dir, args.template)
    for ln in report:
        print(ln)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
