# Skill Catalog — the full capability map

> The **map layer** of this kit's skill system. The
> [skill-system roadmap](docs/skill-system-roadmap.md) argued *why* each capability earns (or
> fails to earn) a place; this catalog is the standing answer — every capability the kit knows
> about, tagged with where it actually lives today. It is breadth at near-zero context cost:
> nothing here is loaded into a session, so the map can be exhaustive without paying for it.
>
> The standard everywhere is [`PHILOSOPHY.md`](PHILOSOPHY.md) — **"best-fit, honest about limits,
> not gospel."** A capability is listed only with an honest status and, where relevant, the thing
> it deliberately does *not* do.

🇻🇳 *Tóm tắt — Đây là **bản đồ năng lực** của hệ skills: mỗi dòng là một capability, gắn nhãn trạng thái (LIVE / BLUEPRINT / ADOPTER-FILLS / REJECTED) cho biết nó sống ở đâu hôm nay. Bản đồ không phải bộ đếm — số LIVE chuẩn được gate ở README; nếu trang này và README lệch nhau, **tin README**.*

## How to read this

Each row is one **capability**, not one file. A capability can land as a runnable skill, a hook, a
tool, a method doc, or a reserved placeholder — the **Status** column says which, and **Lands as /
Caveat** says where it lives plus the honest limit that travels with it.

| Status | Meaning |
|---|---|
| **LIVE** | Ships as a runnable artifact today — a skill, hook, or tool you can invoke now. |
| **BLUEPRINT** | Ships as **documentation** — a method or pattern you implement; the doc exists, the thing it describes is yours to build. Zero routing cost. |
| **ADOPTER-FILLS** | A reserved placeholder. The *shape* ships; the content is domain-specific and you fill it (your config, your brand, your invariants). |
| **REJECTED** | Evaluated and deliberately not shipped — domain-locked, redundant, or no original method left after genericizing. The reason is the point. |

> **The authoritative count of LIVE skills is gated in the README** ("At a glance"), kept
> honest by `tools/readme_metrics.py --check`. This catalog is a *map*, not a counter — if a number
> here and the README ever disagree, the README wins. As of this writing the kit ships **19 live
> skills** across all five tiers.

---

## 1. Live skills — by tier

The runnable exemplars. Each is a working reference whose *shape* you copy, not its content. Every
guard-tier skill states what it does **not** do (the honesty contract `skill_lint.py` greps for).

### Workflow (12)

