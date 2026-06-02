# Memory Governance

**Created:** 2026-04-21 | **Version:** 1.0

> Specification for the 3-layer memory system used with Claude Code projects. Ensures memory stays fresh, non-fragmented, and has a clear promotion path.

> ⚠ **What this repo actually ships vs. what this doc describes.** This document is the
> **conceptual model**. **Agent Workbench ships only the file-based scaffold** — the
> [`memory/`](../memory/) folder (one-fact-per-file + an index-gated `MEMORY.md`) and this design
> note. The *automation* this doc references — `memory_*.py` scripts, Semgrep enforcement, a
> `reports/` folder, an auto-promotion sleep cycle — is **NOT included here**; it belongs to the
> larger private codebase this kit was extracted from, and in that codebase the automation layer
> is itself **code-complete but unexecuted** with auto-promotion **mathematically infeasible**
> (see §10). Treat the named tooling below as *illustrative design*, not files you'll find in this
> repo. The genuinely portable, working part is the layout + the promotion *model* you implement
> yourself.

---

## 1. Three-Layer Architecture

| Layer | Source | Loaded | Written by | Characteristics |
|-------|--------|--------|------------|-----------------|
| **L1 — Core config** | `CLAUDE.md` / `AGENTS.md` | Always, every session | Human | Project invariants, quick reference. Target **< 200 lines** (Anthropic guideline). |
| **L2 — Path-scoped rules** | `.claude/rules/*.md` | Conditional (`paths:` frontmatter) | Human | Lessons / rules that load only when Claude edits a file matching the path pattern. |
| **L3 — Auto memory** | `~/.claude/projects/<project>/memory/` | First 200 lines of `MEMORY.md`; topic files on-demand | Claude | Per-machine, not committed to git. |

**Principle:** Narrower-scope lessons belong in lower layers. Do not duplicate content across layers.

---

## 2. Frontmatter Spec for Memory Files (L3)

Every file in `~/.claude/projects/<project>/memory/*.md` should carry these fields:

```yaml
---
name: <human-readable name>
description: <short description>
type: feedback | project | reference | user

# 4 core fields:
pattern_key: project.<area>.<issue>   # stable dedup key, lowercase dot-separated
severity: neutral | success | error | critical
status: pending | in_progress | resolved | superseded
pinned: false                          # true = no decay, no invalidation

# 3 optional fields (Phase 2 — supersession support):
superseded_by: feedback_newer.md      # path relative to memory dir (when status=superseded)
valid_until: 2026-12-31               # ISO date; entry expires after this date
subtype: lesson                        # refines type further (see §4.1)
---
```

### `pattern_key` Namespace (whitelist)

Define namespaces appropriate for your project. Examples:

| Prefix | Scope |
|--------|-------|
| `project.config.*` | Configuration access patterns |
| `project.db.*` | Database queries, connection lifecycle |
| `project.etl.*` | Data pipeline transforms |
| `project.frontend.*` | JS, CSS, templates |
| `project.security.*` | Auth, session, secrets handling |
| `project.deploy.*` | Dependency and environment issues |
| `project.tooling.*` | Code review, audit, CI references |
| `project.docs.*` | Documentation and translation patterns |
| `project.ui.*` | UI/UX design patterns |

Keys outside the whitelist should trigger a warning from `memory_health.py`.

### `severity` Semantics

| Level | When to use | Effective half-life |
|-------|-------------|---------------------|
| `neutral` | General info, preference | 1.0× (default 90 days) |
| `success` | Confirmed best practice | 1.3× |
| `error` | Bug encountered and fixed | 1.5× |
| `critical` | Silent failure, security issue | 2.0× |

> ⚠ **[UNIMPLEMENTED]** The severity multipliers above are the *intended* design. The reference `memory_invalidate.py` only reads a `half_life_days` field (defaulting to 90) without applying severity multipliers. The column above describes planned behavior, not current behavior.

### `status` Lifecycle

```
pending → in_progress → resolved → (optional) superseded
```

- `resolved` **requires** a `resolution` block (see §3).
- `superseded` is used when a lesson has been replaced by a rule or Semgrep check — keep the file for traceability, but `pinned: false` allows natural decay.

---

## 3. Resolution Block (Artifact Trail)

When `status: resolved`, add a `resolution` block to the frontmatter:

