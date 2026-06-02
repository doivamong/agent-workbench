#!/usr/bin/env python3
"""Summarize skill-usage telemetry — which skills fire, which are dead weight.

Reads the JSONL written by `.claude/hooks/scripts/skill_usage_logger.py` and produces a
per-skill summary over a time window, plus the skills that ship but never showed up
(dormant — candidates to prune, or whose trigger description needs work).

    python tools/skill_usage_report.py                     # last 30 days, markdown to stdout
    python tools/skill_usage_report.py --days 90
    python tools/skill_usage_report.py --since 2026-01-01
    python tools/skill_usage_report.py --json
    python tools/skill_usage_report.py --output report.md
    python tools/skill_usage_report.py --log-path L --skills-dir D   # override locations

WHAT THIS IS NOT — read before trusting a number:
- It counts NAME signals in prompts, a PROXY for use, not use itself:
    * a "mention" (bare name in passing) is often not a real use   -> false positives;
    * a skill the model auto-fires without the name being typed is NOT counted -> false negatives;
    * "invoke" (a `/<skill>` slash command) is the trustworthy signal — weight it accordingly.
- It needs the opt-in logger wired AND time to accumulate; an empty or short window says nothing.
- With only a handful of skills, just eyeball it — this earns its keep on a large skill library.
Use it to spot dead skills and to tune `USE WHEN` / `DO NOT TRIGGER`, never as ground truth.

Zero external dependencies — stdlib only.
"""
import argparse
import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

if sys.stdout is not None and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    except Exception:
        pass

DEFAULT_LOG = ".claude/.logs/skill_usage.jsonl"
DEFAULT_SKILLS = ".claude/skills"
DEFAULT_DAYS = 30
RECENT_DAYS = 7  # the report splits the window into "last 7 days" vs "prior" for a trend


def _project_dir() -> Path:
    return Path(os.environ.get("CLAUDE_PROJECT_DIR", "."))


