---
name: awb-handover
description: >
  WHAT: package finished work — research, a design discussion, a half-done task — into a
  self-contained handover a fresh session can execute without any of your context.
  USE WHEN: you're ending a session and want the next one (or a teammate) to pick up
  cleanly ("hand this off", "package this for next session", "write a handover",
  "research is done, move it to execution", "context is filling up, save the state").
  DO NOT TRIGGER: the work isn't finished enough to hand off (keep going, or use a
  research/plan skill first); a quick mid-task context note (just jot it down); starting
  fresh implementation right now (that's a plan-then-code skill); you'll resume THIS same
  conversation later (its history comes back — a handover earns its keep only for a reader
  that starts COLD: a new/cleared session, a teammate, or another machine).
tier: workflow
oversight: high
---

# Package work for a cold next session

> **Announce on activation:** "Using awb-handover — I'll package this into artifacts a cold reader can execute."

The failure this prevents: a session ends with everything still in your head, and the next
session — a teammate, or you in a week — re-derives the same decisions, contradicts them, or
silently drops them. A handover is only as good as what a reader with **none of *this
session's* context** — no conversation history, no files you read, no decisions you reached
out loud — can do with it. (That reader still auto-loads the committed `CLAUDE.md` and project
rules, but those are *soft* context, not enforced — so restate any load-bearing constraint in
the artifacts anyway. Project memory (`MEMORY.md`) is machine-local and does **not** travel to
a teammate or another machine, so anything load-bearing that lives only there must go in the
artifacts too.) This skill **packages** what's settled; it does not re-decide it.

## Scope

- **Targets a COLD reader:** a brand-new or cleared session, a teammate, or another machine —
  one that does NOT carry this conversation forward. If the same conversation will simply be
  restored later, the history comes back and a handover adds little.
- **Does:** crystallize already-made decisions and current state into artifacts a fresh
  agent can act on, and prove they're self-contained with a cold-reader test.
- **Does NOT:** re-open settled decisions (only if the cold-reader test exposes a real
  gap), do new research (use a research skill first), or start implementing (hand off to
  a plan/implement skill).

## The four artifacts

Split by *what each one answers*, so the next session reads only what it needs:

| Artifact | Answers | Holds |
|---|---|---|
| `HANDOVER.md` | "Where are we?" | State: what's done, what's in progress, key decisions **with their rationale**, dead ends not to retry, and — if blocked — the blocker. Stamp it: the date + the base commit at handover time |
| `plan.md` | "What do we do?" | The ordered steps to execute, naming the files each one touches |
| `spec.md` | "What does done look like?" | Acceptance criteria — the observable contract, not the implementation |
| `NEXT_SESSION_PROMPT.md` | "How do we start?" | The literal paste-in prompt: which files to read first, the goal, the constraints. First line: "git fetch and confirm <files> haven't changed since <base commit>; if they have, re-validate the plan." It points AT the plan/spec (when they exist) — it does not duplicate the steps |

Write the set to a worktree-local artifact folder (the gitignored `handovers/<date>/`): it
survives session close with no commit, but it does **not** travel to another worktree or
machine. Scale it to the work: for a small handoff, `HANDOVER.md` plus a prompt is enough —
don't manufacture four files for a one-step task. Scaling down drops *artifacts*, never the
cold-reader test (step 5 is a HARD GATE at every size). Scale UP too: for large state, keep
`HANDOVER.md` a short index and link out to supporting artifacts (a captured diff, a file
inventory, a decision log) rather than inlining one unreadable blob — and redact linked
artifacts too (a raw captured diff is the easiest place for a path or token to ride in).

## Process

1. **Inventory what's settled.** Gather the decisions, the current state, and the open
   questions from this session. Ground each decision's rationale in disk artifacts (git diff,
   the actual files, any plan/research notes), not in recalled conversation — if context has
   compacted, the verbatim "why" may already be gone; a rationale you cannot re-derive from
   disk is a gap to flag, not to invent. If there's almost nothing to package, the work isn't
   ready to hand off — stop and keep going instead. (A *blocked* task IS ready: it's finished
   enough to package the blocker — record the precise blocker, what was tried and ruled out,
   and the condition that unblocks it; `plan.md` then starts from the unblock step.)
2. **Record each decision with its *why*.** A decision without its rationale gets
   relitigated or reversed. Write what was chosen, the reason, and the alternative you
   rejected — the same three things a good research pass hands you.
