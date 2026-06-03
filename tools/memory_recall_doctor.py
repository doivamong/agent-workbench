#!/usr/bin/env python3
"""memory_recall_doctor.py — does your curated memory actually reach the agent?

This kit's repo ``memory/`` is a COMMITTED REFERENCE TEMPLATE. The Claude Code harness
(v2.1.59+) auto-loads ``MEMORY.md`` (first 200 lines / ~25 KB) from a PER-PROJECT path —
``~/.claude/projects/<mangled-cwd>/memory/`` — NOT from the repo's ``./memory/``. So a fact you
curate in the repo dir is never recalled unless you also place it at the path the harness reads
(see ``docs/memory-governance.md``). This read-only doctor makes that wiring visible:

  - which directory the harness most likely loads, and whether it exists;
  - how many facts live there vs in the repo template (a big mismatch = curating the wrong dir);
  - whether the live ``MEMORY.md`` is over the ~25 KB / 200-line load budget (entries past it
    truncate silently from recall).

Live-dir resolution order: ``--dir`` > ``autoMemoryDirectory`` in ``.claude/settings.json`` >
derived ``~/.claude/projects/<mangled-cwd>/memory``. The derived path is harness-specific and
version-fragile, so it is ALWAYS stat-verified — the doctor never asserts a path it did not
stat, and never reports a missing dir as a failure (your Claude Code may simply predate v2.1.59).

Exit code: 1 ONLY when a located live ``MEMORY.md`` is over budget (truncation is certain).
Every other case — missing dir, unresolved path, healthy index — exits 0 (advisory).

Does NOT: read or query fact contents, follow ``[[wiki-links]]``, verify your Claude Code
version, or write anything. It is a read-only wiring trip-wire, not a recall engine. Stdlib only.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# Keep in lockstep with tools/memory_audit.py — the harness MEMORY.md load budget.
INDEX_MAX_BYTES = 25_600   # Claude Code v2.1.59+ loads the first ~25 KB ...
INDEX_MAX_LINES = 200      # ... or the first 200 lines of MEMORY.md, whichever comes first.
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


def doctor(project: Path, explicit_dir: "Path | None", template: Path) -> "tuple[list[str], int]":
    """Return (report_lines, exit_code). Read-only. exit 1 only on a certain over-budget index."""
    lines: "list[str]" = []
    live, how = resolve_live_dir(project, explicit_dir)
    template_facts = _fact_count(template) if template.is_dir() else 0
    lines.append(f"Live (harness-loaded) memory dir: {live}")
    lines.append(f"  resolved via: {how}")
    lines.append(f"Repo template dir: {template}  ({template_facts} fact file(s))")

    if not live.is_dir():
        lines.append("  STATUS: live dir NOT found at the path above.")
        lines.append("  -> Facts curated only in the repo template are never recalled by the agent.")
        lines.append("     Copy your scaffold to the live path (or set autoMemoryDirectory), then re-run.")
        lines.append("     If you expected it to exist, pass --dir <path>; your Claude Code may also "
                     "predate v2.1.59 (native auto-memory).")
        return lines, 0  # advisory, NOT a failure — could be an older harness

    live_facts = _fact_count(live)
    lines.append(f"  STATUS: live dir found, {live_facts} fact file(s).")
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
