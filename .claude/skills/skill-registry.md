# Skill Registry

A single, greppable index of every skill: one row per skill with its tier and its
trigger / anti-trigger summary. The point is that a future session (or a tired you) can
`grep` this one file to see the whole library at a glance, instead of opening 30 folders.

> This is a from-first-principles index format. Keep it deliberately simple — name, tier,
> when it fires, when it must not. Resist adding columns you won't maintain.

## How to use it

- Add a row the moment you create a skill; delete the row when you archive one.
- When two skills feel like they overlap, the **Do-not-trigger** column is where you write
  the boundary that separates them.
- Treat this file as the source of truth; if a skill's `SKILL.md` description drifts from
  its row here, fix one to match the other.

## Conflict resolution (write your rule down)

When more than one skill could match a request:

1. **Workflow > Guard > Feature > Audit** (tier precedence).
2. A **domain-specific rule beats a general one** when they disagree.
3. If still ambiguous, the agent should ask rather than guess.

## Registry

| Skill | Tier | Fires when (triggers) | Does NOT fire when |
|-------|------|------------------------|--------------------|
| `example-plan-then-code` | workflow | "implement X", "add feature", anything multi-file that needs a plan first | a one-line fix; a pure question; a code review |
| `example-review` | guard | "review my changes", before a commit/merge of a non-trivial change | general "is my whole codebase good?" audits; research questions |
| `example-debug` | guard | "it's broken / erroring / wrong / crashing" with an unknown cause | a known one-line fix; a feature; a code review |
| `prompt-refiner` | workflow | a vague, multi-part request (the `prompt-refiner-inject.py` hook flags these) | an already-specific request; a trivial one-liner |
| `example-research` | workflow | "how should we / what's the best way", comparing approaches, understanding a module before a non-trivial change | a vague request to clarify (that's prompt-refiner); executing an already-chosen approach; a one-line fix |
| `example-handover` | workflow | ending a session, "hand this off / package for next session / write a handover", research-done-move-to-execution | work not finished enough to hand off; a quick mid-task note; starting fresh implementation now |
| `example-stress-test` | workflow | "stress test this / poke holes in this plan / what could go wrong / edge cases / is this design sound", before building or testing something non-trivial | a one-line / low-risk change; comparing approaches (research); reviewing code already written (review); a known bug (debug) |
| `example-output-guard` | guard | generating a whole file / large template / big refactor | a small edit to an existing file; a question; prose-only output |
| `example-using-skills` | meta | auto-injected each session; also when ≥2 skills could match, or you're unsure any applies | as a destination — it routes TO other skills, never does the work itself |
| `example-config-guard` | guard | writing/modifying code that reads config — esp. a nested key or a cross-context read | reading config once to understand it; a single non-nested constant |
| _your-ui-guide_ | feature | designing or editing the UI | backend performance work |
| _your-dead-code-audit_ | audit | "find unused code", post-refactor cleanup | "this function is too long" (that's a structural-size concern) |

Replace the placeholder rows with your real skills. The ten non-placeholder rows correspond to
the runnable example skills in this folder (five workflows + four guards + one meta routing skill).
