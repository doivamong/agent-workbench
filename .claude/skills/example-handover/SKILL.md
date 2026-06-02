---
name: example-handover
description: >
  WHAT: package finished work — research, a design discussion, a half-done task — into a
  self-contained handover a fresh session can execute without any of your context.
  USE WHEN: you're ending a session and want the next one (or a teammate) to pick up
  cleanly ("hand this off", "package this for next session", "write a handover",
  "research is done, move it to execution", "context is filling up, save the state").
  DO NOT TRIGGER: the work isn't finished enough to hand off (keep going, or use a
  research/plan skill first); a quick mid-task context note (just jot it down); starting
  fresh implementation right now (that's a plan-then-code skill).
tier: workflow
oversight: high
---

# Package work for a fresh session

> **Announce on activation:** "Using example-handover — I'll package this into artifacts a cold reader can execute."

The failure this prevents: a session ends with everything still in your head, and the next
session — a teammate, or you in a week — re-derives the same decisions, contradicts them, or
silently drops them. A handover is only as good as what a reader with *zero context* can do
with it. This skill **packages** what's settled; it does not re-decide it.

## Scope

- **Does:** crystallize already-made decisions and current state into artifacts a fresh
  agent can act on, and prove they're self-contained with a cold-reader test.
- **Does NOT:** re-open settled decisions (only if the cold-reader test exposes a real
  gap), do new research (use a research skill first), or start implementing (hand off to
  a plan/implement skill).

## The four artifacts

Split by *what each one answers*, so the next session reads only what it needs:

| Artifact | Answers | Holds |
|---|---|---|
| `HANDOVER.md` | "Where are we?" | State: what's done, what's in progress, key decisions **with their rationale**, and dead ends not to retry |
| `plan.md` | "What do we do?" | The ordered steps to execute, naming the files each one touches |
| `spec.md` | "What does done look like?" | Acceptance criteria — the observable contract, not the implementation |
| `NEXT_SESSION_PROMPT.md` | "How do we start?" | The literal paste-in prompt: which files to read first, the goal, the constraints |

Keep the set together (e.g. one dated folder). Scale it to the work: for a small handoff,
`HANDOVER.md` plus a prompt is enough — don't manufacture four files for a one-step task.

## Process

1. **Inventory what's settled.** Gather the decisions, the current state, and the open
   questions from this session. If there's almost nothing to package, the work isn't ready
   to hand off — stop and keep going instead.
2. **Record each decision with its *why*.** A decision without its rationale gets
   relitigated or reversed. Write what was chosen, the reason, and the alternative you
   rejected — the same three things a good research pass hands you.
3. **Redact before you write.** Artifacts get committed; a leaked secret is permanent.
   Strip credentials, tokens, internal identifiers, and absolute machine paths. (A scanner
   like `leak_scan.py` is the seatbelt here, not a substitute for reading the diff.)
4. **Emit the artifacts**, scaled to the work.
5. **HARD GATE: the cold-reader test.** Spawn a *fresh* agent with no memory of this
   session and give it only the artifacts. Ask it to state the goal, the first concrete
   action, and any decision it finds unclear. If it can't act, or flags a decision as
   ambiguous, the handover failed — fill the gap and re-test. *You* reading it is not the
   test: you have the context. The cold reader is the test.
6. **Echo the prompt inline.** Print `NEXT_SESSION_PROMPT.md` straight into the chat. The
   user runs this at the end of a long session and needs the prompt *now* — making them
   open a file to copy it out defeats the purpose.

## Banned behaviours

- Re-debating preferences or naming because you're "already here" — package, don't relitigate.
- A `NEXT_SESSION_PROMPT` that just says "continue from where we left off" — name the files
  to read, the goal, and the constraints.
- Skipping the cold-reader test because "the next agent will figure it out" — it won't have
  your context; that gap is the whole problem.
- Running the cold-reader test with a context-laden agent — it must be fresh, or the test
  proves nothing.

## Anti-rationalization

| You'll think | Reality |
|---|---|
| "The work is clear, I can skip the cold-reader test" | Clear *to you* — you hold the context. The next session doesn't. Five minutes here saves hours there. |
| "Re-stating the *why* is busywork" | A decision without its reason is reopened by default the moment someone disagrees with it. |
| "One file is fine for everything" | For a one-step task, yes. For multi-step work, the next session wastes time mining one blob for the prompt, the plan, and the contract. |
| "It's a draft, I'll redact later" | The draft gets committed. Secrets leak permanently. Redact before you write, not after. |
