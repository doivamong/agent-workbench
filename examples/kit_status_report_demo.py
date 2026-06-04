#!/usr/bin/env python3
"""Demo: generate a kit-status HTML report from a tiny synthetic project.

Builds a throwaway project tree in a temp dir (a couple of skills, a wired
telemetry log with a few events, a memory index), renders the report with
tools/kit_status_report.py, and prints where it landed. Stdlib only; run:

    python examples/kit_status_report_demo.py
"""
from __future__ import annotations

import json
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import kit_status_report as ksr  # noqa: E402


def build_demo_project(root: Path) -> Path:
    skills = {"awb-review": "guard", "awb-plan-then-code": "workflow",
              "awb-debug": "guard", "awb-tdd": "workflow"}  # awb-tdd will be a dead candidate
    sk = root / ".claude" / "skills"
    sk.mkdir(parents=True)
    rows = ["| name | tier | fires when | does NOT |", "|---|---|---|---|"]
    for name, tier in skills.items():
        (sk / name).mkdir()
        (sk / name / "SKILL.md").write_text(f"# {name}\n", encoding="utf-8")
        rows.append(f"| {name} | {tier} | ... | ... |")
    (sk / "skill-registry.md").write_text("\n".join(rows), encoding="utf-8")

    # wire telemetry so the report shows real fire-counts (and a dead candidate)
    (root / ".claude" / "settings.json").write_text(json.dumps({"hooks": {"UserPromptSubmit": [
        {"hooks": [{"type": "command", "command": "python .../skill_usage_logger.py"}]}]}}),
        encoding="utf-8")
    logs = root / ".claude" / ".logs"
    logs.mkdir(parents=True)
    fires = {"awb-review": 6, "awb-plan-then-code": 4, "awb-debug": 2}  # awb-tdd: 0
    lines = []
    for i, (name, n) in enumerate(fires.items()):
        for k in range(n):
            t = (datetime.now() - timedelta(days=(i + k) % 10)).isoformat(timespec="seconds")
            lines.append(json.dumps({"time": t, "skill": name, "signal": "invoke"}))
    (logs / "skill_usage.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")

    (root / "tools").mkdir()
    (root / "tools" / "leak_scan.py").write_text("# tool\n", encoding="utf-8")

    mem = root / "memory"
    mem.mkdir()
    (mem / "MEMORY.md").write_text("# index\n- [[fact-a]] a real fact\n", encoding="utf-8")
    (mem / "fact-a.md").write_text("body", encoding="utf-8")
    return root


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="awb_kit_status_demo_"))
    proj = build_demo_project(tmp)
    out = proj / "kit-status.html"
    html = ksr.render(ksr.gather(proj, days=14, gates_json=None))
    out.write_text(html, encoding="utf-8")
    print(f"Demo project: {proj}")
    print(f"Report:       {out}  ({len(html):,} bytes)")
    print("Open it in a browser — it is self-contained and works offline.")
    print("Note: awb-tdd has 0 fires + telemetry wired -> shown as 'ứng viên chết'.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
