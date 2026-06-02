# Session Context Preservation — a reference design

> **What ships vs. what this describes.** Agent Workbench now ships the **automatic layers** as
> fail-open hooks: a PreCompact transcript backup
> ([`precompact_backup.py`](../.claude/hooks/scripts/precompact_backup.py)), a post-compact
> restore that re-injects the latest handover excerpt
> ([`compact_restore.py`](../.claude/hooks/scripts/compact_restore.py)), and a context-budget
> nudge ([`context_tracker.py`](../.claude/hooks/scripts/context_tracker.py)), and a session-end
> breadcrumb ([`session_end.py`](../.claude/hooks/scripts/session_end.py)) the next SessionStart
> surfaces as a one-line "Last session: …" — wire them via
> [`install.py`](../install.py) or the `.claude/settings.json` snippet. It does **not** ship the
> `/session-save` or `/catchup` **commands** or the tiered-restore *workflow*; those, and the
> HANDOVER you write by hand, stay manual (the command names below are *the commands you would
> create*). The reusable core to copy is the **HANDOVER template** and the three-layer shape.

The problem it solves: an agent's working context is easy to lose, and re-establishing it is
expensive. Three common ways it goes:

| Scenario | Cause | Consequence |
|:---------|:------|:------------|
| **Account switch** (quota exhausted) | The old session can't resume under a new account | Conversation history gone |
| **Context window full** | Auto-compaction summarizes and drops nuance | The agent "forgets" decisions, repeats work |
| **New session** | Fresh context, nothing carried over | You re-explain everything |

---

## The design: three layers

```
Layer 3 — Tiered restore (on demand)
   quick   : git diff + log            (~5 s)   — short break, same account
   restore : + a saved HANDOVER        (~15 s)  — account switch / new session
   full    : + parse a transcript copy (~30-60 s) — reconstruct an old session
Layer 2 — Structured handover (you trigger it)
   Write a HANDOVER capturing goal, decisions + WHY, failed approaches, next steps.
Layer 1 — Automatic safety net (a PreCompact hook)
   Back up the transcript before every compaction, so nothing is lost even if you
   forgot to save.
```

The three layers are independent — you can adopt only the HANDOVER template (Layer 2) and skip
the hooks, or wire all three. Layer 1 is the only fully automatic piece; the rest are explicit.

---

## The HANDOVER template (the reusable core)

This is the part worth copying verbatim. A HANDOVER is a single Markdown file; every section is
optional — skip the ones with no content. The two that pay for the whole format are **decisions
*with WHY*** and **failed approaches** — they are what a fresh session can't reconstruct from a
diff.

```markdown
# Session Handover — YYYY-MM-DD HH:MM

## Goal               — the session's main objective
## Completed          — work finished, with file paths
## In Progress        — work underway, current state
## Key Decisions (with WHY)   — Decision: the reason it was made
## Failed Approaches (DO NOT retry)  — what was tried: why it failed
## Active Plan        — plan file or summary
## Open Questions     — unresolved
## Next Steps (priority order)  — 1. the concrete next action (start here)
## Files Changed      — git diff --stat
## Context for Next Session  — branch state, test status, config changes
```

Store HANDOVERs outside version control (gitignore them) — they are short-lived working state
and can contain in-progress detail you don't want committed. Keep a few most-recent ones and
let older ones age out.

---

## Make the handover survive a cold read

A handover is only worth writing if the next session can *act* on it without you. Two checks keep
it honest.

**The Cold Reader Test.** Before you rely on a handover, read it as if you've never seen this work —
no memory of the session, only the file. If a fresh reader would need **more than one** clarifying
question to take the next step, the handover has a gap — fix it now, while you still have the context
to. Passing this test is the bar for "done"; failing it means it's still a draft.

**A severity-graded integrity check.** Not every gap costs the same. Grade a missing piece by what
it does to the next reader:

