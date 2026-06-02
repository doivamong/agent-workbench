#!/usr/bin/env python3
"""check_context_budget.py — audit the token overhead Claude Code loads into a session.

Every skill, agent, rule, command, the CLAUDE.md/AGENTS.md chain, and each MCP server costs
context. CLAUDE.md asks you to keep that "short and high-signal" — this tool measures it so the
rule has teeth: it scans `.claude/` + the CLAUDE.md chain + `.mcp.json`, classifies each piece
into always / sometimes / rarely loaded buckets, and separates a skill's BODY (and its
`references/`) — both of which load **on-demand, only when the skill is invoked** — from what is
truly loaded every session: the CLAUDE.md chain and each skill's frontmatter *description*. (Claude
Code uses progressive disclosure — the description is always in context; the SKILL.md body enters
the conversation only when the skill fires. So 27 installed skills cost 27 short descriptions at
session start, NOT 27 full bodies.) Use it to spot a single bloated skill and keep the always-loaded
surface lean — the body-token figures are an on-demand / maintenance magnitude, not a per-session tax.

    python tools/check_context_budget.py            # text report (default)
    python tools/check_context_budget.py --json      # machine-readable
    python tools/check_context_budget.py --top 5     # top N issues
    python tools/check_context_budget.py --verbose   # list every component
    python tools/check_context_budget.py --window 1000000   # 1M context window
    python tools/check_context_budget.py --max-skills 16  # CI gate: cap the live-skill COUNT

Exit 0 = OK / minor warnings; exit 1 = a component crossed a *critical* threshold (e.g. a SKILL.md
body > 800 lines, an agent description > 50 words) OR a --max-skills / --max-skill-tokens cap was
exceeded. Audit-only by default (no cap set = it never blocks). The recommended CI gate is
`--max-skills` (count) + the automatic per-skill body-critical; `--max-skill-tokens` caps the TOTAL
skill-body tokens, which is an opt-in *maintenance* budget, NOT a session-start one (bodies are
on-demand) — leave it off unless you specifically want a whole-library size ceiling.

HONEST LIMITS: token counts are a rough heuristic (words × TOKENS_PER_WORD), NOT a real
tokenizer — treat them as relative magnitudes, not an exact budget. The per-server MCP cost and
all THRESH values are tunable starting points, not measured truths; calibrate them for your repo.

The component-scan + bucket + session-start-vs-on-demand framing was re-implemented in stdlib from
the design of `affaan-m/ECC` (skills/context-budget, MIT) — see THIRD_PARTY_NOTICES.md. No code copied.
"""
from __future__ import annotations

import argparse
import io
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

# Windows pythonw.exe can hand us a non-UTF stdout; keep prints from crashing.
# (When a second tool needs this, lift it into a shared util — see PORT_CATALOG "W1-util".)
if sys.stdout is not None and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    except Exception:
        pass

ROOT = Path(__file__).resolve().parent.parent

# --- heuristics & thresholds: STARTING POINTS, not measured truths. Tune for your project. ---
TOKENS_PER_WORD = 1.3            # rough word→token factor; NOT a real tokenizer
DEFAULT_WINDOW = 200_000         # context window for the "% available" figure (--window to change)
APPROX_TOKENS_PER_MCP_TOOL = 500  # per-tool schema overhead estimate
DEFAULT_MCP_TOOLS_PER_SERVER = 10  # assumed tool count when the real one is unknown at scan time

THRESH = {
    "skill_lines_heavy": 400,
    "skill_lines_critical": 800,
    "agent_lines_heavy": 200,
    "agent_desc_words": 30,
    "agent_desc_critical": 50,
    "rule_lines_heavy": 200,
    "claudemd_chain_critical": 800,
    "mcp_tools_per_server": 20,
}


@dataclass
class Component:
    kind: str
    name: str
    path: Path
    # For a skill, `lines`/`tokens` = the SKILL.md BODY only (the session-start cost).
    # For other kinds they measure the file itself.
    lines: int = 0
    tokens: int = 0
    # `ref_*` = a skill's references/ subdir (loaded on demand, not at session start).
    ref_lines: int = 0
    ref_tokens: int = 0
    desc_words: int = 0
    bucket: str = "unknown"
    issues: list[str] = field(default_factory=list)


