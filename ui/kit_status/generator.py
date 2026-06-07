#!/usr/bin/env python3
"""kit_status_report.py — render a self-contained "kit status" HTML report.

Gathers REAL Agent-Workbench data from the project it runs in — skills + their
tiers and (if wired) telemetry fire-counts, installed tools, wired hooks, and the
MEMORY.md budget — and renders the status-rail layout (``ui/kit_status/template.html``)
with ``string.Template``. Stdlib only; the output is a single self-contained HTML
file with no external network (inline CSS + inline SVG), so it opens offline.

Honesty (this is the load-bearing part — see .claude/rules/measurement-honesty.md):
  - Telemetry is OPT-IN. If ``skill_usage_logger`` is not wired into settings.json,
    or the log is empty, skills are shown as ``chưa đo`` (NOT "dead") and the chart
    shows an empty state. A 0 in a window where the logger never ran is not a "dead
    skill" — it is an un-measured one, and the banner says so.
  - Gates are NOT run by this tool (running pytest/leak_scan is heavy and out of
    scope for a report). They show ``chưa chạy`` unless you pass ``--gates-json``.

Usage:
    python ui/kit_status/generator.py                      # -> kit-status.html
    python ui/kit_status/generator.py --output /tmp/x.html
    python ui/kit_status/generator.py --days 14 --open
    python ui/kit_status/generator.py --run-gates               # run read-only gates live
    python ui/kit_status/generator.py --gates-json gates.json   # {"leak_scan": true, ...}

What it does NOT do: it does not run the gates, does not measure skills the model
auto-fired without typing their name (telemetry only sees name signals in prompts),
and is a snapshot — re-run it to refresh.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta
from html import escape
from pathlib import Path
from string import Template

if hasattr(sys.stdout, "reconfigure"):  # legacy Windows console safety
    sys.stdout.reconfigure(encoding="utf-8")

HERE = Path(__file__).resolve().parent
TEMPLATE = HERE / "template.html"

# This generator lives in ui/kit_status/, so the kit's tools/ (with the shared
# memory_budget + memory_recall_doctor modules it reuses) is two levels up. Put that on
# the path so we REUSE the single sources of truth instead of re-deriving them. If those
# tools are not installed here (they are opt-in), the imports fall back honestly — never
# silently re-derive a wrong constant (.claude/rules/measurement-honesty.md).
_TOOLS = HERE.parent.parent / "tools"
sys.path.insert(0, str(_TOOLS))
try:
    from memory_budget import INDEX_MAX_BYTES  # type: ignore
except Exception:
    INDEX_MAX_BYTES = 25_600  # documented fallback; see tools/memory_budget.py
try:
    import memory_audit  # type: ignore — the hygiene tripwire; reused, never re-derived
except Exception:
    memory_audit = None  # opt-in tool absent → the panel degrades to budget-only, never a fake 0

# The EN/VI string catalog lives one level up in the stdlib core (ui/i18n.py). BOTH this report
# and the opt-in ui/web dashboard read from it, so their shared vocabulary (tier labels, the
# language whitelist, every translated string) can never drift apart. It is stdlib-only — no
# Flask — so importing it keeps this report dependency-free.
sys.path.insert(0, str(HERE.parent))
import i18n  # noqa: E402


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def _project_dir() -> Path:
    return Path(os.environ.get("CLAUDE_PROJECT_DIR", ".")).resolve()


def _fmt_num(x: float, lang: str = "vi") -> str:
    """Locale-aware decimal: VI uses a comma (5.9 -> '5,9'), EN keeps the period (5.9 -> '5.9').
    Integers stay bare. Without this the EN report showed VI-style '19,2 KB' / '5,8' avg/day."""
    if isinstance(x, int) or float(x).is_integer():
        return str(int(x))
    s = f"{x:.1f}"
    return s.replace(".", ",") if lang == "vi" else s


def _kpi_display(value, unit: str = "", extra: str = "") -> str:
    """A hero KPI figure. Numeric -> big display number; a state word
    ('chưa đo', 'chưa chạy', '—') -> muted, smaller, so it never shouts a non-number."""
    val = str(value)
    if re.fullmatch(r"[\d.,/%+-]+", val):
        u = f'<span class="kit-num__unit">{escape(unit)}</span>' if unit else ""
        return f'<span class="kit-num kit-num--display {extra}">{escape(val)}</span>{u}'
    return f'<span class="kit-num muted" style="font-size:var(--fs-lg);font-weight:600">{escape(val)}</span>'


def _run(cmd: list[str], cwd: Path) -> str | None:
    try:
        out = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True,
                             encoding="utf-8", timeout=30)
        return out.stdout if out.returncode == 0 else None
    except Exception:
        return None


TIER_OK = {"workflow", "guard", "feature", "audit", "meta"}


# --------------------------------------------------------------------------- #
# data gathering (each returns plain data; honesty handled here, not in markup)
# --------------------------------------------------------------------------- #
def parse_registry_tiers(proj: Path) -> dict[str, str]:
    """name -> tier, parsed from .claude/skills/skill-registry.md table rows."""
    reg = proj / ".claude" / "skills" / "skill-registry.md"
    tiers: dict[str, str] = {}
    if not reg.is_file():
        return tiers
    for line in reg.read_text(encoding="utf-8").splitlines():
        if not line.lstrip().startswith("|"):
            continue
        cells = [c.strip().strip("`_*") for c in line.strip().strip("|").split("|")]
        if len(cells) >= 2 and cells[1] in TIER_OK:
            tiers[cells[0]] = cells[1]
    return tiers


def discover_skills(proj: Path) -> list[str]:
    d = proj / ".claude" / "skills"
    if not d.is_dir():
        return []
    return sorted(p.name for p in d.iterdir() if p.is_dir() and (p / "SKILL.md").is_file())


def telemetry_wired(proj: Path) -> bool:
    s = proj / ".claude" / "settings.json"
    if not s.is_file():
        return False
    try:
        return "skill_usage_logger" in s.read_text(encoding="utf-8")
    except OSError:
        return False


def load_usage(proj: Path, days: int) -> tuple[dict[str, int], list[int], list[str], int]:
    """Returns (per_skill_total, daily_counts, day_labels, total).

    Reads .claude/.logs/skill_usage.jsonl directly. Empty/missing -> zeros."""
    log = proj / ".claude" / ".logs" / "skill_usage.jsonl"
    per: dict[str, int] = {}
    now = datetime.now()
    start = (now - timedelta(days=days - 1)).date()
    day_keys = [start + timedelta(days=i) for i in range(days)]
    daily = {d: 0 for d in day_keys}
    total = 0
    if log.is_file():
        for raw in log.read_text(encoding="utf-8", errors="ignore").splitlines():
            raw = raw.strip()
            if not raw:
                continue
            try:
                e = json.loads(raw)
                t = datetime.fromisoformat(e["time"]).date()
                name = e["skill"]
            except Exception:
                continue
            if t < start or t > now.date():
                continue
            per[name] = per.get(name, 0) + 1
            if t in daily:
                daily[t] += 1
            total += 1
    labels = [d.strftime("%d/%m") for d in day_keys]
    return per, [daily[d] for d in day_keys], labels, total


def installed_tools(proj: Path) -> tuple[list[str], list[str]]:
    """(present, missing) tool stems. 'missing' is derived from the kit self-inventory
    manifest if present; otherwise empty (we do not invent a 'full set')."""
    tdir = proj / "tools"
    present = sorted(p.stem for p in tdir.glob("*.py")) if tdir.is_dir() else []
    full: set[str] = set(present)
    manifest = proj / ".claude" / "manifest.json"
    if manifest.is_file():
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
            full = {Path(k).stem for k, v in data.get("files", {}).items()
                    if isinstance(v, dict) and v.get("category") == "tools"}
        except Exception:
            full = set(present)
    missing = sorted(full - set(present))
    return present, missing


def wired_hooks(proj: Path) -> tuple[list[str], int]:
    """(event names, total hook commands) from settings.json."""
    s = proj / ".claude" / "settings.json"
    if not s.is_file():
        return [], 0
    try:
        hooks = json.loads(s.read_text(encoding="utf-8")).get("hooks", {})
    except Exception:
        return [], 0
    events, total = [], 0
    for event, groups in hooks.items():
        n = sum(len(g.get("hooks", [])) for g in groups)
        if n:
            events.append(f"{event}×{n}" if n > 1 else event)
            total += n
    return events, total


def memory_health(proj: Path) -> dict:
    """MEMORY.md bytes vs budget, fact count, dangling [[links]]. Honest if absent."""
    # Prefer the live per-project dir; fall back to the repo memory/ folder.
    mem_dir = None
    used_live = False  # True only when the harness-loaded live dir was found (not the template)
    try:
        import memory_recall_doctor as mrd  # type: ignore
        live, _how = mrd.resolve_live_dir(proj, None)
        if live.is_dir():
            mem_dir = live
            used_live = True
    except (ImportError, OSError):
        mem_dir = None
    if mem_dir is None and (proj / "memory").is_dir():
        mem_dir = proj / "memory"
    if mem_dir is None:
        return {"present": False}
    index = mem_dir / "MEMORY.md"
    if not index.is_file():
        return {"present": False}
    raw = index.read_text(encoding="utf-8")
    used = len(raw.encode("utf-8"))
    facts = sorted(p.stem for p in mem_dir.glob("*.md")
                   if p.name not in ("MEMORY.md", "README.md"))
    targets = set(facts)
    dangling = sorted({m for m in re.findall(r"\[\[([^\]]+)\]\]", raw) if m not in targets})
    health = {"present": True, "live": used_live, "used": used, "budget": INDEX_MAX_BYTES,
              "facts": len(facts), "dangling": len(dangling)}
    # Enrich with the fuller hygiene summary (orphans, near-dups, frontmatter errors) the panel
    # would otherwise miss — it sees only `dangling`. Reused from memory_audit, not re-derived.
    # Absent keys (tool not installed, or a scan error) mean the panel shows budget-only rather
    # than inventing zeros — an un-measured count is not a clean 0 (measurement-honesty).
    if memory_audit is not None:
        try:
            findings = memory_audit.audit(mem_dir)
            health["errors"] = sum(1 for sev, _, _ in findings if sev == "error")
            health["warns"] = sum(1 for sev, _, _ in findings if sev == "warn")
        except Exception:
            pass
    return health


def git_meta(proj: Path) -> tuple[str, str]:
    branch = (_run(["git", "branch", "--show-current"], proj) or "").strip() or "—"
    commit = (_run(["git", "rev-parse", "--short", "HEAD"], proj) or "").strip() or "—"
    return branch, commit


# Read-only gates safe to run from a report (NOT pytest — slow; opt-in via --run-gates).
READONLY_GATES = [
    ("leak_scan", ["leak_scan.py", ".", "--entropy", "--fail-on-find", "--respect-gitignore"]),
    ("invariants", ["invariants.py", ".", "--allow", "known_violations.json"]),
    ("skill_lint", ["skill_lint.py"]),
]


def run_readonly_gates(proj: Path) -> dict[str, bool]:
    """Run the read-only gates present in this project; returncode 0 == PASS.
    A gate whose tool (or a referenced file) is missing is SKIPPED, not failed —
    an absent tool is not a red gate (measurement-honesty: don't invent a result)."""
    results: dict[str, bool] = {}
    for name, argv in READONLY_GATES:
        tool = proj / "tools" / argv[0]
        if not tool.is_file():
            continue
        cmd = [sys.executable, str(tool), *argv[1:]]
        if "--allow" in cmd and not (proj / "known_violations.json").is_file():
            i = cmd.index("--allow")
            del cmd[i:i + 2]
        try:
            r = subprocess.run(cmd, cwd=str(proj), capture_output=True, timeout=120)
            results[name] = r.returncode == 0
        except Exception:
            pass  # a gate we cannot run is omitted, never shown as a false fail
    return results


# --------------------------------------------------------------------------- #
# fragment builders (return full HTML blocks matching the template placeholders)
# --------------------------------------------------------------------------- #
DOT = {"workflow": "dot--workflow", "guard": "dot--guard", "feature": "dot--feature",
       "audit": "dot--audit", "meta": "dot--meta"}


def build(ctx: dict, lang: str = i18n.DEFAULT_LANG) -> dict[str, str]:
    lang = i18n.normalize_lang(lang)
    t = i18n.report_catalog(lang)
    f: dict[str, str] = {}
    # Document-chrome strings substituted into template.html (the bits outside the fragment
    # placeholders): the <html lang>, <title>, skip link, and the rail's aria/screen labels.
    f["lang"] = lang
    f["page_title"] = t["page_title"]
    f["skip_to_content"] = t["skip_to_content"]
    f["rail_aria"] = t["rail_aria"]
    f["rail_screen"] = t["rail_screen"]
    cfg_wired = ctx["wired"]
    total = ctx["total"]
    # "wired" below means MEASURED = configured AND has data. A logger just wired with an
    # empty log must NOT turn every 0-fire skill into a "dead candidate" — that 0 is
    # not-yet-measured, not dead (see .claude/rules/measurement-honesty.md, trap #1).
    wired = cfg_wired and total > 0
    n_skills = len(ctx["skills"])
    dead = ctx["dead_candidates"]
    # Any 0-fire skill (guard OR non-guard) means the measured-state caveat is relevant —
    # a guard's "tự gọi" badge needs explaining even when `dead` (non-guard zeros) is 0.
    n_zero = sum(1 for s in ctx["skills"] if wired and s["fired"] == 0)
    tools_present, tools_missing = ctx["tools_present"], ctx["tools_missing"]
    n_tools_full = len(tools_present) + len(tools_missing)
    events, n_hooks = ctx["events"], ctx["n_hooks"]
    mem = ctx["mem"]
    gates = ctx["gates"]
    branch, commit, today = ctx["branch"], ctx["commit"], ctx["today"]

    skills_lbl = t["state_unmeasured"] if not wired else t["rk_skills_sub_measured"].format(dead=dead)
    tools_lbl = f"{len(tools_present)}/{n_tools_full}"
    mem_pct = round(mem["used"] / mem["budget"] * 100) if mem.get("present") else 0
    mem_pct_lbl = f"{mem_pct}%" if mem.get("present") else "—"
    gates_lbl = f"{sum(gates.values())}/{len(gates)}" if gates else t["state_not_run"]

    # --- honesty banner (3 states: not-wired / wired-but-no-data / measured) #
    def _banner(title: str, sub: str) -> str:
        return ('<div class="overall" role="status" style="margin:0 0 var(--sp-5);'
            'background:var(--warn-dim);border-color:var(--warn)">'
            '<span class="overall__pulse" aria-hidden="true" style="background:var(--warn)"></span>'
            f'<span class="overall__txt"><span class="overall__title">{title}</span>'
            f'<span class="overall__sub">{sub}</span></span></div>')
    if not cfg_wired:
        f["honesty_banner"] = _banner(t["banner_notwired_title"], t["banner_notwired_body"])
    elif not wired:  # configured, but the log is still empty
        f["honesty_banner"] = _banner(t["banner_empty_title"], t["banner_empty_body"])
    else:
        # MEASURED state. The two banners above only fire when NOT measured, so this is the
        # one state that prints the 0-fire labels — and it must carry the caveat that the
        # metric only counts skills NAMED in a prompt (model-auto-fired skills, esp. guards,
        # are invisible here). Neutral surface, NOT the amber warn banner: an un-named skill
        # is information, not an error. See .claude/rules/measurement-honesty.md (trap #2).
        f["honesty_banner"] = ("" if not n_zero else
            '<div role="status" style="margin:0 0 var(--sp-5);padding:var(--sp-3) var(--sp-4);'
            'border:1px solid var(--border);border-radius:var(--r-md);background:var(--surface-2);'
            'color:var(--text-dim);font-size:var(--fs-sm);line-height:1.5">'
            f'{t["banner_measured"]}</div>')

    # --- rail -------------------------------------------------------------- #
    ok = "kit-num--ok"
    warn = "kit-num--warn"
    f["rail_overall"] = (
        '<div class="overall" role="status"><span class="overall__pulse" aria-hidden="true"></span>'
        '<span class="overall__txt"><span class="overall__title">%s</span>'
        '<span class="overall__sub">%s</span></span></div>' % (
            (t["rail_overall_ok"] if gates and all(gates.values()) else t["rail_overall_status"]),
            (t["rail_overall_pass"].format(lbl=gates_lbl) if gates else t["rail_overall_norun"])))

    def rk(label, sub, val, cls):
        return ('<div class="rail-kpi"><span class="rail-kpi__meta">'
                f'<span class="rail-kpi__label">{label}</span>'
                f'<span class="rail-kpi__sub">{escape(sub)}</span></span>'
                f'<span class="rail-kpi__val"><span class="kit-num kit-num--lg {cls}">{val}</span></span></div>')
    f["rail_kpis"] = (f'<div class="rail-kpis" aria-label="{t["rail_kpis_aria"]}">'
        + rk(t["rk_skills"], skills_lbl, n_skills, ok)  # un-named ≠ error: never amber (fix B)
        + rk(t["rk_gates"], "leak · inv · lint · pytest", gates_lbl, ok if gates and all(gates.values()) else warn)
        + rk(t["rk_tools"], t["rk_tools_sub"].format(n=len(tools_missing)), tools_lbl, ok if not tools_missing else warn)
        + rk(t["rk_hooks"], t["rk_hooks_sub"], n_hooks, ok)
        + '</div>')

    def nav(href, label, count):
        return f'<a href="#{href}">{label} <span class="railnav__count">{count}</span></a>'
    f["rail_nav"] = (f'<nav class="railnav" aria-label="{t["nav_cap"]}"><span class="railnav__cap">{t["nav_cap"]}</span>'
        + nav("gates", t["nav_gates"], gates_lbl)
        + nav("skills", t["nav_skills"], n_skills)
        + nav("telemetry", t["nav_telemetry"], total if wired else "—")
        + nav("tools", t["nav_tools"], tools_lbl)
        + nav("memory", t["nav_memory"], mem_pct_lbl)
        + nav("hooks", t["nav_hooks"], n_hooks) + '</nav>')

    f["rail_foot"] = ('<div class="rail__foot hairline-soft" style="padding-top:var(--sp-3)">'
        f'{t["rail_foot_branch"]} <span class="mono">{escape(branch)}</span> · <span class="mono">{escape(commit)}</span><br>'
        f'{t["rail_foot_updated"].format(today=today)}</div>')

    # --- hero -------------------------------------------------------------- #
    tele_kpi = _kpi_display(total, t["unit_times"], "kit-num--accent") if wired else _kpi_display(t["state_unmeasured"])
    tele_sub = (t["hero_tele_sub_measured"].format(avg=_fmt_num(total / max(ctx["days"], 1), lang))
                if wired else t["hero_tele_sub_unmeasured"])
    gates_val = _kpi_display(gates_lbl, "PASS" if gates else "",
                             "kit-num--ok" if gates and all(gates.values()) else "")
    mem_hero = _kpi_display(mem_pct, "%") if mem.get("present") else _kpi_display("—")
    tele_phrase = (t["tele_phrase_measured"].format(total=total, days=ctx["days"]) if wired
                   else t["tele_phrase_empty"] if cfg_wired else t["tele_phrase_notwired"])
    mem_sub = (t["hero_mem_sub_present"].format(used=_fmt_num(mem["used"] / 1024, lang),
                                                budget=round(mem["budget"] / 1024), facts=mem["facts"])
               if mem.get("present") else t["hero_mem_sub_absent"])
    f["hero"] = (
        f'<section class="hero panel" aria-label="{t["hero_aria"]}"><div class="statushero">'
        '<div class="statushero__top"><div>'
        f'<div class="sec__eyebrow">{t["hero_eyebrow"]}</div>'
        f'<h1>{t["hero_h1"].format(today=today)}</h1>'
        '<p class="muted" style="margin-top:var(--sp-2);max-width:54ch">'
        f'{t["hero_lead"].format(n_skills=n_skills, n_hooks=n_hooks, tele_phrase=tele_phrase)}</p>'
        '</div><div class="statushero__meta">'
        '<span class="env-pill"><span class="env-pill__live" aria-hidden="true"></span> LOCAL</span>'
        f'<span class="env-pill">{t["pill_branch"]} <span class="kit-num">{escape(branch)}</span></span>'
        f'<span class="env-pill">{t["pill_commit"]} <span class="kit-num">{escape(commit)}</span></span>'
        '</div></div>'
        '<div class="row wrap" style="gap:var(--sp-6);border-top:1px solid var(--border-soft);padding-top:var(--sp-4)">'
        f'<div class="kpi"><span class="kpi__label">{t["hero_kpi_namecalls"].format(days=ctx["days"])}</span>'
        f'<span class="kpi__value">{tele_kpi}</span><span class="kpi__sub">{tele_sub}</span></div>'
        f'<div class="kpi"><span class="kpi__label">{t["hero_kpi_gates"]}</span>'
        f'<span class="kpi__value">{gates_val}</span>'
        '<span class="kpi__sub">leak · invariants · lint · pytest</span></div>'
        f'<div class="kpi"><span class="kpi__label">{t["hero_kpi_mem"]}</span>'
        f'<span class="kpi__value">{mem_hero}</span><span class="kpi__sub">{mem_sub}</span></div>'
        '</div></div></section>')

    # --- gates ------------------------------------------------------------- #
    if gates:
        cards = ""
        names = {"leak_scan": t["gate_name_leak_scan"], "invariants": t["gate_name_invariants"],
                 "skill_lint": t["gate_name_skill_lint"], "pytest": t["gate_name_pytest"]}
        for name, passed in gates.items():
            state = "PASS" if passed else "FAIL"
            icon_col = "" if passed else 'style="color:var(--danger)"'
            cards += (f'<div class="gate-card"><span class="gate-card__icon" aria-hidden="true" {icon_col}>'
                '<svg viewBox="0 0 24 24" width="15" height="15"><path d="M5 12.5l4 4 10-10" '
                'stroke-linecap="round" stroke-linejoin="round"/></svg></span>'
                f'<span class="gate-card__body"><span class="gate-card__name">{escape(name)}</span>'
                f'<span class="gate-card__detail">{escape(names.get(name, ""))}</span></span>'
                f'<span class="gate-card__state">{state}</span></div>')
        badge = f'<span class="badge badge--{"ok" if all(gates.values()) else "danger"}">{gates_lbl} PASS</span>'
        body = (f'<div class="gate-grid">{cards}</div>'
                f'<p class="section-foot">{t["gates_foot"]}</p>')
    else:
        badge = f'<span class="badge badge--warn">{t["state_not_run"]}</span>'
        body = ('<div class="empty"><span class="empty__icon" aria-hidden="true">'
                '<svg viewBox="0 0 24 24" width="26" height="26" fill="none" stroke="currentColor" stroke-width="1.6">'
                '<path d="M12 8v5m0 3h.01M12 3l9 16H3l9-16Z" stroke-linecap="round" stroke-linejoin="round"/></svg></span>'
                f'<span class="empty__title">{t["gates_empty_title"]}</span>'
                f'<span class="empty__msg">{t["gates_empty_msg"]}</span></div>')
    f["gates"] = ('<section class="sec" id="gates" aria-labelledby="h-gates"><div class="sec__head"><div>'
        f'<div class="sec__eyebrow">{t["gates_eyebrow"]}</div><h2 id="h-gates">{t["gates_h2"]}</h2></div>'
        f'{badge}</div><div class="surface panel">{body}</div></section>')

    # --- skills ------------------------------------------------------------ #
    rows, maxv = "", max([s["fired"] for s in ctx["skills"]] + [1])
    for s in ctx["skills"]:
        dotc = DOT.get(s["tier"], "dot--workflow")
        if not wired:
            spark = f'<span class="muted" style="font-size:var(--fs-xs)">{t["state_unmeasured"]}</span>'
            status = f'<span class="badge">{t["state_unmeasured"]}</span>'
            numcell = '<td class="num num--zero">—</td>'
        elif s["fired"] == 0:
            numcell = '<td class="num num--zero">0</td>'
            if s["tier"] == "guard":  # auto-fired by design → a prompt-name 0 is expected, not dead
                spark = f'<span class="muted" style="font-size:var(--fs-xs)">{t["skill_guard_spark"]}</span>'
                status = (f'<span class="badge badge--dead" title="{t["skill_guard_title"]}">'
                          f'{t["skill_guard_badge"]}</span>')
            else:
                spark = f'<span class="muted" style="font-size:var(--fs-xs)">{t["skill_zero_spark"]}</span>'
                status = (f'<span class="badge badge--dead" title="{t["skill_dead_title"]}">'
                          f'{t["skill_dead_badge"]}</span>')
        else:
            h = max(2, round(s["fired"] / maxv * 18))
            spark = f'<span class="sparkbar" aria-hidden="true"><i class="hi" style="height:{h}px"></i></span>'
            status = f'<span class="badge badge--ok">{t["skill_named_badge"]}</span>'
            numcell = f'<td class="num">{s["fired"]}</td>'
        rows += (f'<tr><td><span class="cell-skill"><span class="dot {dotc}"></span>{escape(s["name"])}</span></td>'
                 f'<td class="muted">{escape(s["tier"])}</td>{numcell}'
                 f'<td><div class="cell-spark">{spark}</div></td><td>{status}</td></tr>')
    head_badges = (f'<span class="badge"><span class="kit-num">{n_skills}</span>&nbsp;{t["badge_n_skills"]}</span>'
        + ('' if not wired else f'<span class="badge badge--dead"><span class="kit-num">{dead}</span>&nbsp;{t["skill_dead_badge"]}</span>'))
    f["skills"] = ('<section class="sec" id="skills" aria-labelledby="h-skills"><div class="sec__head"><div>'
        f'<div class="sec__eyebrow">{t["skills_eyebrow"]}</div><h2 id="h-skills">{t["skills_h2"]}</h2></div>'
        f'<div class="row" style="gap:var(--sp-2)">{head_badges}</div></div>'
        '<div class="surface panel"><div class="panel__head" style="margin-bottom:var(--sp-3)">'
        f'<h4>{t["skills_panel_head"]}</h4><span class="label">{t["skills_panel_hint"]}</span></div>'
        f'<table class="tbl tbl--zebra"><thead><tr><th scope="col">{t["th_skill"]}</th><th scope="col">{t["th_tier"]}</th>'
        f'<th scope="col" class="num">{t["th_namecalls"]}</th><th scope="col" class="num">{t["th_ratio"]}</th>'
        f'<th scope="col">{t["th_signal"]}</th></tr></thead><tbody>{rows}</tbody></table></div></section>')

    # --- telemetry --------------------------------------------------------- #
    if wired and total > 0:
        series, labels = ctx["daily"], ctx["labels"]
        n = len(series)
        mx = max(series + [1])
        x0, x1, y0, ybase = 40, 704, 20, 206
        xs = [x0 + i * (x1 - x0) / max(n - 1, 1) for i in range(n)]
        ys = [ybase - (v / mx) * (ybase - y0) for v in series]
        line = "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in zip(xs, ys))
        area = line + f" L{x1},{ybase} L{x0},{ybase} Z"
        peak_i = series.index(mx)
        dots = "".join(
            f'<circle class="viz-dot--hi" cx="{xs[i]:.1f}" cy="{ys[i]:.1f}" r="4.5"/>' if i == peak_i
            else f'<circle class="viz-dot" cx="{xs[i]:.1f}" cy="{ys[i]:.1f}" r="2.6"/>'
            for i in range(n))
        xlabels = "".join(
            f'<text class="viz-axis-label" x="{xs[i]:.1f}" y="224" text-anchor="middle">{labels[i]}</text>'
            for i in range(0, n, max(1, n // 7)))
        svg = (f'<svg class="viz" viewBox="0 0 720 240" role="img" aria-label="{t["tele_chart_aria"].format(n=n)}">'
            '<defs><linearGradient id="vizAreaGrad" x1="0" y1="0" x2="0" y2="1">'
            '<stop offset="0%" stop-color="#CC2929" stop-opacity="0.28"/>'
            '<stop offset="55%" stop-color="#CC2929" stop-opacity="0.07"/>'
            '<stop offset="100%" stop-color="#CC2929" stop-opacity="0"/></linearGradient></defs>'
            f'<line class="viz-baseline" x1="40" y1="206" x2="704" y2="206"/>'
            f'<path class="viz-area" d="{area}"/><path class="viz-line" d="{line}"/>{dots}'
            f'<text class="viz-peak-label" x="{xs[peak_i]:.1f}" y="{ys[peak_i]-8:.1f}" text-anchor="middle">{mx} · {labels[peak_i]}</text>'
            f'{xlabels}</svg>')
        avg = _fmt_num(total / max(n, 1), lang)
        kpis = (f'<div class="kpi"><span class="kpi__label">{t["tele_total_label"].format(n=n)}</span><span class="kpi__value">'
            f'<span class="kit-num kit-num--xl kit-num--accent">{total}</span><span class="kit-num__unit">{t["unit_times"]}</span></span></div>'
            f'<div class="kpi"><span class="kpi__label">{t["tele_avg_label"]}</span><span class="kpi__value">'
            f'<span class="kit-num kit-num--xl">{avg}</span><span class="kit-num__unit">{t["unit_times_per_day"]}</span></span></div>'
            f'<div class="kpi"><span class="kpi__label">{t["tele_peak_label"]}</span><span class="kpi__value">'
            f'<span class="kit-num kit-num--xl kit-num--accent">{mx}</span><span class="kit-num__unit">{t["tele_peak_unit"].format(label=labels[peak_i])}</span></span></div>')
        tbadge = f'<span class="badge"><span class="kit-num">{total}</span>&nbsp;{t["tele_badge_total"]}</span>'
        inner = (f'<div class="row wrap" style="gap:var(--sp-6);margin-bottom:var(--sp-5)">{kpis}</div>{svg}'
                 f'<p class="section-foot">{t["tele_foot"]}</p>')
    else:
        tbadge = f'<span class="badge badge--warn">{t["state_unmeasured"]}</span>'
        inner = ('<div class="empty"><span class="empty__icon" aria-hidden="true">'
            '<svg viewBox="0 0 24 24" width="26" height="26" fill="none" stroke="currentColor" stroke-width="1.6">'
            '<path d="M4 19V5m0 14h16M8 15l3-4 3 2 4-6" stroke-linecap="round" stroke-linejoin="round"/></svg></span>'
            f'<span class="empty__title">{t["tele_empty_title"]}</span>'
            f'<span class="empty__msg">{t["tele_empty_msg"]}</span></div>')
    f["telemetry"] = ('<section class="sec" id="telemetry" aria-labelledby="h-telemetry"><div class="sec__head"><div>'
        f'<div class="sec__eyebrow">{t["tele_eyebrow"]}</div><h2 id="h-telemetry">{t["tele_h2"]}</h2></div>'
        f'{tbadge}</div><div class="surface panel">{inner}</div></section>')

    # --- tools ------------------------------------------------------------- #
    pct = round(len(tools_present) / n_tools_full * 100) if n_tools_full else 100
    circ = 301.59
    dash = circ * len(tools_present) / n_tools_full if n_tools_full else circ
    if tools_missing:
        miss = "".join('<span class="tool-miss"><svg viewBox="0 0 24 24" width="13" height="13">'
            '<path d="M12 8v5m0 3h.01M12 3l9 16H3l9-16Z" stroke-linecap="round" stroke-linejoin="round"/></svg>'
            f'{escape(m)}</span>' for m in tools_missing)
        right = ('<div class="row row--between" style="margin-bottom:var(--sp-3)">'
            f'<h4>{t["tools_missing_head"]} <span class="kit-num kit-num--accent">{len(tools_missing)}</span></h4>'
            f'<span class="label">{t["tools_missing_hint"]}</span></div>'
            f'<div class="tools-missing">{miss}</div>')
        tbadge2 = f'<span class="badge badge--warn"><span class="kit-num">{tools_lbl}</span>&nbsp;· {t["tools_badge_missing"].format(n=len(tools_missing))}</span>'
    else:
        right = (f'<div class="empty" style="padding:var(--sp-4)"><span class="empty__title">{t["tools_complete_title"]}</span>'
            f'<span class="empty__msg">{t["tools_complete_msg"]}</span></div>')
        tbadge2 = f'<span class="badge badge--ok"><span class="kit-num">{tools_lbl}</span>&nbsp;· {t["tools_badge_ok"]}</span>'
    f["tools"] = ('<section class="sec" id="tools" aria-labelledby="h-tools"><div class="sec__head"><div>'
        f'<div class="sec__eyebrow">{t["tools_eyebrow"]}</div><h2 id="h-tools">{t["tools_h2"]}</h2></div>'
        f'{tbadge2}</div><div class="surface panel"><div class="tools-grid"><div class="tools-donut">'
        '<svg viewBox="0 0 120 120" width="148" height="148" role="img" '
        f'aria-label="{t["tools_donut_aria"].format(present=len(tools_present), full=n_tools_full)}">'
        '<circle cx="60" cy="60" r="48" fill="none" stroke="var(--surface-3)" stroke-width="12"/>'
        f'<circle cx="60" cy="60" r="48" fill="none" stroke="var(--{"ok" if not tools_missing else "warn"})" stroke-width="12" '
        f'stroke-linecap="round" stroke-dasharray="{dash:.2f} {circ}" transform="rotate(-90 60 60)"/>'
        f'<text x="60" y="56" text-anchor="middle" class="kit-num" style="font-size:23px;fill:var(--text-strong)">{tools_lbl}</text>'
        f'<text x="60" y="76" text-anchor="middle" style="font-size:11px;fill:var(--text-dim);font-family:var(--font-sans);letter-spacing:.08em">{t["tools_donut_caption"]}</text>'
        f'</svg><div class="meter meter--{"ok" if not tools_missing else "warn"}" style="width:100%">'
        f'<span class="meter__fill" style="width:{pct}%"></span></div>'
        f'<span class="kpi__sub">{t["tools_pct_sub"].format(pct=pct)}</span></div><div>{right}</div></div></div></section>')

    # --- memory ------------------------------------------------------------ #
    if mem.get("present"):
        used_kb = _fmt_num(mem["used"] / 1024, lang)
        bud_kb = round(mem["budget"] / 1024)
        free_kb = _fmt_num(max(mem["budget"] - mem["used"], 0) / 1024, lang)
        sev = "warn" if mem_pct >= 75 else "ok"
        dang = mem["dangling"]
        # The fuller hygiene line — only when memory_audit actually ran (keys present). Absent =>
        # the panel stays budget-only rather than printing a fabricated "0 errors" (measurement-honesty).
        audit_foot = (f'<p class="section-foot">{t["mem_audit_summary"].format(errors=mem["errors"], warns=mem["warns"])}</p>'
                      if "warns" in mem else "")
        # Day-1-empty signal: the live recall is empty (fresh clone) or we fell back to the repo
        # template — say so plainly so the panel can't read as a green "memory works" (mirrors the
        # recall_doctor day-1-empty WARN).
        day1_foot = (f'<p class="section-foot">{t["mem_day1_empty"]}</p>'
                     if (not mem.get("live") or mem["facts"] == 0) else "")
        mbadge = f'<span class="badge badge--{sev}"><span class="kit-num">{mem_pct}%</span>&nbsp;{t["mem_badge_used"]}</span>'
        body = ('<div class="mem-grid"><div>'
            '<div class="row row--between row--baseline" style="margin-bottom:var(--sp-2)">'
            f'<span class="kpi__value"><span class="kit-num kit-num--xl kit-num--{sev}">{used_kb}</span>'
            f'<span class="kit-num__unit">/ {bud_kb} KB</span></span>'
            f'<span class="kit-num kit-num--lg">{mem_pct}<span class="kit-num__unit">%</span></span></div>'
            f'<div class="meter meter--{sev}" aria-label="{t["mem_meter_aria"].format(pct=mem_pct)}">'
            f'<span class="meter__fill" style="width:{mem_pct}%"></span></div>'
            f'<p class="section-foot">{t["mem_free"].format(free=free_kb)}'
            f'{t["mem_over"] if mem_pct>=75 else "."}</p>'
            + day1_foot + audit_foot + '</div>'
            '<div class="mem-stats">'
            f'<div class="mem-stat surface-2 panel--tight"><span class="kpi__label">{t["mem_stat_facts"]}</span><span class="kit-num kit-num--lg">{mem["facts"]}</span></div>'
            f'<div class="mem-stat surface-2 panel--tight"><span class="kpi__label">{t["mem_stat_dangling"]}</span><span class="kit-num kit-num--lg {"kit-num--accent" if dang else ""}">{dang}</span></div>'
            f'<div class="mem-stat surface-2 panel--tight"><span class="kpi__label">{t["mem_stat_used"]}</span><span class="kit-num kit-num--lg">{used_kb}<span class="kit-num__unit">KB</span></span></div>'
            f'<div class="mem-stat surface-2 panel--tight"><span class="kpi__label">{t["mem_stat_budget"]}</span><span class="kit-num kit-num--lg">{bud_kb}<span class="kit-num__unit">KB</span></span></div>'
            '</div></div>')
    else:
        mbadge = '<span class="badge badge--warn">—</span>'
        body = (f'<div class="empty"><span class="empty__title">{t["mem_empty_title"]}</span>'
            f'<span class="empty__msg">{t["mem_empty_msg"]}</span></div>')
    f["memory"] = ('<section class="sec" id="memory" aria-labelledby="h-memory"><div class="sec__head"><div>'
        f'<div class="sec__eyebrow">{t["mem_eyebrow"]}</div><h2 id="h-memory">{t["mem_h2"]}</h2></div>'
        f'{mbadge}</div><div class="surface panel">{body}</div></section>')

    # --- hooks ------------------------------------------------------------- #
    chips = "".join(f'<span class="hook-chip"><span class="hook-chip__dot"></span>{escape(e)}</span>' for e in events) \
        or f'<span class="muted">{t["hooks_empty"]}</span>'
    f["hooks"] = ('<section class="sec" id="hooks" aria-labelledby="h-hooks"><div class="sec__head"><div>'
        f'<div class="sec__eyebrow">{t["hooks_eyebrow"]}</div><h2 id="h-hooks">{t["hooks_h2"]}</h2></div>'
        f'<span class="badge badge--ok"><span class="kit-num">{n_hooks}</span>&nbsp;{t["hooks_badge"]}</span></div>'
        '<div class="surface panel"><div class="row wrap" style="gap:var(--sp-6)">'
        f'<div class="kpi"><span class="kpi__label">{t["hooks_total_label"]}</span><span class="kpi__value">'
        f'<span class="kit-num kit-num--xl kit-num--ok">{n_hooks}</span></span>'
        f'<span class="kpi__sub">{t["hooks_events_sub"].format(n=len(events))}</span></div></div>'
        f'<div class="hook-events">{chips}</div></div></section>')

    # --- footer ------------------------------------------------------------ #
    f["footer"] = ('<footer class="rail__foot" style="text-align:center;padding:var(--sp-5) 0">'
        f'Agent Workbench · {t["footer_label"]} '
        f'<span class="mono">{escape(commit)}</span> · {today}</footer>')
    return f


# --------------------------------------------------------------------------- #
# orchestration
# --------------------------------------------------------------------------- #
def gather(proj: Path, days: int, gates_json: str | None, run_gates: bool = False) -> dict:
    tiers = parse_registry_tiers(proj)
    names = discover_skills(proj) or sorted(tiers)
    wired = telemetry_wired(proj)
    per, daily, labels, total = load_usage(proj, days)
    skills = [{"name": n, "tier": tiers.get(n, "workflow"), "fired": per.get(n, 0)} for n in names]
    skills.sort(key=lambda s: (-s["fired"], s["name"]))
    measured = wired and total > 0  # configured AND has data; an empty log != dead skills
    # Exclude guard-tier skills: they are DESIGNED to be model-auto-fired, not typed by name,
    # so a prompt-name count of 0 is structural, not a sign of disuse. Counting them would
    # cry-wolf and train the owner to ignore the signal. They still render (own neutral badge).
    dead = sum(1 for s in skills if measured and s["fired"] == 0 and s["tier"] != "guard")
    tools_present, tools_missing = installed_tools(proj)
    events, n_hooks = wired_hooks(proj)
    gates: dict[str, bool] = run_readonly_gates(proj) if run_gates else {}
    if gates_json:
        try:
            gates.update({str(k): bool(v) for k, v in
                          json.loads(Path(gates_json).read_text(encoding="utf-8")).items()})
        except Exception as e:
            print(f"warning: could not read --gates-json ({e}); showing 'chưa chạy'", file=sys.stderr)
    branch, commit = git_meta(proj)
    return {"skills": skills, "wired": wired, "daily": daily, "labels": labels,
            "total": total, "dead_candidates": dead, "tools_present": tools_present,
            "tools_missing": tools_missing, "events": events, "n_hooks": n_hooks,
            "mem": memory_health(proj), "gates": gates, "branch": branch, "commit": commit,
            "today": datetime.now().strftime("%d/%m/%Y"), "days": days}


def render(ctx: dict, lang: str = i18n.DEFAULT_LANG) -> str:
    tmpl = Template(TEMPLATE.read_text(encoding="utf-8"))
    return tmpl.substitute(build(ctx, lang))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Render a self-contained kit-status HTML report.")
    ap.add_argument("--output", default="kit-status.html", help="output HTML path (default: kit-status.html)")
    ap.add_argument("--days", type=int, default=14, help="telemetry window in days (default: 14)")
    ap.add_argument("--gates-json", help='JSON map {"leak_scan": true, ...}; absent -> "chưa chạy"')
    ap.add_argument("--run-gates", action="store_true",
                    help="run the read-only gates (leak_scan, invariants, skill_lint) and show real PASS/FAIL")
    ap.add_argument("--json", action="store_true",
                    help="print gather()'s data as JSON to stdout (the data contract ui/web/ consumes); skips HTML")
    ap.add_argument("--project", help="project root (default: $CLAUDE_PROJECT_DIR or cwd)")
    ap.add_argument("--lang", choices=list(i18n.LANGS), default=i18n.DEFAULT_LANG,
                    help=f"report language (default: {i18n.DEFAULT_LANG}); a static file can't toggle "
                         "in-page without doubling the DOM, so the language is a build-time choice")
    ap.add_argument("--open", action="store_true", help="open the report in the default browser")
    args = ap.parse_args(argv)

    proj = Path(args.project).resolve() if args.project else _project_dir()
    ctx = gather(proj, args.days, args.gates_json, args.run_gates)
    if args.json:
        # The stable data seam: gather() is plain JSON-serializable data. ui/web/ (and any
        # external tool) can consume this instead of re-deriving collection. No HTML written.
        print(json.dumps(ctx, ensure_ascii=False, indent=2))
        return 0
    if not TEMPLATE.is_file():
        print(f"error: template missing: {TEMPLATE}", file=sys.stderr)
        return 1
    out = Path(args.output)
    out.write_text(render(ctx, args.lang), encoding="utf-8")
    print(f"wrote -> {out.resolve()}", file=sys.stderr)
    if not ctx["wired"]:
        print("tip: telemetry not wired — skill counts show 'chưa đo'. Add skill_usage_logger "
              "to .claude/settings.json to measure.", file=sys.stderr)
    if not args.run_gates and not args.gates_json:
        print("tip: pass --run-gates to show real gate PASS/FAIL.", file=sys.stderr)
    if args.open:
        import webbrowser
        webbrowser.open(out.resolve().as_uri())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