```yaml
resolution:
  commit: abc1234                     # Git SHA — required for audit trail
  files:                              # Files modified — at least 1 required
    - services/example_service.py
    - scripts/some_script.py
  notes: |
    Added null-guard for stdout when running in detached mode.
    Audited all scripts/ and services/ — all pass.
  date: 2026-04-21
```

**Rules:**
- `commit` **required** — provides audit trail reference
- `files[]` **required**, ≥ 1 — closes the Artifact Trail gap
- `notes` ≤ 3 lines — summary only, do not copy file contents

---

## 4.1 `subtype` Semantics

The `subtype` field refines `type` to clarify lifecycle handling:

| subtype | Description | Lifecycle | Example |
|---------|-------------|-----------|---------|
| `lesson` | Bug / mistake encountered and fixed | pending → resolved → (optional) superseded | `feedback_stdout_guard.md` |
| `decision` | Technical decision with rationale | pending → decided → (optional) reconsidered | "use SQLite instead of Postgres" |
| `retro` | Session retrospective (compressed) | pending → archived (never superseded) | HANDOVER.md compressed |
| `pattern` | Reusable code pattern | pending → validated → (optional) deprecated | items from `docs/PATTERNS.md` |

**Rules:**
- `lesson` entries can be invalidated and superseded (code changes make them outdated).
- `decision` and `pattern` are stable — `memory_invalidate.py` should **not** touch them automatically (only manual user supersession).
- `retro` is an immutable archive — no decay, no invalidation.

`memory_sleep.py` (Phase 3) should only consolidate entries with `subtype: lesson` — leave decision / pattern / retro untouched.

If `subtype` is missing, treat as `lesson` (default behavior).

---

## 4. Promotion Path

Lessons move from L3 → L2 / L1 according to hard thresholds.

### Threshold: 3 / 2 / 90

Promote when **all three** conditions hold:
1. `recurrence_count >= 3` (encountered at least 3 times)
2. `distinct_sessions >= 2` (across at least 2 different sessions)
3. `last_seen - first_seen <= 90 days` (still "hot")

### Promotion Target by Scope

| Content | Target |
|---------|--------|
| Applies only to one path (e.g., `scripts/**`) | `.claude/rules/lessons-<topic>.md` with `paths:` frontmatter |
| Applies to the entire project (e.g., core invariants) | `CLAUDE.md` L-section (keep file < 200 lines) |
| Enforceable via regex / AST | Semgrep rule in `.semgrep/rules/` |

**Rule:** Prefer path-scoped rules over `CLAUDE.md` additions (KV-cache friendliness per Anthropic context-engineering guideline).

---

## 5. Invalidation — Stale Detection via Git (Phase 2) — ⛔ DEPRECATED

> ⛔ **DEPRECATED.** `tools/memory_invalidate.py` has been renamed to `.deprecated`. Git-log token matching is **not a valid invalidation signal**: a commit message like "migrate X to Y" describes a code change, not that the L3 lesson about X is outdated. In the reference implementation this logic incorrectly flagged the majority of memory files. Replace with the safe snapshot/restore + type-aware retention approach (§5b). Do not revive without a new design review and safety caps. Description below is kept as historical record.

Tool `tools/memory_invalidate.py` scanned `git log --since=<last_run>` and matched 5 patterns:

| Pattern | Example commit msg | Action |
|---------|--------------------|----|
| `migrate X to Y` | `feat: migrate from waitress to gunicorn` | Memory containing "waitress" → halve half-life + tag `stale` |
| `replace X with Y` | `fix: replace os.walk with rglob` | Memory containing "os.walk" → halve + stale |
| `deprecate X` | `docs: deprecate legacy_endpoint` | Memory containing "legacy_endpoint" → halve + stale |
| `remove X` | `refactor: remove unused helpers` | Memory containing "helpers" (non-trivial) → halve + stale |
| `from X to Y` (standalone) | `chore: from pandas 1.x to 2.x` | Memory containing "pandas 1" → halve + stale |

**Guard logic (retained for reference):**
- Skip `pinned: true`
- Token match threshold 0.5
- Trivial word skip: `extra, unused, empty, old, whitespace, spaces, blank, dead, commented` (only when `remove X` has ≤ 2 words)

---

## 5b. Type-Aware Retention + Safety Core