def parse_log(log_path: Path, since: datetime) -> tuple[list[dict], int]:
    """Read the JSONL log; return (entries at/after `since`, count of malformed lines skipped).

    Each kept entry gets an `_at` key holding its parsed timestamp."""
    entries: list[dict] = []
    skipped = 0
    if not log_path.is_file():
        return entries, skipped
    with log_path.open("r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
                at = datetime.fromisoformat(row["time"])
            except (json.JSONDecodeError, KeyError, ValueError, TypeError):
                skipped += 1
                continue
            if at >= since:
                row["_at"] = at
                entries.append(row)
    return entries, skipped


def aggregate(entries: list[dict], recent_cutoff: datetime) -> dict[str, dict]:
    """Per-skill rollup. `recent_cutoff` separates the recent slice from the prior slice."""
    stats: dict[str, dict] = defaultdict(
        lambda: {"invoke": 0, "mention": 0, "total": 0, "prompts": set(),
                 "sessions": set(), "first": None, "last": None, "recent": 0, "prior": 0}
    )
    for e in entries:
        skill = e.get("skill", "<unknown>")
        at = e["_at"]
        s = stats[skill]
        s["total"] += 1
        if e.get("signal") == "invoke":
            s["invoke"] += 1
        else:
            s["mention"] += 1
        s["prompts"].add(e.get("prompt", ""))
        s["sessions"].add(e.get("session", ""))
        s["first"] = at if s["first"] is None or at < s["first"] else s["first"]
        s["last"] = at if s["last"] is None or at > s["last"] else s["last"]
        if at >= recent_cutoff:
            s["recent"] += 1
        else:
            s["prior"] += 1
    return stats


def discover_known_skills(skills_dir: Path) -> set[str]:
    """Skill names shipped in the project = subdirs of `.claude/skills/` holding a SKILL.md."""
    if not skills_dir.is_dir():
        return set()
    return {d.name for d in skills_dir.iterdir() if d.is_dir() and (d / "SKILL.md").is_file()}


def _trend(recent: int, prior: int) -> str:
    if recent > prior:
        return f"+{recent - prior}"
    if recent < prior:
        return f"-{prior - recent}"
    return "="


def _distinct(values: set) -> int:
    return len({v for v in values if v})


def format_markdown(stats: dict[str, dict], known: set[str], since: datetime,
                    now: datetime, window_days: int, skipped: int, log_path: Path) -> str:
    active = set(stats)
    dormant = sorted(known - active)
    out: list[str] = []
    out.append(f"# Skill usage — {now.strftime('%Y-%m-%d %H:%M')}")
    out.append("")
    out.append(f"**Window:** {since.strftime('%Y-%m-%d')} -> {now.strftime('%Y-%m-%d')} "
               f"({window_days} days) · **Log:** `{log_path}`")
    total = sum(s["total"] for s in stats.values())
    sessions = _distinct({sess for s in stats.values() for sess in s["sessions"]})
    out.append(f"**Signals:** {total} · **Distinct sessions:** {sessions} · "
               f"**Skills seen:** {len(active)}/{len(known) if known else '?'} · "
               f"**Malformed lines skipped:** {skipped}")
    out.append("")

    if not stats:
        out.append("> **No telemetry in this window.** The logger may not be wired "
                   "(`.claude/settings.json` `UserPromptSubmit`), the window may be too short, "
                   "or the log may have rotated to `*.jsonl.1`.")
        out.append("")
        out.append(_limits_note())
        return "\n".join(out)

    out.append(f"## Per skill (sorted by invokes, then total; last {RECENT_DAYS}d vs prior)")
    out.append("")
    out.append("| Skill | Invokes | Mentions | Sessions | First | Last | 7d |")
    out.append("|---|---|---|---|---|---|---|")
    ordered = sorted(stats.items(), key=lambda kv: (kv[1]["invoke"], kv[1]["total"]), reverse=True)
    for skill, s in ordered:
        first = s["first"].strftime("%m-%d") if s["first"] else "-"
        last = s["last"].strftime("%m-%d") if s["last"] else "-"
        out.append(f"| `{skill}` | {s['invoke']} | {s['mention']} | "
                   f"{_distinct(s['sessions'])} | {first} | {last} | {_trend(s['recent'], s['prior'])} |")
    out.append("")

    if dormant:
        out.append(f"## Dormant — shipped but 0 signals in window ({len(dormant)})")
        out.append("")
        out.append("Prune, or fix the trigger description so the skill actually fires:")
        out.append("")
        for name in dormant:
            out.append(f"- `{name}`")
        out.append("")

    out.append(_limits_note())
    return "\n".join(out)


def _limits_note() -> str:
    return ("---\n\n"
            "_Honest limit: these are NAME signals in prompts, a proxy. `invoke` (`/<skill>`) is "
            "trustworthy; `mention` is not (a name in passing is not a use), and a skill the model "
            "auto-fires without its name typed is invisible here. Use it to spot dead skills and "
            "tune triggers, not as ground truth._")


def format_json(stats: dict[str, dict], known: set[str], since: datetime,
                now: datetime, skipped: int) -> str:
    payload = {
        "generated_at": now.isoformat(timespec="seconds"),
        "window_start": since.isoformat(timespec="seconds"),
        "malformed_lines_skipped": skipped,
        "skills_seen": len(stats),
        "skills_known": len(known),
        "dormant": sorted(known - set(stats)),
        "per_skill": {
            skill: {
                "invoke": s["invoke"],
                "mention": s["mention"],
                "total": s["total"],
                "distinct_prompts": _distinct(s["prompts"]),
                "distinct_sessions": _distinct(s["sessions"]),
                "first_seen": s["first"].isoformat(timespec="seconds") if s["first"] else None,
                "last_seen": s["last"].isoformat(timespec="seconds") if s["last"] else None,
                "recent": s["recent"],
                "prior": s["prior"],
            }
            for skill, s in stats.items()
        },
    }
    return json.dumps(payload, indent=2, ensure_ascii=False)


def build_report(args, now: datetime) -> str:
    if args.since:
        since = datetime.strptime(args.since, "%Y-%m-%d")
        window_days = max((now - since).days, 0)
    else:
        since = now - timedelta(days=args.days)
        window_days = args.days

    log_path = Path(args.log_path)
    if not log_path.is_absolute():
        log_path = _project_dir() / log_path
    skills_dir = Path(args.skills_dir)
    if not skills_dir.is_absolute():
        skills_dir = _project_dir() / skills_dir

    entries, skipped = parse_log(log_path, since)
    stats = aggregate(entries, now - timedelta(days=RECENT_DAYS))
    known = discover_known_skills(skills_dir)

    if args.json:
        return format_json(stats, known, since, now, skipped)
    return format_markdown(stats, known, since, now, window_days, skipped, log_path)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Summarize skill-usage telemetry into a report.")
    p.add_argument("--log-path", default=DEFAULT_LOG, help=f"telemetry log (default: {DEFAULT_LOG})")
    p.add_argument("--skills-dir", default=DEFAULT_SKILLS,
                   help=f"skills directory for dormant detection (default: {DEFAULT_SKILLS})")
    p.add_argument("--days", type=int, default=DEFAULT_DAYS, help=f"window in days (default: {DEFAULT_DAYS})")
    p.add_argument("--since", help="explicit start date YYYY-MM-DD (overrides --days)")
    p.add_argument("--output", help="write to this file instead of stdout")
    p.add_argument("--json", action="store_true", help="emit JSON instead of markdown")
    args = p.parse_args(argv)

    if args.since:
        try:
            datetime.strptime(args.since, "%Y-%m-%d")
        except ValueError:
            print(f"error: --since must be YYYY-MM-DD, got {args.since!r}", file=sys.stderr)
            return 2

    report = build_report(args, datetime.now())
    if args.output:
        Path(args.output).write_text(report, encoding="utf-8")
        print(f"wrote {len(report)} bytes -> {args.output}", file=sys.stderr)
    else:
        print(report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