3. **Redact before you write.** Artifacts outlive your control — they get committed, pasted
   into chat, mailed to a teammate, or moved into a tracked location later; a leaked secret in
   any of those is permanent. Strip credentials, tokens, internal identifiers, and absolute
   machine paths, regardless of whether the dir is git-tracked. (`leak_scan.py` is the seatbelt
   — run it deliberately on the artifacts, it does not auto-fire on a gitignored dir — not a
   substitute for reading the diff: a green scan misses brand/namespace identifiers used as
   code prefixes, paid-product references, and example machine paths.)
4. **Emit the artifacts**, scaled to the work.
5. **HARD GATE: the cold-reader test.** A reader isolated from this conversation must be able
   to act on the artifacts alone.
   - **Run it cold.** The surest cold read is a SEPARATE, brand-new session reading only the
     artifacts (or a teammate). For an in-session spawn, use a *named* isolated agent (e.g. an
     Explore-style agent) — not a fork. Beware fork mode (some harness versions spawn a fork
     in place of the general-purpose subagent; a fork inherits this whole conversation and will
     pass for the wrong reason). Quick check: have the tester first state what it can see — if
     it references any session decision you did NOT put in the artifacts, it's context-laden;
     discard the result.
   - **Deliver the artifacts the only way a spawned agent receives them — its prompt string.**
     Paste the artifact CONTENTS inline, or pass ABSOLUTE paths to this worktree's folder; a
     relative path won't resolve for an agent rooted in another worktree, and a gitignored
     folder written elsewhere won't be checked out into its tree. Pass nothing from this
     conversation but those files.
   - **Ask** it to state the goal, the first concrete action, and any decision it finds unclear.
     **PASS** = it states the goal correctly, names a first action matching your intent, and
     flags zero load-bearing decisions as ambiguous. On failure, fill the specific gap *in the
     artifacts* (don't relitigate settled preferences) and re-test. If a re-test keeps exposing
     new gaps, that's the signal the work isn't settled enough to hand off — stop and return to
     research/plan, or hand off the OPEN QUESTION explicitly rather than a false-settled decision.
   - **Fallback (weaker — label it).** If you genuinely cannot spawn an isolated agent (e.g.
     you're already inside a subagent — subagents can't spawn subagents — or the harness offers
     no isolated fan-out), read ONLY the artifact files in a scratch pass and answer the three
     questions without drawing on this conversation. This deliberately reintroduces the
     self-grading bias the gate exists to avoid, so use it only when no isolated agent exists,
     prefer the real spawn whenever available, and say you used it.
6. **Print the prompt inline.** Print `NEXT_SESSION_PROMPT.md` straight into the chat — it is
   the already-redacted artifact, so paste it as written. The user runs this at the end of a
   long session and needs the prompt *now*; making them open a file to copy it out defeats the
   purpose.

## Banned behaviours

- Re-debating preferences or naming because you're "already here" — package, don't relitigate.
- A `NEXT_SESSION_PROMPT` that just says "continue from where we left off" — name the files
  to read, the goal, and the constraints.
- Skipping the cold-reader test because "the next agent will figure it out" — it won't have
  your context; that gap is the whole problem.
- Running the cold-reader test with a context-laden agent — including a fork (or any agent
  that inherited this conversation): a fork sees the full session and will pass a handover a
  real cold reader could not act on, so the test proves nothing.

## Anti-rationalization

| You'll think | Reality |
|---|---|
| "The work is clear, I can skip the cold-reader test" | Clear *to you* — you hold the context. The next session doesn't. Five minutes here saves hours there — and the test is not optional at any size. |
| "Re-stating the *why* is busywork" | A decision without its reason is reopened by default the moment someone disagrees with it. |
| "One file is fine for everything" | For a one-step task, yes — but still run the cold-reader test. For multi-step work, the next session wastes time mining one blob for the prompt, the plan, and the contract. |
| "It's a draft, I'll redact later" | A draft gets committed, pasted, or mailed — secrets leak permanently from any of those. Redact before you write, not after. |
| "It's gitignored, so it won't leak / the cold reader will see it" | Gitignored ≠ safe (it still gets quoted, pasted, mailed) and ≠ shared (a spawned agent in another worktree won't see it). Redact anyway; deliver by absolute path or inline. |