The memory directory is **outside git** — there is no `git checkout` fallback. Guiding principle: *reads are safe to automate; writes/deletes require human-in-the-loop.* Run scripts manually, **not via hooks or cron** (to avoid silent automation failures).

### Safety Core (required for any mutating operation)

| Mechanism | Tool / usage |
|-----------|-------------|
| **Snapshot-before-mutate** — precondition for any mutation | `memory_lib.snapshot_memory()` → `memory/.snapshots/<ISO>/` (rotate, keep last 10). Without this, accidental bulk overwrites cannot be recovered. |
| **Restore from snapshot** | `python tools/memory_restore.py --latest --apply` (or `--from <ISO>`). Round-trip is byte-identical. |
| **Kill switch** | `PROJECT_MEMORY_AUTOMATION=0` → all mutating tools (migrate / sleep / promote / restore / archive-sweep) exit 0 without touching files. Read-only health checks are unaffected. |
| **Invalidate deprecated** | `memory_invalidate.py.deprecated` — git-log token matching is invalid as described in §5. |
| **All tools scan `-maxdepth 1`** | `.backup-*/` and `.snapshots/` are subdirectories → exclude them (use `is_file()` only). Recursive scans double-count. |

### Type-Aware Retention

| Type | Age-based sweep? | Rule |
|------|-----------------|------|
| **`feedback_*`** | ❌ **NEVER** | Timeless lessons. Exit the index only via **supersession** (`status: superseded` + `superseded_by`) or promotion (`promoted_to_rule`). Auto-archiving by age risks destroying valid lessons. |
| **`project_*`** | ✅ age + status | Session logs can decay. Sweep when `--older-than` + closed `status`. Respect `bake_until` (see below). |
| **`reference_*`** | ✅ age + status | Similar to project; old references can be archived when the upstream source changes. |

**`bake_until: <YYYY-MM-DD>`** (optional on `project_*`): entry is under evaluation (waiting for KEEP/REVERT verdict) — sweep skips it until the date passes. Read by `memory_health.py --archive-sweep`.

### Archive = Remove from Index (not physical delete)

Recall is **index-gated**: only `MEMORY.md` (~200 lines / ~24 KB) auto-loads each session; topic files load on-demand. **Archiving = removing the index line from `MEMORY.md`** is sufficient to reduce recall noise (the file remains safely on disk). `MEMORY_archive.md` is a **cold-storage dead-end** — do not link from `MEMORY.md` with a markdown link (Claude will not auto-follow it). Physical moves to `_archive/` are an optional secondary exclusion layer, not required.

### Health and Sweep Commands

```bash
# Read-only health check (not blocked by kill switch) — reports broken links, orphans, dup titles
python tools/memory_health.py

# List archive candidates (safe, no writes)
python tools/memory_health.py --archive-sweep --type project --older-than 30d --status closed --list

# Apply: snapshot first, then move index entries, then verify no dead links
python tools/memory_health.py --archive-sweep --type project --older-than 30d --status closed --apply
```

### Dedup: Detection In-Scope, Enforcement Deferred

`memory_health.py` reports near-duplicates by `description` (Jaccard ≥ 0.7, read-only — no auto-merge). Dedup-at-write via LLM/automation is **deferred** (same failure risks as the deprecated invalidate approach). Safe blueprint: lazy-decay-on-read + soft-flag + dedup-at-write Jaccard — distinct from invalidation.

> Trigger: MANUAL from end-of-session skill or wrap-up command. **Not** hook/cron.

---

## 6. HANDOVER Template (Anchored Iterative)

The session-save command uses this template (~98% compression, good quality/brevity balance):

```markdown
# HANDOVER — <session title>

## Session Intent
Original goal: <1-2 sentences describing the original objective>

## Files Modified
- `<path>`: <what changed>
- `<path>`: <what changed>

## Decisions Made
- <decision>: <rationale>
- <decision>: <rationale>

## Current State
<Progress summary — paragraph or bullets — current state>

## Next Steps
1. <next action 1>
2. <next action 2>
```

**Rules:**
- On compression (next session opens old HANDOVER + new work): **merge new content into existing sections, don't regenerate**.
- `Files Modified` section must not be empty — artifact trail requirement.
- `Decisions Made` must include rationale, not just "chose X".

---

## 7. Read Protocol — Session Start Order (KV-Cache Optimization)