| Capability | Tier | Status | Lands as / Caveat |
|---|---|---|---|
| Plan → implement → test → review a non-trivial change | workflow | LIVE | [`awb-plan-then-code`](.claude/skills/awb-plan-then-code/) · a bypassable exemplar, not a gate |
| Turn a vague, multi-part request into a crisp spec before working | workflow | LIVE | [`prompt-refiner`](.claude/skills/prompt-refiner/) · paired with the `prompt-refiner-inject.py` hook; refines wording, does not guess intent |
| Understand before building — scope, read the code, compare ≥2 options | workflow | LIVE | [`awb-research`](.claude/skills/awb-research/) · recommends, does not decide for you |
| Package settled work into a cold-readable handover | workflow | LIVE | [`awb-handover`](.claude/skills/awb-handover/) · only for work finished enough to hand off |
| Pressure-test a change on paper before building (lenses → GO/CAUTION/STOP + edge-case list) | workflow | LIVE | [`awb-stress-test`](.claude/skills/awb-stress-test/) · verdicts are reasoned opinion, not proof; absorbed the pre-mortem nugget (see Rejected) |
| Red-green-refactor in vertical slices | workflow | LIVE | [`awb-tdd`](.claude/skills/awb-tdd/) · passing tests prove only what they assert; guards the silent-skip (0-collected) trap |
| Advanced build — graduated oversight + multi-perspective planning, orchestrating the guards | workflow | LIVE | [`awb-cook`](.claude/skills/awb-cook/) · enforces nothing; a heavier exemplar for higher-stakes builds |
| Responsibly reuse outside code — license decision, idea/expression split, injection + supply-chain checks | workflow | LIVE | [`awb-external-ref`](.claude/skills/awb-external-ref/) · a classification seatbelt, **not legal advice** |
| Mine a finished session for durable lessons — score against a fixed bar, write only approved survivors to live memory | workflow | LIVE | [`awb-lessons-capture`](.claude/skills/awb-lessons-capture/) · an honesty overlay on auto-memory; the honest output can be zero |
| Wire the kit's guards into a project and prove they run — `install.py --merge-settings` then `--doctor` | workflow | LIVE | [`awb-install-and-verify`](.claude/skills/awb-install-and-verify/) · relays only what `--doctor` proves (PROVEN vs INSTALLED); narrates, does not edit settings by hand. The verifier is also copied in as [`tools/doctor.py`](tools/doctor.py) so you can re-check from inside your own repo |
| Remove the kit from a project safely — dry-run plan, explicit confirm, KEEP files you edited | workflow | LIVE | [`awb-uninstall`](.claude/skills/awb-uninstall/) · dry-run by default; never deletes a file you modified; refuses to guess with no manifest |
| Verify a working tree is safe to close at session end — uncommitted / unpushed / unmerged / stale branches, clean on approval | workflow | LIVE | [`awb-session-close`](.claude/skills/awb-session-close/) · read-only [`tools/session_close_audit.py`](tools/session_close_audit.py); BLOCKs only what would be lost (uncommitted/unpushed), never auto-deletes a branch |

### Guard (4)

| Capability | Tier | Status | Lands as / Caveat |
|---|---|---|---|
| Review a change in three passes (spec → build quality → adversarial) | guard | LIVE | [`awb-review`](.claude/skills/awb-review/) · model-invoked and bypassable; not a whole-codebase audit |
| Debug methodically — reproduce → root cause → fix → prove | guard | LIVE | [`awb-debug`](.claude/skills/awb-debug/) · for an unknown cause, not a known one-line fix |
| Keep long generation complete — no truncation / placeholders / "for brevity" | guard | LIVE | [`awb-output-guard`](.claude/skills/awb-output-guard/) · guards completeness, not correctness |
| Catch the two silent config-access traps (wrong context; nested key → silent `None`) | guard | LIVE | [`awb-config-guard`](.claude/skills/awb-config-guard/) · the **advisory** layer over the deterministic `config-flat-access` invariant |

### Feature · Audit · Meta (3)

| Capability | Tier | Status | Lands as / Caveat |
|---|---|---|---|
| Make code measurably faster — baseline → measure → fix top bottleneck → re-measure → before/after table | feature | LIVE | [`awb-optimize`](.claude/skills/awb-optimize/) · ships no profiler; needs a measurable goal and a baseline |
| Find genuinely dead code behind a false-positive gate | audit | LIVE | [`awb-dead-code-audit`](.claude/skills/awb-dead-code-audit/) · static finders over-report on dynamic dispatch; never auto-deletes |
| Route to the right skill (tier precedence, match the object not the verb) | meta | LIVE | [`awb-using-skills`](.claude/skills/awb-using-skills/) · a routing nudge; never does the work itself. Paired with the `skill_routing_inject.py` SessionStart hook |

---

## 2. Deterministic guards — reclassified to a hook / tool

A guard whose value is *always firing* is not a skill — a bypassable, keyword-matched skill would
silently skip when no keyword matches. These shipped as deterministic mechanisms instead. The rule
behind the choice is [`docs/guard-mechanisms.md`](docs/guard-mechanisms.md).