def count_tokens(text: str) -> int:
    """Rough heuristic: word count × TOKENS_PER_WORD. Not a real tokenizer."""
    return int(len(re.findall(r"\S+", text)) * TOKENS_PER_WORD)


def read_safe(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def scan_file(p: Path) -> tuple[int, int]:
    text = read_safe(p)
    if not text:
        return 0, 0
    return text.count("\n") + 1, count_tokens(text)


def parse_frontmatter_description(text: str) -> str:
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.DOTALL)
    if not m:
        return ""
    fm_body = m.group(1)
    desc_match = re.search(
        r"^description:\s*([>|]?\s*\n?.+?)(?=^[a-zA-Z_]+\s*:|^---|\Z)",
        fm_body,
        re.MULTILINE | re.DOTALL,
    )
    if not desc_match:
        return ""
    raw = re.sub(r"^[>|]\s*", "", desc_match.group(1).strip())
    return re.sub(r"\s+", " ", raw)


def scan_skills(base: Path) -> list[Component]:
    result: list[Component] = []
    skills_dir = base / ".claude" / "skills"
    if not skills_dir.is_dir():
        return result
    for sk_dir in sorted(skills_dir.iterdir()):
        if not sk_dir.is_dir() or sk_dir.name.startswith("_"):
            continue
        skill_md = sk_dir / "SKILL.md"
        if not skill_md.exists():
            continue
        comp = Component(kind="skill", name=sk_dir.name, path=skill_md)
        comp.lines, comp.tokens = scan_file(skill_md)  # BODY = session-start cost
        ref_dir = sk_dir / "references"
        if ref_dir.is_dir():
            for f in ref_dir.rglob("*.md"):
                sl, st = scan_file(f)
                comp.ref_lines += sl
                comp.ref_tokens += st
        if comp.lines > THRESH["skill_lines_critical"]:
            comp.issues.append(
                f"SKILL.md body too large ({comp.lines} lines > critical "
                f"{THRESH['skill_lines_critical']}) — split into references/ "
                f"(currently {comp.ref_lines} ref lines)"
            )
        elif comp.lines > THRESH["skill_lines_heavy"]:
            comp.issues.append(
                f"SKILL.md body heavy ({comp.lines} lines > {THRESH['skill_lines_heavy']}) "
                "— consider extracting references/"
            )
        result.append(comp)
    return result


def scan_agents(base: Path) -> list[Component]:
    result: list[Component] = []
    agents_dir = base / ".claude" / "agents"
    if not agents_dir.is_dir():
        return result
    for f in sorted(agents_dir.glob("*.md")):
        comp = Component(kind="agent", name=f.stem, path=f)
        comp.lines, comp.tokens = scan_file(f)
        comp.desc_words = len(re.findall(r"\S+", parse_frontmatter_description(read_safe(f))))
        if comp.desc_words > THRESH["agent_desc_critical"]:
            comp.issues.append(
                f"frontmatter description {comp.desc_words} words > critical "
                f"{THRESH['agent_desc_critical']} — loaded on every Task() spawn"
            )
        elif comp.desc_words > THRESH["agent_desc_words"]:
            comp.issues.append(
                f"frontmatter description {comp.desc_words} words > "
                f"{THRESH['agent_desc_words']} — loaded on every Task() spawn"
            )
        if comp.lines > THRESH["agent_lines_heavy"]:
            comp.issues.append(f"agent file heavy ({comp.lines} lines) — trim it")
        result.append(comp)
    return result


def scan_rules(base: Path) -> list[Component]:
    result: list[Component] = []
    rules_dir = base / ".claude" / "rules"
    if not rules_dir.is_dir():
        return result
    for f in sorted(rules_dir.glob("*.md")):
        comp = Component(kind="rule", name=f.stem, path=f)
        comp.lines, comp.tokens = scan_file(f)
        if comp.lines > THRESH["rule_lines_heavy"]:
            comp.issues.append(
                f"rule file long ({comp.lines} lines > {THRESH['rule_lines_heavy']}) "
                "— auto-loads when a path matches its frontmatter paths:"
            )
        result.append(comp)
    return result


