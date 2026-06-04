#!/usr/bin/env python3
"""Demo: render the opt-in web dashboard from a tiny synthetic project.

Builds a throwaway project tree (a few skills, a wired telemetry log, a memory index),
points the ui/web Flask app at it, and uses Flask's TEST CLIENT to render the dashboard
page plus a couple of HTMX fragments to temp HTML files — no server, no open port. It
then checks the rendered page has no external network references (Chart.js + htmx are
vendored), proving the offline guarantee.

This is the kit's only dependency-bearing demo: it needs Flask (the opt-in ui/web dep).
If Flask isn't installed it prints the one-line install hint and exits 0 — still runnable.

    pip install -r ui/web/requirements.txt   # only if you want to run this demo
    python examples/ui_web_demo.py
"""
from __future__ import annotations

import json
import re
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def build_demo_project(root: Path) -> Path:
    skills = {"awb-review": "guard", "awb-plan-then-code": "workflow",
              "awb-debug": "guard", "awb-tdd": "workflow"}  # awb-tdd → dead candidate
    sk = root / ".claude" / "skills"
    sk.mkdir(parents=True)
    rows = ["| name | tier | fires when | does NOT |", "|---|---|---|---|"]
    for name, tier in skills.items():
        (sk / name).mkdir()
        (sk / name / "SKILL.md").write_text(f"# {name}\n", encoding="utf-8")
        rows.append(f"| {name} | {tier} | ... | ... |")
    (sk / "skill-registry.md").write_text("\n".join(rows), encoding="utf-8")

    # wire telemetry so the dashboard shows real fire-counts (and a dead candidate)
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
    sys.path.insert(0, str(ROOT / "ui" / "web"))
    try:
        import app as webapp  # noqa: E402  (needs Flask — the opt-in ui/web dependency)
    except (SystemExit, ImportError):
        # app.py raises SystemExit (with the install hint) when Flask is missing; catch a
        # bare ImportError too so any flask-absence variant skips cleanly rather than crashing.
        print("ui/web/ demo skipped — Flask not installed (it is opt-in).")
        print("Install it then re-run:  pip install -r ui/web/requirements.txt")
        return 0

    tmp = Path(tempfile.mkdtemp(prefix="awb_ui_web_demo_"))
    proj = build_demo_project(tmp)
    webapp.app.config.update(TESTING=True, DAYS=14, PROJECT=proj)
    client = webapp.app.test_client()

    # Render the full page + two HTMX fragments via the test client (no server/port).
    page = client.get("/").get_data(as_text=True)
    frag_days = client.get("/fragment?days=7").get_data(as_text=True)
    frag_tier = client.get("/fragment/skills?tier=guard").get_data(as_text=True)

    out = proj / "dashboard.html"
    out.write_text(page, encoding="utf-8")

    # Prove the offline guarantee: no external src/href in the rendered page.
    external = re.findall(r'(?:src|href)="https?://', page)

    print(f"Demo project: {proj}")
    print(f"Dashboard:    {out}  ({len(page):,} bytes)")
    print(f"External network refs in page: {len(external)} (0 = fully offline; Chart.js + htmx vendored)")
    print(f"HTMX day fragment (?days=7):   {len(frag_days):,} bytes, partial={'<html' not in frag_days}")
    print(f"HTMX tier filter (guard):      "
          f"{'awb-review' in frag_tier and 'awb-tdd' not in frag_tier} "
          f"(only guard skills; workflow filtered out)")
    print("Note: awb-tdd has 0 fires + telemetry wired -> shown as 'ứng viên chết'.")
    print("To view it live:  python ui/web/app.py  (then open http://127.0.0.1:5151)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