| Capability | Tier | Status | Lands as / Caveat |
|---|---|---|---|
| Keep the file-set in sync (a new/removed source file must update its dependents) | guard → hook + tool | LIVE | [`tools/sync_manifest.py`](tools/sync_manifest.py) (`--check` gate) + `sync_guard.py` PostToolUse nudge · the tool is authoritative, the nudge is advisory |
| Catch a config read in the wrong context / at the wrong nesting level | guard → invariant + skill | LIVE | `config-flat-access` invariant in [`tools/invariants.py`](tools/invariants.py) (deterministic) + the advisory `awb-config-guard` (judgment) |
| Block common destructive shell commands | guard → hook | LIVE | [`block_dangerous.py`](.claude/hooks/scripts/block_dangerous.py) PreToolUse · a **seatbelt, not a security boundary** — a determined operator evades any string matcher |

---

## 3. Harvested capabilities — a nugget folded into an existing skill or doc

Not everything worth keeping is worth shipping whole. These methods were distilled to their durable
core and folded into something that already ships, rather than added as a new skill.

| Capability | Tier | Status | Lands as / Caveat |
|---|---|---|---|
| Confidence-scored review with a scope gate that filters adversarial false positives | guard | LIVE (harvested) | inside [`awb-review`](.claude/skills/awb-review/) · a score tells you to *verify*, not to *fix* |
| Fast deterministic pass/fail loop first; test-collection trap; 3-failure escalation | guard | LIVE (harvested) | inside [`awb-debug`](.claude/skills/awb-debug/) |
| Iterative one-question "grill mode" + a 4-tier clarity scale | workflow | LIVE (harvested) | inside [`prompt-refiner`](.claude/skills/prompt-refiner/) |
| Cold Reader Test + a severity-graded handover integrity gate + merge-don't-regenerate | — | BLUEPRINT | [`docs/session-preservation.md`](docs/session-preservation.md) |
| Lesson-value scoring (gates → score → severity-rescue) + a "dare to report zero" honesty gate | — | BLUEPRINT | [`docs/lessons-as-rules.md`](docs/lessons-as-rules.md) |
| An append-only commit failure-modes registry + advisory-vs-blocking tiering | — | BLUEPRINT | [`docs/pre-commit-failure-modes.md`](docs/pre-commit-failure-modes.md) |
| A domain-free vocabulary for structural quality (deep module / seam / deletion test) | — | BLUEPRINT | [`docs/architecture-vocabulary.md`](docs/architecture-vocabulary.md) |

---

## 4. Blueprints — ship as a method doc

Breadth that costs zero routing context. The *method* ships; the brand/domain specifics it would
need are yours to fill (see section 5).

| Capability | Tier | Status | Lands as / Caveat |
|---|---|---|---|
| UI redesign as a gated workflow (admin + public toggle) | workflow | BLUEPRINT | [`docs/ui-redesign-workflow.md`](docs/ui-redesign-workflow.md) · ships the method; brand palette, tokens, component macros, SEO-block layout stay placeholders |
| Design discipline — numeric dials, scan→diagnose→fix audit, anti-AI-slop, a11y/perf budgets | guard | BLUEPRINT | [`docs/design-discipline.md`](docs/design-discipline.md) · a practice shape; specific scales and rule sets are yours |
| Use an external analysis tool honestly — benchmark accuracy, ban its 0%-accurate queries, degrade to grep | guard | BLUEPRINT | [`docs/external-tool-reliability.md`](docs/external-tool-reliability.md) · an instance of measurement-honesty, not a tool |
| Choosing the right guard mechanism (skill vs hook vs tool vs sub-agent) | meta | BLUEPRINT | [`docs/guard-mechanisms.md`](docs/guard-mechanisms.md) |
| Run a skill's playbook outside Claude Code (Cursor / Copilot / raw API) | meta | BLUEPRINT | [`docs/skills-as-cli.md`](docs/skills-as-cli.md) |
| Delegate to sub-agents — when it pays, briefing one that can't see your chat, a status protocol | meta | BLUEPRINT | [`docs/orchestration.md`](docs/orchestration.md) · the shipped `silent-failure-hunter` is the worked example |
| The path-scoped rule-card pattern (a rule that auto-loads when you edit a matching file) | meta | LIVE + BLUEPRINT | [`.claude/rules/`](.claude/rules/) ships working cards; [`docs/lessons-as-rules.md`](docs/lessons-as-rules.md) is the how-to |