> ⚠ **Clarification:** The session-start hook does **not** inject `CLAUDE.md` / rules / `MEMORY.md`. The Claude Code harness loads those automatically (`CLAUDE.md`/`AGENTS.md` = always-load; `rules/*.md` = auto-load per `paths:`; `MEMORY.md` = built-in auto-memory ~24 KB). The stable→variable ordering and cache hit target below describe **default harness behavior**, not custom hook logic. The table shows the *effective load order* (harness + hook combined).

Effective load order at session start (stable → variable, to optimize KV-cache):

```
1. CLAUDE.md + AGENTS.md (stable, rarely changes)        ← harness always-load, cacheable prefix
2. .claude/rules/*.md (path-scoped)                      ← harness auto-load per paths:
3. meta-skill inject (e.g., your using-skills convention) ← session-start hook
4. Auto memory MEMORY.md (variable, changes each session) ← harness built-in auto-memory
5. Status / warning messages (if any)                    ← session-start hook, variable suffix
```

Target cache hit ≥ 70% (Anthropic context-engineering benchmark) — achieved through default harness behavior, no custom intervention needed.

---

## 8. Health Metrics

`tools/memory_health.py` outputs a weekly report covering:

| Metric | Threshold |
|--------|-----------|
| Total file count | info |
| `pattern_key` null | < 10% (remainder not yet migrated) |
| `status: pending` > 90 days | warn |
| `status: resolved` without `resolution.files[]` | warn (artifact trail gap) |
| Duplicate `pattern_key` ≥ 3 entries | flag for Phase 3 consolidation |
| `pinned: true` count | info |
| Total size | warn if > 500 KB |
| `MEMORY.md` line length | warn ≥ 200 chars, critical ≥ 300 chars (truncation risk) |
| `MEMORY.md` file size | warn ≥ 24 KB (Claude Code session-start load limit ~24.4 KB) |

Output: `reports/memory_health_YYYYMMDD.md`.

### MEMORY.md Index Discipline

**Rule:** Each entry in `MEMORY.md` is a **single-line summary**, target ≤ 200 chars (including markdown markup). Detail belongs in the topic file body — **trust that future sessions will follow the link when they need detail**.

**Why:**
- Claude Code loads the first ~24 KB of `MEMORY.md` at session start
- Long entries push the file over the load limit → later entries are **truncated** (recall lost)
- Example: 67% of entries exceeding 200 chars + a 26 KB file → over limit → required manual pruning

**How to write a good index entry:**
```markdown
- [filename.md](filename.md) — Subject: key insight + 1 specific detail (commit hash OR pattern key OR number). Max 200 chars total.
```

**Anti-pattern vs good pattern:**
```markdown
# BAD — too much detail (belongs in the topic file body)
- [feedback_x.md](feedback_x.md) — Detailed explanation of the problem with multiple sentences. The root cause was X. The fix was Y. Memory ref Z. Commit ABC. Plus aside note about W. Plus ROI analysis. 320 chars.

# GOOD — punchy hook + key tag
- [feedback_x.md](feedback_x.md) — X problem (root: Y). Fix: Z pattern. Commit ABC. 150 chars.
```

Enforcement: `tools/memory_health.py` flags entries > 200 chars. Critical (> 300) must be trimmed **before** committing new batch entries.

---

## 9. Prohibited Actions

- Creating a new entry with `pattern_key: null` (migration tools will assign a default like `project.misc.unclassified` — rename promptly)
- Setting `pinned: true` on a lesson with `status: superseded`
- Promoting into the core `CLAUDE.md` if the file is already at or near the 200-line limit
- Modifying `resolution.commit` after the commit has been made (audit integrity)
- Marking `status: resolved` without populating `resolution.files[]`

---

## 10. Roadmap

> ⚠ **[UNIMPLEMENTED]** "Done" in the context below means *code-complete*, **not** *running in production*. Phases 2/3 have not executed end-to-end in the reference implementation (no state files, no reports directory, no scheduled tasks). Actual status is noted under each phase.