def scan_commands(base: Path) -> list[Component]:
    result: list[Component] = []
    cmd_dir = base / ".claude" / "commands"
    if not cmd_dir.is_dir():
        return result
    for f in sorted(cmd_dir.glob("*.md")):
        comp = Component(kind="command", name=f.stem, path=f)
        comp.lines, comp.tokens = scan_file(f)
        result.append(comp)
    return result


def scan_claudemd(base: Path) -> list[Component]:
    result: list[Component] = []
    for rel in ("CLAUDE.md", ".claude/CLAUDE.md", "AGENTS.md"):
        p = base / rel
        if p.exists():
            comp = Component(kind="claudemd", name=rel, path=p)
            comp.lines, comp.tokens = scan_file(p)
            result.append(comp)
    chain_lines = sum(c.lines for c in result)
    if chain_lines > THRESH["claudemd_chain_critical"] and result:
        result[0].issues.append(
            f"CLAUDE.md chain totals {chain_lines} lines > critical "
            f"{THRESH['claudemd_chain_critical']} — loaded 100% of every session"
        )
    return result


def scan_mcp(base: Path) -> list[Component]:
    result: list[Component] = []
    for mcp_path in (base / ".mcp.json", base / ".claude" / ".mcp.json"):
        if not mcp_path.exists():
            continue
        try:
            cfg = json.loads(read_safe(mcp_path))
        except json.JSONDecodeError:
            continue
        for name in cfg.get("mcpServers", {}):
            comp = Component(kind="mcp", name=name, path=mcp_path)
            # Real tool count is only known at runtime, so estimate (tunable).
            tool_count = DEFAULT_MCP_TOOLS_PER_SERVER
            comp.tokens = tool_count * APPROX_TOKENS_PER_MCP_TOOL
            comp.lines = tool_count  # reuse `lines` to carry the (estimated) tool count for display
            if tool_count > THRESH["mcp_tools_per_server"]:
                comp.issues.append(
                    f"~{tool_count} tools > {THRESH['mcp_tools_per_server']} (over-subscription)"
                )
            result.append(comp)
        break  # first config wins
    return result


def classify_buckets(components: list[Component], claudemd_text: str) -> None:
    text_lower = claudemd_text.lower()
    for comp in components:
        if comp.kind in ("claudemd", "mcp"):
            comp.bucket = "always"
            continue
        name_token = comp.name.lower().replace("_", "-")
        if name_token in text_lower or comp.name.lower() in text_lower:
            comp.bucket = "always"  # heuristic: named in the CLAUDE.md chain
        elif comp.kind in ("rule", "command", "skill", "agent"):
            comp.bucket = "sometimes"  # path-scoped / user-invoked / trigger-matched / Task()-spawned
        else:
            comp.bucket = "rarely"