| Missing | Severity | Why it hurts |
|---|---|---|
| the **next concrete step** ("start here") | blocking | the reader doesn't know where to begin |
| a **decision's WHY** | high | the reader re-litigates a settled call, or silently undoes it |
| a **failed approach** | high | the reader burns time re-trying a dead end |
| file paths / branch / test state | medium | recoverable from git, but slows the restart |
| wording, formatting | low | cosmetic |

Block on the blocking row; fix the high rows before you stop; let the low ones go.

**Update by merging, not regenerating.** When you revise a handover mid-work, edit its existing
sections in place — don't regenerate the whole file from the current context. A regenerate quietly
drops the hard-won detail (an early decision, a failed approach) that the live context has already
compacted away. Anchor on the sections and accumulate into them.

---

## Restore tiers — the depth/speed trade-off

Reading everything every time is wasteful; match the restore depth to the situation.

| Tier | Reads | Speed | Fidelity | Use when |
|:-----|:------|:------|:---------|:---------|
| **Quick** | git diff + log | ~5 s | low | short break, same account |
| **Standard** | + the latest HANDOVER | ~15 s | high | account switch, new session |
| **Full** | + a transcript copy | ~30–60 s | highest | reconstructing an old session |

---

## How it's wired

The automatic layers ship as three hooks (all fail-open via
[`hook_logger.py`](../.claude/hooks/lib/hook_logger.py), so a crash in any never wedges your
session):

- **PreCompact** → [`precompact_backup.py`](../.claude/hooks/scripts/precompact_backup.py):
  copies the transcript before compaction and drops a `.last_compact` signal file (Layer 1).
- **SessionStart[compact]** → [`compact_restore.py`](../.claude/hooks/scripts/compact_restore.py):
  on the post-compaction restart, if the signal is recent it re-injects the top of the newest
  HANDOVER so the agent resumes with goal/decisions/next-steps (Layer 2's automatic half).
- **PostToolUse** → [`context_tracker.py`](../.claude/hooks/scripts/context_tracker.py): nudges
  you to `/compact` or save a handover once a session gets long, before limits hit unexpectedly.
- **SessionEnd** → [`session_end.py`](../.claude/hooks/scripts/session_end.py): on session end,
  writes a one-line breadcrumb (git branch, last commit, uncommitted count, time). The next
  session's **SessionStart** ([`session_start.py`](../.claude/hooks/scripts/session_start.py))
  reads a recent one and injects a "Last session: …" line — automatic, lightweight orientation
  between sessions. It complements, never replaces, a hand-written HANDOVER (a breadcrumb, not a
  replay: it has no goal/decisions and reflects git state at the moment the session ended).

Still manual (by design): writing the HANDOVER itself, and a **save command/skill** that gathers
`git diff`/`log` + your plan state into the template above. Kill switches: `PRECOMPACT_BACKUP=0`,
`COMPACT_RESTORE=0`, `CONTEXT_TRACKER=0`, `SESSION_BREADCRUMB=0`.

---

## Limitations (be honest about these)

- **Manual save is the weak link.** If quota runs out before you save, only the automatic
  transcript backup (Layer 1) survives — that's a raw copy, not a structured HANDOVER.
- **Quality tracks context health.** A HANDOVER written from an already heavily-compacted
  context is less accurate. **Save early, while context is still clear** — don't wait for the
  compaction warning.
- **A handover is a summary, not a replay.** Fine-grained nuance is lost by design; that's the
  trade for a cheap, fast restore.
- **Local and short-lived.** HANDOVERs live on one machine and age out. To move work across
  machines, copy the file deliberately.

## Relationship to long-term memory

This is **not** the [`memory/`](../memory/) system. A HANDOVER holds *session-specific* state
(what I was doing, what's next) and is short-lived; a memory file holds a *durable* lesson worth
recalling on unrelated future sessions. When a session ends, a one-off "what's next" goes in a
HANDOVER; a reusable insight gets promoted to a memory file (see
[`memory-governance.md`](memory-governance.md)). They complement each other; neither replaces
the other.
