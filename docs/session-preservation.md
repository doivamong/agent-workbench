# Session Context Preservation — a reference design

> **This is a blueprint, not a shipped feature.** Agent Workbench does **not** ship the
> `/session-save` or `/catchup` commands, the context tracker, or the restore hooks described
> below. What ships in this repo is the *fail-open hook architecture*
> ([`.claude/hooks/lib/hook_logger.py`](../.claude/hooks/lib/hook_logger.py)) and the
> cross-session [`memory/`](../memory/) scaffold. This page is the **design** — the patterns and
> the HANDOVER template — so you (or future-you on a new project) can build your own version
> without re-deriving it. Treat the command names here as *the commands you would create*, not
> ones you can run today.

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

## Restore tiers — the depth/speed trade-off

Reading everything every time is wasteful; match the restore depth to the situation.

| Tier | Reads | Speed | Fidelity | Use when |
|:-----|:------|:------|:---------|:---------|
| **Quick** | git diff + log | ~5 s | low | short break, same account |
| **Standard** | + the latest HANDOVER | ~15 s | high | account switch, new session |
| **Full** | + a transcript copy | ~30–60 s | highest | reconstructing an old session |

---

## How you'd wire it (sketch)

If you implement the automatic layers, the moving parts are:

- A **PreCompact hook** that copies the transcript before compaction and drops a small signal
  file — this is Layer 1, the safety net. (Backlog item for this repo; not shipped yet.)
- A **SessionStart hook** that, on a new session, notices a recent HANDOVER and suggests
  restoring it.
- An optional **PostToolUse counter** that nudges you to save after N tool calls, before quota
  or context limits hit unexpectedly.
- A **save command/skill** that gathers `git diff`/`log` + your plan/todo state and writes the
  HANDOVER above.

Wrap every hook fail-open (see [`hook_logger.py`](../.claude/hooks/lib/hook_logger.py)) so a
crash in any of them never wedges your session.

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