def render_text_report(components: list[Component], top_n: int, verbose: bool, window: int,
                       cap_breaches: list[str] | None = None) -> str:
    lines: list[str] = []
    sep, sub = "=" * 60, "-" * 60
    lines += [sep, "Context budget report", sep]
    lines.append("(token figures are a word-count heuristic, not a real tokenizer)")

    total = sum(c.tokens for c in components)          # upper bound: counts bodies that load on-demand
    ondemand = sum(c.ref_tokens for c in components)   # references/, on demand only
    avail = window - total
    pct = avail * 100 // window if window else 0
    lines.append(f"\nLoaded surface (upper bound): ~{total:,} tokens")
    lines.append("  NOTE: skill bodies + path-scoped rules load on-demand, NOT every session — only")
    lines.append("        the CLAUDE.md chain + skill descriptions are truly always-loaded (see split below)")
    lines.append(f"On-demand references/:  ~{ondemand:,} tokens (only when a skill is invoked)")
    lines.append(f"Context window:         {window:,} tokens (set with --window)")
    lines.append(f"Estimated headroom:     ~{avail:,} tokens ({pct}%)")

    if cap_breaches:
        lines += ["", "BUDGET CAP EXCEEDED (exit 1):", sub]
        lines += [f"  ! {b}" for b in cap_breaches]

    by_kind: dict[str, list[Component]] = {}
    for c in components:
        by_kind.setdefault(c.kind, []).append(c)
    lines += ["\nBy component kind:", sub, f"{'Kind':<14}{'Count':<8}{'Tokens':<12}"]
    for kind in ("claudemd", "skill", "agent", "rule", "command", "mcp"):
        comps = by_kind.get(kind, [])
        if comps:
            lines.append(f"{kind:<14}{len(comps):<8}~{sum(c.tokens for c in comps):,}")

    by_bucket: dict[str, list[Component]] = {}
    for c in components:
        by_bucket.setdefault(c.bucket, []).append(c)
    lines += ["\nBy when it loads (heuristic):", sub]
    for b in ("always", "sometimes", "rarely"):
        comps = by_bucket.get(b, [])
        lines.append(f"{b:<12}{len(comps):<6}~{sum(c.tokens for c in comps):,} tokens")

    flagged = sorted((c for c in components if c.issues), key=lambda c: -c.tokens)
    lines += [f"\nIssues found ({len(flagged)} component(s)):", sub]
    if not flagged:
        lines.append("  (none — context budget looks healthy)")
    else:
        for c in (flagged if verbose else flagged[:top_n]):
            if c.kind == "skill" and c.ref_tokens > 0:
                hdr = (f"  [{c.kind}] {c.name} (body {c.tokens:,} tok / {c.lines} lines "
                       f"+ refs {c.ref_tokens:,} tok / {c.ref_lines} lines on-demand)")
            else:
                hdr = f"  [{c.kind}] {c.name} ({c.tokens:,} tok, {c.lines} lines)"
            lines.append(hdr)
            for iss in c.issues:
                lines.append(f"    - {iss}")
        if not verbose and len(flagged) > top_n:
            lines.append(f"  ... and {len(flagged) - top_n} more (use --verbose)")

    lines += ["\nTop suggestions:", sub]
    recs = _build_recommendations(components)
    if not recs:
        lines.append("  (no clear issues)")
    else:
        for i, (msg, savings) in enumerate(recs[:top_n], 1):
            lines.append(f"  {i}. {msg}")
            if savings:
                lines.append(f"     ~ saves an estimated {savings:,} tokens")

    if verbose:
        lines += ["\nAll components (verbose):", sub]
        for c in sorted(components, key=lambda c: -c.tokens):
            mark = " !" if c.issues else ""
            lines.append(f"  [{c.kind:<9}] {c.name:<40} {c.tokens:>6,} tok  {c.lines:>5} lines  bucket={c.bucket}{mark}")
    return "\n".join(lines)


def _build_recommendations(components: list[Component]) -> list[tuple[str, int]]:
    recs: list[tuple[str, int]] = []

    sometimes_skills = sorted(
        (c for c in components if c.kind == "skill" and c.bucket == "sometimes"),
        key=lambda c: -c.tokens,
    )[:3]
    if sometimes_skills:
        names = ", ".join(c.name for c in sometimes_skills)
        recs.append((f"Largest 'sometimes' skills ({names}) — extract references/ or demote tier",
                     sum(c.tokens for c in sometimes_skills)))

    bloated = [c for c in components if c.kind == "agent" and c.desc_words > THRESH["agent_desc_words"]]
    if bloated:
        names = ", ".join(c.name for c in bloated)
        recs.append((f"Trim frontmatter description of {len(bloated)} agent(s) ({names}) "
                     f"to <= {THRESH['agent_desc_words']} words",
                     sum((c.desc_words - THRESH["agent_desc_words"]) * 2 for c in bloated)))

    crit = sorted(
        (c for c in components if c.kind in ("skill", "rule")
         and c.lines > THRESH.get(f"{c.kind}_lines_heavy", 10**9)),
        key=lambda c: -c.lines,
    )
    if crit:
        c = crit[0]
        if c.kind == "skill":
            action, save = "split the body into references/ to cut session-start cost", c.tokens * 50 // 100
        else:
            action, save = "review and trim (rules auto-load when their path matches)", c.tokens * 20 // 100
        recs.append((f"Largest file ({c.kind} {c.name}, {c.lines} lines) — {action}", save))

    chain_total = sum(c.lines for c in components if c.kind == "claudemd")
    if chain_total > THRESH["claudemd_chain_critical"]:
        recs.append((f"CLAUDE.md chain {chain_total} lines > {THRESH['claudemd_chain_critical']} "
                     "— move detail into docs/ and keep CLAUDE.md a short index",
                     (chain_total - THRESH["claudemd_chain_critical"]) * 3))

    mcp_heavy = [c for c in components if c.kind == "mcp" and c.lines > THRESH["mcp_tools_per_server"]]
    if mcp_heavy:
        names = ", ".join(c.name for c in mcp_heavy)
        recs.append((f"MCP server(s) over-subscribed ({names}) — disable unused tools or drop the server",
                     sum((c.lines - THRESH["mcp_tools_per_server"]) * APPROX_TOKENS_PER_MCP_TOOL for c in mcp_heavy)))

    recs.sort(key=lambda x: -x[1])
    return recs


