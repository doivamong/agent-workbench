<div align="center">

# Agent Workbench

### Skills, rules, hooks, and tooling for running an AI coding agent reliably on a long-lived codebase

*Bộ công cụ + phương pháp luận làm việc với Claude Code — rút ra từ một codebase production thật, đã domain-stripped.*

[![CI](https://github.com/doivamong/agent-workbench/actions/workflows/ci.yml/badge.svg)](https://github.com/doivamong/agent-workbench/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Core: stdlib-only](https://img.shields.io/badge/core-stdlib--only-blue.svg)](#at-a-glance)

<kbd>[Why](#why-this-exists)</kbd> · <kbd>[What's inside](#whats-inside)</kbd> · <kbd>[How it fits together](#how-it-fits-together)</kbd> · <kbd>[Quickstart](#quickstart-5-minutes)</kbd> · <kbd>[Install](#install-it-into-your-own-project)</kbd> · <kbd>[Honesty](#status--honesty)</kbd>

</div>

---

> **The problem.** Most Claude Code advice is toy examples. The hard part of using an AI
> agent isn't a clever one-off prompt — it's keeping the agent **consistent, safe, and
> on-pattern** across hundreds of sessions on a codebase you actually have to maintain.

> **The approach.** Encode the recurring decisions *once* — as intent-triggered skills,
> path-scoped rules, fail-open hooks, a carried-forward memory, and greppable invariant
> checks — so the agent re-derives them every session instead of you re-explaining them.

> **The result.** A copy-pasteable kit that installs into any project in one command and
> starts blocking dangerous shell commands, refining vague prompts, and gating commits
> immediately. Core is **stdlib-only**, the demos run in seconds, and CI is green.

<details>
<summary><b>New here? Start with the guided tour →</b></summary>

Read [`docs/getting-started.md`](docs/getting-started.md) for a guided walkthrough: clone,
run the three demos, then point the installer at one of your own projects. The rest of this
README is the reference map — skim the [What's inside](#whats-inside) table, then dive into
the [`<details>` deep-dives](#how-it-fits-together) only for the mechanisms you care about.

</details>

---

## Why this exists

> **Canonical statement:** the four tenets and the "what would betray this" review checklist live
> in [`PHILOSOPHY.md`](PHILOSOPHY.md) — the source of truth. This section is their narrative form.

This kit is the **generic, reusable layer** extracted from a real single-developer project —
the parts that have nothing to do with the original business domain and everything to do with
**making an AI coding agent reliable, safe, and consistent over a long-lived codebase.**

It is deliberately **domain-stripped**. Every business identifier, secret, machine path, and
piece of customer data has been removed and verified with a leak scanner (see
[`docs/SANITIZATION.md`](docs/SANITIZATION.md)). What remains is methodology you can lift.

> **Why it's public — and why it isn't about stars.** The codebase this came from can never be
> public; the methodology inside it is too useful to stay buried there for good. So it's shared
> for one plain reason: *let whoever needs it lift it, and skip the stumbling, the guesswork, and
> the avoidable mistakes it already cost to learn.* Success here isn't traction or attention — it
> is that the kit is **available, correct, and honest** the day someone reaches for it. If it
> spares one person an avoidable wrong turn — a stranger, or its own author starting the next
> codebase — it has done its job. That is the only scoreboard here.

> **Honesty is the deal, not decoration.** Because the point is to spare you avoidable pain, every
> tool states plainly what it does *not* do (see [Status & honesty](#status--honesty) and
> [`docs/SECURITY.md`](docs/SECURITY.md)). A guardrail that oversold itself would cause the exact
> stumble it is meant to prevent. The standard everywhere here: **best-fit, honest about limits,
> not gospel.**

**Who it's for** — solo developers (or tiny teams) who use an AI agent as their primary
pair-programmer, maintain code long enough that **consistency** and **guardrails** matter
more than raw speed, and want concrete copy-pasteable patterns instead of abstract advice.

## What's inside

A benefit-first map — *what it helps you do*, not an endpoint dump. Technical detail is
deferred to the linked paths and the [deep-dives below](#how-it-fits-together).

| When you need to… | What this gives you | Path |
|---|---|---|
| **Configure the agent itself** | Drop-in `CLAUDE.md` + `AGENTS.md` templates — short, high-signal project instructions loaded every session, portable across AI coding tools | [`CLAUDE.md`](CLAUDE.md) · [`AGENTS.md`](AGENTS.md) |
| **Encode reusable playbooks** | A skill system with anatomy, tiers, a registry, and **sixteen** runnable skills across all five tiers — nine **workflows** (plan-then-code, prompt-refiner, research, handover, stress-test, tdd, cook, external-ref, lessons-capture), four **guards** (review, debug, output-guard, config-guard), a **meta** router (using-skills), a **feature** (optimize), and an **audit** (dead-code-audit) | [`.claude/skills/`](.claude/skills/) |
| **Carry context across sessions** | A file-based, index-gated memory scaffold (example facts to replace). The harness auto-loads `MEMORY.md` from a per-project path, not this repo's `memory/` — see [memory-governance.md](docs/memory-governance.md) | [`memory/`](memory/) |
| **Catch common footguns** | Hooks that catch common destructive shell commands (whitespace/flag-order tolerant — a *seatbelt*, not a security boundary), flag vague prompts, nudge a simplify pass after a burst of edits, and wrap everything fail-open with crash logging | [`.claude/hooks/`](.claude/hooks/) |
| **Keep secrets encrypted at rest** | A dependency-free (stdlib-only) file encryptor — HMAC-CTR stream cipher + PBKDF2 — for keeping sensitive files encrypted in a private backup. A **custom stdlib construction, not an audited crypto library**; fine for at-rest backups, but use `age`/`sops`/libsodium if you have a real adversarial threat model (see [`docs/SECURITY.md`](docs/SECURITY.md)) | [`scripts/secrets_guard.py`](scripts/secrets_guard.py) |
| **Codify rules that must never break** | A tiny framework turning project invariants into fast, greppable checks you can wire into a pre-commit / CI gate | [`tools/invariants.py`](tools/invariants.py) |
| **Run only the relevant tests** | An AST-based "which tests does this change affect?" selector — faster CI than running everything | [`tools/affected_tests.py`](tools/affected_tests.py) |
| **Catch leaked secrets before commit** | A line-based secret/identifier *tripwire* with a private deny-list (catches common shapes + your own identifiers), an opt-in `--entropy` sweep for random-looking tokens, and `--respect-gitignore` to skip files that never ship — the commit-time seatbelt used to vet this export | [`tools/leak_scan.py`](tools/leak_scan.py) |
| **Vet third-party code before you vendor it** | A license/attribution *tripwire* — greps a file or tree for OSS-license, copyright, and "adapted-from" markers and says what each implies for reuse. Honest limit: it reads markers, not meaning — a clean result is not proof of original authorship | [`tools/license_scan.py`](tools/license_scan.py) |
| **Keep memory honest** | A hygiene tripwire for the memory system — flags malformed frontmatter, dangling index links, orphan facts, broken `[[wiki-links]]`, and an oversized index | [`tools/memory_audit.py`](tools/memory_audit.py) |
| **Roll back a bad memory edit** | A manual snapshot/restore CLI for the memory store (which lives outside git, so `git checkout` can't save you) — snapshot before a risky mutation, restore *additively* if it goes wrong; manual-only, never a hook/cron | [`tools/memory_snapshot.py`](tools/memory_snapshot.py) |
| **Check memory actually reaches the agent** | A read-only wiring trip-wire — the harness auto-loads `MEMORY.md` from a per-project path, not this repo's `memory/`, so facts curated in the wrong dir are silently never recalled. Flags that mismatch and an over-budget live index; stat-verifies every path and writes nothing | [`tools/memory_recall_doctor.py`](tools/memory_recall_doctor.py) |
| **Keep skills in sync** | A linter that catches drift between `skill-registry.md` and the `SKILL.md` files (a folder with no row, a row with no folder, frontmatter gaps, missing trigger markers) | [`tools/skill_lint.py`](tools/skill_lint.py) |
| **Catch file-set drift** | A manifest gate over the source-of-truth dirs (skills, hooks, rules, tools, scripts): adding or removing a file without updating its dependent docs/wiring fails CI. Paired with a `PostToolUse` hook that nudges you the moment a new file lands | [`tools/sync_manifest.py`](tools/sync_manifest.py) |
| **Keep the README counts honest** | A generator/gate for the "At a glance" numbers (tests/demos/tools/skills): `--check` fails CI when a count is stale, `--write` recomputes them from the tree — so two branches stop conflicting on hand-typed counts. Gates the numbers, not the prose lists | [`tools/readme_metrics.py`](tools/readme_metrics.py) |
| **Watch the context budget** | An auditor for everything Claude Code loads each session (skills, agents, rules, the CLAUDE.md chain, MCP servers) — buckets each as always/sometimes/rarely and flags the heavy ones, so "short, high-signal context" gets a number (heuristic, not a real tokenizer) | [`tools/check_context_budget.py`](tools/check_context_budget.py) |
| **Catch an un-installed dependency** | A pre-commit *seatbelt* that warns (never blocks) when a commit adds a line to `requirements.txt`, so you remember to install it where the code runs before it fails at import | [`tools/check_requirements_diff.py`](tools/check_requirements_diff.py) |
| **See which skills actually fire** | An opt-in prompt-logger + report that surfaces which skills get used and which are dead weight — to prune them or fix their trigger text. Honest proxy: it counts name *mentions*, not true uses | [`tools/skill_usage_report.py`](tools/skill_usage_report.py) |
| **Codify recurring traps as rules** | Path-scoped rules that auto-load when you edit a matching file — slash-command style, and measurement honesty (don't trust a green check you didn't verify) | [`.claude/rules/`](.claude/rules/) |
| **Run a real pre-commit gate** | A ready [`.pre-commit-config.yaml`](.pre-commit-config.yaml) wiring the leak scanner + invariant checks before every commit | [`.pre-commit-config.yaml`](.pre-commit-config.yaml) |
| **Try everything in 30 seconds** | Each tool ships a runnable `examples/` entry | [`examples/`](examples/) |

## How it fits together

The reusable core is a handful of small, independent pieces that the installer drops into a
target project. Nothing here is a framework — each part stands alone and is opt-in.

```mermaid
flowchart TB
    subgraph agent["Agent configuration (loaded every session)"]
        cfg["CLAUDE.md / AGENTS.md<br/>project instructions"]
        skills["Skills<br/>intent-triggered playbooks"]
        rules["Rules<br/>path-scoped style"]
        mem["Memory<br/>index-gated; live store is per-project, not the repo copy"]
    end

    subgraph guards["Runtime guardrails (hooks)"]
        block["block_dangerous.py<br/>PreToolUse"]
        refine["prompt-refiner-inject.py<br/>UserPromptSubmit"]
        simplify["post_edit_simplify.py<br/>PostToolUse"]
        wrap["hook_logger<br/>fail-open + crash log"]
    end

    subgraph gate["Commit / CI gate"]
        inv["invariants.py"]
        leak["leak_scan.py"]
        aff["affected_tests.py"]
        sec["secrets_guard.py"]
    end

    install["install.py"] -->|copies into| agent
    install -->|wires| guards
    install -->|"--with-git-hook"| gate

    block -.->|wrapped by| wrap
    refine -.->|wrapped by| wrap
    simplify -.->|wrapped by| wrap

    classDef config fill:#dbeafe,stroke:#3b82f6,color:#1e3a8a
    classDef hook fill:#fef3c7,stroke:#d97706,color:#78350f
    classDef check fill:#dcfce7,stroke:#16a34a,color:#14532d
    classDef entry fill:#ede9fe,stroke:#7c3aed,color:#4c1d95

    class cfg,skills,rules,mem config
    class block,refine,simplify,wrap hook
    class inv,leak,aff,sec check
    class install entry
```

<details>
<summary><b>Deep-dive: the skill system (tiers, registry & skills)</b></summary>

Skills are intent-triggered playbooks. The registry classifies each into a **tier** so the
agent knows which takes precedence when several match. Sixteen runnable skills ship as
working references:

| Skill | Tier | Fires when | Role |
|---|---|---|---|
| `awb-plan-then-code` | workflow | "implement X", multi-file work needing a plan first | Orchestrates a full plan → implement → review flow |
| `awb-review` | guard | "review my changes", before a non-trivial commit | Gates quality on changed code |
| `awb-debug` | guard | "it's broken / erroring" with an unknown cause | Maps symptom → suspect files before any fix |
| `awb-research` | workflow | "how should we / what's the best way", comparing approaches | Reads the code, compares ≥2 options, recommends before building |
| `prompt-refiner` | workflow | a vague, multi-part request (flagged by the `prompt-refiner-inject.py` hook) | Restates intent into a crisp spec before work starts |
| `awb-handover` | workflow | ending a session, "package this for the next session / write a handover" | Packages settled work into artifacts a cold reader can execute |
| `awb-stress-test` | workflow | "stress test this / what could go wrong / edge cases", before building or testing | Runs a change past fixed lenses for a GO/CAUTION/STOP verdict and an edge-case list |
| `awb-output-guard` | guard | generating a whole file / large refactor | Stops truncation, placeholders, and "for brevity" stubs in long output |
| `awb-using-skills` | meta | auto-injected each session; ≥2 skills could match, or unsure any applies | Routes to the right skill (tier precedence, match the object not the verb) |
| `awb-config-guard` | guard | writing code that reads config (a nested key, or a cross-context read) | Advisory layer over the deterministic `config-flat-access` invariant — catches the silent-None trap |
| `awb-tdd` | workflow | "do this TDD / test-first / red-green-refactor" | One failing test → minimal code → repeat, in vertical slices; guards the silent-skip trap |
| `awb-cook` | workflow | "cook this / full workflow with checkpoints / plan from a few angles" | Graduated oversight + multi-perspective plan, orchestrating the guard skills |
| `awb-external-ref` | workflow | about to copy/adapt outside code ("can we use this / port this") | Classify the licence → port-with-notice or salvage-the-concept; injection + supply-chain checks |
| `awb-optimize` | feature | "it's too slow / optimize / cut latency" with a measurable goal | Baseline → measure → fix the top bottleneck → re-measure → before/after table |
| `awb-dead-code-audit` | audit | "find unused / dead code", a post-refactor prune | Calls a symbol dead only when every independent cross-check is empty; never auto-deletes |
| `awb-lessons-capture` | workflow | end of a session, "capture the lessons / memory retro", after a surprising bug or correction | Mines the session for durable lessons, scores each, writes only the approved ones to live memory |

The registry ([`.claude/skills/skill-registry.md`](.claude/skills/skill-registry.md)) is the
single grep-able index of trigger / do-not-trigger boundaries; the
[`SKILL_TEMPLATE.md`](.claude/skills/SKILL_TEMPLATE.md) is the starting point for your own.

</details>

<details>
<summary><b>Deep-dive: hooks are fail-open by design</b></summary>

Every hook is wrapped so that a crash **never blocks your workflow** — it logs to a JSONL
crash file and exits cleanly, rather than wedging the agent. The shipped hooks:

| Hook | Event | What it does |
|---|---|---|
| `block_dangerous.py` | `PreToolUse` (Bash) | Catches common destructive command shapes — `rm -rf` (any flag order/spacing), `find -delete`, `dd`, `mkfs`, fork bombs, force-push, `DROP TABLE`, … — and denies them via the documented hook contract. A **seatbelt against accidents, not a security boundary** (a determined operator can evade any string matcher). Adversarial evasion cases are in the test suite. |
| `prompt-refiner-inject.py` | `UserPromptSubmit` | Flags vague prompts to be refined before execution |
| `post_edit_simplify.py` | `PostToolUse` (Edit/Write) | After a burst of edits, nudges a simplification pass (dead code, unused imports, over-long functions, DRY). Throttled by a cooldown and a session TTL so it nudges occasionally, never spams. Advisory only — never blocks. |
| `precompact_backup.py` | `PreCompact` | Backs up the transcript and writes a `.last_compact` signal before a compaction, so context is recoverable even if you didn't save. |
| `compact_restore.py` | `SessionStart` (compact) | After a compaction, re-injects the top of the newest handover so the agent resumes with goal/decisions/next-steps. |
| `skill_routing_inject.py` | `SessionStart` (all) | Injects a compact, tier-ordered routing map derived from `skill-registry.md`, so the agent starts each session knowing which skill fires when. Output is kept small (it loads every session); pairs with the `awb-using-skills` meta-skill. |
| `sync_guard.py` | `PostToolUse` (Write) | When a Write creates a *new* file in a watched source-of-truth dir, nudges you to update its dependents and regenerate the manifest. Distinguishes new-file from edit via `.claude/manifest.json`, so content edits stay quiet. Advisory; the deterministic gate is `tools/sync_manifest.py --check`. |
| `context_tracker.py` | `PostToolUse` (all) | As a session grows long, nudges you to `/compact` or to save a handover before limits hit. Throttled; counts are per-project. |
| `session_end.py` | `SessionEnd` | Writes a one-line breadcrumb (git branch, last commit, uncommitted count, time) when a session ends; `session_start.py` surfaces it next time as a "Last session: …" line. A lightweight, automatic complement to a hand-written handover — orientation, not a replay. Kill-switch `SESSION_BREADCRUMB=0`. |
| `skill_usage_logger.py` | `UserPromptSubmit` | **Opt-in — not wired by default.** Logs which skills a prompt names (an explicit `/<skill>` as a strong "invoke", a bare name as a weak "mention") to a local, gitignored JSONL for [`tools/skill_usage_report.py`](tools/skill_usage_report.py) to summarize. Enable by adding it to the `UserPromptSubmit` chain in `.claude/settings.json`. |

The fail-open wrapper lives in [`.claude/hooks/lib/hook_logger.py`](.claude/hooks/lib/hook_logger.py).
Run [`examples/hook_block_demo.py`](examples/hook_block_demo.py) to see the classifier decide.

</details>

## Generic vs. domain-specific — read this first

This kit is the **GENERIC** half of a larger private codebase. The table is honest about
what's transferable and what was intentionally left behind:

| Transferable (here) | Left behind (domain-specific, not shareable) |
|---|---|
| Hook architecture (fail-open, crash-logged) | Application routes + domain data-access code |
| `secrets_guard` crypto | The project's domain business logic |
| Invariant *framework* | The project's concrete invariant rules |
| Memory governance *model* | The actual memory corpus |
| Prompt-refiner *mechanism* | The project's domain prompt vocabulary |

## At a glance

<!-- BEGIN GENERATED:metrics (hand-maintained; run `python -m pytest --co -q` to recount tests) -->

| Signal | Value |
|---|---|
| Reusable core dependencies | **0** (stdlib-only) |
| Tests | **396**, green in CI (incl. adversarial evasion cases for the command guard) |
| Runnable demos | **16** (`examples/`) |
| Skills | **16** (9 workflow + 4 guards + 1 meta + 1 feature + 1 audit) |
| Standalone tools | **15** (`invariants`, `affected_tests`, `leak_scan`, `license_scan`, `secrets_guard`, `memory_audit`, `memory_snapshot`, `memory_recall_doctor`, `memory_budget`, `skill_lint`, `check_context_budget`, `check_requirements_diff`, `sync_manifest`, `skill_usage_report`, `readme_metrics`) |

<!-- END GENERATED:metrics -->

> The test count is mirrored in three places (this row, the Quickstart comment, the footer).
> `tests/test_readme_metrics.py` guards against drift — it collects the suite and fails CI if any
> advertised number is stale, so the figure can't silently rot when you add tests.

## Quickstart (5 minutes)

```bash
git clone https://github.com/doivamong/agent-workbench
cd agent-workbench
python -m pip install -r requirements.txt   # stdlib-only core; deps are for examples/tests

# See it work (each runs in seconds):
python examples/secrets_demo.py     # encrypt/decrypt round-trip + tamper detection
python examples/hook_block_demo.py  # dangerous-command classifier
python examples/post_edit_simplify_demo.py  # the simplify-nudge classifier
python examples/invariant_demo.py   # the invariant gate
python examples/memory_audit_demo.py  # memory hygiene tripwire
python examples/skill_lint_demo.py    # registry/skill drift check
python examples/memory_snapshot_demo.py  # snapshot/restore a memory dir
python examples/memory_recall_doctor_demo.py  # does curated memory reach the agent?
python examples/context_budget_demo.py   # audit this repo's context budget
python examples/requirements_diff_demo.py # warn on a newly added dependency
python examples/affected_tests_demo.py   # pick only the tests a change affects
python examples/sync_manifest_demo.py     # file-set drift gate (added/removed files)

# Prove the tools actually work:
python -m pytest -q                 # 396 tests
```

## Install it into your own project

This is the part that makes it real, not just a reference. Point the installer at any project
and it copies the hooks, skills, rules, tools, `secrets_guard`, and the memory scaffold in, then
wires the hooks for you:

```bash
python install.py /path/to/your/project --with-git-hook --merge-settings
# --merge-settings deep-merges the hooks into .claude/settings.json (idempotent —
#   safe to re-run, preserves your other settings). Omit it to print the snippet
#   to paste yourself instead.
# --dry-run to preview first; --force to overwrite existing copied files.
```

With `--merge-settings` the hooks are active immediately; without it you paste the printed
snippet into `.claude/settings.json` yourself. Either way, opening that project in your agent
gives you, working immediately:

- **Dangerous `Bash` commands get blocked** (force-push, `rm -rf /`, `DROP TABLE`, …) via a
  real `PreToolUse` hook — verified against the documented hook I/O contract.
- **Vague prompts get flagged** to be refined first, via a `UserPromptSubmit` hook.
- **A git pre-commit gate** (`--with-git-hook`) that refuses to commit a leaked secret.
- **Drop-in skills** under `.claude/skills/` and a **working memory folder** under `memory/`.

Then make it yours: replace these skills with your own, put your real rules in
[`tools/invariants.py`](tools/invariants.py), and list your project's identifiers in a private
deny-list for [`tools/leak_scan.py`](tools/leak_scan.py).

## Documentation

| Group | Key file | When to read |
|---|---|---|
| **Start here** | [`docs/getting-started.md`](docs/getting-started.md) | First clone — guided walkthrough |
| **Map** | [`SKILL_CATALOG.md`](SKILL_CATALOG.md) | The full capability taxonomy — every skill/hook/doc/placeholder tagged LIVE / BLUEPRINT / ADOPTER-FILLS / REJECTED |
| **Security** | [`docs/SECURITY.md`](docs/SECURITY.md) | What each guard does / does NOT defend against |
| **Blueprint** | [`docs/memory-governance.md`](docs/memory-governance.md) | Reference design for cross-session memory — the repo ships the `memory/` scaffold; the governance tooling is a model you implement |
| **Design + hooks** | [`docs/session-preservation.md`](docs/session-preservation.md) | Context handover on long projects — the automatic layers ship as hooks (PreCompact backup, post-compact restore, context-budget nudge); the `/session-save` commands and the HANDOVER you write stay manual |
| **Guide** | [`docs/sub-agents.md`](docs/sub-agents.md) | The sub-agent convention + the shipped `silent-failure-hunter` (an error-handling reviewer you spawn on demand; adapted from Anthropic's pr-review-toolkit, Apache-2.0) |
| **Guide** | [`docs/orchestration.md`](docs/orchestration.md) | How to delegate to sub-agents — when it pays off, briefing one that can't see your chat, a status protocol, and writing big outputs to disk |
| **Guide** | [`docs/lessons-as-rules.md`](docs/lessons-as-rules.md) | Turning a hard-won mistake into a path-scoped rule — the rule shape, promotion from memory, and the periodic anti-bloat cull |
| **Guide** | [`docs/development-rules.md`](docs/development-rules.md) | Everyday coding defaults (YAGNI/KISS/DRY, error handling, testing) — guidance, not law, and what yields when a path-scoped rule disagrees |
| **Guide** | [`docs/workflow.md`](docs/workflow.md) | Which skills to chain for which task type, and what the hooks fire on their own — the routing map over the skill set |
| **Guide** | [`docs/architecture-vocabulary.md`](docs/architecture-vocabulary.md) | A small domain-free vocabulary for *structural* quality — deep vs shallow module, seam, the deletion test, interface-as-test-surface |
| **Blueprint** | [`docs/ui-redesign-workflow.md`](docs/ui-redesign-workflow.md) | UI redesign as a gated workflow (admin + public toggle) — front-load the cheap checks; ships the method, you fill the brand |
| **Guide** | [`docs/design-discipline.md`](docs/design-discipline.md) | Make UI quality explicit, not a vibe — numeric design dials, a scan→diagnose→fix audit, anti-AI-slop rules, a11y/perf as hard rules |
| **Guide** | [`docs/external-tool-reliability.md`](docs/external-tool-reliability.md) | Trust an external analysis tool only after benchmarking it — ban its 0%-accurate queries, degrade gracefully to grep |
| **Guide** | [`docs/pre-commit-failure-modes.md`](docs/pre-commit-failure-modes.md) | A commit gate that learns — an append-only failure-modes registry plus advisory-vs-blocking tiering |
| **Guide** | [`docs/windows-agent-gotchas.md`](docs/windows-agent-gotchas.md) | Silent failures specific to driving an agent on Windows — `.bat` swallowed by `cmd /c`, headless `sys.stdout=None`, "restart didn't take" (stale PID/elevation), `requirements.txt` ≠ deployed |
| **Pattern** | [`docs/patterns/config-access.md`](docs/patterns/config-access.md) | Two config-access traps — the wrong accessor for the execution context, and the silent-`None` nested-key bug that detonates far downstream |
| **Pattern** | [`docs/patterns/optimization-loop.md`](docs/patterns/optimization-loop.md) | Let a measurement, not intuition, decide each change — the measure → change → keep-or-revert-via-git loop, and the honest limit that it only fits measurable goals |
| **Pattern** | [`docs/patterns/boundary-coherence.md`](docs/patterns/boundary-coherence.md) | When you change one side of a producer↔consumer boundary, read the other — contract drift there fails silently (blank render, silent `None`, a no-op) and a one-sided test still passes |
| **Blueprint** | [`docs/skills-as-cli.md`](docs/skills-as-cli.md) | Pattern for running a skill's playbook outside Claude Code (Cursor/Copilot/raw API) |
| **Provenance** | [`docs/SANITIZATION.md`](docs/SANITIZATION.md) | How the domain was stripped and verified |
| **Provenance** | [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md) | Ports/derivatives and their obligations |

## Status & honesty

This is **best-fit as currently known, with better approaches left open** — not gospel. It
comes from *one* developer's context (solo, long-lived, AI-first). Your trade-offs may differ.
PRs that challenge a pattern are as welcome as PRs that extend one.

**On the guardrails specifically:** `block_dangerous.py` and `leak_scan.py` are **seatbelts, not
security boundaries.** They catch common accidental and obvious-malicious shapes; they do **not**
stop a determined operator (string matchers can be evaded via encoding or indirection; the
opt-in `leak_scan --entropy` pass catches random-looking tokens but a line scanner still can't
see everything). Use them to reduce footguns, not as your last line of defense.

## License

[MIT](LICENSE) for the original code. Several pieces are ports/derivatives of other open-source
work — see [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md) for attribution and the
obligations that come with them.

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md). The short version: this is a learning artifact, so
**"here's a better way" issues are the whole point.**

---

<div align="center">

**Agent Workbench** · stdlib-only core · 396 tests · MIT

🐍 Python · 🤖 Claude Code / AI agents · 🔒 fail-open guardrails

<sub>A domain-stripped methodology kit · best-fit, not gospel · MIT licensed</sub>

</div>