---

## 5. Adopter-fills — a reserved placeholder you complete

The kit ships the slot and the discipline; the content is domain-specific by nature. Filling these
is how the kit becomes *yours*.

| Capability | Tier | Status | Lands as / Caveat |
|---|---|---|---|
| Your project's config-guard rules | guard | ADOPTER-FILLS | the reserved `_your-config-guard_` registry slot + the `config-flat-access` invariant — encode your real config shape |
| Your UI brand guide (palette, token prefixes, component macros, SEO-block layout) | guard | ADOPTER-FILLS | the reserved `_your-ui-guide_` slot — domain-locked by definition; the [design-discipline](docs/design-discipline.md) + [redesign-workflow](docs/ui-redesign-workflow.md) docs ship the method, not your brand |
| Your project's concrete invariant rules | — | ADOPTER-FILLS | [`tools/invariants.py`](tools/invariants.py) — the framework ships; the rules are yours |
| Your identifiers in the leak-scan deny-list | — | ADOPTER-FILLS | a private deny-list for [`tools/leak_scan.py`](tools/leak_scan.py) — list your project's names/paths |

---

## 6. Rejected — evaluated, deliberately not shipped

The reason a thing is *not* here is part of the map. (Full debate: roadmap [section E](docs/skill-system-roadmap.md).)

| Capability | Tier | Status | Lands as / Caveat |
|---|---|---|---|
| A standalone pre-mortem skill | feature | REJECTED | ~90% redundant with [`awb-stress-test`](.claude/skills/awb-stress-test/); its two unique nuggets (an adversarial-debate + pre-mortem round, and Integration/Compliance failure axes) were **harvested** into it instead |
| A code-graph assist skill | meta | REJECTED | ships **no engine** — it only calls an external graph server; shipping the skill alone would oversell. Its durable *lesson* lives in [`docs/external-tool-reliability.md`](docs/external-tool-reliability.md) |
| A "zoom out one layer" skill | workflow | REJECTED | its generic core is an unmodified third-party MIT skill; nothing original remains after genericizing — link upstream instead |
| An ETL-pipeline guard | guard | REJECTED | almost entirely a specific app's pipeline internals; the one transferable idea (beware *silent* data corruption) is too thin to ship alone |
| A separate research-workflow skill | workflow | REJECTED | duplicates [`awb-research`](.claude/skills/awb-research/); only its banned-behaviors list + mandatory-comparison-table were worth keeping |
| Architecture / config / ETL guards **as skills** | guard | REJECTED | their value is *determinism* → they belong in the invariant tool / lint / hooks, not in bypassable skills (see [`docs/guard-mechanisms.md`](docs/guard-mechanisms.md)) |
| Brand UI skills **as ship items** | guard | REJECTED | domain-locked (a specific palette, token prefixes, component catalog) → ADOPTER-FILLS, not a ship item; ship the method (section 4), not the brand |

---

## 7. Operational & analysis tooling — LIVE (the layer that runs *this* repo)

Distinct from the installable skill core above: these are the **repo-operation** and **opt-in**
capabilities — the tools that operate the workbench itself and the dashboards that visualise its
state. They are **not** part of `install.py`'s payload (the `ops/` tools are repo-maintenance; the
`ui/` layer is opt-in and is the only place a runtime dependency lives). The authoritative detail
lives in [`ops/README.md`](ops/README.md), [`ui/web/README.md`](ui/web/README.md), and
[`docs/SECURITY.md`](docs/SECURITY.md); this is the status map.

> **Read this as a maintainer add-on, not adopter payload.** Its value is for whoever *runs this
> repo* (operating the workbench, visualising its state) — not lifted methodology a stranger
> installs. The transferable core is §1–6 above; this section is convenience for the maintainer.

