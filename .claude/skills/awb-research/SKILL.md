---
name: awb-research
description: >
  WHAT: understand a problem before building — scope it, read the actual code, compare
  at least two approaches, then recommend one with reasons.
  USE WHEN: a non-trivial change where the approach isn't obvious ("how should we...",
  "what's the best way to...", "look into X before we build it", "which option...").
  DO NOT TRIGGER: a vague *request* that needs clarifying first (that's prompt-refiner);
  executing an already-chosen approach (that's a plan-then-code skill); a known one-line fix.
tier: workflow
---

# Research before building

> **Announce on activation:** "Using awb-research — I'll read the code and compare options before recommending."

The expensive mistake is committing to an approach you picked before you understood the terrain.
This skill forces *understand → compare → decide*, on evidence, before any plan or code.

## Process

1. **Zoom out first.** Before diving into one file, go up one layer: what module owns this, who
   calls it, where does the data come from and go? A quick map of the neighbourhood stops you
   solving the wrong problem in the right file. Don't deep-read yet — orient.
2. **Scope.** State the question in one sentence and the constraints that actually bind (perf,
   compatibility, deadline, the existing stack). An approach that ignores a real constraint is noise.
3. **Explore — read the real code.** Read the relevant code and configuration *as it is now*, not
   as you remember or assume it. Note what exists already (a helper, a pattern, a prior decision)
   so you don't reinvent or contradict it.
4. **HARD GATE: at least two approaches, in a table.** Do not recommend until you have compared
   ≥ 2 concrete options across the dimensions that matter (effort, risk, fit with existing code,
   reversibility). One option is not a comparison — it's a foregone conclusion dressed up.

   | Approach | Effort | Risk | Fits existing code? | Reversible? |
   |---|---|---|---|---|
   | A — … | … | … | … | … |
   | B — … | … | … | … | … |

5. **Recommend one, with the reason and the trade-off you accept.** Name the option, why it wins
   *given the constraints*, and what you're giving up by not picking the runner-up. Then hand off
   to a plan/implement skill — research stops at the decision, it doesn't build.

## Banned behaviours

- Proposing an approach **before** reading the code it touches ("I'd probably use X") — that's a
  guess wearing a recommendation's clothes.
- A "comparison" with one real option and a strawman.
- Recommending without naming the trade-off you're accepting.

## Anti-rationalization

| You'll think | Reality |
|---|---|
| "I already know how this codebase works" | Memory drifts; the code is the source of truth. A 5-minute read beats a confident wrong assumption. |
| "There's obviously only one way" | If it's truly obvious, the comparison takes two minutes and confirms it. If it's not, you just dodged a rebuild. |
| "Comparing is slower than just building" | Building the wrong approach and reversing it is the slow path. The table is the cheap one. |
