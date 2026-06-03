#!/usr/bin/env python3
"""Runnable demo for tools/skill_usage_report.py.

Builds a throwaway skills directory + a synthetic telemetry log in a temp dir, then runs the
report exactly as the CLI would — so you can see what the aggregator produces without wiring
the opt-in logger or waiting for real data to accumulate.

    python examples/skill_usage_demo.py
"""
from __future__ import annotations

import json
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.skill_usage_report import build_report  # noqa: E402


class _Args:
    """Stand-in for argparse.Namespace so the demo can call build_report() directly."""

    def __init__(self, log_path: Path, skills_dir: Path):
        self.log_path = str(log_path)
        self.skills_dir = str(skills_dir)
        self.days = 30
        self.since = None
        self.output = None
        self.json = False


def _make_skill(skills_dir: Path, name: str) -> None:
    d = skills_dir / name
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text(f"# {name}\n", encoding="utf-8")


def main() -> int:
    now = datetime.now()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        skills = root / ".claude" / "skills"
        # Three skills ship; one (deep-research) gets zero telemetry -> shows up as dormant.
        for name in ("awb-debug", "awb-review", "deep-research"):
            _make_skill(skills, name)

        log = root / ".claude" / ".logs" / "skill_usage.jsonl"
        log.parent.mkdir(parents=True)
        rows: list[dict] = []

        def add(skill: str, signal: str, days_ago: int, session: str) -> None:
            ts = (now - timedelta(days=days_ago)).isoformat(timespec="seconds")
            rows.append({"time": ts, "skill": skill, "signal": signal,
                         "prompt": f"p{len(rows)}", "session": session})

        add("awb-debug", "invoke", 1, "s1")    # heavily invoked, recent
        add("awb-debug", "invoke", 2, "s2")
        add("awb-debug", "invoke", 10, "s1")
        add("awb-review", "mention", 3, "s2")  # only ever mentioned (weak signal)
        add("awb-review", "mention", 12, "s3")
        add("example-ghost", "mention", 5, "s1")   # logged but not a shipped skill

        text = "\n".join(json.dumps(r) for r in rows) + "\n"
        text += "{not valid json}\n"               # one malformed line -> skipped-count path
        log.write_text(text, encoding="utf-8")

        print(build_report(_Args(log, skills), now))
    return 0


if __name__ == "__main__":
    sys.exit(main())
