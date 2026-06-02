# Memory Governance — a reference design

> **What ships here vs. what this describes.** Agent Workbench ships the file-based
> [`memory/`](../memory/) scaffold — one fact per file plus an index-gated `MEMORY.md` — and
> this design note. It does **not** ship the `memory_*.py` automation (health checks, decay,
> auto-promotion), a `reports/` folder, or Semgrep enforcement; those belong to the private
> codebase this kit was extracted from. In that codebase the automation layer is **code-complete
> but unexecuted, with auto-promotion mathematically infeasible** (see the honest lessons at the
> end). So treat the tooling named below as *the design you'd build*, not files in this repo. The
> portable, working parts are the **layout**, the **index-gating discipline**, and the
> **promotion model** — which you implement yourself.

---

## 1. Three layers

Lessons live at the narrowest scope that fits; don't duplicate across layers.

| Layer | Lives in | Loaded | Written by |
|-------|----------|--------|------------|
| **L1 — Core config** | `CLAUDE.md` / `AGENTS.md` | always, every session | human; keep it < ~200 lines |
| **L2 — Path-scoped rules** | `.claude/rules/*.md` | only when editing a path that matches the rule's `paths:` | human |
| **L3 — Auto memory** | `memory/` (per-machine, gitignored) | `MEMORY.md` index each session; topic files on demand | the agent |

---

## 2. What the scaffold actually uses (L3)

Each memory is one file: a short frontmatter plus the fact. This is the convention the shipped
[`memory/`](../memory/) examples follow — start here.

```yaml
---
name: <short-kebab-slug>
description: <one line — used to decide relevance during recall>
metadata:
  type: user | feedback | project | reference
---
```

`feedback` and `project` facts add **Why:** and **How to apply:** lines in the body. Link related
memories with `[[other-name]]` — a convention your recall step resolves, not an auto-followed
link.

## 3. The index-gating discipline (the working core)

Recall is **index-gated**: only `MEMORY.md` auto-loads each session (the agent follows a link to
a topic file only when it needs the detail). The whole system's cost control rests on keeping
that index small, so this is the one rule worth enforcing:

- **Each `MEMORY.md` entry is a single line**, target ≤ 200 characters including markup.
- The session-start load reads roughly the first ~24 KB of `MEMORY.md`. Long entries push later
  entries past that limit, and they are silently **truncated** — recall lost, with no error.
- Detail belongs in the topic file body. Trust that a future session follows the link.

```markdown
# GOOD — punchy hook + one key tag
- [feedback-x.md](feedback-x.md) — X problem (root: Y). Fix: Z pattern. ~150 chars.

# BAD — multi-sentence detail that belongs in the file body, pushes the index over budget
- [feedback-x.md](feedback-x.md) — Detailed explanation… root cause was X, the fix was Y, plus an
  aside about W, plus a ROI note… 320 chars.
```

"Archiving" a memory means **removing its line from `MEMORY.md`** (the file stays on disk). That
is enough to drop it out of recall — you don't need to delete anything.

---

## 4. The promotion model (grow into it)

A recurring lesson should climb from L3 → L2/L1 so it loads reliably instead of depending on
recall. A simple, defensible threshold: promote when a lesson has recurred **≥ 3 times across
≥ 2 sessions** and is still "hot" (first→last seen within ~90 days).

| The lesson applies to… | Promote it to… |
|---|---|
| one path area (e.g. `scripts/**`) | `.claude/rules/lessons-<topic>.md` with a `paths:` filter |
| the whole project | a section in `CLAUDE.md` (keep the file short) |
| something a linter can check | a lint/AST rule |

Prefer path-scoped rules over growing `CLAUDE.md` — they load only when relevant and keep the
always-on prefix cacheable.

A fuller design can add lifecycle frontmatter (a stable `pattern_key` for dedup, a `severity`
that tunes decay, a `status` lifecycle with a resolution trail). Those are useful at scale, but
they are **the design you'd add**, not what the scaffold ships — add them when the corpus is big
enough to need them, not before.

## 5. Retention principle

If you do automate maintenance, one rule keeps it safe: **reads are safe to automate; writes and
deletes need a human in the loop.** The memory dir is outside git — there's no `git checkout` to
undo a bad bulk edit — so snapshot before any mutation and run such tools manually, never from a
hook or cron. And never age-sweep `feedback` (timeless lessons); only session-scoped `project`
entries should decay.

---

## 6. Honest lessons — what did *not* work

These cost real time to learn; the point of writing them down is so you skip them.

- **Git-log token matching is not a valid invalidation signal.** Scanning commit messages for
  "migrate X to Y" / "remove X" and decaying any memory that mentions X *seems* clever but
  misfires badly — a commit describes a code change, not that a lesson is stale. In the reference
  implementation it flagged the majority of memory files. Abandoned. Don't rebuild it without a
  new design and hard safety caps.
- **Auto-promotion was mathematically infeasible as designed.** Promotion needed ≥ 3 memories
  sharing one `pattern_key`, but `pattern_key` was also used as a *unique* identifier — so no key
  ever had 3 members and the cycle produced zero candidates. Every promotion that actually
  happened was a manual human decision. **The manual path is the one that works** — don't over-
  invest in automating it.

The meta-lesson: a memory system's failure mode is silent (a truncated index, a wrongly-decayed
lesson). Favor read-only health checks and manual mutation over clever automation you can't see
fail.

---

## Related

A HANDOVER is *session-scoped* working state, a different thing from these *durable* memories —
see [`session-preservation.md`](session-preservation.md) for that template and how the two
relate.

**Design influences:** Anthropic's
[memory](https://docs.claude.com/en/docs/claude-code/memory) and
[context-engineering](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)
guidance, and claudekit (MIT) — see [`../THIRD_PARTY_NOTICES.md`](../THIRD_PARTY_NOTICES.md).