- **Phase 1 (done + operational):** Frontmatter migration + rule splits + core config refactor + health tool + HANDOVER template. `memory_health.py` runs successfully.
- **Phase 2 (code-complete, NOT operational — EXPERIMENTAL):** Invalidation tool written but **never run with `--apply`** (no state file). Scheduled task script written but not installed. Supersession fields (subtype, resolution) have low metadata coverage in the reference corpus. See §5 caveats.
- **Phase 3 (code-complete, AUTO-PROMOTION INFEASIBLE):** Sleep cycle + promotion helper written, but auto-promotion produces **zero candidates** because `pattern_key` is used as a unique identifier (every key is unique, so `uniq -d` returns nothing) while `memory_sleep.py` needs ≥ 3 files sharing the same key. All actual promotions in the reference implementation used **manual user-override**. That manual path is the one that works.

### Phase 3 — Sleep Cycle (implemented, manual trigger only)

3-step cycle in `tools/memory_sleep.py`:

**Step 1 — EXTRACT** (`extract_candidates()`):
- Scan all memory entries
- Filter `subtype: lesson` (skip decision / pattern / retro)
- Group by `pattern_key`
- Apply threshold 3 / 2 / 90:
  - `recurrence_count >= 3` sharing the same `pattern_key`
  - `distinct_days >= 2` (approximate sessions)
  - Within a 90-day window
- Skip `pinned: true`, `status: promoted_to_rule`

**Step 2 — GENERATE** (`generate_draft_rule()`):
- For each qualifying `pattern_key`, build a draft rule file
- `paths:` frontmatter is inferred from the namespace prefix (define mappings appropriate to your project):
  - `project.config.*` → `services/`, `core/`
  - `project.db.*` → `repositories/`, `core/`
  - `project.frontend.*` → `templates/`, `static/`
  - … (see `NAMESPACE_PATHS` in the tool)
- Template follows 3-section format: Context → Pattern → Implication
- Raw lesson bodies are referenced only (human distills manually)
- Output: `reports/memory_sleep_draft_<key>.md`

**Step 3 — PROMOTE** (`tools/memory_promote.py`):
- Permission-aware gate: the target rule file **must exist** before promotion
  - Human reviews the draft and edits the 3-section content
  - Human copies draft → `.claude/rules/lessons-<topic>.md`
  - Human adds `paths:` frontmatter as needed
- Tool only marks source entries: `status: promoted_to_rule` + `superseded_by: <target>`
- Creates `.bak.promote` backup for each modified entry
- Skips `pinned: true`

**User workflow:**
```bash
# 1. Scan candidates (dry run)
python tools/memory_sleep.py --dry-run

# 2. Generate draft rule files
python tools/memory_sleep.py --apply
# → reports/memory_sleep_draft_project_config_silent_none.md

# 3. Human reviews and edits the draft (distill 3-section content)

# 4. Human copies draft to rules dir
cp reports/memory_sleep_draft_<key>.md .claude/rules/lessons-<topic>.md

# 5. Mark source entries as promoted
python tools/memory_promote.py \
  --draft reports/memory_sleep_draft_<key>.md \
  --target .claude/rules/lessons-<topic>.md \
  --apply
```

This cycle is enforced by `.claude/rules/memory-governance.md` (path-scoped trigger when editing `memory/`, `tools/memory_*.py`, `.claude/rules/lessons-*.md`).

### Phase 4 (backlog — deferred)

The following are explicitly deferred. Do not re-evaluate each audit session:

- `tools/memory_explain.py` — retrieval debugging. **DEFER** → trigger: ≥ 1 incident of "unexplained recall miss". Has not occurred → YAGNI.
- Full protocol-driven session workflows. **REJECTED** → message-bus / pub-sub orchestration is over-engineering for a single-developer project.
- Strict permission-aware write scope enforcement. **SUFFICIENT** → the permission gate in `memory_promote.py` (target rule must exist before promotion) is enough.
- Namespace Semgrep rule for `pattern_key`. **DEFER** → trigger: after backfilling `pattern_key` to a clean state AND namespace violations recur ≥ 2 times. Enforcing early blocks legitimate writes on unclean data.

---

## References

- Claude Code official memory docs: https://docs.claude.com/en/docs/claude-code/memory
- Anthropic context engineering: https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents
- hippo-memory (MIT) — decay + invalidation patterns
- self-improving-agent pattern — Pattern-Key + promotion threshold concept
- Nate-Vish 500-file proven pattern — scaling problems + 3-section rule template
- claudekit-engineer context-engineering skill — 4-bucket strategy + Anchored Iterative template