def check_caps(components: list[Component], max_skills: int | None,
               max_skill_tokens: int | None) -> list[str]:
    """Cap breaches that should fail the run (exit 1). Empty when no cap is set or all pass.

    Both caps are opt-in (without them the tool stays advisory) and target the SKILL set. They
    differ in what they actually protect:
      * ``max_skills`` caps the live-skill COUNT — the right session-start guard, because only each
        skill's *description* (plus, here, the routing-map) is always loaded, and that cost grows
        with count, not body size.
      * ``max_skill_tokens`` caps the TOTAL skill-*body* tokens. Bodies load on-demand (only when a
        skill is invoked), so this is a whole-library *maintenance* ceiling, NOT a session-start
        one — keep it off in CI unless you specifically want a total-size budget. (The per-skill
        body-critical at THRESH["skill_lines_critical"] already catches a single bloated skill.)
    Neither caps on-demand references/ (those don't load until a skill is invoked).
    """
    breaches: list[str] = []
    skills = [c for c in components if c.kind == "skill"]
    if max_skills is not None and len(skills) > max_skills:
        breaches.append(f"live skills {len(skills)} > cap {max_skills}")
    if max_skill_tokens is not None:
        tok = sum(c.tokens for c in skills)
        if tok > max_skill_tokens:
            breaches.append(f"total skill-body tokens ~{tok:,} > cap {max_skill_tokens:,} (on-demand/maintenance, not session-start)")
    return breaches


def collect(base: Path) -> list[Component]:
    components: list[Component] = []
    components += scan_skills(base)
    components += scan_agents(base)
    components += scan_rules(base)
    components += scan_commands(base)
    components += scan_claudemd(base)
    components += scan_mcp(base)
    claudemd_text = "".join(
        read_safe(base / rel) for rel in ("CLAUDE.md", ".claude/CLAUDE.md", "AGENTS.md")
        if (base / rel).exists()
    )
    classify_buckets(components, claudemd_text)
    return components


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Audit the context budget of a Claude Code project.")
    ap.add_argument("--json", action="store_true", help="emit JSON instead of a text report")
    ap.add_argument("--top", type=int, default=10, help="number of top issues to show (default 10)")
    ap.add_argument("--verbose", action="store_true", help="list every component")
    ap.add_argument("--window", type=int, default=DEFAULT_WINDOW, help=f"context window in tokens (default {DEFAULT_WINDOW})")
    ap.add_argument("--root", type=Path, default=ROOT, help="project root (default: this repo)")
    ap.add_argument("--max-skills", type=int, default=None,
                    help="exit 1 if the number of live skills exceeds this cap (default: no cap)")
    ap.add_argument("--max-skill-tokens", type=int, default=None,
                    help="exit 1 if total skill session-start tokens exceed this cap (default: no cap)")
    args = ap.parse_args(argv)

    components = collect(args.root)
    cap_breaches = check_caps(components, args.max_skills, args.max_skill_tokens)

    if args.json:
        print(json.dumps([{
            "kind": c.kind, "name": c.name, "lines": c.lines, "tokens": c.tokens,
            "ref_lines": c.ref_lines, "ref_tokens": c.ref_tokens,
            "bucket": c.bucket, "desc_words": c.desc_words, "issues": c.issues,
        } for c in components], indent=2, ensure_ascii=False))
        if cap_breaches:  # keep JSON a pure component list; surface caps on stderr
            print("BUDGET CAP EXCEEDED: " + "; ".join(cap_breaches), file=sys.stderr)
    else:
        print(render_text_report(components, args.top, args.verbose, args.window, cap_breaches))

    has_critical = any("critical" in i for c in components for i in c.issues)
    return 1 if (cap_breaches or has_critical) else 0


if __name__ == "__main__":
    raise SystemExit(main())