| Capability | Tier | Status | Lands as / Caveat |
|---|---|---|---|
| Process control for the opt-in dashboard (start / stop / restart / status) | ops | LIVE | [`ops/dashboard_ctl.py`](ops/dashboard_ctl.py) + [`ops/win/restart_all.bat`](ops/win/restart_all.bat) · localhost/single-dev; only manages the process in its own pidfile, never hunts-and-kills by port |
| Working-tree snapshot / restore as a dev safety net | ops | LIVE | [`ops/tree_snapshot.py`](ops/tree_snapshot.py) · gitignore-respecting; restore is an *overlay*, dry-run by default, plan-hash + auto-backup guarded |
| Verifiable release zip of the installable kit | ops | LIVE | [`ops/release_pack.py`](ops/release_pack.py) · packs exactly `install.py`'s `COPY_MAP`; the sha256 manifest proves **integrity, not authenticity** (unsigned) |
| Default-to-LAN bind + firewall helper | ops | LIVE | [`ops/lan_setup.py`](ops/lan_setup.py) (`status`/`enable`/`disable`/`firewall`) · **the OS firewall is the control, not the app** |
| Start the dashboard at logon | ops | LIVE | [`ops/autostart.py`](ops/autostart.py) · Windows `ONLOGON` Scheduled Task / POSIX systemd *user* service; reachable on the subnet every logon — firewall stays the control |
| Offline, zero-dependency status report | ui | LIVE | [`ui/kit_status/`](ui/kit_status/) · self-contained HTML rendered from the single data source; stdlib-only |
| Interactive dashboard (charts + in-place controls) | ui | LIVE | [`ui/web/`](ui/web/) (Flask + Jinja + vendored Chart.js/htmx) · the kit's **only** runtime dependency, isolated from the stdlib core; manual refresh, not a daemon |
| `/admin` web action surface — always-mounted, **login is the gate** | ui | LIVE | [`ui/web/admin.py`](ui/web/admin.py) + [`ui/web/set_password.py`](ui/web/set_password.py) · pbkdf2-sha256 password + lockout + CSRF + `SameSite` cookie; **inert without a password** (every action 403s); plain HTTP — **cleartext on a LAN, trusted-network only**; `--debug` is refused |
| Memory **recall-quality** benchmark | tool | LIVE | [`tools/memory_eval.py`](tools/memory_eval.py) · a stdlib retrieval benchmark over a hand-labeled gold set (recall@k / precision@k / MRR) — measures *retrieval*, not answer correctness; a **floor**, not a leaderboard; advisory, not a gate. Pairs with `memory_recall_doctor` (wiring) |
| Redacted secret/identifier-shape leak detection | tool | LIVE | [`tools/leak_scan.py`](tools/leak_scan.py) · flags common secret/token shapes (private key, AWS, Slack/Telegram, `api_key=`/`password=`) with the matched value **redacted**; high-confidence secrets need a *named* opt-out. A line-based **seatbelt, not a dedicated scanner** (`docs/SECURITY.md`) |

---

## Honest limits of this catalog

- **It is a map, not a guarantee.** A row says a capability *exists and where it landed* — not that
  it is the best design, nor that it will fit your project. Challenge any verdict; the roadmap records
  the reasoning so you can.
- **Statuses drift.** This file is hand-maintained. The one number under machine guard is the LIVE
  skill count in the README; everything else here is only as current as its last edit. If a
  link 404s or a status looks stale, trust the tree over this page.
- **"Generic core only."** Capabilities distilled from a private codebase ship as the transferable
  method with all domain content removed. Where a capability needs domain content to be useful, it is
  an ADOPTER-FILLS slot — the kit cannot fill it for you, and pretending otherwise would be the exact
  overselling [`PHILOSOPHY.md`](PHILOSOPHY.md) forbids.
